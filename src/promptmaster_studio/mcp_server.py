"""Model Context Protocol (MCP) Server for PromptMaster Studio.

Implements the standard MCP JSON-RPC 2.0 protocol over stdio for seamless integration
with Claude Desktop, Cursor, Continue, Roo Code, VSCode, and other MCP clients.
100% Python Standard Library. Zero external dependencies.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional, Union

from . import (
    __version__,
    estimate_tokens,
    get_curriculum_lessons,
    get_model_specs,
    get_prompt_templates,
    lint_prompt,
    optimize_prompt,
    render_template,
)
from .compat import get_platform_info

# Setup logging to sys.stderr so stdout remains a pure JSON-RPC stream
logger = logging.getLogger("promptmaster_studio.mcp")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter("[MCP %(levelname)s] %(message)s"))
logger.addHandler(handler)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "promptmaster-studio"


class MCPServer:
    """Production-grade Model Context Protocol (MCP) stdio server."""

    def __init__(self) -> None:
        self.server_name = SERVER_NAME
        self.server_version = __version__
        self.initialized = False
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._tool_handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the standard suite of PromptMaster Studio MCP tools."""
        
        # 1. prompt_optimize
        self.register_tool(
            name="prompt_optimize",
            description="Enhance and optimize a raw prompt with expert personas, XML tags, boundary constraints, and Chain-of-Thought reasoning.",
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The raw prompt or instructions to optimize.",
                    },
                    "target": {
                        "type": "string",
                        "enum": ["anthropic", "openai", "gemini", "generic"],
                        "default": "generic",
                        "description": "Target LLM architecture style.",
                    },
                    "cot": {
                        "type": "boolean",
                        "default": False,
                        "description": "Enable structured Chain-of-Thought reasoning steps.",
                    },
                    "persona": {
                        "type": "string",
                        "description": "Optional specific persona or role to assign (e.g. 'Senior Security Auditor').",
                    },
                    "constraints": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of explicit positive or negative constraints.",
                    },
                    "xml_tags": {
                        "type": "boolean",
                        "default": True,
                        "description": "Wrap sections in semantic XML tags.",
                    },
                },
                "required": ["prompt"],
            },
            handler=self._handle_prompt_optimize,
        )

        # 2. prompt_lint
        self.register_tool(
            name="prompt_lint",
            description="Perform static prompt analysis, clarity scoring, security checks, and actionable quality suggestions.",
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt text to analyze and lint.",
                    },
                    "target": {
                        "type": "string",
                        "default": "generic",
                        "description": "Target LLM provider context.",
                    },
                },
                "required": ["prompt"],
            },
            handler=self._handle_prompt_lint,
        )

        # 3. prompt_interpolate
        self.register_tool(
            name="prompt_interpolate",
            description="Render a prompt template with dynamic variable dictionary values.",
            input_schema={
                "type": "object",
                "properties": {
                    "template": {
                        "type": "string",
                        "description": "Template string, file path, or built-in template ID.",
                    },
                    "variables": {
                        "type": "object",
                        "description": "Key-value map of variable values to interpolate.",
                        "additionalProperties": True,
                    },
                },
                "required": ["template", "variables"],
            },
            handler=self._handle_prompt_interpolate,
        )

        # 4. prompt_estimate_tokens
        self.register_tool(
            name="prompt_estimate_tokens",
            description="Estimate token counts, context window utilization, and estimated API input cost for a target model.",
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The text or prompt to estimate.",
                    },
                    "model": {
                        "type": "string",
                        "enum": ["claude", "claude-haiku", "gpt4o", "gpt4o-mini", "gemini", "gemini-flash", "deepseek", "generic"],
                        "default": "claude",
                        "description": "Target model identifier.",
                    },
                },
                "required": ["prompt"],
            },
            handler=self._handle_prompt_estimate_tokens,
        )

        # 5. prompt_templates
        self.register_tool(
            name="prompt_templates",
            description="List, search, or inspect built-in production-grade prompt templates.",
            input_schema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["coding", "reasoning", "engineering", "agents", "writing", "all"],
                        "description": "Filter templates by category.",
                    },
                    "search": {
                        "type": "string",
                        "description": "Keyword search query across titles, descriptions, and tags.",
                    },
                    "id": {
                        "type": "string",
                        "description": "Specific template ID to inspect in detail.",
                    },
                },
            },
            handler=self._handle_prompt_templates,
        )

        # 6. prompt_curriculum
        self.register_tool(
            name="prompt_curriculum",
            description="Retrieve prompt engineering curriculum lessons, guides, and practical exercises.",
            input_schema={
                "type": "object",
                "properties": {
                    "lesson_id": {
                        "type": "string",
                        "description": "Specific lesson ID (e.g. 'l1', 'l2', 'l3', 'l4', 'l5', 'l6').",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["Prompting", "Engineering", "Local", "Agents", "all"],
                        "description": "Filter lessons by category.",
                    },
                },
            },
            handler=self._handle_prompt_curriculum,
        )

        # 7. prompt_diagnostics
        self.register_tool(
            name="prompt_diagnostics",
            description="Run system health checks, verify platform environment, and report diagnostic status.",
            input_schema={
                "type": "object",
                "properties": {},
            },
            handler=self._handle_prompt_diagnostics,
        )

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        """Register a new MCP tool with its JSON schema and execution handler."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
        }
        self._tool_handlers[name] = handler

    # -------------------------------------------------------------------------
    # Tool Handlers
    # -------------------------------------------------------------------------

    def _handle_prompt_optimize(self, args: Dict[str, Any]) -> Dict[str, Any]:
        prompt = args.get("prompt", "")
        target = args.get("target", "generic")
        cot = bool(args.get("cot", False))
        persona = args.get("persona")
        constraints = args.get("constraints")
        xml_tags = bool(args.get("xml_tags", True))

        result = optimize_prompt(
            prompt=prompt,
            target=target,
            cot=cot,
            persona=persona,
            constraints=constraints,
            xml_tags=xml_tags,
        )

        formatted_output = f"""# Optimized Prompt ({result.target_provider})
Estimated Tokens: {result.estimated_tokens_before} -> {result.estimated_tokens_after}

## Improvements Applied
{chr(10).join('- ' + imp for imp in result.improvements)}

## Optimized Output
```
{result.optimized_prompt}
```"""

        return {
            "content": [
                {"type": "text", "text": formatted_output},
            ],
            "data": result.to_dict(),
        }

    def _handle_prompt_lint(self, args: Dict[str, Any]) -> Dict[str, Any]:
        prompt = args.get("prompt", "")
        target = args.get("target", "generic")

        result = lint_prompt(prompt=prompt, target=target)

        issues_md = "\n".join(
            f"- [{i.severity.upper()}] {i.rule_id} ({i.category}): {i.message}" + (f"\n  * Suggestion: {i.suggestion}" if i.suggestion else "")
            for i in result.issues
        ) if result.issues else "No issues detected. Clean prompt!"

        formatted_output = f"""# Prompt Quality Analysis
- Overall Score: {result.overall_score}/100
- Clarity Score: {result.clarity_score}/100
- Structure Score: {result.structure_score}/100
- Security Score: {result.security_score}/100
- Estimated Tokens: {result.estimated_tokens} ({result.word_count} words)

## Issues Detected
{issues_md}

## Key Recommendations
{chr(10).join('- ' + s for s in result.suggestions_summary)}"""

        return {
            "content": [
                {"type": "text", "text": formatted_output},
            ],
            "data": result.to_dict(),
        }

    def _handle_prompt_interpolate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        template = args.get("template", "")
        variables = args.get("variables", {})

        rendered = render_template(template=template, variables=variables)

        # Check for any remaining unfilled variables
        import re
        unfilled = list(set(re.findall(r"\{\{([a-zA-Z0-9_\-]+)\}\}", rendered) + re.findall(r"\{([a-zA-Z0-9_\-]+)\}", rendered)))

        return {
            "content": [
                {"type": "text", "text": rendered},
            ],
            "data": {
                "rendered": rendered,
                "unfilled_variables": unfilled,
                "variable_count": len(variables),
            },
        }

    def _handle_prompt_estimate_tokens(self, args: Dict[str, Any]) -> Dict[str, Any]:
        prompt = args.get("prompt", "")
        model = args.get("model", "claude")

        report = estimate_tokens(prompt_or_text=prompt, model=model)
        if hasattr(report, "to_dict"):
            r_dict = report.to_dict()
        else:
            r_dict = dict(report)

        model_name = r_dict.get("model_name", model)
        est_tokens = r_dict.get("estimated_tokens", r_dict.get("prompt_tokens", 0))
        char_count = r_dict.get("char_count", len(prompt))
        word_count = r_dict.get("word_count", len(prompt.split()))
        ctx_win = r_dict.get("context_window", 128000)
        usage_pct = r_dict.get("context_usage_percent", 0.0)
        rem_ctx = r_dict.get("remaining_context", 0)
        cost_usd = r_dict.get("estimated_cost_usd", 0.0)
        fits = r_dict.get("fits_in_context", True)

        formatted_output = f"""# Token & Context Budget Report ({model_name})
- Estimated Tokens: {est_tokens:,}
- Characters: {char_count:,} | Words: {word_count:,}
- Context Window Limit: {ctx_win:,} tokens
- Context Utilization: {usage_pct}%
- Remaining Envelope: {rem_ctx:,} tokens
- Estimated API Input Cost: ${cost_usd:.6f} USD
- Status: {'PASSED (Within context limit)' if fits else 'EXCEEDED CONTEXT LIMIT'}"""

        return {
            "content": [
                {"type": "text", "text": formatted_output},
            ],
            "data": r_dict,
        }

    def _handle_prompt_templates(self, args: Dict[str, Any]) -> Dict[str, Any]:
        category = args.get("category")
        search = args.get("search")
        template_id = args.get("id")

        templates = get_prompt_templates(category=category, search=search, template_id=template_id)

        if template_id and templates:
            t = templates[0]
            vars_list = "\n".join(f"- `{v.name}`: {v.description} (e.g. '{v.sample_value}')" for v in t.variables)
            formatted = f"""# Template: {t.title} (ID: `{t.id}`)
**Category**: {t.category} | **Target**: {t.target_provider}
**Description**: {t.description}
**Tags**: {', '.join(t.tags)}

## Variables
{vars_list or 'None'}

## Template Body
```
{t.template_str}
```"""
        else:
            lines = [f"# Production Prompt Templates ({len(templates)} found)\n"]
            for t in templates:
                lines.append(f"- **{t.title}** (`{t.id}`) [{t.category}]")
                lines.append(f"  {t.description}")
                lines.append(f"  *Variables*: {', '.join(v.name for v in t.variables) or 'None'}")
            formatted = "\n".join(lines)

        return {
            "content": [
                {"type": "text", "text": formatted},
            ],
            "data": [t.to_dict() for t in templates],
        }

    def _handle_prompt_curriculum(self, args: Dict[str, Any]) -> Dict[str, Any]:
        lesson_id = args.get("lesson_id")
        category = args.get("category")

        lessons = get_curriculum_lessons(lesson_id=lesson_id, category=category)

        if lesson_id and lessons:
            # Single lesson detail
            lesson = lessons if not isinstance(lessons, list) else lessons[0]
            takeaways = "\n".join(f"- {k}" for k in lesson.key_takeaways)
            formatted = f"""{lesson.content_markdown}

---
### Key Takeaways
{takeaways}

### Before vs After Example
**Before (Naive)**:
```
{lesson.sample_before_prompt}
```

**After (Optimized)**:
```
{lesson.sample_after_prompt}
```"""
            data_out = lesson.to_dict()
        else:
            lesson_list = lessons if isinstance(lessons, list) else [lessons]
            lines = [f"# Prompt Engineering Curriculum ({len(lesson_list)} lessons)\n"]
            for l in lesson_list:
                lines.append(f"### Lesson {l.id.upper()}: {l.title} ({l.difficulty} - {l.estimated_minutes} min)")
                lines.append(f"*{l.summary}*")
                lines.append(f"Category: `{l.category}`\n")
            formatted = "\n".join(lines)
            data_out = [l.to_dict() for l in lesson_list]

        return {
            "content": [
                {"type": "text", "text": formatted},
            ],
            "data": data_out,
        }

    def _handle_prompt_diagnostics(self, args: Dict[str, Any]) -> Dict[str, Any]:
        platform_info = get_platform_info()
        templates_count = len(get_prompt_templates())
        curriculum_count = len(get_curriculum_lessons())
        models_count = len(get_model_specs())

        diag_text = f"""# PromptMaster Studio Diagnostics
- Version: {self.server_version}
- MCP Protocol: {PROTOCOL_VERSION}
- Operating System: {platform_info['system']} ({platform_info['release']} {platform_info['machine']})
- Python Version: {platform_info['python_version']}
- Filesystem Encoding: {platform_info['filesystem_encoding']}
- Registered MCP Tools: {len(self._tools)}
- Built-in Templates: {templates_count}
- Curriculum Lessons: {curriculum_count}
- Supported Model Profiles: {models_count}
- Overall Status: HEALTHY (Zero External Dependencies)"""

        return {
            "content": [
                {"type": "text", "text": diag_text},
            ],
            "data": {
                "version": self.server_version,
                "protocol_version": PROTOCOL_VERSION,
                "platform": platform_info,
                "tools_count": len(self._tools),
                "templates_count": templates_count,
                "curriculum_count": curriculum_count,
                "models_count": models_count,
                "status": "HEALTHY",
            },
        }

    # -------------------------------------------------------------------------
    # JSON-RPC 2.0 Dispatcher
    # -------------------------------------------------------------------------

    def handle_message(self, request_str: str) -> Optional[str]:
        """Process a raw incoming JSON-RPC string message and return response string if required."""
        if not request_str.strip():
            return None

        try:
            req = json.loads(request_str)
        except Exception as e:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}",
                },
            })

        # Handle batch or single
        if isinstance(req, list):
            responses = [self._dispatch_single(item) for item in req]
            valid_resps = [r for r in responses if r is not None]
            return json.dumps(valid_resps) if valid_resps else None

        resp = self._dispatch_single(req)
        return json.dumps(resp) if resp is not None else None

    def _dispatch_single(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(req, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: expected JSON object"},
            }

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        # Notifications (no id)
        is_notification = "id" not in req

        try:
            # 1. initialize
            if method == "initialize":
                self.initialized = True
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "prompts": {"listChanged": False},
                            "resources": {"subscribe": False, "listChanged": False},
                        },
                        "serverInfo": {
                            "name": self.server_name,
                            "version": self.server_version,
                        },
                    },
                }

            # 2. notifications/initialized
            if method == "notifications/initialized":
                logger.info("Client completed MCP initialization.")
                return None

            # 3. ping
            if method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}

            # 4. tools/list
            if method == "tools/list":
                tools_list = list(self._tools.values())
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": tools_list},
                }

            # 5. tools/call
            if method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})

                if not tool_name or tool_name not in self._tool_handlers:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Tool '{tool_name}' not found",
                        },
                    }

                handler = self._tool_handlers[tool_name]
                try:
                    result_data = handler(tool_args)
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": result_data.get("content", []),
                            "isError": False,
                        },
                    }
                except Exception as e:
                    logger.error(f"Error executing tool '{tool_name}': {e}\n{traceback.format_exc()}")
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": f"Error executing tool '{tool_name}': {str(e)}"}],
                            "isError": True,
                        },
                    }

            # 6. prompts/list
            if method == "prompts/list":
                templates = get_prompt_templates()
                prompt_items = []
                for t in templates:
                    prompt_items.append({
                        "name": t.id,
                        "description": t.description,
                        "arguments": [
                            {"name": v.name, "description": v.description, "required": v.required}
                            for v in t.variables
                        ],
                    })
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"prompts": prompt_items},
                }

            # 7. prompts/get
            if method == "prompts/get":
                prompt_name = params.get("name")
                prompt_args = params.get("arguments", {})
                templates = get_prompt_templates(template_id=prompt_name)
                if not templates:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": f"Prompt '{prompt_name}' not found"},
                    }
                t = templates[0]
                rendered = render_template(t.template_str, prompt_args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "description": t.description,
                        "messages": [
                            {
                                "role": "user",
                                "content": {"type": "text", "text": rendered},
                            }
                        ],
                    },
                }

            # 8. resources/list
            if method == "resources/list":
                resources = [
                    {
                        "uri": "promptmaster://templates",
                        "name": "Prompt Templates Catalog",
                        "mimeType": "application/json",
                        "description": "Full directory of built-in production prompt templates.",
                    },
                    {
                        "uri": "promptmaster://curriculum",
                        "name": "Prompt Engineering Curriculum",
                        "mimeType": "application/json",
                        "description": "Educational prompt engineering lessons and best practices.",
                    },
                    {
                        "uri": "promptmaster://models",
                        "name": "Model Specifications & Context Budgets",
                        "mimeType": "application/json",
                        "description": "Model token limits and pricing reference.",
                    },
                ]
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"resources": resources},
                }

            # 9. resources/read
            if method == "resources/read":
                uri = params.get("uri", "")
                if uri == "promptmaster://templates":
                    data = [t.to_dict() for t in get_prompt_templates()]
                elif uri == "promptmaster://curriculum":
                    data = [l.to_dict() for l in get_curriculum_lessons()]
                elif uri == "promptmaster://models":
                    data = {k: v.to_dict() for k, v in get_model_specs().items()}
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": f"Resource URI '{uri}' not found"},
                    }
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": json.dumps(data, indent=2),
                            }
                        ]
                    },
                }

            # Unknown Method
            if is_notification:
                return None

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found",
                },
            }

        except Exception as e:
            logger.error(f"Internal error processing method '{method}': {e}\n{traceback.format_exc()}")
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                },
            }

    def run_stdio(self) -> None:
        """Run the MCP server over standard input / standard output in a continuous event loop."""
        logger.info(f"Starting {self.server_name} v{self.server_version} MCP server over stdio...")
        
        # Read from sys.stdin line by line
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    # EOF reached
                    logger.info("Received EOF on stdin. Shutting down MCP server.")
                    break

                line_str = line.strip()
                if not line_str:
                    continue

                # Support Content-Length HTTP-style header framing if sent by client
                if line_str.startswith("Content-Length:"):
                    try:
                        content_len = int(line_str.split(":", 1)[1].strip())
                        # Read blank line
                        sys.stdin.readline()
                        # Read body
                        body = sys.stdin.read(content_len)
                        response_str = self.handle_message(body)
                    except Exception as e:
                        logger.error(f"Error reading header framed message: {e}")
                        continue
                else:
                    response_str = self.handle_message(line_str)

                if response_str:
                    sys.stdout.write(response_str + "\n")
                    sys.stdout.flush()

            except (KeyboardInterrupt, SystemExit):
                logger.info("Interrupted. Exiting MCP server.")
                break
            except Exception as e:
                logger.error(f"Unexpected loop exception: {e}\n{traceback.format_exc()}")


def run_mcp_server() -> None:
    """Convenience entrypoint to instantiate and execute the MCP server."""
    server = MCPServer()
    server.run_stdio()


if __name__ == "__main__":
    run_mcp_server()
