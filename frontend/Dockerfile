# ---- Build Stage ----
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
ARG BACKEND_URL=http://localhost:18080
ENV BACKEND_URL=$BACKEND_URL
ARG VITE_RESTAURANT_TIMEZONE=Asia/Tbilisi
ENV VITE_RESTAURANT_TIMEZONE=$VITE_RESTAURANT_TIMEZONE
RUN npm run build

# ---- Serve Stage ----
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

