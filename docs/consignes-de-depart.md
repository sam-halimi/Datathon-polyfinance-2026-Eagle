# Consignes de départ

Une personne et une session Claude Code par branche. Coller la consigne telle quelle.

## Branche `outils`

```
Lis CLAUDE.md et docs/contexte.md. Écris les fonctions de tools/ listées dans CLAUDE.md, avec des tests pytest sur les vrais CSV de data/. Commence par charger_prix, convertir_cad, aligner_calendriers, rendements, volatilite, pire_baisse. Tes résultats doivent retrouver les chiffres du tableau de docs/contexte.md. Montre-moi les résultats des tests avant de continuer.
```

Ensuite : `stats_portefeuille`, `parts_du_risque`, `sensibilite_taux`, `pente_courbe`, `gain_de_rattrapage`, `rendement_en_cad`, `verifier_contraintes`. Puis les données à ajouter (ESG, composition des FNB), chacune avec sa ligne dans `data/sources_metadata.csv`.

## Branche `agents`

```
Lis CLAUDE.md et docs/contexte.md. Écris le schéma du profil et les trois scénarios de tests/scenarios/ (Amira, Mateo, Robert) avec le résultat attendu de chacun. Ensuite déploie un premier agent Strands sur Bedrock qui appelle un seul outil, pour valider l'accès AWS avant de construire le pipeline.
```

Ensuite : orchestrateur, trois spécialistes, constructeur, gouvernance (2 essais au plus), explication à trois niveaux. Relancer les scénarios après chaque changement.

## Branche `interface`

```
Lis CLAUDE.md et docs/contexte.md. Construis l'écran d'appel et les six cartes en Next.js, à 390 px de large d'abord, avec des données d'exemple en JSON. Aucun défilement dans un écran. Pas de voix pour l'instant : accueil en texte.
```

Ensuite : barre d'étapes, bouton « tout voir », branchement au pipeline, puis la voix (ElevenLabs Agents) en dernier. Tester sur un vrai iPhone dès que l'écran d'appel existe.
