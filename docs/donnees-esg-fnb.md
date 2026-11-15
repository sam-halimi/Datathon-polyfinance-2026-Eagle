# Tables ESG et composition des FNB

Trois fichiers dans `data/`, ajoutés par la branche `donnees` le 15 novembre 2026. Leurs sources et leurs limites sont aussi dans `data/sources_metadata.csv`. Contrôles : `pytest tests/donnees`.

## `esg_actions.csv` : une ligne par action de l'univers (20)

| Colonne | Contenu |
| --- | --- |
| `activite_fossile` | `oui` si la société tire des produits de l'exploration, la production, le raffinage, le transport, le stockage, la distribution ou la vente au détail de pétrole, gaz ou charbon, ou produit de l'électricité fossile. Ce sont les critères de l'indice FTSE Global Choice v5.0, que suit ESGV. Le financement par une banque n'est pas compté : il est décrit dans `precision_fossile` quand le chiffre a été trouvé |
| `controverse` | `oui` si une source officielle (régulateur, tribunal, dépôt annuel) documente une amende, un règlement, une condamnation ou un litige important, environnemental ou social. `non` si la note sur les litiges du dernier dépôt annuel n'en montre aucun. Sinon `inconnu` |
| `resume_controverse` | Les faits et l'ampleur. L'ampleur varie beaucoup : 278 000 $ pour CNQ, 3,088 G$ US pour TD. L'agent ESG doit citer ce texte, pas seulement le `oui` |
| `retenu_par_esgv` | `oui` ou `non` selon la composition d'ESGV au 31 août 2026, `sans objet` pour les titres canadiens (hors de l'univers de l'indice) |
| `source_*_url`, `source_*_date` | La page ouverte et sa date de publication, pour chaque valeur |
| `notes` | Doutes et éléments non vérifiés |

Les extraits qui appuient chaque valeur sont dans `esg_sources.csv` (champ `fossile`, `controverse`, `esgv` ou `complement`).

Résultat : 6 actions ont une activité fossile (ENB, CNQ, CNR, FTS, ATD, XOM), 15 ont une controverse documentée, et 5 n'en ont pas dans leur dernier dépôt (ATD, SHOP, CSU, NVDA, PG). ESGV ne détient ni XOM (exclusion fossile publiée par Vanguard) ni JNJ (aucun motif publié, ne pas en inventer).

## Ce que ces tables ne disent pas

- `non` ne prouve pas l'absence de controverse : seuls le dépôt annuel et quelques sources officielles ont été lus.
- Les affaires de concurrence et de fiscalité sont classées en gouvernance et ne comptent pas (amendes de l'UE contre Apple et Alphabet, par exemple). Elles figurent dans `notes`.
- Aucune note ESG de fournisseur (MSCI, Sustainalytics) n'est utilisée.
- Les extraits ont été relevés avec un outil de lecture de pages. Certains réunissent deux fragments par « ... ». À revérifier sur la page avant une citation mot pour mot.
- Rien n'est suivi après le 15 novembre 2026.

## `fnb_composition.csv`

`fnb, symbole_detenu, nom_detenu, poids, date, source_url`. Le poids est une fraction de l'actif net (0,0712 pour 7,12 %).

| FNB | Date | Lignes | Source |
| --- | --- | --- | --- |
| SPY | 2026-11-12 | 505, tout le fonds | Fichier quotidien de State Street |
| QQQ | 2026-11-12 | 105, tout le fonds | Données du site d'Invesco |
| XIU.TO | 2026-11-12 | 65, tout le fonds | CSV de BlackRock iShares Canada |
| ESGV | 2026-08-31 | 9, titres de l'univers seulement | Formulaire N-PORT à la SEC |

À savoir :

- Pour ESGV, les poids ont été lus dans le N-PORT avec un outil de lecture de pages, pas téléchargés. Ils sont donc à revérifier. La date a aussi 2,5 mois de retard sur les trois autres fonds.
- QQQ détient `SHOP`, la cotation Nasdaq de Shopify : même société que `SHOP.TO`, mais autre cotation et autre devise.
- Dans XIU.TO, `NA` est le symbole de la Banque Nationale. Lire le fichier avec `keep_default_na=False`, sinon pandas en fait une valeur manquante.
- Les symboles détenus hors de notre univers ne sont pas des actifs du projet. Pour en ajouter un, il faut passer par `assets_universe.csv` et `build_dataset.py`.
