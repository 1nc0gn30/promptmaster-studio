"""Tests for PromptMaster Studio UI server and REST API endpoints in promptmaster_studio.ui_server."""

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from promptmaster_studio.ui_server import create_server


@pytest.fixture(scope="module")
def live_ui_server():
    """Start UI server on an ephemeral loopback port in background thread."""
    # Find free port or use 8769
    host = "127.0.0.1"
    port = 8799
    server = create_server(host=host, port=port)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.3)  # Brief warm-up

    base_url = f"http://{host}:{port}"
    yield base_url

    server.shutdown()
    server.server_close()


class TestUIServerRoutes:
    """Test all UI Server REST endpoints and static file serving."""

    def _http_get(self, url: str) -> tuple[int, dict | str, dict]:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            headers = dict(resp.getheaders())
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8")
            if "application/json" in content_type:
                return status, json.loads(body), headers
            return status, body, headers

    def _http_post(self, url: str, data: dict) -> tuple[int, dict, dict]:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            headers = dict(resp.getheaders())
            body = json.loads(resp.read().decode("utf-8"))
            return status, body, headers

    def test_get_root_serves_html(self, live_ui_server: str):
        status, body, headers = self._http_get(f"{live_ui_server}/")
        assert status == 200
        assert "text/html" in headers.get("Content-Type", "")
        assert "PromptMaster Studio" in str(body)

    def test_api_health(self, live_ui_server: str):
        status, data, _ = self._http_get(f"{live_ui_server}/api/health")
        assert status == 200
        assert data["status"] == "healthy"
        assert "version" in data

    def test_api_stats(self, live_ui_server: str):
        status, data, _ = self._http_get(f"{live_ui_server}/api/stats")
        assert status == 200
        assert data["templates_count"] >= 5
        assert data["curriculum_count"] >= 5
        assert len(data["supported_targets"]) >= 4

    def test_api_models(self, live_ui_server: str):
        status, data, _ = self._http_get(f"{live_ui_server}/api/models")
        assert status == 200
        assert "claude" in data or "claude-3-5-sonnet" in str(data)

    def test_api_templates_list_and_detail(self, live_ui_server: str):
        status, templates, _ = self._http_get(f"{live_ui_server}/api/templates")
        assert status == 200
        assert isinstance(templates, list)
        assert len(templates) >= 5

        # Query single
        status_single, single_tpl, _ = self._http_get(f"{live_ui_server}/api/templates/code_reviewer")
        assert status_single == 200
        assert single_tpl["id"] == "code_reviewer"

    def test_api_curriculum_list_and_detail(self, live_ui_server: str):
        status, lessons, _ = self._http_get(f"{live_ui_server}/api/curriculum")
        assert status == 200
        assert isinstance(lessons, list)
        assert len(lessons) >= 5

        # Query single lesson
        status_l1, lesson_l1, _ = self._http_get(f"{live_ui_server}/api/curriculum/l1")
        assert status_l1 == 200
        assert "Anatomy" in lesson_l1["title"] or "Foundations" in lesson_l1["title"]

    def test_post_api_optimize(self, live_ui_server: str):
        payload = {
            "prompt": "Write a Python script to download S3 files concurrently",
            "target": "anthropic",
            "cot": True,
        }
        status, res, _ = self._http_post(f"{live_ui_server}/api/optimize", payload)
        assert status == 200
        assert "optimized_prompt" in res
        assert "<instructions>" in res["optimized_prompt"]

    def test_post_api_lint(self, live_ui_server: str):
        payload = {
            "prompt": "Please kindly do some stuff with things.",
        }
        status, res, _ = self._http_post(f"{live_ui_server}/api/lint", payload)
        assert status == 200
        assert "clarity_score" in res
        assert res["clarity_score"] < 95.0

    def test_post_api_autofix(self, live_ui_server: str):
        payload = {
            "prompt": "Please kindly review this data: {{ input }}",
        }
        status, res, _ = self._http_post(f"{live_ui_server}/api/autofix", payload)
        assert status == 200
        assert "fixed_prompt" in res
        assert "Please kindly" not in res["fixed_prompt"]

    def test_post_api_render(self, live_ui_server: str):
        payload = {
            "template": "Hello {{ name }}, mode: {{ mode }}",
            "variables": {"name": "Morpheus", "mode": "Matrix"},
        }
        status, res, _ = self._http_post(f"{live_ui_server}/api/render", payload)
        assert status == 200
        assert res["rendered"] == "Hello Morpheus, mode: Matrix"

    def test_post_api_tokens(self, live_ui_server: str):
        payload = {
            "prompt": "Estimate token budget for this text.",
            "model": "claude",
        }
        status, res, _ = self._http_post(f"{live_ui_server}/api/tokens", payload)
        assert status == 200
        assert res["estimated_tokens"] > 0
        assert res["fits_in_context"] is True

    def test_post_api_cove(self, live_ui_server: str):
        payload = {
            "prompt": "Explain the safety benchmarks for autonomous driving systems.",
            "domain": "automotive_engineering",
        }
        status, res, _ = self._http_post(f"{live_ui_server}/api/cove", payload)
        assert status == 200
        assert res["domain"] == "automotive_engineering"
        assert len(res["stages"]) == 4

    def test_post_api_debate(self, live_ui_server: str):
        payload = {
            "topic": "SQL vs NoSQL for distributed timeseries telemetry data",
            "rounds": 3,
        }
        status, res, _ = self._http_post(f"{live_ui_server}/api/debate", payload)
        assert status == 200
        assert res["total_rounds"] == 3
        assert len(res["personas"]) == 4

    def test_404_on_unknown_endpoint(self, live_ui_server: str):
        url = f"{live_ui_server}/api/unknown_route_999"
        req = urllib.request.Request(url, method="GET")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 404
