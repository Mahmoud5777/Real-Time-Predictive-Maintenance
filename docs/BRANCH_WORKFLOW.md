# Workflow Git du projet FOG

## Principe

**Une branche de mini-projet par personne.** Chacun travaille, commit et **push sur SA
branche**. Le regroupement dans `main` se fait par pull request, jamais par push direct.

```
main  (stable, protegee)
  |-- mp1/simulator     <- Member 1   -> dossier mp1-simulator/
  |-- mp2/fog           <- Member 2   -> dossier mp2-fog/
  |-- mp3/cloud         <- Member 3   -> dossier mp3-cloud/ + contracts/openapi.yaml
  |-- mp4/dashboard     <- Member 4   -> dossier mp4-dashboard/ + infra/ + .github/
```

Pourquoi ce choix : les 4 mini-projets sont developpes en parallele. Une branche par projet
evite qu un code incomplet casse les autres, tout en gardant un seul depot (obligation du cahier
des charges).

## Mise en place (une seule fois, par celui qui cree le depot remote)

```bash
cd C:\Users\User\Desktop\FOG
git remote add origin https://github.com/<org>/<depot>.git
git branch -M main                      # renommer la branche locale en main
git push -u origin main                 # pousser la base commune
git push origin main:mp1/simulator      # creer les 4 branches de travail
git push origin main:mp2/fog
git push origin main:mp3/cloud
git push origin main:mp4/dashboard
```

Ensuite, sur GitHub : **Settings → Branches → Add rule** sur `main`
→ *Require a pull request before merging* + *Require status checks to pass*.

## Cycle de travail quotidien (exemple MP3)

```bash
git fetch origin
git switch mp3/cloud
git pull --rebase origin main            # rester aligne sur la base

git switch -c feat/mp3/ingest-mqtt       # une tache = une branche courte
# ... coder ...
python -m ruff check . && python -m pytest
git add -p
git commit -m "feat(mp3): subscribe to fog prediction topics"
git push -u origin feat/mp3/ingest-mqtt  # PR vers mp3/cloud
```

Quand un lot est termine : **PR `mp3/cloud` → `main`**, relue par le membre impacte.

##branches courtes autorisees

| Prefixe | Quand |
|---|---|
| `feat/<mp>/<sujet>` | nouvelle fonctionnalite |
| `fix/<mp>/<sujet>` | correction de bug |
| `perf/<mp>/<sujet>` | optimisation (ex. batch writes) |
| `test/<mp>/<sujet>` | ajout de tests seul |
| `docs/<mp>/<sujet>` | documentation |
| `chore/<mp>/<sujet>` | config, deps, migrations |

## Commits

`type(portee): phrase imperative` — ex. `feat(mp3): expose GET /analytics/kpis`.
Portee = `mp1`, `mp2`, `mp3`, `mp4` ou `repo`/`contracts` pour le partage.

## Regles de conflits

- Un membre ne modifie **que son dossier**, plus `contracts/` (accord prealable obligatoire).
- `contracts/openapi.yaml` et `docs/DATA_CONTRACT.md` sont la propriete de MP3 : toute
  modification non retrocompatible passe par une PR etiquetee `BREAKING` + accord de MP4.
- `infra/docker-compose.yml` global appartient a MP4 ; MP3 garde son propre
  `mp3-cloud/docker-compose.yml` pour travailler seul.
- Pas de rebase d une branche deja pushee partagee ; utiliser merge.

## Ce qui casse la CI (donc bloque le merge)

- `ruff check` ou `pytest` rouges dans `mp3-cloud/`.
- `contracts/openapi.yaml` invalide (job `contracts`).
- Une fixture de `contracts/fixtures/valid/` rejetee, ou une fixture `invalid/` acceptee.
- Un secret commité : `.env` n est jamais suivi, seul `.env.example` l est.
