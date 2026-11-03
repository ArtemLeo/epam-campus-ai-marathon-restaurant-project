SHELL := /bin/sh
.DEFAULT_GOAL := help
PYTHON ?= python3
CLOUD_PYTHON := .venv-cloud/bin/python
.PHONY: help up down restart reset logs logs-backend logs-frontend status health seed test test-backend test-frontend lint lint-backend lint-frontend typecheck build check e2e e2e-api e2e-ui e2e-clean shell-backend shell-frontend aws-tools aws-configure aws-init aws-deploy aws-update aws-admin aws-seed aws-frontend aws-status aws-destroy terraform-check
.PHONY: frontend-image backend-test-image demo-photos

help: ## Show commands
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "make %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Build and start; wait until the app is ready
	docker compose up --build --wait --wait-timeout 180
	docker compose ps

down: ## Stop containers; keep data and uploaded photos
	docker compose down

restart: ## Rebuild/restart without deleting data
	docker compose up --build --wait --wait-timeout 180

reset: ## Delete LOCAL data and rebuild a clean demo (asks before deleting)
	@printf 'Delete all local restaurant data and photos? Type RESET: '; read answer; test "$$answer" = RESET
	docker compose down --volumes
	$(MAKE) up

logs: ## Follow all logs (Ctrl+C exits)
	docker compose logs -f
logs-backend: ## Follow backend logs
	docker compose logs -f backend
logs-frontend: ## Follow frontend logs
	docker compose logs -f frontend
status: ## Show containers and readiness
	docker compose ps
health: ## Verify the backend and frontend are reachable
	docker compose exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/health').read().decode())"
	docker compose exec -T frontend node -e "fetch('http://localhost:4200').then(r=>{if(!r.ok)process.exit(1);console.log('Frontend OK')}).catch(()=>process.exit(1))"
seed: ## Add missing demo data; preserve existing edits/passwords
	docker compose exec -T backend python -m local.seed_local

demo-photos: ## Upgrade existing demo dish photos; keep custom uploads and other data
	docker compose exec -T backend python -m local.seed_local --refresh-dish-photos

shell-backend: ## Open backend shell
	docker compose exec backend sh
shell-frontend: ## Open frontend shell
	docker compose exec frontend sh

test: test-backend test-frontend ## Run unit tests (errors fail the command)
backend-test-image:
	docker compose build backend-tests
frontend-image:
	docker compose build frontend
test-backend: backend-test-image ## Run isolated backend tests with moto
	docker compose run --rm --no-deps backend-tests
test-frontend: frontend-image ## Run frontend unit tests
	docker compose run --rm --no-deps frontend npm test
lint: lint-backend lint-frontend ## Run all code style checks
lint-backend: backend-test-image ## Check all Python source, local adapter and tests
	docker compose run --rm --no-deps -v "$(CURDIR):/workspace:ro" -w /workspace backend-tests ruff check --no-cache backend
	docker compose run --rm --no-deps -v "$(CURDIR):/workspace:ro" -w /workspace backend-tests ruff format --check --no-cache backend
lint-frontend: frontend-image ## Check frontend code style
	docker compose run --rm --no-deps frontend npm run lint
typecheck: frontend-image ## Check TypeScript
	docker compose run --rm --no-deps frontend npm run type-check
build: frontend-image ## Verify frontend production build in Docker
	docker compose run --rm --no-deps -e BACKEND_URL=http://localhost:18080 frontend npm run build
check: lint typecheck test build ## Full local static/unit/build checks

e2e-clean: ## Remove only local AQA acceptance-test records and containers
	@docker compose exec -T backend python -m local.seed_local --cleanup-aqa
	@docker rm -f restaurant-e2e-api restaurant-e2e-ui >/dev/null 2>&1 || true
e2e-api: health ## Run API acceptance tests in a disposable lightweight Docker container
	@set -e; cleanup() { $(MAKE) --no-print-directory e2e-clean >/dev/null 2>&1 || true; }; trap cleanup EXIT INT TERM; cleanup; docker compose build e2e-api; docker compose run --rm --no-deps --name restaurant-e2e-api e2e-api
e2e-ui: health ## Run Chromium browser acceptance tests in a disposable Docker container
	@set -e; cleanup() { $(MAKE) --no-print-directory e2e-clean >/dev/null 2>&1 || true; }; trap cleanup EXIT INT TERM; cleanup; docker compose build e2e-ui; docker compose run --rm --no-deps --name restaurant-e2e-ui e2e-ui
e2e: e2e-api e2e-ui ## Run all API and Chromium browser acceptance tests in Docker

aws-tools: ## Install isolated AWS deployment tooling (Python 3.12+)
	$(PYTHON) -m venv .venv-cloud
	$(CLOUD_PYTHON) -m pip install "aws-syndicate==1.21.3"

aws-configure: ## Generate portable cloud config using the selected AWS account
	$(CLOUD_PYTHON) backend/scripts/cloud.py configure
aws-init: ## Create Terraform-owned AWS infrastructure (interactive plan/apply)
	$(CLOUD_PYTHON) backend/scripts/cloud.py init
aws-deploy: test-backend ## First deployment of Syndicate-owned backend resources
	$(CLOUD_PYTHON) backend/scripts/cloud.py deploy
aws-update: test-backend ## Update an existing backend deployment
	$(CLOUD_PYTHON) backend/scripts/cloud.py update
aws-admin: ## Create the first AWS administrator (asks for email/password)
	$(CLOUD_PYTHON) backend/scripts/cloud.py admin
aws-seed: ## Add demo data to AWS only with explicit DEMO_PASSWORD and API_URL
	$(CLOUD_PYTHON) backend/scripts/cloud.py seed
aws-frontend: ## Build/upload frontend; invalidate the correct CloudFront distribution
	$(CLOUD_PYTHON) backend/scripts/cloud.py frontend
aws-status: ## Inspect AWS outputs without changing resources
	terraform -chdir=terraform output
aws-destroy: ## Confirm account, then delete application resources from both tools
	$(CLOUD_PYTHON) backend/scripts/cloud.py destroy
terraform-check: ## Validate Terraform configuration without deploying
	terraform -chdir=terraform init -backend=false
	terraform -chdir=terraform validate
	terraform -chdir=terraform fmt -check -recursive
