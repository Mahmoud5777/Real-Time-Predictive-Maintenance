# Semaine 1 - points a valider en equipe (owner: MP3)

Objectif : congele des contrats. Sans cela, l integration se fait en larmes en semaine 5.

## Ordre du jour (45 min)

1. **Formats JSON** (`docs/DATA_CONTRACT.md`) - 10 min
   - Chaque champ est-il produit reellement par MP1/MP2 ? Supprimer ce qui n existe pas, ajouter ce qui manque.
   - Validation explicite : `message_id` genere par qui ? (reponse attendue : le producteur).
2. **Topics MQTT** (`contracts/mqtt-topics.md`) - 10 min
   - QoS 1 + retain sur status uniquement. MP2 accepte-t-il ?
   - Un message capte par deux consommateurs ne doit jamais creer deux lignes en base.
3. **Contrat OpenAPI** (`contracts/openapi.yaml`) - 15 min
   - MP4 confirme que les routes suffisent pour son dashboard (zones, machines, alertes, sante Fog, migrations, KPI).
   - Nommage : `/api/v1`, pluriel, kebab-case. Pagination `limit`/`offset`.
4. **Timestamps et identifiants** - 5 min
   - UTC partout, ISO-8601 avec `Z`, `timestamptz` en base.
   - `task_id` = UUIDv4 stable ; `alert_id` unique global.
5. **Decoupage et dates** - 5 min
   - Qui livre quoi fin semaine 2 / 3 / 4 ; jalons de test croise.

## Questions ouvertes a trancher maintenant

| Question | Position MP3 (proposee) | Impact si non tranche |
|---|---|---|
| Ingestion Cloud : MQTT ou HTTP push ? | MQTT principal + HTTP batch de secours | MP3 depend du planning MP2 |
| Qui definit les KPI et leurs formules ? | MP3, formule ecrite dans le rapport | Dashboard incoherent |
| Retention des mesures brutes ? | 7 jours + agregrats illimites | Perfs API degradees en demo |
| Temps reel vers MP4 ? | SSE depuis MP3 | MP4 poll et perds en latence |
| Auth ingestion ? | Bearer token via env | Endpoint d ecriture ouvert |
| Definition critique vs non critique ? | critique = detection temps reel + alarme | Choix de migration arbitraire |

## Livrables exiges de chaque membre fin semaine 1

- MP1 : echantillon reel de 60 s de données d une machine au format contrat.
- MP2 : liste definitive des topics publies + exemple de payload par topic.
- MP3 : `openapi.yaml` publie + fixtures valides/invalides dans `contracts/fixtures/`.
- MP4 : maquette des vues + confirmation ecrite qu il peut mocker ces routes.

## Regle de sortie de semaine 1

Aucune ligne de code metier n est mergee tant que les 4 membres n ont pas approuve la PR
`chore(contracts): freeze data contract and openapi`.
