# Regles d equipe - FOG

## 1. Modele de branches

Une branche longue par mini-projet, plus des branches courtes dediees :

```
main                     # toujours stable, jamais pousse directement
`-- mp1/simulator
`-- mp2/fog
`-- mp3/cloud            # <- backend Cloud (Member 3)
`-- mp4/dashboard
```

Règles :
- On ne push **jamais** sur `main`.
- Une branche courte part toujours de sa branche de mini-projet : `feat/mp3/ingest-mqtt`, `fix/mp3/dedup-predictions`.
- Merge de la branche courte dans `mpX/...` par PR, puis `mpX/...` vers `main` par PR quand le lot est fini.
- Rebase `origin/main` au moins une fois par jour sur sa branche pour limiter les conflits.

### Cycle de travail quotidien

```bash
git fetch origin
git checkout mp3/cloud
git pull --rebase origin main          # synchronisation
git checkout -b feat/mp3/<sujet>
# ... travail ...
pytest -q                              # tests verts avant tout commit
git add -p                             # ne commiter que ce qui compte
git commit -m "feat(mp3): add MQTT prediction ingestion"
git push -u origin feat/mp3/<sujet>    # puis ouvrir la PR vers mp3/cloud
```

## 2. Commits

Format Conventional Commits, scope obligatoire = mini-projet :

```
feat(mp3): expose GET /api/v1/analytics/kpis
fix(mp2): stop migrating tasks flagged critical
chore(mp1): add bearing-wear scenario fixtures
docs(mp4): document failure demo script
test(mp3): cover duplicate message rejection
```

Types autorises : `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`.
Une ligne = 72 caracteres max. L imperatif : « add », pas « added ».

## 3. Revues de code

- 1 approbation suffisante (le responsable du mini-projet concerne).
- Le MP3 relit obligatoirement toute modification de `contracts/` : il bloque MP4 sinon.
- Un PR > 400 lignes doit etre decoupee.

## 4. Definition of Done (par livrable)

- [ ] Code execute localement via `docker compose up` sans geste manuel.
- [ ] Tests pytest passent depuis un clone frais.
- [ ] Variables d environnement documentees dans `.env.example`.
- [ ] Aucun secret en Git (`gitleaks` ou recherche manuelle).
- [ ] Endpoint / topic / fonction decrit dans le README du mini-projet.
- [ ] KPI ou metrique associe mesure et reporte (pas d impression).

## 5. Contrat inter-mini-projets

Semaine 1 = congele des formats. Apres congele, toute evolution passe par :
1. Issue/PR avec la mention `BREAKING`;
2. Accord explicite des membres impactes;
3. Migration prevue pour les donnees existantes.

## 6. Calendrier recommande

| Semaine | MP1 | MP2 | MP3 | MP4 |
|---|---|---|---|---|
| 1 | Formats + scenarios | Topics + heartbeat | **OpenAPI + schema BDD** | Maquettes |
| 2 | Detection regles | Services Fog A/B/C | Ingestion + validation | Dashboard statique |
| 3 | ML + evaluation | Scheduler + migration | Lecture + pagination | Vue machines |
| 4 | Tests + datasets | Fault tolerance | KPI + analytics | Vue Fog + alertes |
| 5 | Rapport metriques | Benchmark statique/dynamique | Perf + rapport | Grafana + CI |
| 6 | Integration + demo complete sur `main` ||||

## 7. Gestion des conflits

- Les fichiers de perimetre sont cloisonnes : chaque MP ne touche que son dossier, sauf `contracts/` et `infra/docker-compose.yml` (modification concertee).
- `pyproject.toml` / `requirements.txt` par mini-projet, pas de fichier global partage.
