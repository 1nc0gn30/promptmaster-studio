"""Global pytest configuration and fixtures for PromptMaster Studio test suite."""

import os
import sys
from pathlib import Path

# Ensure src/ is on sys.path for test imports
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

from promptmaster_studio.models import (
    FewShotExample,
    LessonDifficulty,
    LinterCategory,
    LinterIssue,
    LinterSeverity,
    PromptAnalysisResult,
    PromptTemplate,
    PromptVariable,
    ProviderTarget,
    VariableType,
)


@pytest.fixture
def sample_variable() -> PromptVariable:
    """Fixture providing a sample prompt variable."""
    return PromptVariable(
        name="topic",
        description="The topic to explain",
        var_type="string",
        default_value="Quantum Computing",
        required=True,
        sample_value="Photosynthesis",
    )


@pytest.fixture
def sample_few_shot() -> FewShotExample:
    """Fixture providing a sample few-shot example."""
    return FewShotExample(
        input_text="Explain gravity in simple terms.",
        output_text="Gravity is an invisible force that pulls objects toward each other.",
        explanation="Simple, jargon-free explanation.",
    )


@pytest.fixture
def sample_template(sample_variable: PromptVariable, sample_few_shot: FewShotExample) -> PromptTemplate:
    """Fixture providing a sample complete PromptTemplate."""
    return PromptTemplate(
        id="t-explainer-001",
        title="Concepts Explainer",
        description="Explains complex topics to non-technical audiences.",
        category="education",
        tags=["explainer", "education", "clarity"],
        template_str="You are an expert science educator. Please explain {{ topic }} in simple terms for a {{ audience:-general }} audience.",
        variables=[sample_variable],
        few_shot_examples=[sample_few_shot],
        recommended_models=["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"],
        target_provider=ProviderTarget.ANTHROPIC_XML.value,
        system_message="You are a clear, engaging teacher.",
    )
