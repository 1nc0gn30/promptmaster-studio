"""Tests for MetaOptimizer in promptmaster_studio.engine.meta_optimizer."""

import pytest

from promptmaster_studio.engine.meta_optimizer import MetaOptimizer
from promptmaster_studio.models import FewShotExample, OptimizedPromptResult, ProviderTarget


class TestMetaOptimizer:
    """Test role inference, task cleaning, constraint synthesis, and provider formatting."""

    @pytest.fixture
    def optimizer(self) -> MetaOptimizer:
        return MetaOptimizer()

    def test_infer_role_coding(self, optimizer: MetaOptimizer):
        role = optimizer.infer_role("Refactor this Python FastAPI backend function for async performance.")
        assert "Software Architect" in role or "Engineer" in role

    def test_infer_role_security(self, optimizer: MetaOptimizer):
        role = optimizer.infer_role("Review this JWT auth token implementation for OWASP vulnerabilities.")
        assert "Cybersecurity" in role or "Security" in role

    def test_extract_clean_task(self, optimizer: MetaOptimizer):
        raw = "Please kindly help me write a function that parses CSV data"
        clean = optimizer.extract_clean_task(raw)
        assert "Please kindly" not in clean
        assert "parses CSV data" in clean

    def test_optimize_anthropic_xml(self, optimizer: MetaOptimizer):
        prompt = "Write a Python script to scrape product prices from HTML."
        res = optimizer.optimize(prompt, target_provider=ProviderTarget.ANTHROPIC_XML.value)

        assert isinstance(res, OptimizedPromptResult)
        assert res.target_provider == ProviderTarget.ANTHROPIC_XML.value
        assert "<instructions>" in res.optimized_prompt
        assert "<constraints>" in res.optimized_prompt
        assert "<output_format>" in res.optimized_prompt
        assert "<input_data>" in res.optimized_prompt
        assert res.system_message is not None
        assert "You are" in res.system_message

    def test_optimize_openai_chat(self, optimizer: MetaOptimizer):
        prompt = "Extract customer sentiment from these support tickets."
        res = optimizer.optimize(prompt, target_provider=ProviderTarget.OPENAI_CHAT.value)

        assert res.target_provider == ProviderTarget.OPENAI_CHAT.value
        assert "## Objective" in res.optimized_prompt
        assert "## Instructions" in res.optimized_prompt
        assert res.system_message is not None
        assert "# Role & Directive" in res.system_message

    def test_optimize_google_gemini(self, optimizer: MetaOptimizer):
        prompt = "Explain quantum entanglement to high school students."
        res = optimizer.optimize(prompt, target_provider=ProviderTarget.GOOGLE_GEMINI.value)

        assert res.target_provider == ProviderTarget.GOOGLE_GEMINI.value
        assert "# Task" in res.optimized_prompt
        assert "## Guidelines & Instructions" in res.optimized_prompt
        assert "## Constraints & Guardrails" in res.optimized_prompt

    def test_optimize_generic_markdown(self, optimizer: MetaOptimizer):
        prompt = "Create a 30-day fitness plan."
        res = optimizer.optimize(prompt, target_provider=ProviderTarget.GENERIC_MARKDOWN.value)

        assert "### Role & Persona" in res.optimized_prompt
        assert "### Core Objective" in res.optimized_prompt

    def test_optimize_with_few_shots_and_context(self, optimizer: MetaOptimizer):
        prompt = "Classify customer feedback"
        few_shots = [
            FewShotExample(
                input_text="Great app, fast support!",
                output_text='{"sentiment": "positive", "score": 0.95}',
            )
        ]
        res = optimizer.optimize(
            prompt,
            target_provider=ProviderTarget.ANTHROPIC_XML.value,
            context="Domain: E-commerce SaaS application.",
            few_shots=few_shots,
        )
        assert "<context>" in res.optimized_prompt
        assert "Domain: E-commerce" in res.optimized_prompt
        assert "<examples>" in res.optimized_prompt
        assert "Great app, fast support!" in res.optimized_prompt

    def test_cot_reasoning_generation(self, optimizer: MetaOptimizer):
        steps = optimizer.generate_cot_steps("Analyze revenue data")
        assert len(steps) >= 3
        assert any("metric" in s.lower() or "data" in s.lower() for s in steps)
