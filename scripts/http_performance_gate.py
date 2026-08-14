"""Loopback-only real HTTP latency/throughput acceptance gate.

The gate authenticates through the public API and exercises read-heavy business
queries against the running FastAPI/PostgreSQL stack. Credentials are accepted
only via environment variables and are never written to the report.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import threading
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

DEFAULT_ENDPOINTS = (
    "GET /workbench/summary",
    "GET /workbench/layout",
    "GET /business-events?page=1&page_size=30",
    "POST /business-events/dispatch?limit=10",
    "GET /leases?page=1&page_size=50",
    "GET /parties?page=1&page_size=50",
    "GET /units?page=1&page_size=50",
)


@dataclass(frozen=True)
class Sample:
    endpoint: str
    status_code: int
    latency_ms: float
    error: str | None = None


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def summarize(samples: list[Sample], elapsed_seconds: float) -> dict:
    latencies = [sample.latency_ms for sample in samples]
    failures = [sample for sample in samples if sample.error or not 200 <= sample.status_code < 300]
    total = len(samples)
    by_endpoint: dict[str, dict] = {}
    for endpoint in sorted({sample.endpoint for sample in samples}):
        subset = [sample for sample in samples if sample.endpoint == endpoint]
        endpoint_latencies = [sample.latency_ms for sample in subset]
        endpoint_failures = [
            sample for sample in subset if sample.error or not 200 <= sample.status_code < 300
        ]
        by_endpoint[endpoint] = {
            "requests": len(subset),
            "failures": len(endpoint_failures),
            "p50_ms": round(percentile(endpoint_latencies, 0.50), 3),
            "p95_ms": round(percentile(endpoint_latencies, 0.95), 3),
            "p99_ms": round(percentile(endpoint_latencies, 0.99), 3),
            "max_ms": round(max(endpoint_latencies, default=0.0), 3),
        }
    return {
        "requests": total,
        "failures": len(failures),
        "error_rate_percent": round((len(failures) / total * 100) if total else 100.0, 4),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "requests_per_second": round((total / elapsed_seconds) if elapsed_seconds else 0.0, 3),
        "mean_ms": round(statistics.fmean(latencies), 3) if latencies else 0.0,
        "p50_ms": round(percentile(latencies, 0.50), 3),
        "p95_ms": round(percentile(latencies, 0.95), 3),
        "p99_ms": round(percentile(latencies, 0.99), 3),
        "max_ms": round(max(latencies, default=0.0), 3),
        "by_endpoint": by_endpoint,
        "failure_examples": [asdict(sample) for sample in failures[:10]],
    }


def evaluate_gate(
    summary: dict,
    *,
    max_p95_ms: float,
    max_error_rate_percent: float,
    min_requests_per_second: float,
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if summary["p95_ms"] > max_p95_ms:
        failures.append(f"p95_ms={summary['p95_ms']} > {max_p95_ms}")
    if summary["error_rate_percent"] > max_error_rate_percent:
        failures.append(
            f"error_rate_percent={summary['error_rate_percent']} > {max_error_rate_percent}"
        )
    if summary["requests_per_second"] < min_requests_per_second:
        failures.append(
            f"requests_per_second={summary['requests_per_second']} < {min_requests_per_second}"
        )
    return not failures, failures


def _loopback_base_url(value: str) -> str:
    base_url = value.rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise argparse.ArgumentTypeError("performance gate is restricted to loopback targets")
    return base_url


def _login(base_url: str, username: str, password: str, tenant_code: str, timeout: float) -> str:
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{base_url}/auth/login",
            json={"username": username, "password": password, "tenant_code": tenant_code},
        )
        response.raise_for_status()
        token = response.json().get("data", {}).get("access_token")
        if not token:
            raise RuntimeError("login response did not contain an access token")
        return str(token)


def run_requests(
    *,
    base_url: str,
    token: str,
    endpoints: tuple[str, ...],
    requests: int,
    concurrency: int,
    timeout: float,
) -> tuple[list[Sample], float]:
    local = threading.local()

    def execute(index: int) -> Sample:
        endpoint = endpoints[index % len(endpoints)]
        method, path = endpoint.split(" ", 1)
        client = getattr(local, "client", None)
        if client is None:
            client = httpx.Client(
                headers={"Authorization": f"Bearer {token}"},
                timeout=timeout,
            )
            local.client = client
        started = time.perf_counter()
        try:
            response = client.request(method, f"{base_url}{path}")
            return Sample(endpoint, response.status_code, (time.perf_counter() - started) * 1000)
        except httpx.HTTPError as exc:
            return Sample(endpoint, 0, (time.perf_counter() - started) * 1000, type(exc).__name__)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        samples = list(executor.map(execute, range(requests)))
    return samples, time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        type=_loopback_base_url,
        default="http://127.0.0.1:8010/api/v1",
    )
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--warmup", type=int, default=40)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--max-p95-ms", type=float, default=500.0)
    parser.add_argument("--max-error-rate-percent", type=float, default=1.0)
    parser.add_argument("--min-rps", type=float, default=20.0)
    parser.add_argument(
        "--endpoint",
        action="append",
        dest="endpoints",
        help="repeatable 'METHOD /path' override; defaults to the shared business read set",
    )
    parser.add_argument("--tenant-code", default=os.getenv("PERF_TENANT_CODE", "default"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.requests < 1 or args.concurrency < 1 or args.concurrency > args.requests:
        parser.error("requests/concurrency must be positive and concurrency <= requests")
    if args.warmup < 0:
        parser.error("warmup must be non-negative")
    endpoints = tuple(args.endpoints or DEFAULT_ENDPOINTS)
    for endpoint in endpoints:
        parts = endpoint.split(" ", 1)
        if len(parts) != 2 or parts[0] not in {"GET", "POST"} or not parts[1].startswith("/"):
            parser.error(f"invalid endpoint: {endpoint!r}")
    username = os.getenv("PERF_USERNAME", "").strip()
    password = os.getenv("PERF_PASSWORD", "")
    if not username or not password:
        parser.error("PERF_USERNAME and PERF_PASSWORD environment variables are required")

    token = _login(args.base_url, username, password, args.tenant_code, args.timeout_seconds)
    if args.warmup:
        warmup_samples, _ = run_requests(
            base_url=args.base_url,
            token=token,
            endpoints=endpoints,
            requests=args.warmup,
            concurrency=min(args.concurrency, args.warmup),
            timeout=args.timeout_seconds,
        )
        if any(sample.error or not 200 <= sample.status_code < 300 for sample in warmup_samples):
            raise RuntimeError("warmup request failed; measured run was not started")

    samples, elapsed = run_requests(
        base_url=args.base_url,
        token=token,
        endpoints=endpoints,
        requests=args.requests,
        concurrency=args.concurrency,
        timeout=args.timeout_seconds,
    )
    aggregate = summarize(samples, elapsed)
    passed, gate_failures = evaluate_gate(
        aggregate,
        max_p95_ms=args.max_p95_ms,
        max_error_rate_percent=args.max_error_rate_percent,
        min_requests_per_second=args.min_rps,
    )
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Python 3.10
        "target": args.base_url,
        "runtime": {
            "requests": args.requests,
            "concurrency": args.concurrency,
            "warmup": args.warmup,
            "endpoints": list(endpoints),
        },
        "thresholds": {
            "max_p95_ms": args.max_p95_ms,
            "max_error_rate_percent": args.max_error_rate_percent,
            "min_requests_per_second": args.min_rps,
        },
        "aggregate": aggregate,
        "gate": {"passed": passed, "failures": gate_failures},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "HTTP_PERFORMANCE_GATE="
        + ("PASS" if passed else "FAIL")
        + f" requests={aggregate['requests']} p95_ms={aggregate['p95_ms']} "
        + f"rps={aggregate['requests_per_second']} errors={aggregate['error_rate_percent']}%"
    )
    print(f"REPORT={args.output.resolve()}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
