// L'avatar d'Eagle : une tête d'aigle de profil, dessinée pour le projet.
// Quand Eagle parle ou travaille, un anneau s'anime autour.

export function Aigle({ taille = 140, actif = false, image = null }: { taille?: number; actif?: boolean; image?: string | null }) {
  // Avatar de la direction artistique (web/public/da/), s'il a été déposé.
  if (image) {
    return (
      <span className={actif ? "aigle aigle--image aigle--actif" : "aigle aigle--image"} style={{ width: taille, height: taille }}>
        <img src={image} alt="Eagle, l'assistant" width={taille} height={taille} />
        <svg viewBox="0 0 200 200" aria-hidden="true"><circle cx="100" cy="100" r="96" className="aigle__anneau" /></svg>
      </span>
    );
  }
  return (
    <svg className={actif ? "aigle aigle--actif" : "aigle"} width={taille} height={taille} viewBox="0 0 200 200" role="img" aria-label="Eagle, l'assistant">
      <circle cx="100" cy="100" r="96" className="aigle__anneau" />
      <circle cx="100" cy="100" r="86" fill="#1f3b63" />
      {/* cou et plumage brun */}
      <path d="M38 186 C48 140 70 122 96 118 C124 114 150 132 162 186 Z" fill="#5b3a1e" />
      <path d="M58 186 C64 158 80 144 100 142 C122 140 140 156 146 186 Z" fill="#7a4f2a" />
      {/* tête blanche */}
      <path d="M52 120 C40 92 52 52 92 42 C126 34 150 52 156 78 C160 96 152 112 138 122 C122 132 98 138 78 134 C66 132 58 128 52 120 Z" fill="#f4f1ea" />
      {/* plumes du sommet */}
      <path d="M70 58 C78 40 96 34 112 38 C100 42 92 48 88 56 Z" fill="#e2ddd2" />
      <path d="M58 108 C62 118 70 126 80 130 C70 132 60 126 54 118 Z" fill="#e2ddd2" />
      {/* sourcil et œil */}
      <path d="M112 70 C124 64 138 66 146 74 C136 72 124 74 114 80 Z" fill="#2b2b2b" />
      <circle cx="128" cy="80" r="7.5" fill="#f2b01e" />
      <circle cx="129.5" cy="80" r="3.6" fill="#1b1b1b" />
      <circle cx="131" cy="78.4" r="1.2" fill="#fff" />
      {/* bec crochu */}
      <path d="M140 84 C156 82 172 90 176 104 C178 114 172 122 164 124 C166 116 162 110 154 108 C148 106 142 104 138 100 Z" fill="#f2b01e" />
      <path d="M138 100 C146 104 156 106 162 112 C156 112 148 112 140 108 Z" fill="#d48d0c" />
      <path d="M140 86 C146 86 150 88 152 92" stroke="#b5780b" strokeWidth="2" fill="none" strokeLinecap="round" />
    </svg>
  );
}
