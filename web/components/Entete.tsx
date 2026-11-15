import { typo } from "./Chiffres";
import { ETAPES } from "@/lib/types";

export function BarreEtapes({ active }: { active: number }) {
  return (
    <ol className="etapes" aria-label="Étapes">
      {ETAPES.map((nom, i) => (
        <li
          key={nom}
          className={i < active ? "etape etape--faite" : i === active ? "etape etape--active" : "etape"}
          aria-current={i === active ? "step" : undefined}
        >
          <span className="etape__trait" aria-hidden="true" />
          <span className="etape__nom">{nom}</span>
        </li>
      ))}
    </ol>
  );
}

export function Assistant({ message, sousTitre }: { message: string; sousTitre?: string }) {
  return (
    <section className="assistant" aria-live="polite">
      <div className="assistant__avatar" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="assistant__bulle">
        {sousTitre ? <p className="assistant__sous-titre">{sousTitre}</p> : null}
        <p className="assistant__message">{typo(message)}</p>
      </div>
    </section>
  );
}
