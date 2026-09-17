"""Unit tests for few-shot exemplar ranker and prompt token pruner."""

import pytest
from promptmaster_studio import (
    FewShotExample,
    prune_prompt_tokens,
    rank_few_shot_examples,
)


def test_rank_few_shot_examples():
    query = "Write a python function to parse JSON with error handling"

    examples = [
        FewShotExample(
            input_text="How to parse JSON in Python?",
            output_text="import json\ntry:\n    data = json.loads(s)\nexcept json.JSONDecodeError:\n    pass",
        ),
        FewShotExample(
            input_text="Write a poem about sunflowers",
            output_text="Yellow petals in the sun...",
        ),
        FewShotExample(
            input_text="Python safe dictionary get",
            output_text="val = d.get('key', default)",
        ),
    ]

    ranked = rank_few_shot_examples(query, examples, top_k=2)
    assert len(ranked) == 2
    # The JSON parsing example should rank #1
    assert "parse JSON" in ranked[0].input_text


def test_rank_few_shot_examples_budget_limit():
    query = "Code review feedback"
    examples = [
        FewShotExample(input_text="Input 1 " * 50, output_text="Output 1 " * 50),
        FewShotExample(input_text="Short", output_text="Code looks good!"),
    ]

    # Constrain with very small budget
    ranked = rank_few_shot_examples(query, examples, top_k=2, max_token_budget=30)
    assert len(ranked) <= 1
    if ranked:
        assert ranked[0].input_text == "Short"


def test_prune_prompt_tokens():
    prompt = (
        "Please note that I would like you to basically create a python script.\n"
        "As mentioned earlier, please be sure to handle all exceptions carefully.\n\n\n"
        "Make sure that you return JSON."
    )

    pruned, tokens = prune_prompt_tokens(prompt, target_token_limit=15)
    assert len(pruned) < len(prompt)
    assert "Please note that" not in pruned
    assert "basically" not in pruned
    assert tokens <= 15 or len(pruned) < len(prompt)
