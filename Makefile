.PHONY: dev backend frontend up seed

dev:
	docker compose up --build

up:
	docker compose up --build

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

seed:
	python scripts/seed_project.py
