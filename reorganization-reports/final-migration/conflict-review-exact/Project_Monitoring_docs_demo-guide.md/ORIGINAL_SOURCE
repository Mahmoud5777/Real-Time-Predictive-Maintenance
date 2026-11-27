# Guide de démonstration — MP4 Dashboard and Monitoring

Ce guide décrit une démonstration avec les données réellement disponibles dans
l'API MP3 et les métriques collectées. Le Dashboard n'invente pas de données de
démonstration. Une réponse vide doit être présentée comme telle.

## 1. Préparation

### Services nécessaires

Avant la présentation, vérifier que les équipes responsables ont démarré :

- **MP3** : l'API Cloud, PostgreSQL, Mosquitto et les workers Ingest, Analytics,
  Supervision et Retention.
- **MP2** : le Scheduler et les Fog A, B et C, connectés au réseau partagé
  `mp3-cloud_default`.
- **MP4** : `mp4-dashboard-api`, Prometheus, Grafana, Blackbox Exporter et
  cAdvisor.

MP3 doit fournir le réseau `mp3-cloud_default` et l'API `api:8000` avant le
démarrage de MP4. Les services MP2/MP3 restent gérés par leurs équipes. Depuis
PowerShell, dans `Project_Monitoring`, les commandes de démarrage MP4 documentées
sont :

```powershell
$env:GF_SECURITY_ADMIN_PASSWORD = '<mot de passe local non versionné>'
docker compose -f docker-compose.yml up -d --build
docker compose -f docker/docker-compose.monitoring.yml up -d
```

Remplacer le texte entre chevrons par un mot de passe local. Ne pas l'ajouter au
dépôt. Si les services sont déjà actifs, ne pas les redémarrer pour la
présentation.

### URLs locales

| Service | URL |
|---|---|
| Dashboard MP4 | `http://localhost:3001` |
| Santé Dashboard | `http://localhost:3001/healthz` |
| Grafana | `http://localhost:3002` |
| Santé Grafana | `http://localhost:3002/api/health` |
| Prometheus | `http://localhost:9090` |
| Targets Prometheus | `http://localhost:9090/targets` |
| Santé Prometheus | `http://localhost:9090/-/healthy` |

Le compte Grafana est `admin` par défaut. Son mot de passe est celui fourni dans
`GF_SECURITY_ADMIN_PASSWORD`.

## 2. Démonstration du Dashboard React

Le menu latéral présente les pages suivantes :

1. **Vue d'ensemble** : situer les machines, les alertes et l'état général à
   partir des données reçues.
2. **Machines** : choisir une machine, consulter ses mesures et leur historique.
   Le statut affiché est déduit des mesures et des prédictions.
3. **Maintenance Prédictive** : présenter les prédictions disponibles, leur
   niveau de risque et les filtres proposés.
4. **Alertes** : parcourir les alertes et leurs états. Une liste vide signifie
   qu'aucune alerte ne correspond aux données et filtres reçus.
5. **Surveillance Fog** : montrer l'état rapporté des nœuds, leurs ressources et
   leurs informations de supervision lorsqu'elles sont disponibles.
6. **Événements et migrations** : utiliser les onglets **Tous les événements de
   tâches**, **Événements MIGRATED** et **Supervision**. Les listes sont paginées.

Les appels du Dashboard passent par le proxy Nginx vers l'API Cloud MP3. Les
pages de tâches et de supervision reflètent les réponses de l'API; elles ne
garantissent pas qu'un événement existe pour la période choisie.

## 3. Démonstration Grafana

Présenter les cinq dashboards dans cet ordre :

1. **MP4 - Vue globale** (`infrastructure`) : état des targets, sondes HTTP,
   connectivité TCP du broker et activité Ingest exposée par MP3.
2. **MP4 - Disponibilité et latence API** (`api-availability`) : succès et
   durée des sondes HTTP, puis sonde TCP Mosquitto.
3. **MP4 - Services et conteneurs** (`services`) : disponibilité des endpoints,
   états de préparation exposés par les workers MP3 et âge des échantillons
   cAdvisor.
4. **MP4 - CPU et mémoire** (`resources`) : ressources des conteneurs visibles
   par cAdvisor et CPU/RAM des nœuds Fog.
5. **MP4 - Nœuds Fog et tâches** (`fog-nodes`) : file d'attente, tâches
   terminées/échouées, migrations et latence de traitement p95.

Les panneaux sont alimentés par Prometheus. Une série absente peut laisser un
panneau vide : ne pas remplacer ce résultat par une valeur supposée.

## 4. Prometheus

Ouvrir **Status → Targets** ou `http://localhost:9090/targets` et montrer les
targets `UP`. Les jobs couvrent notamment :

- l'API et les workers MP3 ;
- le Scheduler et les trois Fog MP2 ;
- les sondes HTTP, y compris le Dashboard MP4 ;
- la sonde TCP Mosquitto, Prometheus, Blackbox Exporter et cAdvisor.

`UP` signifie que Prometheus a pu joindre et scruter l'endpoint configuré. Cela
ne prouve pas à lui seul que le traitement métier ou MQTT fonctionne de bout en
bout. Lors de la validation locale du 21 novembre 2026, 21/21 targets étaient
`UP`; recompter les targets le jour de la démonstration et annoncer le résultat
observé à ce moment-là.

## 5. Scénario oral — environ 5 minutes

**0:00–0:40 — Introduction**

> Bonjour. Je présente MP4, le Dashboard et le monitoring de notre intégration
> Fog. Le Dashboard React lit l'API Cloud MP3. Prometheus collecte séparément
> les métriques exposées par les services MP2 et MP3, puis Grafana les présente.
> Nous montrons les réponses et mesures réellement disponibles ; nous n'ajoutons
> pas de données artificielles pour remplir l'écran.
>
> Les appels du navigateur passent par le proxy Nginx du Dashboard. React ne
> se connecte pas directement à PostgreSQL. Les listes sont paginées et leurs
> filtres modifient les résultats affichés.

**0:40–2:25 — Dashboard React**

> Je commence par la Vue d'ensemble pour situer les machines, les alertes et
> les états reçus. Dans Machines, je peux sélectionner un équipement et
> examiner ses mesures ainsi que son historique. Le statut affiché est déduit
> des mesures et des prédictions ; ce n'est pas un champ de statut fourni
> directement par l'API.
>
> Certaines valeurs de mesure ou dates peuvent être absentes. Le Dashboard les
> présente comme indisponibles et ne les remplace pas par une valeur inventée.
> Si une liste est vide, je vérifie les filtres et les données reçues avant d'en
> tirer une conclusion.
>
> Dans Maintenance Prédictive, je présente les prédictions disponibles, leur
> niveau de risque et les filtres. Dans Alertes, je montre les états et les
> filtres. Les états affichés viennent de l'API ; je ne change aucune alerte
> pendant la démonstration.
>
> Je passe ensuite à Surveillance Fog. Je présente les statuts, les ressources
> et les informations de heartbeat visibles dans les réponses. Un état inconnu
> ou une information manquante reste une information manquante ; nous ne la
> remplaçons pas par une valeur estimée.
>
> Enfin, dans Événements et migrations, les onglets séparent les événements de
> tâches, les événements MIGRATED et la supervision. Ces pages sont paginées
> et alimentées par l'API MP3. Elles peuvent ne contenir aucun événement pour
> la période affichée.

**2:25–4:10 — Grafana et Prometheus**

> Je passe à Grafana. La Vue globale rassemble l'état des targets et les sondes.
> Disponibilité et latence détaille les probes HTTP et la sonde TCP du broker.
> Services et conteneurs montre la disponibilité des endpoints et les métriques
> de conteneurs visibles par cAdvisor. CPU et mémoire affiche les ressources
> observées et les métriques CPU/RAM Fog.
>
> Le dernier tableau, Nœuds Fog et tâches, présente les files d'attente, les
> compteurs de tâches terminées ou échouées, les migrations et une latence de
> traitement. Les panneaux cAdvisor peuvent afficher un identifiant Docker au
> lieu d'un nom Compose. Certaines séries n'apparaissent que lorsqu'un
> événement réel a alimenté le compteur.
>
> Dans Prometheus, j'ouvre Status puis Targets. Je lis l'état au moment de la
> présentation. Lors de la validation locale du 21 novembre 2026, 21 targets
> sur 21 étaient UP ; ce résultat doit être revérifié aujourd'hui. UP confirme
> qu'un endpoint répond au scrape. Il ne prouve pas, à lui seul, que toute la
> chaîne métier fonctionne.
>
> La sonde HTTP mesure la réponse d'une route. La sonde du broker est seulement
> une vérification TCP : elle ne publie pas de message et ne valide pas
> l'authentification MQTT. Je distingue donc disponibilité réseau et traitement
> des données.

**4:10–5:00 — Conclusion**

> Pour conclure, MP4 rassemble les données du Dashboard et les métriques
> disponibles pour le monitoring. Les événements détaillés viennent de l'API ;
> Prometheus fournit surtout des métriques agrégées. Si une série ou un
> événement est absent, nous le signalons clairement. Par exemple, le graphique
> des migrations ne peut montrer un compteur qu'après une migration réelle.
> L'objectif est de présenter fidèlement l'état observable du système et ses
> limites, pas de déduire un résultat que les données ne confirment pas.

## 6. Limites connues

- Si MP2 n'expose pas une métrique ou si Prometheus ne reçoit aucun échantillon,
  le panneau correspondant reste vide. `UP` ne garantit pas la présence de
  données métier.
- Les tâches et migrations sont des événements détaillés dans l'API MP3; les
  métriques Prometheus MP2 sont des compteurs, jauges et histogrammes. Elles ne
  remplacent pas un journal de chaque événement.
- Le compteur `fog_migrations_total` ne produit une série qu'après une migration
  réelle. Une période sans migration donne donc un panneau vide, sans que cela
  prouve une erreur de collecte.
- La sonde Mosquitto vérifie seulement l'ouverture TCP, pas l'authentification,
  la publication ou la réception de messages MQTT.
- L'état `UP` ne donne pas l'état détaillé d'un conteneur, son code de sortie ni
  son nombre de redémarrages. cAdvisor ne fournit pas un historique fiable des
  conteneurs arrêtés et ses panneaux peuvent afficher des identifiants Docker
  plutôt que des noms Compose.
- La supervision Fog repose sur les heartbeats et les seuils configurés. Un
  nœud `UNKNOWN` ou `UNREACHABLE` n'est pas à lui seul une preuve de panne
  matérielle. L'indisponibilité réelle n'est pas calculée sans preuves
  suffisantes.
- Cette intégration n'ajoute pas de métriques MP1 ni d'exporter PostgreSQL.
  Mosquitto n'a pas d'endpoint `/metrics` configuré.
- Si l'API MP3 ne contient pas encore d'historique, les pages peuvent être vides.
  Les événements de tâches ne fournissent pas toujours un identifiant de
  machine.

Les détails et limites complets sont dans [monitoring.md](./monitoring.md),
[docker.md](./docker.md) et [api-contract.md](./api-contract.md).

## 7. Vérification finale avant la présentation

Ces commandes PowerShell sont des lectures et des requêtes HTTP GET. Elles ne
démarrent, n'arrêtent ni ne redémarrent de service et n'écrivent pas dans MQTT
ou PostgreSQL.

```powershell
docker info --format 'Docker Engine {{.ServerVersion}}'
docker ps -a --format '{{.Names}}|{{.Status}}|{{.Ports}}' |
  Select-String '^(mp4-|mp2-|mp3-cloud-)'
```

Vérifier ensuite les endpoints du Dashboard, de Grafana, de Prometheus et les
routes API utilisées par MP4 :

```powershell
$urls = @(
  'http://localhost:3001/healthz',
  'http://localhost:3001/api/v1/machines?limit=1',
  'http://localhost:3001/api/v1/fog/nodes?limit=1',
  'http://localhost:3001/api/v1/tasks/events?limit=1',
  'http://localhost:3001/api/v1/fog/supervision-history?limit=1',
  'http://localhost:3002/api/health',
  'http://localhost:9090/-/healthy'
)

foreach ($url in $urls) {
  try {
    $response = Invoke-WebRequest -Method Get -Uri $url `
      -UseBasicParsing -TimeoutSec 5
    Write-Output ("HTTP {0} {1}" -f [int]$response.StatusCode, $url)
  } catch {
    Write-Output ("ECHEC {0} : {1}" -f $url, $_.Exception.Message)
  }
}
```

Compter les targets et afficher ceux qui ne sont pas `UP` :

```powershell
$targets = Invoke-RestMethod -Method Get `
  -Uri 'http://localhost:9090/api/v1/targets' -TimeoutSec 5
$active = @($targets.data.activeTargets)
$notUp = @($active | Where-Object { $_.health -ne 'up' })
Write-Output ("Targets UP : {0}/{1}" -f ($active.Count - $notUp.Count), $active.Count)
$notUp | Select-Object `
  @{Name='job'; Expression={$_.labels.job}},
  @{Name='instance'; Expression={$_.labels.instance}},
  health, lastError
```

Si un endpoint échoue ou si des targets ne sont pas `UP`, annoncer le problème
et son périmètre avant la démonstration. Ne pas créer de données artificielles
pour masquer une absence de métriques.
