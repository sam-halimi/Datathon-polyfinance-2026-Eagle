"use client";

import { ConversationProvider, useConversation } from "@elevenlabs/react";
import type { MutableRefObject } from "react";
import type { EagleApi } from "./Eagle";

// La voix d'Eagle : un agent ElevenLabs (configuration dans
// docs/agent-elevenlabs.md). La voix ne fait qu'appeler trois outils ; le
// contenu vient toujours du pipeline. Sans identifiant d'agent, le texte reste.

const AGENT = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID;

type Props = { api: MutableRefObject<EagleApi | null>; dire: (texte: string, qui?: "eagle" | "vous") => void };

function Controle({ api, dire }: Props) {
  const conversation = useConversation({
    clientTools: {
      noter_profil: ({ champ, valeur }: Record<string, unknown>) => api.current?.noterProfil(String(champ), valeur) ?? "Indisponible.",
      lancer_analyse: async () => (await api.current?.lancerAnalyse()) ?? "Indisponible.",
      afficher_diapositive: ({ id }: Record<string, unknown>) => api.current?.afficherDiapositive(String(id)) ?? "Indisponible.",
    },
    onMessage: (m) => dire(m.message, m.role === "user" ? "vous" : "eagle"),
    onError: (message) => dire(`Voix interrompue : ${message}. Vous pouvez poursuivre par écrit.`),
  });
  const enLigne = conversation.status === "connected";
  const demarrer = async () => {
    try {
      // Le navigateur exige un geste de l'utilisateur et HTTPS (ou localhost) pour le micro.
      await navigator.mediaDevices.getUserMedia({ audio: true });
      conversation.startSession({ agentId: AGENT!, connectionType: "webrtc" });
    } catch {
      dire("Le micro n'est pas accessible. Nous poursuivons par écrit.");
    }
  };
  return (
    <div className="voix">
      <button type="button" className={enLigne ? "bouton bouton--secondaire" : "bouton bouton--principal"}
        onClick={enLigne ? () => conversation.endSession() : () => void demarrer()} disabled={conversation.status === "connecting"}>
        {enLigne ? "Raccrocher" : conversation.status === "connecting" ? "Connexion…" : "Démarrer l'appel"}
      </button>
      <p className="voix__etat">{enLigne ? (conversation.isSpeaking ? "Eagle parle" : "Eagle écoute") : "Voix coupée · l'écrit reste disponible"}</p>
    </div>
  );
}

export function Voix(props: Props) {
  if (!AGENT) {
    return (
      <div className="voix">
        <button type="button" className="bouton bouton--secondaire" disabled title="NEXT_PUBLIC_ELEVENLABS_AGENT_ID n'est pas défini">Démarrer l&apos;appel</button>
        <p className="voix__etat">Voix non configurée : l&apos;échange se poursuit par écrit.</p>
      </div>
    );
  }
  return (
    <ConversationProvider>
      <Controle {...props} />
    </ConversationProvider>
  );
}
