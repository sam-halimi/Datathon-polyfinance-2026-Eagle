import { Appel } from "@/components/Appel";
import exemple from "@/data/exemple.json";
import type { SortiePipeline } from "@/lib/types";

// Étape 1 : la sortie du pipeline est lue dans web/data/exemple.json.
// Étape 2 : elle viendra du pipeline (format de docs/sortie-pipeline.md).

export default function Page() {
  return <Appel sortie={exemple as unknown as SortiePipeline} />;
}
