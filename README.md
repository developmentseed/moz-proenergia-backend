# Plataforma Integrada de Electrificação de Moçambique - PIEM

[![Built with](https://img.shields.io/badge/Built_with-Cookiecutter_Django_Rest-F7B633.svg)](https://github.com/agconti/cookiecutter-django-rest)

Plataforma Integrada de Electrificação de Moçambique (PIEM) backend.

## Prerequisites

- [Docker](https://docs.docker.com/docker-for-mac/install/) (for Docker setup)
- [RabbitMQ](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/rabbitmq.html) (for Celery task processing)
- [Tippecanoe](https://github.com/felt/tippecanoe) (for PMTiles generation)
- [gdal-bin](https://gdal.org/en/stable/download.html#binaries) (for file conversion)
- Python 3.8+ and PostgreSQL (for local development)

## Quick Setup

### Local Development

**1. Set up Python environment:**

```bash
# Create databases
createdb proenergia
createdb proenergia_test

# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up environment variables (choose one method):
# Method 1: Copy and configure .env file (recommended)
cp .env.example .env
# Edit .env file with your database credentials

# Method 2: Export variables directly
export DJANGO_DB_URL="postgis://user:password@localhost:5432/proenergia"
export DJANGO_SECRET_KEY="anyTextIsS3cr3t"
```

**2. Install RabbitMQ:**

*macOS:*
```bash
brew install rabbitmq
export PATH=$PATH:/usr/local/sbin
sudo rabbitmq-server -detached
```

*Ubuntu/Debian:*
```bash
sudo apt-get update && sudo apt-get install -y rabbitmq-server
sudo systemctl enable rabbitmq-server
sudo systemctl start rabbitmq-server
```

**3. Run migrations and start server:**

```bash
python manage.py migrate
python manage.py runserver
```

## Celery Task Processing

**Start Celery worker** (separate terminal):
```bash
source venv/bin/activate
# If using .env file, variables are loaded automatically
celery -A proenergia worker --loglevel=info
```

**Optional - Start Celery beat for scheduled tasks:**
```bash
celery -A proenergia beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**Optional - Monitor with Flower:**
```bash
pip install flower
celery -A proenergia flower --address=127.0.0.1 --port=5555
```
Access at http://localhost:5555

## Testing Celery

**Test endpoints:**
```bash
# Test hello world task
curl -X POST http://localhost:8000/api/v1/tasks/hello/ -H "Content-Type: application/json" -d '{"name": "Alice"}'

# Check task status (use task_id from above)
curl http://localhost:8000/api/v1/tasks/status/<task_id>/

# List recent tasks  
curl http://localhost:8000/api/v1/tasks/list/
```

**Run tests:**
```bash
# All tests
python manage.py test

# Task tests only
python manage.py test proenergia.tasks.test_tasks

# With pytest
pytest proenergia/tasks/test_tasks.py -v
```

## Configuration

### Environment Variables

Environment variables can be configured in two ways:

1. **Using a `.env` file** (recommended for local development):
   - Copy `.env.example` to `.env` in the project root
   - Edit the values in `.env` file
   - Variables are automatically loaded when running Django or Celery commands

2. **Using export commands** (takes precedence over `.env` file):
   - Export variables in your shell before running commands
   - Useful for CI/CD or production environments

**Key environment variables:**
- `DJANGO_DB_URL` - Database connection string  
- `DJANGO_SECRET_KEY` - Django secret key
- `CELERY_BROKER_URL` - RabbitMQ connection (default: `amqp://guest:guest@localhost:5672//`)
- `DJANGO_DEBUG` - Debug mode (default: `False`)

See `.env.example` for a complete list of available variables.

## Available Tasks

**Hello World Task** (`hello_world_task`): Demo task with 2-second delay for testing async processing framework.

## Troubleshooting

- **Connection refused to RabbitMQ**: Check `sudo rabbitmqctl status`  
- **Tasks not executing**: Ensure Celery worker is running with proper environment variables
- **Database connection errors**: Check `DJANGO_DB_URL` in your `.env` file or environment
- **Settings import errors**: Ensure `DJANGO_SECRET_KEY` is set in `.env` file or environment

**Logs:**
- Django: console output from `runserver`
- Celery: console output from worker and TaskResults in Django Admin
- Task results: Django admin → "Django Celery Results"
- Flower: http://localhost:5555 (if running)

## API Documentation

- Swagger UI: http://localhost:8000/api/v1/docs/
- API Schema: http://localhost:8000/api/v1/schema/
