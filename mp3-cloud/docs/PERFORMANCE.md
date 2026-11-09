# Etapes 9 et 10 - verification A/B/C et mesures de performance

Cette etape prepare MP3 avant l'integration avec les programmes reels MP2 et MP4.
Elle mesure le backend avec des observations synthetiques. Elle ne demontre pas
l'execution de trois VM Fog ni le gain reel d'un ordonnanceur MP2.

## Verification de l'integration des trois zones

Depuis mp3-cloud, sous PowerShell, avec Docker et PostgreSQL disponibles :

```powershell
.\.venv\Scripts\python.exe -m pytest --mqtt tests/test_mqtt_integration.py -k three_fog
```

Le scenario traverse le broker Docker, le worker MQTT, un commit PostgreSQL puis
les lectures HTTP de FastAPI. Il verifie les douze machines en A/B/C, les alertes
de chaque Fog, une prediction hors zone et trois transferts A->B, B->C, C->A avec
origine preservee. Une declaration OFFLINE puis ONLINE de B produit les decisions
Cloud consultees via l'API. Le rejeu de tout le scenario reste sans doublons.
Ce test fonctionnel utilise le transport HTTP ASGI en processus ; les mesures
ci-dessous utilisent un vrai serveur HTTP TCP.

Les [topics MQTT](MQTT_INGESTION.md) couvrent deja les trois zones. Un exemple
`fog/A/sensor/M01` ne signifie pas que B et C sont exclus.

## Lancer les mesures longues

```powershell
.\.venv\Scripts\python.exe -m pytest --mqtt --performance tests/test_performance.py -s -x --tb=short
```

Ces mesures sont ignorees dans la suite ordinaire, meme avec --mqtt. Le parametre
--performance les active explicitement. Les assertions portent sur les ecritures,
les doublons, les lectures non vides, les KPI et la purge, pas sur des seuils de temps
dependants du poste. Le compte PostgreSQL configure doit pouvoir creer des bases.

Isolation : une base mp3_test_<UUID> par scenario, broker et volume de test pour MQTT,
API liee a 127.0.0.1 sur un port libre. Le serveur HTTP refuse une base hors de ce
namespace. Les fixtures existantes suppriment leurs bases, broker et volume en fin
d'essai, y compris en cas d'echec de test. Aucun scenario n'insere dans fog_cloud et
aucune suppression n'est activee dans le worker de retention de travail.

## Charge et methode

- HTTP : deux bases neuves, chacune avec 12 mesures de warmup et 2400 nouvelles
  mesures sur les douze machines. Un seul client ecrit par lots de 1, puis de 100.
  Le rejeu de 12 messages confirme la deduplication. Le debit compte les nouvelles
  mesures par seconde, pas les requetes HTTP par seconde.
- Lecture : huit collections, 100 appels chacune, six requetes concurrentes.
  Le premier essai mesure les lectures seules ; le second ajoute HTTP, trois
  producteurs MQTT QoS 1 et des appels aux services KPI/supervision/retention.
- Contention : 1320 messages HTTP, 267 messages MQTT, services de workers appeles
  successivement par cycle avec une pause de 0,2 s. Les tentatives de verrou
  indisponible sont comptees. Cette cadence de stress differe du Compose normal.
  Les distributions des jobs incluent leurs tentatives ignorees lorsque le verrou
  est indisponible ; consulter job_lock_skips avant d'interpreter leur temps.
- Jeu mixte : 5280 mesures, 528 predictions, trois alertes et neuf evenements de
  taches avant purge. Les heures recentes permettent de verifier le cache ; une
  heure expiree contient 240 mesures et 24 predictions supprimables.
- Retention : preview puis application dans la seule base jetable, verification
  des 264 suppressions, du KPI finalise et du rejeu toujours duplicate apres purge.
- Profil SQL : EXPLAIN ANALYZE/BUFFERS de la derniere page de mesures de M01, apres
  ANALYZE sensor_data dans la base de test.

HTTP passe par TCP loopback avec Uvicorn et HTTPX dans le meme processus Python.
PostgreSQL et Mosquitto utilisent Docker Desktop. Les services Compose de travail
restent actifs sur le meme poste. Le temps perf_counter couvre l'appel client
jusqu'a la lecture du JSON ; l'attente du semaphore du generateur de lectures est
exclue de la latence individuelle, mais incluse dans le debit global.

Les quantiles sont en millisecondes : mediane p50, p95 par rang seulement a partir
de 100 observations, p99 a partir de 1000. Les autres valeurs sont nulles et ne
doivent pas etre interpretees comme zero. Les 24 requetes du lot HTTP de 100 ne
suffisent donc pas pour publier son p95. Les latences par route restent distinctes
du p95 combine de toutes les routes.

Le debit MQTT inclut le rythme des publications et ACK QoS 1. L'ACK du broker
n'atteste pas a lui seul un commit Cloud : l'essai attend aussi les ACK du worker
et verifie les lignes. La moyenne de traitement du worker mesure reception jusqu'a
decision, y compris l'attente dans sa file, sans mesurer le trajet producteur->broker.

## Rapports et interpretation

Un JSON horodate est ecrit dans data/benchmarks/ ; ce dossier est ignore par Git.
Il contient environnement, effectifs, debit, latences, cycles et verrous ignores,
purge, coherence et plan SQL. selected_tests identifie les scenarios selectionnes ;
all_scenarios_recorded=false signale un resultat manquant parmi ces scenarios.
Le commit HEAD ne suffit pas a identifier des modifications locales non commitees.

Les objectifs existants sont des cibles, pas des resultats garantis : p95 d'historique
<150 ms, reception MQTT->base <250 ms, alerte->lecture <500 ms, refresh horaire <5 s.
Le protocole mesure directement les lectures. La moyenne MQTT et les quelques
refreshs ne prouvent ni un p95 MQTT ni une latence d'alerte. Ces deux parcours et le
dimensionnement sur plusieurs jours restent a mesurer avec davantage d'echantillons.

Une premiere baseline locale sert a choisir la prochaine experience. Aucune
modification d'index, de partitionnement ou de garantie de deduplication n'est
justifiee par le seul fait qu'un benchmark existe. Comparer les memes charges sur
des repetitions et sur un historique beaucoup plus grand avant de conclure.

## Correction de contention des lignes Fog

La premiere charge a montre jusqu'a 6,9 s pour un scan de supervision. Un test
PostgreSQL a reproduit l'attente en maintenant une prediction non commitee : sa
cle etrangere prend FOR KEY SHARE sur le Fog, incompatible avec FOR UPDATE.
Le scan echoue alors au timeout ; ce resultat confirme le mecanisme de blocage.

L'ingestion des heartbeats et la supervision prennent maintenant FOR NO KEY UPDATE.
Ces deux operations restent mutuellement exclusives et conservent etat/historique
dans une transaction, mais elles ne bloquent plus les simples references au Fog.
Elles ne changent pas fog_id ou zone. Aucun index, schema ou contrat producteur
n'est modifie. Les tests maintiennent une vraie prediction non commitee pendant
un scan et pendant un nouveau heartbeat, et conservent le test de serialisation
entre deux mises a jour Fog.

Pour repeter uniquement la comparaison de charge apres cette correction :

```powershell
.\.venv\Scripts\python.exe -m pytest --mqtt --performance tests/test_performance.py -k workers -s -x --tb=short
```

## Mesures locales du 7 novembre 2026

Environnement : Windows 11, Python local 3.13.2, PostgreSQL 16.15 dans Docker Desktop,
20 processeurs logiques. La baseline complete a termine trois scenarios en 169,5 s.
La repetition du seul scenario mixte apres correction a termine en 95,2 s. Chaque
scenario a sa propre base jetable et conserve les memes quantites de donnees.

HTTP unitaire : 2400 insertions en 54,25 s, soit 44,2 messages/s, p95 de requete
31,8 ms sur 2400 requetes. HTTP par lots de 100 : 2400 insertions en 21,99 s,
soit 109,2 messages/s ; 24 requetes, mediane 922,3 ms par lot, p95 non publie.
Sur cet essai, le lot augmente le debit d'environ 2,47 fois ; il n'accelere pas
la reponse de chaque requete. Les deux essais utilisent le meme volume et le meme
warmup dans des bases neuves.

Avant correction du verrou Fog, p95 combine des 800 lectures : 129,0 ms seules,
228,2 ms avec ingestion et jobs. Apres correction : 156,0 ms seules, 233,7 ms sous
charge. Pour M01, p95 de l'historique : 130,1 puis 167,3 ms seules et 207,1 puis
223,2 ms sous charge. Ces deux essais ne montrent pas d'amelioration generale des
lectures et ne valident pas la cible de 150 ms sous charge. La variabilite du poste
et la topologie partageant un processus Python restent a separer du cout SQL.

La supervision profite de la correction ciblee : sur le premier essai, 27 scans,
mediane 117,1 ms et maximum 6881,7 ms ; sur le second, 56 scans, mediane 26,3 ms et
maximum 251,0 ms. Pas de p95 sur ces effectifs. Le test de concurrence reproduit
le blocage ancien et valide son elimination ; les mesures restent deux essais
locaux avec une cadence de scans acceleree.

MQTT sous charge : 267 messages produits par trois clients, tous confirmes et
verifies, 22,26 puis 22,77 s jusqu'au dernier ACK Cloud, environ 12 messages/s.
La moyenne reception->decision vaut 1,36 puis 1,47 s, avec une rafale et une file
d'attente. Ce resultat ne valide pas une latence <250 ms pour chaque message et
ne constitue pas une mesure du debit soutenu en production.

Retention sous charge : 27/27 puis 54/56 tentatives de preview ignorees car une
ingestion possede le verrou partage. Les deux previews effectifs du second essai
restent sans suppression. Hors charge, suppression des 240 mesures et 24 predictions
en 228,0 puis 212,9 ms ; les KPI finalises et les 264 doublons rejoues sont verifies.
Une ingestion continue peut retarder la maintenance : il faudra mesurer cette
progression avec une charge cadensee et des pauses representant les vrais flux.

EXPLAIN de la page M01 sur la premiere base : execution SQL 0,225 ms, 118 blocs
en cache, aucun bloc lu du disque. Ce petit jeu de donnees ne justifie pas un
nouvel index ni du partitionnement. Les prochaines mesures devront separer
latence TCP/driver, temps SQL, attente de verrous et saturation du generateur.

Rapports locaux : data/benchmarks/20261107T175612532045Z.json pour la baseline et
data/benchmarks/20261107T180307461435Z.json apres correction. Ces sorties ignorees
par Git sont regenerables par les commandes ci-dessus.

## Etape 10 - charge cadensee et processus separes

Le [laboratoire pas a pas](LAB_ETAPE10.md) permet de reproduire les essais soi-meme.
Il utilise fog_lab et deux volumes dedies dans un projet Compose mp3lab_<identifiant>.
L'API, l'ingestion, les KPI, la supervision et la retention sont cinq processus
Docker distincts du generateur HTTP/MQTT Windows. Le Compose de travail reste actif.
La base du laboratoire commence avec les catalogues, puis chaque run ajoute 60
observations historiques : 36 expirees et 24 recentes. Aucun envoi ne cible fog_cloud.

```powershell
.\.venv\Scripts\python.exe -m scripts.lab start
.\.venv\Scripts\python.exe -m scripts.lab run --seconds 120 --hz 5
.\.venv\Scripts\python.exe -m scripts.lab status
```

Douze machines envoient des mesures a cadence fixe, predictions toutes les 10 s
et heartbeats toutes les 5 s ; trois alertes et neuf evenements de taches completent
le scenario. Six GET sont rafraichis une fois par seconde. Le generateur ne rattrape
pas une echeance manquee par une rafale : workload_valid et skipped_ticks permettent
de distinguer coherence des messages emis et cadence effectivement tenue. Un seul
run a la fois. Les compteurs SQL par identifiant de run confirment la persistence.

Les workers conservent leurs cadences normales : KPI/retention 60 s, supervision 5 s.
La suppression est active uniquement dans fog_lab pour verifier la maintenance.
Le rapport capture les tentatives success/busy/error et verifie deux rejeux HTTP
d'une mesure deja recue sans insertion supplementaire. Les distributions HTTP
mesurent le client jusqu'au JSON decode. Le p95 MQTT est l'intervalle d'un histogramme
Prometheus du worker, reception monotone jusqu'au retour du commit, file incluse.
Il exclut le delai avant le callback ; une file interne vide ne prouve donc pas
l'absence de retard au niveau du broker ou du socket.

### Limitation reseau trouvee et correction

Le premier essai a 1 Hz par machine a confirme 1668 messages en 120 s : p95 HTTP
combine 65,4 ms, historique M01 57,1 ms, MQTT moyen 7,4 ms, p95 MQTT dans (10,25] ms.
Le premier essai a 5 Hz publie 7428 messages, mais le worker n'en confirme que 5539
vers 121,5 s, puis 6465 vers 141,8 s. Il depasse les 30 s de vidage autorisees.
Son rapport reste incomplete ; il ne fournit pas de bilan final de latence valide.

La boucle reseau faisait une pause de 20 ms apres chaque poll Paho, y compris
apres un message, ce qui limitait la reception a environ 46 messages/s sur cet essai.
Retirer cette pause seule a revele une autre attente : le poll bloquant conservait
le verrou dont l'ACK a besoin. Cet essai intermediaire a ete interrompu et son
laboratoire supprime ; il ne constitue pas un resultat de performance valide.

La lecture est maintenant non bloquante sous ce verrou (timeout=0), puis la boucle
fait une pause uniquement a vide ou lorsque la file est pleine. Cela libere le
verrou pour l'ACK sans imposer un delai par message actif. La file reste bornee,
et l'ACK reste posterieur a une decision de persistence definitive. Les tests de
regression couvrent reception active, idle et saturation ; la suite MQTT controle
toujours reconnect/retry, rejeux et acquittements.

### Essai corrige du 8 novembre 2026

Environnement : Windows 11, Python du generateur 3.13.2, Python Docker 3.12,
PostgreSQL 16.15 et Mosquitto Docker Desktop, meme poste physique. Laboratoire neuf,
120 s a 5 Hz/machine, six lectures/s. Pas de build ou suite de tests pendant la mesure.
Le rapport conserve l'empreinte SHA-256 des sources de l'essai.

- Cadence valide : 7200 mesures, 144 predictions, 72 heartbeats, trois alertes,
  neuf evenements ; 7428 messages confirmes et comptes en SQL, sans rejet MQTT,
  erreur HTTP ni echeance manquee. Duree avec vidage : 120,13 s.
- HTTP : 720 lectures, p95 combine 69,7 ms ; 120 appels par route. P95 M01 56,9 ms,
  machines 51,2 ms, predictions B 72,7 ms, alertes 77,1 ms, Fog 57,7 ms,
  evenements 66,0 ms. Pas de p99 HTTP : effectifs insuffisants.
- MQTT reception->commit : moyenne 42,7 ms sur 7428 messages, p95 dans (75,100] ms.
  La file observee toutes les 5 s atteint 16 ; des pics courts peuvent echapper au scan.
- Timestamp producteur->reception Cloud : p95 95,1 ms, p99 167,2 ms sur 7200 mesures,
  aucune difference negative. Deux horloges UTC ; ce parcours finit avant le commit.
  Ce n'est pas une latence complete MQTT ni une latence ML et ces p95 ne s'additionnent pas.
- Maintenance : deux cycles KPI et 24 scans de supervision reussis ; retention
  un succes et quatre tentatives busy, aucune erreur. Les 36 observations expirees
  ont toutes disparu, les agregats finalises restent presents, deux rejeux sont duplicate.
- Profil SQL hors charge : page M01 0,151 ms et count 0,099 ms, blocs en cache,
  sans lecture disque. Ces temps ne sont pas des latences HTTP.

Le meme flux 5 Hz, auparavant incomplet, est maintenant termine dans la duree
prevue sur un laboratoire neuf. Les deux essais 5 Hz permettent de conclure sur
ce blocage de reception ; aucune amelioration chiffree de p95 avant/apres n'est
annoncee pour le run incomplet. L'essai 1 Hz differe de charge et de version du worker.
L'etape 9 differe aussi de topologie, volume et rythme ; ses p95 ne sont pas une
baseline directement comparable a ceux de cette etape.

Les six routes testees et le p95 MQTT satisfont les cibles de ce run local. Cela
ne dimensionne pas plusieurs jours de donnees, des VM Fog reelles ou un poste
distant. Le parcours alerte->affichage MP4, les temps ML, le partitionnement et
les limites de capacite soutenue restent a verifier dans leurs conditions reelles.

La commande du tutoriel a aussi ete verifiee apres les derniers garde-fous du CLI,
sur une nouvelle base : 60 s a 1 Hz, 840/840 messages confirmes et comptes en SQL,
cadence valide, 360 lectures HTTP avec p95 combine 70,5 ms. Le worker MQTT mesure
45,8 ms en moyenne et un p95 dans (100,250] ms sur 840 observations ; un cycle KPI,
12 scans et un nettoyage reussissent sans busy/error, 0/36 anciennes observations
restent. Les p95 par route sont nulls (60 appels) ; ce controle du parcours debutant
n'est pas une repetition du protocole 120 s a 5 Hz.

Rapports locaux conserves dans data/lab/, ignores par Git :
20261108T154001904153Z-1hz.json (initial), 20261108T154246482274Z-5hz.json (incomplet),
20261108T154906418975Z-5hz.json (intermediaire interrompu),
20261108T155340662443Z-5hz.json (corrige),
20261108T160029115975Z-1hz.json (commande du tutoriel). stop supprime les volumes du laboratoire
et conserve ces rapports.

## Suite avant l'echange avec MP2 et MP4

Un usage manuel a revele le chevauchement de deux generateurs : le run 240 s/1 Hz
a tourne de 17:26:25 a 17:28:32 (interrompu), et le run 60 s/5 Hz a commence a
17:28:20. Les confirmations du worker sont communes ; leurs deltas melanges ne
peuvent pas mesurer un run. Ces deux rapports incomplets ne constituent pas des
benchmarks valides, meme si les messages emis ont tous ete retrouves en SQL.
Le CLI utilise desormais un verrou OS interprocessus, attend le vidage avant la
baseline et refuse surplus/reset des confirmations ou histogramme contamine.
Un run interrompu conserve sa raison d'arret ; status/logs/sql restent disponibles.
Deux courts essais consecutifs de controle confirment 288 puis 630 messages. Ils
verifient cette correction du laboratoire et ne remplacent pas les mesures 120 s.

1. Reproduire le laboratoire soi-meme et comprendre compteurs, pagination et supervision.
2. Preparer CI et instructions de lancement depuis un clone frais pour l'equipe.
3. Valider les vrais messages MP2 et les ecrans MP4 avec les contrats existants.
4. Mesurer sur un historique beaucoup plus grand avant de dimensionner ou partitionner.

Les champs de chronologie manquants des taches restent a convenir avec MP2 ; les
actions d'alertes et SSE restent des fonctionnalites ulterieures, distinctes de ces mesures.
