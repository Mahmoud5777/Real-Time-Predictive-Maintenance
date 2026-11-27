# Etape 10 - tester MP3 soi-meme

Ce laboratoire reproduit les flux de trois Fog pour apprendre a mesurer MP3.
L'API, l'ingestion MQTT, les KPI, la supervision et la retention tournent dans cinq
processus Docker distincts. Le generateur et le lecteur HTTP tournent dans ton
terminal Windows. PostgreSQL et Mosquitto sont dedies au laboratoire.

Les valeurs sont synthetiques : ce programme ne fait pas de ML, ne decide pas d'un
ordonnancement et ne represente pas trois VM MP2. Les observations montrent ce que
MP3 recoit, stocke et expose.

## 1. Ouvrir le terminal au bon endroit

Dans PowerShell :

```powershell
Set-Location 'C:\Users\User\Desktop\FOG\mp3-cloud'
docker desktop status
```

Si Docker est arrete, lancer `docker desktop start`. Utiliser le Python du projet
pour toutes les commandes ci-dessous. Les dependances de requirements-dev.txt
doivent etre installees dans .venv, notamment HTTPX pour le generateur.

## 2. Creer le laboratoire

```powershell
.\.venv\Scripts\python.exe -m scripts.lab start
```

La commande construit une image du code local, applique les migrations, initialise
trois Fog et douze machines, puis attend que les services soient prets. Le nom
Compose ressemble a mp3lab_<identifiant>. Un second start conserve le laboratoire
existant ; pour repartir d'une base vide, executer stop puis start.

- Swagger : http://127.0.0.1:8100/docs
- MQTT : 127.0.0.1:1884
- Metriques ingest/KPI/supervision/retention : ports 8101/8102/8103/8104, route /metrics.
- Base : fog_lab, dans un conteneur sans port PostgreSQL publie.

Les ports de ton backend de travail restent 8000/1883. Le laboratoire utilise son
propre mot de passe de demonstration et ses propres volumes ; il ne lit pas ton .env.
Si 8100 ou 1884 est occupe, avant le premier start utiliser par exemple :

```powershell
.\.venv\Scripts\python.exe -m scripts.lab start --api-port 8200 --mqtt-port 1885
```

Les quatre ports de metriques suivent le port API. status affiche l'adresse effective.

## 3. Premier test : une mesure par seconde pour chaque machine

```powershell
.\.venv\Scripts\python.exe -m scripts.lab run --seconds 60 --hz 1
```

1 Hz signifie un envoi par seconde pour chaque machine. Les douze machines
produisent donc 12 mesures/s, soit 720 mesures en 60 secondes si la cadence est tenue.
Le programme envoie aussi :

- Une prediction synthetique toutes les 10 secondes pour chaque machine : 72 predictions.
- Un heartbeat toutes les 5 secondes pour chaque Fog : 36 heartbeats.
- Une alerte par Fog : 3 alertes.
- Trois evenements par tache, creation/migration/completion : 9 evenements.

Le total attendu est donc 840 messages MQTT. Chaque envoi distinct a un message_id
unique. Les six lectures du dashboard sont rafraichies une fois par seconde.
Lancer un seul run a la fois : les compteurs du worker sont communs au laboratoire.
Le CLI refuse maintenant un second run pendant un essai et affiche le PID du
processus qui occupe le laboratoire. start et stop sont egalement bloques pendant
le run ; status, logs et sql restent disponibles dans un autre terminal. Le verrou
control.lock est libere par Windows apres Ctrl+C ou un crash ; ne pas supprimer
ce fichier pour contourner un essai actif.

Pendant le test, une ligne apparait toutes les cinq secondes :

```text
temps | publies=... confirmes=... | file MQTT=...
```

publies compte les demandes d'envoi du generateur. confirmes vient du worker Cloud
apres confirmation de persistence. Une difference temporaire peut etre normale :
le Cloud finit de traiter les messages. Le programme attend jusqu'a 30 secondes
apres la duree demandee pour vider les messages en attente, puis verifie les
comptages SQL pour ce run precis. L'ACK du broker ne suffit pas a cette verification.

Si le generateur manque une echeance, il ne rattrape pas par une rafale. skipped_ticks
et workload_valid indiquent alors que la cadence demandee n'a pas ete atteinte.
PASS coherence signifie que les messages effectivement emis sont coherents ; il
ne signifie pas automatiquement que tous les objectifs de performance sont atteints.
Avant les envois, le programme attend deux secondes sans activite MQTT pour laisser
finir les messages d'un ancien essai interrompu (attente maximale 30 s). Si confirmes
depasse publies ou que le compteur redemarre, il arrete le run avec un rapport
incomplete au lieu de continuer avec des metriques contaminees. Cette detection
complete le verrou ; ne pas publier manuellement pendant une mesure de performance.

## 4. Observer ce qui se passe

Dans un deuxieme terminal PowerShell, depuis mp3-cloud :

```powershell
Set-Location 'C:\Users\User\Desktop\FOG\mp3-cloud'
.\.venv\Scripts\python.exe -m scripts.lab status
.\.venv\Scripts\python.exe -m scripts.lab logs ingest --tail 20
```

Ouvrir Swagger du laboratoire. Choisir une route, cliquer Try it out puis Execute :

- GET /api/v1/measurements, machine_id=M01 : les mesures de la machine A.
- La meme route avec machine_id=M05, puis M09 : zones B et C.
- GET /api/v1/fog/nodes : statuts rapportes, ages et supervision Cloud.
- GET /api/v1/tasks/events : sources et destinations des migrations A->B->C->A.
- GET /api/v1/alerts : les trois alertes de demonstration.

Un graphique n'est pas necessaire pour commencer : items est la liste de resultats
et meta.total compte tous les resultats du filtre. Les listes sont paginees.
Chaque nouveau run ajoute des donnees ; status montre le total du laboratoire,
tandis que le rapport compare seulement les identifiants de son propre run.

Pour consulter directement les tables du laboratoire :

```powershell
.\.venv\Scripts\python.exe -m scripts.lab sql
```

Dans psql :

```sql
\dt
SELECT machine_id, count(*) FROM sensor_data GROUP BY machine_id ORDER BY machine_id;
SELECT machine_id, count(*) FROM sensor_data
WHERE message_id LIKE 'lab%-live-%' GROUP BY machine_id ORDER BY machine_id;
SELECT source_fog, destination_fog, status FROM task_events WHERE status='MIGRATED';
\q
```

Le prompt est fog_lab, pas fog_cloud.
La premiere requete compte aussi les observations historiques de preparation.
La seconde ne compte que les mesures du generateur : apres un seul run de 60 s
a 1 Hz, elle doit donner 60 pour chacune des douze machines. Apres plusieurs runs,
elle cumule leurs mesures ; le rapport JSON garde les comptes du run individuel.

Pour distinguer les essais deja presents dans la base :

```sql
SELECT split_part(message_id, '-', 1) AS run_id, machine_id, count(*)
FROM sensor_data WHERE message_id LIKE 'lab%-live-%'
GROUP BY 1, 2 ORDER BY 1, 2;
```

Un essai de 240 secondes a 1 Hz doit produire 240 mesures par machine s'il termine.
Ctrl+C avant la fin conserve uniquement les messages deja emis, puis libere le
terminal. Attendre le bilan PASS avant de lancer le run suivant. La commande status
observe les tables pendant le test : un SELECT lance plus tard peut donc compter
davantage de mesures.

## 5. Comprendre le rapport

Le chemin JSON est affiche en fin de test. Pour lire le dernier rapport dans PowerShell :

```powershell
$labReportFile = Get-ChildItem .\data\lab\*.json |
    Where-Object { $_.Name -ne 'state.json' } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
$labReport = Get-Content -LiteralPath $labReportFile.FullName -Raw | ConvertFrom-Json
$labReport | Select-Object status, workload_valid, achieved_sensor_hz, confirmed
$labReport.all_read_routes
$labReport.mqtt_p95_bucket
$labReport.database.producer_to_cloud_receipt
$labReport.worker_cycles
```

Le debit est le nombre de mesures par seconde. La latence est le temps necessaire
pour obtenir une reponse. p95 signifie que 95 % des temps observes sont inferieurs
ou egaux a cette valeur ; il ne signifie pas une moyenne.

HTTP : temps du client jusqu'a la lecture du JSON, avec p50/p95/p99 et effectifs.
Le p95 par route n'est publie qu'a partir de 100 lectures de cette route. Un run de
60 secondes a 60 lectures par route ; son p95 combine utilise 360 lectures. Pour
mesurer le p95 de chaque route, utiliser --seconds 120. p99 exige au moins 1000
observations. Une valeur null signifie effectif insuffisant, pas zero milliseconde.

MQTT : le worker mesure avec son horloge monotone la reception jusqu'au retour
de la persistence confirmee, y compris sa file d'attente. Le p95 est un intervalle
de buckets Prometheus, par exemple lower_ms=25 et upper_ms=50 ; on ne pretend
pas connaitre une valeur exacte entre ces bornes. Ce temps exclut le trajet
producteur->broker. Il ne s'agit pas d'une latence complete de detection ML.

producer_to_cloud_receipt compare le timestamp de la mesure a sa date de reception
Cloud. Cette observation inclut le trajet avant le callback MQTT, mais utilise deux
horloges UTC et reste anterieure a l'insertion/commit. Un decalage d'horloge peut la
fausser ; negative_delay_count compte les differences negatives exclues des quantiles.
Ne pas additionner son p95 au p95 du worker : les quantiles ne s'additionnent pas.

Les objectifs existants sont p95 de lecture <150 ms et reception MQTT->commit
<250 ms. Pour le second, une borne superieure de p95 <=250 ms permet seulement
de conclure sur le 95e percentile du run, pas sur chacun des messages.

queue_max_sampled est un maximum observe toutes les cinq secondes ; une courte
rafale entre deux observations peut lui echapper. generator_lag mesure le retard
du generateur par rapport a son calendrier d'envoi.

## 6. Verifier la maintenance pendant l'ingestion

Avant chaque run, le programme ajoute 60 observations historiques dans fog_lab :
36 expirees et 24 recentes. Les recentes donnent un historique de demonstration
aux KPI de la derniere heure terminee. Les donnees MQTT du run actuel entrent
dans leurs propres KPI une fois leur heure terminee.

La retention est active en suppression dans ce laboratoire uniquement. Elle
conserve ses intervals normaux de 60 secondes, tout comme analytics ; supervision
verifie toutes les 5 secondes. Le rapport montre success/busy/error par worker et
old_remaining pour les 36 observations expirees de ce run. Un run de 10 secondes
peut finir avant le prochain nettoyage ; utiliser 120 secondes pour observer la
progression sur plusieurs cycles. Un busy signifie verrou indisponible, pas perte
de donnees. Le nettoyage peut etre retarde si l'ingestion occupe continuellement
le verrou partage.

Le programme rejoue aussi deux fois une mesure deja acceptee via HTTP : il doit
obtenir deux doublons sans insertion supplementaire.

## 7. Augmenter progressivement la charge

Avant de lancer le second test, calculer le nombre attendu de mesures :
12 machines x 5 mesures/s x 60 secondes = 3600 mesures.

```powershell
.\.venv\Scripts\python.exe -m scripts.lab run --seconds 60 --hz 5
```

Comparer la cadence atteinte, les erreurs, la file et la latence avec le premier
rapport. Predictions et heartbeats gardent leurs cadences de 10 et 5 secondes.
Pour augmenter les lectures plutot que les mesures :

```powershell
.\.venv\Scripts\python.exe -m scripts.lab run --seconds 60 --hz 1 --read-hz 2
```

Modifier un seul facteur a la fois. Ces essais successifs augmentent aussi le volume
historique de la base ; pour une comparaison stricte de deux changements de code,
repartir de deux laboratoires neufs avec le meme prechargement et les memes parametres.

## 8. Arreter et nettoyer

Le generateur s'arrete en fin de run, mais le laboratoire reste disponible pour
inspecter les donnees. Au bout d'environ 15 secondes sans heartbeat, un scan peut
declarer les Fog UNREACHABLE ; leur dernier statut rapporte peut rester ONLINE.
Lire effective_supervision_status pour la conclusion Cloud actuelle.

```powershell
.\.venv\Scripts\python.exe -m scripts.lab stop
```

stop supprime uniquement les conteneurs et les deux volumes du projet mp3lab.
Les observations du laboratoire sont effacees ; les rapports JSON restent dans
data/lab/, ignore par Git. Ton projet Compose mp3-cloud et fog_cloud restent separes.
Ctrl+C interrompt le generateur, conserve un rapport incomplet et laisse le
laboratoire disponible ; consulter status puis utiliser stop si necessaire.
Un echec conserve aussi un rapport incomplete, avec failure lorsque l'erreur est
capturee. Ce resultat ne valide pas la charge ; examiner les logs avant de recommencer.
