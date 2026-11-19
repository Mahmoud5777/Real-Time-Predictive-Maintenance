# ==========================================
# Étape 1 : Construction de l'application React
# ==========================================
FROM node:20-alpine AS builder

WORKDIR /app

# Arguments de build (valeurs par défaut en mode standalone mock)
ARG VITE_API_BASE_URL=""
ARG VITE_DATA_SOURCE="mock"

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_DATA_SOURCE=$VITE_DATA_SOURCE

# Installation des dépendances via package-lock.json
COPY package*.json ./
RUN npm ci

# Copie du code source et compilation
COPY . .
RUN npm run build

# ==========================================
# Étape 2 : Image d'exécution légère Nginx
# ==========================================
FROM nginx:alpine AS runner

LABEL maintainer="Équipe DevOps MP4" \
      description="Industrial Monitoring Dashboard Frontend (React 19, Vite, Nginx)" \
      version="1.0.0"

# Remplacement de la configuration par défaut
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copie des artefacts statiques compilés
COPY --from=builder /app/dist /usr/share/nginx/html

# Port HTTP interne
EXPOSE 80

# Healthcheck périodique via l'endpoint dédié /healthz
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:80/healthz || exit 1

# Démarrage de Nginx en avant-plan
CMD ["nginx", "-g", "daemon off;"]
