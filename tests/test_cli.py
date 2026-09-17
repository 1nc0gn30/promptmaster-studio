"""Tests for PromptMaster Studio CLI subcommands and argument parser in promptmaster_studio.cli."""

import io
import json
import sys
from pathlib import Path

import pytest

from promptmaster_studio.cli import build_parser, main


class TestCLIParser:
    """Test CLI argument parsing and flags."""

    def test_parser_creation(self):
        parser = build_parser()
        assert parser.prog == "promptmaster"

    def test_no_args_returns_zero(self, capsys: pytest.CaptureFixture):
        ret = main([])
        assert ret == 0
        captured = capsys.readouterr()
        assert "PromptMaster" in captured.out or "usage:" in captured.out


class TestCLISubcommands:
    """Test CLI subcommand execution."""

    def test_optimize_subcommand_json(self, capsys: pytest.CaptureFixture):
        ret = main(["optimize", "Review this Python code for bugs", "--target", "anthropic", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "optimized_prompt" in data
        assert data["target_provider"] == "anthropic_xml"

    def test_lint_subcommand_json(self, capsys: pytest.CaptureFixture):
        ret = main(["lint", "Please kindly do some stuff with things.", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "clarity_score" in data
        assert "issues" in data
        assert data["clarity_score"] < 95.0

    def test_tokens_subcommand_json(self, capsys: pytest.CaptureFixture):
        ret = main(["tokens", "Calculate token count for this prompt", "--model", "claude", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "estimated_tokens" in data
        assert data["estimated_tokens"] > 0
        assert data["fits_in_context"] is True

    def test_templates_subcommand_json(self, capsys: pytest.CaptureFixture):
        ret = main(["templates", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) >= 5

    def test_templates_subcommand_single_id_json(self, capsys: pytest.CaptureFixture):
        ret = main(["templates", "--id", "code_reviewer", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 1
        assert data[0]["id"] == "code_reviewer"

    def test_curriculum_subcommand_json(self, capsys: pytest.CaptureFixture):
        ret = main(["curriculum", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) >= 5

    def test_curriculum_subcommand_single_lesson_json(self, capsys: pytest.CaptureFixture):
        ret = main(["curriculum", "--lesson", "l1", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data is not None
        assert "id" in data

    def test_diagnostics_subcommand_json(self, capsys: pytest.CaptureFixture):
        ret = main(["diagnostics", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "version" in data
        assert "platform" in data

    def test_render_subcommand(self, capsys: pytest.CaptureFixture):
        ret = main(["render", "Hello {{name}}, welcome to {{place}}!", "-V", "name=Neo", "-V", "place=Zion", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["rendered"] == "Hello Neo, welcome to Zion!"

    def test_test_subcommand(self, capsys: pytest.CaptureFixture):
        ret = main(["test"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "TESTS PASSED" in captured.out
