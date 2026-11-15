import { Appel } from "@/components/Appel";

// Le site lit les vraies sorties du pipeline : agents/sorties/<persona>.json
// (format : docs/sortie-pipeline.md). Le persona se choisit au début de l'appel.

export default function Page() {
  return <Appel />;
}
