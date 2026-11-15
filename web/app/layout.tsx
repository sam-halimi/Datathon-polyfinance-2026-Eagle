import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, IBM_Plex_Serif } from "next/font/google";
// Charte Eagle (docs/da-eagle.md) : tokens puis composants, puis les rôles de l'interface
// (app/tokens.css, qui ne fait que pointer vers la charte), puis les styles des écrans.
import "../public/da/tokens.css";
import "../public/da/eagle-components.css";
import "./tokens.css";
import "./globals.css";

const plexSans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex-sans" });
const plexSerif = IBM_Plex_Serif({ subsets: ["latin"], weight: ["500"], variable: "--font-plex-serif" });

export const metadata: Metadata = {
  title: "Eagle",
  description: "Eagle, un assistant qui établit un portefeuille simulé et en détaille chaque chiffre.",
  icons: { icon: "/da/logo/eagle-badge.svg" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#111417", // --bg de la charte (une métadonnée ne lit pas les variables CSS)
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr-CA" className={`${plexSans.variable} ${plexSerif.variable}`}>
      <body>{children}</body>
    </html>
  );
}
