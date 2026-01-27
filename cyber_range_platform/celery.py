from __future__ import absolute_import, unicode_literals
import os

from celery import Celery
from django.conf import settings
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cyber_range_platform.settings')

app = Celery('cyber_range_platform')
app.conf.enable_utc = False

app.conf.update(timezone = 'Asia/Kolkata')

app.config_from_object(settings, namespace = "CELERY")

"""
Some Commands-

Beat Command is -
celery -A cyber_range_platform beat -l INFO

Celery Command is -
celery -A cyber_range_platform.celery worker --pool=solo -l info

"""

# Celery Beats Settings

app.conf.beat_schedule = {
    'blacklisted-domains-scheduler-everyday-at-1-am':{
        'task' : 'core.utils.update_blacklisted_domains',
        'schedule' : crontab(day_of_week="*", hour=1, minute= 0),    
        },
    'games-auto-delete-scheduler-in-every-30-min':{
        'task' : 'core.utils.game_auto_delete_in_30_min',
        'schedule' : crontab(day_of_week="*", hour="*", minute= "*/30"), 
    },
    # 'scenario-games-auto-delete-scheduler-in-every-30-min':{
    #     'task' : 'core.utils.scenario_game_auto_delete_in_30_min',
    #     'schedule' : crontab(day_of_week="*", hour="*", minute= "*/30"), 
    # }
}


#--------------------------------

app.autodiscover_tasks()

@app.task(bind = True)
def debug_task(self):
    print(f"Request : {self.request!r}")

