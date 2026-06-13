FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Since we want to proxy API requests in development, we will just use `npm run dev`
# with host 0.0.0.0. In a real production deployment we would build and serve via Nginx.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
