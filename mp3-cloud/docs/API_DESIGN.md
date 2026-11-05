# MP3 - Decisions de conception backend

## Pourquoi une double ingestion MQTT + HTTP

Le contrat d equipe fait circuler les donnees en MQTT. Si je n accepte que du HTTP, je
force MP2 a ecrire un client Cloud : ca casse son design et rend mon module dependant de son
planning. Si je n accepte que du MQTT, je ne peux ni seed ni tester seul.

**Decision** : `app/ingest/worker.py` (MQTT, chemin principal) et `POST /api/v1/ingest/batch`
(HTTP, secours + seed + tests) partagent le **mem**e pipeline `app/services/ingest.py`.
Un seul code de validation/dedup = pas de divergence possible entre les deux transports.

## Pourquoi la deduplication est une contrainte de base

MQTT QoS 1 garantit *au moins une fois* : les retransmissions sont possibles et doivent
etre gerees. Un controle applicatif (« ai-je deja vu cet id ? ») seul laisse une course
sous concurrence : deux insertions paralleles peuvent passer le test. La contrainte unique
par type et `INSERT ... ON CONFLICT (message_id) DO NOTHING` arbitrent atomiquement.
Le contenu est ensuite compare : identique = doublon, different = conflit rejete.

Le bilan HTTP compte les doublons depuis l'etape 3. Le worker MQTT expose depuis l'etape 4
ses compteurs d'ingestion sur le port 8001 ; les compteurs ne prouvent pas seuls toutes les
formes de coherence de donnees. Le pipeline est dans [HTTP_INGESTION.md](HTTP_INGESTION.md)
et la reprise MQTT dans [MQTT_INGESTION.md](MQTT_INGESTION.md).

## Pourquoi les KPI sont pre-calculés

Un endpoint qui agreege 1 M lignes par requete ne tient pas le critere « query performance »
et fait souffrir le dashboard. Les jobs periodiques ecrivent dans `kpi_records` ; l API lit une
petite table indexee. Contrepartie assumée : les KPI ont jusqu'a `KPI_REFRESH_SECONDS` de retard,
documente dans OpenAPI pour eviter que MP4 affiche « temps reel » la ou c'est quasi-temps reel.

## Pourquoi le brut est partitionne et purge

12 machines x 1 Hz = ~1,04 M lignes/jour. Apres 3 jours de demo, une requete d historique scanne
des millions de lignes. Partition par jour => purge = `DROP PARTITION` (instantane) et requetes
qui ne touchent que les partitions concernees (partition pruning).

## Convention temporelle

Base `timestamptz`, payloads ISO-8601 avec `Z`, refus explicite des timestamps naifs (`WrapValidator`).
Sans cette durete, trois conteneurs a trois fuseaux produisent des KPI silencieusement faux.

## Erreurs normalisees

Toutes les erreurs sortent en RFC 7807 (`type/title/status/detail/instance`). MP4 ecrit un seul
gestionnaire d erreur au lieu d un par endpoint.

## Ce que je refuse volontairement

- Le calcul temps reel critique : si mon API tombe, l usine doit continuer a alerter (responsabilite MP2).
- L entree directe du dashboard dans PostgreSQL : ca detruit la frontiere et rend tout test impossible.
