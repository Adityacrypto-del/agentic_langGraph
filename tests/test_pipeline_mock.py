"""Offline tests of the LangChain pipeline with the scripted MOCK LLM.

MOCK LLM (scripted) — EDA results are real: the EDA tool server must be running
(docker compose up -d eda); tests skip otherwise.
"""
import pytest
from langchain_core.messages import SystemMessage

from common import prompts, tools_client as T
from langchain_app import mock_llm
from langchain_app.chains import assert_spec_only, make_prompt
from langchain_app.mock_llm import MockChatModel
from langchain_app.pipeline import build_pipeline
from langchain_app.tracing import FrostByteTracer


def _server_up() -> bool:
    try:
        return bool(T.health().get("ok"))
    except Exception:
        return False


needs_server = pytest.mark.skipif(not _server_up(), reason="EDA tool server not running")


def _run(spec_file: str):
    mock_llm.CALL_LOG.clear()
    tracer = FrostByteTracer(mock=True, live=False)
    pipe = build_pipeline(MockChatModel(), max_retries=3, auto_approve=True)
    state = pipe.invoke({"request": open(spec_file).read()}, {"callbacks": [tracer]})
    return state, tracer


@needs_server
def test_mock_s1_self_heals_and_synthesizes():
    s, tracer = _run("specs/s1.txt")
    assert s["lint_calls"] == 2                         # TOOL USE: agent linted twice
    assert s["retries"] == 1                            # REFLECTION: one verify retry
    assert "fixed RTL" in s["history"][0]               # CRITIC blamed the RTL
    assert s["passed"] and s["sim"]["failed"] == 0 and s["sim"]["total"] > 0
    assert s["synth"]["ok"] and s["synth"]["cells"] > 0
    assert s["pwr"]["ok"] and s["pwr"]["within_budget"]
    assert s["approved_by"] == "auto" and s["report"]
    tool_ends = [e for e in tracer.events if e["event"] == "tool_end"]
    assert [e["ok"] for e in tool_ends] == [False, True]
    assert any(e["event"] == "custom" and e["name"] == "retry" for e in tracer.events)


@needs_server
def test_tb_writer_never_sees_rtl():
    _run("specs/s1.txt")
    tb_calls = [c for c in mock_llm.CALL_LOG if c["role"] == "tb"]
    assert tb_calls and all("endmodule" not in c["user"] for c in tb_calls)


def test_mock_s5_asks_questions_and_writes_no_rtl():
    s, _ = _run("specs/s5.txt")
    assert s["status"] == "clarification" and len(s["questions"]) >= 2
    assert "rtl" not in s and "tb" not in s
    assert [c["role"] for c in mock_llm.CALL_LOG] == ["spec"]


def test_assert_spec_only_guardrail():
    with pytest.raises(AssertionError):
        assert_spec_only({"module_name": "x", "rtl": "module x; endmodule"})
    with pytest.raises(AssertionError):
        assert_spec_only({"notes": "module x; endmodule"})
    assert_spec_only({"module_name": "x"})


def test_prompts_with_braces_reach_model_verbatim():
    """Shared prompts contain JSON braces; they must not be treated as template variables."""
    for system in (prompts.SPEC_SYSTEM, prompts.RTL_SYSTEM, prompts.TB_SYSTEM,
                   prompts.DEBUG_SYSTEM, prompts.REPORT_SYSTEM):
        msgs = make_prompt(system).invoke({"user": "hi {x}"}).to_messages()
        assert isinstance(msgs[0], SystemMessage) and msgs[0].content == system
        assert msgs[1].content == "hi {x}"
