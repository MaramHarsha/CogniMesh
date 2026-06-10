FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY app /app/app
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 cognimesh \
  && mkdir -p /var/lib/cognimesh/pipeline-control/exports \
  && chown -R cognimesh:cognimesh /var/lib/cognimesh
USER cognimesh

EXPOSE 8040

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8040"]
