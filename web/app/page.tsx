import { Eagle } from "@/components/Eagle";
import { lireDa } from "@/lib/da";

// Eagle, sur ordinateur : questions, analyse par le pipeline (POST /analyse),
// présentation en diapositives. Démonstrations : agents/sorties/<persona>.json.

export default function Page() {
  const da = lireDa();
  return <Eagle avatar={da.avatar} logo={da.logo} />;
}
