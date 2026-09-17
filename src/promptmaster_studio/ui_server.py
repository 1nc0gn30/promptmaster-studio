"""Pure Python standard library HTTP & REST UI Server for PromptMaster Studio.

Serves the Google Material 3 web studio interface and provides REST API endpoints
for prompt optimization, static linting, template interpolation, token estimation,
and curriculum knowledge base queries.
100% Python Standard Library. Zero external runtime dependencies.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import sys
import threading
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from promptmaster_studio import (
    __version__,
    estimate_tokens,
    get_curriculum_lessons,
    get_model_specs,
    get_prompt_templates,
    lint_prompt,
    optimize_prompt,
    render_template,
)
from promptmaster_studio.compat import safe_path
from promptmaster_studio.engine.linter import PromptLinter

logger = logging.getLogger("promptmaster_studio.ui_server")


# Embedded Minimal UI Fallback when public/index.html is not on disk
EMBEDDED_HTML_FALLBACK = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Google PromptMaster Studio</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f8fafd; color: #1f1f1f; }
    h1 { color: #1a73e8; }
    .card { background: white; border: 1px solid #e0e3e7; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    textarea { width: 100%; height: 160px; font-family: monospace; border: 1px solid #c4c7c5; border-radius: 8px; padding: 12px; }
    button { background: #1a73e8; color: white; border: none; padding: 10px 20px; border-radius: 20px; cursor: pointer; font-weight: 600; margin-top: 12px; }
    pre { background: #f1f5f9; padding: 16px; border-radius: 8px; white-space: pre-wrap; margin-top: 16px; }
  </style>
</head>
<body>
  <h1>Google PromptMaster Studio (Standalone Fallback)</h1>
  <div class="card">
    <textarea id="promptInput" placeholder="Enter prompt to optimize..."></textarea>
    <br>
    <button onclick="optimize()">🚀 Meta-Optimize</button>
    <pre id="output">Output will appear here...</pre>
  </div>
  <script>
    async function optimize() {
      const text = document.getElementById('promptInput').value;
      const res = await fetch('/api/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text })
      });
      const data = await res.json();
      document.getElementById('output').innerText = data.optimized_prompt || JSON.stringify(data, null, 2);
    }
  </script>
</body>
</html>"""


class PromptMasterStudioRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler implementing REST endpoints and static file serving."""

    server_version = f"PromptMasterStudio/{__version__}"

    def __init__(self, *args: Any, public_dir: Optional[Path] = None, **kwargs: Any) -> None:
        if public_dir is not None:
            self.public_dir = public_dir
        else:
            # Auto-locate public directory relative to package or workspace root
            pkg_root = Path(__file__).resolve().parent.parent.parent
            candidate = pkg_root / "public"
            if candidate.exists():
                self.public_dir = candidate
            else:
                self.public_dir = Path.cwd() / "public"
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use standard logging rather than stderr printing."""
        logger.debug(f"{self.address_string()} - {format % args}")

    def _send_cors_headers(self) -> None:
        """Add permissive CORS headers for local and remote development clients."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Serialize payload to JSON and send with proper headers."""
        try:
            if hasattr(data, "to_dict"):
                data = data.to_dict()
            elif isinstance(data, list):
                data = [item.to_dict() if hasattr(item, "to_dict") else item for item in data]
            payload = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        except Exception as e:
            payload = json.dumps({"error": f"Serialization error: {str(e)}"}).encode("utf-8")
            status = 500

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        """Send standardized JSON error object."""
        self._send_json({"error": message, "status": status}, status=status)

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests for static assets and REST endpoints."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # ---------------------------------------------------------------------
        # REST API Routes
        # ---------------------------------------------------------------------
        if path == "/api/health":
            self._send_json({
                "status": "healthy",
                "version": __version__,
                "server": "Google PromptMaster Studio",
            })
            return

        if path == "/api/stats":
            self._send_json({
                "version": __version__,
                "templates_count": len(get_prompt_templates()),
                "curriculum_count": len(get_curriculum_lessons()),
                "models_count": len(get_model_specs()),
                "supported_targets": ["anthropic_xml", "openai_chat", "google_gemini", "generic_markdown"],
                "linter_rules_count": 15,
            })
            return

        if path == "/api/models":
            specs = {k: v.to_dict() for k, v in get_model_specs().items()}
            self._send_json(specs)
            return

        if path == "/api/templates":
            cat = query_params.get("category", [None])[0]
            search = query_params.get("search", [None])[0]
            templates = get_prompt_templates(category=cat, search=search)
            self._send_json([t.to_dict() for t in templates])
            return

        if path.startswith("/api/templates/"):
            template_id = path[len("/api/templates/") :].strip()
            templates = get_prompt_templates(template_id=template_id)
            if not templates:
                self._send_error_json(f"Template with ID '{template_id}' not found", status=404)
                return
            self._send_json(templates[0].to_dict())
            return

        if path == "/api/curriculum":
            cat = query_params.get("category", [None])[0]
            lessons = get_curriculum_lessons(category=cat)
            lesson_list = lessons if isinstance(lessons, list) else [lessons]
            self._send_json([l.to_dict() for l in lesson_list])
            return

        if path.startswith("/api/curriculum/"):
            lesson_id = path[len("/api/curriculum/") :].strip()
            lessons = get_curriculum_lessons(lesson_id=lesson_id)
            if not lessons:
                self._send_error_json(f"Curriculum lesson '{lesson_id}' not found", status=404)
                return
            target_lesson = lessons if not isinstance(lessons, list) else lessons[0]
            self._send_json(target_lesson.to_dict())
            return

        # ---------------------------------------------------------------------
        # Static Asset Serving
        # ---------------------------------------------------------------------
        if path == "/" or path == "/index.html":
            self._serve_index_html()
            return

        # Serve static file from public directory
        rel_path = path.lstrip("/")
        try:
            target_file = (self.public_dir / rel_path).resolve()
            # Ensure target stays within public_dir
            if self.public_dir.exists() and target_file.is_file():
                try:
                    is_subpath = target_file.is_relative_to(self.public_dir.resolve())
                except AttributeError:
                    is_subpath = str(target_file).startswith(str(self.public_dir.resolve()))

                if is_subpath:
                    mime_type, _ = mimetypes.guess_type(str(target_file))
                    mime_type = mime_type or "application/octet-stream"
                    content = target_file.read_bytes()

                    self.send_response(200)
                    self.send_header("Content-Type", mime_type)
                    self.send_header("Content-Length", str(len(content)))
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(content)
                    return
        except Exception as e:
            logger.debug(f"Static file lookup failed for '{path}': {e}")

        # If not found in public, 404
        self._send_error_json(f"Path '{path}' not found", status=404)

    def _serve_index_html(self) -> None:
        """Serve public/index.html or embedded fallback."""
        index_file = self.public_dir / "index.html"
        if index_file.exists() and index_file.is_file():
            content = index_file.read_bytes()
        else:
            content = EMBEDDED_HTML_FALLBACK.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def _read_json_body(self) -> Dict[str, Any]:
        """Read and parse incoming JSON request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return {}
        raw_body = self.rfile.read(content_length).decode("utf-8", errors="replace")
        if not raw_body.strip():
            return {}
        return json.loads(raw_body)

    def do_POST(self) -> None:
        """Handle POST REST API requests."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        try:
            body = self._read_json_body()
        except json.JSONDecodeError as e:
            self._send_error_json(f"Malformed JSON body: {str(e)}", status=400)
            return

        try:
            # 1. /api/optimize
            if path == "/api/optimize":
                prompt = body.get("prompt", "")
                target = body.get("target", "anthropic")
                cot = bool(body.get("cot", True))
                persona = body.get("persona")
                constraints = body.get("constraints")
                xml_tags = bool(body.get("xml_tags", True))

                res = optimize_prompt(
                    prompt=prompt,
                    target=target,
                    cot=cot,
                    persona=persona,
                    constraints=constraints,
                    xml_tags=xml_tags,
                )
                self._send_json(res.to_dict())
                return

            # 2. /api/lint
            if path == "/api/lint":
                prompt = body.get("prompt", "")
                target = body.get("target", "generic")
                res = lint_prompt(prompt=prompt, target=target)
                self._send_json(res.to_dict())
                return

            # 3. /api/autofix
            if path == "/api/autofix":
                prompt = body.get("prompt", "")
                linter = PromptLinter()
                fixed = linter.auto_fix(prompt)
                self._send_json({"fixed_prompt": fixed, "original_prompt": prompt})
                return

            # 4. /api/render
            if path == "/api/render":
                template = body.get("template", "")
                variables = body.get("variables", {})
                rendered = render_template(template=template, variables=variables)
                self._send_json({
                    "rendered": rendered,
                    "variables": variables,
                })
                return

            if path == "/api/tokens":
                prompt = body.get("prompt", "")
                model = body.get("model", "claude")
                report = estimate_tokens(prompt_or_text=prompt, model=model)
                self._send_json(report.to_dict() if hasattr(report, "to_dict") else report)
                return

            # Unknown POST route
            self._send_error_json(f"POST route '{path}' not recognized", status=404)

        except Exception as e:
            logger.error(f"Error processing POST {path}: {e}", exc_info=True)
            self._send_error_json(f"Internal server error: {str(e)}", status=500)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    public_dir: Optional[Union[str, Path]] = None,
) -> ThreadingHTTPServer:
    """Instantiate and configure the ThreadingHTTPServer instance."""
    pub_path = safe_path(public_dir) if public_dir else None

    def handler_factory(*args: Any, **kwargs: Any) -> PromptMasterStudioRequestHandler:
        return PromptMasterStudioRequestHandler(*args, public_dir=pub_path, **kwargs)

    server = ThreadingHTTPServer((host, port), handler_factory)
    return server


def start_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    open_browser: bool = False,
    public_dir: Optional[Union[str, Path]] = None,
) -> None:
    """Start the PromptMaster Studio HTTP server and optionally open the browser."""
    server = create_server(host=host, port=port, public_dir=public_dir)
    url = f"http://{host}:{port}/"

    print(f"\n=======================================================")
    print(f"  ⚡ Google PromptMaster Studio v{__version__}")
    print(f"  ✨ Studio UI:     {url}")
    print(f"  🛡️ REST Health:   {url}api/health")
    print(f"  📚 Curriculum:    {url}api/curriculum")
    print(f"  📦 Templates:     {url}api/templates")
    print(f"  Press Ctrl+C to stop.")
    print(f"=======================================================\n")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        print("\nShutting down PromptMaster Studio server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    start_server(host="127.0.0.1", port=8000, open_browser=True)
