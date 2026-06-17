import asyncio
import time
import sys
import json
from typing import Dict, Any

try:
    import httpx
except ImportError:
    print("This script requires 'httpx' package. Please install it using 'pip install httpx'.")
    sys.exit(1)


async def send_request(client: httpx.AsyncClient, url: str) -> float:
    start = time.time()
    try:
        res = await client.get(url, timeout=5.0)
        duration = time.time() - start
        if res.status_code == 200:
            return duration
        return -1.0
    except Exception:
        return -1.0


async def run_load_test(target_url: str, requests_count: int, concurrency: int) -> Dict[str, Any]:
    limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency)
    async with httpx.AsyncClient(limits=limits) as client:
        sem = asyncio.Semaphore(concurrency)

        async def worker():
            async with sem:
                return await send_request(client, target_url)

        tasks = [worker() for _ in range(requests_count)]
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

    success_durations = [r for r in results if r > 0]
    failed_count = len(results) - len(success_durations)
    
    avg_latency = sum(success_durations) / len(success_durations) if success_durations else 0.0
    p95_latency = sorted(success_durations)[int(len(success_durations) * 0.95)] if success_durations else 0.0
    throughput = len(success_durations) / total_time if total_time > 0 else 0.0

    return {
        "target": target_url,
        "requests_total": requests_count,
        "concurrency": concurrency,
        "success_count": len(success_durations),
        "failed_count": failed_count,
        "avg_latency_seconds": avg_latency,
        "p95_latency_seconds": p95_latency,
        "throughput_requests_per_second": throughput,
        "total_test_duration_seconds": total_time,
    }


def main():
    target = "http://localhost:8000/ready"  # default to object-registry ready endpoint
    if len(sys.argv) > 1:
        target = sys.argv[1]

    print(f"Starting load test on target: {target}...")
    summary = asyncio.run(run_load_test(target, 50, 5))
    print("\n--- Load Test Summary ---")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
