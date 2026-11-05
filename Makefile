# FinScout — common commands
# Pick: `make help` to list everything.

PYTHON ?= python3.12
VENV   ?= venv
PIP     = $(VENV)/bin/pip
PY      = $(VENV)/bin/python
ST      = $(VENV)/bin/streamlit

# Default universe + limit for the seed; override on the command line:
#   make seed LIMIT=100 UNIVERSE=nifty100
LIMIT    ?= 20
UNIVERSE ?= nifty50

.DEFAULT_GOAL := help

help:                        ## Show this help
	@awk 'BEGIN {FS=":.*##"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup:                       ## Create venv and install deps
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@test -f .env || cp .env.example .env
	@echo ""
	@echo "  ✓ venv ready. Edit .env, then: make db && make seed && make ui"

db:                          ## Start only the Postgres container
	docker compose up -d db
	@echo "  ✓ Postgres up on localhost:5432"

seed:                        ## Ingest + score $(LIMIT) tickers from $(UNIVERSE)
	POSTGRES_HOST=localhost $(PY) -m app.jobs.nightly $(LIMIT) $(UNIVERSE)

why-now:                     ## LLM 'Why Now' for the top 10 scoring tickers
	POSTGRES_HOST=localhost $(PY) -m app.jobs.monday_feed

ui:                          ## Launch the Streamlit UI on :8501
	POSTGRES_HOST=localhost $(ST) run app/main.py --server.port 8501

ui-stop:                     ## Kill any running streamlit on this machine
	-pkill -9 -f "streamlit run" 2>/dev/null; true

docker-up:                   ## docker compose up --build (app + scheduler + db)
	docker compose up --build

docker-down:                 ## docker compose down (data persists in pgdata volume)
	docker compose down

docker-nuke:                 ## docker compose down -v (deletes Postgres data too)
	docker compose down -v

shell:                       ## Open a psql shell on the db container
	docker compose exec db psql -U finscout -d finscout

test:                        ## Run the test suite (placeholder)
	@echo "No tests yet. Add them under tests/."

clean:                       ## Remove venv and local caches
	rm -rf $(VENV) __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

package:                     ## Build a shareable zip in dist/
	mkdir -p dist
	zip -r dist/finscout.zip . \
		-x '*.git/*' -x 'venv/*' -x '__pycache__/*' -x '*/__pycache__/*' \
		-x '.env' -x 'dist/*' -x '*.DS_Store' -x 'pgdata/*' -x 'interview-prep.md' \
		-x 'docs/screenshots/*'
	@ls -lh dist/finscout.zip
	@echo ""
	@echo "  ✓ dist/finscout.zip ready to share."

.PHONY: help setup db seed why-now ui ui-stop docker-up docker-down docker-nuke shell test clean package
