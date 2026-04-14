.PHONY: help setup up down dev logs test clean pull-model submodules

GREEN  := \033[0;32m
YELLOW := \033[0;33m
CYAN   := \033[0;36m
RESET  := \033[0m

help: ## Show this help
	@echo ""
	@echo "$(CYAN)Voice Insight Engine$(RESET)"
	@echo "────────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(RESET) %s\n", $$1, $$2}'
	@echo ""

setup: ## First-time setup: init submodules + copy .env
	@echo "$(CYAN)→ Initializing submodules...$(RESET)"
	git submodule update --init --recursive
	@echo "$(CYAN)→ Copying .env.example to .env...$(RESET)"
	@[ -f .env ] || cp .env.example .env
	@echo "$(GREEN)✓ Setup complete. Edit .env with your API keys.$(RESET)"

submodules: ## Update all submodules to latest
	@echo "$(CYAN)→ Pulling submodule updates...$(RESET)"
	git submodule update --remote --merge
	@echo "$(GREEN)✓ Submodules updated$(RESET)"

up: ## Start all services (prod mode)
	docker compose -f docker-compose.yml up --build -d
	@echo "$(GREEN)✓ Services running:$(RESET)"
	@echo "   API  → http://localhost:8000"
	@echo "   Docs → http://localhost:8000/docs"
	@echo "   UI   → http://localhost:3000"

dev: ## Start backend + ollama only (run frontend locally)
	docker compose up --build -d
	@echo "$(GREEN)✓ Dev services running:$(RESET)"
	@echo "   API  → http://localhost:8000"
	@echo "   Docs → http://localhost:8000/docs"
	@echo "$(YELLOW)   Frontend: cd frontend && npm run dev$(RESET)"

down: ## Stop all services
	docker compose down

logs: ## Follow all service logs
	docker compose logs -f

logs-backend: ## Follow backend logs only
	docker compose logs -f backend

frontend-install: ## Install frontend dependencies
	cd frontend && npm install

frontend-dev: ## Run frontend dev server locally
	cd frontend && npm run dev

frontend-build: ## Build frontend for production
	cd frontend && npm run build

test: ## Run all backend tests
	cd backend && pip install pytest pytest-asyncio httpx --quiet && \
		pytest -v --tb=short

test-cov: ## Run tests with coverage report
	cd backend && pip install pytest pytest-asyncio httpx pytest-cov --quiet && \
		pytest --cov=app --cov-report=term-missing --cov-report=html -v

pull-model: ## Pull an Ollama model. Usage: make pull-model MODEL=mistral
	@[ -n "$(MODEL)" ] || (echo "Usage: make pull-model MODEL=mistral" && exit 1)
	curl -s -X POST "http://localhost:8000/api/v1/ollama/pull?model=$(MODEL)"
	@echo "\n$(GREEN)✓ Model $(MODEL) pulled$(RESET)"

list-models: ## List available Ollama models
	curl -s http://localhost:8000/api/v1/ollama/models | python3 -m json.tool

status: ## Check provider status
	curl -s http://localhost:8000/api/v1/status | python3 -m json.tool

clean: ## Remove containers and volumes
	docker compose down -v --remove-orphans
	@echo "$(GREEN)✓ Cleaned$(RESET)"

clean-all: clean ## Remove containers, volumes AND ollama model cache
	docker volume rm vie-ollama-data vie-whisper-cache 2>/dev/null || true
	@echo "$(GREEN)✓ Full clean done$(RESET)"
