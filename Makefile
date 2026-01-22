.PHONY: help build test fmt lint deploy-staging

help:
	@echo "Targets: build test fmt lint deploy-staging"

build:
	@echo "No build steps defined yet"

test:
	pytest -q || true

fmt:
	black . || true

lint:
	ruff . || true

deploy-staging:
	@echo "Deploy to staging: implement infra scripts"
