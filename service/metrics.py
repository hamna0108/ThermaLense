"""Metrics collector for Digital Twin Inverse Service.

Tracks:
- Total requests and per-endpoint counts
- Refusals and errors
- Latency history with p50 / p95 percentile calculations
- Share of model_invalid and out_of_range flags
"""

import threading
import numpy as np

class MetricsTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self.requests_total = 0
        self.requests_by_endpoint = {
            "/v1/estimate": 0,
            "/v1/diagnose": 0,
            "/v1/placement": 0,
            "/v1/field": 0,
            "/v1/poisson": 0,
            "/health": 0,
            "/version": 0,
            "/metrics": 0,
        }
        self.refusals_total = 0
        self.errors_total = 0
        self.latencies_by_endpoint = {
            "/v1/estimate": [],
            "/v1/diagnose": [],
            "/v1/placement": [],
            "/v1/field": [],
            "/v1/poisson": [],
            "/health": [],
            "/version": [],
            "/metrics": [],
        }
        self.model_invalid_count = 0
        self.out_of_range_count = 0
        self.estimate_requests_count = 0

    def record_request(self, endpoint: str):
        with self._lock:
            self.requests_total += 1
            if endpoint in self.requests_by_endpoint:
                self.requests_by_endpoint[endpoint] += 1
            else:
                self.requests_by_endpoint[endpoint] = 1
                self.latencies_by_endpoint[endpoint] = []

    def record_latency(self, endpoint: str, latency_ms: float):
        with self._lock:
            if endpoint not in self.latencies_by_endpoint:
                self.latencies_by_endpoint[endpoint] = []
            self.latencies_by_endpoint[endpoint].append(latency_ms)
            # Cap latency array to prevent unbounded memory growth
            if len(self.latencies_by_endpoint[endpoint]) > 5000:
                self.latencies_by_endpoint[endpoint] = self.latencies_by_endpoint[endpoint][-2500:]

    def record_refusal(self):
        with self._lock:
            self.refusals_total += 1

    def record_error(self):
        with self._lock:
            self.errors_total += 1

    def record_estimate_flags(self, model_invalid: bool, out_of_range: bool):
        with self._lock:
            self.estimate_requests_count += 1
            if model_invalid:
                self.model_invalid_count += 1
            if out_of_range:
                self.out_of_range_count += 1

    def get_summary(self):
        with self._lock:
            p50 = {}
            p95 = {}
            for ep, lats in self.latencies_by_endpoint.items():
                if len(lats) > 0:
                    p50[ep] = round(float(np.percentile(lats, 50)), 2)
                    p95[ep] = round(float(np.percentile(lats, 95)), 2)
                else:
                    p50[ep] = 0.0
                    p95[ep] = 0.0

            est_cnt = max(1, self.estimate_requests_count)
            model_invalid_share = round(self.model_invalid_count / est_cnt, 4)
            out_of_range_share = round(self.out_of_range_count / est_cnt, 4)

            return {
                "requests_total": self.requests_total,
                "requests_by_endpoint": dict(self.requests_by_endpoint),
                "refusals_total": self.refusals_total,
                "errors_total": self.errors_total,
                "latency_p50_ms": p50,
                "latency_p95_ms": p95,
                "flags": {
                    "estimate_requests_count": self.estimate_requests_count,
                    "model_invalid_count": self.model_invalid_count,
                    "model_invalid_share": model_invalid_share,
                    "out_of_range_count": self.out_of_range_count,
                    "out_of_range_share": out_of_range_share,
                }
            }

GLOBAL_METRICS = MetricsTracker()
