"""Tests for data models and schemas in promptmaster_studio.models."""

import json

import pytest

from promptmaster_studio.models import (
    ContextBudgetReport,
    CurriculumLesson,
    FewShotExample,
    LessonDifficulty,
    LinterCategory,
    LinterIssue,
    LinterSeverity,
    ModelSpec,
    OptimizedPromptResult,
    PromptAnalysisResult,
    PromptTemplate,
    PromptVariable,
    ProviderTarget,
    VariableType,
)


class TestEnums:
    """Test standard enumeration constants."""

    def test_provider_targets(self):
        assert ProviderTarget.ANTHROPIC_XML.value == "anthropic_xml"
        assert ProviderTarget.OPENAI_CHAT.value == "openai_chat"
        assert ProviderTarget.GOOGLE_GEMINI.value == "google_gemini"
        assert ProviderTarget.GENERIC_MARKDOWN.value == "generic_markdown"

    def test_variable_types(self):
        assert VariableType.STRING.value == "string"
        assert VariableType.NUMBER.value == "number"
        assert VariableType.BOOLEAN.value == "boolean"
        assert VariableType.LIST.value == "list"
        assert VariableType.OBJECT.value == "object"

    def test_linter_severity_and_categories(self):
        assert LinterSeverity.INFO.value == "info"
        assert LinterSeverity.WARNING.value == "warning"
        assert LinterSeverity.ERROR.value == "error"
        assert LinterSeverity.CRITICAL.value == "critical"

        assert LinterCategory.CLARITY.value == "clarity"
        assert LinterCategory.SECURITY.value == "security"
        assert LinterCategory.CONSTRAINTS.value == "constraints"

    def test_lesson_difficulty(self):
        assert LessonDifficulty.BEGINNER.value == "beginner"
        assert LessonDifficulty.INTERMEDIATE.value == "intermediate"
        assert LessonDifficulty.ADVANCED.value == "advanced"
        assert LessonDifficulty.EXPERT.value == "expert"


class TestPromptVariable:
    """Test PromptVariable dataclass serialization and conversion."""

    def test_prompt_variable_defaults_and_dict(self):
        var = PromptVariable(name="query", description="Search query")
        assert var.name == "query"
        assert var.required is True
        assert var.var_type == "string"

        d = var.to_dict()
        assert d["name"] == "query"
        assert d["required"] is True

        reconstructed = PromptVariable.from_dict(d)
        assert reconstructed.name == var.name
        assert reconstructed.description == var.description


class TestFewShotExample:
    """Test FewShotExample serialization."""

    def test_few_shot_serialization(self):
        example = FewShotExample(
            input_text="Convert 100 EUR to USD",
            output_text="100 EUR = 108 USD (approximate)",
            explanation="Exchange rate conversion demonstration.",
            metadata={"currency_pair": "EUR/USD"},
        )
        d = example.to_dict()
        assert d["input_text"] == "Convert 100 EUR to USD"
        assert d["metadata"]["currency_pair"] == "EUR/USD"

        reconstructed = FewShotExample.from_dict(d)
        assert reconstructed.input_text == example.input_text
        assert reconstructed.output_text == example.output_text
        assert reconstructed.explanation == example.explanation


class TestPromptTemplate:
    """Test PromptTemplate serialization, JSON encoding/decoding."""

    def test_prompt_template_lifecycle(self, sample_template: PromptTemplate):
        assert sample_template.id == "t-explainer-001"
        assert len(sample_template.variables) == 1
        assert len(sample_template.few_shot_examples) == 1
        assert sample_template.created_at is not None

        # Convert to dict and JSON
        d = sample_template.to_dict()
        assert d["id"] == "t-explainer-001"
        assert isinstance(d["variables"], list)

        json_str = sample_template.to_json()
        assert "t-explainer-001" in json_str

        from_json_tmpl = PromptTemplate.from_json(json_str)
        assert from_json_tmpl.id == sample_template.id
        assert from_json_tmpl.title == sample_template.title
        assert len(from_json_tmpl.variables) == 1
        assert from_json_tmpl.variables[0].name == "topic"


class TestLinterAndAnalysisModels:
    """Test LinterIssue and PromptAnalysisResult serialization."""

    def test_linter_issue_serialization(self):
        issue = LinterIssue(
            rule_id="PML001",
            message="Avoid politeness hedging",
            severity="warning",
            category="clarity",
            line_number=1,
            suggestion="Remove 'Please kindly'",
            matched_text="Please kindly",
        )
        d = issue.to_dict()
        assert d["rule_id"] == "PML001"
        reconstructed = LinterIssue.from_dict(d)
        assert reconstructed.rule_id == issue.rule_id
        assert reconstructed.line_number == 1

    def test_prompt_analysis_result(self):
        issue = LinterIssue(
            rule_id="PML002",
            message="Ambiguous directive",
            severity="error",
            category="clarity",
        )
        res = PromptAnalysisResult(
            clarity_score=85.0,
            security_score=95.0,
            structure_score=90.0,
            overall_score=90.0,
            issues=[issue],
            estimated_tokens=42,
            word_count=30,
            char_count=180,
            detected_variables=["user_query"],
        )
        d = res.to_dict()
        assert d["clarity_score"] == 85.0
        assert len(d["issues"]) == 1

        reconstructed = PromptAnalysisResult.from_dict(d)
        assert reconstructed.clarity_score == 85.0
        assert reconstructed.estimated_tokens == 42
        assert len(reconstructed.issues) == 1


class TestOptimizedPromptResultAndCurriculum:
    """Test OptimizedPromptResult and CurriculumLesson models."""

    def test_optimized_prompt_result(self):
        opt = OptimizedPromptResult(
            original_prompt="Help me write code",
            optimized_prompt="<role>Expert Software Engineer</role>\n<task>Write clean, tested Python code</task>",
            target_provider=ProviderTarget.ANTHROPIC_XML.value,
            strategy_used="xml_decomposition",
            sections={"role": "Expert Software Engineer", "task": "Write clean, tested Python code"},
            added_tags=["<role>", "<task>"],
            estimated_tokens_before=4,
            estimated_tokens_after=18,
            improvements=["Injected explicit role persona", "Added structured XML tags"],
        )
        d = opt.to_dict()
        assert d["original_prompt"] == "Help me write code"
        assert "role" in d["sections"]

        reconstructed = OptimizedPromptResult.from_dict(d)
        assert reconstructed.target_provider == ProviderTarget.ANTHROPIC_XML.value
        assert len(reconstructed.improvements) == 2

    def test_curriculum_lesson(self):
        lesson = CurriculumLesson(
            id="cur-01-delimiters",
            title="Mastering Prompt Delimiters & XML Framing",
            category="delimiters",
            difficulty="beginner",
            estimated_minutes=15,
            summary="Learn how clear boundary delimiters prevent prompt injection and ambiguity.",
            content_markdown="# Delimiters Guide\n\nUse XML tags or triple quotes.",
            key_takeaways=["XML tags are Claude's native boundary marker."],
            exercises=[{"question": "What is the best delimiter for Anthropic Claude?", "answer": "XML tags"}],
            sample_before_prompt="Summarize this: text here",
            sample_after_prompt="<task>Summarize</task><text>text here</text>",
        )
        d = lesson.to_dict()
        assert d["id"] == "cur-01-delimiters"
        assert d["estimated_minutes"] == 15

        reconstructed = CurriculumLesson.from_dict(d)
        assert reconstructed.title == lesson.title
        assert len(reconstructed.exercises) == 1


class TestModelSpecAndContextBudgetReport:
    """Test ModelSpec and ContextBudgetReport schemas."""

    def test_model_spec(self):
        spec = ModelSpec(
            name="claude-3-5-sonnet",
            family="anthropic",
            context_window=200000,
            max_output_tokens=8192,
            cost_per_million_input=3.0,
            cost_per_million_output=15.0,
        )
        d = spec.to_dict()
        assert d["name"] == "claude-3-5-sonnet"
        assert d["context_window"] == 200000

    def test_context_budget_report(self):
        report = ContextBudgetReport(
            model_name="gpt-4o",
            family="openai",
            prompt_tokens=1500,
            estimated_output_tokens=500,
            total_tokens=2000,
            context_window=128000,
            remaining_context=126000,
            context_usage_percent=1.56,
            estimated_cost_usd=0.0075,
            fits_in_context=True,
            warning_level="nominal",
            recommendations=["Context usage is optimal."],
        )
        d = report.to_dict()
        assert d["fits_in_context"] is True
        assert d["total_tokens"] == 2000
