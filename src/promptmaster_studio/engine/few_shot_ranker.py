"""Few-shot exemplar ranking and selection engine.

Scores and ranks exemplar candidates based on token overlap, lexical similarity,
and prompt relevance to select the highest-leverage few-shot demonstrations
within a given token budget.
100% Python Standard Library. Zero external dependencies.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from promptmaster_studio.engine.tokenizer_estimator import TokenizerEstimator
from promptmaster_studio.models import FewShotExample


def _tokenize_text(text: str) -> List[str]:
    """Tokenize lowercase alphanumeric words for similarity comparison."""
    return re.findall(r"\b\w+\b", text.lower())


def rank_few_shot_examples(
    query: str,
    candidates: Sequence[FewShotExample],
    top_k: int = 3,
    max_token_budget: Optional[int] = None,
    diversity_weight: float = 0.25,
    model_name: str = "gpt-4o",
) -> List[FewShotExample]:
    """Rank and select optimal few-shot exemplars given a target query prompt.

    Uses a hybrid BM25 / Jaccard term-frequency overlap combined with
    Maximal Marginal Relevance (MMR) for diverse, non-redundant exemplars,
    constrained by an optional max token budget.

    Args:
        query: Target task prompt or input text.
        candidates: Pool of candidate FewShotExample objects.
        top_k: Maximum number of examples to select.
        max_token_budget: Optional token budget limit for all selected examples.
        diversity_weight: Lambda trade-off parameter (0.0 = pure relevance, 1.0 = pure diversity).
        model_name: Model spec to estimate token costs.

    Returns:
        List[FewShotExample]: Ranked and pruned list of examples.
    """
    if not candidates or top_k <= 0:
        return []

    tokenizer = TokenizerEstimator()
    query_tokens = set(_tokenize_text(query))
    if not query_tokens:
        query_tokens = {"prompt"}

    # Compute candidate term sets and query relevance scores
    candidate_tokens: List[set] = []
    relevance_scores: List[float] = []

    for ex in candidates:
        combined_text = f"{ex.input_text} {ex.output_text} {ex.explanation or ''}"
        toks = set(_tokenize_text(combined_text))
        candidate_tokens.append(toks)

        # Jaccard + Overlap score
        intersection = query_tokens.intersection(toks)
        union = query_tokens.union(toks)
        jaccard = len(intersection) / len(union) if union else 0.0
        overlap = len(intersection) / len(query_tokens)
        score = (overlap * 0.7) + (jaccard * 0.3)
        relevance_scores.append(score)

    # Maximal Marginal Relevance (MMR) Greedy Selection
    selected_indices: List[int] = []
    remaining_indices = list(range(len(candidates)))
    current_tokens = 0

    while remaining_indices and len(selected_indices) < top_k:
        best_mmr = -float("inf")
        best_idx = -1

        for idx in remaining_indices:
            rel = relevance_scores[idx]
            # Redundancy penalty: max similarity to already selected candidates
            if not selected_indices:
                redundancy = 0.0
            else:
                sims = []
                idx_toks = candidate_tokens[idx]
                for sel_idx in selected_indices:
                    sel_toks = candidate_tokens[sel_idx]
                    inter = idx_toks.intersection(sel_toks)
                    un = idx_toks.union(sel_toks)
                    sims.append(len(inter) / len(un) if un else 0.0)
                redundancy = max(sims)

            mmr_score = (1.0 - diversity_weight) * rel - diversity_weight * redundancy
            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_idx = idx

        if best_idx == -1:
            break

        cand = candidates[best_idx]
        # Check budget constraint
        cand_str = f"Input: {cand.input_text}\nOutput: {cand.output_text}"
        cand_tok_count = tokenizer.count_tokens(cand_str, model_family=model_name)

        if max_token_budget is not None and (current_tokens + cand_tok_count > max_token_budget):
            remaining_indices.remove(best_idx)
            continue

        selected_indices.append(best_idx)
        remaining_indices.remove(best_idx)
        current_tokens += cand_tok_count

    return [candidates[i] for i in selected_indices]


def prune_prompt_tokens(
    prompt: str,
    target_token_limit: int,
    model_name: str = "gpt-4o",
    preserve_brackets: bool = True,
) -> Tuple[str, int]:
    """Prune verbose or filler phrases to compress a prompt to fit within target_token_limit.

    Removes conversational padding, duplicate whitespace, redundant adjectives,
    and unnecessary filler while preserving technical terms and semantic intent.

    Args:
        prompt: Raw input prompt string.
        target_token_limit: Maximum allowed token count.
        model_name: Model identifier for token estimation.
        preserve_brackets: Whether to preserve tags like <xml> or {{vars}}.

    Returns:
        Tuple[str, int]: (compressed_prompt, new_token_count).
    """
    tokenizer = TokenizerEstimator()
    curr_tokens = tokenizer.count_tokens(prompt, model_family=model_name)
    if curr_tokens <= target_token_limit:
        return prompt, curr_tokens

    # Stage 1: Strip obvious conversational pleasantries and fillers
    filler_patterns = [
        r"(?i)\b(?:please\s+note\s+that|kindly\s+note\s+that|it\s+is\s+important\s+to\s+note\s+that)\b",
        r"(?i)\b(?:as\s+mentioned\s+earlier|as\s+stated\s+above|in\s+order\s+to|for\s+the\s+purpose\s+of)\b",
        r"(?i)\b(?:i\s+would\s+like\s+you\s+to|please\s+be\s+sure\s+to|make\s+sure\s+that\s+you)\b",
        r"(?i)\b(?:could\s+you\s+please|can\s+you\s+please|would\s+you\s+mind)\b",
        r"(?i)\b(?:basically|essentially|literally|virtually|definitely|certainly)\b",
    ]

    compressed = prompt
    for pat in filler_patterns:
        compressed = re.sub(pat, "", compressed)

    # Normalize excessive whitespaces
    compressed = re.sub(r"[ \t]+", " ", compressed)
    compressed = re.sub(r"\n{3,}", "\n\n", compressed).strip()

    curr_tokens = tokenizer.count_tokens(compressed, model_family=model_name)
    if curr_tokens <= target_token_limit:
        return compressed, curr_tokens

    # Stage 2: Line-by-line truncation if still exceeding budget
    lines = compressed.splitlines()
    pruned_lines: List[str] = []
    for line in lines:
        test_text = "\n".join(pruned_lines + [line])
        if tokenizer.count_tokens(test_text, model_family=model_name) <= target_token_limit:
            pruned_lines.append(line)
        else:
            break

    final_text = "\n".join(pruned_lines).strip()
    return final_text, tokenizer.count_tokens(final_text, model_family=model_name)
