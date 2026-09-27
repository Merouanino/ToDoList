## Livrable ToDoList 
[![CI](https://github.com/Merouanino/ToDoList/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Merouanino/ToDoList/actions/workflows/ci.yml)
[![CD](https://github.com/Merouanino/ToDoList/actions/workflows/cd.yml/badge.svg)](https://github.com/Merouanino/ToDoList/actions/workflows/cd.yml)

API de ToDoList minimaliste afin de tester une chaîne DevOps.

## Architecture
- Développement local sur `Dev`
	- Push ou PR déclenche la CI : lint, tests, build et check `ci-ok`
	- Après validation de la CI sur `main`, la CD construit et publie l'image
- Publication sur GHCR avec les tags `latest`, SHA et semver
- Déploiement de l'image sur le runner self-hosted
	- Application sur le port 8080
	- Redis pour le stockage
- Prometheus collecte les métriques et déclenche les alertes

## Services
APP: `ghcr.io/merouanio/todolist`
REDIS: `redis:7.4-alpine`
PROMETHEUS: `prom/prometheus:v2.55.1`
Une API flask servie par gunicorn, un stockage persistent REDIS et la collecte des métriques Prometheus

## Run
```bash
git clone https://github.com/Merouanino/ToDoList.git
cd ToDoList
docker compose up -d --build
```
## URLs pertinentes
http://localhost:5000/health pour l'état de l'app et REDIS
http://localhost:9090 pour la target prometheus et les alertes
```bash
curl -X POST http://localhost:5000/todos -H "Content-Type: application/json" -d '{"title":"Première tâche"}'
curl http://localhost:5000/todos
```
## Tests
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-local.txt
docker run -d --name redis-dev -p 6379:6379 redis:7-alpine
pytest -v --cov=app
flake8 && yamllint --strict .
```
## CI/CD
Chaque changement sur MAIN passe par une branche courte et un PR squashed. 
Ruleset main: PR obligatoire et check `ci-ok` vert

## Actions CI
- Workflow : `.github/workflows/ci.yml`, déclenché sur PR ou push vers `main`
- Lint : flake8, yamllint et promtool
- Tests : Python 3.11 et Python 3.12
- Build et vérification de l'utilisateur non-root
- Check final : `ci-ok`

## Actions CD
- Workflow : `.github/workflows/cd.yml`, déclenché après une CI verte sur `main` ou manuellement
- Build et push : tags `latest`, SHA court immuable pour rollback et semver provenant du tag Git

Déploiement sur le runner WSL self-hosted avec le label `todo-deploy`, dans l'environnement `production` (restreint à `main`) :
1. Lecture de la version en production
2. `docker compose pull` puis `up -d --no-build` de l'image
3. Vérification de `/health` et comparaison de `/version` au SHA attendu
4. En cas d'échec, rollback et redémarrage sur le SHA précédent

## Production
Compose `todo-prod`, app sur 8080 et Prometheus sur 9091

## Observabilité
Metrics: `http_requests_total` - `http_request_duration_seconds` - `app_build_info` 

## Alertes
`Erreur 503` firing si 503 / total > 5 % avec une fenêtre de 2mins for 1min - Critical
`HighLatencyP95` firing si p95 de la latence > 500 ms avec une fenêtre de 2min for 2min - Warning
Scraping chaque 15s donc 8 intervals de mesures

## Best Practice
- GitHub Token éphémère pour ghcr.io => pas de secret stocké
- Permissions explicitées dans chaque workflow
- Image non root avec vérification
- Runner Self-Hosted réservé au déploiement
- CD reservé au push sur Main
