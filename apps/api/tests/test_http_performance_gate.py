from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "http_performance_gate.py"
SPEC = importlib.util.spec_from_file_location("http_performance_gate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_percentile_interpolates_and_empty_is_zero() -> None:
    assert MODULE.percentile([], 0.95) == 0.0
    assert MODULE.percentile([10], 0.95) == 10.0
    assert MODULE.percentile([10, 20, 30, 40], 0.50) == 25.0


def test_gate_requires_all_three_thresholds() -> None:
    summary = {"p95_ms": 501.0, "error_rate_percent": 1.1, "requests_per_second": 19.0}
    passed, failures = MODULE.evaluate_gate(
        summary,
        max_p95_ms=500,
        max_error_rate_percent=1,
        min_requests_per_second=20,
    )
    assert passed is False
    assert len(failures) == 3


def test_summary_counts_non_2xx_and_transport_errors() -> None:
    samples = [
        MODULE.Sample("/a", 200, 10.0),
        MODULE.Sample("/a", 503, 30.0),
        MODULE.Sample("/b", 0, 20.0, "ReadTimeout"),
    ]
    result = MODULE.summarize(samples, elapsed_seconds=0.3)
    assert result["requests"] == 3
    assert result["failures"] == 2
    assert result["requests_per_second"] == 10.0
    assert len(result["failure_examples"]) == 2
