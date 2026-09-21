"""Prompt version history and rollback store.

Lightweight JSON-file-backed version control for prompt iterations.
Supports save, list, get, compare, rollback, and branch operations.
100% Python Standard Library.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from promptmaster_studio.engine.prompt_diff import compare_prompts
from promptmaster_studio.engine.tokenizer_estimator import TokenizerEstimator

# Regex patterns (module-level to avoid Pyright overload issues)
_TAG_RE = re.compile(r"<([a-zA-Z0-9_-]+)")
_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*(?:\||:-|:|\}\})")


@dataclass
class PromptVersion:
    """A single version snapshot of a prompt."""
    version_id: str
    prompt_text: str
    label: str
    parent_version_id: Optional[str]
    created_at: str
    branch: str
    tokens: int
    tags: List[str]
    variables: List[str]
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "prompt_text": self.prompt_text,
            "label": self.label,
            "parent_version_id": self.parent_version_id,
            "created_at": self.created_at,
            "branch": self.branch,
            "tokens": self.tokens,
            "tags": self.tags,
            "variables": self.variables,
            "message": self.message,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PromptVersion:
        return cls(
            version_id=data.get("version_id", ""),
            prompt_text=data.get("prompt_text", ""),
            label=data.get("label", "untitled"),
            parent_version_id=data.get("parent_version_id"),
            created_at=data.get("created_at", ""),
            branch=data.get("branch", "main"),
            tokens=data.get("tokens", 0),
            tags=data.get("tags", []),
            variables=data.get("variables", []),
            message=data.get("message", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PromptBranch:
    """A branch of prompt versions."""
    name: str
    head_version_id: str
    created_at: str
    version_count: int = 0


class PromptVersionHistory:
    """JSON-backed version history store for prompts.

    Organizes versions into branches with full rollback support.
    Storage format is a single JSON file per project/workspace.
    """

    def __init__(self, storage_path: Optional[str] = None) -> None:
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            home = Path.home() / ".promptmaster"
            home.mkdir(parents=True, exist_ok=True)
            self.storage_path = home / "versions.json"

        self._data: Dict[str, Any] = {
            "branches": {},
            "versions": {},
            "metadata": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "version_count": 0,
            },
        }
        self._load()

    def _load(self) -> None:
        """Load data from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    self._data = raw
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self) -> None:
        """Persist data to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def _generate_id(self) -> str:
        """Generate a short unique version ID."""
        return uuid.uuid4().hex[:12]

    def _extract_tags(self, text: str) -> List[str]:
        """Extract XML tags and markdown headers from text."""
        tags = set()
        for match in _TAG_RE.finditer(text):
            tags.add(f"<{match.group(1)}>")
        for match in re.finditer(r"^#{1,6}\s+(.+)$", text, re.MULTILINE):
            tags.add(match.group(0).strip())
        return sorted(tags)

    def _extract_variables(self, text: str) -> List[str]:
        """Extract template variable names."""
        return sorted(set(_VAR_RE.findall(text)))

    def _count_tokens(self, text: str) -> int:
        """Count tokens using the estimator."""
        tokenizer = TokenizerEstimator()
        return tokenizer.count_tokens(text, "general")

    def create_branch(self, branch_name: str, from_version_id: Optional[str] = None) -> PromptBranch:
        """Create a new branch, optionally forked from an existing version."""
        if branch_name in self._data.get("branches", {}):
            existing = self.get_branch(branch_name)
            if existing is not None:
                return existing

        now = datetime.now(timezone.utc).isoformat()

        if from_version_id and from_version_id in self._data.get("versions", {}):
            source = self._data["versions"][from_version_id]
            branch = PromptBranch(
                name=branch_name,
                head_version_id=from_version_id,
                created_at=now,
                version_count=0,
            )
        else:
            # Empty branch — head is placeholder
            branch = PromptBranch(
                name=branch_name,
                head_version_id="",
                created_at=now,
                version_count=0,
            )

        if "branches" not in self._data:
            self._data["branches"] = {}
        self._data["branches"][branch_name] = {
            "name": branch.name,
            "head_version_id": branch.head_version_id,
            "created_at": branch.created_at,
            "version_count": branch.version_count,
        }
        self._save()
        return branch

    def save_version(
        self,
        prompt_text: str,
        label: str = "",
        branch: str = "main",
        message: str = "",
        parent_version_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptVersion:
        """Save a new prompt version to history.

        Args:
            prompt_text: The prompt text to save.
            label: Short descriptive label.
            branch: Target branch name (created if doesn't exist).
            message: Commit message describing the change.
            parent_version_id: Explicit parent (None = use branch head).
            metadata: Extra metadata to attach.

        Returns:
            The created PromptVersion instance.
        """
        # Ensure branch exists
        if branch not in self._data.get("branches", {}):
            self.create_branch(branch)

        now = datetime.now(timezone.utc).isoformat()
        version_id = self._generate_id()

        # Determine parent
        if parent_version_id is None:
            parent_version_id = self._data["branches"][branch].get("head_version_id") or None

        # If no parent and branch has versions, use the branch head
        if parent_version_id and parent_version_id not in self._data.get("versions", {}):
            parent_version_id = None

        version = PromptVersion(
            version_id=version_id,
            prompt_text=prompt_text,
            label=label or f"v{self._data.get('metadata', {}).get('version_count', 0) + 1}",
            parent_version_id=parent_version_id,
            created_at=now,
            branch=branch,
            tokens=self._count_tokens(prompt_text),
            tags=self._extract_tags(prompt_text),
            variables=self._extract_variables(prompt_text),
            message=message,
            metadata=metadata or {},
        )

        if "versions" not in self._data:
            self._data["versions"] = {}
        self._data["versions"][version_id] = version.to_dict()

        # Update branch head
        self._data["branches"][branch]["head_version_id"] = version_id
        self._data["branches"][branch]["version_count"] = (
            self._data["branches"][branch].get("version_count", 0) + 1
        )

        # Update global count
        if "metadata" not in self._data:
            self._data["metadata"] = {}
        self._data["metadata"]["version_count"] = (
            self._data["metadata"].get("version_count", 0) + 1
        )

        self._save()
        return version

    def get_version(self, version_id: str) -> Optional[PromptVersion]:
        """Retrieve a specific version by ID."""
        raw = self._data.get("versions", {}).get(version_id)
        return PromptVersion.from_dict(raw) if raw else None

    def get_branch_head(self, branch: str = "main") -> Optional[PromptVersion]:
        """Get the latest version on a branch."""
        branch_data = self._data.get("branches", {}).get(branch)
        if not branch_data or not branch_data.get("head_version_id"):
            return None
        return self.get_version(branch_data["head_version_id"])

    def list_versions(self, branch: Optional[str] = None, limit: int = 20) -> List[PromptVersion]:
        """List versions, optionally filtered by branch, newest first."""
        versions = []
        for vid, raw in self._data.get("versions", {}).items():
            v = PromptVersion.from_dict(raw)
            if branch is None or v.branch == branch:
                versions.append(v)

        # Sort by created_at descending
        versions.sort(key=lambda v: v.created_at, reverse=True)
        return versions[:limit]

    def list_branches(self) -> List[PromptBranch]:
        """List all branches."""
        result = []
        for name, data in self._data.get("branches", {}).items():
            result.append(PromptBranch(
                name=data.get("name", name),
                head_version_id=data.get("head_version_id", ""),
                created_at=data.get("created_at", ""),
                version_count=data.get("version_count", 0),
            ))
        return result

    def get_branch(self, branch_name: str) -> Optional[PromptBranch]:
        """Get a single branch by name."""
        data = self._data.get("branches", {}).get(branch_name)
        if not data:
            return None
        return PromptBranch(
            name=data.get("name", branch_name),
            head_version_id=data.get("head_version_id", ""),
            created_at=data.get("created_at", ""),
            version_count=data.get("version_count", 0),
        )

    def rollback(self, version_id: str, branch: Optional[str] = None) -> Optional[PromptVersion]:
        """Rollback to a specific version, creating a new version with the old content."""
        target = self.get_version(version_id)
        if not target:
            return None

        return self.save_version(
            prompt_text=target.prompt_text,
            label=f"rollback-{target.label}",
            message=f"Rolled back to version {target.version_id}",
            branch=branch or target.branch,
            metadata={"rollback_source": version_id, "rollback": True},
        )

    def compare_versions(
        self,
        version_id_a: str,
        version_id_b: str,
        model_name: str = "gpt-4o",
    ) -> Optional[Dict[str, Any]]:
        """Compare two specific versions."""
        va = self.get_version(version_id_a)
        vb = self.get_version(version_id_b)
        if not va or not vb:
            return None

        result = compare_prompts(va.prompt_text, vb.prompt_text, model_name)
        report = result.to_dict()
        report["left_version_id"] = version_id_a
        report["right_version_id"] = version_id_b
        report["left_label"] = va.label
        report["right_label"] = vb.label
        return report

    def get_history_tree(self, branch: str = "main", max_depth: int = 20) -> List[Dict[str, Any]]:
        """Get a linearized history for a branch."""
        chain: List[Dict[str, Any]] = []
        branch_data = self._data.get("branches", {}).get(branch)
        if not branch_data:
            return chain

        current_id = branch_data.get("head_version_id")
        depth = 0

        while current_id and depth < max_depth:
            version = self.get_version(current_id)
            if not version:
                break
            chain.append({
                "version_id": version.version_id,
                "label": version.label,
                "message": version.message,
                "tokens": version.tokens,
                "created_at": version.created_at,
                "tags_count": len(version.tags),
                "depth": depth,
            })
            current_id = version.parent_version_id
            depth += 1

        return chain

    def search_versions(self, query: str) -> List[PromptVersion]:
        """Search versions by label, message, or content substring."""
        query_lower = query.lower()
        results = []
        for vid, raw in self._data.get("versions", {}).items():
            if (query_lower in raw.get("label", "").lower()
                    or query_lower in raw.get("message", "").lower()
                    or query_lower in raw.get("prompt_text", "").lower()):
                results.append(PromptVersion.from_dict(raw))
        results.sort(key=lambda v: v.created_at, reverse=True)
        return results

    def delete_version(self, version_id: str) -> bool:
        """Delete a version. Returns True if found and deleted."""
        if version_id in self._data.get("versions", {}):
            del self._data["versions"][version_id]
            self._save()
            return True
        return False

    def delete_branch(self, branch_name: str, force: bool = False) -> bool:
        """Delete a branch. Only allowed if empty or force=True."""
        if branch_name not in self._data.get("branches", {}):
            return False

        # Check if versions exist on this branch
        versions_on_branch = [
            v for v in self._data.get("versions", {}).values()
            if v.get("branch") == branch_name
        ]

        if versions_on_branch and not force:
            return False

        # Delete versions if forced
        if force:
            for v in versions_on_branch:
                vid = v.get("version_id")
                if vid and vid in self._data.get("versions", {}):
                    del self._data["versions"][vid]

        del self._data["branches"][branch_name]
        self._save()
        return True

    def stats(self) -> Dict[str, Any]:
        """Return store statistics."""
        versions = list(self._data.get("versions", {}).values())
        branches = list(self._data.get("branches", {}).keys())
        total_tokens = sum(v.get("tokens", 0) for v in versions)

        return {
            "total_versions": len(versions),
            "total_branches": len(branches),
            "branches": branches,
            "total_tokens": total_tokens,
            "storage_path": str(self.storage_path),
            "oldest_version": min((v.get("created_at", "") for v in versions), default=None),
            "newest_version": max((v.get("created_at", "") for v in versions), default=None),
        }

    def clear_history(self, confirm: bool = False) -> bool:
        """Clear all history. Requires confirm=True."""
        if not confirm:
            return False
        self._data["versions"] = {}
        self._data["branches"] = {}
        self._data["metadata"]["version_count"] = 0
        self._save()
        return True
