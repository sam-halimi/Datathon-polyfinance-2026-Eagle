import type { Metadata } from "next";
import { Suspense } from "react";
import { Rapport } from "@/components/Rapport";

export const metadata: Metadata = { title: "Dossier de portefeuille simulé · AlphaForge" };

// Le dossier imprimable d'un persona : /rapport?persona=robert.
export default function Page() {
  return (
    <Suspense fallback={null}>
      <Rapport />
    </Suspense>
  );
}
