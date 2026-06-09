FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml alembic.ini /app/
COPY app /app/app

RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 cognimesh
USER cognimesh

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

