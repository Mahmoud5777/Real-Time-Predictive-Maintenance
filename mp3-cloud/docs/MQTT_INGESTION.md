# Etape 4 - reception MQTT et reprise

Le worker autonome `python -m app.ingest.worker` recoit les cinq types de messages et
appelle `persist_batch`, le meme service transactionnel que l'entree HTTP. Le payload
MQTT est un objet JSON brut ; le worker construit l'enveloppe interne kind/payload.
Les modeles, migrations, regles de deduplication et projections de l'etape 3 sont conserves.

## Topics et coherence

- fog/{zone}/sensor/{machine_id} : la zone et la machine du topic correspondent au payload.
- fog/{fog_id}/predictions, alerts, status : le fog_id correspond au producteur rapporte.
- tasks/events : les sources et destinations sont validees par le service commun.

M01 reste en zone A. Une prediction publiee par FOG_B peut concerner M01 : ce Fog est
l'executant. Aucune validation ne force toutes les analyses a rester sur le Fog du catalogue.

Les cinq abonnements sont confirmes en QoS 1 avant que le worker soit marque pret. Les
producteurs doivent aussi publier en QoS 1 pour obtenir une reprise ; QoS 0 reste accepte
en mode sans garantie de relivraison. retain=true est reserve aux heartbeats. Un ancien
heartbeat retenu peut etre rejoue ; les protections de l'etape 3 evitent un doublon ou une
regression de l'etat courant. Son age ne devient pas une preuve de fonctionnement actuel.

## Decisions d'acquittement

Une nouvelle session PostgreSQL est creee pour chaque livraison. Apres le retour du
service, la transaction est confirmee : le worker compte l'insertion, le doublon ou le
rejet metier puis emet l'ACK. Une confirmation perdue produit un rejeu avec le meme
message_id et donc un doublon sans nouvel effet.

Un JSON invalide, un topic incoherent, un payload trop volumineux ou un rejet metier
definitif est consigne par code dans les logs et les compteurs puis acquitte. Cela evite
de bloquer tous les messages suivants. Ces rejets n'ont pas encore de table de quarantaine
ni de conservation du payload complet.

Les erreurs temporaires de base sont retentees sans ACK, avec un delai croissant borne.
Les erreurs inattendues font echouer le processus ; Docker peut le redemarrer. Les ACK
portent la generation de connexion de leur livraison : un ancien numero de paquet n'est
jamais acquitte sur une connexion nouvelle ou deconnectee.

## File et boucle reseau

La reception Paho et le traitement PostgreSQL sont separes. Une file bornee conserve
les livraisons ; un unique tampon supplementaire couvre une livraison deja lue. Les
operations Paho sont serialisees. Quand la file est pleine, la boucle cesse de lire de
nouveaux paquets mais traite les sorties et keepalives. La memoire est bornee par la
capacite configuree, le tampon et le message actif, avec une limite de taille par payload.

Une interruption suffisamment longue peut entrainer une reconnexion. La session persistante
permet alors de recevoir les livraisons QoS 1 non acquittees. Pendant un arret propre,
le message actif peut terminer dans le delai configure ; les messages restants ne sont
pas acquittes. Aucun broker ni PostgreSQL de travail n'est arrete par les tests.

## Preparation et lancement sur Windows

Depuis le dossier mp3-cloud, avec l'environnement et le catalogue des etapes 1 et 2 :

```powershell
docker compose up -d db mosquitto
.\.venv\Scripts\python.exe -m app.ingest.worker
```

Le worker verifie la revision Alembic, les neuf tables et les catalogues de trois Fog et
douze machines avant de se connecter au broker. Il attend si ce socle n'est pas pret.
Il n'execute pas de migration et ne cree pas de faux heartbeats pour remplir le catalogue.

Pour un lancement dans Docker, une fois le schema et le catalogue prepares :

```powershell
docker compose up -d --build ingest mosquitto
docker compose ps
docker compose logs --tail 50 ingest
```

Dans Compose, les services api et ingest utilisent les adresses db et mosquitto.
Sur Windows, le fichier .env local conserve localhost. La configuration example contient
CORS_ORIGINS au format tableau JSON. Le contexte Docker exclut .env, .venv et les caches.

Le worker est distinct de l'API : ne pas lancer simultanement un worker Windows et Docker
avec le meme MQTT_CLIENT_ID. Deux clients portant le meme identifiant se deconnectent.

## Essai manuel avec une fixture

Cette commande ecrit volontairement une mesure de test dans la base utilisee par le worker.
Elle conserve l'identifiant de la fixture, donc trois publications donnent une insertion
et deux doublons si cette fixture n'avait pas deja ete envoyee.

```powershell
.\.venv\Scripts\python.exe -m scripts.publish_mqtt --topic fog/A/sensor/M01 --file ../contracts/fixtures/valid/sensor_ok.json --repeat 3
```

Le programme accepte une fixture kind/payload ou un objet brut, valide le message et
publie seulement l'objet brut. La confirmation affichee concerne le broker. Verifier
ensuite la base ou http://127.0.0.1:8001/metrics. Si l'API est active, la mesure est
consultable via http://127.0.0.1:8000/api/v1/machines/M01/latest.

## Observabilite et configuration

Le worker expose son propre endpoint /metrics, port 8001 par defaut. Il ne partage pas
le registre Prometheus de l'API. Le port est publie seulement sur 127.0.0.1 dans Compose.

- fog_cloud_mqtt_ready : base verifiee et abonnements confirmes.
- fog_cloud_mqtt_connected : dernier etat connu de la connexion.
- fog_cloud_mqtt_database_ready : derniere verification/ecriture reussie ; pas une sonde continue.
- fog_cloud_mqtt_received_total : receptions par QoS.
- fog_cloud_mqtt_accepted_total / duplicates_total : decisions confirmees par type.
- fog_cloud_mqtt_rejected_total : rejets par type et code.
- fog_cloud_mqtt_retries_total : erreurs temporaires de demarrage, reseau ou base.
- fog_cloud_mqtt_queue_depth / backpressure_total : attente et pauses de lecture.
- fog_cloud_mqtt_acknowledgements_total / stale_ack_skipped_total : ACK emis ou ignores.
- fog_cloud_mqtt_processing_seconds : reception jusqu'a decision definitive, retries compris.

Ces compteurs appartiennent au processus et repartent a zero apres son redemarrage.
Le healthcheck Compose verifie le dernier etat de readiness ; la supervision temporelle
des Fog et les KPI de disponibilite restent a construire.

Les valeurs example couvrent capacite 256, payload 65536 octets, retry initial 1 s / max
30 s, connexion 5 s, transaction 10 s, arret 15 s et keepalive 30 s. MQTT_METRICS_PORT=0
desactive le serveur pour les tests ou un lancement local particulier.

## Persistance Mosquitto et limites

Le volume mqttdata conserve les sessions et messages retenus. La sauvegarde periodique
est configuree a une seconde ; un redemarrage propre sauvegarde l'etat. Cela ne garantit
pas une absence de perte lors de toute panne brutale avant sauvegarde.

Un producteur qui ne peut pas joindre le broker doit lui-meme conserver ses messages.
La reprise ne couvre pas les messages publies avant la premiere creation de la session
et de ses abonnements. Ne pas effacer mqttdata pour redemarrer les services.

La configuration anonyme du broker reste celle de la demonstration locale. La gestion
de comptes/ACL et le deploiement externe ne sont pas couverts par ce jalon.

## Verification

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest --postgres
.\.venv\Scripts\python.exe -m pytest --mqtt
.\.venv\Scripts\python.exe scripts/check_contract.py
docker compose config --quiet
```

--mqtt implique les tests PostgreSQL. Les tests utilisent uniquement des bases mp3_test_UUID,
des conteneurs mp3_mqtt_test_UUID et leurs volumes de test. Ils verifient les cinq types,
HTTP/MQTT sans divergence, les rejets, les pannes de connexion, le commit sans ACK suivi
d'un rejeu, la persistance du broker, les heartbeats retenus, la file pleine, le demarrage
sans catalogue, l'endpoint de metriques et l'outil de publication.

Verification obtenue le 2 novembre 2026 : 149 tests reussis avec --mqtt, 50 tests locaux
reussis sans option (99 tests d'integration ignores), Ruff valide et 11 fixtures conformes.
L'image ingest est construite et exclut .env / .venv. Sur ce poste, le worker Docker est
healthy, connected=1, database_ready=1 et ready=1 sur http://127.0.0.1:8001/metrics.
Mosquitto sauvegarde son etat dans mqttdata. L'API Windows reste sur le port 8000 et
renvoie les douze machines. La base de travail conserve les trois Fog OFFLINE sans
heartbeat et les sept tables d'observations / taches / KPI vides. Aucun broker, volume
ou base de test nomme mp3_mqtt_test_UUID / mp3_test_UUID ne reste apres la verification.

La prochaine etape est 5 : completer les API de lecture utiles au dashboard. Le worker
MP3 n'effectue ni ordonnancement ni inference ML ; ces observations viennent de MP2.
