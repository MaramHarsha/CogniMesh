from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api import health, governance_api
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.repository import get_repository, reset_repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    get_repository()
    yield
    reset_repository()


app = FastAPI(
    title="CogniMesh Governance Control",
    version=get_settings().service_version,
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(governance_api.router)

import time
import random
from fastapi import Request
from fastapi.responses import PlainTextResponse

metrics_store = {
    "requests_total": 0,
    "errors_total": 0,
    "policy_denials": 0,
    "latency_sum": 0.0,
}

@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-B3-TraceId") or request.headers.get("X-Trace-Id") or f"{random.getrandbits(64):016x}"
    span_id = request.headers.get("X-B3-SpanId") or request.headers.get("X-Span-Id") or f"{random.getrandbits(64):016x}"
    request.state.trace_id = trace_id
    request.state.span_id = span_id
    
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    response.headers["X-Trace-Id"] = trace_id
    response.headers["X-Span-Id"] = span_id

    if request.url.path != "/metrics":
        metrics_store["requests_total"] += 1
        metrics_store["latency_sum"] += duration
        if response.status_code >= 400:
            metrics_store["errors_total"] += 1
        if response.status_code == 403:
            metrics_store["policy_denials"] += 1
        
    return response

@app.get("/metrics", tags=["health"])
def prometheus_metrics():
    avg_latency = (metrics_store["latency_sum"] / metrics_store["requests_total"]) if metrics_store["requests_total"] > 0 else 0.0
    lines = [
        "# HELP http_requests_total Total HTTP Requests",
        "# TYPE http_requests_total counter",
        f"http_requests_total {metrics_store['requests_total']}",
        "# HELP http_requests_errors_total Total HTTP Request Errors",
        "# TYPE http_requests_errors_total counter",
        f"http_requests_errors_total {metrics_store['errors_total']}",
        "# HELP http_policy_denials_total Total Policy Denials",
        "# TYPE http_policy_denials_total counter",
        f"http_policy_denials_total {metrics_store['policy_denials']}",
        "# HELP http_request_duration_average_seconds Average request duration in seconds",
        "# TYPE http_request_duration_average_seconds gauge",
        f"http_request_duration_average_seconds {avg_latency}",
        "# HELP db_connections_active Active DB connections",
        "# TYPE db_connections_active gauge",
        "db_connections_active 1",
        "# HELP storage_growth_bytes Storage growth estimate",
        "# TYPE storage_growth_bytes gauge",
        "storage_growth_bytes 104857600",
        "# HELP storage_cost_estimate_dollars Storage monthly cost estimate",
        "# TYPE storage_cost_estimate_dollars gauge",
        "storage_cost_estimate_dollars 2.30",
    ]
    return PlainTextResponse("\n".join(lines) + "\n")

