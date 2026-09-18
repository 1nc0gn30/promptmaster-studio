"""Tests for Chain-of-Verification (CoVe) and Multi-Agent Debate Synthesis Engine."""

from __future__ import annotations

import json
from promptmaster_studio.cli import main
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
from promptmaster_studio.mcp_server import MCPServer
from promptmaster_studio.ui_server import PromptMasterStudioRequestHandler


def test_cove_engine_decomposition_structure() -> None:
    engine = ChainOfVerificationEngine()
    task = "Summarize the key breakthroughs in mRNA vaccine technology and key clinical milestones."
    pipeline = engine.decompose(task, domain="medical", target_provider="anthropic_xml")

    assert isinstance(pipeline, CoVePipeline)
    assert pipeline.task_description == task
    assert pipeline.domain == "medical"
    assert len(pipeline.stages) == 4

    stage_names = [s.name for s in pipeline.stages]
    assert "Baseline Generation" in stage_names[0]
    assert "Verification Planning" in stage_names[1]
    assert "Execution" in stage_names[2]
    assert "Final Verified Synthesis" in stage_names[3]

    assert "<task_context>" in pipeline.baseline_prompt
    assert "<initial_draft>" in pipeline.question_generation_prompt
    assert "<verification_questions>" in pipeline.verification_execution_prompt
    assert "<verified_facts>" in pipeline.final_synthesis_prompt
    assert pipeline.estimated_token_overhead > 0

    p_dict = pipeline.to_dict()
    assert p_dict["domain"] == "medical"
    assert len(p_dict["stages"]) == 4


def test_cove_engine_generic_markdown_target() -> None:
    task = "Explain the mechanics of zero-knowledge proofs in distributed ledgers."
    pipeline = decompose_cove_pipeline(task, domain="cryptography", target_provider="generic")

    assert "### Role & Context" in pipeline.baseline_prompt
    assert "### User Query" in pipeline.baseline_prompt
    assert "cryptography" in pipeline.baseline_prompt
    assert len(pipeline.stages) == 4


def test_multi_agent_debate_synthesis() -> None:
    synthesizer = MultiAgentDebateSynthesizer()
    topic = "Should an enterprise adopt a micro-frontend architecture versus a modular monolithic frontend?"
    ensemble = synthesizer.synthesize(topic, rounds=3, domain="software_architecture")

    assert isinstance(ensemble, DebateEnsemble)
    assert ensemble.topic == topic
    assert ensemble.total_rounds == 3
    assert len(ensemble.personas) == 4

    persona_roles = [p.role_name for p in ensemble.personas]
    assert any("Proponent" in r for r in persona_roles)
    assert any("Skeptic" in r or "Red-Teamer" in r for r in persona_roles)
    assert any("Pragmatist" in r or "Architect" in r for r in persona_roles)
    assert any("Arbiter" in r or "Judge" in r for r in persona_roles)

    assert len(ensemble.rounds) == 3
    round_names = [r.name for r in ensemble.rounds]
    assert "Opening Thesis" in round_names[0]
    assert "Cross-Examination & Rebuttal" in round_names[1]
    assert "Convergence & Compromise" in round_names[2]

    assert "Impartial Arbiter" in ensemble.arbiter_synthesis_prompt
    assert "Consensus Resolution" in ensemble.arbiter_synthesis_prompt

    d_dict = ensemble.to_dict()
    assert d_dict["total_rounds"] == 3
    assert len(d_dict["personas"]) == 4


def test_debate_rounds_bounds() -> None:
    # Verify clamping between 2 and 5 rounds
    ens_min = synthesize_debate_ensemble("Topic", rounds=1)
    assert ens_min.total_rounds == 2

    ens_max = synthesize_debate_ensemble("Topic", rounds=10)
    assert ens_max.total_rounds == 5


def test_mcp_prompt_cove_tool() -> None:
    server = MCPServer()
    req_json = json.dumps({
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tools/call",
        "params": {
            "name": "prompt_chain_of_verification",
            "arguments": {
                "prompt": "Evaluate legal liability under EU AI Act for high-risk biometric systems.",
                "domain": "legal",
            },
        },
    })
    resp_str = server.handle_message(req_json)
    assert resp_str is not None
    resp = json.loads(resp_str)
    assert "result" in resp
    text = resp["result"]["content"][0]["text"]
    assert "Chain-of-Verification (CoVe) Pipeline" in text
    assert "Stage 1: Baseline Generation" in text
    assert "Stage 4: Verified Final Synthesis" in text

    # Direct handler test
    direct_res = server._handle_prompt_cove({"prompt": "Evaluate legal liability.", "domain": "legal"})
    assert direct_res["data"]["domain"] == "legal"
    assert len(direct_res["data"]["stages"]) == 4


def test_mcp_prompt_debate_tool() -> None:
    server = MCPServer()
    req_json = json.dumps({
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tools/call",
        "params": {
            "name": "prompt_multi_agent_debate",
            "arguments": {
                "topic": "Should autonomous agents be allowed to execute database migrations without human signoff?",
                "rounds": 4,
            },
        },
    })
    resp_str = server.handle_message(req_json)
    assert resp_str is not None
    resp = json.loads(resp_str)
    assert "result" in resp
    text = resp["result"]["content"][0]["text"]
    assert "Multi-Agent Society-of-Mind Debate Ensemble" in text
    assert "Participating Personas:" in text
    assert "Arbiter Consensus Synthesis Protocol:" in text

    # Direct handler test
    direct_res = server._handle_prompt_debate({"topic": "Autonomous migrations", "rounds": 4})
    assert direct_res["data"]["total_rounds"] == 4
    assert len(direct_res["data"]["personas"]) == 4


def test_cli_cove_command(capsys) -> None:
    code = main(["cove", "Provide an audit trail for financial transaction reversals.", "--domain", "financial", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["domain"] == "financial"
    assert "baseline_prompt" in data
    assert len(data["stages"]) == 4


def test_cli_debate_command(capsys) -> None:
    code = main(["debate", "Monorepo vs Polyrepo for a 50-engineer organization", "-r", "3", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "Monorepo vs Polyrepo" in data["topic"]
    assert data["total_rounds"] == 3
    assert len(data["personas"]) == 4
