import textwrap

from interviewforge.config.settings import Settings, load_settings


def test_load_defaults_from_yaml(tmp_path, monkeypatch):
    roles = tmp_path / "roles.yaml"
    roles.write_text(textwrap.dedent("""
        bounds:
          token_budget: 24000
          max_turns: 30
          max_replans: 3
          max_tool_calls_per_turn: 5
          single_output_cap: 2000
          snip_after_turns: 20
        global_rules:
          - id: score_in_range
            desc: must be 1-5
    """), encoding="utf-8")
    monkeypatch.delenv("TOKEN_BUDGET", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://x/v1")
    monkeypatch.setenv("MODEL_NAME", "m")

    s = load_settings(roles_path=roles)
    assert isinstance(s, Settings)
    assert s.token_budget == 24000
    assert s.max_turns == 30
    assert s.api_key == "sk-test"
    assert s.base_url == "https://x/v1"
    assert s.model_name == "m"
    assert {r["id"] for r in s.global_rules} == {"score_in_range"}


def test_env_overrides_yaml_bounds(tmp_path, monkeypatch):
    roles = tmp_path / "roles.yaml"
    roles.write_text(textwrap.dedent("""
        bounds:
          token_budget: 24000
          max_turns: 30
          max_replans: 3
          max_tool_calls_per_turn: 5
          single_output_cap: 2000
          snip_after_turns: 20
        global_rules: []
    """), encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://x/v1")
    monkeypatch.setenv("MODEL_NAME", "m")
    monkeypatch.setenv("TOKEN_BUDGET", "8000")

    s = load_settings(roles_path=roles)
    assert s.token_budget == 8000  # env 覆盖 yaml


def test_missing_api_key_raises(tmp_path, monkeypatch):
    import pytest
    roles = tmp_path / "roles.yaml"
    roles.write_text("bounds: {token_budget: 1, max_turns: 1, max_replans: 1, "
                     "max_tool_calls_per_turn: 1, single_output_cap: 1, snip_after_turns: 1}\n"
                     "global_rules: []\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://x/v1")
    monkeypatch.setenv("MODEL_NAME", "m")
    # load_dotenv() would re-read .env and restore the key; suppress it for this test
    monkeypatch.setattr("interviewforge.config.settings.load_dotenv", lambda **_: None)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        load_settings(roles_path=roles)
