import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Movie Studio",
  description: "Autonomous AI production dashboard for Lili Marleen - Damascus"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
