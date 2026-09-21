"""Tests for v3 enhancement engines."""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import tempfile
import os

from promptmaster_studio.engine.v3_enhancements import (
    ContextWindowOptimizer,
    ContextWindowPlan,
    ProviderMigrator,
    MigrationResult,
    PromptBatchProcessor,
    PromptScoringRubric,
    RubricScore,
    EnhancedHistory,
    ExportFormatter,
)


# ============================================================================
# CONTEXT WINDOW OPTIMIZER TESTS
# ============================================================================

class TestContextWindowOptimizer:
    def test_analyze_basic(self):
        text = "<instructions>Write a function</instructions>"
        result = ContextWindowOptimizer.analyze(text, "gpt-4o")
        assert "total_tokens" in result
        assert "fits" in result
        assert "context_window" in result
        assert result["context_window"] == 128000
        assert result["fits"] is True

    def test_analyze_very_long_prompt(self):
        text = "x " * 50000
        result = ContextWindowOptimizer.analyze(text, "mistral-7b")
        assert result["fits"] is False
        assert result["overage"] > 0

    def test_optimize_short_prompt_no_changes(self):
        text = "<instructions>Write code</instructions>"
        plan = ContextWindowOptimizer.optimize(text, model_name="gpt-4o")
        assert isinstance(plan, ContextWindowPlan)
        assert plan.optimized_tokens == plan.original_tokens
        assert "No optimization needed" in plan.actions_taken[0]

    def test_optimize_long_prompt(self):
        text = "<instructions>" + "Please write detailed code. " * 1000 + "</instructions>"
        plan = ContextWindowOptimizer.optimize(text, model_name="mistral-7b")
        assert isinstance(plan, ContextWindowPlan)
        assert plan.original_tokens > 0

    def test_optimize_preserves_core_content(self):
        text = "<instructions>Write a function to sort a list</instructions>"
        plan = ContextWindowOptimizer.optimize(text, model_name="gpt-4o")
        assert "Write a function" in plan.optimized_text

    def test_context_window_plan_dict_export(self):
        plan = ContextWindowOptimizer.optimize("Test prompt", "gpt-4o")
        assert hasattr(plan, 'to_dict') or hasattr(plan, '__dict__')

    def test_analyze_with_all_models(self):
        text = "<instructions>Test prompt</instructions>"
        for model in ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro", "mistral-7b", "command-r"]:
            result = ContextWindowOptimizer.analyze(text, model)
            assert result["fits"] is True

    def test_optimize_unknown_model(self):
        with pytest.raises(ValueError):
            ContextWindowOptimizer.optimize("test", "unknown-model")


# ============================================================================
# PROVIDER MIGRATOR TESTS
# ============================================================================

class TestProviderMigrator:
    def test_migrate_anthropic_to_openai(self):
        text = "<instructions>You are an expert. Write code.</instructions>"
        result = ProviderMigrator.migrate(text, "openai", "anthropic")
        assert isinstance(result, MigrationResult)
        assert result.target_provider == "OpenAI"
        assert "instructions" in result.migrated_text.lower() or "## Instructions" in result.migrated_text

    def test_migrate_anthropic_to_gemini(self):
        text = "<instructions>You are an expert. Write code.</instructions>"
        result = ProviderMigrator.migrate(text, "gemini", "anthropic")
        assert result.target_provider == "Google Gemini"

    def test_migrate_anthropic_to_mistral(self):
        text = "<instructions>You are an expert. Write code.</instructions>"
        result = ProviderMigrator.migrate(text, "mistral", "anthropic")
        assert result.target_provider == "Mistral"

    def test_migrate_anthropic_to_cohere(self):
        text = "<instructions>You are an expert. Write code.</instructions>"
        result = ProviderMigrator.migrate(text, "cohere", "anthropic")
        assert result.target_provider == "Cohere"

    def test_migrate_openai_to_anthropic(self):
        text = "# System\nYou are a senior engineer.\n\n## Instructions\nWrite code."
        result = ProviderMigrator.migrate(text, "anthropic", "openai")
        assert result.target_provider == "Anthropic Claude"
        assert "<instructions>" in result.migrated_text

    def test_detect_format_anthropic(self):
        text = "<instructions>Test</instructions>"
        detected = ProviderMigrator._detect_format(text)
        assert detected == "anthropic"

    def test_detect_format_openai(self):
        text = "# System\nYou are helpful.\n\n## Instructions\nDo things."
        detected = ProviderMigrator._detect_format(text)
        assert detected == "openai"

    def test_migrate_with_preserves_content(self):
        text = "<instructions>You are a Python expert. Write a function.</instructions>\n<context>The context.</context>"
        result = ProviderMigrator.migrate(text, "anthropic")
        assert "Python expert" in result.migrated_text
        assert "context" in result.migrated_text.lower()

    def test_migrate_unknown_target(self):
        with pytest.raises(ValueError):
            ProviderMigrator.migrate("<instructions>Test</instructions>", "unknown-provider")


# ============================================================================
# BATCH PROCESSOR TESTS
# ============================================================================

class TestPromptBatchProcessor:
    def test_process_single_prompt(self):
        result = PromptBatchProcessor.process_batch(
            ["Write a function"],
            ["lint", "tokens"],
        )
        assert result.total == 1
        assert result.processed == 1
        assert result.errors == 0

    def test_process_multiple_prompts(self):
        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        result = PromptBatchProcessor.process_batch(prompts, ["lint", "tokens"])
        assert result.total == 3
        assert result.processed == 3
        assert len(result.results) == 3

    def test_process_batch_with_all_operations(self):
        prompts = ["<instructions>Write code</instructions>"]
        operations = ["lint", "optimize", "tokens", "context_check"]
        result = PromptBatchProcessor.process_batch(prompts, operations)
        assert result.processed == 1

    def test_batch_summary_has_token_totals(self):
        result = PromptBatchProcessor.process_batch(
            ["Short prompt", "Another short prompt"],
            ["tokens"]
        )
        assert "total_tokens_before" in result.summary
        assert "total_tokens_after" in result.summary
        assert "token_delta" in result.summary

    def test_batch_handles_empty_prompts(self):
        result = PromptBatchProcessor.process_batch([], ["lint"])
        assert result.total == 0
        assert result.processed == 0

    def test_batch_result_per_prompt(self):
        result = PromptBatchProcessor.process_batch(
            ["<instructions>Test</instructions>"],
            ["lint", "tokens"]
        )
        entry = result.results[0]
        assert "index" in entry
        assert "status" in entry
        assert "results" in entry
        assert "lint" in entry["results"]
        assert "tokens" in entry["results"]


# ============================================================================
# SCORING RUBRIC TESTS
# ============================================================================

class TestPromptScoringRubric:
    def test_score_simple_prompt(self):
        rubric = PromptScoringRubric.score("Write a function")
        assert isinstance(rubric, RubricScore)
        assert 0 <= rubric.overall <= 100
        assert rubric.grade in ["A", "B", "C", "D", "F"]

    def test_score_detailed_prompt(self):
        text = """<instructions>
You are a Principal Software Architect.
- Write production code
- Follow best practices
- Test thoroughly
</instructions>
<context>
The codebase is Python 3.12 with FastAPI.
</context>
<constraints>
- Must use async/await
- Must include type hints
</constraints>
<output_format>
Return GitHub-flavored Markdown.
</output_format>"""
        rubric = PromptScoringRubric.score(text)
        assert rubric.overall >= 60
        assert "A" <= rubric.grade

    def test_score_vague_prompt(self):
        text = "kindly do some stuff with things"
        rubric = PromptScoringRubric.score(text)
        assert rubric.overall < 80
        assert rubric.grade in ["C", "D", "F"]

    def test_dimensions_present(self):
        rubric = PromptScoringRubric.score("Test prompt")
        assert "clarity" in rubric.dimensions
        assert "specificity" in rubric.dimensions
        assert "structure" in rubric.dimensions
        assert "safety" in rubric.dimensions
        assert "efficiency" in rubric.dimensions
        assert "completeness" in rubric.dimensions

    def test_dimensions_in_range(self):
        rubric = PromptScoringRubric.score("Test prompt for scoring")
        for dim, score in rubric.dimensions.items():
            assert 0 <= score <= 100

    def test_recommendations_for_weak_prompt(self):
        rubric = PromptScoringRubric.score("stuff things maybe")
        assert len(rubric.recommendations) > 0

    def test_grade_thresholds(self):
        perfect = PromptScoringRubric.score("<instructions>You are a Principal Architect.- Do X- Do Y- Do Z</instructions><context>Context here</context><constraints>- Rule 1- Rule 2</constraints><output_format>JSON</output_format><examples>Example 1</examples>")
        assert perfect.grade == "A"


# ============================================================================
# ENHANCED HISTORY TESTS
# ============================================================================

class TestEnhancedHistory:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "enhanced_versions.json")

    def _make_store(self):
        return EnhancedHistory(storage_path=self.store_path)

    def test_save_with_analysis(self):
        store = self._make_store()
        v = store.save_with_analysis("<instructions>Write code</instructions>", label="v1")
        assert v.metadata.get("lint_score", 0) > 0
        assert "<instructions>" in v.metadata.get("tags", [])

    def test_find_by_tag(self):
        store = self._make_store()
        store.save_with_analysis("<instructions>Write code</instructions>", label="v1")
        store.save_with_analysis("<context>Analyze this</context>", label="v2")
        results = store.find_by_tag("<instructions>")
        assert len(results) >= 1

    def test_find_by_score(self):
        store = self._make_store()
        store.save_with_analysis("<instructions>You are an expert architect.</instructions>", label="good")
        results = store.find_by_score(min_score=50)
        assert len(results) >= 1

    def test_get_best_version(self):
        store = self._make_store()
        store.save_with_analysis("<instructions>You are an expert.</instructions>", label="good")
        store.save_with_analysis("bad", label="bad")
        best = store.get_best_version()
        assert best is not None


# ============================================================================
# EXPORT FORMATTER TESTS
# ============================================================================

class TestExportFormatter:
    def test_to_json(self):
        result = ExportFormatter.to_json("Hello world", {"key": "value"})
        assert "Hello world" in result
        assert "version" in result
        assert "metadata" in result

    def test_to_yaml(self):
        result = ExportFormatter.to_yaml("Hello world", {"key": "value"})
        assert "prompt:" in result
        assert "Hello world" in result
        assert "version:" in result

    def test_to_markdown(self):
        result = ExportFormatter.to_markdown("Hello world", "My Prompt")
        assert "# My Prompt" in result
        assert "```" in result
        assert "Hello world" in result

    def test_to_env(self):
        result = ExportFormatter.to_env_file("Hello world", "MY_PROMPT")
        assert "MY_PROMPT=" in result

    def test_to_json_roundtrip(self):
        import json
        original = "Test prompt text"
        exported = ExportFormatter.to_json(original)
        parsed = json.loads(exported)
        assert parsed["prompt"] == original

    def test_to_yaml_with_list_metadata(self):
        result = ExportFormatter.to_yaml("Test", {"tags": ["a", "b", "c"]})
        assert "tags:" in result
        assert "- a" in result
