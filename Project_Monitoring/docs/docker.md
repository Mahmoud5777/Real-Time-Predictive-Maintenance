# Documentation Docker & Déploiement — Module MP4 (Monitoring Dashboard)

## 1. Contexte et Architecture Globale

Le module **MP4 (Industrial Monitoring Dashboard)** constitue l'interface de supervision et d'observabilité du système distribué de maintenance prédictive et fog computing.

### 1.1. Rôle du Module
* **Frontend SPA** : Développé en React 19 et packagé avec Vite 8.
* **Serveur Web de Production** : Nginx Alpine servant les artefacts statiques compilés, assurant la compression, la sécurité HTTP et le routage d'application à page unique (SPA).
* **Mode Opérationnel Actuel** : Standalone avec source de données simulée (`mock`).
* **Préparation Intégration** : Architecture découplée prête pour l'interconnexion avec les APIs FastAPI du Cloud Backend (**MP3**) sans impacter le mode autonome.

```
                    +------------------------------------+
                    |       Navigateur Utilisateur       |
                    +------------------------------------+
                                      |
                                      | HTTP :3000
                                      v
    +--------------------------------------------------------------------+
    | Conteneur Docker : mp4-dashboard (Image: mp4-dashboard:latest)    |
    |                                                                    |
    |   +------------------------------------------------------------+   |
    |   | Nginx 1.31 (Alpine) - Port interne : 80                    |   |
    |   |                                                            |   |
    |   |   - /          -> index.html + try_files (SPA Fallback)    |   |
    |   |   - /assets/*  -> Fichiers JS/CSS hachés (Cache immutable) |   |
    |   |   - /healthz   -> Sonde de santé HTTP (Healthcheck Docker) |   |
    |   |                                                            |   |
    |   |   [Optionnel Intégration MP3 :]                            |   |
    |   |   - /api/*     -> Reverse Proxy vers FastAPI (Port 8000)   |   |
    |   +------------------------------------------------------------+   |
    |                                                                    |
    |   Réseau Docker isolé : mp4-network (bridge)                       |
    +--------------------------------------------------------------------+
```

---

## 2. Organisation des Fichiers

```
Project_Monitoring/
├── docker-compose.yml              # Fichier Compose principal (mode standalone)
├── docker/
│   ├── docker-compose.api.yml      # Template Compose pour future intégration MP3
│   └── nginx/
│       └── nginx.api.conf          # Configuration Nginx avec reverse-proxy /api/
├── docs/
│   └── docker.md                   # Ce document technique
└── frontend/
    ├── Dockerfile                  # Multi-stage build (Node.js -> Nginx Alpine)
    ├── .dockerignore               # Exclusion optimisée du contexte de build
    ├── nginx.conf                  # Configuration Nginx standalone (mock)
    ├── nginx.api.conf              # Copie locale de référence pour reverse-proxy
    ├── .env                        # Variables locales (développement)
    ├── .env.production             # Variables de build (production mock)
    ├── package.json                # Dépendances React 19 & Vite 8
    └── src/                        # Code source React
```

---

## 3. Analyse du Dockerfile Multi-Stage

Le `Dockerfile` situé dans `frontend/Dockerfile` repose sur une approche multi-étapes pour garantir une taille d'image minimale, des builds reproductibles et une sécurité renforcée.

### Étape 1 : Construction (Builder)
* **Image de base** : `node:20-alpine`.
* **Arguments de build (`ARG`)** :
  * `VITE_API_BASE_URL` : URL du backend (vide par défaut en mode mock).
  * `VITE_DATA_SOURCE` : `mock` par défaut pour l'exécution standalone.
* **Gestion du cache des couches** :
  * Copie de `package*.json` suivie de `npm ci` avant de copier le reste du code source. Les dépendances ne sont réinstallées que si `package.json` ou `package-lock.json` change.
* **Compilation** : Exécution de `npm run build` produisant les bundles optimisés dans `/app/dist`.

### Étape 2 : Image Finale d'Exécution (Runner)
* **Image de base** : `nginx:alpine` (empreinte mémoire minimale ~26 Mo compressée, ~94 Mo décompressée).
* **Isolation** : Seul le dossier `/app/dist` est transféré depuis le builder. Le dossier `node_modules` et le compilateur Node.js sont exclus de l'image de production.
* **Configuration** : Remplacement du fichier `/etc/nginx/conf.d/default.conf` par la configuration durcie `nginx.conf`.
* **Sonde de santé (`HEALTHCHECK`)** :
  * Exécute `wget --quiet --tries=1 --spider http://127.0.0.1:80/healthz || exit 1`.
  * Intervalle : 30 secondes, Timeout : 3 secondes, Délai initial : 5 secondes, 3 tentatives.

---

## 4. Configuration Nginx

### 4.1. Configuration Standalone (`frontend/nginx.conf`)
* **En-têtes de Sécurité HTTP** :
  * `X-Frame-Options "SAMEORIGIN"` (protection contre le clickjacking).
  * `X-Content-Type-Options "nosniff"` (protection contre le reniflage de type MIME).
  * `X-XSS-Protection "1; mode=block"` (filtre anti-XSS).
  * `Referrer-Policy "strict-origin-when-cross-origin"`.
* **Compression Gzip** : Activée pour le texte, CSS, JavaScript, JSON et SVG afin d'accélérer les transferts réseau.
* **Stratégie de Cache HTTP** :
  * `/assets/*` : Cache public immutable d'un an (`max-age=31536000, immutable`).
  * `index.html` : Aucun cache (`no-store, no-cache, must-revalidate`) pour garantir la propagation immédiate des mises à jour.
* **Routage SPA** : `try_files $uri $uri/ /index.html;` permettant à React de gérer la navigation côté client sur n'importe quelle URL rechargée directement par l'utilisateur.
* **Endpoint `/healthz`** : Retourne immédiatement un code `200 OK` avec le texte `healthy\n` sans enregistrer de journaux inutiles (`access_log off`).

### 4.2. Configuration Intégration API (`docker/nginx/nginx.api.conf`)
Identique à la configuration standalone, avec l'ajout du bloc reverse-proxy suivant :
```nginx
location /api/ {
    proxy_pass http://api:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
```

### 4.3. Canonical API proxy configuration

The canonical API integration configuration is `docker/nginx/nginx.api.conf`, mounted by
`docker/docker-compose.api.yml`. The file `frontend/nginx.api.conf` is a duplicate copy and
is not the Compose-mounted canonical file. `frontend/nginx.conf` remains the standalone
mock configuration. `frontend/nginx.conf.bak` is a backup and must be preserved.

### 4.4. Standalone and API Compose commands

From `Project_Monitoring`:

```powershell
# Standalone dashboard in mock mode
docker compose -f docker-compose.yml up -d

# Static validation only
docker compose -f docker-compose.yml config
docker compose -f docker/docker-compose.api.yml config
```

---

## 5. Guide d'Exploitation (Commandes)

Toutes les commandes s'exécutent depuis la racine du projet : `C:\Users\PC\Desktop\IT\GI3-\Cloud\Project\Project_Monitoring`.

### 5.1. Validation de la Configuration Compose
```powershell
docker compose config
```

### 5.2. Construction de l'Image
```powershell
# Construction sans cache pour forcer la recompilation
docker compose build --no-cache

# Ou construction standard avec utilisation du cache
docker compose build
```

### 5.3. Démarrage du Service
```powershell
docker compose up -d
```

### 5.4. Vérification de l'État et du Healthcheck
```powershell
# Afficher les conteneurs du projet MP4
docker compose ps

# Inspecter le statut de santé précis
docker inspect --format='{{json .State.Health.Status}}' mp4-dashboard
```

### 5.5. Consultation des Journaux
```powershell
# Afficher les derniers logs
docker compose logs

# Suivre les logs en direct (streaming)
docker compose logs -f
```

### 5.6. Arrêt et Redémarrage
```powershell
# Arrêter le conteneur MP4 proprement
docker compose stop

# Relancer le conteneur MP4
docker compose start

# Arrêter et supprimer le conteneur et le réseau du projet MP4 uniquement
docker compose down
```
> **RAPPEL IMPORTANT** : N'exécutez `docker compose down` que depuis le répertoire `Project_Monitoring`. Ne jamais exécuter de commande globale qui impacterait les conteneurs MP1, MP2 ou MP3.

---

## 6. Procédure de Test et Validation

### 6.1. Test de Connectivité HTTP Racine
```powershell
curl.exe -i http://localhost:3000/
```
* **Résultat attendu** : Code HTTP `200 OK`, en-tête `Cache-Control: no-store, no-cache...`, rendu du code HTML avec le div `<div id="root"></div>`.

### 6.2. Test de l'Endpoint de Santé
```powershell
curl.exe -i http://localhost:3000/healthz
```
* **Résultat attendu** : Code HTTP `200 OK`, contenu texte `healthy`.

### 6.3. Test du Routage SPA (Les 6 Pages du Dashboard)
```powershell
# Test des 6 routes du dashboard
curl.exe -s -o NUL -w "%{http_code}\n" http://localhost:3000/overview
curl.exe -s -o NUL -w "%{http_code}\n" http://localhost:3000/machines
curl.exe -s -o NUL -w "%{http_code}\n" http://localhost:3000/predictions
curl.exe -s -o NUL -w "%{http_code}\n" http://localhost:3000/alerts
curl.exe -s -o NUL -w "%{http_code}\n" http://localhost:3000/fog
curl.exe -s -o NUL -w "%{http_code}\n" http://localhost:3000/events
```
* **Résultat attendu** : Code HTTP `200` pour chaque URL sans erreur 404 Nginx.

### 6.4. Test des En-têtes de Cache et Gzip sur les Assets
```powershell
curl.exe -I -H "Accept-Encoding: gzip" http://localhost:3000/assets/index-CTXa7da0.js
```
* **Résultat attendu** : Code HTTP `200 OK`, `Content-Encoding: gzip`, `Cache-Control: public, max-age=31536000, immutable`.

---

## 7. Guide de Dépannage (Troubleshooting)

### Problème 1 : Conflit de port sur le port 3000
* **Symptôme** : Message d'erreur Docker `port is already allocated` ou `Bind for 0.0.0.0:3000 failed`.
* **Cause** : Un autre conteneur (ex. ancien conteneur de test `mp4-dashboard-test`) ou un processus local utilise le port 3000.
* **Diagnostic** :
  ```powershell
  # Lister les conteneurs occupant le port 3000
  docker ps -a --filter "publish=3000"
  ```
* **Résolution** :
  ```powershell
  # Arrêter l'ancien conteneur de test du projet MP4
  docker stop mp4-dashboard-test
  # Puis relancer Compose
  docker compose up -d
  ```

### Problème 2 : Le conteneur affiche l'état `unhealthy`
* **Symptôme** : `docker compose ps` indique `Up (unhealthy)`.
* **Diagnostic** :
  ```powershell
  docker inspect --format='{{json .State.Health}}' mp4-dashboard
  ```
* **Résolution** :
  * Vérifier que Nginx répond bien en interne sur le port 80 en exécutant :
    ```powershell
    docker exec mp4-dashboard wget -q -O - http://127.0.0.1:80/healthz
    ```
  * Consulter les logs d'erreurs Nginx :
    ```powershell
    docker exec mp4-dashboard cat /var/log/nginx/error.log
    ```

### Problème 3 : Erreur 404 lors du rechargement d'une page SPA
* **Symptôme** : L'accès à `http://localhost:3000/` fonctionne, mais actualiser `http://localhost:3000/machines` renvoie une erreur Nginx 404 Not Found.
* **Cause** : La directive `try_files` est manquante ou mal positionnée dans la configuration Nginx.
* **Résolution** :
  * S'assurer que le bloc `location /` contient bien `try_files $uri $uri/ /index.html;` dans `frontend/nginx.conf`.
  * Reconstruire l'image : `docker compose build && docker compose up -d`.

### Problème 4 : Échec lors du build `npm ci`
* **Symptôme** : Le build Docker échoue à l'étape `RUN npm ci` avec une erreur d'incompatibilité de lockfile.
* **Résolution** :
  * Vérifier la cohérence de `package-lock.json` en local dans `frontend/` avec `npm install --package-lock-only`.
  * S'assurer que `frontend/.dockerignore` n'exclut pas `package.json` ou `package-lock.json`.
