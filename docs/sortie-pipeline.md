# Sortie du pipeline

Le pipeline (`agents/pipeline.py`) renvoie un seul objet JSON. L'interface le lit à la place de `web/data/exemple.json`.

```bash
python -m agents.pipeline robert amira mateo
```

Cette commande écrit `agents/sorties/robert.json`, `amira.json` et `mateo.json`, un fichier par persona de `tests/scenarios/`. Il faut Bedrock pour la lancer. Les fichiers sont versionnés : l'interface n'a donc pas besoin de Bedrock pour les afficher.

Le format reprend `web/lib/types.ts`. Les écarts sont marqués **nouveau** ou **changé**. Un champ en plus peut être ignoré par l'interface.

## Règle des chiffres

Aucun texte écrit par un modèle ne contient de chiffre. Les textes portent des repères `{id}`, et chaque `id` est une clé de `chiffres`. L'interface remplace le repère par la valeur formatée (`formaterChiffre`), touchable pour voir sa référence d'appel.

Le pipeline vérifie cette règle mécaniquement :

- un texte avec un chiffre écrit en dur, ou avec un repère inconnu, est renvoyé une fois au modèle ;
- s'il est encore faux, il est retiré et noté dans `journal.textes_retires`.

Certains textes sont écrits par le code, pas par un modèle : les contrôles de gouvernance, les lignes du niveau 3, les faits sur les obligations. Ils peuvent contenir des chiffres, des dates ou des poids, mais chacun vient d'un outil de `tools/` ou du portefeuille lui-même.

## Objet racine

| Champ | Type | Contenu |
| --- | --- | --- |
| `exemple` | `false` | Toujours `false` en sortie du pipeline. La pastille « Exemple » disparaît |
| `note` | string | Origine et date |
| `scenario` | string | **nouveau** : `robert`, `amira` ou `mateo` |
| `profil` | Profil | Voir plus bas |
| `demande_analysee` | objet | **nouveau** : `texte`, `resume`, `symboles` [{`symbole`, `poids`}], `classes`, `part_risquee` |
| `etapes` | [{`agent`, `fait`}] | Ce que chaque agent a fait, dans l'ordre. Sans repère |
| `portefeuilles` | Portefeuille[] | 2 ou 3, le retenu en premier |
| `gouvernance` | objet | Voir plus bas |
| `explication` | objet | Voir plus bas |
| `limites` | {`faits`, `hypotheses`, `limites`, `methode`} : string[], plus `limites_specifiques` et `hypotheses_specifiques` | Textes avec repères. **v2** : voir « Limites et hypothèses » |
| `messages` | {`analyse`, `repartition`, `risque`, `verifications`, `pourquoi`, `limites`, `tout`} | Une phrase de l'assistant par carte |
| `chiffres` | {id: Reference} | Table des chiffres |
| `contraintes` | objet | **nouveau** : `limites`, `origine` de chaque limite, `exclusions`, `nature`, `seuils_risque` |
| `specialistes` | objet | **nouveau** : `marche_et_risque` et `macro` (constats, string[]), `esg` : {`criteres`, `fiches` (une par action : valeurs, résumé, `source_url`, `source_date`, ou `statut` « information manquante »), `expositions_fnb`, `constats`} |
| `theme` | objet ou null | **nouveau** : `nom`, `secteur`, `symboles`, `source` |
| `exclus` | {symbole: raison} | **nouveau** : candidats écartés avant construction |
| `journal` | objet | **nouveau** : `appels` (chaque appel d'outil : `agent`, `id`, `outil`, `parametres`) et `textes_retires` |
| `meta` | objet | **nouveau** : `modele`, `duree_secondes`, `date` |
| `adequation` | Adequation[] | **v2** : chaque critère du profil vérifié contre le portefeuille retenu. Voir plus bas |

## Profil

Champs de `agents/profil.py`, plus `demande` et `prenom`.

- **changé** : `horizon_annees` est un **nombre** (3, 8, 15), plus une chaîne. Pour afficher « 3 à 5 ans », lire `choix_de_l_accueil` dans le scénario ou écrire « {n} ans ».
- `capital_fictif` est un nombre, `devise` vaut `CAD` ou `USD`.

## Portefeuille

| Champ | Type | Contenu |
| --- | --- | --- |
| `id` | string | `A`, `B` ou `C` |
| `nom` | string | Sans chiffre |
| `intention` | string | **nouveau** : une phrase, à quoi sert ce portefeuille pour ce profil |
| `lignes` | Ligne[] | Triées par poids décroissant |
| `volatilite` | id | Repère du chiffre (pas la valeur) |
| `pire_baisse` | id | **nouveau** : pire baisse du portefeuille |
| `parts_du_risque` | {symbole: id} | Somme des valeurs = 1 |
| `pires_baisses` | {symbole: id} | Pire baisse de chaque actif, dans sa devise de cotation |
| `volatilites` | {symbole: id} | **nouveau** |
| `theme` | {`nom`, `symboles`} ou null | **nouveau** : lignes du thème plafonné |
| `essai` | 1 ou 2 | **nouveau** : essai où la gouvernance l'a accepté |
| `controles` | Controle[] | **nouveau** : contrôles de ce portefeuille |
| `adequation` | Adequation[] | **v2** : même vérification que `adequation` à la racine, pour ce portefeuille |

### Ligne

| Champ | Type | Contenu |
| --- | --- | --- |
| `symbole`, `nom` | string | Tirés de `data/assets_universe.csv` |
| `classe` | string | Libellé affiché : Action, FNB d'actions, FNB d'obligations, FNB d'or, Cryptoactif |
| `classe_code` | string | **nouveau** : `equity`, `etf_equity`, `etf_bond`, `etf_commodity`, `crypto` |
| `role` | string | Libellé affiché, par exemple « L'amortisseur » |
| `role_code` | string | **nouveau** : `coeur`, `amortisseur`, `diversification`, `theme`, `audace` |
| `poids` | number | Fraction du capital (0,05 = 5 %), à formater avec `formaterPoids` |
| `poids_id` | id | **v2** : le poids comme chiffre citable (nature « décision du constructeur ») |
| `secteur` | string | **v2** : colonne `sector` de `data/assets_universe.csv` |
| `pays` | string | **v2** : pays de cotation, tiré de la colonne `market` (TSX : Canada ; NASDAQ, NYSE, NYSE Arca, Cboe BZX : États-Unis ; cryptoactif : « sans pays, cotation continue ») |
| `devise` | `CAD` ou `USD` | **v2** : devise de cotation |
| `pourquoi` | string | **v2** : pourquoi cette ligne pour cette personne, avec repères. Écrit par le constructeur, contrôlé par la gouvernance |
| `critere_profil` | string | **v2** : critère du profil que la ligne sert (`horizon`, `objectif`, `tolerance`, `preferences`, `exclusions`, `centres_interet`, `capital`, `demande`) |
| `plutot_que` | {`symbole`, `raison`} | **v2** : le candidat écarté au profit de cette ligne, et pourquoi (texte avec repères) |
| `chiffres` | {`volatilite`, `pire_baisse`, `part_du_risque`} : id | **v2** : repères des chiffres de la ligne |
| `sources` | [{`fichier`, `url`, `date`, `objet`}] | **v2** : d'où vient chaque information de la ligne (univers, prix, change, ESG, composition du FNB). `url` et `date` viennent de `data/sources_metadata.csv` ou de la table ESG |

## Gouvernance

| Champ | Type | Contenu |
| --- | --- | --- |
| `essai` | number | Nombre d'essais du constructeur, 2 au plus |
| `essais_max` | 2 | |
| `statut` | `"accepte"` | Le pipeline échoue s'il n'accepte aucun portefeuille, il n'invente pas de repli |
| `portefeuille_retenu` | string | **nouveau** : `id` du portefeuille expliqué |
| `controles` | Controle[] | Contrôles sur la demande (`demande_hors_profil`), puis ceux du portefeuille retenu, puis « Simulation seulement » |
| `historique` | objet[] | **nouveau** : chaque proposition de chaque essai (`essai`, `portefeuille`, `nom`, `poids`, `accepte`, `rejets`). C'est ici que se lit un rejet suivi d'une correction |

### Controle

| Champ | Type | Contenu |
| --- | --- | --- |
| `statut` | `ok`, `alerte` ou `echec` | Pour l'affichage. `alerte` couvre « à signaler » et « information manquante » |
| `titre` | string | Court |
| `detail` | string | Peut contenir des repères `{id}` |
| `controle` | string | **nouveau** : nom technique (`plafond_par_titre`, `demande_hors_profil`, `diversification`, `exclusion_esg`, `transparence_fnb`…) |
| `statut_outil` | string | **nouveau** : `conforme`, `non conforme`, `à signaler` ou `information manquante` |
| `symboles`, `actifs` | string[] | **nouveau**, facultatif : actifs concernés |
| `chiffres` | id[] | **nouveau**, facultatif : chiffres cités dans `detail` |
| `source` | string | **nouveau**, facultatif : fichier de `data/` qui fonde le contrôle |

## Explication

| Champ | Type | Contenu |
| --- | --- | --- |
| `niveau_par_defaut` | 1, 2 ou 3 | Selon `connaissance` (débutant 1, intermédiaire 2, avancé 3) |
| `sujet` | string | La question à laquelle répond l'explication |
| `niveau1` | string | Une phrase |
| `niveau2` | string[] | Le pourquoi chiffré |
| `niveau3` | {`formule`, `lignes`} | Écrit par le code à partir de la référence du chiffre central : formule de l'outil, paramètres, poids, période, sources, résultat |
| `chiffre_central` | id | **nouveau** : chiffre dont le calcul est montré |

## Reference (entrée de `chiffres`)

Mêmes champs que `web/lib/types.ts` : `outil`, `parametres`, `periode` {`debut`, `fin`, `observations`}, `valeur` (number, brute), `unite`, `formule`, `sources`, `details`. S'y ajoutent :

- `champ` (facultatif) : la valeur extraite d'un outil qui en renvoie plusieurs. Par exemple `stats_portefeuille` donne `ptf_a_volatilite` (`champ` = `volatilite`), et `parts_du_risque` donne `part_a_tsla` (`champ` = `TSLA`).
- Les limites du profil sont aussi des chiffres (`lim_max_titre_individuel`, `seuil_volatilite`…). Leur `outil` est `agents.profil.contraintes` ou `tools.gouvernance.SEUILS_PAR_TOLERANCE`, leur `unite` « fraction du capital » ou « fraction », et leur `periode` est vide (`debut` null).

`formaterChiffre` marche tel quel : `unite` commence par « fraction » (affichage en %) ou par « coefficient » (corrélation, deux décimales).

## Identifiants

| Forme | Exemple | Outil |
| --- | --- | --- |
| `vol_<symbole>` | `vol_tsla` | `volatilite` |
| `pb_<symbole>` | `pb_xbb_to` | `pire_baisse` |
| `rattrapage_<symbole>` | `rattrapage_tsla` | `gain_de_rattrapage` |
| `corr_<a>_<b>` | `corr_nvda_qqq` | `correlations` |
| `ptf_<id>_<champ>` | `ptf_a_volatilite` | `stats_portefeuille` |
| `part_<id>_<symbole>` | `part_a_tsla` | `parts_du_risque` |
| `lim_<limite>`, `seuil_<mesure>` | `lim_max_crypto` | limites du profil |
| `sens_<symbole>` | `sens_xbb_to` | `sensibilite_taux` (FNB obligataires) |
| `pente_<pays>` | `pente_canada` | `pente_courbe` |
| `expo_<fnb>_<critere>` | `expo_esgv_controverse` | `tools.esg.exposition_fnb` : part du FNB dans des titres signalés |
| `inconnu_<fnb>_<critere>` | `inconnu_esgv_controverse` | même appel, `champ` = `part_inconnue` : part du FNB non jugée |

Dans un symbole, tout caractère autre qu'une lettre ou un chiffre devient `_`, en minuscules : `BTC-USD` donne `btc_usd`, `XBB.TO` donne `xbb_to`.

## Format v2 (branche agents-eagle)

`meta.version_format` vaut `2`. Les champs v2 s'ajoutent ; aucun champ v1 ne disparaît ni ne change de type. Une interface v1 continue de marcher.

### Profil

- `connaissance_niveau` (1 à 5) : curseur d'Eagle. Absent, il découle de `connaissance` (débutant 2, intermédiaire 3, avancé 4) et `profil.connaissance_niveau` est rempli dans la sortie.
- `centres_interet` : texte libre (« les jeux vidéo », « l'IA »). Un centre d'intérêt que l'univers ne couvre pas donne une entrée `non couvert` dans `adequation` et une limite spécifique, jamais un symbole inventé.

### Adequation

Une entrée par critère du profil : `horizon`, `objectif`, `tolerance`, `capital`, puis une entrée par élément de `preferences`, `exclusions` et `centres_interet` (une entrée « aucun » si la liste est vide). Écrite par le code, pas par un modèle.

| Champ | Type | Contenu |
| --- | --- | --- |
| `critere` | string | `horizon`, `objectif`, `tolerance`, `preferences`, `exclusions`, `centres_interet`, `capital` |
| `element` | string ou null | L'élément de la liste (« ESG », « énergies fossiles »), null pour un critère simple |
| `attente` | string | Ce que le profil demande, en clair |
| `reponse` | string | Ce que fait le portefeuille, avec repères `{id}` |
| `statut` | `respecté`, `partiel` ou `non couvert` | `non couvert` : l'univers ou les données ne permettent pas de répondre |
| `raison` | string ou null | Obligatoire si `non couvert` : quelle donnée manque |
| `chiffres` | id[] | Au moins un chiffre, sauf si `non couvert` ou si la liste du profil est vide (« aucune exclusion déclarée ») |
| `regle` | string | La règle appliquée (hypothèse de l'équipe), par exemple « pire baisse du portefeuille au-dessus du seuil du profil » |

### Limites et hypothèses

| Champ | Type | Contenu |
| --- | --- | --- |
| `limites.limites_specifiques` | [{`texte`, `type`, `lignes`, `chiffres`, `importance`}] | Propres au portefeuille retenu, calculées par le code, triées de la plus à la moins importante pour ce profil (`importance` 1 = la première). Chaque `texte` nomme la ou les lignes et porte au moins un repère. `type` : `source_de_risque`, `dollar_americain`, `taux`, `duree_pire_baisse`, `recoupement_fnb`, `theme_non_couvert`, `donnee_manquante` |
| `limites.hypotheses_specifiques` | [{`texte`, `si_elle_tombe`, `type`, `chiffres`, `lignes`}] | Hypothèses dont dépend ce portefeuille, avec ce qui changerait si elles tombaient, chiffré par `tools/`. `type` : `fenetre`, `correlations`, `conversion_cad`, `plafonds` |
| `limites.methode` | string[] | Les phrases générales (biais du survivant, passé qui ne promet rien…), qui étaient avant dans `limites.limites` et `limites.hypotheses` |
| `limites.limites`, `limites.hypotheses` | string[] | Gardés pour l'interface v1 : les `texte` spécifiques, dans l'ordre d'importance, puis ceux du modèle |

### Explication

| Champ | Type | Contenu |
| --- | --- | --- |
| `registre` | {`niveau`, `nom`, `description`} | `niveau` = `connaissance_niveau`. `nom` : `courant` (1-2), `usuel` (3), `professionnel` (4-5) |
| `lexique` | [{`terme`, `definition`}] | Niveaux 1 et 2 : chaque terme technique employé dans l'explication, défini par le code (`agents/langage.py`). Vide aux niveaux 3 à 5 |

Le texte de l'explication change avec le niveau : mots courants aux niveaux 1 et 2, termes usuels au niveau 3, vocabulaire de gestion de portefeuille aux niveaux 4 et 5 (contribution au risque, corrélation, duration, perte maximale, sensibilité aux taux). Vouvoiement à tous les niveaux.

### Identifiants v2

| Forme | Exemple | Outil |
| --- | --- | --- |
| `poids_<id>_<symbole>` | `poids_a_tsla` | poids décidé par le constructeur |
| `ptf_<id>_duree_pire_baisse` | `ptf_a_duree_pire_baisse` | `stats_portefeuille`, durée du sommet au retour (ou à la fin de la fenêtre), en années |
| `ptf_<id>_<champ>_recent` | `ptf_a_volatilite_recent` | `stats_portefeuille` sur les deux dernières années (hypothèse « fenêtre ») |
| `ptf_<id>_<champ>_cotation` | `ptf_a_volatilite_cotation` | `stats_portefeuille` sans conversion en CAD (hypothèse « conversion ») |
| `ptf_<id>_vol_sans_diversification` | | `stats_portefeuille`, volatilité si toutes les corrélations valaient 1 |
| `expo_usd_<id>` | `expo_usd_a` | part du capital cotée en USD |
| `sens_ptf_<id>` | | sensibilité aux taux pondérée des lignes obligataires |
| `titre_<id>_<symbole>` | `titre_a_nvda` | `tools.esg.exposition_titre` : exposition réelle à un titre, en direct et via les FNB |
| `transp_<id>_<critere>` | `transp_a_activite_fossile` | `tools.esg.exposition_transparente` |
| `montant_pb_<id>` | | pire baisse du portefeuille appliquée au capital fictif, en dollars (`unite` « montant en CAD ») |
