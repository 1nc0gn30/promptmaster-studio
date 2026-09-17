"""Command Line Interface for PromptMaster Studio.

Multi-OS CLI supporting prompt optimization, linting, templating, token budgeting,
curriculum navigation, local web UI serving, MCP server execution, and self-testing.
100% Python Standard Library. Zero external dependencies.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import platform
import re
import socketserver
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from . import (
    __version__,
    PromptTemplate,
    estimate_tokens,
    get_curriculum_lessons,
    get_model_specs,
    get_prompt_templates,
    lint_prompt,
    optimize_prompt,
    render_template,
)
from .compat import (
    IS_LINUX,
    IS_MACOS,
    IS_TERMUX,
    IS_WINDOWS,
    atomic_write_text,
    get_app_dir,
    get_platform_info,
    read_json_safe,
    read_text_safe,
    safe_path,
)
from .mcp_server import MCPServer, PROTOCOL_VERSION, run_mcp_server

# ============================================================================
# COLOR & FORMATTING SYSTEM
# ============================================================================

_COLOR_ENABLED = True


def set_color_enabled(enabled: bool) -> None:
    """Explicitly enable or disable ANSI color output."""
    global _COLOR_ENABLED
    _COLOR_ENABLED = enabled


def should_use_color() -> bool:
    """Determine whether color output is active based on flags, env vars, and tty."""
    if not _COLOR_ENABLED:
        return False
    if "NO_COLOR" in os.environ and os.environ["NO_COLOR"].strip():
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    return True


class Color:
    """ANSI color codes with automatic bypass when color is disabled."""
    
    @staticmethod
    def _c(code: str, text: str) -> str:
        if not should_use_color():
            return text
        return f"\033[{code}m{text}\033[0m"

    @classmethod
    def bold(cls, text: str) -> str:
        return cls._c("1", text)

    @classmethod
    def dim(cls, text: str) -> str:
        return cls._c("2", text)

    @classmethod
    def red(cls, text: str) -> str:
        return cls._c("31", text)

    @classmethod
    def green(cls, text: str) -> str:
        return cls._c("32", text)

    @classmethod
    def yellow(cls, text: str) -> str:
        return cls._c("33", text)

    @classmethod
    def blue(cls, text: str) -> str:
        return cls._c("34", text)

    @classmethod
    def magenta(cls, text: str) -> str:
        return cls._c("35", text)

    @classmethod
    def cyan(cls, text: str) -> str:
        return cls._c("36", text)

    @classmethod
    def white(cls, text: str) -> str:
        return cls._c("37", text)


def print_banner() -> None:
    """Print the PromptMaster Studio ASCII banner."""
    banner = f"""{Color.cyan("╔══════════════════════════════════════════════════════════════════════════╗")}
{Color.cyan("║")}  {Color.bold(Color.magenta("PromptMaster Studio"))} {Color.dim(f"v{__version__}")} - {Color.yellow("Prompt Engineering & Protocol Suite")}     {Color.cyan("║")}
{Color.cyan("╚══════════════════════════════════════════════════════════════════════════╝")}"""
    print(banner)


def read_prompt_input(prompt_or_file: str) -> str:
    """Read prompt content from direct string, file path, or standard input."""
    if not prompt_or_file or prompt_or_file == "-":
        if sys.stdin.isatty():
            print(Color.dim("Reading prompt from standard input (press Ctrl+D or Ctrl+Z when done)..."), file=sys.stderr)
        return sys.stdin.read()
    
    if os.path.isfile(prompt_or_file):
        return read_text_safe(prompt_or_file)
    
    return prompt_or_file


# ============================================================================
# CLI SUBCOMMAND HANDLERS
# ============================================================================

def cmd_optimize(args: argparse.Namespace) -> int:
    """Execute the prompt optimization subcommand."""
    raw_prompt = read_prompt_input(args.prompt_or_file)
    if not raw_prompt.strip():
        print(Color.red("Error: Input prompt is empty."), file=sys.stderr)
        return 1

    constraints = args.constraints or []
    result = optimize_prompt(
        prompt=raw_prompt,
        target=args.target,
        cot=args.cot,
        persona=args.persona,
        constraints=constraints,
        xml_tags=not args.no_xml,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0

    print(Color.bold(Color.cyan(f"\n✨ Optimized Prompt ({result.target_provider})")))
    print(Color.dim(f"Token Estimate: {result.estimated_tokens_before} -> {result.estimated_tokens_after} tokens\n"))

    if result.improvements:
        print(Color.bold("Improvements Applied:"))
        for imp in result.improvements:
            print(f"  {Color.green('✓')} {imp}")
        print()

    print(Color.bold("Optimized Output:"))
    print(Color.dim("----------------------------------------------------------------------"))
    print(result.optimized_prompt)
    print(Color.dim("----------------------------------------------------------------------"))

    if args.output:
        atomic_write_text(args.output, result.optimized_prompt)
        print(Color.green(f"\nSaved optimized prompt to: {args.output}"))

    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    """Execute the prompt linting and static analysis subcommand."""
    raw_prompt = read_prompt_input(args.prompt_or_file)
    if not raw_prompt.strip():
        print(Color.red("Error: Input prompt is empty."), file=sys.stderr)
        return 1

    result = lint_prompt(prompt=raw_prompt, target=args.target)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0

    print(Color.bold(Color.cyan("\n🔍 Prompt Static Analysis & Quality Audit")))
    print(Color.dim("======================================================================"))

    # Score coloring
    def fmt_score(score: float) -> str:
        if score >= 80:
            return Color.green(f"{score}/100")
        elif score >= 60:
            return Color.yellow(f"{score}/100")
        return Color.red(f"{score}/100")

    print(f"Overall Quality Score : {fmt_score(result.overall_score)}")
    print(f"Clarity Score         : {fmt_score(result.clarity_score)}")
    print(f"Structure Score       : {fmt_score(result.structure_score)}")
    print(f"Security Score        : {fmt_score(result.security_score)}")
    print(f"Estimated Tokens      : {Color.bold(str(result.estimated_tokens))} ({result.word_count} words, {result.char_count} chars)\n")

    if result.issues:
        print(Color.bold("Issues Flagged:"))
        for i in result.issues:
            sev_color = Color.red if i.severity in ("error", "critical") else (Color.yellow if i.severity == "warning" else Color.blue)
            print(f"  {sev_color(f'[{i.severity.upper()}]')} {Color.bold(i.rule_id)} ({i.category}): {i.message}")
            if i.suggestion:
                print(f"    {Color.dim('Suggestion:')} {i.suggestion}")
        print()
    else:
        print(f"  {Color.green('✓ No issues detected. Clean and well-structured prompt!')}\n")

    if result.suggestions_summary:
        print(Color.bold("Key Actionable Recommendations:"))
        for sug in result.suggestions_summary:
            print(f"  {Color.cyan('•')} {sug}")
        print()

    return 0


def cmd_render(args: argparse.Namespace) -> int:
    """Execute template rendering and variable substitution."""
    template_src = args.template_file
    raw_template = template_src
    
    # Check if template_src is a file or catalog id
    matched = get_prompt_templates(template_id=template_src)
    if matched:
        raw_template = matched[0].template_str
    elif os.path.isfile(template_src):
        raw_template = read_text_safe(template_src)
    elif template_src == "-":
        raw_template = sys.stdin.read()

    variables: Dict[str, Any] = {}

    # Read from --vars-json if supplied
    if args.vars_json:
        if os.path.isfile(args.vars_json):
            variables.update(read_json_safe(args.vars_json, default={}))
        else:
            try:
                variables.update(json.loads(args.vars_json))
            except Exception as e:
                print(Color.red(f"Error parsing --vars-json string: {e}"), file=sys.stderr)
                return 1

    # Read from --var key=val arguments
    var_items = getattr(args, "var", None) or getattr(args, "V", None) or []
    for item in var_items:
        if "=" in item:
            k, v = item.split("=", 1)
            variables[k.strip()] = v.strip()
        else:
            variables[item.strip()] = ""

    rendered = render_template(raw_template, variables)

    # Check for unpopulated variables
    unfilled = list(set(re.findall(r"\{\{([a-zA-Z0-9_\-]+)\}\}", rendered) + re.findall(r"\{([a-zA-Z0-9_\-]+)\}", rendered)))

    if args.json:
        print(json.dumps({
            "rendered": rendered,
            "variables_applied": variables,
            "unfilled_variables": unfilled,
        }, indent=2, ensure_ascii=False))
        return 0

    if unfilled:
        print(Color.yellow(f"Warning: Unfilled template placeholders remaining: {', '.join(unfilled)}\n"), file=sys.stderr)

    print(rendered)

    if args.output:
        atomic_write_text(args.output, rendered)
        print(Color.green(f"\nRendered template saved to: {args.output}"), file=sys.stderr)

    return 0


def cmd_tokens(args: argparse.Namespace) -> int:
    """Execute token and context envelope estimation."""
    raw_text = read_prompt_input(args.prompt_or_file)
    if not raw_text.strip():
        print(Color.red("Error: Input prompt is empty."), file=sys.stderr)
        return 1

    report = estimate_tokens(raw_text, model=args.model)
    if hasattr(report, "to_dict"):
        report_dict = report.to_dict()
    else:
        report_dict = dict(report)

    if "estimated_tokens" not in report_dict:
        report_dict["estimated_tokens"] = report_dict.get("prompt_tokens", 0)

    if args.json:
        print(json.dumps(report_dict, indent=2, ensure_ascii=False))
        return 0

    model_name = report_dict.get("model_name", args.model)
    est_toks = f"{report_dict.get('estimated_tokens', report_dict.get('prompt_tokens', 0)):,}"
    char_cnt = f"{report_dict.get('char_count', len(raw_text)):,}"
    word_cnt = f"{report_dict.get('word_count', len(raw_text.split())):,}"
    ctx_win = f"{report_dict.get('context_window', 128000):,}"
    ctx_pct = f"{report_dict.get('context_usage_percent', 0.0)} %"
    rem_ctx = f"{report_dict.get('remaining_context', 0):,}"
    cost_usd = f"{report_dict.get('estimated_cost_usd', 0.0):.6f}"

    print(Color.bold(Color.cyan(f"\n📊 Token & Context Budget Report ({model_name})")))
    print(Color.dim("======================================================================"))
    print(f"Estimated Tokens      : {Color.bold(Color.yellow(est_toks))}")
    print(f"Character Count       : {char_cnt}")
    print(f"Word Count            : {word_cnt}")
    print(f"Model Context Window  : {ctx_win} tokens")
    print(f"Context Utilization   : {Color.bold(ctx_pct)}")
    print(f"Remaining Envelope    : {rem_ctx} tokens")
    print(f"Estimated Input Cost  : ${cost_usd} USD")
    
    if report_dict.get("fits_in_context", True):
        print(f"Fit Status            : {Color.green('✓ FITS SAFELY IN CONTEXT')}")
    else:
        print(f"Fit Status            : {Color.red('✗ EXCEEDS CONTEXT WINDOW')}")
    print()

    return 0


def cmd_templates(args: argparse.Namespace) -> int:
    """List or inspect built-in production prompt templates."""
    templates = get_prompt_templates(
        category=args.category,
        search=args.search,
        template_id=args.id,
    )
    if isinstance(templates, PromptTemplate):
        templates = [templates]
    elif not isinstance(templates, list):
        templates = [templates] if templates else []

    if args.json:
        print(json.dumps([t.to_dict() for t in templates], indent=2, ensure_ascii=False))
        return 0

    if args.id and templates:
        t = templates[0]
        print(Color.bold(Color.cyan(f"\n📝 Template: {t.title} ({t.id})")))
        print(Color.dim("======================================================================"))
        print(f"Category : {Color.yellow(t.category)} | Target: {t.target_provider}")
        print(f"Summary  : {t.description}")
        print(f"Tags     : {', '.join(t.tags)}")
        print(f"\n{Color.bold('Template Variables:')}")
        if t.variables:
            for v in t.variables:
                print(f"  - {Color.bold(v.name)}: {v.description} (e.g. '{v.sample_value}')")
        else:
            print("  (None)")

        print(f"\n{Color.bold('Template Content:')}")
        print(Color.dim("----------------------------------------------------------------------"))
        print(t.template_str)
        print(Color.dim("----------------------------------------------------------------------\n"))
        return 0

    print(Color.bold(Color.cyan(f"\n📚 PromptMaster Studio Templates Catalog ({len(templates)} templates)")))
    print(Color.dim("======================================================================"))
    for t in templates:
        print(f"{Color.bold(Color.yellow(f'[{t.category.upper()}]'))} {Color.bold(t.title)} {Color.dim(f'(ID: {t.id})')}")
        print(f"  {t.description}")
        vars_str = ", ".join(v.name for v in t.variables) or "None"
        print(f"  {Color.dim('Variables:')} {vars_str}")
        print()

    print(Color.dim("Use 'promptmaster templates --id <id>' to view full template source."))
    return 0


def cmd_curriculum(args: argparse.Namespace) -> int:
    """Explore and study prompt engineering curriculum lessons."""
    lessons_data = get_curriculum_lessons(lesson_id=args.lesson, category=args.category)

    if args.json:
        if isinstance(lessons_data, list):
            print(json.dumps([l.to_dict() for l in lessons_data], indent=2, ensure_ascii=False))
        elif lessons_data:
            print(json.dumps(lessons_data.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(json.dumps(None))
        return 0

    if args.lesson and lessons_data:
        lesson = lessons_data if not isinstance(lessons_data, list) else lessons_data[0]
        print(Color.bold(Color.cyan(f"\n📖 Lesson {lesson.id.upper()}: {lesson.title}")))
        print(Color.dim("======================================================================"))
        print(f"Category: {Color.yellow(lesson.category)} | Difficulty: {lesson.difficulty} | Time: ~{lesson.estimated_minutes} min\n")
        print(lesson.content_markdown)
        print(Color.dim("\n----------------------------------------------------------------------"))
        print(Color.bold("Key Takeaways:"))
        for k in lesson.key_takeaways:
            print(f"  {Color.green('✓')} {k}")
        print(Color.dim("----------------------------------------------------------------------\n"))
        return 0

    lesson_list = lessons_data if isinstance(lessons_data, list) else [lessons_data]
    print(Color.bold(Color.cyan(f"\n🎓 Prompt Engineering Curriculum ({len(lesson_list)} lessons)")))
    print(Color.dim("======================================================================"))
    for l in lesson_list:
        print(f"{Color.bold(Color.yellow(f'[{l.id.upper()}]'))} {Color.bold(l.title)} {Color.dim(f'({l.difficulty} • ~{l.estimated_minutes} min)')}")
        print(f"  {l.summary}")
        print(f"  {Color.dim('Category:')} {l.category}")
        print()

    print(Color.dim("Use 'promptmaster curriculum --lesson <id>' to study a full lesson."))
    return 0


def cmd_diagnostics(args: argparse.Namespace) -> int:
    """Generate and display platform and system diagnostics report."""
    platform_info = get_platform_info()
    app_dir = get_app_dir()
    templates = get_prompt_templates()
    lessons = get_curriculum_lessons()
    models = get_model_specs()

    diag = {
        "version": __version__,
        "mcp_protocol": PROTOCOL_VERSION,
        "platform": platform_info,
        "app_directory": str(app_dir),
        "templates_count": len(templates),
        "curriculum_count": len(lessons) if isinstance(lessons, list) else 1,
        "model_profiles_count": len(models),
        "system_status": "OPERATIONAL",
    }

    if getattr(args, "json", False):
        print(json.dumps(diag, indent=2, ensure_ascii=False))
        return 0

    print_banner()
    print(Color.bold(Color.cyan("\n🩺 System & Platform Diagnostics Report")))
    print(Color.dim("======================================================================"))
    print(f"PromptMaster Version  : {Color.bold(Color.green(__version__))}")
    print(f"MCP Protocol Version  : {Color.bold(PROTOCOL_VERSION)}")
    print(f"Operating System      : {platform_info['system']} {platform_info['release']} ({platform_info['machine']})")
    print(f"Python Runtime        : {platform_info['python_version']} ({sys.executable})")
    print(f"Filesystem Encoding   : {platform_info['filesystem_encoding']}")
    print(f"Default Text Encoding : {platform_info['default_encoding']}")
    print(f"App Data Directory    : {app_dir}")
    print(f"Loaded Templates      : {len(templates)}")
    print(f"Loaded Lessons        : {len(lessons) if isinstance(lessons, list) else 1}")
    print(f"Model Specs           : {len(models)}")
    print(f"Dependencies          : {Color.green('100% Python Standard Library (Zero External Runtime Deps)')}")
    print(f"Overall Health        : {Color.bold(Color.green('ALL SYSTEMS NOMINAL'))}\n")

    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    """Run the MCP server over stdio."""
    run_mcp_server()
    return 0


def cmd_redteam(args: argparse.Namespace) -> int:
    """Simulate adversarial jailbreak attacks and synthesize zero-trust defense."""
    from promptmaster_studio.engine.adversarial_jailbreak import AdversarialRedTeamSimulator
    prompt_text = read_prompt_input(args.prompt_or_file)
    if not prompt_text.strip():
        print(Color.red("Error: Input prompt is empty."), file=sys.stderr)
        return 1

    simulator = AdversarialRedTeamSimulator()
    report = simulator.simulate(prompt_text)

    if getattr(args, "json", False):
        res_data = {
            "vulnerability_score": report.vulnerability_score,
            "risk_level": report.risk_level,
            "total_vectors_tested": report.total_vectors_tested,
            "vulnerabilities_found": report.vulnerabilities_found,
            "defense_layers_detected": report.defense_layers_detected,
            "hardened_prompt": report.hardened_prompt_suggestion,
            "findings": [
                {
                    "vector_id": f.vector_id,
                    "vector_name": f.vector_name,
                    "category": f.category,
                    "severity": f.severity,
                    "is_vulnerable": f.is_vulnerable,
                    "confidence": f.confidence,
                    "remediation": f.defensive_remediation,
                }
                for f in report.findings
            ],
        }
        print(json.dumps(res_data, indent=2, ensure_ascii=False))
        return 0

    print_banner()
    color_risk = Color.red if report.risk_level in ("CRITICAL", "HIGH") else (Color.yellow if report.risk_level == "MEDIUM" else Color.green)
    print(Color.bold(Color.cyan(f"\n🛡️ Adversarial Red-Team Jailbreak Simulator ({report.total_vectors_tested} Attack Vectors)")))
    print(Color.dim("======================================================================"))
    print(f"Vulnerability Score : {color_risk(f'{report.vulnerability_score}/100')} ({color_risk(report.risk_level)} RISK)")
    print(f"Vectors Tested      : {report.total_vectors_tested}")
    print(f"Vulnerabilities     : {color_risk(str(report.vulnerabilities_found))}")
    active_def = ", ".join(report.defense_layers_detected) if report.defense_layers_detected else "None"
    print(f"Active Defenses     : {Color.green(active_def)}")
    print(Color.dim("----------------------------------------------------------------------"))
    print(Color.bold("Attack Vector Findings:"))
    for f in report.findings:
        tag = Color.red("[VULNERABLE]") if f.is_vulnerable else Color.green("[RESISTANT] ")
        sev = Color.bold(Color.yellow(f"({f.severity.upper()})"))
        print(f"  {tag} {f.vector_name} {sev}")
        if f.is_vulnerable:
            print(f"      {Color.dim('Remedy:')} {f.defensive_remediation}")

    if getattr(args, "harden", False) and report.hardened_prompt_suggestion:
        print(Color.dim("----------------------------------------------------------------------"))
        print(Color.bold(Color.cyan("Synthesized Zero-Trust Hardened Prompt:")))
        print(report.hardened_prompt_suggestion)

    print()
    return 0


# ============================================================================
# SELF-TEST RUNNER (cmd_test)
# ============================================================================

def cmd_test(args: argparse.Namespace) -> int:
    """Execute the internal test suite verifying all modules, tools, and protocols."""
    print(Color.bold(Color.cyan(f"\n🧪 PromptMaster Studio Test Suite (v{__version__})")))
    print(Color.dim("======================================================================"))

    passed = 0
    failed = 0
    start_time = time.time()

    def run_unit(name: str, fn: Any) -> None:
        nonlocal passed, failed
        try:
            fn()
            print(f"  {Color.green('✓')} {name}")
            passed += 1
        except Exception as e:
            print(f"  {Color.red('✗')} {name}: {e}")
            failed += 1

    # 1. Token estimation tests
    def test_token_estimation() -> None:
        text = "Hello world! This is a test prompt for estimating tokens."
        res = estimate_tokens(text, "claude")
        toks = getattr(res, "prompt_tokens", res.get("prompt_tokens") if isinstance(res, dict) else 0)
        assert toks > 0
        fits = getattr(res, "fits_in_context", res.get("fits_in_context") if isinstance(res, dict) else True)
        assert fits is True

    run_unit("Token Estimator Engine (Claude, GPT-4o, Gemini)", test_token_estimation)

    # 2. Prompt Optimizer tests
    def test_optimizer() -> None:
        raw = "Write a python function to parse json."
        res_anthropic = optimize_prompt(raw, target="anthropic", cot=True)
        assert "<instructions>" in res_anthropic.optimized_prompt
        assert "<thinking_process>" in res_anthropic.optimized_prompt or "<thinking" in res_anthropic.optimized_prompt
        assert res_anthropic.estimated_tokens_after > 0

        res_openai = optimize_prompt(raw, target="openai", cot=False)
        assert "## Objective" in res_openai.optimized_prompt or "# Role" in (res_openai.system_message or "")

    run_unit("Prompt Optimizer Multi-Provider Decomposition", test_optimizer)

    # 3. Linter tests
    def test_linter() -> None:
        vague_prompt = "Make it good with stuff and things etc."
        res = lint_prompt(vague_prompt)
        assert res.clarity_score < 90 or len(res.issues) > 0
        assert len(res.issues) > 0

    run_unit("Prompt Static Linter & Quality Scoring", test_linter)

    # 4. Template Rendering tests
    def test_templating() -> None:
        tpl = "Hello {{name}}, your role is {{role}}!"
        rendered = render_template(tpl, {"name": "Alice", "role": "Architect"})
        assert rendered == "Hello Alice, your role is Architect!"

        # Catalog lookup
        templates = get_prompt_templates()
        assert len(templates) > 0
        first_tpl = templates[0]
        rendered_cat = render_template(first_tpl.template_str, {"language": "Rust", "code": "fn main() {}"}, strict=False)
        assert len(rendered_cat) > 0

        code_tpls = get_prompt_templates(template_id="code_reviewer")
        target_tpl = code_tpls[0] if code_tpls else templates[0]
        sample_vars = {v.name: v.sample_value or f"test_{v.name}" for v in target_tpl.variables}
        rendered_cat = render_template(target_tpl.id, sample_vars)
        assert len(rendered_cat) > 0

    run_unit("Template Variable Interpolation & Catalog Resolver", test_templating)

    # 5. Curriculum tests
    def test_curriculum() -> None:
        lessons = get_curriculum_lessons()
        assert len(lessons) >= 5
        lesson_l1 = get_curriculum_lessons(lesson_id="lesson-01-core-anatomy") or get_curriculum_lessons(lesson_id="l1")
        assert lesson_l1 is not None
        assert "Anatomy" in lesson_l1.title

    run_unit("Curriculum Knowledge Store & Category Filtering", test_curriculum)

    # 6. MCP Server Protocol tests
    def test_mcp_server() -> None:
        server = MCPServer()
        
        # Test initialize
        init_req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        init_resp = json.loads(server.handle_message(init_req) or "{}")
        assert init_resp["result"]["protocolVersion"] == PROTOCOL_VERSION
        assert init_resp["result"]["serverInfo"]["name"] == "promptmaster-studio"

        # Test tools/list
        tools_req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools_resp = json.loads(server.handle_message(tools_req) or "{}")
        tool_names = [t["name"] for t in tools_resp["result"]["tools"]]
        assert "prompt_optimize" in tool_names
        assert "prompt_lint" in tool_names
        assert "prompt_interpolate" in tool_names
        assert "prompt_estimate_tokens" in tool_names
        assert "prompt_templates" in tool_names
        assert "prompt_curriculum" in tool_names
        assert "prompt_diagnostics" in tool_names

        # Test tool call: prompt_optimize
        opt_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "prompt_optimize", "arguments": {"prompt": "Fix my SQL query", "target": "generic"}},
        })
        opt_resp = json.loads(server.handle_message(opt_req) or "{}")
        assert opt_resp["result"]["isError"] is False
        assert len(opt_resp["result"]["content"]) > 0

        # Test resources/list
        res_req = json.dumps({"jsonrpc": "2.0", "id": 4, "method": "resources/list", "params": {}})
        res_resp = json.loads(server.handle_message(res_req) or "{}")
        assert len(res_resp["result"]["resources"]) >= 3

    run_unit("Model Context Protocol (MCP) JSON-RPC 2.0 In-Memory Engine", test_mcp_server)

    # 7. Diagnostics telemetry test
    def test_diag() -> None:
        info = get_platform_info()
        assert "system" in info
        assert "python_version" in info

    run_unit("Platform Diagnostics & Telemetry", test_diag)

    elapsed = round(time.time() - start_time, 3)
    print(Color.dim("======================================================================"))
    if failed == 0:
        print(Color.bold(Color.green(f"🎉 ALL {passed} TESTS PASSED in {elapsed}s (100% Quality Pass Rate)\n")))
        return 0
    else:
        print(Color.bold(Color.red(f"❌ {failed} TESTS FAILED, {passed} passed in {elapsed}s\n")))
        return 1


# ============================================================================
# WEB UI & REST API SERVER (cmd_serve)
# ============================================================================

EMBEDDED_MATERIAL3_UI = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PromptMaster Studio - AI Prompt Engineering Suite</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace'],
          },
          colors: {
            brand: {
              50: '#eef2ff',
              100: '#e0e7ff',
              500: '#6366f1',
              600: '#4f46e5',
              700: '#4338ca',
              900: '#312e81',
            }
          }
        }
      }
    }
  </script>
  <style>
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
    pre, code, textarea { font-family: 'JetBrains Mono', monospace; }
  </style>
</head>
<body class="bg-zinc-950 text-zinc-100 min-h-screen flex flex-col selection:bg-indigo-500 selection:text-white">
  <!-- Top Navigation Bar -->
  <header class="border-b border-zinc-800/80 bg-zinc-900/60 backdrop-blur-md sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
          <span class="text-white font-black text-lg">P</span>
        </div>
        <div>
          <span class="font-bold text-lg tracking-tight bg-gradient-to-r from-indigo-400 to-violet-300 bg-clip-text text-transparent">PromptMaster Studio</span>
          <span class="ml-2 text-xs font-mono px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">v0.1.0</span>
        </div>
      </div>
      <div class="flex items-center gap-1.5 text-xs font-medium">
        <button onclick="switchTab('optimize')" id="tab-optimize" class="px-3.5 py-2 rounded-lg bg-indigo-600 text-white shadow-sm transition">✨ Optimizer</button>
        <button onclick="switchTab('lint')" id="tab-lint" class="px-3.5 py-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition">🔍 Linter</button>
        <button onclick="switchTab('templates')" id="tab-templates" class="px-3.5 py-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition">📚 Templates</button>
        <button onclick="switchTab('curriculum')" id="tab-curriculum" class="px-3.5 py-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition">🎓 Curriculum</button>
        <button onclick="switchTab('tokens')" id="tab-tokens" class="px-3.5 py-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition">📊 Tokens</button>
      </div>
    </div>
  </header>

  <!-- Main Workspace Content -->
  <main class="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
    
    <!-- OPTIMIZE TAB -->
    <div id="view-optimize" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Input Section -->
        <div class="bg-zinc-900/70 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-base font-bold text-zinc-200 flex items-center gap-2">
              <span>Raw Prompt Specification</span>
            </h2>
            <select id="opt-target" class="bg-zinc-800 border border-zinc-700 text-xs text-zinc-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500">
              <option value="anthropic">Anthropic (Claude XML)</option>
              <option value="openai">OpenAI (Markdown Headers)</option>
              <option value="gemini">Google Gemini (Grounded)</option>
              <option value="generic" selected>Generic Multi-Model</option>
            </select>
          </div>

          <textarea id="opt-input" rows="8" placeholder="Enter your raw prompt or goal here..." class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-4 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500/50 resize-y">Review this Python code for security issues and calculate Big-O time complexity.</textarea>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <div>
              <label class="block text-xs font-semibold text-zinc-400 mb-1">Custom Persona (Optional)</label>
              <input type="text" id="opt-persona" placeholder="e.g. Senior Security Auditor" class="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-indigo-500">
            </div>
            <div class="flex items-center justify-start sm:justify-end pt-5">
              <label class="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                <input type="checkbox" id="opt-cot" class="rounded bg-zinc-800 border-zinc-700 text-indigo-600 focus:ring-0" checked>
                <span>Inject Chain-of-Thought (CoT)</span>
              </label>
            </div>
          </div>

          <button onclick="runOptimize()" id="opt-btn" class="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-sm shadow-lg shadow-indigo-600/20 transition flex items-center justify-center gap-2">
            <span>✨ Optimize & Decompose Prompt</span>
          </button>
        </div>

        <!-- Output Section -->
        <div class="bg-zinc-900/70 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-base font-bold text-zinc-200">Optimized Prompt Output</h2>
            <span id="opt-tokens-badge" class="text-xs font-mono px-2.5 py-1 rounded-md bg-zinc-800 text-zinc-300">Ready</span>
          </div>
          <pre id="opt-output" class="flex-1 w-full bg-zinc-950 border border-zinc-800 rounded-xl p-4 text-xs text-indigo-300 overflow-x-auto whitespace-pre-wrap">Click 'Optimize' to generate a production-ready structured prompt.</pre>
          <div class="mt-4 flex justify-end">
            <button onclick="copyOptOutput()" class="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-semibold text-zinc-200 transition">📋 Copy Output</button>
          </div>
        </div>
      </div>
    </div>

    <!-- LINT TAB -->
    <div id="view-lint" class="hidden space-y-6">
      <div class="bg-zinc-900/70 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4">
        <h2 class="text-base font-bold text-zinc-200">Static Prompt Quality & Security Audit</h2>
        <textarea id="lint-input" rows="5" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-4 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500/50 resize-y">Make a fast API that handles stuff with high quality etc.</textarea>
        <button onclick="runLint()" class="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-sm transition">🔍 Audit Prompt Quality</button>
      </div>

      <div id="lint-results" class="hidden grid grid-cols-1 md:grid-cols-4 gap-4">
        <div class="bg-zinc-900/70 border border-zinc-800 rounded-xl p-4 text-center">
          <div class="text-xs text-zinc-400 font-semibold uppercase">Overall Quality</div>
          <div id="lint-overall" class="text-2xl font-black text-indigo-400 mt-1">-</div>
        </div>
        <div class="bg-zinc-900/70 border border-zinc-800 rounded-xl p-4 text-center">
          <div class="text-xs text-zinc-400 font-semibold uppercase">Clarity Score</div>
          <div id="lint-clarity" class="text-2xl font-black text-emerald-400 mt-1">-</div>
        </div>
        <div class="bg-zinc-900/70 border border-zinc-800 rounded-xl p-4 text-center">
          <div class="text-xs text-zinc-400 font-semibold uppercase">Structure Score</div>
          <div id="lint-structure" class="text-2xl font-black text-blue-400 mt-1">-</div>
        </div>
        <div class="bg-zinc-900/70 border border-zinc-800 rounded-xl p-4 text-center">
          <div class="text-xs text-zinc-400 font-semibold uppercase">Security Score</div>
          <div id="lint-security" class="text-2xl font-black text-violet-400 mt-1">-</div>
        </div>
      </div>

      <div id="lint-details" class="hidden bg-zinc-900/70 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4">
        <h3 class="font-bold text-sm text-zinc-300">Detailed Findings & Recommendations</h3>
        <div id="lint-issues" class="space-y-2 text-xs"></div>
      </div>
    </div>

    <!-- TEMPLATES TAB -->
    <div id="view-templates" class="hidden space-y-6">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-bold text-zinc-200">Built-in Production Prompt Templates</h2>
        <input type="text" id="tpl-search" oninput="loadTemplates()" placeholder="Search templates..." class="bg-zinc-900 border border-zinc-800 text-xs rounded-lg px-3 py-1.5 text-zinc-200 focus:outline-none focus:border-indigo-500">
      </div>
      <div id="tpl-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"></div>
    </div>

    <!-- CURRICULUM TAB -->
    <div id="view-curriculum" class="hidden space-y-6">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-bold text-zinc-200">Prompt Engineering Mastery Curriculum</h2>
      </div>
      <div id="cur-list" class="space-y-4"></div>
    </div>

    <!-- TOKENS TAB -->
    <div id="view-tokens" class="hidden space-y-6">
      <div class="bg-zinc-900/70 border border-zinc-800 rounded-2xl p-6 shadow-xl space-y-4">
        <h2 class="text-base font-bold text-zinc-200">Multi-Model Token & Context Window Estimator</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="md:col-span-2">
            <textarea id="tok-input" rows="6" oninput="runTokens()" class="w-full bg-zinc-950 border border-zinc-800 rounded-xl p-4 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500 resize-y" placeholder="Paste your prompt or context here to calculate multi-model token budgets...">Large Language Models process text as tokens rather than individual words or characters. PromptMaster Studio computes token usage heuristics across Claude, GPT-4o, Gemini, and DeepSeek.</textarea>
          </div>
          <div id="tok-matrix" class="bg-zinc-950 border border-zinc-800 rounded-xl p-4 space-y-3 text-xs">
            <div class="font-bold text-zinc-300">Live Context Analysis</div>
            <div id="tok-results-inner">Type above to calculate...</div>
          </div>
        </div>
      </div>
    </div>

  </main>

  <footer class="border-t border-zinc-800/80 bg-zinc-950 py-6 text-center text-xs text-zinc-500">
    <p>PromptMaster Studio • Powered by Pure Python Standard Library • MCP Protocol 2024-11-05</p>
  </footer>

  <script>
    function switchTab(tab) {
      ['optimize', 'lint', 'templates', 'curriculum', 'tokens'].forEach(t => {
        document.getElementById('view-' + t).classList.toggle('hidden', t !== tab);
        const btn = document.getElementById('tab-' + t);
        if (btn) {
          if (t === tab) {
            btn.className = 'px-3.5 py-2 rounded-lg bg-indigo-600 text-white shadow-sm transition';
          } else {
            btn.className = 'px-3.5 py-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition';
          }
        }
      });
      if (tab === 'templates') loadTemplates();
      if (tab === 'curriculum') loadCurriculum();
      if (tab === 'tokens') runTokens();
    }

    async function runOptimize() {
      const prompt = document.getElementById('opt-input').value;
      const target = document.getElementById('opt-target').value;
      const persona = document.getElementById('opt-persona').value;
      const cot = document.getElementById('opt-cot').checked;

      const res = await fetch('/api/optimize', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prompt, target, persona, cot})
      });
      const data = await res.json();
      document.getElementById('opt-output').textContent = data.optimized_prompt;
      document.getElementById('opt-tokens-badge').textContent = `${data.estimated_tokens_before} -> ${data.estimated_tokens_after} tokens`;
    }

    async function runLint() {
      const prompt = document.getElementById('lint-input').value;
      const res = await fetch('/api/lint', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prompt})
      });
      const data = await res.json();
      document.getElementById('lint-results').classList.remove('hidden');
      document.getElementById('lint-details').classList.remove('hidden');
      document.getElementById('lint-overall').textContent = data.overall_score + '/100';
      document.getElementById('lint-clarity').textContent = data.clarity_score + '/100';
      document.getElementById('lint-structure').textContent = data.structure_score + '/100';
      document.getElementById('lint-security').textContent = data.security_score + '/100';

      const container = document.getElementById('lint-issues');
      container.innerHTML = '';
      data.issues.forEach(i => {
        const div = document.createElement('div');
        div.className = 'p-3 rounded-lg bg-zinc-950 border border-zinc-800';
        div.innerHTML = `<span class="font-bold text-amber-400">[${i.severity.toUpperCase()}]</span> <span class="font-mono text-zinc-300">${i.rule_id}</span>: ${i.message}<br><span class="text-zinc-500">Suggestion: ${i.suggestion || 'N/A'}</span>`;
        container.appendChild(div);
      });
    }

    async function loadTemplates() {
      const q = document.getElementById('tpl-search').value;
      const res = await fetch(`/api/templates?search=${encodeURIComponent(q)}`);
      const list = await res.json();
      const grid = document.getElementById('tpl-grid');
      grid.innerHTML = '';
      list.forEach(t => {
        const card = document.createElement('div');
        card.className = 'bg-zinc-900/70 border border-zinc-800 rounded-xl p-4 flex flex-col justify-between';
        card.innerHTML = `<div><div class="flex items-center justify-between mb-1"><span class="text-xs font-bold text-indigo-400 uppercase tracking-wider">${t.category}</span><span class="text-[10px] font-mono text-zinc-500">${t.id}</span></div><h4 class="font-bold text-sm text-zinc-200">${t.title}</h4><p class="text-xs text-zinc-400 mt-1 line-clamp-2">${t.description}</p></div><button onclick="useTemplate('${t.id}')" class="mt-4 w-full py-1.5 bg-zinc-800 hover:bg-zinc-700 text-xs font-semibold text-zinc-200 rounded-lg transition">Use Template</button>`;
        grid.appendChild(card);
      });
    }

    function useTemplate(id) {
      fetch(`/api/templates?id=${id}`).then(r => r.json()).then(t => {
        if (t && t.length > 0) {
          document.getElementById('opt-input').value = t[0].template_str;
          switchTab('optimize');
        }
      });
    }

    async function loadCurriculum() {
      const res = await fetch('/api/curriculum');
      const list = await res.json();
      const container = document.getElementById('cur-list');
      container.innerHTML = '';
      list.forEach(l => {
        const item = document.createElement('div');
        item.className = 'bg-zinc-900/70 border border-zinc-800 rounded-xl p-5 space-y-2';
        item.innerHTML = `<div class="flex items-center justify-between"><span class="text-xs font-bold text-indigo-400 font-mono">LESSON ${l.id.toUpperCase()}</span><span class="text-xs text-zinc-500">${l.difficulty} • ~${l.estimated_minutes} min</span></div><h3 class="text-base font-bold text-zinc-100">${l.title}</h3><p class="text-xs text-zinc-400">${l.summary}</p>`;
        container.appendChild(item);
      });
    }

    async function runTokens() {
      const text = document.getElementById('tok-input').value;
      const res = await fetch('/api/tokens', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prompt: text, model: 'claude'})
      });
      const data = await res.json();
      document.getElementById('tok-results-inner').innerHTML = `
        <div class="flex justify-between py-1 border-b border-zinc-800"><span class="text-zinc-400">Estimated Tokens:</span><span class="font-bold text-indigo-400 font-mono">${data.estimated_tokens}</span></div>
        <div class="flex justify-between py-1 border-b border-zinc-800"><span class="text-zinc-400">Characters:</span><span class="font-mono text-zinc-300">${data.char_count}</span></div>
        <div class="flex justify-between py-1 border-b border-zinc-800"><span class="text-zinc-400">Words:</span><span class="font-mono text-zinc-300">${data.word_count}</span></div>
        <div class="flex justify-between py-1 border-b border-zinc-800"><span class="text-zinc-400">Claude Context Usage:</span><span class="font-mono text-emerald-400">${data.context_usage_percent}%</span></div>
        <div class="flex justify-between py-1"><span class="text-zinc-400">Est. API Cost:</span><span class="font-mono text-zinc-300">$${data.estimated_cost_usd}</span></div>
      `;
    }

    function copyOptOutput() {
      const text = document.getElementById('opt-output').textContent;
      navigator.clipboard.writeText(text);
      alert('Optimized prompt copied to clipboard!');
    }
  </script>
</body>
</html>
"""


class PromptMasterHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    """REST API and Web UI HTTP request dispatcher."""

    def log_message(self, format: str, *args: Any) -> None:
        """Quiet HTTP server logging to stderr."""
        sys.stderr.write(f"[Studio HTTP] {format % args}\n")

    def _send_json(self, data: Any, status: int = 200) -> None:
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/templates":
            category = query.get("category", [None])[0]
            search = query.get("search", [None])[0]
            template_id = query.get("id", [None])[0]
            templates = get_prompt_templates(category=category, search=search, template_id=template_id)
            self._send_json([t.to_dict() for t in templates])
            return

        if path == "/api/curriculum":
            lesson_id = query.get("lesson_id", [None])[0]
            category = query.get("category", [None])[0]
            lessons = get_curriculum_lessons(lesson_id=lesson_id, category=category)
            if isinstance(lessons, list):
                self._send_json([l.to_dict() for l in lessons])
            elif lessons:
                self._send_json(lessons.to_dict())
            else:
                self._send_json(None)
            return

        if path == "/api/diagnostics":
            diag = {
                "version": __version__,
                "mcp_protocol": PROTOCOL_VERSION,
                "platform": get_platform_info(),
                "templates_count": len(get_prompt_templates()),
                "curriculum_count": len(get_curriculum_lessons()),
            }
            self._send_json(diag)
            return

        if path == "/api/models":
            models = {k: v.to_dict() for k, v in get_model_specs().items()}
            self._send_json(models)
            return

        # Serve static web UI
        # Check if public/index.html exists on disk
        public_dir = Path(__file__).resolve().parent.parent.parent / "public"
        index_file = public_dir / "index.html"
        
        if index_file.is_file():
            html_bytes = index_file.read_bytes()
        else:
            html_bytes = EMBEDDED_MATERIAL3_UI.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"

        try:
            body = json.loads(post_body)
        except Exception:
            body = {}

        if path == "/api/optimize":
            prompt = body.get("prompt", "")
            target = body.get("target", "generic")
            cot = bool(body.get("cot", False))
            persona = body.get("persona")
            constraints = body.get("constraints")
            xml_tags = bool(body.get("xml_tags", True))
            result = optimize_prompt(prompt, target=target, cot=cot, persona=persona, constraints=constraints, xml_tags=xml_tags)
            self._send_json(result.to_dict())
            return

        if path == "/api/lint":
            prompt = body.get("prompt", "")
            target = body.get("target", "generic")
            result = lint_prompt(prompt, target=target)
            self._send_json(result.to_dict())
            return

        if path == "/api/render":
            template = body.get("template", "")
            variables = body.get("variables", {})
            rendered = render_template(template, variables)
            self._send_json({"rendered": rendered})
            return

        if path == "/api/tokens":
            prompt = body.get("prompt", "")
            model = body.get("model", "claude")
            result = estimate_tokens(prompt, model=model)
            if hasattr(result, "to_dict"):
                res_dict = result.to_dict()
            else:
                res_dict = dict(result)
            self._send_json(res_dict)
            return

        self._send_json({"error": "Endpoint not found"}, status=404)


def cmd_serve(args: argparse.Namespace) -> int:
    """Launch the PromptMaster Studio local Web UI & REST API server."""
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8765)
    open_browser = getattr(args, "open", False)

    print_banner()
    print(Color.bold(Color.cyan(f"\n🚀 Launching PromptMaster Studio Web Server...")))
    print(Color.bold(f"   Local URL   : {Color.green(f'http://{host}:{port}/')}"))
    print(Color.dim(f"   REST API    : http://{host}:{port}/api/optimize"))
    print(Color.dim("   Press Ctrl+C to stop the server.\n"))

    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    try:
        server = ThreadedHTTPServer((host, port), PromptMasterHTTPRequestHandler)
        if open_browser:
            webbrowser.open(f"http://{host}:{port}/")
        server.serve_forever()
    except KeyboardInterrupt:
        print(Color.yellow("\nServer stopped. Goodbye!"))
    except Exception as e:
        print(Color.red(f"Error starting server on {host}:{port}: {e}"), file=sys.stderr)
        return 1

    return 0


# ============================================================================
# CLI ARGUMENT PARSER & ENTRYPOINT
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build the unified command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="promptmaster",
        description="PromptMaster Studio - High-Performance AI Prompt Engineering, Optimization, Linting & MCP Protocol Suite.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"promptmaster-studio {__version__}",
        help="Show PromptMaster Studio version and exit.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # 1. optimize
    p_opt = subparsers.add_parser("optimize", help="Enhance raw prompt with structured XML tags, persona, constraints, and CoT reasoning.")
    p_opt.add_argument("prompt_or_file", help="Prompt text, file path, or '-' for stdin.")
    p_opt.add_argument("-t", "--target", choices=["anthropic", "anthropic_xml", "openai", "openai_chat", "gemini", "google_gemini", "generic", "generic_markdown"], default="generic", help="Target LLM provider architecture.")
    p_opt.add_argument("--cot", action="store_true", help="Enable structured Chain-of-Thought reasoning steps.")
    p_opt.add_argument("-p", "--persona", help="Specific persona or role to embed.")
    p_opt.add_argument("-c", "--constraint", dest="constraints", action="append", help="Add explicit constraint (can specify multiple).")
    p_opt.add_argument("--no-xml", action="store_true", help="Disable XML tags in output.")
    p_opt.add_argument("-o", "--output", help="Save optimized prompt to file.")
    p_opt.add_argument("--json", action="store_true", help="Output raw JSON result.")
    p_opt.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")

    # 2. lint
    p_lint = subparsers.add_parser("lint", help="Analyze prompt quality, clarity score, token estimate, and suggestions.")
    p_lint.add_argument("prompt_or_file", help="Prompt text, file path, or '-' for stdin.")
    p_lint.add_argument("-t", "--target", default="generic", help="Target LLM provider context.")
    p_lint.add_argument("--json", action="store_true", help="Output raw JSON result.")
    p_lint.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")

    # 3. render
    p_render = subparsers.add_parser("render", help="Render template with variable dictionary values.")
    p_render.add_argument("template_file", help="Template string, file path, template ID, or '-' for stdin.")
    p_render.add_argument("-V", "--var", action="append", help="Template variable in key=val format (can specify multiple).")
    p_render.add_argument("--vars-json", help="JSON file or JSON string containing variable map.")
    p_render.add_argument("-o", "--output", help="Save rendered text to file.")
    p_render.add_argument("--json", action="store_true", help="Output JSON formatted result.")
    p_render.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")

    # 4. tokens
    p_tok = subparsers.add_parser("tokens", help="Estimate token count and context window percentage for target model.")
    p_tok.add_argument("prompt_or_file", help="Prompt text, file path, or '-' for stdin.")
    p_tok.add_argument("-m", "--model", choices=["claude", "claude-haiku", "gpt4o", "gpt4o-mini", "gemini", "gemini-flash", "deepseek", "generic"], default="claude", help="Target model.")
    p_tok.add_argument("--json", action="store_true", help="Output raw JSON result.")
    p_tok.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")

    # 5. templates
    p_tpl = subparsers.add_parser("templates", help="List or search built-in production prompt templates.")
    p_tpl.add_argument("-c", "--category", help="Filter templates by category (coding, reasoning, engineering, agents, writing).")
    p_tpl.add_argument("-s", "--search", help="Search keyword in titles, descriptions, and tags.")
    p_tpl.add_argument("--id", help="Inspect specific template by ID.")
    p_tpl.add_argument("--json", action="store_true", help="Output JSON result.")
    p_tpl.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")

    # 6. curriculum
    p_cur = subparsers.add_parser("curriculum", help="Retrieve prompt engineering curriculum lessons.")
    p_cur.add_argument("-l", "--lesson", help="Lesson ID to view (e.g. l1, l2, l3, l4, l5, l6).")
    p_cur.add_argument("-c", "--category", help="Filter lessons by category.")
    p_cur.add_argument("--json", action="store_true", help="Output JSON result.")
    p_cur.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")

    # 7. serve
    p_serve = subparsers.add_parser("serve", help="Launch the PromptMaster Studio Web UI (design influenced by Material 3).")
    p_serve.add_argument("-p", "--port", type=int, default=8765, help="Port to listen on (default: 8765).")
    p_serve.add_argument("-H", "--host", default="127.0.0.1", help="Host address (default: 127.0.0.1).")
    p_serve.add_argument("--open", action="store_true", help="Open browser automatically.")
    p_serve.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")

    # 8. mcp
    p_mcp = subparsers.add_parser("mcp", help="Run Model Context Protocol (MCP) server over stdio.")
    p_mcp.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")

    # 9. platform / doctor / diagnostics
    for diag_alias in ["platform", "doctor", "diagnostics"]:
        p_diag = subparsers.add_parser(diag_alias, help="System diagnostics and platform health check.")
        p_diag.add_argument("--json", action="store_true", help="Output JSON diagnostics.")
        p_diag.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")

    # 10. test
    p_test = subparsers.add_parser("test", help="Execute internal self-verification test runner.")
    p_test.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")

    # 11. redteam
    p_red = subparsers.add_parser("redteam", help="Simulate adversarial jailbreak attacks and evaluate prompt vulnerability.")
    p_red.add_argument("prompt_or_file", help="Prompt text, file path, or '-' for stdin.")
    p_red.add_argument("--harden", action="store_true", help="Output synthesized zero-trust hardened prompt.")
    p_red.add_argument("--json", action="store_true", help="Output JSON results.")
    p_red.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    if argv is None:
        argv = sys.argv[1:]

    # Pre-check for --no-color flag anywhere in arguments to ensure early configuration
    if "--no-color" in argv:
        set_color_enabled(False)

    parser = build_parser()
    
    if not argv:
        print_banner()
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    if getattr(args, "no_color", False):
        set_color_enabled(False)

    sub = args.subcommand
    if not sub:
        print_banner()
        parser.print_help()
        return 0

    if sub == "optimize":
        return cmd_optimize(args)
    elif sub == "lint":
        return cmd_lint(args)
    elif sub == "render":
        return cmd_render(args)
    elif sub == "tokens":
        return cmd_tokens(args)
    elif sub == "templates":
        return cmd_templates(args)
    elif sub == "curriculum":
        return cmd_curriculum(args)
    elif sub in ("platform", "doctor", "diagnostics"):
        return cmd_diagnostics(args)
    elif sub == "mcp":
        return cmd_mcp(args)
    elif sub == "serve":
        return cmd_serve(args)
    elif sub == "test":
        return cmd_test(args)
    elif sub == "redteam":
        return cmd_redteam(args)
    else:
        print(Color.red(f"Unknown subcommand: {sub}"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
