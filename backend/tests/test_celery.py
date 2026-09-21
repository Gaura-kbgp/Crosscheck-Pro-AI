from app.worker.celery_app import celery_app
from app.worker.tasks.ping import ping_task

def test_celery_initializes():
    assert celery_app is not None
    assert celery_app.conf.broker_url is not None

def test_ping_task_executes():
    result = ping_task()
    assert result["status"] == "ok"
    assert result["message"] == "celery worker is alive"
