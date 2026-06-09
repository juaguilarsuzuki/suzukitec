import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("suzukitec")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Registra a tarefa de conciliação explicitamente (não está em INSTALLED_APPS)
app.autodiscover_tasks(["conciliacao.src"], related_name="task")

app.conf.beat_schedule = {
    "generate-monthly-reports": {
        "task": "apps.reports.tasks.generate_all_monthly_reports",
        # Runs on the 1st of every month at 06:00
        "schedule": crontab(day_of_month="1", hour=6, minute=0),
    },
    # Conciliação no dia 25 às 08:00 — antes do fechamento do faturamento
    "run-asset-reconciliation": {
        "task": "conciliacao.run_all",
        "schedule": crontab(day_of_month="25", hour=8, minute=0),
    },
}
