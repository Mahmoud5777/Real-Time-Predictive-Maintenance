# Étape 1 : construire l'application React
FROM node:22-alpine AS builder

WORKDIR /app

# Copier les fichiers de dépendances
COPY package*.json ./

# Installer les dépendances
RUN npm ci

# Copier le code source
COPY . .

# Compiler React avec Vite
RUN npm run build


# Étape 2 : servir l'application avec Nginx
FROM nginx:alpine

# Supprimer la configuration Nginx par défaut
RUN rm /etc/nginx/conf.d/default.conf

# Ajouter notre configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copier le frontend compilé
COPY --from=builder /app/dist /usr/share/nginx/html

# Port HTTP
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]