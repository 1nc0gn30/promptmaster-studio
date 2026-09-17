"""Pure Python BPE heuristic token counter and context budget analyzer.

Models tokenizer dynamics for OpenAI, Anthropic, Google Gemini, Meta Llama,
Mistral, and DeepSeek without third-party dependencies.
100% Python Standard Library.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Union

from promptmaster_studio.models import ContextBudgetReport, ModelSpec


# Comprehensive Model Specifications Catalog
MODEL_CATALOG: Dict[str, ModelSpec] = {
    # OpenAI Models
    "gpt-4o": ModelSpec(
        name="gpt-4o",
        family="OpenAI",
        context_window=128000,
        max_output_tokens=16384,
        cost_per_million_input=2.50,
        cost_per_million_output=10.00,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="o200k_base",
    ),
    "gpt-4o-mini": ModelSpec(
        name="gpt-4o-mini",
        family="OpenAI",
        context_window=128000,
        max_output_tokens=16384,
        cost_per_million_input=0.15,
        cost_per_million_output=0.60,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="o200k_base",
    ),
    "gpt-4-turbo": ModelSpec(
        name="gpt-4-turbo",
        family="OpenAI",
        context_window=128000,
        max_output_tokens=4096,
        cost_per_million_input=10.00,
        cost_per_million_output=30.00,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="cl100k_base",
    ),
    "o1": ModelSpec(
        name="o1",
        family="OpenAI",
        context_window=200000,
        max_output_tokens=100000,
        cost_per_million_input=15.00,
        cost_per_million_output=60.00,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="o200k_base",
    ),
    "o3-mini": ModelSpec(
        name="o3-mini",
        family="OpenAI",
        context_window=200000,
        max_output_tokens=100000,
        cost_per_million_input=1.10,
        cost_per_million_output=4.40,
        supports_system_prompt=True,
        supports_vision=False,
        supports_json_mode=True,
        tokenizer_type="o200k_base",
    ),
    "gpt-3.5-turbo": ModelSpec(
        name="gpt-3.5-turbo",
        family="OpenAI",
        context_window=16385,
        max_output_tokens=4096,
        cost_per_million_input=0.50,
        cost_per_million_output=1.50,
        supports_system_prompt=True,
        supports_vision=False,
        supports_json_mode=True,
        tokenizer_type="cl100k_base",
    ),

    # Anthropic Models
    "claude-3-7-sonnet": ModelSpec(
        name="claude-3-7-sonnet",
        family="Anthropic",
        context_window=200000,
        max_output_tokens=64000,
        cost_per_million_input=3.00,
        cost_per_million_output=15.00,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="claude_bpe",
    ),
    "claude-3-5-sonnet": ModelSpec(
        name="claude-3-5-sonnet",
        family="Anthropic",
        context_window=200000,
        max_output_tokens=8192,
        cost_per_million_input=3.00,
        cost_per_million_output=15.00,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="claude_bpe",
    ),
    "claude-3-5-haiku": ModelSpec(
        name="claude-3-5-haiku",
        family="Anthropic",
        context_window=200000,
        max_output_tokens=8192,
        cost_per_million_input=0.80,
        cost_per_million_output=4.00,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="claude_bpe",
    ),
    "claude-3-opus": ModelSpec(
        name="claude-3-opus",
        family="Anthropic",
        context_window=200000,
        max_output_tokens=4096,
        cost_per_million_input=15.00,
        cost_per_million_output=75.00,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="claude_bpe",
    ),

    # Google Gemini Models
    "gemini-1.5-pro": ModelSpec(
        name="gemini-1.5-pro",
        family="Google",
        context_window=2097152,
        max_output_tokens=8192,
        cost_per_million_input=3.50,
        cost_per_million_output=10.50,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="gemini_sp",
    ),
    "gemini-1.5-flash": ModelSpec(
        name="gemini-1.5-flash",
        family="Google",
        context_window=1048576,
        max_output_tokens=8192,
        cost_per_million_input=0.075,
        cost_per_million_output=0.30,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="gemini_sp",
    ),
    "gemini-2.0-flash": ModelSpec(
        name="gemini-2.0-flash",
        family="Google",
        context_window=1048576,
        max_output_tokens=8192,
        cost_per_million_input=0.10,
        cost_per_million_output=0.40,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="gemini_sp",
    ),
    "gemini-2.5-pro": ModelSpec(
        name="gemini-2.5-pro",
        family="Google",
        context_window=2097152,
        max_output_tokens=8192,
        cost_per_million_input=2.50,
        cost_per_million_output=10.00,
        supports_system_prompt=True,
        supports_vision=True,
        supports_json_mode=True,
        tokenizer_type="gemini_sp",
    ),

    # Meta Llama Models
    "llama-3.3-70b": ModelSpec(
        name="llama-3.3-70b",
        family="Meta",
        context_window=131072,
        max_output_tokens=4096,
        cost_per_million_input=0.60,
        cost_per_million_output=0.80,
        supports_system_prompt=True,
        supports_vision=False,
        supports_json_mode=True,
        tokenizer_type="llama3_tiktoken",
    ),
    "llama-3.1-405b": ModelSpec(
        name="llama-3.1-405b",
        family="Meta",
        context_window=131072,
        max_output_tokens=4096,
        cost_per_million_input=2.00,
        cost_per_million_output=2.00,
        supports_system_prompt=True,
        supports_vision=False,
        supports_json_mode=True,
        tokenizer_type="llama3_tiktoken",
    ),
    "llama-3-8b": ModelSpec(
        name="llama-3-8b",
        family="Meta",
        context_window=8192,
        max_output_tokens=2048,
        cost_per_million_input=0.10,
        cost_per_million_output=0.10,
        supports_system_prompt=True,
        supports_vision=False,
        supports_json_mode=True,
        tokenizer_type="llama3_tiktoken",
    ),

    # Mistral Models
    "mistral-large-2": ModelSpec(
        name="mistral-large-2",
        family="Mistral",
        context_window=128000,
        max_output_tokens=4096,
        cost_per_million_input=2.00,
        cost_per_million_output=6.00,
        supports_system_prompt=True,
        supports_vision=False,
        supports_json_mode=True,
        tokenizer_type="mistral_sp",
    ),
    "codestral": ModelSpec(
        name="codestral",
        family="Mistral",
        context_window=32768,
        max_output_tokens=4096,
        cost_per_million_input=0.20,
        cost_per_million_output=0.60,
        supports_system_prompt=True,
        supports_vision=False,
        supports_json_mode=True,
        tokenizer_type="mistral_sp",
    ),

    # DeepSeek Models
    "deepseek-v3": ModelSpec(
        name="deepseek-v3",
        family="DeepSeek",
        context_window=65536,
        max_output_tokens=8192,
        cost_per_million_input=0.14,
        cost_per_million_output=0.28,
        supports_system_prompt=True,
        supports_vision=False,
        supports_json_mode=True,
        tokenizer_type="deepseek_bpe",
    ),
    "deepseek-r1": ModelSpec(
        name="deepseek-r1",
        family="DeepSeek",
        context_window=65536,
        max_output_tokens=8192,
        cost_per_million_input=0.55,
        cost_per_million_output=2.19,
        supports_system_prompt=True,
        supports_vision=False,
        supports_json_mode=True,
        tokenizer_type="deepseek_bpe",
    ),
}


class TokenizerEstimator:
    """Byte-Pair Encoding (BPE) and subword heuristic token counter."""

    # Standard library token regex
    PORTABLE_TOKEN_REGEX = re.compile(
        r"""(?x)
        '(?:[sS]|[tT]|[rR][eE]|[vV][eE]|[mM]|[lL][lL]|[dD])
        |[a-zA-Z]+
        |[0-9]{1,3}
        |[^\s\w]
        |\s+
        """
    )

    # CJK character range
    CJK_REGEX = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u1100-\u11ff]")
    EMOJI_REGEX = re.compile(r"[\U00010000-\U0010ffff]")
    INDENT_SPACES_REGEX = re.compile(r"^( +)", re.MULTILINE)
    BASE64_HEX_REGEX = re.compile(r"\b(?:[A-Fa-f0-9]{32,}|[A-Za-z0-9+/=]{40,})\b")
    XML_JSON_TAGS_REGEX = re.compile(r"</?[a-zA-Z0-9_\-]+(?:\s+[^>]*?)?>")

    @classmethod
    def count_tokens(cls, text: str, model_family: str = "general") -> int:
        """Estimate token count for a text string using calibrated BPE heuristics.
        
        Args:
            text: Prompt or completion string.
            model_family: Target family ("openai", "anthropic", "google", "meta", "general").
            
        Returns:
            Estimated token count integer.
        """
        if not text:
            return 0

        # Calibration multipliers across model tokenizers
        family_clean = model_family.lower()
        if "anthropic" in family_clean or "claude" in family_clean:
            family_mult = 1.02
        elif "google" in family_clean or "gemini" in family_clean:
            family_mult = 0.98
        elif "llama" in family_clean or "meta" in family_clean:
            family_mult = 0.95
        elif "deepseek" in family_clean:
            family_mult = 0.97
        else:
            family_mult = 1.00

        total_tokens = 0.0

        # 1. Handle CJK characters (each CJK char ~ 1.6 tokens in standard BPE)
        cjk_chars = len(cls.CJK_REGEX.findall(text))
        total_tokens += cjk_chars * 1.6

        # 2. Handle Emojis (each emoji ~ 2.5 - 3.5 tokens)
        emojis = len(cls.EMOJI_REGEX.findall(text))
        total_tokens += emojis * 2.8

        # 3. Strip CJK and Emojis for Latin / code parsing
        clean_text = cls.CJK_REGEX.sub(" ", text)
        clean_text = cls.EMOJI_REGEX.sub(" ", clean_text)

        # 4. Handle indentation whitespace (leading 2-4 spaces per line count as separate subword tokens)
        for indent_match in cls.INDENT_SPACES_REGEX.finditer(clean_text):
            spaces_len = len(indent_match.group(1))
            total_tokens += max(1, spaces_len // 3)

        # 5. Handle base64 / long hex tokens (dense byte chunks)
        for blob in cls.BASE64_HEX_REGEX.finditer(clean_text):
            blob_len = len(blob.group(0))
            total_tokens += blob_len / 2.8

        # 6. Parse regular subwords and punctuation
        tokens_matches = cls.PORTABLE_TOKEN_REGEX.findall(clean_text)
        for token in tokens_matches:
            tok_len = len(token)
            if token.isspace():
                newlines = token.count("\n")
                if newlines > 1:
                    total_tokens += newlines * 0.7
                elif newlines == 1:
                    total_tokens += 0.5
            elif token.isdigit():
                # Digits group 1-3 digits per token
                total_tokens += max(1.0, tok_len / 2.2)
            elif token.isalpha():
                # Short word vs compound word subword splits
                if tok_len <= 4:
                    total_tokens += 1.0
                elif tok_len <= 8:
                    total_tokens += 1.25
                elif tok_len <= 14:
                    total_tokens += 2.0
                else:
                    total_tokens += tok_len / 4.0
            else:
                # Punctuation / symbol
                total_tokens += 1.0

        estimated = int(round(total_tokens * family_mult))
        return max(1, estimated) if text.strip() else 0

    @classmethod
    def get_model(cls, model_name: str) -> ModelSpec:
        """Lookup model specifications by name or alias.
        
        Args:
            model_name: Exact name or substring (e.g. 'gpt-4o', 'sonnet', 'gemini-1.5-pro').
            
        Returns:
            ModelSpec instance or default GPT-4o spec.
        """
        name_clean = model_name.lower().strip()
        if name_clean in MODEL_CATALOG:
            return MODEL_CATALOG[name_clean]

        # Substring fuzzy match
        for key, spec in MODEL_CATALOG.items():
            if key in name_clean or name_clean in key:
                return spec

        # Fallback default
        return MODEL_CATALOG["gpt-4o"]

    @classmethod
    def analyze_budget(
        cls,
        prompt_text: str,
        model_name: str = "gpt-4o",
        expected_output_tokens: int = 1000,
    ) -> ContextBudgetReport:
        """Evaluate prompt against the target model context envelope.
        
        Args:
            prompt_text: Complete prompt text.
            model_name: Target model identifier.
            expected_output_tokens: Expected completion length.
            
        Returns:
            ContextBudgetReport with utilization metrics, cost, and recommendations.
        """
        model = cls.get_model(model_name)
        prompt_tokens = cls.count_tokens(prompt_text, model.family)
        total_tokens = prompt_tokens + expected_output_tokens
        remaining_context = max(0, model.context_window - total_tokens)
        usage_pct = (total_tokens / model.context_window) * 100.0

        # Cost calculation ($ per million tokens)
        cost_input = (prompt_tokens / 1_000_000.0) * model.cost_per_million_input
        cost_output = (expected_output_tokens / 1_000_000.0) * model.cost_per_million_output
        estimated_cost = cost_input + cost_output

        fits = total_tokens <= model.context_window

        # Determine warning level
        if not fits or usage_pct >= 95.0:
            warning_level = "overflow"
        elif usage_pct >= 80.0:
            warning_level = "critical"
        elif usage_pct >= 60.0:
            warning_level = "moderate"
        else:
            warning_level = "safe"

        recommendations: List[str] = []
        if warning_level == "overflow":
            recommendations.append(
                f"Prompt + completion ({total_tokens:,} tokens) exceeds {model.name} context window ({model.context_window:,})."
            )
            recommendations.append(
                "Consider chunking documents, summarizing long context, or migrating to Gemini 1.5 Pro (2M window)."
            )
        elif warning_level == "critical":
            recommendations.append(
                f"High context utilization ({usage_pct:.1f}%). Attention degradation (needle-in-a-haystack issues) may occur."
            )
            recommendations.append(
                "Move critical instructions to both the top and bottom of the prompt context."
            )
        elif warning_level == "moderate":
            recommendations.append(
                f"Context utilization is moderate ({usage_pct:.1f}%). Plenty of headroom remaining."
            )
        else:
            recommendations.append(
                f"Prompt is lean and efficient ({prompt_tokens:,} tokens, {usage_pct:.2f}% of budget)."
            )

        if expected_output_tokens > model.max_output_tokens:
            recommendations.append(
                f"Expected output ({expected_output_tokens:,}) exceeds model max generation limit ({model.max_output_tokens:,})."
            )

        return ContextBudgetReport(
            model_name=model.name,
            family=model.family,
            prompt_tokens=prompt_tokens,
            estimated_output_tokens=expected_output_tokens,
            total_tokens=total_tokens,
            context_window=model.context_window,
            remaining_context=remaining_context,
            context_usage_percent=usage_pct,
            estimated_cost_usd=estimated_cost,
            fits_in_context=fits,
            warning_level=warning_level,
            recommendations=recommendations,
        )

    @classmethod
    def list_available_models(cls) -> List[ModelSpec]:
        """List all models in the catalog."""
        return list(MODEL_CATALOG.values())
