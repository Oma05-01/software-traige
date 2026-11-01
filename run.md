(.venv) PS C:\Users\user\multi-agents> docker run --rm `
>>     --name stt-celery-worker `
>>     --env-file backend/.env `
>>     -e DB_HOST=host.docker.internal `
>>     -e CELERY_BROKER_URL=redis://host.docker.internal:6379/0 `
>>     software-triage-worker:dev
 

(.venv) PS C:\Users\user\multi-agents\backend> python manage.py runserver