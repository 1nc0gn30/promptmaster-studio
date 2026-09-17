"""Tests for PromptTemplateEngine and variable interpolation in promptmaster_studio.engine.template_engine."""

import json

import pytest

from promptmaster_studio.engine.template_engine import (
    BuiltinFilters,
    PromptTemplateEngine,
    TemplateError,
    VariableMissingError,
    VariableValidationError,
)
from promptmaster_studio.models import PromptTemplate, PromptVariable, VariableType


class TestTemplateEngineBasics:
    """Test standard variable interpolation and default handling."""

    @pytest.fixture
    def engine(self) -> PromptTemplateEngine:
        return PromptTemplateEngine()

    def test_basic_interpolation(self, engine: PromptTemplateEngine):
        template = "Hello, {{ name }}! Welcome to {{ service }}."
        result = engine.render(template, {"name": "Alice", "service": "PromptMaster"})
        assert result == "Hello, Alice! Welcome to PromptMaster."

    def test_default_value_syntax(self, engine: PromptTemplateEngine):
        template_dash = "Explain {{ topic }} for {{ audience:-general audience }}."
        result1 = engine.render(template_dash, {"topic": "Photosynthesis"})
        assert result1 == "Explain Photosynthesis for general audience."

        result2 = engine.render(template_dash, {"topic": "Photosynthesis", "audience": "PhD Physicists"})
        assert result2 == "Explain Photosynthesis for PhD Physicists."

    def test_strict_mode_raises_on_missing_var(self, engine: PromptTemplateEngine):
        template = "Process file {{ filename }} with mode {{ mode }}."
        with pytest.raises(VariableMissingError, match="Variable 'mode' is missing"):
            engine.render(template, {"filename": "data.csv"}, strict=True)

    def test_lenient_mode_defaults_to_empty(self, engine: PromptTemplateEngine):
        template = "Task: {{ task }} (Context: {{ context }})"
        result = engine.render(template, {"task": "Refactor code"}, strict=False)
        assert result == "Task: Refactor code (Context: )"

    def test_extract_variables(self, engine: PromptTemplateEngine):
        template = (
            "You are a {{ role }}.\n"
            "{{#if show_context}}Context: {{ context }}{{/if}}\n"
            "Analyze {{ document:-doc.txt }} with temperature {{ settings.temperature }}.\n"
            "{{#each items}}{{ this }}{{/each}}"
        )
        vars_found = engine.extract_variables(template)
        assert "role" in vars_found
        assert "show_context" in vars_found
        assert "context" in vars_found
        assert "document" in vars_found
        assert "settings" in vars_found
        assert "items" in vars_found
        # Control keywords should not be in extracted variables
        assert "this" not in vars_found
        assert "@index" not in vars_found


class TestBuiltinFilters:
    """Test built-in filter pipelines."""

    @pytest.fixture
    def engine(self) -> PromptTemplateEngine:
        return PromptTemplateEngine()

    def test_string_filters(self, engine: PromptTemplateEngine):
        tmpl = "{{ text | trim | upper }} / {{ text | trim | lower }} / {{ text | trim | title }} / {{ text | trim }}"
        res = engine.render(tmpl, {"text": "  hello world  "})
        assert res == "HELLO WORLD / hello world / Hello World / hello world"

    def test_list_and_bullet_filters(self, engine: PromptTemplateEngine):
        tmpl = "Key Items:\n{{ items | bullets }}"
        res = engine.render(tmpl, {"items": ["Item A", "Item B", "Item C"]})
        assert "- Item A\n- Item B\n- Item C" in res

    def test_numbered_filter(self, engine: PromptTemplateEngine):
        tmpl = "Steps:\n{{ steps | numbered }}"
        res = engine.render(tmpl, {"steps": ["Step 1", "Step 2"]})
        assert "1. Step 1\n2. Step 2" in res

    def test_json_filter(self, engine: PromptTemplateEngine):
        tmpl = "Config:\n{{ config | json }}"
        res = engine.render(tmpl, {"config": {"alpha": 1, "beta": 2}})
        assert '"alpha": 1' in res

    def test_indent_filter(self, engine: PromptTemplateEngine):
        tmpl = "<context>\n{{ raw_text | indent(2) }}\n</context>"
        res = engine.render(tmpl, {"raw_text": "line1\nline2"})
        assert "  line1\n  line2" in res

    def test_custom_filter_registration(self, engine: PromptTemplateEngine):
        engine.register_filter("shout", lambda val: f"{val}!!!")
        tmpl = "Alert: {{ message | shout }}"
        assert engine.render(tmpl, {"message": "Danger"}) == "Alert: Danger!!!"


class TestConditionalsAndLoops:
    """Test template branching and iteration."""

    @pytest.fixture
    def engine(self) -> PromptTemplateEngine:
        return PromptTemplateEngine()

    def test_if_else_branching(self, engine: PromptTemplateEngine):
        tmpl = "{{#if verbose}}Detailed breakdown: {{ details }}{{else}}Brief summary: {{ summary }}{{/if}}"

        res_true = engine.render(tmpl, {"verbose": True, "details": "Full tech log", "summary": "Quick glance"})
        assert res_true == "Detailed breakdown: Full tech log"

        res_false = engine.render(tmpl, {"verbose": False, "details": "Full tech log", "summary": "Quick glance"})
        assert res_false == "Brief summary: Quick glance"

    def test_unless_branching(self, engine: PromptTemplateEngine):
        tmpl = "{{#unless hide_header}}# Report Header\n{{/unless}}Body text."
        assert engine.render(tmpl, {"hide_header": False}) == "# Report Header\nBody text."
        assert engine.render(tmpl, {"hide_header": True}) == "Body text."

    def test_each_loop_over_list(self, engine: PromptTemplateEngine):
        tmpl = "{{#each rules}}Rule {{@index}}: {{this}}\n{{/each}}"
        res = engine.render(tmpl, {"rules": ["No hallucinations", "Use XML tags"]})
        assert "Rule 0: No hallucinations\nRule 1: Use XML tags" in res

    def test_each_loop_over_objects(self, engine: PromptTemplateEngine):
        tmpl = "{{#each users}}User: {{name}} (Role: {{role}})\n{{/each}}"
        users = [
            {"name": "Alice", "role": "Admin"},
            {"name": "Bob", "role": "User"},
        ]
        res = engine.render(tmpl, {"users": users})
        assert "User: Alice (Role: Admin)" in res
        assert "User: Bob (Role: User)" in res


class TestVariableValidationAndSpecRendering:
    """Test PromptVariable validation and PromptTemplate rendering."""

    @pytest.fixture
    def engine(self) -> PromptTemplateEngine:
        return PromptTemplateEngine()

    def test_type_validation_number(self, engine: PromptTemplateEngine):
        spec = PromptVariable(name="count", var_type="number", required=True)
        assert engine.validate_variable(spec, 42) == 42
        assert engine.validate_variable(spec, "123") == 123
        assert engine.validate_variable(spec, "3.14") == 3.14

        with pytest.raises(VariableValidationError):
            engine.validate_variable(spec, "not-a-number")

    def test_type_validation_boolean(self, engine: PromptTemplateEngine):
        spec = PromptVariable(name="is_active", var_type="boolean", required=True)
        assert engine.validate_variable(spec, True) is True
        assert engine.validate_variable(spec, "yes") is True
        assert engine.validate_variable(spec, "0") is False

        with pytest.raises(VariableValidationError):
            engine.validate_variable(spec, "maybe")

    def test_enum_validation(self, engine: PromptTemplateEngine):
        spec = PromptVariable(name="mode", enum_values=["fast", "accurate", "balanced"])
        assert engine.validate_variable(spec, "fast") == "fast"

        with pytest.raises(VariableValidationError, match="not one of allowed enum values"):
            engine.validate_variable(spec, "hyperdrive")

    def test_render_template_instance(self, engine: PromptTemplateEngine, sample_template: PromptTemplate):
        rendered = engine.render_template(sample_template, {"topic": "General Relativity", "audience": "College Students"})
        assert "General Relativity" in rendered
        assert "College Students" in rendered
