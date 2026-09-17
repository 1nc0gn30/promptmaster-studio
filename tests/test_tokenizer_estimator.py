"""Tests for TokenizerEstimator and context budget analyzer in promptmaster_studio.engine.tokenizer_estimator."""

import pytest

from promptmaster_studio.engine.tokenizer_estimator import (
    MODEL_CATALOG,
    TokenizerEstimator,
)
from promptmaster_studio.models import ContextBudgetReport, ModelSpec


class TestTokenizerEstimator:
    """Test token estimation heuristics across text types and model families."""

    def test_empty_string(self):
        assert TokenizerEstimator.count_tokens("") == 0
        assert TokenizerEstimator.count_tokens("   ") == 0

    def test_basic_english_sentence(self):
        text = "The quick brown fox jumps over the lazy dog."
        tokens = TokenizerEstimator.count_tokens(text)
        assert 8 <= tokens <= 15

    def test_cjk_character_tokenization(self):
        # CJK characters consume ~1.6 tokens per character
        cjk_text = "人工智能与提示词工程"  # 10 characters
        tokens = TokenizerEstimator.count_tokens(cjk_text)
        assert tokens >= 12

    def test_emoji_tokenization(self):
        emoji_text = "🚀 🌟 🔥 💡 🤖"
        tokens = TokenizerEstimator.count_tokens(emoji_text)
        assert tokens >= 10

    def test_code_and_indentation(self):
        code_text = (
            "def calculate_total(items):\n"
            "    total = 0\n"
            "    for item in items:\n"
            "        total += item.price\n"
            "    return total\n"
        )
        tokens = TokenizerEstimator.count_tokens(code_text)
        assert tokens >= 20

    def test_model_family_calibrations(self):
        sample = "Complex prompt text containing XML tags <context>system data</context>"
        openai_tokens = TokenizerEstimator.count_tokens(sample, model_family="openai")
        claude_tokens = TokenizerEstimator.count_tokens(sample, model_family="anthropic")
        gemini_tokens = TokenizerEstimator.count_tokens(sample, model_family="google")

        assert openai_tokens > 0
        assert claude_tokens > 0
        assert gemini_tokens > 0


class TestModelCatalogAndBudget:
    """Test Model catalog retrieval and context budget analytics."""

    def test_catalog_retrieval(self):
        models = TokenizerEstimator.list_available_models()
        assert len(models) >= 10

        gpt4o = TokenizerEstimator.get_model("gpt-4o")
        assert gpt4o.name == "gpt-4o"
        assert gpt4o.context_window == 128000

        claude = TokenizerEstimator.get_model("claude-3-5-sonnet")
        assert claude.family == "Anthropic"
        assert claude.context_window == 200000

        gemini = TokenizerEstimator.get_model("gemini-1.5-pro")
        assert gemini.context_window == 2097152

    def test_fuzzy_model_match(self):
        matched = TokenizerEstimator.get_model("sonnet")
        assert "claude" in matched.name or "sonnet" in matched.name

    def test_budget_analysis_nominal(self):
        prompt = "Write a unit test for a Python function."
        budget = TokenizerEstimator.analyze_budget(
            prompt_text=prompt,
            model_name="gpt-4o",
            expected_output_tokens=500,
        )
        assert isinstance(budget, ContextBudgetReport)
        assert budget.fits_in_context is True
        assert budget.warning_level == "safe"
        assert budget.estimated_cost_usd > 0
        assert budget.remaining_context > 120000

    def test_budget_analysis_overflow(self):
        # Simulate very long prompt on a small context model (llama-3-8b context = 8192)
        huge_prompt = "word " * 6000
        budget = TokenizerEstimator.analyze_budget(
            prompt_text=huge_prompt,
            model_name="llama-3-8b",
            expected_output_tokens=3000,
        )
        assert budget.fits_in_context is False
        assert budget.warning_level == "overflow"
        assert any("exceeds" in rec for rec in budget.recommendations)
