import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SMRITI AI — Ambedkar Digital Archive",
  description: "An evidence-led, multilingual archive for the life and work of Dr. B. R. Ambedkar.",
  manifest: "/manifest.webmanifest",
  applicationName: "SMRITI AI",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "SMRITI AI" },
  icons: { icon: "/icons/smriti-ai-192.png", apple: "/icons/smriti-ai-apple.png" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
