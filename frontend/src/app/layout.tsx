import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Voice Insight Engine",
  description: "Multi-provider audio intelligence pipeline",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
