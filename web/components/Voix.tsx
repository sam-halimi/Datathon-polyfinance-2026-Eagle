"use client";

import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { Mic, MicOff } from "lucide-react";
import type { EagleApi } from "./Eagle";
import { useLangue } from "./Langue";
import { tr } from "@/lib/langue";
import { DEMO } from "@/lib/api";

// La voix d'Eagle : un agent ElevenLabs (configuration dans
// docs/agent-elevenlabs.md). La voix ne fait qu'appeler trois outils ; le
// contenu vient toujours du pipeline. Sans identifiant d'agent, le texte reste.

const AGENT = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID;
// Option anglaise : un second agent, même outils, consigne et voix en anglais. Sans lui, l'agent français répond.
const AGENT_EN = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID_EN;

// Présentation menée par la voix. Un agent vocal rend la parole après chaque diapositive et attend
// qu'on lui réponde : sans rien dire, il fallait une trentaine de secondes de silence avant la suivante.
// Le site dit donc « continuez » à sa place, deux secondes et demie après la fin de chaque diapositive,
// jusqu'à la dernière. La personne peut couper la parole à tout moment : Eagle répond, puis reprend.
/** Retire les marques de ton entre crochets que le modèle de voix place dans son texte (« [calme] », « [pause] »). */
export function sansMarquesDeTon(texte: string): string {
  return texte.replace(/\[[\p{L}' -]{2,24}\]\s*/gu, "").replace(/\s{2,}/g, " ").trim();
}

const DERNIERE_DIAPOSITIVE = "limites";
const SILENCE_AVANT_SUITE = 2500;
const SUITE = { fr: "Continuez la présentation.", en: "Please continue the presentation." };

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
  const raccroche = useRef(false);
  const guidage = useRef<{ id: string; aParle: boolean; silence: number } | null>(null);
  const langue = useLangue();
  // Ce que les outils renvoient à la voix passe par tr() : en anglais, les nombres sont écrits à l'anglaise
  // (« 12.5% ») pour être bien prononcés. Les textes du pipeline arrivent déjà traduits.
  const conversation = useConversation({
    clientTools: {
      noter_profil: ({ champ, valeur }: Record<string, unknown>) => tr(api.current?.noterProfil(String(champ), valeur) ?? "Indisponible."),
      lancer_analyse: async () => { guidage.current = null; return tr((await api.current?.lancerAnalyse()) ?? "Indisponible."); },
      afficher_diapositive: ({ id, element }: Record<string, unknown>) => {
        // La voix vient de montrer une diapositive : on suivra la fin de ce qu'elle en dit.
        guidage.current = String(id) === "alternative" ? null : { id: String(id), aParle: false, silence: 0 };
        return tr(api.current?.afficherDiapositive(String(id), element ? String(element) : undefined) ?? "Indisponible.");
      },
    },
    onConnect: () => {
      liaison.current.etablie = true;
      // L'agent apprend ce qui est déjà à l'écran (réponses données avant l'appel, résultat affiché).
      window.setTimeout(() => { try { const e = api.current?.etat(); if (e) conversation.sendContextualUpdate(e); } catch { /* appel fermé entre-temps */ } }, 400);
    },
    onDisconnect: () => {
      guidage.current = null;
      // Appel coupé sans que la personne ait raccroché (réseau, micro retiré) : on le dit, l'écran reste utilisable.
      if (liaison.current.etablie && !raccroche.current) dire("L'appel s'est interrompu. Vous pouvez le reprendre avec « Démarrer l'appel », ou poursuivre à l'écran.");
      liaison.current.etablie = false;
    },
    // La relance automatique « continuez » n'est pas une parole de la personne : elle n'entre pas dans la transcription.
    onMessage: (m) => {
      if (m.role === "user" && Object.values(SUITE).includes(m.message.trim())) return;
      // Les marques de ton de la synthèse vocale (« [calme] ») guident la voix : elles ne s'affichent pas.
      const texte = m.role === "user" ? m.message : sansMarquesDeTon(m.message);
      if (texte) dire(texte, m.role === "user" ? "vous" : "eagle");
    },
    onError: (message) => {
      const l = liaison.current;
      if (!l.etablie && l.mode === "webrtc" && !l.repli) {
        l.repli = true;
        reprendre.current();
        return;
      }
      // Agent injoignable (quota de crédits ElevenLabs épuisé, agent désactivé) : on le dit en clair, sans jargon.
      dire(/not available|quota|credit|limit/i.test(message)
        ? "La voix n'est pas disponible pour le moment : le service vocal ne répond pas (quota atteint ou service interrompu). Tout le parcours reste possible à l'écran."
        : `Voix interrompue : ${message.replace(/[.\s]+$/, "")}. Vous pouvez poursuivre par écrit.`);
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
      const en = langue === "en";
      conversation.sendContextualUpdate(p
        ? (en ? "The person has paused the call to think: their microphone is off. Say nothing and call no tool until the call resumes."
          : "La personne a mis l'appel en pause pour réfléchir : son micro est coupé. Ne dites rien et n'appelez aucun outil jusqu'à la reprise.")
        : (en ? "The person has resumed the call: their microphone is on again. Resume where you were, with one short sentence."
          : "La personne a repris l'appel : son micro est rouvert. Reprenez là où vous en étiez, par une phrase courte."));
      // Pendant une présentation, ce qui a été dit pendant la pause n'a pas été entendu (son coupé) :
      // Eagle reprend la diapositive affichée, au lieu de passer à la suivante.
      const enPresentation = Boolean(guidage.current);
      if (!p) conversation.sendUserMessage(enPresentation
        ? (en ? "I am back. I did not hear what you said during the pause: please present the slide currently on screen again, then continue."
          : "Je suis de retour. Je n'ai pas entendu ce que vous avez dit pendant la pause : reprenez la diapositive affichée à l'écran, puis continuez.")
        : (en ? "I am back, let us resume where we were." : "Je suis de retour, reprenons là où nous en étions."));
    } catch { /* appel fermé entre-temps */ }
    dire(p ? "Appel en pause : votre micro est coupé et je me tais. Reprenez quand vous voulez." : "Reprise de l'appel.");
  };
  // Enchaînement des diapositives par la voix (voir SUITE plus haut).
  const parleRef = useRef(false);
  parleRef.current = conversation.isSpeaking;
  useEffect(() => {
    if (!enLigne) { guidage.current = null; return; }
    const t = window.setInterval(() => {
      const g = guidage.current;
      if (!g || pause || reflechit) return;
      if (parleRef.current) { g.aParle = true; g.silence = 0; return; }
      if (!g.aParle) return; // Eagle n'a pas encore commencé à parler de cette diapositive
      g.silence += 500;
      if (g.silence < SILENCE_AVANT_SUITE) return;
      if (g.id === DERNIERE_DIAPOSITIVE) { guidage.current = null; return; } // après la dernière, Eagle pose sa question et attend
      g.aParle = false; g.silence = 0;
      try { conversation.sendUserMessage(SUITE[langue]); } catch { /* appel fermé entre-temps */ }
    }, 500);
    return () => window.clearInterval(t);
  }, [enLigne, pause, reflechit, langue, conversation]);
  const parle = enLigne && !pause && conversation.isSpeaking;
  useEffect(() => { surParole?.(parle); }, [parle, surParole]);
  useEffect(() => { surLigne?.(enLigne); }, [enLigne, surLigne]);
  const ouvrir = (mode: "webrtc" | "websocket") => {
    liaison.current = { ...liaison.current, mode, etablie: false };
    raccroche.current = false;
    conversation.startSession({ agentId: (langue === "en" && AGENT_EN) || AGENT!, connectionType: mode });
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
        onClick={enLigne ? () => { raccroche.current = true; conversation.endSession(); } : () => void demarrer()} disabled={conversation.status === "connecting"}>
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
        <p className="voix__etat">{props.reflechit ? "Eagle réfléchit" : DEMO ? "Voix désactivée sur cette démonstration publique." : "Voix non configurée : l'échange se poursuit par écrit."}</p>
      </div>
    );
  }
  return (
    <ConversationProvider>
      <Controle {...props} />
    </ConversationProvider>
  );
}
