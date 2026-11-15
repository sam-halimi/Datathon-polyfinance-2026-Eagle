import { Eagle } from "@/components/Eagle";
import { lireDa } from "@/lib/da";

// Eagle, sur ordinateur : questions, analyse par le pipeline (POST /analyse),
// présentation en diapositives. Démonstrations : agents/sorties/<persona>.json.
// Direction artistique : web/public/da/ (docs/da-eagle.md).

export default function Page() {
  return <Eagle da={lireDa()} />;
}
