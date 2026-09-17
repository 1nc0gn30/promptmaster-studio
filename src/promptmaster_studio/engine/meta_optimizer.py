"""Meta-prompt synthesizer and prompt restructuring engine.

Transforms unstructured, vague, or raw user prompts into enterprise-grade,
well-structured prompts with roles, explicit constraints, XML delimiters,
Chain-of-Thought reasoning steps, and provider-specific formatting.
100% Python Standard Library.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from promptmaster_studio.engine.tokenizer_estimator import TokenizerEstimator
from promptmaster_studio.models import (
    FewShotExample,
    OptimizedPromptResult,
    ProviderTarget,
)


class MetaOptimizer:
    """Enterprise meta-prompt optimizer and provider structure synthesizer."""

    # Role inference keyword heuristics
    ROLE_HEURISTICS: List[Tuple[re.Pattern, str]] = [
        (re.compile(r"(?i)\b(?:python|javascript|typescript|c\+\+|rust|golang|sql|code|refactor|debug|api|backend|frontend|function|class|algorithm)\b"), "Principal Software Architect and Senior Code Engineer"),
        (re.compile(r"(?i)\b(?:data|analytics|pandas|numpy|dataframe|dataset|metric|chart|statistics|predict|ml|model|regression)\b"), "Senior Data Scientist and Quantitative Analytics Lead"),
        (re.compile(r"(?i)\b(?:security|vulnerability|exploit|auth|encryption|token|jwt|pci|owasp|cve|penetration)\b"), "Senior Cybersecurity Consultant and Application Security Specialist"),
        (re.compile(r"(?i)\b(?:copy|write|blog|article|content|email|newsletter|headline|story|marketing|pitch)\b"), "Master Direct-Response Copywriter and Editorial Strategist"),
        (re.compile(r"(?i)\b(?:product|roadmap|prd|feature|spec|user story|persona|mvp|kpi|ux)\b"), "Lead Technical Product Manager and Systems Designer"),
        (re.compile(r"(?i)\b(?:legal|contract|agreement|nda|compliance|clause|liability|terms)\b"), "Senior Legal Counsel and Contract Specialist"),
        (re.compile(r"(?i)\b(?:finance|financial|budget|valuation|dcf|p&l|balance sheet|invest|roi|forecast)\b"), "Chartered Financial Analyst (CFA) and Investment Strategist"),
        (re.compile(r"(?i)\b(?:translate|translation|localize|spanish|french|german|japanese|chinese)\b"), "Professional Technical Translator and Cultural Localization Specialist"),
        (re.compile(r"(?i)\b(?:tutor|teach|explain to me|learn|student|curriculum|beginner|guide)\b"), "Distinguished University Professor and Master Pedagogical Tutor"),
    ]

    def __init__(self) -> None:
        self.tokenizer = TokenizerEstimator()

    def infer_role(self, prompt: str) -> str:
        """Infer an optimal expert persona based on domain keywords in prompt."""
        # Check if user already explicitly defined a role
        role_match = re.search(
            r"(?i)\b(?:you are (?:an?|the)|act as (?:an?|the)|your role is)\s+([^.\n,]+)",
            prompt,
        )
        if role_match:
            return role_match.group(1).strip()

        for pattern, inferred_role in self.ROLE_HEURISTICS:
            if pattern.search(prompt):
                return inferred_role

        return "Elite AI Subject Matter Expert and Strategic Advisor"

    def extract_constraints(self, prompt: str) -> List[str]:
        """Extract explicit and implicit constraints from prompt text."""
        constraints: List[str] = []

        # Find negative constraints
        neg_matches = re.findall(
            r"(?i)\b(?:do not|don't|never|should not|must not|avoid|without)\s+([^\n.,;]+)",
            prompt,
        )
        for match in neg_matches:
            clean = match.strip()
            if clean and len(clean) > 3:
                constraints.append(f"Do not {clean}")

        # Find format / length constraints
        format_matches = re.findall(
            r"(?i)\b(?:only\s+json|format\s+as\s+[a-zA-Z0-9_-]+|in\s+\d+\s+(?:words|bullets|paragraphs)|no\s+yapping|concise|bullet points?)\b",
            prompt,
        )
        for match in format_matches:
            clean = match.strip()
            if clean:
                constraints.append(f"Adhere strictly to: {clean}")

        if not constraints:
            constraints = [
                "Maintain absolute factual precision; do not extrapolate beyond verified context.",
                "Ensure output is concise, structured, and free of conversational pleasantries.",
                "Adhere strictly to all specified formatting and structural guidelines.",
            ]

        return constraints

    def extract_clean_task(self, prompt: str) -> str:
        """Isolate core task objective by removing meta-framing and politeness."""
        task = prompt

        # Remove pleasantries
        task = re.sub(
            r"(?i)\b(?:please\s+kindly|kindly|could you please|can you please|i need you to|i want you to|help me)\b",
            "",
            task,
        )
        # Remove existing 'act as' phrases so we don't duplicate
        task = re.sub(
            r"(?i)\b(?:you are (?:an?|the)|act as (?:an?|the)|your role is)\s+[^.\n,]+[.\n]?",
            "",
            task,
        )
        task = re.sub(r"\n{3,}", "\n\n", task).strip()
        return task or "Execute the requested objective with maximum rigor and clarity."

    def generate_cot_steps(self, task: str) -> List[str]:
        """Synthesize structured Chain-of-Thought reasoning steps tailored to task."""
        task_lower = task.lower()

        if any(w in task_lower for w in ["code", "refactor", "algorithm", "function", "debug"]):
            return [
                "Analyze the inputs, edge cases, algorithmic time/space constraints, and dependencies.",
                "Formulate the modular code structure, typing contracts, and error handling paths.",
                "Verify logic step-by-step for null safety, boundary conditions, and performance bottlenecks.",
                "Assemble the final clean, production-ready code with concise docstrings.",
            ]
        elif any(w in task_lower for w in ["data", "analyze", "analytics", "metric", "dataset"]):
            return [
                "Identify key metrics, data schemas, statistical properties, and anomaly potentials.",
                "Decompose analytical dimensions, segmentations, and comparative baselines.",
                "Synthesize quantitative observations and evaluate confidence levels.",
                "Formulate actionable business insights and recommendations based on findings.",
            ]
        elif any(w in task_lower for w in ["write", "article", "copy", "email", "pitch"]):
            return [
                "Analyze target audience psychology, core emotional hook, and primary conversion goal.",
                "Outline structural flow: Attention -> Interest -> Desire -> Action (AIDA).",
                "Draft high-impact copy emphasizing benefits over features with vivid framing.",
                "Review and refine tone, rhythm, readability grade level, and call-to-action clarity.",
            ]
        else:
            return [
                "Deconstruct the core request into fundamental requirements and boundary constraints.",
                "Retrieve and synthesize relevant domain principles and structured context.",
                "Evaluate potential approaches, verifying completeness and logical consistency.",
                "Draft the final response adhering strictly to the required output schema.",
            ]

    def _format_anthropic_xml(
        self,
        role: str,
        task: str,
        instructions: List[str],
        constraints: List[str],
        output_format: str,
        context: Optional[str],
        include_cot: bool,
        cot_steps: List[str],
        few_shots: Optional[List[FewShotExample]],
    ) -> Tuple[str, Optional[str]]:
        """Format prompt according to Anthropic Claude XML best practices."""
        system_msg = f"You are {role}. You follow instructions with precision, critical analysis, and unwavering adherence to constraints."

        sections: List[str] = []

        # Instructions Section
        instr_body = "\n".join(f"- {inst}" for inst in instructions)
        sections.append(f"<instructions>\n{instr_body}\n</instructions>")

        # Context Section (if present)
        if context and context.strip():
            sections.append(f"<context>\n{context.strip()}\n</context>")

        # Constraints Section
        constr_body = "\n".join(f"- {c}" for c in constraints)
        sections.append(f"<constraints>\n{constr_body}\n</constraints>")

        # Few-Shot Examples (if present)
        if few_shots:
            examples_xml: List[str] = ["<examples>"]
            for idx, ex in enumerate(few_shots, 1):
                examples_xml.append(f"  <example id=\"{idx}\">")
                examples_xml.append(f"    <input>\n{ex.input_text}\n    </input>")
                examples_xml.append(f"    <output>\n{ex.output_text}\n    </output>")
                if ex.explanation:
                    examples_xml.append(f"    <explanation>\n{ex.explanation}\n    </explanation>")
                examples_xml.append("  </example>")
            examples_xml.append("</examples>")
            sections.append("\n".join(examples_xml))

        # Output Format Section
        sections.append(f"<output_format>\n{output_format}\n</output_format>")

        # Chain of Thought directive
        if include_cot:
            cot_body = "\n".join(f"{i+1}. {s}" for i, s in enumerate(cot_steps))
            sections.append(
                f"<thinking_process>\nBefore providing your final response, systematically reason through these steps inside <thinking> tags:\n{cot_body}\n</thinking_process>"
            )

        # Input data wrapper
        sections.append("<input_data>\n{{input}}\n</input_data>")

        final_prompt = "\n\n".join(sections)
        return final_prompt, system_msg

    def _format_openai_chat(
        self,
        role: str,
        task: str,
        instructions: List[str],
        constraints: List[str],
        output_format: str,
        context: Optional[str],
        include_cot: bool,
        cot_steps: List[str],
        few_shots: Optional[List[FewShotExample]],
    ) -> Tuple[str, Optional[str]]:
        """Format prompt according to OpenAI Developer / System message conventions."""
        system_lines: List[str] = [
            f"# Role & Directive\nYou are {role}.",
            "\n## Core Operating Rules",
        ]
        for c in constraints:
            system_lines.append(f"- {c}")

        system_msg = "\n".join(system_lines)

        user_lines: List[str] = [
            f"## Objective\n{task}",
            "\n## Instructions",
        ]
        for inst in instructions:
            user_lines.append(f"- {inst}")

        if context and context.strip():
            user_lines.append(f"\n## Context & Reference Material\n```\n{context.strip()}\n```")

        if few_shots:
            user_lines.append("\n## Reference Examples")
            for idx, ex in enumerate(few_shots, 1):
                user_lines.append(f"### Example {idx}\n**Input:**\n```\n{ex.input_text}\n```\n**Expected Output:**\n```\n{ex.output_text}\n```")

        user_lines.append(f"\n## Output Specification\n{output_format}")

        if include_cot:
            cot_body = "\n".join(f"{i+1}. {s}" for i, s in enumerate(cot_steps))
            user_lines.append(f"\n## Step-by-Step Reasoning\nFollow this reasoning protocol:\n{cot_body}")

        user_lines.append("\n## Input\n```\n{{input}}\n```")

        return "\n".join(user_lines), system_msg

    def _format_google_gemini(
        self,
        role: str,
        task: str,
        instructions: List[str],
        constraints: List[str],
        output_format: str,
        context: Optional[str],
        include_cot: bool,
        cot_steps: List[str],
        few_shots: Optional[List[FewShotExample]],
    ) -> Tuple[str, Optional[str]]:
        """Format prompt according to Google Gemini structured markdown guidelines."""
        system_msg = f"System Directive: You are {role}. Provide clear, direct, and structurally organized responses."

        lines: List[str] = [
            f"# Task: {task}",
            "\n## Guidelines & Instructions",
        ]
        for inst in instructions:
            lines.append(f"- {inst}")

        if context and context.strip():
            lines.append(f"\n## Background Context\n{context.strip()}")

        lines.append("\n## Constraints & Guardrails")
        for c in constraints:
            lines.append(f"- {c}")

        if few_shots:
            lines.append("\n## Few-Shot Input/Output Demonstrations")
            for idx, ex in enumerate(few_shots, 1):
                lines.append(f"Example {idx}:")
                lines.append(f"[INPUT]\n{ex.input_text}")
                lines.append(f"[OUTPUT]\n{ex.output_text}\n")

        lines.append(f"\n## Expected Output Schema\n{output_format}")

        if include_cot:
            cot_body = "\n".join(f"- Step {i+1}: {s}" for i, s in enumerate(cot_steps))
            lines.append(f"\n## Thought Protocol\n{cot_body}")

        lines.append("\n## Target Input\n{{input}}")

        return "\n".join(lines), system_msg

    def _format_generic_markdown(
        self,
        role: str,
        task: str,
        instructions: List[str],
        constraints: List[str],
        output_format: str,
        context: Optional[str],
        include_cot: bool,
        cot_steps: List[str],
        few_shots: Optional[List[FewShotExample]],
    ) -> Tuple[str, Optional[str]]:
        """Format prompt into clean, universally portable Markdown."""
        lines: List[str] = [
            f"### Role & Persona\nYou are {role}.",
            f"\n### Core Objective\n{task}",
            "\n### Step-by-Step Instructions",
        ]
        for inst in instructions:
            lines.append(f"1. {inst}")

        if context and context.strip():
            lines.append(f"\n### Context\n{context.strip()}")

        lines.append("\n### Constraints & Rules")
        for c in constraints:
            lines.append(f"- {c}")

        if few_shots:
            lines.append("\n### Examples")
            for idx, ex in enumerate(few_shots, 1):
                lines.append(f"**Example {idx}:**\n- Input: {ex.input_text}\n- Output: {ex.output_text}")

        lines.append(f"\n### Output Format\n{output_format}")

        if include_cot:
            cot_body = "\n".join(f"- {s}" for s in cot_steps)
            lines.append(f"\n### Reasoning Method\n{cot_body}")

        lines.append("\n### Input Data\n```\n{{input}}\n```")

        return "\n".join(lines), None

    def optimize(
        self,
        prompt: str,
        target_provider: str = ProviderTarget.ANTHROPIC_XML.value,
        include_cot: bool = True,
        role_override: Optional[str] = None,
        output_format: Optional[str] = None,
        constraints: Optional[List[str]] = None,
        context: Optional[str] = None,
        few_shots: Optional[List[FewShotExample]] = None,
    ) -> OptimizedPromptResult:
        """Transform raw prompt into a production structured prompt template.
        
        Args:
            prompt: Raw prompt text.
            target_provider: Target model provider format ('anthropic_xml', 'openai_chat', 'google_gemini', 'generic_markdown').
            include_cot: Whether to synthesize Chain-of-Thought reasoning steps.
            role_override: Custom role definition (defaults to inferred role).
            output_format: Custom output format directive (defaults to structured schema).
            constraints: Explicit constraints list.
            context: Supplemental context or documentation.
            few_shots: List of FewShotExample objects.
            
        Returns:
            OptimizedPromptResult dataclass instance.
        """
        raw_prompt = prompt.strip()
        tokens_before = self.tokenizer.count_tokens(raw_prompt)

        # 1. Determine Role
        role = role_override or self.infer_role(raw_prompt)

        # 2. Extract clean task & synthesized instructions
        clean_task = self.extract_clean_task(raw_prompt)
        instructions = [
            f"Analyze the incoming task requirements: {clean_task}",
            "Synthesize domain-accurate insights adhering strictly to the constraints.",
            "Structure the response cleanly according to the output specification without conversational padding.",
        ]

        # 3. Determine Constraints
        active_constraints = list(constraints or [])
        if not active_constraints:
            active_constraints = self.extract_constraints(raw_prompt)

        # 4. Determine Output Format
        if not output_format:
            if "json" in raw_prompt.lower():
                output_format = "Provide your final response as valid, RFC 8259 compliant JSON. Do not include extra commentary outside the JSON block."
            elif "code" in raw_prompt.lower() or "function" in raw_prompt.lower():
                output_format = "Provide complete, clean, self-contained code inside appropriate Markdown fences with concise inline comments."
            else:
                output_format = "Provide a structured, modular response with clear headings, bullet points, and high information density."

        # 5. Determine CoT steps
        cot_steps = self.generate_cot_steps(clean_task) if include_cot else []

        # 6. Format according to target provider
        provider_enum = target_provider.lower()
        if provider_enum == ProviderTarget.ANTHROPIC_XML.value:
            optimized_text, sys_msg = self._format_anthropic_xml(
                role, clean_task, instructions, active_constraints, output_format, context, include_cot, cot_steps, few_shots
            )
            added_tags = ["<instructions>", "<constraints>", "<output_format>", "<input_data>"]
            if include_cot:
                added_tags.append("<thinking_process>")
            if context:
                added_tags.append("<context>")
            if few_shots:
                added_tags.append("<examples>")
        elif provider_enum == ProviderTarget.OPENAI_CHAT.value:
            optimized_text, sys_msg = self._format_openai_chat(
                role, clean_task, instructions, active_constraints, output_format, context, include_cot, cot_steps, few_shots
            )
            added_tags = ["# Role & Directive", "## Objective", "## Constraints", "## Output Specification"]
        elif provider_enum == ProviderTarget.GOOGLE_GEMINI.value:
            optimized_text, sys_msg = self._format_google_gemini(
                role, clean_task, instructions, active_constraints, output_format, context, include_cot, cot_steps, few_shots
            )
            added_tags = ["# Task", "## Guidelines", "## Constraints & Guardrails", "## Expected Output Schema"]
        else:
            optimized_text, sys_msg = self._format_generic_markdown(
                role, clean_task, instructions, active_constraints, output_format, context, include_cot, cot_steps, few_shots
            )
            added_tags = ["### Role & Persona", "### Core Objective", "### Constraints & Rules", "### Output Format"]

        tokens_after = self.tokenizer.count_tokens(optimized_text) + (self.tokenizer.count_tokens(sys_msg) if sys_msg else 0)

        improvements: List[str] = [
            f"Synthesized explicit expert persona: '{role}'.",
            "Structured instructions into clean, unambiguous directive points.",
            f"Added {len(active_constraints)} deterministic constraints and boundary guardrails.",
            f"Applied '{target_provider}' layout with dedicated delimiters.",
        ]
        if include_cot:
            improvements.append(f"Injected {len(cot_steps)}-step Chain-of-Thought reasoning protocol.")
        if sys_msg:
            improvements.append("Separated system-level directives from user-level task context.")

        sections_dict: Dict[str, str] = {
            "role": role,
            "task": clean_task,
            "constraints": "\n".join(active_constraints),
            "output_format": output_format,
        }
        if context:
            sections_dict["context"] = context

        return OptimizedPromptResult(
            original_prompt=raw_prompt,
            optimized_prompt=optimized_text,
            system_message=sys_msg,
            target_provider=target_provider,
            strategy_used="role_task_xml_decomposition",
            sections=sections_dict,
            added_tags=added_tags,
            estimated_tokens_before=tokens_before,
            estimated_tokens_after=tokens_after,
            improvements=improvements,
            variables_extracted=["input"],
            cot_steps=cot_steps,
        )
