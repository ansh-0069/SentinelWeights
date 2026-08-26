FROM node:20-alpine

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173
# dev server proxies /api to the api container (see vite.config.ts override below)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
