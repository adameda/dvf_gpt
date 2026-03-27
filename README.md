# DVF GPT

Assistant conversationnel immobilier basé sur les données publiques DVF (Demandes de Valeurs Foncières) en France.

Ce projet permet de poser des questions en langage naturel, par exemple:

- "Quel est le prix au m2 à Lyon ?"
- "Trouve des comparables pour un appartement de 70m2 à Paris"
- "Estime une maison de 95m2 à Toulouse"

L'application répond en francais, affiche les chiffres clefs et propose des visualisations (carte, graphique, tableau).

## 1) A quoi sert le projet

DVF GPT sert a:

- expliquer rapidement le marche immobilier local a partir de donnees reelles;
- comparer des zones geographiques (villes ou departements);
- produire une estimation simple de bien basee sur des transactions comparables;
- presenter des resultats lisibles a un public non technique.

## 2) Stack technique

- Backend: Flask 3
- Base analytique: DuckDB
- Traitement data: Pandas/SQL
- LLM: Google Gemini (`gemini-2.5-flash`)
- Validation/contrats: Pydantic v2
- Frontend: HTML + Tailwind CSS + Leaflet + Chart.js + Marked

## 3) Comment ca marche

Pipeline d'une question:

```text
Question utilisateur
-> Gemini detecte l'intention (prix, comparables, estimation, etc.)
-> Validation stricte (Pydantic)
-> Service metier Python
-> Requetes SQL sur DuckDB (base locale DVF)
-> Resume des resultats
-> Gemini reformule la reponse en francais naturel
-> Frontend affiche texte + visualisation
```

Point important:

- Le LLM ne calcule pas les prix.
- Le LLM sert uniquement a comprendre la demande et reformuler la reponse.
- Les calculs metier et les requetes sont geres par le code Python + DuckDB.

## 4) Fonctionnalites disponibles

Le systeme gere 5 intentions metier:

| Intention | Exemple de question | Resultat principal |
|---|---|---|
| `prix_m2` | "prix m2 a Bordeaux" | prix median/moyen, volume, carte |
| `comparables` | "comparables appartement 70m2 Paris" | liste de transactions similaires + carte |
| `estimation` | "estimation maison 90m2 Marseille" | fourchette basse/haute + valeur centrale |
| `evolution` | "evolution des prix a Nantes" | evolution annuelle en graphique |
| `comparaison` | "comparer Lyon et Paris" / "comparer le 75 et le 69" | ecart en pourcentage + bar chart |

Comportements utiles:

- Arrondissements agreges pour Paris, Lyon, Marseille.
- Messages d'aide si ville/surface manquante.
- Message explicite si la base DVF locale n'est pas construite.

## 5) Architecture du projet

```text
dvf-gpt/
├── app/
│   ├── __init__.py                 # Factory Flask + enregistrement des routes
│   ├── llm/
│   │   └── gemini_client.py        # Parsing d'intention + generation de reponse
│   ├── models/
│   │   └── schemas.py              # Modeles Pydantic (Intent, Resultats, ChatResponse)
│   ├── repositories/
│   │   └── dvf_repository.py       # Toutes les requetes SQL DuckDB
│   ├── routes/
│   │   ├── api.py                  # /api/chat et /api/health
│   │   └── web.py                  # /
│   ├── services/
│   │   ├── chat_service.py         # Orchestration complete du pipeline
│   │   ├── intent_service.py       # Appel parse intent
│   │   ├── response_service.py     # Appel reformulation
│   │   └── dvf/
│   │       ├── price_service.py
│   │       ├── comparables_service.py
│   │       ├── estimation_service.py
│   │       ├── trend_service.py
│   │       └── comparison_service.py
│   └── templates/
│       └── index.html              # Interface web (chat + cartes + graphiques)
├── scripts/
│   └── build_dvf_database.py       # ETL DVF -> data/dvf.duckdb
├── data/
│   └── dvf.duckdb                  # Base locale generee
├── run.py                          # Point d'entree Flask
├── requirements.txt
└── .env.example
```

## 6) Zoom technique detaille sur une intention: prix_m2

Cette section explique le fonctionnement complet sur un seul cas d'usage.
Les autres intentions suivent ensuite la meme logique globale.

Exemple de question:

- "prix m2 a Lyon appartement"

Ce que le systeme doit extraire:

- type = prix_m2
- ville = Lyon
- type_local = Appartement

Chemin d'execution dans le code:

1. **app/routes/api.py**
   - valide que le champ message existe;
   - appelle chat_service.handle_message(question).
3. **app/services/chat_service.py** (fonction _handle_prix_m2)
   - verifie qu'on a au moins une ville ou un departement;
   - appelle price_service.get_prix_m2(intent).
5. **app/services/dvf/price_service.py**
   - delegue la requete a dvf_repository.fetch_prix_m2(...);
   - transforme la ligne SQL en objet metier PrixM2Result.
7. **app/repositories/dvf_repository.py**
   - calcule les statistiques SQL:
     - prix median au m2;
     - prix moyen au m2;
     - volume de transactions;
     - percentiles bas/haut (p10/p90);
     - latitude/longitude moyennes pour la carte.
9. retour dans **chat_service/**
    - construit un resume metier;
    - demande une reformulation naturelle a Gemini;
    - retourne une reponse API structuree (message + data + type de visualisation).

Points techniques importants:

- Paris, Lyon et Marseille agregent automatiquement leurs arrondissements.
- Si aucune donnee n'est trouvee, le systeme renvoie un message explicite.
- Le LLM ne fait pas les calculs: il reformule des chiffres deja calcules.

## 7) Les autres intentions: meme structure, regles differentes

Les intentions comparables, estimation, evolution et comparaison utilisent la meme architecture:

1. intention parsee;
2. routage vers un service dedie;
3. requete(s) SQL via repository;
4. resume metier;
5. reformulation finale.

Ce qui change entre les intentions:

- comparables: filtre ville + type de bien + surface dans une plage de +/-20%.
- estimation: reutilise les comparables puis applique une fourchette simple de +/-10%.
- evolution: calcule une serie annuelle (prix median et volume).
- comparaison: compare 2 zones (2 villes ou 2 departements) et calcule l'ecart en pourcentage.

## 8) Modele de donnees et contrats (Pydantic)

Le fichier app/models/schemas.py garantit la stabilite des echanges entre couches.

Contrats principaux:

- Intent: structure extraite depuis la question utilisateur.
- Resultats metier: PrixM2Result, ComparablesResult, EstimationResult, EvolutionResult, ComparaisonResult.
- ChatResponse: format final renvoye par l'API.

Pourquoi c'est important pour le projet:

- moins d'erreurs de type au runtime;
- validation automatique des bornes (ex: confidence entre 0 et 1);
- format de sortie stable pour le frontend.

## 9) Couche SQL centralisee (repository)

Toutes les requetes SQL sont regroupees dans app/repositories/dvf_repository.py.

Principes appliques:

- une seule couche pour parler a la base;
- requetes parametrees (placeholders) pour securiser les entrees;
- fonctions dediees par besoin metier (fetch_prix_m2, fetch_comparables, fetch_evolution, fetch_comparaison).

Pourquoi ce choix d'architecture:

- la logique SQL n'est pas dispersee dans tout le code;
- maintenance plus simple si le schema evolue;
- meilleure lisibilite lors d'une revue technique.

## 10) Construction de la base DVF locale (pipeline data)

Le script scripts/build_dvf_database.py fait tout le pretraitement avant utilisation par l'API.

Etapes detaillees:

1. Telechargement des fichiers DVF par annee et departement.
2. Lecture des CSV (avec fallback de separateur si necessaire).
3. Aggregation par id_mutation pour eviter les doublons metier.
4. Filtres metier:
        - nature de mutation = Vente;
        - type_local = Appartement ou Maison;
        - surface > 0 et valeur fonciere > 0;
        - latitude/longitude presentes.
5. Calcul du prix_m2.
6. Suppression des outliers par type de bien (quantiles 5%-95%).
7. Ecriture dans la table transactions_clean de DuckDB.
8. Creation d'index pour ameliorer les temps de reponse.

Pourquoi ce pretraitement est crucial:

- il deplace la complexite data en amont;
- il fiabilise les statistiques exposees au chat;
- il accelere les requetes pendant l'utilisation en direct.

## 11) Prerequis

- Python 3.10+
- Connexion internet (pour telecharger les donnees DVF)
- Cle API Gemini (Google AI Studio)

## 12) Installation rapide

### Etape 1: installer les dependances

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Etape 2: configurer l'environnement

```bash
cp .env.example .env
```

Modifier .env et renseigner:

```env
GEMINI_API_KEY=your_real_key
FLASK_ENV=development
FLASK_DEBUG=1
```

### Etape 3: construire la base DVF locale

```bash
# Donnees larges (long et volumineux)
python scripts/build_dvf_database.py

# Variante recommandee pour un test rapide
python scripts/build_dvf_database.py --years 2024 --departments 75 69 13
```

### Etape 4: lancer l'application

```bash
python run.py
```

Application web:

- http://localhost:5001/

Verification sante API:

- http://localhost:5001/api/health

## 13) API (pour integrer ou tester)

### POST /api/chat

Entree:

```json
{
        "message": "prix m2 a Lyon appartement"
}
```

Sortie type (exemple):

```json
{
        "intent": "prix_m2",
        "message": "...",
        "data_type": "prix_m2",
        "data": {
                "ville": "Lyon",
                "type_local": "Appartement",
                "prix_median_m2": 5200.0,
                "prix_moyen_m2": 5500.0,
                "volume_transactions": 1234,
                "prix_min_m2": 3600.0,
                "prix_max_m2": 7900.0,
                "annee": 2024,
                "latitude": 45.764,
                "longitude": 4.8357
        },
        "visualisation": "map",
        "debug": {
                "steps": ["..."],
                "intent_parsed": {
                        "type": "prix_m2"
                }
        }
}
```

### GET /api/health

Reponse:

```json
{
        "status": "ok",
        "database": "ready"
}
```

Si la base n'existe pas encore:

```json
{
        "status": "ok",
        "database": "missing"
}
```

## 14) Interface utilisateur

L'interface web inclut:

- un chat principal;
- un panneau de visualisation (affichable/masquable);
- des cartes Leaflet pour localiser les points;
- des graphiques Chart.js pour evolution et comparaison;
- un tableau de comparables (date, surface, prix/m2, prix total);
- un bloc de raisonnement (debug) pour expliquer les etapes de traitement.

## 15) Depannage rapide

1. Erreur "base non disponible": lancer `python scripts/build_dvf_database.py`.
2. Reponse vide sur une ville: verifier l'orthographe ou tester un departement.
3. Erreur LLM: verifier `GEMINI_API_KEY` dans `.env`.
4. Port incorrect: l'application tourne par defaut sur `5001` (voir `run.py`).

## 16) Docker

Cette version est ideale si la base locale est présente dans le dossier data.

Pourquoi c'est utile:

- meme environnement pour tout le monde;
- lancement en une commande;
- pas besoin d'installer Python/venv sur chaque machine.

Ce qui est fourni dans le repo:

- Dockerfile: image Python + installation des dependances avec uv + lancement Gunicorn;
- docker-compose.yml: demarrage simple avec port 5001;
- volume `./data:/app/data` pour reutiliser la base DuckDB locale.

### Prerequis

- Docker Desktop installe
- fichier .env present a la racine (avec GEMINI_API_KEY)
- base locale presente dans data/dvf.duckdb

### Lancer l'application avec Docker

```bash
docker compose up --build
```

Application disponible sur:

- http://localhost:5001/

Arreter:

```bash
docker compose down
```

### Notes importantes

1. Le conteneur lit la base locale grace au volume `./data:/app/data`.
2. Si `data/dvf.duckdb` est absent, l'API repondra que la base est manquante.
3. Le serveur dans Docker utilise Gunicorn (plus adapte qu'un serveur Flask dev).
