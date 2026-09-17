"""Static prompt quality analyzer, safety inspector, and scoring engine.

Evaluates prompts across clarity, security, formatting, constraint balance,
and structural integrity using 15+ specialized heuristic rules.
100% Python Standard Library.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from promptmaster_studio.engine.tokenizer_estimator import TokenizerEstimator
from promptmaster_studio.models import (
    LinterCategory,
    LinterIssue,
    LinterSeverity,
    PromptAnalysisResult,
)


class PromptLinter:
    """Production static analyzer for LLM prompts."""

    # Ambiguous adjectives, adverbs, and vague directives
    VAGUE_TERMS_PATTERNS: List[Tuple[str, str, str]] = [
        (r"\b(?:make it|write it|be)\s+(?:good|better|nice|awesome|great)\b", "Vague quality adjective", "Specify concrete quality criteria (e.g., 'Ensure O(n) time complexity', 'Follow PEP-8 standards')."),
        (r"\b(?:stuff|things|and so on|etc\.?|and more)\b", "Ambiguous catch-all phrase", "List specific items, parameters, or edge cases explicitly instead of using catch-alls."),
        (r"\b(?:as much as possible|as best (?:as )?you can|to the best of your ability)\b", "Subjective ability appeal", "Provide deterministic completion targets or concrete evaluation constraints."),
        (r"\b(?:make it pop|eye-catching|clean code|high quality)\b", "Subjective aesthetic goal", "Define precise structural, stylistic, or performance metrics."),
        (r"\b(?:appropriate(?:ly)?|suitably|various|soon|fast|brief(?:ly)?)\b", "Unquantified adjective/adverb", "Quantify parameters (e.g., 'under 150 words', 'in 3 bullet points', 'latency < 200ms')."),
        (r"\b(?:simple|easy|straightforward)\b", "Subjective complexity assumption", "Specify exact prerequisites, step counts, or technical depth."),
    ]

    # Prompt injection vectors and unsafe template interpolation
    INJECTION_RISK_PATTERNS: List[Tuple[str, str, str]] = [
        (r"(?i)\b(?:ignore|disregard|forget|bypass|override)\s+(?:all\s+)?(?:previous|prior|above|system)\s+(?:instructions|prompts|directives|rules)\b", "Direct prompt injection attempt", "Wrap external input in distinct XML delimiters (e.g., <user_input>) and instruct the model to treat content strictly as untrusted data."),
        (r"(?i)\b(?:DAN mode|jailbreak|developer mode|unrestricted mode)\b", "Jailbreak signature phrase", "Remove jailbreak phrasing and implement robust role definition."),
        (r"\{\{\s*(?:user_input|input|query|prompt|data)\s*\}\}(?!\s*</)", "Unbounded / undelimited variable interpolation", "Wrap dynamic input variables in explicit delimiter tags such as <user_query>{{input}}</user_query> to prevent prompt injection."),
        (r"(?i)\b(?:system:\s*|developer:\s*|<\|im_start\|>|<\|im_end\|>)\b", "Raw chat template control token injection", "Escape or sanitize raw control tokens that may confuse model chat parsing."),
    ]

    # Credential and sensitive data leakage patterns
    SECRET_LEAK_PATTERNS: List[Tuple[str, str, str]] = [
        (r"\b(?:sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{50,})\b", "Hardcoded API Token / Key detected", "Never embed API keys or bearer tokens in prompts. Pass secrets via secure server-side environment variables."),
        (r"\bAKIA[0-9A-Z]{16}\b", "AWS Access Key ID detected", "Remove AWS credentials immediately. Use IAM roles and serverless environment secrets."),
        (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private cryptographic key detected", "Never expose private keys in prompt instructions."),
        (r"(?i)\b(?:password|passwd|api_secret|auth_token)\s*=\s*['\"][^'\"]{6,}['\"]", "Hardcoded password/secret assignment", "Remove raw credentials from prompt text."),
    ]

    # Negative constraint indicators
    NEGATIVE_CONSTRAINT_PATTERNS: List[Tuple[str, str]] = [
        (r"\b(?:do not|don't|dont|never|should not|shouldn't|must not|mustn't|avoid)\s+([a-zA-Z0-9_ ]+?)(?=[.,;\n]|$)", "Negative constraint framing"),
    ]

    # Filler and redundant conversational fluff
    POLITENESS_FILLER_PATTERNS: List[Tuple[str, str]] = [
        (r"(?i)\b(?:please\s+kindly|kindly|if you (?:would|could) be so kind|if it(?:'s| is) not too much trouble|I would (?:really\s+)?appreciate it if you (?:could|would))\b", "Redundant polite filler"),
        (r"(?i)\b(?:hello(?: dear)? (?:ai|assistant|chatgpt|claude|bot)|hope you are doing well)\b", "Conversational greeting filler"),
    ]

    # Conflicting / contradictory requirements
    CONTRADICTORY_PAIRS: List[Tuple[str, str, str]] = [
        (r"(?i)\b(?:brief|short|concise|in 1 sentence|summary)\b", r"(?i)\b(?:exhaustive|comprehensive|detailed|in-depth|all details|thorough)\b", "Contradictory directives: 'concise/brief' vs 'exhaustive/comprehensive'"),
        (r"(?i)\b(?:strictly|only)\s+json\b", r"(?i)\b(?:explain|explain your reasoning|in markdown|conversational)\b", "Contradictory output: 'strictly JSON' vs 'conversational explanation'"),
        (r"(?i)\bno assumptions\b", r"(?i)\b(?:extrapolate|brainstorm|be creative|hallucinate)\b", "Contradictory guidance: 'no assumptions' vs 'creative extrapolation'"),
    ]

    def __init__(self) -> None:
        self.tokenizer = TokenizerEstimator()

    def _get_line_and_column(self, text: str, match_start: int) -> Tuple[int, int]:
        """Calculate 1-indexed line number and column for a match character offset."""
        prefix = text[:match_start]
        line_num = prefix.count("\n") + 1
        last_newline = prefix.rfind("\n")
        col_num = (match_start - last_newline) if last_newline != -1 else (match_start + 1)
        return line_num, col_num

    def lint(
        self,
        prompt: str,
        target_provider: Optional[str] = None,
        target: Optional[str] = None,
        **kwargs: Any,
    ) -> PromptAnalysisResult:
        """Run all static analysis rules and calculate prompt quality scores.
        
        Args:
            prompt: Target prompt string.
            target_provider: Optional target provider context.
            
        Returns:
            PromptAnalysisResult with issues, metrics, and scores.
        """
        if not prompt or not prompt.strip():
            return PromptAnalysisResult(
                clarity_score=0.0,
                security_score=100.0,
                structure_score=0.0,
                overall_score=0.0,
                issues=[
                    LinterIssue(
                        rule_id="EMPTY_PROMPT",
                        message="The prompt is completely empty.",
                        severity=LinterSeverity.CRITICAL.value,
                        category=LinterCategory.CLARITY.value,
                        suggestion="Provide explicit instructions, task context, and expected output format.",
                    )
                ],
                estimated_tokens=0,
                word_count=0,
                char_count=0,
                positive_to_negative_ratio=1.0,
                suggestions_summary=["Add a concrete task instruction and role framing."],
            )

        issues: List[LinterIssue] = []
        text = prompt

        # 1. Check Secret / Credential Leaks
        for pattern, msg, suggestion in self.SECRET_LEAK_PATTERNS:
            for match in re.finditer(pattern, text):
                line, col = self._get_line_and_column(text, match.start())
                issues.append(
                    LinterIssue(
                        rule_id="SENSITIVE_DATA_LEAK",
                        message=f"{msg}: '{match.group(0)[:12]}...'",
                        severity=LinterSeverity.CRITICAL.value,
                        category=LinterCategory.SECURITY.value,
                        line_number=line,
                        column=col,
                        suggestion=suggestion,
                        matched_text=match.group(0),
                    )
                )

        # 2. Check Prompt Injection Risks
        for pattern, msg, suggestion in self.INJECTION_RISK_PATTERNS:
            for match in re.finditer(pattern, text):
                line, col = self._get_line_and_column(text, match.start())
                issues.append(
                    LinterIssue(
                        rule_id="PROMPT_INJECTION_RISK",
                        message=msg,
                        severity=LinterSeverity.ERROR.value,
                        category=LinterCategory.SECURITY.value,
                        line_number=line,
                        column=col,
                        suggestion=suggestion,
                        matched_text=match.group(0),
                    )
                )

        # 3. Check Vague & Ambiguous Terms
        for pattern, msg, suggestion in self.VAGUE_TERMS_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                line, col = self._get_line_and_column(text, match.start())
                issues.append(
                    LinterIssue(
                        rule_id="AMBIGUOUS_TERMS",
                        message=f"{msg} detected: '{match.group(0)}'",
                        severity=LinterSeverity.WARNING.value,
                        category=LinterCategory.CLARITY.value,
                        line_number=line,
                        column=col,
                        suggestion=suggestion,
                        matched_text=match.group(0),
                    )
                )

        # 4. Check Negative Constraints vs Positive Directives
        negative_matches: List[re.Match] = []
        for pattern, _ in self.NEGATIVE_CONSTRAINT_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                negative_matches.append(match)

        positive_count = len(
            re.findall(
                r"\b(?:always|ensure|must|include|strictly|verify|adhere to|format as|use|provide)\b",
                text,
                re.IGNORECASE,
            )
        )
        negative_count = len(negative_matches)

        if negative_count > 0:
            ratio = (positive_count + 0.1) / (negative_count + 0.1)
        else:
            ratio = float(positive_count or 1.0)

        if negative_count >= 3 and ratio < 0.8:
            first_neg = negative_matches[0]
            line, col = self._get_line_and_column(text, first_neg.start())
            issues.append(
                LinterIssue(
                    rule_id="NEGATIVE_CONSTRAINTS_DOMINANT",
                    message=f"Prompt relies heavily on negative constraints ({negative_count} negative vs {positive_count} positive). Models follow positive behavioral framing more reliably.",
                    severity=LinterSeverity.WARNING.value,
                    category=LinterCategory.CONSTRAINTS.value,
                    line_number=line,
                    column=col,
                    suggestion="Reframe negative rules ('Do not write long code') into positive instructions ('Provide concise, modular functions under 20 lines').",
                    matched_text=first_neg.group(0),
                )
            )

        # 5. Check Missing Output Indicator / Format Specification
        has_output_spec = bool(
            re.search(
                r"(?i)\b(?:output\s+(?:format|schema|as|in)|respond\s+(?:in|with|using)|return\s+(?:a|the)?\s*(?:json|xml|markdown|table|bullet|list|csv|schema)|format:|<output_format>|### Output)\b",
                text,
            )
        )
        if not has_output_spec and len(text.split()) >= 6:
            issues.append(
                LinterIssue(
                    rule_id="MISSING_OUTPUT_FORMAT",
                    message="No explicit output format specified (e.g. JSON, Markdown table, bullet points, XML).",
                    severity=LinterSeverity.WARNING.value,
                    category=LinterCategory.FORMATTING.value,
                    suggestion="Add an explicit `<output_format>` or `### Output Format` section specifying schema, key names, and length.",
                )
            )

        # 6. Check Missing Role / Persona Definition
        has_role = bool(
            re.search(
                r"(?i)\b(?:you are (?:an?|the)|act as (?:an?|the)|role:|your role is|<role>|### (?:Role|Persona))\b",
                text,
            )
        )
        if not has_role and len(text.split()) > 20:
            issues.append(
                LinterIssue(
                    rule_id="MISSING_ROLE_DEFINITION",
                    message="Prompt lacks a defined role or persona context.",
                    severity=LinterSeverity.INFO.value,
                    category=LinterCategory.STRUCTURE.value,
                    suggestion="Frame the model's perspective (e.g. 'You are an expert Senior Security Architect reviewing code for PCI-DSS compliance').",
                )
            )

        # 7. Check Missing Delimiters for Complex Prompts
        has_delimiters = bool(
            re.search(
                r"(?:<[a-zA-Z0-9_\-]+>|```|\"\"\"|---|\#\#\#)",
                text,
            )
        )
        if not has_delimiters and len(text.split()) > 40:
            issues.append(
                LinterIssue(
                    rule_id="MISSING_DELIMITERS",
                    message="Long prompt without structural delimiters (XML tags, Markdown sections, or triple quotes).",
                    severity=LinterSeverity.WARNING.value,
                    category=LinterCategory.STRUCTURE.value,
                    suggestion="Use XML tags (e.g., <instructions>, <context>, <input>) or Markdown headers to isolate prompt components.",
                )
            )

        # 8. Check Contradictory Constraints
        for pat_a, pat_b, msg in self.CONTRADICTORY_PAIRS:
            if re.search(pat_a, text) and re.search(pat_b, text):
                issues.append(
                    LinterIssue(
                        rule_id="CONTRADICTING_DIRECTIVES",
                        message=msg,
                        severity=LinterSeverity.ERROR.value,
                        category=LinterCategory.CONSTRAINTS.value,
                        suggestion="Reconcile conflicting instructions by setting clear priority or removing the contradiction.",
                    )
                )

        # 9. Check Redundant Politeness Fluff
        for pattern, msg in self.POLITENESS_FILLER_PATTERNS:
            for match in re.finditer(pattern, text):
                line, col = self._get_line_and_column(text, match.start())
                issues.append(
                    LinterIssue(
                        rule_id="REDUNDANT_POLITENESS",
                        message=f"{msg}: '{match.group(0)}' consumes tokens without improving accuracy.",
                        severity=LinterSeverity.INFO.value,
                        category=LinterCategory.EFFICIENCY.value,
                        line_number=line,
                        column=col,
                        suggestion="Remove conversational pleasantries to save tokens and improve instruction following.",
                        matched_text=match.group(0),
                    )
                )

        # 10. Check Unescaped / Malformed Template Syntax
        unmatched_open = len(re.findall(r"\{\{(?!\s*[\w#/@|])", text))
        unmatched_close = len(re.findall(r"(?<![\w\s\"'|])\}\}", text))
        if unmatched_open > 0 or unmatched_close > 0:
            issues.append(
                LinterIssue(
                    rule_id="MALFORMED_TEMPLATE_SYNTAX",
                    message="Detected possible malformed or stray mustache template braces.",
                    severity=LinterSeverity.WARNING.value,
                    category=LinterCategory.FORMATTING.value,
                    suggestion="Ensure all variables follow the `{{ variable_name }}` syntax.",
                )
            )

        # Extract detected variables
        detected_vars = sorted(
            list(
                set(
                    re.findall(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*(?:\||:-|:|\}\})", text)
                )
            )
        )

        # Calculate metrics
        word_count = len(text.split())
        char_count = len(text)
        token_count = self.tokenizer.count_tokens(text)

        # Calculate Dimensional Scores (0 - 100)
        clarity_deductions = sum(
            15 for i in issues if i.category == LinterCategory.CLARITY.value and i.severity == LinterSeverity.WARNING.value
        ) + sum(
            25 for i in issues if i.category == LinterCategory.CLARITY.value and i.severity in (LinterSeverity.ERROR.value, LinterSeverity.CRITICAL.value)
        )
        clarity_score = max(0.0, min(100.0, 100.0 - clarity_deductions))

        security_deductions = sum(
            45 for i in issues if i.category == LinterCategory.SECURITY.value and i.severity == LinterSeverity.CRITICAL.value
        ) + sum(
            25 for i in issues if i.category == LinterCategory.SECURITY.value and i.severity == LinterSeverity.ERROR.value
        )
        security_score = max(0.0, min(100.0, 100.0 - security_deductions))

        structure_deductions = sum(
            15 for i in issues if i.category in (LinterCategory.STRUCTURE.value, LinterCategory.FORMATTING.value) and i.severity == LinterSeverity.WARNING.value
        ) + sum(
            25 for i in issues if i.category in (LinterCategory.STRUCTURE.value, LinterCategory.FORMATTING.value) and i.severity == LinterSeverity.ERROR.value
        ) + sum(
            10 for i in issues if i.rule_id == "MISSING_OUTPUT_FORMAT"
        )
        structure_score = max(0.0, min(100.0, 100.0 - structure_deductions))

        # Overall composite score
        overall_score = (clarity_score * 0.35) + (security_score * 0.40) + (structure_score * 0.25)

        # Build suggestions summary
        suggestions_summary: List[str] = []
        for issue in issues:
            if issue.suggestion and issue.suggestion not in suggestions_summary:
                suggestions_summary.append(issue.suggestion)

        return PromptAnalysisResult(
            clarity_score=clarity_score,
            security_score=security_score,
            structure_score=structure_score,
            overall_score=overall_score,
            issues=issues,
            estimated_tokens=token_count,
            word_count=word_count,
            char_count=char_count,
            detected_variables=detected_vars,
            positive_to_negative_ratio=ratio,
            suggestions_summary=suggestions_summary,
        )

    def auto_fix(self, prompt: str) -> str:
        """Apply deterministic transformations to fix common lint issues.
        
        - Strips conversational politeness fluff
        - Reframes negative constraints into positive imperatives
        - Sanitizes undelimited variable interpolations with XML tags
        
        Args:
            prompt: Raw prompt string.
            
        Returns:
            Cleaned and hardened prompt text.
        """
        fixed = prompt

        # 1. Strip politeness fluff
        for pattern, _ in self.POLITENESS_FILLER_PATTERNS:
            fixed = re.sub(pattern, "", fixed, flags=re.IGNORECASE)

        # 2. Wrap plain untagged variables in XML tags if not already enclosed
        def _wrap_var_tag(match: re.Match) -> str:
            existing_tag = match.group(1)
            var_name = match.group(2)
            if existing_tag:
                return match.group(0)
            return f"<{var_name}>{{{{{var_name}}}}}</{var_name}>"

        fixed = re.sub(
            r"(?:<([a-zA-Z0-9_]+)>\s*)?\{\{\s*(input|user_input|data|query)\s*\}\}(?:\s*</\1>)?",
            _wrap_var_tag,
            fixed,
        )

        # 3. Clean up multiple blank lines
        fixed = re.sub(r"\n{3,}", "\n\n", fixed).strip()

        return fixed
