FROM node:22-slim AS build
WORKDIR /app
COPY framecraft-agent/package*.json ./
RUN npm install
COPY framecraft-agent ./
RUN npm run build

FROM nginx:alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
