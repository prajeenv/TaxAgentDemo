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
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
