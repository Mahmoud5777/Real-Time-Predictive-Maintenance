# Déploiement réel Lot 4 sur 4 PC — guide d'intégration

Ce pack est un **complément additif** au dépôt Collaborative-Fog-Computing. Il réutilise les scripts et Docker Compose déjà présents dans `Lot4_Automation/` et `Lot4_LAN_Integration/`. Il ne remplace pas les configurations validées.

## Architecture

- PC 1 (Central) : broker MQTT + Scheduler. Les services de supervision Prometheus/Grafana/Blackbox restent hébergés selon la configuration monitoring déjà validée sur le PC central.
- PC 2 : Fog A.
- PC 3 : Fog B.
- PC 4 : Fog C.

Le fichier commun `Lot4_Automation/config/deployment.json` décrit les IP et ports. Les quatre PC doivent utiliser le même fichier de configuration et la même version du dépôt.

## Avant le jour du déploiement

1. Remplacer les quatre IP d'exemple dans `Lot4_Automation/config/deployment.json` par les IP réellement réservées sur le LAN.
2. Adapter `network.subnetCidr` au sous-réseau réel. Vérifier que les quatre IP appartiennent à ce sous-réseau et sont réservées/statiques.
3. Vérifier que les ports déclarés correspondent aux Compose et variables d'environnement existants. Le pack conserve les ports documentés du projet : MQTT 1883, scheduler 8100, Fog 8101–8103, Prometheus 9090, Grafana 3002, Blackbox 9115.
4. Publier le code dans Git après validation, ou utiliser une archive identique sur les quatre machines. Ne pas copier de `.env` contenant des secrets dans Git.
5. Installer Docker Desktop, démarrer Docker Engine et vérifier `docker info` sur chaque PC.

## Préparation locale sans les quatre PC

Depuis la racine du dépôt :

```powershell
.\Lot4_Automation\Validate-DeploymentJson.ps1
```

La validation vérifie la syntaxe JSON, les adresses IPv4 uniques et les ports. Les IP d'exemple ne sont pas automatiquement détectées comme fausses : remplace-les avant tout déploiement réel.

## Jour du déploiement

### 1. PC central

Récupérer le même dépôt/commit sur le PC central, puis depuis sa racine :

```powershell
.\Lot4_Automation\Deploy-FromJson.ps1 -Role central -GenerateEnv
```

Cette commande vérifie que l'IP locale du PC correspond à `centralIp`, génère les fichiers `.env` avec les scripts existants, puis appelle le déploiement central déjà présent.

### 2. PC Fog A, B et C

Sur chaque PC, récupérer le même dépôt et le même `deployment.json`. Exécuter le rôle correspondant :

```powershell
.\Lot4_Automation\Deploy-FromJson.ps1 -Role fog-a -GenerateEnv
```

Sur le PC suivant :

```powershell
.\Lot4_Automation\Deploy-FromJson.ps1 -Role fog-b -GenerateEnv
```

Puis :

```powershell
.\Lot4_Automation\Deploy-FromJson.ps1 -Role fog-c -GenerateEnv
```

Chaque script refuse de lancer le déploiement si l'IP locale ne correspond pas au rôle sélectionné. La configuration firewall n'est **pas** modifiée automatiquement : appliquer les règles validées séparément, avec autorisation administrateur et uniquement sur le profil réseau privé.

### 3. Vérification depuis le PC central

```powershell
.\Lot4_Automation\Test-DeploymentFromJson.ps1
```

Puis vérifier les heartbeats et l'état ONLINE des trois Fog dans le scheduler, ainsi que les targets Prometheus et le dashboard Grafana.

## Modèle de distribution

La méthode retenue est volontairement simple et reproductible : cloner/récupérer le même commit sur chaque machine, copier le même JSON non secret, puis exécuter localement le script correspondant au rôle. L'exécution distante automatique (WinRM/SSH) n'est pas activée par défaut : elle exige une configuration d'identité, d'autorisations et de pare-feu sur les quatre PC.

## Sécurité et précautions

- Ne jamais commiter `central/.env`, `fog-node/.env.fog`, ni `monitoring/.env`.
- Ne pas exposer MQTT, Prometheus ou Grafana à Internet ; limiter les accès au LAN de confiance.
- Utiliser un mot de passe Grafana unique et protéger les identifiants.
- Ne pas lancer `docker compose down -v`.
- Les scripts n'arrêtent pas MP2/MP3/MP4 et ne suppriment aucun volume.
- Vérifier les règles Windows Firewall et la connectivité inter-PC avant lancement.

## Limites connues

Le script de déploiement réutilise les Compose/scripts Lot4 existants. Les tests réels de communication inter-PC, du pare-feu, des pertes réseau et de la reprise après panne ne peuvent être déclarés réussis qu'après exécution sur les quatre machines physiques. Une simulation sur un seul PC ne remplace pas ces tests.
