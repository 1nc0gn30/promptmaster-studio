"""PromptMaster Studio v3 — Context Window Optimizer, Provider Migration,
Prompt Batch Processor, Scoring Rubric, and Enhanced History.

All engines are pure Python standard library.
"""

from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from promptmaster_studio.engine.tokenizer_estimator import MODEL_CATALOG, TokenizerEstimator
from promptmaster_studio.engine.version_history import PromptVersionHistory, PromptVersion


# =============================================================================
# CONTEXT WINDOW OPTIMIZER
# =============================================================================

@dataclass
class ContextWindowPlan:
    """Optimization plan for fitting a prompt within context limits."""
    target_model: str
    original_tokens: int
    optimized_tokens: int
    context_window: int
    max_output_tokens: int
    available_input_tokens: int
    original_text: str
    optimized_text: str
    actions_taken: List[str]
    warnings: List[str]
    section_tokens: Dict[str, int]
    truncation_applied: bool = False


class ContextWindowOptimizer:
    """Optimizes prompts to fit within model context window limits."""

    SEGMENT_PATTERNS = [
        (re.compile(r'<instructions>(.*?)</instructions>', re.DOTALL), "instructions", 1),
        (re.compile(r'<context>(.*?)</context>', re.DOTALL), "context", 2),
        (re.compile(r'<constraints>(.*?)</constraints>', re.DOTALL), "constraints", 1),
        (re.compile(r'<output_format>(.*?)</output_format>', re.DOTALL), "output_format", 1),
        (re.compile(r'<examples>(.*?)</examples>', re.DOTALL), "examples", 3),
        (re.compile(r'<anti_hallucination>(.*?)</anti_hallucination>', re.DOTALL), "anti_hallucination", 2),
        (re.compile(r'<role>(.*?)</role>', re.DOTALL), "role", 1),
    ]

    PRIORITY_ORDER = [
        "role", "instructions", "output_format", "anti_hallucination",
        "context", "constraints", "examples",
    ]

    @classmethod
    def analyze(cls, text: str, model_name: str = "gpt-4o") -> Dict[str, Any]:
        """Analyze token usage across segments."""
        spec = MODEL_CATALOG.get(model_name)
        if not spec:
            raise ValueError(f"Unknown model: {model_name}")

        total_tokens = TokenizerEstimator.count_tokens(text, spec.family.lower() if spec.family else "general")
        available = spec.context_window - spec.max_output_tokens

        segments = {}
        for pattern, name, priority in cls.SEGMENT_PATTERNS:
            match = pattern.search(text)
            if match:
                seg_text = match.group(1)
                seg_tokens = TokenizerEstimator.count_tokens(seg_text, spec.family.lower() if spec.family else "general")
                segments[name] = {"tokens": seg_tokens, "priority": priority, "text": seg_text}

        # Classify non-segment text
        remaining = text
        for pattern, _, _ in cls.SEGMENT_PATTERNS:
            remaining = pattern.sub("", remaining)
        remaining_tokens = TokenizerEstimator.count_tokens(remaining.strip(), spec.family.lower() if spec.family else "general")
        if remaining_tokens > 0:
            segments["other"] = {"tokens": remaining_tokens, "priority": 0, "text": remaining.strip()}

        return {
            "model": model_name,
            "total_tokens": total_tokens,
            "context_window": spec.context_window,
            "max_output": spec.max_output_tokens,
            "available_input": available,
            "fits": total_tokens <= available,
            "overage": max(0, total_tokens - available),
            "segments": segments,
            "headroom": max(0, available - total_tokens),
        }

    @classmethod
    def optimize(cls, text: str, model_name: str = "gpt-4o", reserve_tokens: int = 0) -> ContextWindowPlan:
        """Generate an optimized plan to fit text within context window."""
        spec = MODEL_CATALOG.get(model_name)
        if not spec:
            raise ValueError(f"Unknown model: {model_name}")

        family = spec.family.lower() if spec.family else "general"
        original_tokens = TokenizerEstimator.count_tokens(text, family)
        available = spec.context_window - spec.max_output_tokens - reserve_tokens

        actions = []
        warnings = []
        section_tokens = {}

        # Quick check
        if original_tokens <= available:
            return ContextWindowPlan(
                target_model=model_name,
                original_tokens=original_tokens,
                optimized_tokens=original_tokens,
                context_window=spec.context_window,
                max_output_tokens=spec.max_output_tokens,
                available_input_tokens=available,
                original_text=text,
                optimized_text=text,
                actions_taken=["No optimization needed — fits within context."],
                warnings=[],
                section_tokens={},
            )

        # Extract segments and calculate tokens
        segments = {}
        for pattern, name, priority in cls.SEGMENT_PATTERNS:
            match = pattern.search(text)
            if match:
                seg_text = match.group(1)
                seg_tokens = TokenizerEstimator.count_tokens(seg_text, family)
                segments[name] = {
                    "tokens": seg_tokens,
                    "priority": priority,
                    "text": seg_text,
                    "full_match": match.group(0),
                }
                section_tokens[name] = seg_tokens

        # Calculate overage
        total_used = sum(s["tokens"] for s in segments.values())
        remaining_text = text
        for s in segments.values():
            remaining_text = remaining_text.replace(s["full_match"], "")
        other_tokens = TokenizerEstimator.count_tokens(remaining_text.strip(), family)
        total_used += other_tokens
        section_tokens["other"] = other_tokens

        overage = total_used - available

        if overage <= 0:
            return ContextWindowPlan(
                target_model=model_name,
                original_tokens=original_tokens,
                optimized_tokens=original_tokens,
                context_window=spec.context_window,
                max_output_tokens=spec.max_output_tokens,
                available_input_tokens=available,
                original_text=text,
                optimized_text=text,
                actions_taken=["Already fits within context."],
                warnings=[],
                section_tokens=section_tokens,
            )

        # Apply optimizations in priority order
        optimized = text

        # Step 1: Condense verbose patterns
        condense_patterns = [
            (re.compile(r'\n{3,}'), '\n\n', "Removed excessive blank lines"),
            (re.compile(r'[ \t]+'), ' ', "Removed extra whitespace"),
            (re.compile(r'(\n\s*)+\n'), '\n\n', "Normalized indentation"),
        ]
        for pat, repl, desc in condense_patterns:
            new_text = pat.sub(repl, optimized)
            if new_text != optimized:
                actions.append(desc)
                optimized = new_text

        # Recount after condense
        new_tokens = TokenizerEstimator.count_tokens(optimized, family)
        if new_tokens <= available:
            return ContextWindowPlan(
                target_model=model_name,
                original_tokens=original_tokens,
                optimized_tokens=new_tokens,
                context_window=spec.context_window,
                max_output_tokens=spec.max_output_tokens,
                available_input_tokens=available,
                original_text=text,
                optimized_text=optimized,
                actions_taken=actions,
                warnings=[],
                section_tokens=section_tokens,
            )

        # Step 2: Try to reduce low-priority segments (examples first, then context)
        for segment_name in ["examples", "context", "constraints"]:
            if segment_name in segments:
                seg_info = segments[segment_name]
                # Try compressing by removing bullet points or shortening
                compressed = re.sub(r'- .*?(\n|$)', '', seg_info["full_match"])
                compressed = re.sub(r'\s+', ' ', compressed).strip()
                compressed_tokens = TokenizerEstimator.count_tokens(compressed, family)

                if compressed_tokens < seg_info["tokens"]:
                    saving = seg_info["tokens"] - compressed_tokens
                    actions.append(f"Compressed '{segment_name}' section (saved ~{saving} tokens)")
                    optimized = optimized.replace(seg_info["full_match"], compressed)
                    segments[segment_name]["tokens"] = compressed_tokens

                current_tokens = TokenizerEstimator.count_tokens(optimized, family)
                if current_tokens <= available:
                    return ContextWindowPlan(
                        target_model=model_name,
                        original_tokens=original_tokens,
                        optimized_tokens=current_tokens,
                        context_window=spec.context_window,
                        max_output_tokens=spec.max_output_tokens,
                        available_input_tokens=available,
                        original_text=text,
                        optimized_text=optimized,
                        actions_taken=actions,
                        warnings=[],
                        section_tokens=section_tokens,
                    )

        # Step 3: Truncate remaining sections by priority (lowest first)
        current_tokens = TokenizerEstimator.count_tokens(optimized, family)
        truncation_applied = False

        if current_tokens > available:
            sorted_segments = sorted(segments.items(), key=lambda x: -x[1]["priority"])
            for seg_name, seg_info in sorted_segments:
                if seg_name == "instructions" or seg_name == "role":
                    continue  # Never truncate core sections

                if current_tokens <= available:
                    break

                # Truncate to 50%
                truncated_text = seg_info["text"][:len(seg_info["text"])//2]
                truncated_text = truncated_text.rsplit('.', 1)[0] + '...' if '.' in truncated_text else truncated_text[:100] + "..."
                new_seg_full = seg_info["full_match"].replace(seg_info["text"], truncated_text)
                new_seg_tokens = TokenizerEstimator.count_tokens(truncated_text, family)

                saving = seg_info["tokens"] - new_seg_tokens
                if saving > 0:
                    actions.append(f"Truncated '{segment_name}' to 50% (saved ~{saving} tokens)")
                    optimized = optimized.replace(seg_info["full_match"], new_seg_full)
                    current_tokens -= saving
                    truncation_applied = True

        # Final check
        final_tokens = TokenizerEstimator.count_tokens(optimized, family)
        if final_tokens > available:
            warnings.append(f"Still {final_tokens - available} tokens over limit. Consider splitting into multiple prompts.")

        return ContextWindowPlan(
            target_model=model_name,
            original_tokens=original_tokens,
            optimized_tokens=final_tokens,
            context_window=spec.context_window,
            max_output_tokens=spec.max_output_tokens,
            available_input_tokens=available,
            original_text=text,
            optimized_text=optimized,
            actions_taken=actions,
            warnings=warnings,
            section_tokens=section_tokens,
            truncation_applied=truncation_applied,
        )


# =============================================================================
# PROVIDER MIGRATION ENGINE
# =============================================================================

@dataclass
class MigrationResult:
    """Result of migrating a prompt from one provider format to another."""
    source_provider: str
    target_provider: str
    original_text: str
    migrated_text: str
    changes: List[str]
    warnings: List[str]
    tokens_before: int
    tokens_after: int


class ProviderMigrator:
    """Migrates prompts between provider-specific formats."""

    PROVIDER_FORMATS = {
        "anthropic": {
            "name": "Anthropic Claude",
            "system_tag": "<system>",
            "instruction_tag": "instructions",
            "context_tag": "context",
            "constraint_tag": "constraints",
            "output_tag": "output_format",
            "example_tag": "examples",
            "anti_hallucination_tag": "anti_hallucination",
            "role_prefix": "You are",
            "uses_xml": True,
            "uses_markdown": False,
        },
        "openai": {
            "name": "OpenAI",
            "system_tag": "# System",
            "instruction_tag": "## Instructions",
            "context_tag": "## Context",
            "constraint_tag": "## Constraints",
            "output_tag": "## Output Format",
            "example_tag": "## Examples",
            "anti_hallucination_tag": "## Anti-Hallucination Rules",
            "role_prefix": "You are",
            "uses_xml": False,
            "uses_markdown": True,
        },
        "gemini": {
            "name": "Google Gemini",
            "system_tag": "# System",
            "instruction_tag": "## Guidelines & Instructions",
            "context_tag": "## Context",
            "constraint_tag": "## Operational Boundaries",
            "output_tag": "## Output Format",
            "example_tag": "## Examples",
            "anti_hallucination_tag": "## Factual Integrity Rules",
            "role_prefix": "You are",
            "uses_xml": False,
            "uses_markdown": True,
        },
        "mistral": {
            "name": "Mistral",
            "system_tag": "[SYSTEM]",
            "instruction_tag": "## Instructions",
            "context_tag": "## Context",
            "constraint_tag": "## Constraints",
            "output_tag": "## Output Format",
            "example_tag": "## Examples",
            "anti_hallucination_tag": "## Verification Rules",
            "role_prefix": "You are",
            "uses_xml": False,
            "uses_markdown": True,
        },
        "cohere": {
            "name": "Cohere",
            "system_tag": "# System",
            "instruction_tag": "## Instructions",
            "context_tag": "## Context",
            "constraint_tag": "## Constraints",
            "output_tag": "## Output Format",
            "example_tag": "## Examples",
            "anti_hallucination_tag": "## Factual Grounding",
            "role_prefix": "You are",
            "uses_xml": False,
            "uses_markdown": True,
        },
    }

    @classmethod
    def migrate(cls, text: str, target: str, source: Optional[str] = None) -> MigrationResult:
        """Migrate a prompt to a target provider format."""
        target_fmt = cls.PROVIDER_FORMATS.get(target.lower())
        if not target_fmt:
            raise ValueError(f"Unknown target provider: {target}. Available: {list(cls.PROVIDER_FORMATS.keys())}")

        changes = []
        warnings = []

        # Detect source format if not specified
        if source is None:
            source = cls._detect_format(text)
            changes.append(f"Auto-detected source format: {cls.PROVIDER_FORMATS[source]['name']}")

        source_fmt = cls.PROVIDER_FORMATS.get(source.lower())
        if not source_fmt:
            source_fmt = cls.PROVIDER_FORMATS["anthropic"]  # Default

        # Extract content from source format
        sections = cls._extract_sections(text, source_fmt)

        # Rebuild in target format
        migrated = cls._build_target(sections, target_fmt, changes, warnings)

        # Calculate tokens
        family = target.capitalize()
        tokens_before = TokenizerEstimator.count_tokens(text, family)
        tokens_after = TokenizerEstimator.count_tokens(migrated, family)

        return MigrationResult(
            source_provider=source_fmt["name"],
            target_provider=target_fmt["name"],
            original_text=text,
            migrated_text=migrated,
            changes=changes,
            warnings=warnings,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
        )

    @classmethod
    def _detect_format(cls, text: str) -> str:
        """Detect the provider format of a prompt."""
        if re.search(r'<instructions>.*?</instructions>', text, re.DOTALL):
            return "anthropic"
        if re.search(r'## Guidelines & Instructions', text):
            return "gemini"
        if re.search(r'\[SYSTEM\]', text):
            return "mistral"
        if re.search(r'## Factual Grounding', text):
            return "cohere"
        if re.search(r'# System', text):
            return "openai"
        return "anthropic"  # Default

    @classmethod
    def _extract_sections(cls, text: str, fmt: Dict[str, Any]) -> Dict[str, str]:
        """Extract content sections from source format."""
        sections = {}

        if fmt["uses_xml"]:
            # Extract XML sections
            for key in ["instruction", "context", "constraint", "output", "example", "anti_hallucination", "role"]:
                tag = fmt.get(f"{key}_tag", key)
                pattern = re.compile(rf'<{tag}>(.*?)</{tag}>', re.DOTALL)
                match = pattern.search(text)
                if match:
                    sections[key] = match.group(1).strip()
        else:
            # Extract markdown sections
            for key in ["instruction", "context", "constraint", "output", "example", "anti_hallucination"]:
                tag = fmt.get(f"{key}_tag", f"## {key.title()}")
                pattern = re.compile(rf'{re.escape(tag)}\n(.*?)(?=\n## |\n# |\Z)', re.DOTALL)
                match = pattern.search(text)
                if match:
                    sections[key] = match.group(1).strip()

        # Extract role
        role_match = re.search(r'(?i)you are\s+([^.]+)', text)
        if role_match:
            sections["role"] = role_match.group(0).strip()

        return sections

    @classmethod
    def _build_target(cls, sections: Dict[str, str], fmt: Dict[str, Any], changes: List[str], warnings: List[str]) -> str:
        """Build prompt in target format."""
        parts = []

        # Role
        if "role" in sections:
            parts.append(sections["role"])
            parts.append("")

        # Instructions
        if "instruction" in sections:
            tag = fmt["instruction_tag"]
            if fmt["uses_xml"]:
                parts.append(f"<{tag}>\n{sections['instruction']}\n</{tag}>")
            else:
                parts.append(f"{tag}\n{sections['instruction']}")
            parts.append("")

        # Context
        if "context" in sections:
            tag = fmt["context_tag"]
            if fmt["uses_xml"]:
                parts.append(f"<{tag}>\n{sections['context']}\n</{tag}>")
            else:
                parts.append(f"{tag}\n{sections['context']}")
            parts.append("")

        # Constraints
        if "constraint" in sections:
            tag = fmt["constraint_tag"]
            if fmt["uses_xml"]:
                parts.append(f"<{tag}>\n{sections['constraint']}\n</{tag}>")
            else:
                parts.append(f"{tag}\n{sections['constraint']}")
            parts.append("")

        # Output format
        if "output" in sections:
            tag = fmt["output_tag"]
            if fmt["uses_xml"]:
                parts.append(f"<{tag}>\n{sections['output']}\n</{tag}>")
            else:
                parts.append(f"{tag}\n{sections['output']}")
            parts.append("")

        # Examples
        if "example" in sections:
            tag = fmt["example_tag"]
            if fmt["uses_xml"]:
                parts.append(f"<{tag}>\n{sections['example']}\n</{tag}>")
            else:
                parts.append(f"{tag}\n{sections['example']}")
            parts.append("")

        # Anti-hallucination
        if "anti_hallucination" in sections:
            tag = fmt["anti_hallucination_tag"]
            if fmt["uses_xml"]:
                parts.append(f"<{tag}>\n{sections['anti_hallucination']}\n</{tag}>")
            else:
                parts.append(f"{tag}\n{sections['anti_hallucination']}")
            parts.append("")

        if fmt["uses_xml"] and not parts:
            warnings.append("No XML sections found. Wrapping entire content in <instructions>.")
            parts.append(f"<instructions>\n{sections.get('raw', '')}\n</instructions>")

        return "\n".join(parts).strip()


# =============================================================================
# BATCH PROCESSOR
# =============================================================================

@dataclass
class BatchResult:
    """Result of processing a batch of prompts."""
    total: int
    processed: int
    errors: int
    results: List[Dict[str, Any]]
    summary: Dict[str, Any]


class PromptBatchProcessor:
    """Process multiple prompts through the same pipeline."""

    @staticmethod
    def process_batch(
        prompts: List[str],
        operations: List[str],
        model: str = "gpt-4o",
    ) -> BatchResult:
        """Process a batch of prompts through specified operations."""
        from promptmaster_studio.engine.linter import PromptLinter
        from promptmaster_studio.engine.meta_optimizer import MetaOptimizer
        from promptmaster_studio.engine.template_engine import PromptTemplateEngine

        results = []
        errors = 0
        total_tokens_before = 0
        total_tokens_after = 0

        for i, prompt in enumerate(prompts):
            entry = {"index": i, "original": prompt, "status": "ok"}

            try:
                current = prompt
                entry_results = {}

                for op in operations:
                    if op == "lint":
                        linter = PromptLinter()
                        lint_result = linter.lint(current)
                        entry_results["lint"] = {
                            "overall_score": lint_result.overall_score,
                            "issues_count": len(lint_result.issues),
                        }

                    elif op == "optimize":
                        optimizer = MetaOptimizer()
                        opt_result = optimizer.optimize(current, target_provider="anthropic_xml")
                        entry_results["optimize"] = {
                            "strategy": opt_result.strategy_used,
                            "tokens_before": opt_result.estimated_tokens_before,
                            "tokens_after": opt_result.estimated_tokens_after,
                        }
                        current = opt_result.optimized_prompt

                    elif op == "tokens":
                        tokens = TokenizerEstimator.count_tokens(current, model)
                        entry_results["tokens"] = {"count": tokens}

                    elif op == "context_check":
                        analysis = ContextWindowOptimizer.analyze(current, model)
                        entry_results["context_check"] = {
                            "fits": analysis["fits"],
                            "overage": analysis["overage"],
                        }

                    elif op == "render":
                        engine = PromptTemplateEngine()
                        rendered = engine.render(current, {})
                        entry_results["render"] = {"output": rendered}
                        current = rendered

                entry["results"] = entry_results
                entry["final_text"] = current

                # Track token totals
                tokens_before = TokenizerEstimator.count_tokens(prompt, model)
                tokens_after = TokenizerEstimator.count_tokens(current, model)
                total_tokens_before += tokens_before
                total_tokens_after += tokens_after

            except Exception as e:
                entry["status"] = "error"
                entry["error"] = str(e)
                errors += 1

            results.append(entry)

        return BatchResult(
            total=len(prompts),
            processed=len(prompts) - errors,
            errors=errors,
            results=results,
            summary={
                "total_tokens_before": total_tokens_before,
                "total_tokens_after": total_tokens_after,
                "token_delta": total_tokens_after - total_tokens_before,
                "operations_applied": operations,
                "model": model,
            },
        )


# =============================================================================
# SCORING RUBRIC
# =============================================================================

@dataclass
class RubricScore:
    """Detailed scoring rubric for a prompt."""
    overall: float
    dimensions: Dict[str, float]
    grade: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]


class PromptScoringRubric:
    """Multi-dimensional prompt quality scoring rubric."""

    DIMENSIONS = {
        "clarity": {
            "weight": 0.25,
            "description": "Clear, unambiguous language",
            "checks": [
                (lambda t: len(t.split()) >= 10, "Prompt is too short (< 10 words)", 10),
                (lambda t: not re.search(r'\b(kindly|please|just|maybe|stuff|things)\b', t, re.I), "Contains vague language", 15),
                (lambda t: re.search(r'[!?.]', t), "No clear sentence structure", 5),
            ],
        },
        "specificity": {
            "weight": 0.20,
            "description": "Specific, detailed instructions",
            "checks": [
                (lambda t: re.search(r'\b(must|should|will|shall)\b', t, re.I), "No explicit directives", 10),
                (lambda t: re.search(r'\d+', t), "No numeric constraints", 5),
                (lambda t: len(re.findall(r'\n-|\n\d+\.', t)) >= 2, "Few structured points", 10),
            ],
        },
        "structure": {
            "weight": 0.20,
            "description": "Well-organized with clear sections",
            "checks": [
                (lambda t: re.search(r'<[a-z_]+>|<h[1-6]|## ', t), "No structural markers", 15),
                (lambda t: t.count('\n') >= 3, "Too little formatting", 10),
                (lambda t: re.search(r'<instructions>|<context>|<constraints>', t), "Missing key sections", 10),
            ],
        },
        "safety": {
            "weight": 0.15,
            "description": "No injection vectors or unsafe patterns",
            "checks": [
                (lambda t: not re.search(r'ignore.*(?:previous|above|system)', t, re.I), "Potential injection vector", 20),
                (lambda t: not re.search(r'(?:api[_-]?key|password|secret)\s*[:=]', t, re.I), "Potential credential leak", 25),
                (lambda t: not re.search(r'<script|javascript:|on\w+\s*=', t, re.I), "Potential XSS vector", 25),
            ],
        },
        "efficiency": {
            "weight": 0.10,
            "description": "Concise without unnecessary verbosity",
            "checks": [
                (lambda t: len(t) < 4000, "Prompt is very long (> 4000 chars)", 10),
                (lambda t: t.count(' ') / max(len(t), 1) > 0.1, "Low word density", 5),
                (lambda t: not re.search(r'\b(very|really|just|quite|somewhat)\b', t, re.I), "Contains filler words", 5),
            ],
        },
        "completeness": {
            "weight": 0.10,
            "description": "Includes all necessary components",
            "checks": [
                (lambda t: re.search(r'you are|your role|act as', t, re.I), "No role definition", 10),
                (lambda t: re.search(r'output|format|respond|return', t, re.I), "No output specification", 10),
                (lambda t: re.search(r'<examples>|## examples|example:', t, re.I), "No examples provided", 5),
            ],
        },
    }

    @classmethod
    def score(cls, text: str) -> RubricScore:
        """Score a prompt across all dimensions."""
        dimensions = {}
        strengths = []
        weaknesses = []
        recommendations = []

        for dim_name, config in cls.DIMENSIONS.items():
            score = 100.0
            for check_fn, fail_msg, penalty in config["checks"]:
                if not check_fn(text):
                    score -= penalty
                    weaknesses.append(f"{dim_name}: {fail_msg}")
                else:
                    strengths.append(f"{dim_name}: {fail_msg.replace('No ', 'Has ').replace('Missing ', 'Has ')}")

            dimensions[dim_name] = max(0, min(100, score))

        # Calculate weighted overall
        overall = sum(
            dimensions[dim] * cls.DIMENSIONS[dim]["weight"]
            for dim in dimensions
        )

        # Grade
        if overall >= 90:
            grade = "A"
        elif overall >= 80:
            grade = "B"
        elif overall >= 70:
            grade = "C"
        elif overall >= 60:
            grade = "D"
        else:
            grade = "F"

        # Recommendations
        for dim_name, score in dimensions.items():
            if score < 70:
                recommendations.append(f"Improve {dim_name}: {cls.DIMENSIONS[dim_name]['description']}")

        return RubricScore(
            overall=round(overall, 1),
            dimensions={k: round(v, 1) for k, v in dimensions.items()},
            grade=grade,
            strengths=list(set(strengths))[:5],
            weaknesses=list(set(weaknesses))[:5],
            recommendations=recommendations[:3],
        )


# =============================================================================
# ENHANCED HISTORY WITH TAGGING
# =============================================================================

class EnhancedHistory(PromptVersionHistory):
    """Extended version history with tagging and search capabilities."""

    def save_with_analysis(self, prompt_text: str, **kwargs) -> PromptVersion:
        """Save a version with automatic analysis."""
        from promptmaster_studio.engine.linter import PromptLinter
        from promptmaster_studio.engine.prompt_diff import extract_tags, extract_variables

        # Auto-analyze
        linter = PromptLinter()
        lint_result = linter.lint(prompt_text)

        tags = extract_tags(prompt_text)
        variables = extract_variables(prompt_text)

        metadata = kwargs.get("metadata", {})
        metadata["lint_score"] = lint_result.overall_score
        metadata["issues_count"] = len(lint_result.issues)
        metadata["tags"] = tags
        metadata["variables"] = variables
        kwargs["metadata"] = metadata

        return self.save_version(prompt_text, **kwargs)

    def find_by_tag(self, tag: str) -> List[PromptVersion]:
        """Find versions containing a specific tag."""
        results = []
        for vid, raw in self._data.get("versions", {}).items():
            tags = raw.get("metadata", {}).get("tags", [])
            if tag in tags:
                results.append(PromptVersion.from_dict(raw))
        return results

    def find_by_score(self, min_score: float = 80.0) -> List[PromptVersion]:
        """Find versions with a minimum lint score."""
        results = []
        for vid, raw in self._data.get("versions", {}).items():
            score = raw.get("metadata", {}).get("lint_score", 0)
            if score >= min_score:
                results.append(PromptVersion.from_dict(raw))
        return results

    def get_best_version(self, branch: str = "main") -> Optional[PromptVersion]:
        """Get the highest-scoring version on a branch."""
        versions = [v for v in self.list_versions(branch=branch)]
        if not versions:
            return None
        return max(versions, key=lambda v: v.metadata.get("lint_score", 0))


# =============================================================================
# EXPORT FORMATTER
# =============================================================================

class ExportFormatter:
    """Export prompts in various formats."""

    @staticmethod
    def to_json(text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Export as JSON."""
        import json
        data = {
            "version": "3.0",
            "prompt": text,
            "metadata": metadata or {},
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    @staticmethod
    def to_yaml(text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Export as YAML (pure Python implementation)."""
        lines = []
        lines.append("---")
        lines.append("version: '3.0'")
        lines.append("prompt: |")
        for line in text.split("\n"):
            lines.append(f"  {line}")
        if metadata:
            lines.append("metadata:")
            for k, v in metadata.items():
                if isinstance(v, list):
                    lines.append(f"  {k}:")
                    for item in v:
                        lines.append(f"    - {item}")
                else:
                    lines.append(f"  {k}: {v}")
        lines.append("---")
        return "\n".join(lines)

    @staticmethod
    def to_markdown(text: str, title: str = "Prompt", metadata: Optional[Dict[str, Any]] = None) -> str:
        """Export as Markdown document."""
        lines = [
            f"# {title}",
            "",
            "## Prompt",
            "",
            "```",
            text,
            "```",
        ]
        if metadata:
            lines.append("")
            lines.append("## Metadata")
            lines.append("")
            for k, v in metadata.items():
                if isinstance(v, list):
                    lines.append(f"### {k}")
                    for item in v:
                        lines.append(f"- {item}")
                else:
                    lines.append(f"- **{k}**: {v}")
        return "\n".join(lines)

    @staticmethod
    def to_env_file(text: str, var_name: str = "PROMPT") -> str:
        """Export as environment variable file."""
        import base64
        encoded = base64.b64encode(text.encode()).decode()
        return f'{var_name}={encoded}\n# Decode: echo ${var_name} | base64 -d'


__all__ = [
    "ContextWindowOptimizer",
    "ContextWindowPlan",
    "ProviderMigrator",
    "MigrationResult",
    "PromptBatchProcessor",
    "BatchResult",
    "PromptScoringRubric",
    "RubricScore",
    "EnhancedHistory",
    "ExportFormatter",
]
