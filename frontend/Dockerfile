FROM node:24-alpine

WORKDIR /app

# Copy only package files first for fast layer caching
COPY package*.json ./

# Install dependencies (use ci for reproducible installs if package-lock exists)
#RUN npm ci --silent || npm install --silent
RUN npm ci || npm install

# Copy the rest of the frontend source
COPY . .

EXPOSE 5173

# Run Vite in dev mode, exposed to 0.0.0.0 so host can access it
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
