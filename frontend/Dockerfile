FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build
EXPOSE 3000
CMD ["sh", "-c", "mkdir -p public && printf 'window.__MOVIEAI_CONFIG__={API_BASE_URL:\"%s\"};\\n' \"${NEXT_PUBLIC_API_URL:-http://localhost:8000}\" > public/runtime-config.js && npm run start -- --hostname 0.0.0.0 --port ${PORT:-3000}"]
