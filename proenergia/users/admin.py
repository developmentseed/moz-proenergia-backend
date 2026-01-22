from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    SolarSchedule,
)
from django_celery_results.models import GroupResult, TaskResult
from rest_framework.authtoken.models import TokenProxy
from unfold.admin import ModelAdmin

from .models import User


@admin.register(User)
class UserAdmin(UserAdmin, ModelAdmin):
    pass


# Remove some models from the Admin interface
admin.site.unregister(TokenProxy)
admin.site.unregister(TaskResult)
admin.site.unregister(GroupResult)
admin.site.unregister(PeriodicTask)
admin.site.unregister(ClockedSchedule)
admin.site.unregister(CrontabSchedule)
admin.site.unregister(IntervalSchedule)
admin.site.unregister(SolarSchedule)
