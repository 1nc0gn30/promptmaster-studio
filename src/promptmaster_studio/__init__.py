"""PromptMaster Studio - Enterprise Prompt Engineering, Meta-Optimization & Static Linting Toolkit.

100% Python Standard Library.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from promptmaster_studio.compat import (
    DEFAULT_ENCODING_FALLBACKS,
    IS_CYGWIN,
    IS_LINUX,
    IS_MACOS,
    IS_TERMUX,
    IS_WINDOWS,
    SYSTEM,
    atomic_write_bytes,
    atomic_write_text,
    get_app_dir,
    get_platform_info,
    read_json_safe,
    read_text_safe,
    safe_mkdir,
    safe_path,
    safe_remove,
    sanitize_filename,
    write_json_safe,
)
from promptmaster_studio.engine import (
    CURRICULUM_CATALOG,
    LESSONS_CATALOG,
    MODEL_CATALOG,
    TEMPLATES_CATALOG,
    BuiltinFilters,
    CurriculumDB,
    MetaOptimizer,
    PromptLinter,
    PromptTemplateEngine,
    TemplateError,
    TemplateSyntaxError,
    TokenizerEstimator,
    VariableMissingError,
    VariableValidationError,
    get_all_tags,
    get_categories,
    get_lesson,
    get_template,
    list_lessons,
    list_templates,
    prune_prompt_tokens,
    rank_few_shot_examples,
    search_curriculum,
    AdversarialRedTeamSimulator,
    RedTeamSimulationReport,
    RedTeamAttackFinding,
    JailbreakAttackVector,
    ATTACK_VECTORS,
)
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

__version__ = "1.0.0"
__author__ = "PromptMaster Studio Team"
__license__ = "MIT"

# Module singletons for fast top-level access
_engine = PromptTemplateEngine()
_linter = PromptLinter()
_optimizer = MetaOptimizer()
_tokenizer = TokenizerEstimator()


def optimize_prompt(
    prompt: str,
    target: Optional[str] = None,
    target_provider: Optional[str] = None,
    cot: bool = True,
    persona: Optional[str] = None,
    role: Optional[str] = None,
    constraints: Optional[List[str]] = None,
    xml_tags: bool = True,
    context: Optional[str] = None,
    output_format: Optional[str] = None,
    few_shots: Optional[List[FewShotExample]] = None,
) -> OptimizedPromptResult:
    """Optimize a prompt for a specified target model provider format."""
    chosen_target = target_provider or target or ProviderTarget.ANTHROPIC_XML.value
    # Map common short names
    t_clean = chosen_target.lower()
    if "anthropic" in t_clean or "claude" in t_clean or "xml" in t_clean:
        resolved_target = ProviderTarget.ANTHROPIC_XML.value
    elif "openai" in t_clean or "chat" in t_clean or "gpt" in t_clean:
        resolved_target = ProviderTarget.OPENAI_CHAT.value
    elif "gemini" in t_clean or "google" in t_clean:
        resolved_target = ProviderTarget.GOOGLE_GEMINI.value
    else:
        resolved_target = ProviderTarget.GENERIC_MARKDOWN.value

    chosen_role = persona or role
    return _optimizer.optimize(
        prompt=prompt,
        target_provider=resolved_target,
        include_cot=cot,
        role_override=chosen_role,
        output_format=output_format,
        constraints=constraints,
        context=context,
        few_shots=few_shots,
    )


def lint_prompt(prompt: str, target: Optional[str] = None) -> PromptAnalysisResult:
    """Perform static quality and security analysis on a prompt."""
    return _linter.lint(prompt)


def render_template(
    template: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    *,
    template_str: Optional[str] = None,
    strict: bool = False,
    **kwargs: Any,
) -> str:
    """Render a template string or named template ID with variable interpolation."""
    raw = template if template is not None else template_str
    if isinstance(raw, dict) and variables is None:
        raw, variables = "", raw
    if raw is None:
        raw = ""

    # Check if raw is a known template ID (only if short and no template syntax)
    if isinstance(raw, str) and not ("\n" in raw or "{{" in raw or " " in raw or len(raw) > 80):
        catalog_match = get_template(raw)
        if catalog_match is not None:
            return _engine.render_template(catalog_match, variables, strict=strict)

    return _engine.render(str(raw), variables, strict=strict)


def estimate_tokens(
    prompt_or_text: Optional[str] = None,
    text: Optional[str] = None,
    model: str = "gpt-4o",
    expected_output: int = 1000,
    expected_output_tokens: Optional[int] = None,
) -> ContextBudgetReport:
    """Estimate token counts and context budget for a prompt."""
    target_text = prompt_or_text if prompt_or_text is not None else (text or "")
    out_tokens = expected_output_tokens if expected_output_tokens is not None else expected_output
    return _tokenizer.analyze_budget(
        prompt_text=target_text,
        model_name=model,
        expected_output_tokens=out_tokens,
    )


def get_prompt_templates(
    template_id: Optional[str] = None,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    model: Optional[str] = None,
    search: Optional[str] = None,
) -> List[PromptTemplate]:
    """Retrieve all templates or filter by template_id, category, tag, or search query."""
    if template_id:
        match = get_template(template_id)
        return [match] if match is not None else []
    return list_templates(category=category, tag=tag, model=model, search=search)


def get_curriculum_lessons(
    lesson_id: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
) -> Union[List[CurriculumLesson], Optional[CurriculumLesson]]:
    """Retrieve all curriculum lessons or filter by lesson_id, category, difficulty, or search."""
    if lesson_id:
        return get_lesson(lesson_id)
    if search:
        return CurriculumDB.search(search)
    return list_lessons(category=category, difficulty=difficulty, tag=tag)


def get_model_specs(model_name: Optional[str] = None) -> Union[Dict[str, ModelSpec], Optional[ModelSpec]]:
    """Retrieve model specifications map or a single model specification."""
    if model_name:
        return _tokenizer.get_model(model_name)
    return MODEL_CATALOG


__all__ = [
    # Top-level API
    "optimize_prompt",
    "lint_prompt",
    "render_template",
    "estimate_tokens",
    "get_prompt_templates",
    "get_curriculum_lessons",
    "get_model_specs",
    "rank_few_shot_examples",
    "prune_prompt_tokens",
    # Models
    "ProviderTarget",
    "VariableType",
    "LinterSeverity",
    "LinterCategory",
    "LessonDifficulty",
    "PromptVariable",
    "FewShotExample",
    "PromptTemplate",
    "LinterIssue",
    "PromptAnalysisResult",
    "OptimizedPromptResult",
    "CurriculumLesson",
    "ModelSpec",
    "ContextBudgetReport",
    # Engine
    "PromptTemplateEngine",
    "MetaOptimizer",
    "PromptLinter",
    "TokenizerEstimator",
    "CurriculumDB",
    "BuiltinFilters",
    "TemplateError",
    "TemplateSyntaxError",
    "VariableMissingError",
    "VariableValidationError",
    "MODEL_CATALOG",
    "LESSONS_CATALOG",
    "CURRICULUM_CATALOG",
    "TEMPLATES_CATALOG",
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
    # Compat
    "DEFAULT_ENCODING_FALLBACKS",
    "IS_WINDOWS",
    "IS_MACOS",
    "IS_LINUX",
    "IS_TERMUX",
    "IS_CYGWIN",
    "SYSTEM",
    "get_platform_info",
    "sanitize_filename",
    "safe_path",
    "safe_mkdir",
    "atomic_write_text",
    "atomic_write_bytes",
    "read_text_safe",
    "read_json_safe",
    "write_json_safe",
    "safe_remove",
    "get_app_dir",
]
