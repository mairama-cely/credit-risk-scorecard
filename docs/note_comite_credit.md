# Recommandations au comité de crédit

> Grille de score d'octroi, données publiques Home Credit (Kaggle). Généré par `scripts/build_reports.py` depuis `output/tables/`. Mesures sur le test scellé (46 127 demandes, lu uniquement par l'évaluation finale, sans aucun réglage dessus). Montants en unités du jeu de données.

**Décision demandée.** (1) Adopter la grille de score (17 variables, 439 à 660 points) comme modèle de décision ; (2) retenir le scénario **Prudent** (seuil 563, revue manuelle de 553 à 572) ; (3) conditionner la mise en production aux réserves ci-dessous.

**Scénario recommandé (test, LGD 45 %).** Acceptation **60,3 %**, défaut des acceptés **3,44 %** contre 8,07 % sans seuil, **69,9 %** de la perte attendue évitée (632,6 M sur 904,9 M), pour 36,7 % de bons clients refusés.

| Scénario | Seuil | Acceptation | Défaut des acceptés | Bons refusés | Perte évitée | Zone de revue |
|---|---:|---:|---:|---:|---:|---:|
| **Prudent (recommandé)** | 563 | 60,3 % | 3,44 % | 36,7 % | 632,6 M (69,9 %) | 25,4 % |
| Équilibré | 550 | 75,3 % | 4,49 % | 21,8 % | 482,1 M (53,3 %) | 20,2 % |
| Croissance | 539 | 85,0 % | 5,43 % | 12,6 % | 350,2 M (38,7 %) | 15,4 % |

Règle fixée avant le test : maximiser « part de perte évitée − part de bons refusés » sur la validation. Le scénario Équilibré devient rentable si la marge nette d'un bon crédit dépasse **4,2 % du montant prêté** (donnée à fournir par la banque).

**Choix du modèle.** La **grille** : lisible, motifs de refus, calibrée (écart moyen par décile 0,20 pt), stable (AUC train 0,7544, test 0,7518). **LightGBM** reste challenger : AUC test 0,7883, écart +0,0365 (IC 95 % [0,0319 ; 0,0408]), mais moins explicable et sur-appris (AUC train 0,8808).

**Risques et conditions.**

- **Équité** : ratio d'acceptation H/F 0,821 (règle des 4/5 respectée de peu), 0,841 parmi les bons clients ; revue de conformité requise.
- **Zone de revue** : 25,4 % des demandes (≈ 11 714 dossiers au test) ; capacité des analystes à valider.
- **Scores externes** : 3 variables sur 17 dérivent de `EXT_SOURCE`, premier motif de 99,5 % des refus ; source locale équivalente à identifier.
- **LGD supposée** : de 35 % à 55 %, perte attendue acceptée de 211,8 M à 332,9 M.
- **Transposabilité** : données Home Credit ≠ portefeuille camerounais ; PD et seuils à **recalibrer sur l'historique de la banque**.

**Prochaines étapes.** (1) Rejouer la grille sur l'historique interne et recalibrer ; (2) pilote en double run ; (3) suivi mensuel : PSI (alerte > 0,10), défaut des acceptés (référence 3,44 %), calibration, Gini (alerte sous 0,487), ratio H/F (alerte sous 0,80) ; (4) revue annuelle face au challenger.
