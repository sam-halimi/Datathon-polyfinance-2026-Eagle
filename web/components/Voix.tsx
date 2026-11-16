"use client";

import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { Mic, MicOff } from "lucide-react";
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
  /** Un calcul est en cours (analyse, fiche d'un actif) : l'état affiché est « Eagle réfléchit ». */
  reflechit?: boolean;
};

function Controle({ api, dire, surParole, surLigne, reflechit = false }: Props) {
  // Liaison audio : WebRTC d'abord (meilleure qualité). Un réseau qui bloque l'UDP (Wi-Fi d'école,
  // d'entreprise, de salle) fait échouer WebRTC : on reprend alors une fois par WebSocket, qui
  // passe par HTTPS. `liaison` retient le mode en cours et si la connexion a déjà abouti.
  const liaison = useRef<{ mode: "webrtc" | "websocket"; etablie: boolean; repli: boolean }>({ mode: "webrtc", etablie: false, repli: false });
  const reprendre = useRef<() => void>(() => {});
  const conversation = useConversation({
    clientTools: {
      noter_profil: ({ champ, valeur }: Record<string, unknown>) => api.current?.noterProfil(String(champ), valeur) ?? "Indisponible.",
      lancer_analyse: async () => (await api.current?.lancerAnalyse()) ?? "Indisponible.",
      afficher_diapositive: ({ id, element }: Record<string, unknown>) =>
        api.current?.afficherDiapositive(String(id), element ? String(element) : undefined) ?? "Indisponible.",
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
  // Pause : le micro est coupé et Eagle se tait, le temps de réfléchir. L'appel reste ouvert.
  const [pause, setPause] = useState(false);
  useEffect(() => { if (!enLigne) setPause(false); }, [enLigne]);
  useEffect(() => {
    if (!enLigne || !pause) return;
    // Tant que la pause dure, on signale une activité : Eagle ne relance pas la personne.
    const t = window.setInterval(() => { try { conversation.sendUserActivity(); } catch { /* appel fermé entre-temps */ } }, 1500);
    return () => window.clearInterval(t);
  }, [enLigne, pause, conversation]);
  const basculerPause = () => {
    const p = !pause;
    setPause(p);
    try {
      conversation.setMuted(p);
      conversation.setVolume({ volume: p ? 0 : 1 });
      conversation.sendContextualUpdate(p
        ? "La personne a mis l'appel en pause pour réfléchir : son micro est coupé. Ne dites rien et n'appelez aucun outil jusqu'à la reprise."
        : "La personne a repris l'appel : son micro est rouvert. Reprenez là où vous en étiez, par une phrase courte.");
      if (!p) conversation.sendUserMessage("Je suis de retour, reprenons là où nous en étions.");
    } catch { /* appel fermé entre-temps */ }
    dire(p ? "Appel en pause : votre micro est coupé et je me tais. Reprenez quand vous voulez." : "Reprise de l'appel.");
  };
  const parle = enLigne && !pause && conversation.isSpeaking;
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
      {enLigne ? (
        <button type="button" className={pause ? "voix__pause voix__pause--actif" : "voix__pause"} onClick={basculerPause} aria-pressed={pause}>
          {pause ? <MicOff aria-hidden="true" size={18} /> : <Mic aria-hidden="true" size={18} />}
          {pause ? "Reprendre : rouvrir le micro" : "Pause : couper le micro"}
        </button>
      ) : null}
      <p className="voix__etat">
        {reflechit ? "Eagle réfléchit"
          : !enLigne ? "Voix coupée · l'écrit reste disponible"
            : pause ? "Appel en pause · micro coupé, Eagle se tait"
              : conversation.isSpeaking ? "Eagle parle" : "Eagle écoute"}
      </p>
    </div>
  );
}

export function Voix(props: Props) {
  if (!AGENT) {
    return (
      <div className="voix">
        <button type="button" className="bouton bouton--secondaire" disabled title="NEXT_PUBLIC_ELEVENLABS_AGENT_ID n'est pas défini">Démarrer l&apos;appel</button>
        <p className="voix__etat">{props.reflechit ? "Eagle réfléchit" : "Voix non configurée : l'échange se poursuit par écrit."}</p>
      </div>
    );
  }
  return (
    <ConversationProvider>
      <Controle {...props} />
    </ConversationProvider>
  );
}
