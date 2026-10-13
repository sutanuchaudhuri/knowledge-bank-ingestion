from mathbank_rest.route_openai import OpenAIChatProvider


def test_digest_is_model_specific_so_critic_generator_pairs_are_distinguishable():
    a = OpenAIChatProvider(model="gpt-4o-mini")
    b = OpenAIChatProvider(model="gpt-4.1-mini")
    assert a.digest != b.digest
    assert OpenAIChatProvider(model="gpt-4o-mini").digest == a.digest  # stable, not random


def test_explicit_digest_override_is_respected():
    assert OpenAIChatProvider(model="gpt-4o-mini", digest="pinned").digest == "pinned"
