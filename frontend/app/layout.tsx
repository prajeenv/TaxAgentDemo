import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tax Intake — Prototype",
  description:
    "Conversational intake for income-tax returns — prototype for a Steuerberatung.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // lang="de" matches the German UI (stops the browser offering to translate it);
    // suppressHydrationWarning tolerates attributes injected by translate/extensions
    // on <html> after SSR (the standard Next.js remedy for that hydration mismatch).
    <html lang="de" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
