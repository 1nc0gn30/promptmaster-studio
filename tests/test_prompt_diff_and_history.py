"""Tests for the PromptMaster Studio diff and version history engines."""

from __future__ import annotations

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import tempfile
import json

from promptmaster_studio.engine.prompt_diff import (
    PromptComparisonResult,
    PromptDiffEntry,
    compare_prompts,
    extract_variables,
    extract_tags,
    compute_line_diff,
    compute_similarity,
    format_comparison_report,
)
from promptmaster_studio.engine.version_history import (
    PromptVersionHistory,
    PromptVersion,
    PromptBranch,
)


# ============================================================================
# VARIABLE AND TAG EXTRACTION TESTS
# ============================================================================

class TestExtractVariables:
    def test_extracts_simple_variable(self):
        text = "Hello {{ name }}, welcome to {{ place }}."
        result = extract_variables(text)
        assert result == ["name", "place"]

    def test_extracts_nested_path_variable(self):
        text = "User: {{ user.name }} ({{ user.id }})"
        result = extract_variables(text)
        assert "user.id" in result
        assert "user.name" in result

    def test_extracts_variable_with_filter(self):
        text = "Role: {{ role | upper }}"
        result = extract_variables(text)
        assert "role" in result

    def test_extracts_variable_with_default(self):
        text = "Hello {{ name :- Guest }}"
        result = extract_variables(text)
        assert "name" in result

    def test_empty_text_returns_empty(self):
        assert extract_variables("") == []

    def test_deduplicates_variables(self):
        text = "{{ foo }} and {{ foo }} again"
        result = extract_variables(text)
        assert result == ["foo"]


class TestExtractTags:
    def test_extracts_xml_tags(self):
        text = "<instructions>Do this</instructions>\n<context>Info</context>"
        result = extract_tags(text)
        assert "<context>" in result
        assert "<instructions>" in result

    def test_extracts_markdown_headers(self):
        text = "# Task\n## Guidelines\n### Subsection"
        result = extract_tags(text)
        assert "# Task" in result
        assert "## Guidelines" in result

    def test_no_tags_returns_empty(self):
        assert extract_tags("plain text here") == []


# ============================================================================
# LINE DIFF TESTS
# ============================================================================

class TestComputeLineDiff:
    def test_identical_text(self):
        text = "line1\nline2\nline3"
        result = compute_line_diff(text, text)
        assert all(e.line_type == "unchanged" for e in result)
        assert len(result) == 3

    def test_added_lines(self):
        left = "line1\nline2"
        right = "line1\nline2\nline3"
        result = compute_line_diff(left, right)
        added = [e for e in result if e.line_type == "added"]
        assert len(added) == 1
        assert added[0].right_text == "line3"

    def test_removed_lines(self):
        left = "line1\nline2\nline3"
        right = "line1\nline3"
        result = compute_line_diff(left, right)
        removed = [e for e in result if e.line_type == "removed"]
        assert len(removed) == 1
        assert removed[0].left_text == "line2"

    def test_modified_lines(self):
        left = "hello world"
        right = "goodbye world"
        result = compute_line_diff(left, right)
        modified = [e for e in result if e.line_type == "modified"]
        assert len(modified) == 1


class TestComputeSimilarity:
    def test_identical(self):
        assert compute_similarity("hello", "hello") == 1.0

    def test_completely_different(self):
        result = compute_similarity("abc", "xyz")
        assert result < 0.5

    def test_partial_similarity(self):
        result = compute_similarity("hello world", "hello there")
        assert 0.3 < result < 1.0


# ============================================================================
# PROMPT COMPARISON TESTS
# ===========================================================================

class TestComparePrompts:
    def test_basic_comparison(self):
        left = "Write a function to sort a list."
        right = "<instructions>\nYou are a Principal Software Architect.\n- Write a function to sort a list.\n</instructions>"
        result = compare_prompts(left, right)
        assert isinstance(result, PromptComparisonResult)

    def test_token_delta(self):
        left = "Short prompt."
        right = "<instructions>\nYou are an expert.\n- Short prompt.\n- Additional constraint.\n</instructions>"
        result = compare_prompts(left, right)
        assert result.right_tokens > result.left_tokens
        assert result.token_delta > 0
        assert result.token_delta_percent > 0

    def test_variable_overlap(self):
        left = "{{ name }} is {{ age }} years old."
        right = "{{ name }} is {{ height }} tall."
        result = compare_prompts(left, right)
        assert "name" in result.shared_variables
        assert "age" in result.left_only_variables
        assert "height" in result.right_only_variables

    def test_tag_overlap(self):
        left = "<instructions>Task</instructions>"
        right = "<instructions>Task</instructions>\n<constraints>Rule</constraints>"
        result = compare_prompts(left, right)
        assert "<instructions>" in result.shared_tags
        assert "<constraints>" in result.right_only_tags

    def test_quality_scores_present(self):
        left = "do stuff"
        right = "<instructions>Do specific stuff with precision.</instructions>"
        result = compare_prompts(left, right)
        assert 0 <= result.left_linter_score <= 100
        assert 0 <= result.right_linter_score <= 100

    def test_cost_comparison(self):
        left = "x" * 100
        right = "x" * 500
        result = compare_prompts(left, right, compare_costs=True)
        assert len(result.left_cost_usd) > 0
        assert len(result.right_cost_usd) > 0
        # Right should cost more
        assert result.right_cost_usd["gpt-4o"] >= result.left_cost_usd["gpt-4o"]

    def test_to_dict_structure(self):
        left = "prompt a"
        right = "prompt b"
        result = compare_prompts(left, right)
        d = result.to_dict()
        assert "left_tokens" in d
        assert "right_tokens" in d
        assert "token_delta" in d
        assert "shared_variables" in d
        assert "shared_tags" in d
        assert "diff_summary" in d


class TestFormatComparisonReport:
    def test_report_generation(self):
        left = "short prompt"
        right = "<instructions>\nYou are an expert.\n- short prompt.\n</instructions>"
        result = compare_prompts(left, right)
        report = format_comparison_report(result)
        assert "PROMPT COMPARISON REPORT" in report
        assert "TOKEN ANALYSIS" in report
        assert "QUALITY SCORE" in report
        assert "DIFF SUMMARY" in report


# ============================================================================
# VERSION HISTORY TESTS
# ============================================================================

class TestPromptVersionHistory:
    def setup_method(self):
        """Create a temporary file for each test."""
        self.tmpdir = tempfile.mkdtemp()
        self.store_path = os.path.join(self.tmpdir, "test_versions.json")

    def _make_store(self):
        return PromptVersionHistory(storage_path=self.store_path)

    def test_save_version(self):
        store = self._make_store()
        v = store.save_version("Hello {{ name }}", label="v1", message="Initial")
        assert v.version_id is not None
        assert v.label == "v1"
        assert v.message == "Initial"
        assert v.tokens > 0

    def test_get_version(self):
        store = self._make_store()
        v = store.save_version("Test prompt", label="v1")
        fetched = store.get_version(v.version_id)
        assert fetched is not None
        assert fetched.prompt_text == "Test prompt"

    def test_get_nonexistent_version(self):
        store = self._make_store()
        assert store.get_version("nonexistent") is None

    def test_list_versions_newest_first(self):
        store = self._make_store()
        store.save_version("first", label="v1")
        store.save_version("second", label="v2")
        store.save_version("third", label="v3")
        versions = store.list_versions()
        assert len(versions) == 3
        assert versions[0].label == "v3"

    def test_list_versions_branch_filter(self):
        store = self._make_store()
        store.save_version("main v1", label="v1", branch="main")
        store.save_version("dev v1", label="dev1", branch="dev")
        main_versions = store.list_versions(branch="main")
        assert len(main_versions) == 1
        assert main_versions[0].label == "v1"

    def test_create_branch(self):
        store = self._make_store()
        store.save_version("v1", label="v1")
        branch = store.create_branch("experiment")
        assert branch is not None
        assert branch.name == "experiment"

    def test_get_branch(self):
        store = self._make_store()
        store.save_version("v1", label="v1")
        branch = store.get_branch("main")
        assert branch is not None
        assert branch.name == "main"

    def test_branch_head(self):
        store = self._make_store()
        store.save_version("v1", label="v1")
        store.save_version("v2", label="v2")
        head = store.get_branch_head()
        assert head is not None
        assert head.label == "v2"

    def test_rollback(self):
        store = self._make_store()
        v1 = store.save_version("original", label="v1")
        store.save_version("modified", label="v2")
        rollback = store.rollback(v1.version_id)
        assert rollback is not None
        assert rollback.prompt_text == "original"
        assert rollback.metadata.get("rollback") is True

    def test_rollback_nonexistent(self):
        store = self._make_store()
        assert store.rollback("nonexistent") is None

    def test_compare_versions(self):
        store = self._make_store()
        v1 = store.save_version("short prompt", label="v1")
        v2 = store.save_version("much longer prompt with more content", label="v2")
        report = store.compare_versions(v1.version_id, v2.version_id)
        assert report is not None
        assert "left_tokens" in report
        assert "right_tokens" in report

    def test_compare_nonexistent_versions(self):
        store = self._make_store()
        assert store.compare_versions("a", "b") is None

    def test_history_tree(self):
        store = self._make_store()
        store.save_version("v1", label="v1")
        store.save_version("v2", label="v2")
        tree = store.get_history_tree()
        assert len(tree) == 2
        assert tree[0]["label"] == "v2"

    def test_search_versions(self):
        store = self._make_store()
        store.save_version("security audit prompt", label="security")
        store.save_version("data analysis prompt", label="data")
        results = store.search_versions("security")
        assert len(results) == 1
        assert results[0].label == "security"

    def test_stats(self):
        store = self._make_store()
        store.save_version("v1", label="v1")
        store.save_version("v2", label="v2")
        stats = store.stats()
        assert stats["total_versions"] == 2
        assert "main" in stats["branches"]

    def test_delete_version(self):
        store = self._make_store()
        v = store.save_version("to delete", label="v1")
        assert store.delete_version(v.version_id) is True
        assert store.get_version(v.version_id) is None

    def test_delete_nonexistent_version(self):
        store = self._make_store()
        assert store.delete_version("nonexistent") is False

    def test_clear_history(self):
        store = self._make_store()
        store.save_version("v1", label="v1")
        assert store.clear_history(confirm=True) is True
        assert store.list_versions() == []

    def test_clear_history_no_confirm(self):
        store = self._make_store()
        store.save_version("v1", label="v1")
        assert store.clear_history(confirm=False) is False
        assert len(store.list_versions()) == 1

    def test_persistence(self):
        """Test that data persists across store instances."""
        store1 = self._make_store()
        store1.save_version("persistent", label="v1")

        store2 = PromptVersionHistory(storage_path=self.store_path)
        versions = store2.list_versions()
        assert len(versions) == 1
        assert versions[0].prompt_text == "persistent"

    def test_version_extracts_tags(self):
        store = self._make_store()
        v = store.save_version("<instructions>Task</instructions>", label="v1")
        assert "<instructions>" in v.tags

    def test_version_extracts_variables(self):
        store = self._make_store()
        v = store.save_version("Hello {{ name }}", label="v1")
        assert "name" in v.variables

    def test_branch_version_count(self):
        store = self._make_store()
        store.save_version("v1", label="v1", branch="main")
        store.save_version("v2", label="v2", branch="main")
        branch = store.get_branch("main")
        assert branch is not None
        assert branch.version_count == 2

    def test_list_branches(self):
        store = self._make_store()
        store.save_version("v1", label="v1", branch="main")
        store.create_branch("experiment")
        branches = store.list_branches()
        names = [b.name for b in branches]
        assert "main" in names
        assert "experiment" in names

    def test_delete_empty_branch(self):
        store = self._make_store()
        store.create_branch("empty")
        assert store.delete_branch("empty") is True

    def test_delete_nonempty_branch_no_force(self):
        store = self._make_store()
        store.save_version("v1", label="v1", branch="main")
        assert store.delete_branch("main", force=False) is False

    def test_delete_nonempty_branch_with_force(self):
        store = self._make_store()
        store.save_version("v1", label="v1", branch="main")
        assert store.delete_branch("main", force=True) is True
        assert store.get_branch("main") is None


class TestPromptVersion:
    def test_to_dict(self):
        v = PromptVersion(
            version_id="abc123",
            prompt_text="test",
            label="v1",
            parent_version_id=None,
            created_at="2024-01-01T00:00:00",
            branch="main",
            tokens=10,
            tags=["<instructions>"],
            variables=["name"],
            message="Initial",
        )
        d = v.to_dict()
        assert d["version_id"] == "abc123"
        assert d["prompt_text"] == "test"

    def test_from_dict(self):
        data = {
            "version_id": "abc123",
            "prompt_text": "test",
            "label": "v1",
            "parent_version_id": None,
            "created_at": "2024-01-01T00:00:00",
            "branch": "main",
            "tokens": 10,
            "tags": ["<instructions>"],
            "variables": ["name"],
            "message": "Initial",
        }
        v = PromptVersion.from_dict(data)
        assert v.version_id == "abc123"
        assert v.prompt_text == "test"
