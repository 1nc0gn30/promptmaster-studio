"""Prompt comparison and structural diff engine.

Compares two prompts side-by-side and computes:
- Token count delta and cost delta
- Structural score delta (tags, sections, variables)
- Line-by-line unified diff
- Variable overlap analysis
- Tag coverage comparison
100% Python Standard Library.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from promptmaster_studio.engine.linter import PromptLinter
from promptmaster_studio.engine.tokenizer_estimator import TokenizerEstimator


@dataclass
class PromptDiffEntry:
    """A single line-level diff entry."""
    line_type: str  # "added", "removed", "unchanged", "modified"
    left_line_no: Optional[int]
    right_line_no: Optional[int]
    left_text: str
    right_text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_type": self.line_type,
            "left_line_no": self.left_line_no,
            "right_line_no": self.right_line_no,
            "left_text": self.left_text,
            "right_text": self.right_text,
        }


@dataclass
class PromptComparisonResult:
    """Comprehensive comparison between two prompts."""
    left_prompt: str
    right_prompt: str
    left_tokens: int
    right_tokens: int
    token_delta: int
    token_delta_percent: float
    left_variables: List[str]
    right_variables: List[str]
    shared_variables: List[str]
    left_only_variables: List[str]
    right_only_variables: List[str]
    left_tags: List[str]
    right_tags: List[str]
    shared_tags: List[str]
    left_only_tags: List[str]
    right_only_tags: List[str]
    left_linter_score: float
    right_linter_score: float
    score_delta: float
    line_diff: List[PromptDiffEntry]
    similarity_ratio: float
    left_cost_usd: Dict[str, float] = field(default_factory=dict)
    right_cost_usd: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "left_prompt_preview": self.left_prompt[:200],
            "right_prompt_preview": self.right_prompt[:200],
            "left_tokens": self.left_tokens,
            "right_tokens": self.right_tokens,
            "token_delta": self.token_delta,
            "token_delta_percent": round(self.token_delta_percent, 2),
            "left_variables": self.left_variables,
            "right_variables": self.right_variables,
            "shared_variables": self.shared_variables,
            "left_only_variables": self.left_only_variables,
            "right_only_variables": self.right_only_variables,
            "left_tags": self.left_tags,
            "right_tags": self.right_tags,
            "shared_tags": self.shared_tags,
            "left_only_tags": self.left_only_tags,
            "right_only_tags": self.right_only_tags,
            "left_linter_score": self.left_linter_score,
            "right_linter_score": self.right_linter_score,
            "score_delta": round(self.score_delta, 2),
            "similarity_ratio": round(self.similarity_ratio, 3),
            "left_cost_usd": {k: round(v, 6) for k, v in self.left_cost_usd.items()},
            "right_cost_usd": {k: round(v, 6) for k, v in self.right_cost_usd.items()},
            "diff_summary": {
                "added_lines": sum(1 for d in self.line_diff if d.line_type == "added"),
                "removed_lines": sum(1 for d in self.line_diff if d.line_type == "removed"),
                "modified_lines": sum(1 for d in self.line_diff if d.line_type == "modified"),
                "unchanged_lines": sum(1 for d in self.line_diff if d.line_type == "unchanged"),
            },
        }


# XML/Markdown structural tag patterns
TAG_PATTERNS = [
    re.compile(r"<([a-zA-Z0-9_-]+)[\s>]"),  # XML tags
    re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE),  # Markdown headers
    re.compile(r"^###\s+(.+)$", re.MULTILINE),  # H3 specifically
]

VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*(?:\||:-|:|\}\})")


def extract_variables(text: str) -> List[str]:
    """Extract template variable names from prompt text."""
    return sorted(set(VARIABLE_PATTERN.findall(text)))


def extract_tags(text: str) -> List[str]:
    """Extract XML tags and markdown header identifiers."""
    tags = set()
    for match in re.finditer(r"<([a-zA-Z0-9_-]+)[\s>]", text):
        tags.add(f"<{match.group(1)}>")
    for match in re.finditer(r"^#{1,6}\s+(.+)$", text, re.MULTILINE):
        tags.add(match.group(0).strip())
    return sorted(tags)


def compute_line_diff(left_text: str, right_text: str) -> List[PromptDiffEntry]:
    """Compute a unified line-by-line diff between two prompts."""
    left_lines = left_text.splitlines(keepends=False)
    right_lines = right_text.splitlines(keepends=False)

    # Use difflib.SequenceMatcher for structural diff
    sm = difflib.SequenceMatcher(None, left_lines, right_lines, autojunk=False)
    entries: List[PromptDiffEntry] = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                entries.append(PromptDiffEntry(
                    line_type="unchanged",
                    left_line_no=i1 + offset + 1,
                    right_line_no=j1 + offset + 1,
                    left_text=left_lines[i1 + offset],
                    right_text=right_lines[j1 + offset],
                ))
        elif tag == "delete":
            for offset in range(i2 - i1):
                entries.append(PromptDiffEntry(
                    line_type="removed",
                    left_line_no=i1 + offset + 1,
                    right_line_no=None,
                    left_text=left_lines[i1 + offset],
                    right_text="",
                ))
        elif tag == "insert":
            for offset in range(j2 - j1):
                entries.append(PromptDiffEntry(
                    line_type="added",
                    left_line_no=None,
                    right_line_no=j1 + offset + 1,
                    left_text="",
                    right_text=right_lines[j1 + offset],
                ))
        elif tag == "replace":
            # Pair up lines where possible, mark extras as added/removed
            left_chunk = left_lines[i1:i2]
            right_chunk = right_lines[j1:j2]
            max_len = max(len(left_chunk), len(right_chunk))
            for k in range(max_len):
                l_txt = left_chunk[k] if k < len(left_chunk) else ""
                r_txt = right_chunk[k] if k < len(right_chunk) else ""
                has_left = k < len(left_chunk)
                has_right = k < len(right_chunk)
                if has_left and has_right:
                    line_type = "modified"
                elif has_left:
                    line_type = "removed"
                else:
                    line_type = "added"
                entries.append(PromptDiffEntry(
                    line_type=line_type,
                    left_line_no=(i1 + k + 1) if has_left else None,
                    right_line_no=(j1 + k + 1) if has_right else None,
                    left_text=l_txt,
                    right_text=r_txt,
                ))

    return entries


def compute_similarity(left_text: str, right_text: str) -> float:
    """Compute a quick similarity ratio between two prompts."""
    return difflib.SequenceMatcher(
        None, left_text, right_text, autojunk=False
    ).ratio()


def compare_prompts(
    left_prompt: str,
    right_prompt: str,
    model_name: str = "gpt-4o",
    compare_costs: bool = True,
) -> PromptComparisonResult:
    """Compare two prompts and return a comprehensive comparison report.

    Args:
        left_prompt: Original or baseline prompt text.
        right_prompt: Modified or candidate prompt text.
        model_name: Model for cost estimation.
        compare_costs: Whether to compute cost comparison across multiple models.

    Returns:
        PromptComparisonResult with all comparison metrics.
    """
    tokenizer = TokenizerEstimator()
    linter = PromptLinter()

    left_tokens = tokenizer.count_tokens(left_prompt, model_name)
    right_tokens = tokenizer.count_tokens(right_prompt, model_name)
    token_delta = right_tokens - left_tokens

    if left_tokens > 0:
        token_delta_percent = (token_delta / left_tokens) * 100.0
    else:
        token_delta_percent = 0.0 if right_tokens == 0 else 100.0

    # Lint both prompts
    left_lint = linter.lint(left_prompt)
    right_lint = linter.lint(right_prompt)
    score_delta = right_lint.overall_score - left_lint.overall_score

    # Variables
    left_vars = extract_variables(left_prompt)
    right_vars = extract_variables(right_prompt)
    shared_vars = sorted(set(left_vars) & set(right_vars))
    left_only_vars = sorted(set(left_vars) - set(right_vars))
    right_only_vars = sorted(set(right_vars) - set(left_vars))

    # Tags
    left_tags = extract_tags(left_prompt)
    right_tags = extract_tags(right_prompt)
    shared_tags = sorted(set(left_tags) & set(right_tags))
    left_only_tags = sorted(set(left_tags) - set(right_tags))
    right_only_tags = sorted(set(right_tags) - set(left_tags))

    # Line diff
    line_diff = compute_line_diff(left_prompt, right_prompt)

    # Similarity
    similarity = compute_similarity(left_prompt, right_prompt)

    # Cost comparison
    left_costs: Dict[str, float] = {}
    right_costs: Dict[str, float] = {}
    if compare_costs:
        for m in ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"]:
            left_costs[m] = tokenizer.analyze_budget(left_prompt, m).estimated_cost_usd
            right_costs[m] = tokenizer.analyze_budget(right_prompt, m).estimated_cost_usd

    return PromptComparisonResult(
        left_prompt=left_prompt,
        right_prompt=right_prompt,
        left_tokens=left_tokens,
        right_tokens=right_tokens,
        token_delta=token_delta,
        token_delta_percent=token_delta_percent,
        left_variables=left_vars,
        right_variables=right_vars,
        shared_variables=shared_vars,
        left_only_variables=left_only_vars,
        right_only_variables=right_only_vars,
        left_tags=left_tags,
        right_tags=right_tags,
        shared_tags=shared_tags,
        left_only_tags=left_only_tags,
        right_only_tags=right_only_tags,
        left_linter_score=left_lint.overall_score,
        right_linter_score=right_lint.overall_score,
        score_delta=score_delta,
        line_diff=line_diff,
        similarity_ratio=similarity,
        left_cost_usd=left_costs,
        right_cost_usd=right_costs,
    )


def format_comparison_report(result: PromptComparisonResult) -> str:
    """Format a PromptComparisonResult as a human-readable text report."""
    lines: List[str] = []

    lines.append("=" * 72)
    lines.append("  PROMPT COMPARISON REPORT")
    lines.append("=" * 72)

    # Token section
    lines.append("")
    lines.append("TOKEN ANALYSIS:")
    lines.append(f"  Left  : {result.left_tokens:,} tokens")
    lines.append(f"  Right : {result.right_tokens:,} tokens")
    delta_str = f"+{result.token_delta}" if result.token_delta >= 0 else str(result.token_delta)
    pct_str = f"+{result.token_delta_percent:.1f}%" if result.token_delta_percent >= 0 else f"{result.token_delta_percent:.1f}%"
    lines.append(f"  Delta : {delta_str} tokens ({pct_str})")

    # Quality section
    lines.append("")
    lines.append("QUALITY SCORE:")
    lines.append(f"  Left  : {result.left_linter_score:.1f}/100")
    lines.append(f"  Right : {result.right_linter_score:.1f}/100")
    score_str = f"+{result.score_delta:.1f}" if result.score_delta >= 0 else f"{result.score_delta:.1f}"
    lines.append(f"  Delta : {score_str} points")

    # Similarity
    lines.append("")
    lines.append(f"SIMILARITY RATIO: {result.similarity_ratio:.1%}")

    # Variables
    lines.append("")
    lines.append("VARIABLES:")
    lines.append(f"  Shared ({len(result.shared_variables)}): {', '.join(result.shared_variables) or 'None'}")
    if result.left_only_variables:
        lines.append(f"  Left Only  ({len(result.left_only_variables)}): {', '.join(result.left_only_variables)}")
    if result.right_only_variables:
        lines.append(f"  Right Only ({len(result.right_only_variables)}): {', '.join(result.right_only_variables)}")

    # Tags
    lines.append("")
    lines.append("STRUCTURAL TAGS:")
    lines.append(f"  Shared ({len(result.shared_tags)}): {', '.join(result.shared_tags) or 'None'}")
    if result.left_only_tags:
        lines.append(f"  Left Only  ({len(result.left_only_tags)}): {', '.join(result.left_only_tags)}")
    if result.right_only_tags:
        lines.append(f"  Right Only ({len(result.right_only_tags)}): {', '.join(result.right_only_tags)}")

    # Cost comparison
    if result.left_cost_usd:
        lines.append("")
        lines.append("COST COMPARISON (input only, per query):")
        for model in result.left_cost_usd:
            lc = result.left_cost_usd[model]
            rc = result.right_cost_usd[model]
            diff = rc - lc
            diff_str = f"+${diff:.6f}" if diff >= 0 else f"-${abs(diff):.6f}"
            lines.append(f"  {model:25s}: ${lc:.6f} -> ${rc:.6f} ({diff_str})")

    # Diff summary
    lines.append("")
    diff_summary = {
        "added": sum(1 for d in result.line_diff if d.line_type == "added"),
        "removed": sum(1 for d in result.line_diff if d.line_type == "removed"),
        "modified": sum(1 for d in result.line_diff if d.line_type == "modified"),
        "unchanged": sum(1 for d in result.line_diff if d.line_type == "unchanged"),
    }
    lines.append("DIFF SUMMARY:")
    lines.append(f"  Added    : {diff_summary['added']}")
    lines.append(f"  Removed  : {diff_summary['removed']}")
    lines.append(f"  Modified : {diff_summary['modified']}")
    lines.append(f"  Unchanged: {diff_summary['unchanged']}")

    # Unified diff preview (first 30 lines)
    lines.append("")
    lines.append("UNIFIED DIFF (preview):")
    lines.append("-" * 72)
    shown = 0
    for entry in result.line_diff[:50]:
        if entry.line_type == "removed":
            lines.append(f"  - {entry.left_text[:80]}")
        elif entry.line_type == "added":
            lines.append(f"  + {entry.right_text[:80]}")
        elif entry.line_type == "modified":
            lines.append(f"  - {entry.left_text[:80]}")
            lines.append(f"  + {entry.right_text[:80]}")
        shown += 1
    if len(result.line_diff) > 50:
        lines.append(f"  ... ({len(result.line_diff) - 50} more lines)")
    lines.append("-" * 72)

    lines.append("")
    return "\n".join(lines)
