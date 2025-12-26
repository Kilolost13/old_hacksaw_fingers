# Makefile - helper targets for QA and quick dev guards
.PHONY: quality test-frontend build-frontend test-backend ci

quality:
	@echo "Running full quality checks..."
	./scripts/run_quality_checks.sh all

ci:
	@echo "Running local CI checks for front-end"
	cd "frontend/kilo-react-frontend" && npm run ci-local

test-frontend:
	cd "frontend/kilo-react-frontend" && npm test -- --watchAll=false --silent

build-frontend:
	cd "frontend/kilo-react-frontend" && npm run build --silent

test-backend:
	pytest -q
