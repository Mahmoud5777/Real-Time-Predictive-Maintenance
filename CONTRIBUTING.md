# Contribuer au depot FOG

## Premier reflexe (une seule fois)

```bash
git clone <url-du-depot>      # ou garder le dossier local actuel
cd FOG
git remote add origin <url-du-depot>   # ex. https://github.com/<org>/fog-predictive-maintenance.git
git fetch origin
```

Si `main` est vide sur GitHub, pousser la base de travail :

```bash
git checkout master            # branche locale creee par git init
git branch -m main
git add . && git commit -m "chore(repo): scaffold 4 mini-projects and shared contracts"
git push -u origin main
```

## Ou tu travailles

Voir docs/BRANCH_WORKFLOW.md pour le schema complet (une branche par mini-projet, PR vers main).

| Qui | Dossier | Branche longue |
|---|---|---|
| Member 1 | `mp1-simulator/` | `mp1/simulator` |
| Member 2 | `mp2-fog/` | `mp2/fog` |
| **Member 3** | `mp3-cloud/`, `contracts/openapi.yaml` | **`mp3/cloud`** |
| Member 4 | `mp4-dashboard/`, `infra/`, `.github/` | `mp4/dashboard` |

Chacun **push uniquement sa branche**, puis ouvre une pull request vers `main`.
Personne ne push directement sur `main` (protection de branche a activer sur GitHub).

## Cycle quotidien

```bash
git switch mp3/cloud
git pull --rebase origin main          # rester synchronise
git switch -c feat/mp3/ingest-mqtt     # une tache = une branche courte
# ... code + tests ...
pytest -q && ruff check .
git add -p
git commit -m "feat(mp3): subscribe to fog prediction topics"
git push -u origin feat/mp3/ingest-mqtt
# PR -> base: mp3/cloud
```

Quand un lot est pret : PR `mp3/cloud` -> `main` (base : MP3 relit les impacts contrat).

## Messages de commit

`type(portee): description imperative` — `feat`, `fix`, `docs`, `test`, `perf`, `refactor`, `chore`.
Exemples : `feat(mp3): add paginated measurements endpoint`, `fix(mp2): keep critical tasks local`.

## Protections a demander sur GitHub (MP4 ou toi)

- `main` : require a pull request, 1 approval, status checks verts (`contracts`, `mp3-backend`).
- Blocage du push force et de la suppression de branches protegees.
- Contributeurs en lecture sur les dossiers des autres : on evite les modifications croisees silencieuses.

## Ce qui est interdit

- Committer un secret (`.env`, token MQTT, mot de passe BDD). Seul `.env.example` est versionne.
- Modifier `contracts/` sans PR etiquetee `BREAKING` + accord explicite.
- Melanger deux mini-projets dans un meme commit/PR.
- Pusher un build rouge : si CI casse, on reverts ou on fixe avant toute autre feature.

## Definition of Done

- [ ] Execute via `docker compose up` sans geste manuel non documente.
- [ ] Tests pytest verts depuis un clone frais.
- [ ] Variables d environnement ajoutees a `.env.example`.
- [ ] Route/topic/fonction documente dans le README du mini-projet.
- [ ] KPI associe mesure et reporte dans le rapport.

