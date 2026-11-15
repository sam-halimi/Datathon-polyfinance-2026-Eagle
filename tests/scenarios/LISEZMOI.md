# Tests d'acceptation

Trois personas, un fichier chacun. Chaque fichier donne le profil validé par l'accueil, la demande
piège, le piège à éviter et les comportements attendus. À relancer après chaque changement du pipeline :

```bash
python -m pytest tests/scenarios
```

`test_scenarios.py` vérifie que les scénarios sont cohérents (profil valide, limites et symboles
existants, chiffres attendus retrouvés par `tools/`). `test_bout_en_bout.py` applique chaque `controle`
à la vraie sortie du pipeline, enregistrée dans `agents/sorties/`. Pour la régénérer (Bedrock requis) :

```bash
python -m agents.pipeline robert amira mateo
```

## Vocabulaire des contrôles

Les noms de limites (`max_titre_individuel`, `max_crypto`, `plafond_theme`…) renvoient à
`agents.profil.contraintes(profil)["limites"]`. Un contrôle porte sur chaque portefeuille simulé final.

| `type` | Vérifie |
| --- | --- |
| `plafond_poids` | Le poids des `symboles`, de la `classe` (crypto, etf_bond…) ou du `role` (theme) ne dépasse pas `max`. |
| `diversification` | Au moins `min_lignes` lignes et une part risquée sous `max_part_risquee`. |
| `presence_min` | Au moins un portefeuille contient chacun des groupes listés (poids > 0). |
| `controle_gouvernance` | La gouvernance affiche le contrôle `nom` avec le `statut` donné. |
| `chiffres_cites` | Les explications citent un chiffre produit par chaque appel d'outil, avec sa référence. `valeur_attendue` vient de `docs/contexte.md`. |
| `chiffre_cite_si_retenu` | Pour chaque ligne retenue de la `classe`, le chiffre de l'`outil` est cité. |
| `texte_absent` / `texte_present` | Motifs interdits ou exigés dans le texte affiché (`zone` : une carte précise). |
| `niveau_explication_par_defaut` | Niveau ouvert par défaut (1, 2 ou 3). |
| `exclu_ou_signale` | Les titres du `secteur` ont un poids nul, ou un signalement qui cite la `source`. |
| `esg_source_ou_inconnu` | Tout jugement ESG sur les `symboles` cite une ligne du `fichier` (source et date), sinon dit « information manquante ». |
| `transparence_fnb` | Pour chaque FNB large retenu, composition vérifiée dans le `fichier`, sinon limite signalée. |
