"""Chain-of-Verification (CoVe) and Multi-Agent Debate Synthesis Engine.

Provides:
1. Chain-of-Verification (CoVe) 4-stage pipeline decomposition to eliminate hallucinations.
2. Multi-Agent Debate & Society-of-Mind ensemble synthesizer for multi-perspective reasoning.

100% Python Standard Library (zero external runtime dependencies).
"""

from __future__ import annotations

import dataclasses
import html
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Data Models: CoVe & Multi-Agent Debate
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class CoVeStage:
    """A distinct stage in the Chain-of-Verification sequence."""
    stage_number: int
    name: str
    description: str
    prompt_template: str
    instructions: str
    expected_output_format: str


@dataclasses.dataclass
class CoVePipeline:
    """Full 4-Stage Chain-of-Verification prompt decomposition."""
    task_description: str
    domain: str
    baseline_prompt: str
    question_generation_prompt: str
    verification_execution_prompt: str
    final_synthesis_prompt: str
    stages: List[CoVeStage]
    estimated_token_overhead: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_description": self.task_description,
            "domain": self.domain,
            "baseline_prompt": self.baseline_prompt,
            "question_generation_prompt": self.question_generation_prompt,
            "verification_execution_prompt": self.verification_execution_prompt,
            "final_synthesis_prompt": self.final_synthesis_prompt,
            "stages": [dataclasses.asdict(s) for s in self.stages],
            "estimated_token_overhead": self.estimated_token_overhead,
        }


@dataclasses.dataclass
class DebatePersona:
    """An agent persona in a multi-agent debate ensemble."""
    id: str
    role_name: str
    stance: str
    bias_objective: str
    system_prompt: str
    evaluation_criteria: List[str]


@dataclasses.dataclass
class DebateRound:
    """A round of discourse in the multi-agent debate."""
    round_number: int
    name: str
    participating_agents: List[str]
    interaction_protocol: str
    prompt_template: str


@dataclasses.dataclass
class DebateEnsemble:
    """Complete Multi-Agent Debate and Consensus Framework."""
    topic: str
    complexity_level: str
    personas: List[DebatePersona]
    rounds: List[DebateRound]
    arbiter_synthesis_prompt: str
    total_rounds: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "complexity_level": self.complexity_level,
            "personas": [dataclasses.asdict(p) for p in self.personas],
            "rounds": [dataclasses.asdict(r) for r in self.rounds],
            "arbiter_synthesis_prompt": self.arbiter_synthesis_prompt,
            "total_rounds": self.total_rounds,
        }


# ---------------------------------------------------------------------------
# Chain-of-Verification (CoVe) Engine
# ---------------------------------------------------------------------------

class ChainOfVerificationEngine:
    """Synthesizes Chain-of-Verification (CoVe) pipelines to prevent hallucination."""

    def __init__(self) -> None:
        pass

    def decompose(
        self,
        raw_prompt: str,
        domain: str = "general",
        target_provider: str = "anthropic_xml",
    ) -> CoVePipeline:
        """Decompose a raw user prompt into a rigorous 4-stage Chain-of-Verification pipeline."""
        clean_task = raw_prompt.strip()
        is_xml = "xml" in target_provider.lower() or "anthropic" in target_provider.lower()

        # Stage 1: Baseline Generation
        if is_xml:
            s1_prompt = f"""<task_context>
You are an expert specialist tasked with drafting a comprehensive, well-structured response to the user query.
Domain: {domain}
</task_context>

<user_query>
{clean_task}
</user_query>

<instructions>
1. Produce an initial comprehensive baseline draft.
2. Structure your points logically with clear headers.
3. Be explicit with assertions, figures, and historical or technical claims.
</instructions>
"""
        else:
            s1_prompt = f"""### Role & Context
You are an expert specialist in {domain}.

### User Query
{clean_task}

### Instructions
1. Produce a detailed baseline draft addressing the query thoroughly.
2. Clearly state all factual claims, numerical figures, and technical assertions.
"""

        # Stage 2: Plan Verification Questions
        if is_xml:
            s2_prompt = f"""<task_context>
You are an adversarial verification planner analyzing an initial draft for potential hallucinations, inaccurate dates, ungrounded statistics, and logical leaps.
Original Query: {clean_task}
</task_context>

<initial_draft>
{{baseline_draft}}
</initial_draft>

<instructions>
1. Extract every distinct factual, numerical, chronological, or causal claim made in the draft.
2. Formulate 4 to 8 self-contained, atomic verification questions that independently interrogate these claims.
3. CRITICAL: The verification questions must NOT assume the draft is correct; they must ask open, objective questions that can be answered independently.
</instructions>

<output_format>
Output a JSON array of verification queries:
[
  {{"question_id": "Q1", "target_claim": "...", "verification_question": "..."}},
  ...
]
</output_format>
"""
        else:
            s2_prompt = f"""### Role & Goal
You are a verification planner. Given the draft below, identify all testable claims and produce atomic verification questions.

### Original Query
{clean_task}

### Initial Draft
{{baseline_draft}}

### Instructions
Formulate 4 to 8 factual verification questions. Each question must be answerable independently without circular confirmation.
Output valid JSON array:
[
  {{"question_id": "Q1", "target_claim": "...", "verification_question": "..."}}
]
"""

        # Stage 3: Independent Execution
        if is_xml:
            s3_prompt = """<task_context>
You are an objective fact-checking engine. You are answering verification questions in strict isolation.
Do NOT hallucinate or assume context. If uncertain, state the exact degree of confidence or ambiguity.
</task_context>

<verification_questions>
{verification_questions_list}
</verification_questions>

<instructions>
For each question, provide an authoritative, cited or well-reasoned answer based strictly on verifiable facts.
Do NOT reference any previous draft. Answer each question from first principles.
</instructions>

<output_format>
Output a JSON array of answers:
[
  {"question_id": "Q1", "verified_answer": "...", "confidence": "high|medium|low"},
  ...
]
</output_format>
"""
        else:
            s3_prompt = """### Role
You are an isolated fact-checking engine answering targeted verification queries.

### Questions
{verification_questions_list}

### Instructions
Answer each question objectively without reference to any prior context.
Output valid JSON array:
[
  {"question_id": "Q1", "verified_answer": "...", "confidence": "high|medium|low"}
]
"""

        # Stage 4: Final Verified Synthesis
        if is_xml:
            s4_prompt = f"""<task_context>
You are the final synthesis editor. Your job is to reconcile the initial baseline draft with the independently verified facts, eliminating any discrepancies, errors, or hallucinations.
Original Query: {clean_task}
</task_context>

<initial_draft>
{{baseline_draft}}
</initial_draft>

<verified_facts>
{{verified_facts_data}}
</verified_facts>

<instructions>
1. Cross-reference every assertion in the initial draft against the verified facts.
2. If the initial draft contradicted a verified fact, rewrite that portion to reflect the verified reality.
3. Remove any claims that failed verification or lacked supporting grounding.
4. Produce the final polished response with maximum accuracy, clarity, and authority.
</instructions>

<final_verified_response>
<!-- Polished, fully verified answer here -->
</final_verified_response>
"""
        else:
            s4_prompt = f"""### Role & Objective
You are the final synthesis editor. Reconcile the initial draft with independently verified facts.

### Original Query
{clean_task}

### Initial Draft
{{baseline_draft}}

### Verified Facts
{{verified_facts_data}}

### Instructions
1. Replace all inaccurate statements in the draft with verified facts.
2. Discard ungrounded or speculative assertions.
3. Deliver the final high-precision answer.
"""

        stages = [
            CoVeStage(
                stage_number=1,
                name="Baseline Generation",
                description="Generate standard thorough response with all substantive assertions.",
                prompt_template=s1_prompt,
                instructions="Draft full baseline solution.",
                expected_output_format="Text / Markdown",
            ),
            CoVeStage(
                stage_number=2,
                name="Verification Planning",
                description="Extract claims and formulate independent verification questions.",
                prompt_template=s2_prompt,
                instructions="Decompose draft into 4-8 atomic verification questions.",
                expected_output_format="JSON Array of Verification Questions",
            ),
            CoVeStage(
                stage_number=3,
                name="Execution & Fact-Checking",
                description="Execute verification queries in isolated contexts without anchor bias.",
                prompt_template=s3_prompt,
                instructions="Answer verification questions objectively.",
                expected_output_format="JSON Array of Verified Answers",
            ),
            CoVeStage(
                stage_number=4,
                name="Final Verified Synthesis",
                description="Reconcile baseline against verified facts to produce hallucination-free final output.",
                prompt_template=s4_prompt,
                instructions="Synthesize final output removing all debunked claims.",
                expected_output_format="Polished Final Markdown / XML",
            ),
        ]

        # Estimated token overhead: ~800 tokens for templates + question/answer buffers
        estimated_overhead = 850 + len(clean_task.split()) * 3

        return CoVePipeline(
            task_description=clean_task,
            domain=domain,
            baseline_prompt=s1_prompt,
            question_generation_prompt=s2_prompt,
            verification_execution_prompt=s3_prompt,
            final_synthesis_prompt=s4_prompt,
            stages=stages,
            estimated_token_overhead=estimated_overhead,
        )


# ---------------------------------------------------------------------------
# Multi-Agent Debate & Society of Mind Synthesizer
# ---------------------------------------------------------------------------

class MultiAgentDebateSynthesizer:
    """Generates structured multi-agent debate ensembles to resolve complex reasoning tasks."""

    def __init__(self) -> None:
        pass

    def synthesize(
        self,
        topic: str,
        rounds: int = 3,
        domain: str = "general",
        style: str = "adversarial_collaborative",
    ) -> DebateEnsemble:
        """Create a 4-persona multi-round debate structure with arbiter consensus."""
        clean_topic = topic.strip()
        num_rounds = max(2, min(5, rounds))

        # Personas
        proponent = DebatePersona(
            id="proponent",
            role_name="Constructive Proponent (Thesis Advocate)",
            stance="In favor of progressive action, exploring opportunities and primary benefits.",
            bias_objective="Identify core strengths, constructive solutions, and high-upside paths.",
            system_prompt=(
                f"You are Agent A (Constructive Proponent) in a structured multi-agent deliberation on '{clean_topic}'. "
                "Your objective is to build the strongest possible positive case, presenting rigorous arguments, "
                "supporting evidence, and practical implementation blueprints. Remain intellectually honest while defending your thesis."
            ),
            evaluation_criteria=["Feasibility", "Upside potential", "Innovation", "Completeness"],
        )

        skeptic = DebatePersona(
            id="skeptic",
            role_name="Adversarial Skeptic & Red-Teamer (Antithesis)",
            stance="Critical examiner focusing on failure modes, hidden costs, security risks, and edge cases.",
            bias_objective="Stress-test all assertions, expose logical fallacies, and identify worst-case outcomes.",
            system_prompt=(
                f"You are Agent B (Adversarial Skeptic) in a multi-agent deliberation on '{clean_topic}'. "
                "Your duty is to relentlessly challenge assumptions, highlight fatal flaws, cost overruns, regulatory/security risks, "
                "and counter-intuitive consequences. Demand empirical proof and reject hand-waving optimism."
            ),
            evaluation_criteria=["Robustness under failure", "Risk surface", "Cost-benefit balance", "Empirical validity"],
        )

        realist = DebatePersona(
            id="pragmatist",
            role_name="Pragmatic Systems Architect (Synthesis Anchor)",
            stance="Operational realist focused on constraints, trade-offs, step-by-step rollout, and resource limits.",
            bias_objective="Bridge theoretical extremes with pragmatic trade-off analysis and resource allocation.",
            system_prompt=(
                f"You are Agent C (Pragmatic Systems Architect) analyzing '{clean_topic}'. "
                "You do not take ideological sides; instead, you evaluate real-world trade-offs, resource constraints, "
                "computational budgets, and operational maintenance burdens. Propose hybrid, phased implementations."
            ),
            evaluation_criteria=["Operational simplicity", "Resource efficiency", "Maintainability", "Graceful degradation"],
        )

        arbiter = DebatePersona(
            id="arbiter",
            role_name="Impartial Arbiter & Synthesis Judge",
            stance="Neutral magistrate reviewing arguments, scoring premise validity, and formulating final consensus.",
            bias_objective="Weigh evidence from all agents, eliminate bad arguments, and issue an actionable consensus verdict.",
            system_prompt=(
                f"You are the High Arbiter and Chief Magistrate presiding over the deliberation on '{clean_topic}'. "
                "You will review arguments from the Proponent, the Skeptic, and the Pragmatist. You will eliminate fallacies, "
                "highlight undisputed common ground, resolve irreconcilable trade-offs, and produce the definitive conclusion."
            ),
            evaluation_criteria=["Logical coherence", "Weight of evidence", "Pragmatic balance", "Decisive clarity"],
        )

        personas = [proponent, skeptic, realist, arbiter]

        # Rounds
        debate_rounds: List[DebateRound] = []

        # Round 1: Opening Arguments
        debate_rounds.append(
            DebateRound(
                round_number=1,
                name="Opening Thesis & Framing",
                participating_agents=["proponent", "skeptic", "pragmatist"],
                interaction_protocol="Independent simultaneous opening statements without prior exposure.",
                prompt_template=(
                    f"<debate_context>\n"
                    f"Topic: {clean_topic}\n"
                    f"Round 1: Opening Thesis\n"
                    f"</debate_context>\n"
                    f"Deliver your opening statement representing your assigned persona and analytical criteria."
                ),
            )
        )

        # Round 2: Cross-Examination & Rebuttal
        debate_rounds.append(
            DebateRound(
                round_number=2,
                name="Cross-Examination & Rebuttal",
                participating_agents=["proponent", "skeptic", "pragmatist"],
                interaction_protocol="Review peer opening statements, concede valid counterpoints, and rebut flaws.",
                prompt_template=(
                    f"<round_2_protocol>\n"
                    f"Topic: {clean_topic}\n"
                    f"Previous Statements: {{round_1_statements}}\n"
                    f"</round_2_protocol>\n"
                    f"1. Identify the single strongest point made by each of your counterparts and explicitly concede its merits.\n"
                    f"2. Identify the fatal flaw or unsubstantiated assumption in your counterparts' arguments and dismantle it.\n"
                    f"3. Refine your own proposal to accommodate the valid criticisms raised."
                ),
            )
        )

        # Round 3 (if requested): Hardening & Convergence
        if num_rounds >= 3:
            debate_rounds.append(
                DebateRound(
                    round_number=3,
                    name="Convergence & Compromise",
                    participating_agents=["proponent", "skeptic", "pragmatist"],
                    interaction_protocol="Formulate minimum viable consensus and irreconcilable core divergences.",
                    prompt_template=(
                        f"<round_3_protocol>\n"
                        f"Topic: {clean_topic}\n"
                        f"Deliberation History: {{round_2_statements}}\n"
                        f"</round_3_protocol>\n"
                        f"State: (a) What core tenets do all agents now agree upon? (b) What is the exact irreducible tradeoff remaining?"
                    ),
                )
            )

        # Round 4 (if requested): Edge-Case & Stress-Testing
        if num_rounds >= 4:
            debate_rounds.append(
                DebateRound(
                    round_number=4,
                    name="Edge-Case & Boundary Stress-Testing",
                    participating_agents=["proponent", "skeptic", "pragmatist"],
                    interaction_protocol="Subject emerging consensus to boundary conditions, extreme loads, and failure scenarios.",
                    prompt_template=(
                        f"<round_4_protocol>\n"
                        f"Topic: {clean_topic}\n"
                        f"Consensus Baseline: {{round_3_statements}}\n"
                        f"</round_4_protocol>\n"
                        f"Propose 2 extreme edge cases that could break the consensus plan, and provide protective countermeasures."
                    ),
                )
            )

        # Round 5 (if requested): Final Concessions & Synthesis Blueprint
        if num_rounds >= 5:
            debate_rounds.append(
                DebateRound(
                    round_number=5,
                    name="Final Concessions & Synthesis Blueprint",
                    participating_agents=["proponent", "skeptic", "pragmatist"],
                    interaction_protocol="Provide final closing summaries and specific concession statements.",
                    prompt_template=(
                        f"<round_5_protocol>\n"
                        f"Topic: {clean_topic}\n"
                        f"Stress-Testing Results: {{round_4_statements}}\n"
                        f"</round_5_protocol>\n"
                        f"Deliver your final closing synthesis statement, stating your single most critical concession."
                    ),
                )
            )

        # Arbiter Final Verdict Prompt
        arbiter_prompt = f"""<arbiter_context>
You are the Impartial Arbiter presiding over the completed multi-agent debate on:
"{clean_topic}"
</arbiter_context>

<deliberation_transcripts>
{{full_debate_transcript}}
</deliberation_transcripts>

<judicial_instructions>
1. Executive Summary: What was the central debate crux?
2. Argument Scorecard:
   - Proponent: Valid points vs overreach
   - Skeptic: Valid risks vs unwarranted alarmism
   - Pragmatist: Practical viability of proposed trade-offs
3. Consensus Resolution: Synthesize the undisputed truth and sound principles into an integrated, concrete decision.
4. Actionable Next Steps: Provide the finalized, unambiguous blueprint or answer to the original topic.
</judicial_instructions>

<verdict>
<!-- Provide final authoritative consensus verdict here -->
</verdict>
"""

        complexity = "High" if len(clean_topic.split()) > 15 or "vs" in clean_topic.lower() else "Medium"

        return DebateEnsemble(
            topic=clean_topic,
            complexity_level=complexity,
            personas=personas,
            rounds=debate_rounds,
            arbiter_synthesis_prompt=arbiter_prompt,
            total_rounds=len(debate_rounds),
        )


# Singleton instances
cove_engine = ChainOfVerificationEngine()
debate_synthesizer = MultiAgentDebateSynthesizer()


def decompose_cove_pipeline(
    prompt: str,
    domain: str = "general",
    target_provider: str = "anthropic_xml",
) -> CoVePipeline:
    """Convenience helper to build a CoVe pipeline."""
    return cove_engine.decompose(prompt, domain=domain, target_provider=target_provider)


def synthesize_debate_ensemble(topic: str, rounds: int = 3) -> DebateEnsemble:
    """Convenience helper to build a Multi-Agent Debate ensemble."""
    return debate_synthesizer.synthesize(topic, rounds=rounds)
