"""
Step 19: In-Process Thread-Safe Operational Performance Metrics.

Provides:
- Lightweight counters and duration aggregations.
- Strict bounded cardinality (methods, status classes, fixed provider and stage names).
- Zero PHI in metric labels (no patient IDs, names, phones, or clinical data).
- Thread-safe updates via threading.Lock.
"""

import threading
from typing import Any, Dict, Optional


class OperationalMetrics:
    """Thread-safe in-process performance metrics tracker."""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        """Reset all metrics (primarily for test isolation)."""
        with getattr(self, "_lock", threading.Lock()):
            self._requests_total: int = 0
            self._requests_success: int = 0
            self._requests_failed: int = 0
            self._requests_duration_ms_total: float = 0.0

            # Bounded: (method, status_class) e.g. ("POST", "2xx") -> count
            self._requests_by_method_and_status: Dict[str, int] = {}

            # Bounded: (provider, operation) e.g. ("gemini", "summary") -> count
            self._provider_calls: Dict[str, int] = {}

            # Bounded: (provider, error_category) -> count
            self._provider_failures: Dict[str, int] = {}

            # Bounded: stage_name -> {count, success, failure, total_duration_ms}
            self._pipeline_stages: Dict[str, Dict[str, Any]] = {}

    def record_request(self, method: str, status_code: int, duration_ms: float) -> None:
        """Record an HTTP request execution."""
        method_clean = method.upper()[:10] if method else "UNKNOWN"
        status_class = f"{status_code // 100}xx" if 100 <= status_code <= 599 else "other"
        key = f"{method_clean}_{status_class}"

        with self._lock:
            self._requests_total += 1
            if 200 <= status_code < 400:
                self._requests_success += 1
            else:
                self._requests_failed += 1

            self._requests_duration_ms_total += max(0.0, duration_ms)
            self._requests_by_method_and_status[key] = self._requests_by_method_and_status.get(key, 0) + 1

    def record_provider_call(
        self,
        provider: str,
        operation: str,
        success: bool,
        error_category: Optional[str] = None,
    ) -> None:
        """Record a third-party AI or external provider call."""
        provider_clean = (provider or "unknown").lower()[:32]
        op_clean = (operation or "unknown").lower()[:32]
        call_key = f"{provider_clean}_{op_clean}"

        with self._lock:
            self._provider_calls[call_key] = self._provider_calls.get(call_key, 0) + 1
            if not success:
                err_clean = (error_category or "unknown").lower()[:32]
                fail_key = f"{provider_clean}_{err_clean}"
                self._provider_failures[fail_key] = self._provider_failures.get(fail_key, 0) + 1

    def record_pipeline_stage(
        self,
        stage: str,
        success: bool,
        duration_ms: float,
        error_category: Optional[str] = None,
    ) -> None:
        """Record a pipeline stage execution (e.g. document_ocr, case_summary)."""
        stage_clean = (stage or "unknown").lower()[:40]

        with self._lock:
            if stage_clean not in self._pipeline_stages:
                self._pipeline_stages[stage_clean] = {
                    "count": 0,
                    "success": 0,
                    "failure": 0,
                    "total_duration_ms": 0.0,
                    "failures_by_category": {},
                }

            entry = self._pipeline_stages[stage_clean]
            entry["count"] += 1
            entry["total_duration_ms"] += max(0.0, duration_ms)

            if success:
                entry["success"] += 1
            else:
                entry["failure"] += 1
                if error_category:
                    cat_clean = error_category.lower()[:32]
                    cats = entry["failures_by_category"]
                    cats[cat_clean] = cats.get(cat_clean, 0) + 1

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Return a read-only snapshot of current metrics."""
        with self._lock:
            avg_req_ms = (
                round(self._requests_duration_ms_total / self._requests_total, 2)
                if self._requests_total > 0
                else 0.0
            )

            stage_summaries = {}
            for s_name, s_data in self._pipeline_stages.items():
                c = s_data["count"]
                stage_summaries[s_name] = {
                    "count": c,
                    "success": s_data["success"],
                    "failure": s_data["failure"],
                    "avg_duration_ms": round(s_data["total_duration_ms"] / c, 2) if c > 0 else 0.0,
                    "failures_by_category": dict(s_data["failures_by_category"]),
                }

            return {
                "http_requests": {
                    "total": self._requests_total,
                    "success": self._requests_success,
                    "failed": self._requests_failed,
                    "avg_duration_ms": avg_req_ms,
                    "by_method_and_status": dict(self._requests_by_method_and_status),
                },
                "providers": {
                    "calls": dict(self._provider_calls),
                    "failures": dict(self._provider_failures),
                },
                "pipeline_stages": stage_summaries,
            }


# Singleton instance
operational_metrics = OperationalMetrics()
