
BACKEND_DOCKER_IMAGE=personal-fin-hub-api
BACKEND_VERSION=$(shell cat backend/version.txt)
BACKEND_DOCKER_CONTAINER=fin-hub-api-test

FRONTEND_DOCKER_IMAGE_DEV=node:24-alpine

FRONTEND_DOCKER_IMAGE=personal-fin-hub-frontend
FRONTEND_VERSION=$(shell cat frontend/version.txt)
FRONTEND_DOCKER_CONTAINER=fin-hub-frontend-test

dev-run-backend:
	cd backend && \
	python3.12 -m venv .venv && \
	source .venv/bin/activate && \
	pip install --upgrade pip && \
	pip install -r requirements.txt && \
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

docker-build-backend:
	cd backend && \
	docker build -t $(BACKEND_DOCKER_IMAGE):$(BACKEND_VERSION) .

docker-run-backend:
	docker run -d -p 8000:8000 --name $(BACKEND_DOCKER_CONTAINER) $(BACKEND_DOCKER_IMAGE):$(BACKEND_VERSION)

docker-stop-backend:
	docker stop $(BACKEND_DOCKER_CONTAINER) && docker rm $(BACKEND_DOCKER_CONTAINER)

#dev-docker-build-frontend:
#	cd frontend && \
#	docker build -t $(FRONTEND_DOCKER_IMAGE):$(FRONTEND_VERSION) .

dev-run-frontend:
	docker run -d -p 5173:5173 \
	-v $(shell pwd)/frontend/:/app \
	-v /app/node_modules \
	-e NODE_ENV=development \
	--name $(FRONTEND_DOCKER_CONTAINER) \
	$(FRONTEND_DOCKER_IMAGE_DEV) sh -c "cd app && npm ci || npm install && npm run dev -- --host 0.0.0.0"

dev-frontend-logs:
	docker logs -f $(FRONTEND_DOCKER_CONTAINER)

dev-stop-frontend:
	-docker stop $(FRONTEND_DOCKER_CONTAINER)
	-docker rm $(FRONTEND_DOCKER_CONTAINER)