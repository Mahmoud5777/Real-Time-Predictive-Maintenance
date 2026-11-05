# FOG - MP3 : Industrial Cloud Backend, Data Management and Analytics

Depot **exclusivement** dedie au mini-projet 3 de la plateforme
« Collaborative Fog Computing for Real-Time Predictive Maintenance ».

Perimetre : couche Cloud. Collecter les resultats des nœuds Fog, les stocker proprement dans
PostgreSQL, exposer une API REST documentee et calculer les KPI usine.

## Contenu du depot

```
mp3-cloud/          backend FastAPI + PostgreSQL (code, tests, migrations, seed)
contracts/          formats JSON acceptes + contrat OpenAPI publie par ce module
docs/               architecture et contrat de donnees tel que vu depuis le Cloud
infra/              configuration Mosquitto utilisee pour l ingestion
```

## Ce qui est volontairement absent

Les mini-projets 1 (simulateur + ML), 2 (nœuds Fog + scheduler) et 4 (dashboard + DevOps)
ne vivent **pas** ici. Ils ont leurs propres depots et branches. Ce depot ne contient que ce
que je livre et que je peux faire tourner seul.

Ce que j'en garde, sans en ecrire le code : la **definition exacte des messages entrants**
(`docs/DATA_CONTRACT.md`) et le **contrat sortant** (`contracts/openapi.yaml`). C'est la seule
frontiere qui doit rester commune, sinon mon integration contredit les autres.

## Démarrage

Le [guide d’autonomie MP3](GUIDE_AUTONOMIE_MP3.md) détaille le démarrage sous
PowerShell, les essais sans MP2 et les vérifications du backend.

```bash
cd mp3-cloud
cp .env.example .env
docker compose up -d db mosquitto
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m scripts.init_catalogue
docker compose up -d --build ingest
uvicorn app.main:app --reload
```

| URL | Role |
|---|---|
| http://localhost:8000/docs | Swagger / OpenAPI interactif |
| http://localhost:8000/healthz | Health check (Docker, CI, supervision) |
| http://localhost:8000/metrics | Metriques Prometheus |
| http://127.0.0.1:8001/metrics | Metriques du worker MQTT |

## Verification

```bash
cd mp3-cloud
python -m ruff check .            # lint
python -m pytest                  # tests unitaires + contrat HTTP
python -m pytest --postgres       # migrations + integrite dans une base jetable distincte
python -m pytest --mqtt           # inclut PostgreSQL et un broker MQTT jetable
python scripts/check_contract.py  # fixtures valides acceptees, invalides rejetees
python scripts/seed.py --scenario degradation --zone A --duration 60 --dump
```

## Plan de livraison

Les 12 taches, priorites, efforts et criteres de fin sont dans
`mp3-cloud/TASKS.md`. Les decisions de conception justifiees sont dans
`mp3-cloud/docs/API_DESIGN.md` et les formules de KPI dans `mp3-cloud/docs/KPI_FORMULAS.md`.
Le schema et les commandes de l'etape 2 sont dans
[DATABASE_SCHEMA.md](mp3-cloud/docs/DATABASE_SCHEMA.md).
Les entrees HTTP et MQTT sont realisees : voir
[HTTP_INGESTION.md](mp3-cloud/docs/HTTP_INGESTION.md) et
[MQTT_INGESTION.md](mp3-cloud/docs/MQTT_INGESTION.md). L'etape 4 est verifiee avec 149 tests.
L'etape suivante complete les API de lecture pour le dashboard.

## Regles internes

1. Un seul dossier de code : `mp3-cloud/`. Aucune fonctionnalite d un autre mini-projet n y entre.
2. Les secrets restent dans `.env` ; seul `.env.example` est versionné.
3. Tous les timestamps sont UTC (`timestamptz` en base, ISO-8601 avec `Z` dans les JSON).
4. Une tache = une branche courte (`feat/mp3/...`, `fix/mp3/...`), merge par PR vers `main`.
5. Modifier `contracts/` = changement visible par mes collegues : a annoncer explicitement.
