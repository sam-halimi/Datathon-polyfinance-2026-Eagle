# Sortie du pipeline

Format du JSON unique produit par `agents/pipeline.py::executer(profil, demande, prenom)`. Version `1.0`.

Sorties réelles, produites sur Bedrock, pour les trois personas : `agents/sorties/robert.json`, `amira.json`, `mateo.json`.
Les régénérer : `python -m agents.pipeline robert` (environ deux minutes). Les vérifier contre leur scénario :
`python -m tests.scenarios.verifier_sortie robert`.

Point de départ : `web/lib/types.ts`. Les champs de `SortiePipeline` y sont tous, avec le même sens ; les écarts
sont listés à la fin.

## Règle des chiffres

Aucun texte ne contient de chiffre écrit en clair. Un chiffre s'écrit `{repere}` (minuscules, chiffres, `_`), et
`chiffres[repere]` donne sa référence d'appel. L'interface remplace le repère par le chiffre formaté
(`web/lib/format.ts`), qu'on peut toucher pour voir son calcul. Un repère absent de `chiffres` s'affiche « ? ».

Exceptions, écrites par le code et non par un modèle : les messages des contrôles de gouvernance
(`gouvernance.controles[].detail`) contiennent des pourcentages déjà formatés par `tools/gouvernance.py`, et
`etapes[].fait` de la gouvernance contient des comptes (nombre de portefeuilles, d'essais).

`verification_textes` dit si un agent a quand même écrit un nombre, un repère inconnu ou un mot interdit
(`conseil`, `recommand…`, `bon choix`…). Le contrôle « Chaque chiffre a sa source » passe en alerte dans ce cas.

## `Reference` : `chiffres[repere]`

```json
{
  "outil": "volatilite",
  "parametres": {"symbole": "TSLA", "debut": null, "fin": null, "devise": "cotation"},
  "periode": {"debut": "2021-11-12", "fin": "2026-11-12", "observations": 1255},
  "valeur": 0.5961,
  "unite": "fraction annualisée, en USD",
  "formule": "écart-type des rendements quotidiens × √252",
  "sources": ["prices_daily.csv (adj_close)"],
  "details": {"jours_par_an": 252}
}
```

- `valeur` est toujours **un nombre brut, non arrondi**. Un outil qui renvoie plusieurs nombres
  (`correlations`, `stats_portefeuille`, `parts_du_risque`) donne un repère par nombre, et `details.cle` dit lequel.
- `unite` commence par `fraction` (à afficher en %), `coefficient` (à afficher avec deux décimales) ou autre chose.
- `outil` vaut le nom d'une fonction de `tools/`, ou l'un de ces trois cas, qui ne sont pas des mesures
  (`details.nature` le dit) :
  - `contraintes` : une limite du profil (`agents/profil.py`), hypothèse de conception de l'équipe ;
  - `constructeur` : un poids choisi par l'agent constructeur et vérifié par la gouvernance ;
  - `accueil` : une part demandée par l'utilisateur, recopiée de sa demande.

### Repères

| Repère | Outil | Exemple |
| --- | --- | --- |
| `vol_<symbole>` | `volatilite` | `vol_tsla`, `vol_xiu_to`, `vol_btc_usd` |
| `baisse_<symbole>` | `pire_baisse` | `baisse_tsla` |
| `rattrapage_<symbole>` | `gain_de_rattrapage` (chaîné à `pire_baisse`, voir `details.origine`) | `rattrapage_tsla` |
| `corr_<a>_<b>` | `correlations` | `corr_nvda_qqq` |
| `vol_<p>`, `rend_<p>`, `baisse_<p>` | `stats_portefeuille` du portefeuille `<p>` | `vol_a` |
| `part_<p>_<symbole>` | `parts_du_risque` | `part_a_btc_usd` |
| `poids_<p>_<symbole>` | `constructeur` | `poids_a_zst_to` |
| `limite_<nom>` | `contraintes` | `limite_max_titre_individuel`, `limite_max_crypto` |
| `demande_<symbole ou classe>` | `accueil` | `demande_tsla` |
| `sens_<symbole>_<serie>` | `sensibilite_taux` | `sens_tlt_dgs10` |
| `pente_<pays>` | `pente_courbe` | `pente_canada` |

`<symbole>` est le symbole en minuscules, `-` et `.` remplacés par `_`. `<p>` est `a`, `b` ou `c` pour un
portefeuille retenu, `p1`, `p2`… pour un candidat mesuré pendant la construction. Un même repère pour un autre
appel (autre fenêtre) reçoit le suffixe `_2`, `_3`…

`chiffres` contient aussi les chiffres calculés et non cités (candidats écartés) : c'est la trace complète.

## Champs

```text
version_format    "1.0"
exemple           false (true seulement dans web/data/exemple.json)
note              d'où vient la sortie (modèle Bedrock)
genere_le         date et heure, AAAA-MM-JJTHH:MM:SS
duree_secondes    durée de l'exécution
profil            Profil (agents/profil.py) + prenom + demande
contraintes       sortie de agents.profil.contraintes(profil) :
                    limites {max_titre_individuel, max_crypto, max_part_risquee, max_un_secteur, min_lignes, plafond_theme}
                    origine {même clé: d'où vient la limite}, exclusions, niveau_explication_par_defaut, nature
orchestration     ce qu'a compris l'orchestrateur :
                    resume_demande, positions_demandees [{symbole, classe, role, poids}], theme {nom, symboles, justification} | null,
                    candidats [symboles], consigne_specialiste, resume, anomalies [textes]
etapes            [{agent, fait}] : Orchestrateur, Marché et risque, (Macro et taux, ESG et qualité), Constructeur, Gouvernance, Explication
specialistes      {marche_et_risque: {constats [textes], actifs_adaptes [{symbole, raison}], actifs_a_limiter [...], resume}}
portefeuilles     [Portefeuille], 1 à 3, seulement ceux acceptés par la gouvernance
gouvernance       voir plus bas
explication       {niveau_par_defaut 1|2|3, sujet, niveau1, niveau2 [textes], niveau3 {formule, lignes [textes]}}
limites           {faits [textes], hypotheses [textes], limites [textes]}
messages          {analyse, repartition, risque, verifications, pourquoi, limites, tout} : phrase de l'assistant par carte
verification_textes {reperes_inconnus [], nombres_en_clair [], mots_interdits []}
chiffres          {repere: Reference}
```

### `Portefeuille`

```json
{
  "id": "a",
  "nom": "Prudent",
  "intention": "Préserver le capital sur un horizon court.",
  "lignes": [
    {"symbole": "ZST.TO", "nom": "BMO Ultra Short-Term Bond ETF", "classe": "Obligations (FNB)",
     "classe_code": "etf_bond", "secteur": "Bonds (Canada ultra short-term)",
     "role": "L'amortisseur", "role_code": "defensif", "poids": 0.45,
     "raison": "La plus stable de l'univers : pire baisse {baisse_zst_to}."}
  ],
  "volatilite": "vol_a",
  "rendement_passe": "rend_a",
  "pire_baisse": "baisse_a",
  "parts_du_risque": {"ZST.TO": "part_a_zst_to"},
  "pires_baisses": {"ZST.TO": "baisse_zst_to"},
  "volatilites": {"ZST.TO": "vol_zst_to"}
}
```

- `poids` est une fraction (0,45 pour 45 %). Le poids a aussi son repère `poids_<id>_<symbole>`.
- `classe_code` ∈ `equity`, `etf_equity`, `etf_bond`, `etf_commodity`, `crypto` (colonne `asset_class` de
  `data/assets_universe.csv`). `role_code` ∈ `coeur`, `defensif`, `diversification`, `theme`, `crypto`.
- `volatilite`, `pire_baisse`, `rendement_passe` et les valeurs des dictionnaires sont des **repères** (sans
  accolades). Mesures du portefeuille dans la devise du profil (CAD), poids constants ; mesures par actif dans
  la devise de cotation.
- `rendement_passe` décrit la fenêtre 2021-2026 et ne promet rien. L'afficher seulement avec cette mention, ou ne
  pas l'afficher.

### `gouvernance`

```json
{
  "essai": 1,
  "essais_max": 2,
  "statut": "accepte",
  "portefeuille_affiche": "a",
  "controles": [
    {"statut": "alerte", "statut_detaille": "à signaler", "controle": "demande_hors_profil",
     "titre": "Votre demande comparée à votre profil",
     "detail": "Demande non retenue telle quelle : TSLA demandé à 40 % du capital, plafond par titre de 5 % pour votre profil.",
     "symboles": ["TSLA"]},
    {"statut": "ok", "statut_detaille": "conforme", "controle": "volatilite_max",
     "titre": "Volatilité historique", "detail": "…", "mesure": 0.052, "seuil": 0.08,
     "reference": {"outil": "stats_portefeuille", "parametres": {}, "periode": {}, "formule": "…", "sources": []}}
  ],
  "par_portefeuille": {"a": ["Controle…"], "b": ["…"]},
  "historique": [{"essai": 1, "portefeuille": "a", "nom": "Prudent", "poids": {}, "accepte": true, "rejets": [], "messages": []}]
}
```

- `statut` (pour la carte) : `ok`, `alerte` ou `echec`. `statut_detaille` (vocabulaire de `tools/gouvernance.py`) :
  `conforme`, `non conforme`, `à signaler`, `information manquante`.
- `controles` : ce que la carte « vérifications » affiche. Dans l'ordre : l'écart entre la demande et le profil
  (`demande_hors_profil`, s'il y a une demande chiffrée), les contrôles du portefeuille `portefeuille_affiche`, puis
  « Chaque chiffre a sa source » et « Simulation seulement ».
- `par_portefeuille` : les contrôles de chaque portefeuille proposé au dernier essai, y compris un portefeuille rejeté.
- `historique` : chaque essai du constructeur. Un rejet renvoie au constructeur, 2 essais au plus. Après le
  deuxième essai, un portefeuille encore rejeté n'est pas montré ; si aucun ne passe, `statut` vaut `rejete` et
  `portefeuilles` est vide.
- Noms de contrôles : `demande_hors_profil`, `somme_des_poids`, `poids_positifs`, `univers_source`,
  `instruments_autorises`, `exclusion` (un par exclusion, avec `exclusion` et `actifs`), `plafond_par_titre`,
  `plafond_crypto`, `plafond_par_secteur`, `plafond_theme`, `theme_actions_et_fnb`, `part_risquee_max`,
  `lignes_min`, `volatilite_max`, `pire_baisse_max`, `chiffres_sources`, `simulation`.

## Écarts avec `web/lib/types.ts`

| Champ | `types.ts` | Sortie du pipeline |
| --- | --- | --- |
| `profil.horizon_annees` | `string` (« 15 ans et plus ») | `number` (borne basse retenue) |
| `profil.prenom`, `profil.demande` | facultatifs | présents (`prenom` peut être `null`) |
| `Portefeuille.volatilite` | repère | repère, plus `pire_baisse`, `rendement_passe`, `volatilites` |
| `Ligne` | `symbole, nom, classe, role, poids` | les mêmes, plus `classe_code`, `role_code`, `secteur`, `raison` |
| `Controle` | `statut, titre, detail` | les mêmes, plus `controle`, `statut_detaille` et selon le cas `symboles`, `actifs`, `mesure`, `seuil`, `reference` |
| `gouvernance` | `essai, essais_max, statut, controles` | les mêmes, plus `portefeuille_affiche`, `par_portefeuille`, `historique` |
| nouveaux | | `version_format`, `genere_le`, `duree_secondes`, `contraintes`, `orchestration`, `specialistes`, `verification_textes` |

Tous les champs de `types.ts` sont présents avec le même sens : l'interface peut lire une sortie du pipeline sans
changement, à part `horizon_annees`, qui est un nombre.
