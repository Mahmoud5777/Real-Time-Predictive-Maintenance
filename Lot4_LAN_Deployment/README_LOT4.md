# LOT 4 — Déploiement LAN multi-PC (Toolkit d'intégration)

**Projet : Collaborative Fog Computing / Predictive Maintenance**

Ce lot prépare la séparation du système sur quatre ordinateurs :
- **PC Central** : MP1 Simulator, MQTT Broker, MP2 Scheduler, MP3 Cloud (API/ingestion/analytics/etc.), MP4 Dashboard, Prometheus, Grafana.
- **PC Fog A / B / C** : un seul nœud Fog par machine.

> Ce ZIP est un kit d'intégration et de configuration. Il ne remplace pas automatiquement les compose existants et ne modifie pas vos algorithmes MP2 déjà testés. Les chemins/build contexts du dépôt doivent être raccordés aux vrais fichiers locaux avant lancement. Le kit fournit les fichiers d'environnement, snippets Prometheus, scripts PowerShell et un compose modèle pour les nœuds distants.

## 1. Préparation réseau
1. Connecter les 4 PCs au même réseau LAN (ou VPN privé).
2. Attribuer des adresses stables (réservation DHCP conseillée).
3. Relever l'IPv4 du PC Central et de chaque Fog PC.
4. Depuis chaque Fog PC, vérifier l'accès à MQTT central (TCP 1883).
5. Depuis Central, vérifier l'accès HTTP au port d'API de chaque Fog (valeurs configurables).

## 2. Configurer les fichiers
- Copier `config/central.env.example` vers un fichier `.env` privé (ne pas committer de secrets).
- Copier `config/fog-node.env.example` sur chaque Fog PC et remplir `FOG_ID`, `FOG_ZONE`, `CENTRAL_HOST`, et `FOG_HOST_PORT`.
- Remplacer les IP d'exemple dans `config/prometheus-lan.yml` par les IP réelles.
- Configurer le Scheduler avec `FOG_A_URL`, `FOG_B_URL`, `FOG_C_URL` (exemple: `http://192.168.1.21:8001`).
- Configurer chaque Fog node pour utiliser le broker central via `MQTT_BROKER_HOST=<IP_CENTRAL>` et `MQTT_BROKER_PORT=1883`.

## 3. Ports LAN à prévoir
| Service | Port TCP | Où |
|---|---:|---|
| MQTT broker | 1883 | Central, entrant des Fog PCs et MP1 |
| Scheduler API | 8000 (ou port publié existant) | Central |
| Fog A/B/C API | 8001/8002/8003 (adaptable) | PC Fog |
| MP3 API | 8000 (selon stack actuelle) | Central |
| MP3 ingest | 8001 (selon stack actuelle) | Central |
| MP4 dashboard | 3001 | Central |
| Prometheus | 9090 | Central, accès local par défaut |
| Grafana | 3002 | Central, accès local par défaut |

**Attention:** la stack intégrée actuelle publie parfois des ports host différents (8100–8103, 1884). Vérifiez vos compose avant d'ouvrir les ports. N'ouvrez pas les ports Grafana/Prometheus à Internet. Limitez les règles Firewall aux IP du LAN.

## 4. Déploiement Central
1. Garder les compose actuels MP2/MP3/MP4 pour le mode mono-PC.
2. Lancer les services centraux existants en utilisant leurs compose/profiles habituels.
3. Utiliser le fichier `config/prometheus-lan.yml` pour adapter la cible Prometheus aux IP Fog distantes (fusionner les jobs avec le Prometheus actuel, ne pas remplacer les jobs MP3 existants).
4. Utiliser le template `monitoring/docker-compose.monitoring-lan.yml` comme référence d'intégration; renseigner les variables Grafana.
5. Dans le Scheduler, définir les trois URLs Fog distantes. Ne pas laisser les URLs localhost en déploiement multi-PC.
6. Le dashboard MP4 doit continuer d'utiliser l'API MP3 centrale.

## 5. Déploiement d'un Fog PC
1. Copier ce dossier `Lot4_LAN_Deployment` et le dépôt du projet sur la machine Fog, ou préparer le dépôt sur celle-ci.
2. Renseigner `.env` à partir du template.
3. Construire/obtenir l'image Fog existante du projet et définir `FOG_IMAGE` dans `.env`.
4. Lancer `docker compose -f compose/fog-node.compose.yml --env-file .env up -d`.
5. Vérifier `http://localhost:<FOG_HOST_PORT>/health` et la connexion MQTT.
6. Sur Central, configurer l'URL de ce nœud dans le Scheduler et Prometheus.

Le compose Fog est un **modèle**: il suppose que l'image existante accepte les variables FOG_ID/FOG_ZONE/MQTT_BROKER_HOST/MQTT_BROKER_PORT et écoute sur le port container 8001. Si l'image MP2 réelle utilise un autre port ou une autre commande, adapter `compose/fog-node.compose.yml` à la configuration du nœud existant.

## 6. Scripts Windows
Exécuter depuis PowerShell:
- `scripts/Test-LanDeployment.ps1` : vérifie les variables et les ports réseau.
- `scripts/Set-LanFirewallRules.ps1` : crée des règles Windows Firewall restreintes au subnet/IPs renseignées (administrateur requis).
- `scripts/Start-FogNode.ps1` : démarre le compose Fog modèle.
- `scripts/Stop-FogNode.ps1` : arrête le compose Fog modèle.
- `scripts/Status-FogNode.ps1` : affiche état compose et test endpoint health.

## 7. Sécurité
- Ne versionnez jamais les `.env` contenant mots de passe.
- Utilisez une réservation DHCP/IP fixe.
- Restreignez les règles Firewall au LAN.
- Grafana/Prometheus restent localement publiés par défaut.
- Pour un déploiement réel, prévoyez MQTT authentifié + TLS; ce toolkit ne configure pas de certificats.

## 8. Validation ciblée (sans rejouer MP2)
Sur chaque PC, valider configuration Compose:
```powershell
docker compose -f compose/fog-node.compose.yml --env-file .env config
```
Tester la connectivité central depuis un Fog PC:
```powershell
Test-NetConnection <IP_CENTRAL> -Port 1883
```
Depuis Central, vérifier l'API Fog distante:
```powershell
Test-NetConnection <IP_FOG_A> -Port 8001
Invoke-RestMethod "http://<IP_FOG_A>:8001/health"
```
Cette validation LAN ne rejoue pas les scénarios MP2 déjà validés.

## 9. Rollback
Arrêter uniquement le Fog compose modèle sur les PCs distants. Le compose intégré mono-PC du dépôt reste intact. Sur Central, restaurer les anciennes URLs Scheduler et la configuration Prometheus précédente.
