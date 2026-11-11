# CPI Radar Online

Application Streamlit prête à déployer. Les prévisions sont automatiques, sans choix de modèle par l'utilisateur.

## Mise en ligne (Streamlit Community Cloud)
1. Créer un dépôt GitHub et y importer **tous** les fichiers de ce dossier, dont `app.py`, `engine.py` et `requirements.txt`.
2. Aller sur https://share.streamlit.io/ et connecter GitHub.
3. Sélectionner le dépôt, branche `main`, fichier principal `app.py`, puis cliquer sur **Deploy**.
4. Ouvrir l'URL obtenue. Les données FRED sont actualisées toutes les 6 heures lors des visites, et les données BTC toutes les heures. La page doit être ouverte pour afficher les nouvelles valeurs.

## Sources
- FRED : `CPIAUCSL`, `CPILFESL`, `GASREGW`, `DGS10`, `DFF` via `https://fred.stlouisfed.org/graph/fredgraph.csv?id=...`.
- CoinGecko API publique : historique de prix Bitcoin 31 jours. Les limites d'accès peuvent temporairement bloquer la récupération.

## Limites importantes
- Ce prototype prédit **le mois suivant le dernier mois CPI publié**, et non un nowcast complet révisé au fil des jours du mois courant. L'essence utilisée est celle du **dernier mois connu**, pas une estimation de l'essence du mois en cours.
- Le modèle est choisi sur validation 2023–2025, pas sur le test 2026. Il ne faut pas considérer la meilleure MAE de 2026 comme un choix ex ante.
- Backtests rétrospectifs avec données FRED potentiellement révisées, pas des données archivées en temps réel.
- Le consensus des économistes n'est pas connecté, donc aucune surprise attendue CPI/consensus n'est calculée.
- L'indicateur crypto est descriptif. Il ne prédit pas de retournement et ne constitue pas un conseil financier.
- L'actualisation est basée sur le cache Streamlit au moment de la consultation, pas sur un processus permanent en arrière-plan.

## Exécution locale (facultative)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Prochaine étape scientifique
Collecter les snapshots datés des prévisions, intégrer un consensus prépublication sous licence appropriée, des données intramensuelles (essence, logement, autres indicateurs), et évaluer le pouvoir prédictif de la surprise anticipée sur les rendements BTC/ETH à horizon défini en évitant tout lookahead.
