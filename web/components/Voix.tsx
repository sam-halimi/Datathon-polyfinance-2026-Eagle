"use client";

import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { useEffect, useRef, type MutableRefObject } from "react";
import type { EagleApi } from "./Eagle";

// La voix d'Eagle : un agent ElevenLabs (configuration dans
// docs/agent-elevenlabs.md). La voix ne fait qu'appeler trois outils ; le
// contenu vient toujours du pipeline. Sans identifiant d'agent, le texte reste.

const AGENT = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID;

type Props = {
  api: MutableRefObject<EagleApi | null>;
  dire: (texte: string, qui?: "eagle" | "vous") => void;
  /** Remonte « la voix émet » pour l'état « parle » de l'avatar. */
  surParole?: (parle: boolean) => void;
  /** Remonte « l'appel est en cours » : l'agent dit alors lui-même les questions. */
  surLigne?: (enLigne: boolean) => void;
};

function Controle({ api, dire, surParole, surLigne }: Props) {
  // Liaison audio : WebRTC d'abord (meilleure qualité). Un réseau qui bloque l'UDP (Wi-Fi d'école,
  // d'entreprise, de salle) fait échouer WebRTC : on reprend alors une fois par WebSocket, qui
  // passe par HTTPS. `liaison` retient le mode en cours et si la connexion a déjà abouti.
  const liaison = useRef<{ mode: "webrtc" | "websocket"; etablie: boolean; repli: boolean }>({ mode: "webrtc", etablie: false, repli: false });
  const reprendre = useRef<() => void>(() => {});
  const conversation = useConversation({
    clientTools: {
      noter_profil: ({ champ, valeur }: Record<string, unknown>) => api.current?.noterProfil(String(champ), valeur) ?? "Indisponible.",
      lancer_analyse: async () => (await api.current?.lancerAnalyse()) ?? "Indisponible.",
      afficher_diapositive: ({ id }: Record<string, unknown>) => api.current?.afficherDiapositive(String(id)) ?? "Indisponible.",
    },
    onConnect: () => { liaison.current.etablie = true; },
    onMessage: (m) => dire(m.message, m.role === "user" ? "vous" : "eagle"),
    onError: (message) => {
      const l = liaison.current;
      if (!l.etablie && l.mode === "webrtc" && !l.repli) {
        l.repli = true;
        reprendre.current();
        return;
      }
      dire(`Voix interrompue : ${message}. Vous pouvez poursuivre par écrit.`);
    },
  });
  const enLigne = conversation.status === "connected";
  const parle = enLigne && conversation.isSpeaking;
  useEffect(() => { surParole?.(parle); }, [parle, surParole]);
  useEffect(() => { surLigne?.(enLigne); }, [enLigne, surLigne]);
  const ouvrir = (mode: "webrtc" | "websocket") => {
    liaison.current = { ...liaison.current, mode, etablie: false };
    conversation.startSession({ agentId: AGENT!, connectionType: mode });
  };
  reprendre.current = () => {
    // Laisse la tentative WebRTC se refermer avant d'ouvrir la liaison WebSocket.
    window.setTimeout(() => {
      try { void conversation.endSession(); } catch { /* déjà fermée */ }
      window.setTimeout(() => ouvrir("websocket"), 400);
    }, 0);
  };
  const demarrer = async () => {
    try {
      // Le navigateur exige un geste de l'utilisateur et HTTPS (ou localhost) pour le micro.
      const flux = await navigator.mediaDevices.getUserMedia({ audio: true });
      flux.getTracks().forEach((t) => t.stop()); // simple demande d'autorisation : la session ouvre son propre flux
    } catch {
      dire("Le micro n'est pas accessible. Nous poursuivons par écrit.");
      return;
    }
    liaison.current = { mode: "webrtc", etablie: false, repli: false };
    ouvrir("webrtc");
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
