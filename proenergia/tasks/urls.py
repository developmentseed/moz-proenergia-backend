from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Task management endpoints (no authentication required)
    path('hello/', views.trigger_hello_world, name='trigger_hello_world'),
    path('status/<str:task_id>/', views.check_task_status, name='check_task_status'),
    path('list/', views.list_recent_tasks, name='list_recent_tasks'),
]