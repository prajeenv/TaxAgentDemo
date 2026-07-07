import Link from "next/link";

// Placeholder landing page — restyled once the design spec lands.
export default function Home() {
  return (
    <main className="mx-auto max-w-2xl p-10">
      <h1 className="text-2xl font-semibold">Tax Intake — Prototype</h1>
      <p className="mt-2 text-gray-600">
        Two surfaces to demo:
      </p>
      <ul className="mt-4 list-disc space-y-1 pl-6">
        <li>
          <Link href="/chat" className="text-blue-700 underline">
            Client chat
          </Link>{" "}
          — the interactive intake with a live document tracker.
        </li>
        <li>Consultant review — reached by session link (/review/[sessionId]).</li>
      </ul>
    </main>
  );
}
