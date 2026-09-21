<div align="center">

# ⚡ PromptMaster Studio

**Zero-dependency Prompt Engineering & Meta-Optimization Suite**

[![CI](https://github.com/1nc0gn30/promptmaster-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/1nc0gn30/promptmaster-studio/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Compliant](https://img.shields.io/badge/MCP-2024--11--05-green.svg)](https://modelcontextprotocol.io/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0%20external-brightgreen.svg)](https://pypi.org/project/promptmaster-studio/)
[![Tests](https://img.shields.io/badge/tests-233%20passed-success.svg)](https://github.com/1nc0gn30/promptmaster-studio)

*From ad-hoc prompts to production-grade prompt engineering — built with 100% Python Standard Library.*

---

</div>

## 🎨 Studio UI

<p align="center">
  <img src="public/screenshots/studio-main.png" width="900" alt="PromptMaster Studio — Main Interface" />
</p>

<p align="center">
  <img src="public/screenshots/studio-optimized.png" width="900" alt="PromptMaster Studio — Optimized Output" />
</p>

<div align="center">

| Optimize Studio | Prompt Diff | Version History |
|:---:|:---:|:---:|
| Meta-optimize raw prompts into enterprise XML/CoT format | Side-by-side comparison with token delta & cost analysis | Git-like version control with branches & rollback |

</div>

<p align="center">
  <img src="public/screenshots/studio-diff.png" width="900" alt="PromptMaster Studio — Diff Engine" />
</p>

<p align="center">
  <img src="public/screenshots/studio-history.png" width="900" alt="PromptMaster Studio — Version History" />
</p>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [CLI Reference](#-cli-reference)
- [MCP Server](#-mcp-server)
- [Studio UI](#-studio-ui)
- [Prompt Engineering Guide](#-prompt-engineering-architecture-guide)
- [Testing](#-testing)
- [License](#-license)

---

## 🌟 Overview

**PromptMaster Studio v3** is an enterprise-grade toolkit built strictly with the **Python Standard Library (100% zero external runtime dependencies)**. It transforms prompt design from ad-hoc experimentation into rigorous, testable software engineering — with diff engines, version history, context optimization, provider migration, and a Material 3-inspired studio UI.

---

## 🏛 Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Client Interfaces                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  Studio Web   │  │  CLI         │  │  MCP Clients          │  │
│  │  UI           │  │  (promptmaster)│  │  (Claude/Cursor)     │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘  │
└─────────┼─────────────────┼──────────────────────┼──────────────┘
          │                 │                      │
┌─────────┼─────────────────┼──────────────────────┼──────────────┐
│                     Server & Protocol Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  UI HTTP     │  │  CLI         │  │  MCP JSON-RPC         │  │
│  │  REST Server │  │  Dispatcher  │  │  Stdio Server         │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘  │
└─────────┼─────────────────┼──────────────────────┼──────────────┘
          │                 │                      │
┌─────────┼─────────────────┼──────────────────────┼──────────────┐
│                    Core Engine Layer (Pure Stdlib)                │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Meta-Optimizer │ Linter │ Token Estimator │ Curriculum DB │ │
│  │  CoVe Engine    │ Debate │ Diff Engine     │ Version Hist  │ │
│  │  Red-Team Sim   │ Template│ Context Optim. │ Provider Mig. │ │
│  │  Batch Proc.    │ Scoring │ Export Fmt.    │ Enhanced Hist │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/1nc0gn30/promptmaster-studio.git
cd promptmaster-studio

# Install in editable mode
pip install -e .

# Verify zero external dependencies
python -c "import promptmaster_studio; print('⚡ PromptMaster ready!')"
```

---

## 🛠 CLI Reference

### Core Commands

| Command | Description |
|---|---|
| `optimize` | Transform raw prompt into enterprise XML/CoT format |
| `lint` | Static lint audit for clarity, security, structure |
| `render` | Render Mustache templates with variable interpolation |
| `tokens` | Multi-model token & cost estimation |
| `diff` | Side-by-side prompt comparison with token delta |

### Advanced Commands

| Command | Description |
|---|---|
| `context` | Analyze & optimize for context window limits |
| `migrate` | Convert between provider formats (Anthropic/OpenAI/Gemini/Mistral/Cohere) |
| `batch` | Process prompt batches through configurable pipelines |
| `score` | Multi-dimensional rubric scoring (A–F grade) |
| `export` | Export as JSON/YAML/Markdown/env-file |
| `history` | Git-like version control with branches & rollback |

### Example Session

```bash
# 1. Optimize a prompt for Claude
promptmaster optimize "Write a sorting function" --target anthropic --cot

# 2. Lint the result
promptmaster lint "<instructions>You are an expert. Write a sorting function.</instructions>"

# 3. Compare two versions
promptmaster diff "Write a sort function" "<instructions>You are an expert. Write a sort function.</instructions>" --model mistral-large-2

# 4. Check context window fit
promptmaster context "<instructions>...</instructions>" --model mistral-7b --analyze

# 5. Migrate to OpenAI format
promptmaster migrate "<instructions>Code review</instructions>" --target openai

# 6. Score prompt quality
promptmaster score "<instructions>You are a Principal Architect.- Analyze code</instructions>"

# 7. Save version
promptmaster history save "<instructions>v1 prompt</instructions>" --label "v1" --message "Initial"

# 8. Export as YAML
promptmaster export "<instructions>Prompt</instructions>" --format yaml --metadata "author=neo,v=1"
```

---

## 🔌 MCP Server

**14+ native tools** for Claude Desktop, Cursor, and Cline.

### Setup (Claude Desktop)

```json
{
  "mcpServers": {
    "promptmaster": {
      "command": "python",
      "args": ["-m", "promptmaster_studio.mcp_server"]
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|---|---|
| `prompt_optimize` | Enterprise XML/CoT structuring |
| `prompt_lint` | Clarity & security audit |
| `prompt_interpolate` | Template rendering |
| `prompt_estimate_tokens` | Token budget calculation |
| `prompt_diff` | Side-by-side comparison |
| `prompt_context_optimize` | Context window optimization |
| `prompt_migrate` | Provider format conversion |
| `prompt_score` | Rubric scoring |
| `prompt_version_history` | Version control operations |
| `prompt_redteam` | Jailbreak simulation |
| `prompt_chain_of_verification` | CoVe hallucination prevention |
| `prompt_multi_agent_debate` | Debate ensemble synthesis |
| `prompt_templates` | Template directory |
| `prompt_curriculum` | Interactive lessons |
| `prompt_diagnostics` | System health & telemetry |

---

## 🎨 Studio UI

Launch the embedded visual development studio:

```bash
promptmaster serve --port 8000
```

Visit **`http://localhost:8000/`**

### Features

- **Dual-Pane Editor** — Type raw prompts, see live XML/CoT transformations
- **Real-Time Quality Gauges** — Clarity, Structure, Security meters
- **Token & Cost Calculator** — Multi-model pricing estimates
- **Live Variable Interpolation** — Auto-detect `{{ variables }}`
- **Diff Engine** — Side-by-side prompt comparison with results
- **Version History** — Save, branch, compare, rollback versions
- **Curriculum Drawer** — Interactive prompt engineering lessons

---

## 🧠 Prompt Engineering Architecture Guide

### 1. Anthropic Claude (XML Semantic Delimiters)
Anthropic models perform best when instructions, context, and input data are enclosed in semantic XML tags:
```xml
<instructions>
Execute the requested analysis with maximum rigor.
</instructions>

<context>
{{ background_material }}
</context>

<constraints>
- Maintain factual precision.
- Do not extrapolate beyond verified context.
</constraints>

<output_format>
Provide response in GitHub-flavored Markdown.
</output_format>
```

### 2. OpenAI (System / Developer Message Decomposition)
OpenAI models benefit from explicit role definition and Markdown headers:
```markdown
# Role & Directive
You are a Principal Software Architect.

## Instructions
- Analyze system bottlenecks.
- Provide modular code refactorings.

## Output Format
RFC 8259 compliant JSON.
```

### 3. Google Gemini (Grounded Instructions)
Gemini excels with grounded structural priming and boundary rules:
```markdown
# Task: Financial Document Analysis
## Guidelines & Instructions
- Extract all line-item revenues and operating margins.
## Operational Boundaries
* State "Insufficient information" if data is absent.
```

---

## 🧪 Testing

```bash
pytest --verbose
# 233 tests covering all engines
```

---

## 📄 License

MIT License. Built with ❤️ for enterprise prompt engineers.
