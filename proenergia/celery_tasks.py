import time
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def hello_world_task(self, name="World"):
    """
    A simple hello world task for testing Celery integration.
    
    Args:
        name (str): Name to greet, defaults to "World"
        
    Returns:
        dict: Task result with greeting message and metadata
    """
    task_id = self.request.id
    logger.info(f"Starting hello_world_task with ID: {task_id}, greeting: {name}")
    
    try:
        # Simulate some work
        time.sleep(2)
        
        result = {
            "message": f"Hello, {name}!",
            "task_id": task_id,
            "status": "success",
            "timestamp": time.time()
        }
        
        logger.info(f"Completed hello_world_task {task_id} successfully")
        return result
        
    except Exception as exc:
        logger.error(f"hello_world_task {task_id} failed: {str(exc)}")
        raise