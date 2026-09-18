"""PromptMaster Studio Core Engine Module.

Contains the template engine, meta-optimizer, static linter, tokenizer estimator,
and curriculum database.
"""

from __future__ import annotations

from promptmaster_studio.engine.curriculum_db import (
    CURRICULUM_CATALOG,
    LESSONS_CATALOG,
    TEMPLATES_CATALOG,
    CurriculumDB,
    get_all_tags,
    get_categories,
    get_lesson,
    get_template,
    list_lessons,
    list_templates,
    search_curriculum,
)
from promptmaster_studio.engine.linter import PromptLinter
from promptmaster_studio.engine.meta_optimizer import MetaOptimizer
from promptmaster_studio.engine.template_engine import (
    BuiltinFilters,
    PromptTemplateEngine,
    TemplateError,
    TemplateSyntaxError,
    VariableMissingError,
    VariableValidationError,
)
from promptmaster_studio.engine.few_shot_ranker import (
    prune_prompt_tokens,
    rank_few_shot_examples,
)
from promptmaster_studio.engine.adversarial_jailbreak import (
    ATTACK_VECTORS,
    AdversarialRedTeamSimulator,
    JailbreakAttackVector,
    RedTeamAttackFinding,
    RedTeamSimulationReport,
)
from promptmaster_studio.engine.cove_and_debate import (
    ChainOfVerificationEngine,
    CoVePipeline,
    CoVeStage,
    DebateEnsemble,
    DebatePersona,
    DebateRound,
    MultiAgentDebateSynthesizer,
    cove_engine,
    debate_synthesizer,
    decompose_cove_pipeline,
    synthesize_debate_ensemble,
)
from promptmaster_studio.engine.tokenizer_estimator import (
    MODEL_CATALOG,
    TokenizerEstimator,
)

__all__ = [
    "BuiltinFilters",
    "PromptTemplateEngine",
    "TemplateError",
    "TemplateSyntaxError",
    "VariableMissingError",
    "VariableValidationError",
    "MetaOptimizer",
    "PromptLinter",
    "TokenizerEstimator",
    "MODEL_CATALOG",
    "LESSONS_CATALOG",
    "CURRICULUM_CATALOG",
    "TEMPLATES_CATALOG",
    "CurriculumDB",
    "get_lesson",
    "list_lessons",
    "get_template",
    "list_templates",
    "search_curriculum",
    "get_categories",
    "get_all_tags",
    "rank_few_shot_examples",
    "prune_prompt_tokens",
    "AdversarialRedTeamSimulator",
    "RedTeamSimulationReport",
    "RedTeamAttackFinding",
    "JailbreakAttackVector",
    "ATTACK_VECTORS",
    "ChainOfVerificationEngine",
    "CoVePipeline",
    "CoVeStage",
    "DebateEnsemble",
    "DebatePersona",
    "DebateRound",
    "MultiAgentDebateSynthesizer",
    "cove_engine",
    "debate_synthesizer",
    "decompose_cove_pipeline",
    "synthesize_debate_ensemble",
]
