"use client";

import { useEffect, useRef, useState } from "react";

import { TrackerState } from "@/app/lib/api";

// The client-facing DocumentTracker (design spec §2) — the demo centerpiece.
// Three stacked sections that narrow live as the conversation flows. Framed
// PROVISIONAL throughout; refine flags and rule provenance are stripped (those are
// consultant-internal). Items flash on entry; excluded is collapsed by default.

function groupBy<T>(items: T[], key: (t: T) => string): Record<string, T[]> {
  const out: Record<string, T[]> = {};
  for (const it of items) (out[key(it)] ??= []).push(it);
  return out;
}

export function DocumentTracker({
  tracker,
  complete,
}: {
  tracker: TrackerState;
  complete: boolean;
}) {
  const requiredByGroup = groupBy(tracker.required, (d) => d.group);

  return (
    <aside className="flex h-full flex-col">
      <header className="border-b border-line px-4 py-3">
        <div className="flex items-baseline gap-2">
          <h2 className="font-serif text-base font-semibold">Ihre Unterlagen</h2>
          <span className="text-xs text-ink-2">(vorläufig)</span>
        </div>
        <p className="text-xs text-ink-2">
          Stand: während des Gesprächs — noch nicht bestätigt.
        </p>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {/* BENÖTIGT */}
        <section>
          <div className="k-section-header mb-2 text-brand">
            <span>
              Benötigt
              <span className="k-count">{tracker.required.length}</span>
            </span>
          </div>
          {tracker.required.length === 0 ? (
            <p className="text-sm text-ink-2">
              Sammle Unterlagen, während wir sprechen…
            </p>
          ) : (
            Object.entries(requiredByGroup).map(([group, docs]) => (
              <div key={group} className="mb-2 last:mb-0">
                {docs.map((d) => (
                  <TrackerRow key={d.id} id={d.id} label={d.label} tone="required" />
                ))}
              </div>
            ))
          )}
        </section>

        {/* TRIFFT WOHL NICHT ZU (collapsed) */}
        <CollapsibleSection
          title="Trifft wohl nicht zu"
          count={tracker.excluded.length}
          items={tracker.excluded.map((x) => ({
            id: x.rule_id,
            label: x.condition_label,
            reason: x.reason,
          }))}
        />

        {/* NOCH ZU KLÄREN */}
        <section>
          <div className="k-section-header mb-2 text-pending">
            <span>
              Noch zu klären
              <span className="k-count bg-amber-100 text-pending">
                {tracker.pending.length}
              </span>
            </span>
          </div>
          <div>
            {tracker.pending.map((x) => (
              <TrackerRow
                key={x.rule_id}
                id={x.rule_id}
                label={x.condition_label}
                tone="pending"
              />
            ))}
          </div>
        </section>
      </div>

      <footer className="border-t border-line px-4 py-3 text-xs text-ink-2">
        Diese Liste ist vorläufig und geht zur Prüfung an Ihre Steuerberaterin.
      </footer>
    </aside>
  );
}

// A row that flashes green the first time it appears (design spec §2.3 — the
// narrowing is the magic). Uses a keyed enter animation.
function TrackerRow({
  id,
  label,
  tone,
}: {
  id: string;
  label: string;
  tone: "required" | "pending";
}) {
  const [entered, setEntered] = useState(false);
  const seen = useRef(false);
  useEffect(() => {
    if (!seen.current) {
      seen.current = true;
      setEntered(true);
      const t = setTimeout(() => setEntered(false), 650);
      return () => clearTimeout(t);
    }
  }, []);
  const dot = tone === "required" ? "text-brand" : "text-pending";
  return (
    <div
      key={id}
      className={`flex items-start gap-2 border-b border-line py-1.5 text-sm last:border-0 ${
        entered ? "animate-enterFlash" : ""
      }`}
    >
      <span className={`mt-1.5 text-[8px] ${dot}`}>●</span>
      <span className={tone === "pending" ? "text-ink-2" : ""}>{label}</span>
    </div>
  );
}

function CollapsibleSection({
  title,
  count,
  items,
}: {
  title: string;
  count: number;
  items: { id: string; label: string; reason: string }[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <section>
      <button
        className="k-section-header w-full text-excluded"
        onClick={() => setOpen((o) => !o)}
      >
        <span>
          {title}
          <span className="k-count bg-gray-100 text-excluded">{count}</span>
        </span>
        <span>{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="mt-2">
          {items.map((it) => (
            <div
              key={it.id}
              className="border-b border-line py-1.5 text-sm text-excluded last:border-0"
            >
              <div>{it.label}</div>
              {it.reason && (
                <div className="text-xs text-excluded/70">{it.reason}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
