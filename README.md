# moz-proenergia-backend

[![Built with](https://img.shields.io/badge/Built_with-Cookiecutter_Django_Rest-F7B633.svg)](https://github.com/agconti/cookiecutter-django-rest)

Mozambique Proenergia backend.

## Prerequisites

- [Docker](https://docs.docker.com/docker-for-mac/install/) (for Docker setup)
- RabbitMQ (for Celery task processing)  
- Python 3.8+ and PostgreSQL (for local development)

## Quick Setup

### Local Development

**1. Set up Python environment:**

```bash
# Create databases
createdb proenergia
createdb proenergia_test

# Set environment variables
export DJANGO_DB_URL="postgis://user:password@localhost:5432/proenergia"
export DJANGO_SECRET_KEY="anyTextIsS3cr3t"

# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
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
DJANGO_DB_URL="postgis://postgres:postgres@localhost:5432/proenergia" \
DJANGO_SECRET_KEY="anyTextIsS3cr3t" \
celery -A proenergia worker --loglevel=info
```

**Optional - Start Celery beat for scheduled tasks:**
```bash
DJANGO_DB_URL="postgis://postgres:postgres@localhost:5432/proenergia" \
DJANGO_SECRET_KEY="anyTextIsS3cr3t" \
celery -A proenergia beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**Optional - Monitor with Flower:**
```bash
pip install flower
DJANGO_DB_URL="postgis://postgres:postgres@localhost:5432/proenergia" \
DJANGO_SECRET_KEY="anyTextIsS3cr3t" \
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

**Key environment variables:**
- `DJANGO_DB_URL` - Database connection string  
- `DJANGO_SECRET_KEY` - Django secret key
- `CELERY_BROKER_URL` - RabbitMQ connection (default: `amqp://guest:guest@localhost:5672//`)

## Available Tasks

**Hello World Task** (`hello_world_task`): Demo task with 2-second delay for testing async processing framework.

## Troubleshooting

- **Connection refused to RabbitMQ**: Check `sudo rabbitmqctl status`  
- **Tasks not executing**: Ensure Celery worker is running with proper environment variables
- **Database connection errors**: Set `DJANGO_DB_URL` when starting Celery worker
- **Settings import errors**: Ensure `DJANGO_SECRET_KEY` is set for Celery commands

**Logs:**
- Django: console output from `runserver`
- Celery: console output from worker and TaskResults in Django Admin
- Task results: Django admin → "Django Celery Results"
- Flower: http://localhost:5555 (if running)

## API Documentation

- Swagger UI: http://localhost:8000/api/v1/docs/
- API Schema: http://localhost:8000/api/v1/schema/