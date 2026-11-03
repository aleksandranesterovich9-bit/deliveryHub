FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first: this layer is cached until requirements.txt changes,
# so editing code does not reinstall all packages.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Never run as root inside a container.
RUN useradd --create-home --uid 1000 appuser

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app

USER appuser

EXPOSE 8000

# The same image runs the API, the worker and the outbox relay;
# docker-compose.yml overrides the command for the latter two.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
