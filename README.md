# FOG - Collaborative Fog Computing for Real-Time Predictive Maintenance

Plateforme virtuelle de maintenance predictive : 12 machines simulees (3 zones A/B/C),
analyse locale sur 3 noeuds Fog, equilibre de charge par migration de taches,
tolerance aux pannes, backend Cloud central et dashboard industriel.

## Organisation du depot

| Dossier | Responsable | Perimetre |
|---|---|---|
| `mp1-simulator/` | Member 1 | Simulation des machines + modele ML de detection |
| `mp2-fog/` | Member 2 | Services Fog A/B/C, scheduler, migration, fault tolerance |
| `mp3-cloud/` | **Member 3** | API Cloud, PostgreSQL, ingestion MQTT, analytics, KPI |
| `mp4-dashboard/` | Member 4 | Dashboard React, Prometheus/Grafana, Docker Compose global, CI |
| `contracts/` | Tous | Formats JSON partages + contrat OpenAPI (figes en semaine 1) |
| `docs/` | Tous | Regles d integration, architecture, guide de demonstration |
| `infra/` | Member 4 + MP3 | Configuration Mosquitto, docker-compose partage |
| `scripts/` | Tous | Utilitaires transverses (seed, demo, verification) |

## Branche par mini-projet

Chaque membre travaille uniquement sur sa branche, puis ouvre une pull request vers `main`.

```bash
git checkout -b mp1/simulator     # Member 1
git checkout -b mp2/fog           # Member 2
git checkout -b mp3/cloud         # Member 3
git checkout -b mp4/dashboard     # Member 4
```

Autres branches autorisees : `feat/<portee>/<sujet>`, `fix/<portee>/<sujet>`,
`chore/<portee>/<sujet>` (ex. `chore/mp3/migrations`).

## Démarrage rapide (MP3 - backend Cloud)

```bash
cd mp3-cloud
cp .env.example .env
docker compose up -d db mosquitto
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Swagger : http://localhost:8000/docs

## Regles non negociables

1. Les secrets vivent dans `.env`, jamais commités.
2. Tout timestamp est en **UTC** (`timestamptz` en base, ISO-8601 dans les JSON).
3. Un changement dans `contracts/` doit etre annonce a l equipe avant le merge.
4. Chaque merge passe par une pull request + tests verts.
5. Le dashboard (MP4) ne lit **jamais** la base ni les services Fog directement : il passe par l API MP3.

## Documentation

- `docs/TEAM_RULES.md` - conventions Git, revues, definition of done
- `docs/ARCHITECTURE.md` - flux de donnees de bout en bout
- `docs/DATA_CONTRACT.md` - formats JSON partages
- `mp3-cloud/README.md` - perimetre et livrables du backend Cloud

