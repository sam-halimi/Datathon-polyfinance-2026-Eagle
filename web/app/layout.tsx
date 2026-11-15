import type { Metadata, Viewport } from "next";
import "./tokens.css";
import "./globals.css";
import { lireDa } from "@/lib/da";

export const metadata: Metadata = {
  title: "Eagle",
  description: "Eagle, un assistant qui établit un portefeuille simulé et en détaille chaque chiffre.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#f6f4ef",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const da = lireDa();
  return (
    <html lang="fr-CA">
      <head>
        {/* Direction artistique : ses variables remplacent celles de app/tokens.css. */}
        {da.tokens ? <link rel="stylesheet" href="/da/tokens.css" /> : null}
      </head>
      <body>{children}</body>
    </html>
  );
}
