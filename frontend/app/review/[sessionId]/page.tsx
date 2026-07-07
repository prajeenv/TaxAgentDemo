"use client";

import { use, useCallback, useEffect, useState } from "react";

import { api, SessionSnapshot } from "@/app/lib/api";
import {
  ESCALATION_META,
  FIELD_META,
  MARITAL_OPTIONS,
} from "@/app/lib/profileMeta";

// The consultant review surface (design spec §1). Three panes: editable profile,
// the determination result, and the conversation + escalation log. Editing a
// profile field PATCHes the backend and the document list recomputes live — the
// proof that the ruleset is deterministic AND editable.

export default function ReviewPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = use(params);
  const [snap, setSnap] = useState<SessionSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [edited, setEdited] = useState<Set<string>>(new Set());
  const [savingField, setSavingField] = useState<string | null>(null);
  const [recomputeNote, setRecomputeNote] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSession(sessionId)
      .then(setSnap)
      .catch((e) => setError(String(e)));
  }, [sessionId]);

  const patch = useCallback(
    async (field: string, value: unknown) => {
      if (!snap) return;
      setSavingField(field);
      const before = countDocs(snap);
      try {
        const next = await api.patchProfile(sessionId, { [field]: value });
        setSnap(next);
        setEdited((prev) => new Set(prev).add(field));
        const after = countDocs(next);
        setRecomputeNote(recomputeSummary(before, after));
        setTimeout(() => setRecomputeNote(null), 4000);
      } catch (e) {
        setError(String(e));
      } finally {
        setSavingField(null);
      }
    },
    [snap, sessionId],
  );

  const approve = useCallback(async () => {
    if (!snap) return;
    if (
      !window.confirm(
        `Unterlagenliste für Mandant #${shortId(sessionId)} freigeben? Die bestätigte Liste wird dem Mandanten per E-Mail zugesandt.`,
      )
    )
      return;
    try {
      setSnap(await api.approve(sessionId));
    } catch (e) {
      setError(String(e));
    }
  }, [snap, sessionId]);

  if (error)
    return (
      <main className="p-10 text-warn">
        Fehler beim Laden der Sitzung: {error}
      </main>
    );
  if (!snap) return <main className="p-10 text-ink-2">Laden…</main>;

  const t = snap.tracker_state;
  const requiredByGroup = groupBy(t.required, (d) => d.group);

  return (
    <main className="min-h-screen bg-paper">
      {/* Top bar */}
      <header className="flex items-center justify-between border-b border-line bg-surface px-5 py-3">
        <div className="flex items-center gap-3 text-sm">
          <span className="font-serif text-base font-semibold">Kanzlei</span>
          <span className="text-ink-2">·</span>
          <span className="text-ink-2">Mandant #{shortId(sessionId)}</span>
          <span className="text-ink-2">·</span>
          <span className="text-ink-2">
            Steuerjahr {(snap.profile.tax_years as number[])?.join(", ") || "—"}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <StatusPill snap={snap} />
          <button
            className="k-btn-primary"
            disabled={snap.approved}
            onClick={approve}
          >
            {snap.approved ? "Freigegeben" : "Freigeben"}
          </button>
        </div>
      </header>

      {recomputeNote && (
        <div className="border-b border-line bg-brand-tint px-5 py-1.5 text-xs text-brand">
          {recomputeNote}
        </div>
      )}

      {/* Three panes */}
      <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-[280px_1fr_300px]">
        {/* A: Profile */}
        <section className="k-card p-4">
          <h2 className="k-section-header mb-3">Profil</h2>
          {(["Grunddaten", "Bedingungen"] as const).map((grp) => (
            <div key={grp} className="mb-4">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-2/70">
                {grp}
              </div>
              <div className="space-y-2.5">
                {FIELD_META.filter((f) => f.group === grp).map((f) => (
                  <ProfileField
                    key={f.key}
                    meta={f}
                    value={(snap.profile as Record<string, unknown>)[f.key]}
                    edited={edited.has(f.key)}
                    saving={savingField === f.key}
                    onChange={(v) => patch(f.key, v)}
                    disabled={snap.approved}
                  />
                ))}
              </div>
            </div>
          ))}
        </section>

        {/* B: Determination result */}
        <section className="space-y-4">
          <div className="k-card p-4">
            <h2 className="k-section-header mb-3">
              Benötigte Unterlagen
              <span className="k-count">{t.required.length}</span>
            </h2>
            {t.required.length === 0 && (
              <p className="text-sm text-ink-2">
                Noch keine Unterlagen bestimmt.
              </p>
            )}
            {Object.entries(requiredByGroup).map(([group, docs]) => (
              <div key={group} className="mb-3 last:mb-0">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-2/70">
                  {group}
                </div>
                {docs.map((d) => (
                  <div
                    key={d.id}
                    className="animate-enterFlash flex items-start justify-between gap-2 border-b border-line py-2 last:border-0"
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-sm">{d.label}</span>
                      {d.refine_flag && (
                        <span
                          className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-1.5 py-0.5 text-[11px] text-pending"
                          title="Dieses Bündel ist bewusst vollständig gehalten; Feinabgrenzung folgt durch Sie."
                        >
                          ⚑ verfeinern
                        </span>
                      )}
                    </div>
                    <div className="flex shrink-0 gap-1">
                      {d.source_rule_ids.map((rid) => (
                        <span
                          key={rid}
                          className="rounded-full border border-line px-1.5 py-0.5 font-mono text-[11px] text-ink-2"
                          title={rid}
                        >
                          {ruleLabel(rid)}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>

          <CollapsibleList
            title="Trifft nicht zu"
            count={t.excluded.length}
            items={t.excluded.map((x) => ({
              key: x.rule_id,
              primary: x.condition_label,
              secondary: x.reason,
            }))}
          />
          <CollapsibleList
            title="Entscheidungen ausstehend"
            count={t.pending.length}
            items={t.pending.map((x) => ({
              key: x.rule_id,
              primary: x.condition_label,
              secondary: x.triggering_question,
            }))}
          />

          {t.refine_flags.length > 0 && (
            <div className="k-card border-pending/30 bg-amber-50/40 p-4">
              <h2 className="k-section-header mb-2 text-pending">
                Zu verfeinern
                <span className="k-count bg-amber-100 text-pending">
                  {t.refine_flags.length}
                </span>
              </h2>
              <p className="mb-3 text-sm text-ink-2">
                Das vollständige Unterlagen-Bündel ist hinterlegt. Die Fein-Abfrage
                (welche Unterlagen genau je nach Fall) ist noch zu ergänzen. Bitte
                prüfen und verfeinern.
              </p>
              {t.refine_flags.map((rf) => (
                <div key={rf.rule_id} className="border-t border-line py-2">
                  <div className="text-sm font-medium">
                    {rf.label} — Unter-Logik als Stub hinterlegt
                  </div>
                  {rf.note && (
                    <div className="text-xs text-ink-2">{rf.note}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* C: Conversation + escalation log */}
        <section className="space-y-4">
          <div className="k-card p-4">
            <h2 className="k-section-header mb-3">Gespräch</h2>
            {snap.messages.length === 0 && (
              <p className="text-sm text-ink-2">Noch kein Gespräch geführt.</p>
            )}
            <div className="space-y-2">
              {snap.messages.map((m, i) => (
                <div key={i} className="text-sm">
                  <span
                    className={
                      m.role === "assistant"
                        ? "font-medium text-brand"
                        : "font-medium text-ink-2"
                    }
                  >
                    {m.role === "assistant" ? "Agent" : "Klient"}:
                  </span>{" "}
                  <span>{m.text}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="k-card p-4">
            <h2 className="k-section-header mb-3">
              Eskalationen
              <span className="k-count">{snap.escalation_log.length}</span>
            </h2>
            {snap.escalation_log.length === 0 && (
              <p className="text-sm text-ink-2">
                Keine Eskalationen in diesem Gespräch.
              </p>
            )}
            <div className="space-y-2">
              {[...snap.escalation_log].reverse().map((e, i) => {
                const meta = ESCALATION_META[e.category];
                return (
                  <div key={i} className="border-t border-line pt-2 first:border-0 first:pt-0">
                    <div className="mb-1 flex items-center gap-2">
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-medium ${meta?.className ?? ""}`}
                      >
                        {meta?.label ?? e.category}
                      </span>
                      <span className="text-[11px] text-ink-2">
                        Turn {e.turn_index}
                      </span>
                    </div>
                    <div className="text-sm italic text-ink-2">
                      „{e.client_utterance}"
                    </div>
                    <div className="mt-0.5 text-xs text-ink-2">
                      {meta?.gloss ?? e.reason}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

// --- Sub-components ---------------------------------------------------------

function ProfileField({
  meta,
  value,
  edited,
  saving,
  onChange,
  disabled,
}: {
  meta: (typeof FIELD_META)[number];
  value: unknown;
  edited: boolean;
  saving: boolean;
  onChange: (v: unknown) => void;
  disabled: boolean;
}) {
  return (
    <div className={edited ? "border-l-2 border-brand pl-2" : "pl-2"}>
      <div className="mb-1 flex items-center gap-1.5">
        <label className="text-xs text-ink-2">{meta.label}</label>
        {edited && (
          <span className="rounded-full bg-brand-tint px-1.5 text-[10px] text-brand">
            geändert
          </span>
        )}
        {saving && <span className="text-[10px] text-ink-2">…</span>}
      </div>
      {meta.control === "tristate" && (
        <TriState
          value={value as boolean | null}
          disabled={disabled}
          onChange={onChange}
        />
      )}
      {meta.control === "marital" && (
        <select
          className="w-full rounded-md border border-line bg-surface px-2 py-1 text-sm"
          value={(value as string) ?? ""}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value || null)}
        >
          <option value="">— nicht gefragt</option>
          {MARITAL_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
      {meta.control === "children" && (
        <Stepper
          value={(value as unknown[])?.length ?? 0}
          disabled={disabled}
          onChange={(n) =>
            onChange(Array.from({ length: n }, () => ({ age: null })))
          }
        />
      )}
      {meta.control === "taxyears" && (
        <div className="text-sm">
          {((value as number[]) ?? []).join(", ") || "—"}
        </div>
      )}
    </div>
  );
}

function TriState({
  value,
  disabled,
  onChange,
}: {
  value: boolean | null;
  disabled: boolean;
  onChange: (v: boolean | null) => void;
}) {
  const opts: { v: boolean | null; label: string }[] = [
    { v: true, label: "Ja" },
    { v: false, label: "Nein" },
    { v: null, label: "— nicht gefragt" },
  ];
  return (
    <div className="inline-flex overflow-hidden rounded-md border border-line">
      {opts.map((o) => {
        const active = value === o.v;
        const isNull = o.v === null;
        return (
          <button
            key={String(o.v)}
            disabled={disabled}
            onClick={() => onChange(o.v)}
            className={`px-2.5 py-1 text-xs transition-colors ${
              active
                ? isNull
                  ? "border-dashed bg-transparent text-ink-2"
                  : "bg-brand text-white"
                : "bg-surface text-ink-2 hover:bg-brand-tint"
            } ${isNull ? "border-l border-dashed border-line" : "border-l border-line first:border-0"}`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function Stepper({
  value,
  disabled,
  onChange,
}: {
  value: number;
  disabled: boolean;
  onChange: (n: number) => void;
}) {
  return (
    <div className="inline-flex items-center gap-2">
      <button
        className="rounded-md border border-line px-2 text-sm disabled:opacity-40"
        disabled={disabled || value <= 0}
        onClick={() => onChange(value - 1)}
      >
        −
      </button>
      <span className="w-6 text-center text-sm tabular-nums">{value}</span>
      <button
        className="rounded-md border border-line px-2 text-sm disabled:opacity-40"
        disabled={disabled}
        onClick={() => onChange(value + 1)}
      >
        +
      </button>
    </div>
  );
}

function CollapsibleList({
  title,
  count,
  items,
}: {
  title: string;
  count: number;
  items: { key: string; primary: string; secondary: string }[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="k-card p-4">
      <button
        className="k-section-header w-full"
        onClick={() => setOpen((o) => !o)}
      >
        <span>
          {title}
          <span className="k-count">{count}</span>
        </span>
        <span className="text-ink-2">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="mt-2 space-y-1.5">
          {items.map((it) => (
            <div key={it.key} className="border-b border-line py-1.5 last:border-0">
              <div className="text-sm text-ink-2">{it.primary}</div>
              <div className="text-xs text-ink-2/70">{it.secondary}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusPill({ snap }: { snap: SessionSnapshot }) {
  const label = snap.approved
    ? "Freigegeben"
    : snap.complete
      ? "Bereit zur Prüfung"
      : "In Bearbeitung";
  const color = snap.approved
    ? "text-brand"
    : snap.complete
      ? "text-pending"
      : "text-ink-2";
  return (
    <span className={`flex items-center gap-1.5 text-sm ${color}`}>
      <span className="text-xs">●</span>
      {label}
    </span>
  );
}

// --- Helpers ----------------------------------------------------------------

function shortId(id: string): string {
  return id.slice(0, 4).toUpperCase();
}

function ruleLabel(ruleId: string): string {
  // "r4_rental" -> "Regel 4"
  const m = ruleId.match(/^r(\d+)/);
  return m ? `Regel ${m[1]}` : ruleId;
}

function groupBy<T>(items: T[], key: (t: T) => string): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const it of items) (out[key(it)] ??= []).push(it);
  return out;
}

function countDocs(snap: SessionSnapshot): number {
  return snap.tracker_state.required.length;
}

function recomputeSummary(before: number, after: number): string {
  const delta = after - before;
  if (delta === 0) return "Liste neu berechnet — keine Änderung an den Unterlagen.";
  if (delta > 0)
    return `Liste neu berechnet — ${delta} Unterlage(n) hinzugefügt.`;
  return `Liste neu berechnet — ${-delta} Unterlage(n) entfernt.`;
}
