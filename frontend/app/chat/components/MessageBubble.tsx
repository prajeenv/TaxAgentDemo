"use client";

import { ChatMessage } from "@/app/lib/api";

// A single chat message. Agent left, client right. Escalation turns get a subtle
// "Noted for [consultant]" chip (muted, non-alarming — the handoff reads as helpful
// routing, not a wall). Checkpoint turns get a faint "confirming" affordance.

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isAgent = message.role === "assistant";
  return (
    <div className={`flex ${isAgent ? "justify-start" : "justify-end"}`}>
      <div className={`max-w-[80%] ${isAgent ? "" : "text-right"}`}>
        <div
          className={`rounded-md px-3 py-2 text-sm leading-relaxed ${
            isAgent
              ? "border border-line bg-surface"
              : "bg-brand text-white"
          } ${message.checkpoint ? "ring-1 ring-brand/30" : ""}`}
        >
          {message.text}
        </div>
        {isAgent && message.escalated && (
          <div className="mt-1 inline-flex items-center gap-1 text-[11px] text-ink-2">
            <span>↗</span> An Ihre Steuerberaterin weitergegeben
          </div>
        )}
        {isAgent && message.checkpoint && !message.escalated && (
          <div className="mt-1 text-[11px] text-ink-2/70">kurze Rückfrage</div>
        )}
      </div>
    </div>
  );
}
