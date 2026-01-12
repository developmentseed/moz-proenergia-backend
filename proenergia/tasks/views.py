import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from celery.result import AsyncResult
from django_celery_results.models import TaskResult

import proenergia.celery_tasks as celery_tasks

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST", "GET"])
def trigger_hello_world(request):
    """
    Trigger a hello world task (no authentication required).
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else {}
            name = data.get('name', 'World')

            task = celery_tasks.hello_world_task.delay(name)
            logger.info(f"Started hello_world_task with ID: {task.id}")

            return JsonResponse({
                'task_id': task.id,
                'status': 'started',
                'message': f'Hello world task started for: {name}',
                'check_url': f'/api/v1/tasks/status/{task.id}/'
            })

        except Exception as e:
            logger.error(f"Error starting hello_world_task: {str(e)}")
            return JsonResponse({'error': 'Failed to start task'}, status=500)

    else:  # GET request
        return JsonResponse({
            'message': 'POST to this endpoint to trigger a hello world task',
            'example_payload': {'name': 'Alice'},
            'endpoints': {
                'trigger_hello': '/api/v1/tasks/hello/',
                'check_status': '/api/v1/tasks/status/<task_id>/',
                'list_tasks': '/api/v1/tasks/list/'
            }
        })


@csrf_exempt
def check_task_status(request, task_id):
    """
    Check the status of a task (no authentication required).
    """
    try:
        result = AsyncResult(task_id)

        response_data = {
            'task_id': task_id,
            'status': result.status,
            'ready': result.ready(),
            'successful': result.successful() if result.ready() else None,
        }

        if result.ready():
            if result.successful():
                response_data['result'] = result.result
            else:
                response_data['error'] = str(result.result)

        # Get info from django-celery-results if available
        try:
            task_result = TaskResult.objects.get(task_id=task_id)
            response_data['date_created'] = task_result.date_created
            response_data['date_done'] = task_result.date_done
        except TaskResult.DoesNotExist:
            pass

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error checking task {task_id}: {str(e)}")
        return JsonResponse({'error': 'Failed to check task status'}, status=500)


@csrf_exempt
def list_recent_tasks(request):
    """
    List recent tasks from django-celery-results (no authentication required).
    """
    try:
        limit = min(int(request.GET.get('limit', 20)), 100)
        tasks = TaskResult.objects.order_by('-date_created')[:limit]

        task_data = []
        for task in tasks:
            task_data.append({
                'task_id': task.task_id,
                'task_name': task.task_name,
                'status': task.status,
                'date_created': task.date_created,
                'date_done': task.date_done,
                'result': task.result,
            })

        return JsonResponse({
            'tasks': task_data,
            'count': len(task_data)
        })

    except Exception as e:
        logger.error(f"Error listing tasks: {str(e)}")
        return JsonResponse({'error': 'Failed to list tasks'}, status=500)
