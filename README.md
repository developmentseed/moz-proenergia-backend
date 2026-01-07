# moz-proenergia-backend

[![Built with](https://img.shields.io/badge/Built_with-Cookiecutter_Django_Rest-F7B633.svg)](https://github.com/agconti/cookiecutter-django-rest)

Mozambique Proenergia backend with async task processing capabilities.

# Prerequisites

- [Docker](https://docs.docker.com/docker-for-mac/install/)
- [RabbitMQ](https://www.rabbitmq.com/download.html) (for local development with Celery)
- Python 3.8+ (for local development without Docker)

# Local Development

## Option 1: Docker Development

Start the dev server for local development:
```bash
docker-compose up
```

Run a command inside the docker container:
```bash
docker-compose run --rm web [command]
```

## Option 2: Local Development without Docker

### 1. Set up the Python environment

- Create a PostgreSQL database named `proenergia`, and another one named `proenergia_test`
- Set the environment variables:

```bash
export DJANGO_DB_URL="postgis://user:password@localhost:5432/proenergia"
export DJANGO_SECRET_KEY="anyTextIsS3cr3t"
```

- Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

- Install the python dependencies:
```bash
pip install -r requirements.txt
```

GeoDjango may require some additional libraries to be installed in your system, check the [documentation](https://docs.djangoproject.com/en/5.2/ref/contrib/gis/install/#installation) or a Docker file in this repository.

### 2. Set up RabbitMQ Message Broker (for Celery tasks)

#### macOS (using Homebrew)
```bash
# Install RabbitMQ
brew install rabbitmq

# Add RabbitMQ to PATH (add to your shell profile)
export PATH=$PATH:/usr/local/sbin

# Start RabbitMQ server
sudo rabbitmq-server -detached

# Check status
sudo rabbitmqctl status
```

#### Ubuntu/Debian
```bash
# Install Erlang and RabbitMQ
sudo apt-get update
sudo apt-get install -y erlang
sudo apt-get install rabbitmq-server

# Enable and start RabbitMQ service
sudo systemctl enable rabbitmq-server
sudo systemctl start rabbitmq-server

# Check status
sudo systemctl status rabbitmq-server
```

#### Windows
```bash
# Download and install from https://www.rabbitmq.com/install-windows.html
# Or using Chocolatey:
choco install rabbitmq

# Start the service
rabbitmq-service start
```

### 3. Run Database Migrations

```bash
# Run migrations (including Celery-related tables)
python manage.py migrate
```

### 4. Run the application

- To run the server, use `./manage.py runserver`
- You can create a super user with `./manage.py createsuperuser`

## Celery Task Processing

### Starting the Celery Worker

In a separate terminal, start the Celery worker:

```bash
# Activate virtual environment
source venv/bin/activate

# Start Celery worker
celery -A proenergia worker --loglevel=info

# For development with auto-reload (requires watchdog: pip install watchdog)
celery -A proenergia worker --loglevel=info --pool=solo
```

### Starting Celery Beat (for scheduled tasks)

In another terminal, start the Celery beat scheduler:

```bash
# Activate virtual environment
source venv/bin/activate

# Start Celery beat
celery -A proenergia beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Monitoring Tasks

#### Using Flower (Web-based monitoring)
```bash
# Install Flower
pip install flower

# Start Flower
celery -A proenergia flower --address=127.0.0.1 --port=5555

# Access at http://localhost:5555
```

#### Using Django Admin
- Access the Django admin at http://localhost:8000/admin/
- Navigate to "Django Celery Results" → "Task results" to view task history
- Navigate to "Django Celery Beat" → "Periodic tasks" to manage scheduled tasks

**Note**: We use `django-celery-results` for result storage and `django-celery-beat` for scheduled tasks. Flower provides the most comprehensive monitoring interface.

## Testing Async Tasks

### Quick Test Endpoints

The application provides simple endpoints for testing Celery integration (no authentication required):

```bash
# Test hello world task
curl -X POST http://localhost:8000/api/v1/tasks/hello/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice"}'

# Check task status (replace <task_id> with actual task ID from above response)
curl http://localhost:8000/api/v1/tasks/status/<task_id>/

# List recent tasks
curl http://localhost:8000/api/v1/tasks/list/

# Get endpoint information
curl http://localhost:8000/api/v1/tasks/hello/
```

## Running Tests

To run the tests, use:

```bash
DJANGO_DB_URL="postgis://user:password@localhost:5432/proenergia_test" ./manage.py test --settings=proenergia.config.local
```

### Unit Tests for Tasks
```bash
# Run all tests
python manage.py test

# Run only Celery task tests
python manage.py test proenergia.tasks.test_tasks

# Run with pytest
pytest proenergia/tasks/test_tasks.py -v

# Run specific test class
pytest proenergia/tasks/test_tasks.py::TestHelloWorldTask -v
```

### Integration Tests
```bash
# Test with actual Celery worker (requires running worker)
pytest proenergia/tasks/test_tasks.py::TestTaskAsync -v
```

## Configuration

### Environment Variables

Set these environment variables for configuration:

```bash
# Celery broker URL (default: amqp://guest:guest@localhost:5672//)
export CELERY_BROKER_URL="amqp://guest:guest@localhost:5672//"

# Django settings
export DJANGO_SETTINGS_MODULE="proenergia.config.local"
export DJANGO_SECRET_KEY="your-secret-key"
export DJANGO_DEBUG="true"

# Database URL
export DJANGO_DB_URL="postgis://postgres:postgres@localhost:5432/proenergia"
```

### Celery Configuration

Key Celery settings are configured in `proenergia/config/common.py`:

- **Broker**: RabbitMQ (configurable via `CELERY_BROKER_URL`)
- **Result Backend**: Django database (`django-db`)
- **Serialization**: JSON
- **Task Routes**: Tasks routed to `proenergia` queue
- **Result Retention**: 1 day for successful tasks

## Development Workflow

1. **Start RabbitMQ**: `sudo rabbitmq-server -detached`
2. **Start Database**: Set up PostgreSQL locally or use Docker
3. **Run Migrations**: `python manage.py migrate`
4. **Start Django**: `python manage.py runserver`
5. **Start Celery Worker**: `celery -A proenergia worker --loglevel=info`
6. **Optional - Start Flower**: `celery -A proenergia flower`

## Available Task Types

The system includes one example task to demonstrate the async processing framework:

1. **Hello World Task** (`hello_world_task`): Simple greeting task with 2-second delay
   - Demonstrates basic async task execution
   - Includes proper logging
   - Returns structured result data
   - Perfect foundation for adding new task types

## Troubleshooting

### Common Issues

1. **"No module named 'celery'"**: Ensure virtual environment is activated and dependencies installed
2. **Connection refused to RabbitMQ**: Check that RabbitMQ server is running
3. **Tasks not executing**: Ensure Celery worker is running and connected to the same broker
4. **Database connection errors**: Check PostgreSQL is running and connection settings are correct

### Logs

- **Django logs**: Check console output from `runserver`
- **Celery worker logs**: Check console output from worker process  
- **RabbitMQ logs**: Check RabbitMQ management interface or logs
- **Task results**: View in Django admin under "Django Celery Results" → "Task results"
- **Flower monitoring**: Real-time task monitoring at http://localhost:5555 (if Flower is running)

## Production Considerations

For production deployment:

1. Use a robust message broker setup (RabbitMQ cluster)
2. Configure proper logging and monitoring
3. Set up process management (systemd, supervisor, etc.)
4. Configure result backend retention policies
5. Set up alerts for failed tasks
6. Consider using multiple worker processes/machines
7. Implement proper error handling and retries

## API Documentation

- Swagger UI: http://localhost:8000/api/v1/docs/
- API Schema: http://localhost:8000/api/v1/schema/