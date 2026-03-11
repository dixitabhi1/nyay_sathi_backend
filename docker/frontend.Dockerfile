FROM node:20-alpine AS builder

WORKDIR /app
COPY frontend/package.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html /app/
COPY frontend/src /app/src
ARG VITE_API_URL=http://localhost:8000/api/v1
ENV VITE_API_URL=${VITE_API_URL}
RUN npm install
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80

