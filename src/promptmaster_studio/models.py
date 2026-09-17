"""Data models and schemas for PromptMaster Studio.

Unified dataclasses for prompt templates, variables, few-shot examples,
linting issues, prompt analysis results, optimization outputs,
curriculum lessons, and model context budgets.
100% Python Standard Library.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class ProviderTarget(str, Enum):
    """Supported target LLM provider prompt structures."""
    ANTHROPIC_XML = "anthropic_xml"
    OPENAI_CHAT = "openai_chat"
    GOOGLE_GEMINI = "google_gemini"
    GENERIC_MARKDOWN = "generic_markdown"


class VariableType(str, Enum):
    """Variable types supported in templates."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    LIST = "list"
    OBJECT = "object"


class LinterSeverity(str, Enum):
    """Severity levels for linting issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LinterCategory(str, Enum):
    """Categories of static prompt analysis."""
    CLARITY = "clarity"
    SECURITY = "security"
    FORMATTING = "formatting"
    CONSTRAINTS = "constraints"
    EFFICIENCY = "efficiency"
    STRUCTURE = "structure"


class LessonDifficulty(str, Enum):
    """Difficulty rating for curriculum lessons."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


@dataclass
class PromptVariable:
    """Specification and default constraints for a template variable."""
    name: str
    description: str = ""
    var_type: str = "string"
    default_value: Any = None
    required: bool = True
    sample_value: Any = None
    validation_regex: Optional[str] = None
    enum_values: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert variable to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PromptVariable:
        """Construct PromptVariable from dictionary."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            var_type=data.get("var_type", "string"),
            default_value=data.get("default_value"),
            required=data.get("required", True),
            sample_value=data.get("sample_value"),
            validation_regex=data.get("validation_regex"),
            enum_values=data.get("enum_values"),
        )


@dataclass
class FewShotExample:
    """A paired input-output example illustrating target model performance."""
    input_text: str
    output_text: str
    explanation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert few-shot example to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FewShotExample:
        """Construct FewShotExample from dictionary."""
        return cls(
            input_text=data.get("input_text", ""),
            output_text=data.get("output_text", ""),
            explanation=data.get("explanation"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PromptTemplate:
    """Complete production-ready prompt template schema."""
    id: str
    title: str
    description: str
    category: str
    tags: List[str] = field(default_factory=list)
    template_str: str = ""
    variables: List[PromptVariable] = field(default_factory=list)
    few_shot_examples: List[FewShotExample] = field(default_factory=list)
    recommended_models: List[str] = field(default_factory=list)
    target_provider: str = ProviderTarget.GENERIC_MARKDOWN.value
    system_message: Optional[str] = None
    version: str = "1.0.0"
    author: str = "PromptMaster Studio"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now_iso
        if not self.updated_at:
            self.updated_at = now_iso

    def to_dict(self) -> Dict[str, Any]:
        """Convert prompt template to serializable dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "tags": list(self.tags),
            "template_str": self.template_str,
            "variables": [v.to_dict() for v in self.variables],
            "few_shot_examples": [e.to_dict() for e in self.few_shot_examples],
            "recommended_models": list(self.recommended_models),
            "target_provider": self.target_provider,
            "system_message": self.system_message,
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize template to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PromptTemplate:
        """Construct PromptTemplate from dictionary."""
        vars_raw = data.get("variables", [])
        variables = [
            PromptVariable.from_dict(v) if isinstance(v, dict) else v
            for v in vars_raw
        ]
        examples_raw = data.get("few_shot_examples", [])
        few_shot_examples = [
            FewShotExample.from_dict(e) if isinstance(e, dict) else e
            for e in examples_raw
        ]
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            template_str=data.get("template_str", ""),
            variables=variables,
            few_shot_examples=few_shot_examples,
            recommended_models=data.get("recommended_models", []),
            target_provider=data.get("target_provider", ProviderTarget.GENERIC_MARKDOWN.value),
            system_message=data.get("system_message"),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "PromptMaster Studio"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> PromptTemplate:
        """Construct PromptTemplate from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class LinterIssue:
    """A quality, security, or structural issue flagged by the static prompt analyzer."""
    rule_id: str
    message: str
    severity: str
    category: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    suggestion: Optional[str] = None
    matched_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert linter issue to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LinterIssue:
        """Construct LinterIssue from dictionary."""
        return cls(
            rule_id=data.get("rule_id", ""),
            message=data.get("message", ""),
            severity=data.get("severity", LinterSeverity.WARNING.value),
            category=data.get("category", LinterCategory.CLARITY.value),
            line_number=data.get("line_number"),
            column=data.get("column"),
            suggestion=data.get("suggestion"),
            matched_text=data.get("matched_text"),
        )


@dataclass
class PromptAnalysisResult:
    """Comprehensive evaluation scores and findings for a prompt."""
    clarity_score: float
    security_score: float
    structure_score: float
    overall_score: float
    issues: List[LinterIssue] = field(default_factory=list)
    estimated_tokens: int = 0
    word_count: int = 0
    char_count: int = 0
    detected_variables: List[str] = field(default_factory=list)
    positive_to_negative_ratio: float = 1.0
    suggestions_summary: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def keys(self) -> List[str]:
        return list(self.to_dict().keys())

    def items(self) -> List[Tuple[str, Any]]:
        return list(self.to_dict().items())

    def __iter__(self):
        return iter(self.to_dict())

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis result to dictionary."""
        return {
            "clarity_score": round(self.clarity_score, 1),
            "security_score": round(self.security_score, 1),
            "structure_score": round(self.structure_score, 1),
            "overall_score": round(self.overall_score, 1),
            "issues": [i.to_dict() for i in self.issues],
            "estimated_tokens": self.estimated_tokens,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "detected_variables": list(self.detected_variables),
            "positive_to_negative_ratio": round(self.positive_to_negative_ratio, 2),
            "suggestions_summary": list(self.suggestions_summary),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PromptAnalysisResult:
        """Construct PromptAnalysisResult from dictionary."""
        issues_raw = data.get("issues", [])
        issues = [
            LinterIssue.from_dict(i) if isinstance(i, dict) else i
            for i in issues_raw
        ]
        return cls(
            clarity_score=float(data.get("clarity_score", 0.0)),
            security_score=float(data.get("security_score", 0.0)),
            structure_score=float(data.get("structure_score", 0.0)),
            overall_score=float(data.get("overall_score", 0.0)),
            issues=issues,
            estimated_tokens=int(data.get("estimated_tokens", 0)),
            word_count=int(data.get("word_count", 0)),
            char_count=int(data.get("char_count", 0)),
            detected_variables=data.get("detected_variables", []),
            positive_to_negative_ratio=float(data.get("positive_to_negative_ratio", 1.0)),
            suggestions_summary=data.get("suggestions_summary", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class OptimizedPromptResult:
    """Result of transforming and synthesizing a prompt via the meta-optimizer."""
    original_prompt: str
    optimized_prompt: str
    system_message: Optional[str] = None
    target_provider: str = ProviderTarget.ANTHROPIC_XML.value
    strategy_used: str = "role_task_xml_decomposition"
    sections: Dict[str, str] = field(default_factory=dict)
    added_tags: List[str] = field(default_factory=list)
    estimated_tokens_before: int = 0
    estimated_tokens_after: int = 0
    improvements: List[str] = field(default_factory=list)
    variables_extracted: List[str] = field(default_factory=list)
    cot_steps: List[str] = field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def keys(self) -> List[str]:
        return list(self.to_dict().keys())

    def items(self) -> List[Tuple[str, Any]]:
        return list(self.to_dict().items())

    def __iter__(self):
        return iter(self.to_dict())

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def to_dict(self) -> Dict[str, Any]:
        """Convert optimization result to dictionary."""
        return {
            "original_prompt": self.original_prompt,
            "optimized_prompt": self.optimized_prompt,
            "system_message": self.system_message,
            "target_provider": self.target_provider,
            "strategy_used": self.strategy_used,
            "sections": dict(self.sections),
            "added_tags": list(self.added_tags),
            "estimated_tokens_before": self.estimated_tokens_before,
            "estimated_tokens_after": self.estimated_tokens_after,
            "improvements": list(self.improvements),
            "variables_extracted": list(self.variables_extracted),
            "cot_steps": list(self.cot_steps),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OptimizedPromptResult:
        """Construct OptimizedPromptResult from dictionary."""
        return cls(
            original_prompt=data.get("original_prompt", ""),
            optimized_prompt=data.get("optimized_prompt", ""),
            system_message=data.get("system_message"),
            target_provider=data.get("target_provider", ProviderTarget.ANTHROPIC_XML.value),
            strategy_used=data.get("strategy_used", "role_task_xml_decomposition"),
            sections=data.get("sections", {}),
            added_tags=data.get("added_tags", []),
            estimated_tokens_before=int(data.get("estimated_tokens_before", 0)),
            estimated_tokens_after=int(data.get("estimated_tokens_after", 0)),
            improvements=data.get("improvements", []),
            variables_extracted=data.get("variables_extracted", []),
            cot_steps=data.get("cot_steps", []),
        )


@dataclass
class CurriculumLesson:
    """Educational lesson covering prompt engineering patterns and mastery."""
    id: str
    title: str
    category: str
    difficulty: str
    estimated_minutes: int
    summary: str
    content_markdown: str
    key_takeaways: List[str] = field(default_factory=list)
    exercises: List[Dict[str, Any]] = field(default_factory=list)
    sample_before_prompt: str = ""
    sample_after_prompt: str = ""
    related_template_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    order: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert curriculum lesson to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "difficulty": self.difficulty,
            "estimated_minutes": self.estimated_minutes,
            "summary": self.summary,
            "content_markdown": self.content_markdown,
            "key_takeaways": list(self.key_takeaways),
            "exercises": list(self.exercises),
            "sample_before_prompt": self.sample_before_prompt,
            "sample_after_prompt": self.sample_after_prompt,
            "related_template_ids": list(self.related_template_ids),
            "tags": list(self.tags),
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CurriculumLesson:
        """Construct CurriculumLesson from dictionary."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            category=data.get("category", "foundations"),
            difficulty=data.get("difficulty", LessonDifficulty.BEGINNER.value),
            estimated_minutes=int(data.get("estimated_minutes", 10)),
            summary=data.get("summary", ""),
            content_markdown=data.get("content_markdown", ""),
            key_takeaways=data.get("key_takeaways", []),
            exercises=data.get("exercises", []),
            sample_before_prompt=data.get("sample_before_prompt", ""),
            sample_after_prompt=data.get("sample_after_prompt", ""),
            related_template_ids=data.get("related_template_ids", []),
            tags=data.get("tags", []),
            order=int(data.get("order", 0)),
        )


@dataclass
class ModelSpec:
    """Technical specification and pricing for an LLM model."""
    name: str
    family: str
    context_window: int
    max_output_tokens: int
    cost_per_million_input: float
    cost_per_million_output: float
    supports_system_prompt: bool = True
    supports_vision: bool = False
    supports_json_mode: bool = True
    tokenizer_type: str = "cl100k_base"

    def to_dict(self) -> Dict[str, Any]:
        """Convert model specification to dictionary."""
        return asdict(self)


@dataclass
class ContextBudgetReport:
    """Evaluation of prompt token usage against a specific model's context envelope."""
    model_name: str
    family: str
    prompt_tokens: int
    estimated_output_tokens: int
    total_tokens: int
    context_window: int
    remaining_context: int
    context_usage_percent: float
    estimated_cost_usd: float
    fits_in_context: bool
    warning_level: str
    recommendations: List[str] = field(default_factory=list)
    estimated_tokens: int = 0

    def __post_init__(self) -> None:
        if not self.estimated_tokens:
            self.estimated_tokens = self.prompt_tokens

    def __getitem__(self, key: str) -> Any:
        if key == "estimated_tokens":
            return self.prompt_tokens
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        if key == "estimated_tokens":
            return self.prompt_tokens
        return getattr(self, key, default)

    def keys(self) -> List[str]:
        return list(self.to_dict().keys())

    def items(self) -> List[Tuple[str, Any]]:
        return list(self.to_dict().items())

    def __iter__(self):
        return iter(self.to_dict())

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) or key == "estimated_tokens"

    def to_dict(self) -> Dict[str, Any]:
        """Convert budget report to dictionary."""
        return {
            "model_name": self.model_name,
            "family": self.family,
            "estimated_tokens": self.prompt_tokens,
            "prompt_tokens": self.prompt_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "total_tokens": self.total_tokens,
            "context_window": self.context_window,
            "remaining_context": self.remaining_context,
            "context_usage_percent": round(self.context_usage_percent, 2),
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "fits_in_context": self.fits_in_context,
            "warning_level": self.warning_level,
            "recommendations": list(self.recommendations),
        }
