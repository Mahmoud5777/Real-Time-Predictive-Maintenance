# Retention des mesures et predictions - etape 8

Reference executable : `app/retention/service.py`. Le worker retention traite un lot
de l'heure expiree la plus ancienne toutes les 60 secondes. **La simulation est active
par defaut** : le worker indique les candidats sans supprimer de donnees.

## Politique et perimetre

RAW_RETENTION_DAYS reste 7 par defaut. La limite est ramenee a l'heure UTC precedente :
seules les heures entierement expirees sont eligibles. A 12:30 avec sept jours de
retention, une observation datant d'exactement sept jours a 12:00 est conservee.
Les donnees brutes sont purgees par timestamp producteur, pas par reception Cloud.

- sensor_data : mesures expirees, avec conservation permanente de la derniere mesure
  de chaque machine pour `/machines/{machine_id}/latest`.
- predictions : predictions expirees.
- Alertes, taches, evenements de taches et tout fog_status_history : conserves, y compris
  alertes ouvertes, resolutions, charges Fog et preuves de supervision.
- Catalogues, agregrats KPI et preuves techniques de deduplication : conserves.

Ce premier perimetre cible les deux sources a fort volume. Il ne purge pas les preuves
necessaires a l'exploitation ou aux comparaisons de collaboration Fog. Il n'introduit
aucun partitionnement ni calendrier de suppression pour alertes/taches/supervision.
Le dimensionnement de leurs historiques et du registre technique reste a mesurer.

## Deduplication apres suppression

La migration `0004_retention_receipts` ajoute **ingest_receipts**, une table technique
distincte des neuf tables metier. PostgreSQL contient donc neuf tables metier et deux
tables techniques : alembic_version et ingest_receipts, soit onze tables au total.

Le registre conserve kind + message_id et une empreinte SHA-256 binaire de 32 octets.
Les clefs sont independantes pour sensor et prediction. L'empreinte porte sur les champs
producteurs valides, avec valeurs facultatives explicites, UTC et nombres normalises,
sans arrondi Decimal. Format JSON, ordre des champs, fuseau equivalent et echelle
decimale equivalente ne changent pas l'identite. Elle n'est pas un label de verite terrain.

Ingestion et registre sont transactionnels : rejet ou rollback ne conserve pas de clef
orpheline. Une retransmission identique reste un doublon apres suppression du brut ;
un contenu different sous la meme clef reste MESSAGE_ID_CONFLICT. Les lignes anciennes
anterieures a cette migration sont equipees d'une empreinte avant leur suppression.
Le dernier capteur ancien conserve peut recevoir sa preuve lors de sa retransmission.
Un desaccord entre empreinte et ligne source annule tout le cycle de purge.

Le registre n'a pas d'expiration : la garantie ne disparait pas au bout de sept jours.
Il conserve toutefois une ligne par identifiant observe ; sa croissance n'est pas nulle.
Toute politique future d'expiration de ces clefs devra annoncer une fenetre de
deduplication convenue avec les producteurs. Le downgrade refuse la suppression
des empreintes qui protegent encore des lignes brutes deja purgees.

## Agregats avant purge

La premiere suppression d'une heure finalise ses **15 indicateurs de mesures et
predictions**, pour l'heure complete et tous leurs perimetres. Les agregats sont
conserves dans kpi_records. La marque technique `_retention_finalized` dans cette meme
table indique que l'heure est figee pour ces deux sources ; elle n'est jamais exposee
comme KPI du dashboard. Alertes et rapports de taches ne sont pas recalcules par ce job.

Les lots suivants de l'heure utilisent ce resultat complet, sans recalculer une moyenne
sur la fraction de brut restante. Lorsque la derniere mesure ancienne d'une machine
est remplacee par une nouvelle, elle peut etre supprimee sans detruire l'ancien agregrat.
Une observation inconnue arrivant dans une heure finalisee recoit EXPIRED_WINDOW ;
elle ne recree ni brut ni empreinte. Les identifiants deja connus restent rejouables
comme doublons. Une vieille heure non encore finalisee peut encore accepter du brut.
Un refresh KPI refuse les heures finalisees, meme si la retention est allongee plus
tard ou si l'horloge recule : l'absence de brut ne doit pas effacer le cache historique.

La finalisation, la marque, les empreintes et la suppression partagent **un commit**.
Une erreur ou annulation conserve le brut et le cache precedent. Un verrou transactionnel
exclusif bloque le chevauchement avec les ecritures applicatives ; les transactions
HTTP/MQTT prennent le verrou partage correspondant. La retention utilise try-lock :
si l'ingestion est active, elle indique busy et retente. Une retransmission concurrente
attend le commit de purge et verifie ensuite son empreinte. Les lectures restent possibles.
Les applications sont protegees par cette barriere ; les ecritures SQL directes d'un
administrateur ne constituent pas un chemin d'ingestion supporte.

Chaque cycle traite **une heure**, au maximum RETENTION_BATCH_SIZE par table (1000
par defaut), avec timeout total de 30 secondes et statement_timeout PostgreSQL.
Les agregrats couvrent toute l'heure meme lorsque seules mille lignes en sont supprimees.
Les DELETE permettent la reutilisation d'espace via PostgreSQL/autovacuum ; la taille
du fichier sur disque ne diminue pas necessairement immediatement.
La boucle et l'arret sont partages avec les autres workers ; une tentative utilise
une nouvelle session. Les metriques/logs distinguent simulation, candidats et suppression.
Sous ingestion continue, busy peut retarder la purge ; le debit de rattrapage et la
contention doivent etre mesures avant de dimensionner les lots/intervalles.

## Lancement, simulation et activation

Depuis PowerShell dans mp3-cloud, avec .env et catalogues initialises :

```powershell
docker compose up -d --build api ingest analytics supervision retention
docker compose ps
docker compose logs --tail 30 retention
docker compose exec retention python -m scripts.retain_raw
Invoke-RestMethod http://127.0.0.1:8004/metrics
```

Le CLI sans option simule un lot, meme si le worker est configure en suppression.
Il indique cutoff, hour, candidates, deleted et dry_run. Il ne donne pas le volume
total du backlog : candidates ne represente que le lot de l'heure actuellement traitee.

Pour supprimer ce lot apres finalisation et conservation de ses preuves :

```powershell
docker compose exec retention python -m scripts.retain_raw --apply
```

Pour la suppression periodique, definir `RETENTION_DRY_RUN=false` dans le .env puis :

```powershell
docker compose up -d --force-recreate retention
```

Toutes les images d'ingestion doivent etre mises a jour avant d'activer la suppression :
une ancienne application n'utilise pas le registre/barriere. Une migration seule ne
rend pas les anciens producteurs du service Cloud compatibles avec la purge.
Pour revenir a la simulation, remettre RETENTION_DRY_RUN=true et recreer retention.
Cela arrete les suppressions futures ; cela ne restaure pas du brut deja supprime.
Les backups/restaurations ne sont pas implementes par cette etape.

Le port 8004 expose fog_cloud_retention_ready, last_success_timestamp_seconds,
refresh_total, last_written_rows, last_candidates et dry_run, prefixes
fog_cloud_retention_. Docker exige ready=1 et une verification recente. Healthy en
simulation signifie calcul disponible ; il ne prouve aucune suppression.
Un worker en attente de schema ou en erreur retente seul, sans DSN dans les logs.

## Verification

Le 7 novembre 2026 : 385 tests reussis avec --mqtt (21 nouveaux controles), puis
27 controles de base apres le dernier garde-fou KPI. Ruff, 11 fixtures, OpenAPI 3.0.3
et Compose valides. Migration 0004 et metadata conformes ; worker Docker healthy,
dry_run=1, candidats=0, aucune observation synthetique ajoutee ni donnee de travail supprimee.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_retention.py tests/test_retention_database.py --postgres
.\.venv\Scripts\python.exe -m pytest --mqtt
```

Les scenarios verifient empreintes equivalentes, precision, simulation sans ecriture,
bornes horaires, dernier capteur conserve, agregrats avant suppression, lots multiples,
doublons/conflits apres purge, nouvelles dates expirees, anciens bruts sans registre,
transactions concurrentes, rollback et refus de downgrade perdant la deduplication.
Tous les bruts supprimes pour ces tests vivent dans des bases jetables, jamais fog_cloud.
