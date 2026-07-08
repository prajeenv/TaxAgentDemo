"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  api,
  ChatMessage,
  TrackerState,
} from "@/app/lib/api";
import { DocumentTracker } from "./DocumentTracker";
import { MessageBubble } from "./MessageBubble";

const EMPTY_TRACKER: TrackerState = {
  required: [],
  excluded: [],
  pending: [],
  refine_flags: [],
};

// The client chat surface (design spec §2). Left: chat thread + composer. Right:
// the live DocumentTracker. On mount it creates a session and shows the warm opener;
// each send hits POST /message, echoes the client's own text optimistically, then
// reconciles with the server's reply + fresh tracker.

export function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [tracker, setTracker] = useState<TrackerState>(EMPTY_TRACKER);
  const [complete, setComplete] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [startupError, setStartupError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .createSession()
      .then((r) => {
        setSessionId(r.session_id);
        setTracker(r.tracker_state);
        setMessages([
          { role: "assistant", text: r.opening_turn, checkpoint: false, escalated: false },
        ]);
      })
      .catch((e) => setStartupError(String(e)));
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, sending]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || !sessionId || sending) return;
    setInput("");
    setSending(true);
    // Optimistic echo of the client's own message (the one allowed optimistic write).
    setMessages((m) => [
      ...m,
      { role: "user", text, checkpoint: false, escalated: false },
    ]);
    try {
      const r = await api.sendMessage(sessionId, text);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: r.reply_text,
          checkpoint: r.checkpoint,
          escalated: r.escalated,
        },
      ]);
      setTracker(r.tracker_state);
      setComplete(r.complete);
    } catch {
      // Network/backend hiccup — show a warm, recoverable message as an agent turn
      // and put the client's text back so they can simply resend. (This is transient,
      // per-turn feedback shown inline as an agent message — NOT a persistent banner.)
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: "Entschuldigung — da ist die Verbindung kurz abgerissen. Könnten Sie das bitte noch einmal senden?",
          checkpoint: false,
          escalated: false,
        },
      ]);
      setInput(text);
    } finally {
      setSending(false);
    }
  }, [input, sessionId, sending]);

  return (
    <div className="grid h-screen grid-cols-1 lg:grid-cols-[1fr_360px]">
      {/* Chat */}
      <div className="flex h-screen flex-col border-r border-line">
        <header className="border-b border-line bg-surface px-5 py-3">
          <h1 className="font-serif text-base font-semibold">Steuer-Assistenz</h1>
          <p className="text-xs text-ink-2">
            Vorbereitung Ihrer Einkommensteuererklärung
          </p>
        </header>

        {startupError && (
          <div className="border-b border-warn/30 bg-warn-tint px-5 py-2 text-sm text-warn">
            Die Sitzung konnte nicht gestartet werden. Läuft der Server? Bitte laden
            Sie die Seite neu.
          </div>
        )}

        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-5">
          {messages.map((m, i) => (
            <MessageBubble key={i} message={m} />
          ))}
          {sending && <TypingStatus />}
          {complete && <EndStateCard />}
        </div>

        <div className="border-t border-line bg-surface p-4">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
          >
            <input
              className="flex-1 rounded-md border border-line bg-surface px-3 py-2 text-sm shadow-sm focus-within:border-brand focus:border-brand focus:outline-none"
              placeholder="Ihre Antwort…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={!sessionId || complete}
            />
            <button
              type="submit"
              className="k-btn-primary"
              disabled={!sessionId || sending || complete || !input.trim()}
            >
              Senden
            </button>
          </form>
        </div>
      </div>

      {/* Tracker */}
      <DocumentTracker tracker={tracker} complete={complete} />
    </div>
  );
}

function EndStateCard() {
  return (
    <div className="k-card border-brand/30 bg-brand-tint/40 p-4 text-sm leading-relaxed">
      <p className="font-medium">Vielen Dank — das war's für den Moment.</p>
      <p className="mt-1 text-ink-2">
        Ich habe zusammengetragen, welche Unterlagen für Ihre Steuererklärung
        wahrscheinlich relevant sind. <strong>Diese Liste ist noch vorläufig.</strong>{" "}
        Ihre Steuerberaterin prüft alles persönlich und schickt Ihnen anschließend{" "}
        <strong>per E-Mail die bestätigte Liste</strong> der Unterlagen, die Sie
        einreichen sollten.
      </p>
      <p className="mt-1 text-ink-2">
        Zu den steuerlichen Ergebnissen (etwa einer möglichen Erstattung) kann ich
        nichts sagen — das entscheidet Ihre Steuerberaterin.
      </p>
    </div>
  );
}

// A staged, timer-advanced status shown while a turn is in flight. It makes a
// 6-10s wait read as progress rather than a hang. GUARDRAIL RULE: it is strictly
// CONTENT-FREE — it never says anything about tax content or an outcome (no "let me
// check if that's deductible…"), which would be the over-eager-reassurance failure
// the reserved-advice boundary exists to prevent.
const TYPING_STAGES: { after: number; text: string }[] = [
  { after: 0, text: "Einen Moment…" },
  { after: 2500, text: "Ich notiere das…" },
  { after: 5500, text: "Fast fertig…" },
];

function TypingStatus() {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    const timers = TYPING_STAGES.slice(1).map((s, i) =>
      setTimeout(() => setStage(i + 1), s.after),
    );
    return () => timers.forEach(clearTimeout);
  }, []);
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink-2">
        <span className="inline-flex gap-1">
          <Dot /> <Dot /> <Dot />
        </span>
        <span>{TYPING_STAGES[stage].text}</span>
      </div>
    </div>
  );
}

function Dot() {
  return <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-ink-2/50" />;
}
