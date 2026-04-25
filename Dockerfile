FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements_py3.12.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

WORKDIR /app/backend

RUN SECRET_KEY=build-time-placeholder DEBUG=False \
    SKILL_REPO_PATH=/tmp \
    python manage.py collectstatic --noinput -v 0

EXPOSE 3000

CMD ["gunicorn", "skill_market.wsgi", "--bind", "0.0.0.0:3000", "--workers", "2"]
