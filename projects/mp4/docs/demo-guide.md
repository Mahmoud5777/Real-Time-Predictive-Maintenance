# Guide de dÃ©monstration â€” MP4 Dashboard and Monitoring

Ce guide dÃ©crit une dÃ©monstration avec les donnÃ©es rÃ©ellement disponibles dans
l'API MP3 et les mÃ©triques collectÃ©es. Le Dashboard n'invente pas de donnÃ©es de
dÃ©monstration. Une rÃ©ponse vide doit Ãªtre prÃ©sentÃ©e comme telle.

## 1. PrÃ©paration

### Services nÃ©cessaires

Avant la prÃ©sentation, vÃ©rifier que les Ã©quipes responsables ont dÃ©marrÃ© :

- **MP3** : l'API Cloud, PostgreSQL, Mosquitto et les workers Ingest, Analytics,
  Supervision et Retention.
- **MP2** : le Scheduler et les Fog A, B et C, connectÃ©s au rÃ©seau partagÃ©
  `mp3-cloud_default`.
- **MP4** : `mp4-dashboard-api`, Prometheus, Grafana, Blackbox Exporter et
  cAdvisor.

MP3 doit fournir le rÃ©seau `mp3-cloud_default` et l'API `api:8000` avant le
dÃ©marrage de MP4. Les services MP2/MP3 restent gÃ©rÃ©s par leurs Ã©quipes. Depuis
PowerShell, dans `projects/mp4`, les commandes de dÃ©marrage MP4 documentÃ©es
sont :

```powershell
$env:GF_SECURITY_ADMIN_PASSWORD = '<mot de passe local non versionnÃ©>'
docker compose -f docker-compose.yml up -d --build
docker compose -f docker/docker-compose.monitoring.yml up -d
```

Remplacer le texte entre chevrons par un mot de passe local. Ne pas l'ajouter au
dÃ©pÃ´t. Si les services sont dÃ©jÃ  actifs, ne pas les redÃ©marrer pour la
prÃ©sentation.

### URLs locales

| Service | URL |
|---|---|
| Dashboard MP4 | `http://localhost:3001` |
| SantÃ© Dashboard | `http://localhost:3001/healthz` |
| Grafana | `http://localhost:3002` |
| SantÃ© Grafana | `http://localhost:3002/api/health` |
| Prometheus | `http://localhost:9090` |
| Targets Prometheus | `http://localhost:9090/targets` |
| SantÃ© Prometheus | `http://localhost:9090/-/healthy` |

Le compte Grafana est `admin` par dÃ©faut. Son mot de passe est celui fourni dans
`GF_SECURITY_ADMIN_PASSWORD`.

## 2. DÃ©monstration du Dashboard React

Le menu latÃ©ral prÃ©sente les pages suivantes :

1. **Vue d'ensemble** : situer les machines, les alertes et l'Ã©tat gÃ©nÃ©ral Ã 
   partir des donnÃ©es reÃ§ues.
2. **Machines** : choisir une machine, consulter ses mesures et leur historique.
   Le statut affichÃ© est dÃ©duit des mesures et des prÃ©dictions.
3. **Maintenance PrÃ©dictive** : prÃ©senter les prÃ©dictions disponibles, leur
   niveau de risque et les filtres proposÃ©s.
4. **Alertes** : parcourir les alertes et leurs Ã©tats. Une liste vide signifie
   qu'aucune alerte ne correspond aux donnÃ©es et filtres reÃ§us.
5. **Surveillance Fog** : montrer l'Ã©tat rapportÃ© des nÅ“uds, leurs ressources et
   leurs informations de supervision lorsqu'elles sont disponibles.
6. **Ã‰vÃ©nements et migrations** : utiliser les onglets **Tous les Ã©vÃ©nements de
   tÃ¢ches**, **Ã‰vÃ©nements MIGRATED** et **Supervision**. Les listes sont paginÃ©es.

Les appels du Dashboard passent par le proxy Nginx vers l'API Cloud MP3. Les
pages de tÃ¢ches et de supervision reflÃ¨tent les rÃ©ponses de l'API; elles ne
garantissent pas qu'un Ã©vÃ©nement existe pour la pÃ©riode choisie.

## 3. DÃ©monstration Grafana

PrÃ©senter les cinq dashboards dans cet ordre :

1. **MP4 - Vue globale** (`infrastructure`) : Ã©tat des targets, sondes HTTP,
   connectivitÃ© TCP du broker et activitÃ© Ingest exposÃ©e par MP3.
2. **MP4 - DisponibilitÃ© et latence API** (`api-availability`) : succÃ¨s et
   durÃ©e des sondes HTTP, puis sonde TCP Mosquitto.
3. **MP4 - Services et conteneurs** (`services`) : disponibilitÃ© des endpoints,
   Ã©tats de prÃ©paration exposÃ©s par les workers MP3 et Ã¢ge des Ã©chantillons
   cAdvisor.
4. **MP4 - CPU et mÃ©moire** (`resources`) : ressources des conteneurs visibles
   par cAdvisor et CPU/RAM des nÅ“uds Fog.
5. **MP4 - NÅ“uds Fog et tÃ¢ches** (`fog-nodes`) : file d'attente, tÃ¢ches
   terminÃ©es/Ã©chouÃ©es, migrations et latence de traitement p95.

Les panneaux sont alimentÃ©s par Prometheus. Une sÃ©rie absente peut laisser un
panneau vide : ne pas remplacer ce rÃ©sultat par une valeur supposÃ©e.

## 4. Prometheus

Ouvrir **Status â†’ Targets** ou `http://localhost:9090/targets` et montrer les
targets `UP`. Les jobs couvrent notamment :

- l'API et les workers MP3 ;
- le Scheduler et les trois Fog MP2 ;
- les sondes HTTP, y compris le Dashboard MP4 ;
- la sonde TCP Mosquitto, Prometheus, Blackbox Exporter et cAdvisor.

`UP` signifie que Prometheus a pu joindre et scruter l'endpoint configurÃ©. Cela
ne prouve pas Ã  lui seul que le traitement mÃ©tier ou MQTT fonctionne de bout en
bout. Lors de la validation locale du 21 novembre 2026, 21/21 targets Ã©taient
`UP`; recompter les targets le jour de la dÃ©monstration et annoncer le rÃ©sultat
observÃ© Ã  ce moment-lÃ .

## 5. ScÃ©nario oral â€” environ 5 minutes

**0:00â€“0:40 â€” Introduction**

> Bonjour. Je prÃ©sente MP4, le Dashboard et le monitoring de notre intÃ©gration
> Fog. Le Dashboard React lit l'API Cloud MP3. Prometheus collecte sÃ©parÃ©ment
> les mÃ©triques exposÃ©es par les services MP2 et MP3, puis Grafana les prÃ©sente.
> Nous montrons les rÃ©ponses et mesures rÃ©ellement disponibles ; nous n'ajoutons
> pas de donnÃ©es artificielles pour remplir l'Ã©cran.
>
> Les appels du navigateur passent par le proxy Nginx du Dashboard. React ne
> se connecte pas directement Ã  PostgreSQL. Les listes sont paginÃ©es et leurs
> filtres modifient les rÃ©sultats affichÃ©s.

**0:40â€“2:25 â€” Dashboard React**

> Je commence par la Vue d'ensemble pour situer les machines, les alertes et
> les Ã©tats reÃ§us. Dans Machines, je peux sÃ©lectionner un Ã©quipement et
> examiner ses mesures ainsi que son historique. Le statut affichÃ© est dÃ©duit
> des mesures et des prÃ©dictions ; ce n'est pas un champ de statut fourni
> directement par l'API.
>
> Certaines valeurs de mesure ou dates peuvent Ãªtre absentes. Le Dashboard les
> prÃ©sente comme indisponibles et ne les remplace pas par une valeur inventÃ©e.
> Si une liste est vide, je vÃ©rifie les filtres et les donnÃ©es reÃ§ues avant d'en
> tirer une conclusion.
>
> Dans Maintenance PrÃ©dictive, je prÃ©sente les prÃ©dictions disponibles, leur
> niveau de risque et les filtres. Dans Alertes, je montre les Ã©tats et les
> filtres. Les Ã©tats affichÃ©s viennent de l'API ; je ne change aucune alerte
> pendant la dÃ©monstration.
>
> Je passe ensuite Ã  Surveillance Fog. Je prÃ©sente les statuts, les ressources
> et les informations de heartbeat visibles dans les rÃ©ponses. Un Ã©tat inconnu
> ou une information manquante reste une information manquante ; nous ne la
> remplaÃ§ons pas par une valeur estimÃ©e.
>
> Enfin, dans Ã‰vÃ©nements et migrations, les onglets sÃ©parent les Ã©vÃ©nements de
> tÃ¢ches, les Ã©vÃ©nements MIGRATED et la supervision. Ces pages sont paginÃ©es
> et alimentÃ©es par l'API MP3. Elles peuvent ne contenir aucun Ã©vÃ©nement pour
> la pÃ©riode affichÃ©e.

**2:25â€“4:10 â€” Grafana et Prometheus**

> Je passe Ã  Grafana. La Vue globale rassemble l'Ã©tat des targets et les sondes.
> DisponibilitÃ© et latence dÃ©taille les probes HTTP et la sonde TCP du broker.
> Services et conteneurs montre la disponibilitÃ© des endpoints et les mÃ©triques
> de conteneurs visibles par cAdvisor. CPU et mÃ©moire affiche les ressources
> observÃ©es et les mÃ©triques CPU/RAM Fog.
>
> Le dernier tableau, NÅ“uds Fog et tÃ¢ches, prÃ©sente les files d'attente, les
> compteurs de tÃ¢ches terminÃ©es ou Ã©chouÃ©es, les migrations et une latence de
> traitement. Les panneaux cAdvisor peuvent afficher un identifiant Docker au
> lieu d'un nom Compose. Certaines sÃ©ries n'apparaissent que lorsqu'un
> Ã©vÃ©nement rÃ©el a alimentÃ© le compteur.
>
> Dans Prometheus, j'ouvre Status puis Targets. Je lis l'Ã©tat au moment de la
> prÃ©sentation. Lors de la validation locale du 21 novembre 2026, 21 targets
> sur 21 Ã©taient UP ; ce rÃ©sultat doit Ãªtre revÃ©rifiÃ© aujourd'hui. UP confirme
> qu'un endpoint rÃ©pond au scrape. Il ne prouve pas, Ã  lui seul, que toute la
> chaÃ®ne mÃ©tier fonctionne.
>
> La sonde HTTP mesure la rÃ©ponse d'une route. La sonde du broker est seulement
> une vÃ©rification TCP : elle ne publie pas de message et ne valide pas
> l'authentification MQTT. Je distingue donc disponibilitÃ© rÃ©seau et traitement
> des donnÃ©es.

**4:10â€“5:00 â€” Conclusion**

> Pour conclure, MP4 rassemble les donnÃ©es du Dashboard et les mÃ©triques
> disponibles pour le monitoring. Les Ã©vÃ©nements dÃ©taillÃ©s viennent de l'API ;
> Prometheus fournit surtout des mÃ©triques agrÃ©gÃ©es. Si une sÃ©rie ou un
> Ã©vÃ©nement est absent, nous le signalons clairement. Par exemple, le graphique
> des migrations ne peut montrer un compteur qu'aprÃ¨s une migration rÃ©elle.
> L'objectif est de prÃ©senter fidÃ¨lement l'Ã©tat observable du systÃ¨me et ses
> limites, pas de dÃ©duire un rÃ©sultat que les donnÃ©es ne confirment pas.

## 6. Limites connues

- Si MP2 n'expose pas une mÃ©trique ou si Prometheus ne reÃ§oit aucun Ã©chantillon,
  le panneau correspondant reste vide. `UP` ne garantit pas la prÃ©sence de
  donnÃ©es mÃ©tier.
- Les tÃ¢ches et migrations sont des Ã©vÃ©nements dÃ©taillÃ©s dans l'API MP3; les
  mÃ©triques Prometheus MP2 sont des compteurs, jauges et histogrammes. Elles ne
  remplacent pas un journal de chaque Ã©vÃ©nement.
- Le compteur `fog_migrations_total` ne produit une sÃ©rie qu'aprÃ¨s une migration
  rÃ©elle. Une pÃ©riode sans migration donne donc un panneau vide, sans que cela
  prouve une erreur de collecte.
- La sonde Mosquitto vÃ©rifie seulement l'ouverture TCP, pas l'authentification,
  la publication ou la rÃ©ception de messages MQTT.
- L'Ã©tat `UP` ne donne pas l'Ã©tat dÃ©taillÃ© d'un conteneur, son code de sortie ni
  son nombre de redÃ©marrages. cAdvisor ne fournit pas un historique fiable des
  conteneurs arrÃªtÃ©s et ses panneaux peuvent afficher des identifiants Docker
  plutÃ´t que des noms Compose.
- La supervision Fog repose sur les heartbeats et les seuils configurÃ©s. Un
  nÅ“ud `UNKNOWN` ou `UNREACHABLE` n'est pas Ã  lui seul une preuve de panne
  matÃ©rielle. L'indisponibilitÃ© rÃ©elle n'est pas calculÃ©e sans preuves
  suffisantes.
- Cette intÃ©gration n'ajoute pas de mÃ©triques MP1 ni d'exporter PostgreSQL.
  Mosquitto n'a pas d'endpoint `/metrics` configurÃ©.
- Si l'API MP3 ne contient pas encore d'historique, les pages peuvent Ãªtre vides.
  Les Ã©vÃ©nements de tÃ¢ches ne fournissent pas toujours un identifiant de
  machine.

Les dÃ©tails et limites complets sont dans [monitoring.md](./monitoring.md),
[docker.md](./docker.md) et [api-contract.md](./api-contract.md).

## 7. VÃ©rification finale avant la prÃ©sentation

Ces commandes PowerShell sont des lectures et des requÃªtes HTTP GET. Elles ne
dÃ©marrent, n'arrÃªtent ni ne redÃ©marrent de service et n'Ã©crivent pas dans MQTT
ou PostgreSQL.

```powershell
docker info --format 'Docker Engine {{.ServerVersion}}'
docker ps -a --format '{{.Names}}|{{.Status}}|{{.Ports}}' |
  Select-String '^(mp4-|mp2-|mp3-cloud-)'
```

VÃ©rifier ensuite les endpoints du Dashboard, de Grafana, de Prometheus et les
routes API utilisÃ©es par MP4 :

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

Si un endpoint Ã©choue ou si des targets ne sont pas `UP`, annoncer le problÃ¨me
et son pÃ©rimÃ¨tre avant la dÃ©monstration. Ne pas crÃ©er de donnÃ©es artificielles
pour masquer une absence de mÃ©triques.
