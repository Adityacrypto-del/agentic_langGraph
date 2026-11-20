"""The four plain LCEL chains: Spec Analyst, Testbench Writer, Debugger, Report Writer.

Agentic AI concepts: PROMPT CHAINING (prompt | llm | parser), ROLE DECOMPOSITION (one system
prompt per specialist), STRUCTURED OUTPUT PARSING as a guardrail, RELIABILITY (with_retry).

LangChain gotcha: the shared prompts contain literal { } (JSON). Inside a ChatPromptTemplate a
template string would treat them as variables and crash. We pass each system prompt as a
SystemMessage OBJECT, which ChatPromptTemplate keeps verbatim (no template parsing).
"""
import json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from common.prompts import DEBUG_SYSTEM, REPORT_SYSTEM, SPEC_SYSTEM, TB_SYSTEM
from common.utils import extract_code, extract_json

RETRY = dict(stop_after_attempt=5, wait_exponential_jitter=True)


def make_prompt(system: str) -> ChatPromptTemplate:
    # SystemMessage object => kept byte-for-byte; only the human turn is a template ({user}).
    return ChatPromptTemplate.from_messages([SystemMessage(content=system), ("human", "{user}")])


def spec_text(spec: dict) -> str:
    return "SPEC:\n" + json.dumps(spec, indent=1)


# ---------------------------------------------------------------- 1. Spec Analyst
def make_spec_chain(llm):
    prompt = make_prompt(SPEC_SYSTEM)
    raw = (prompt | llm.with_retry(**RETRY) | StrOutputParser())

    def analyse(request: str, config) -> dict:
        text = raw.invoke({"user": request}, config)
        try:
            return extract_json(text)
        except (ValueError, json.JSONDecodeError):
            # OUTPUT-FIXING: show the model its own answer and ask once more for valid JSON only.
            fix = llm.with_retry(**RETRY).invoke(
                [SystemMessage(content=SPEC_SYSTEM), HumanMessage(content=request),
                 AIMessage(content=text),
                 HumanMessage(content="That was not valid JSON. Return valid JSON only.")], config)
            return extract_json(fix.content if isinstance(fix.content, str) else str(fix.content))

    return RunnableLambda(analyse).with_config(run_name="spec_analyst")


# ---------------------------------------------------------------- 4. Testbench Writer
def assert_spec_only(spec) -> dict:
    """GUARDRAIL / TB ISOLATION: the testbench writer may only ever see the spec, never the RTL."""
    assert isinstance(spec, dict), "testbench_writer input must be the spec dict"
    assert "rtl" not in spec and "design_code" not in spec, "RTL leaked into testbench_writer input"
    assert "endmodule" not in json.dumps(spec), "Verilog code leaked into testbench_writer input"
    return spec


def make_testbench_chain(llm):
    prompt = make_prompt(TB_SYSTEM)
    return (RunnableLambda(assert_spec_only)
            | RunnableLambda(lambda spec: {"user": spec_text(spec)})
            | prompt | llm.with_retry(**RETRY) | StrOutputParser()
            | RunnableLambda(extract_code)).with_config(run_name="testbench_writer")


# ---------------------------------------------------------------- Debugger (critic)
def parse_debug(text: str) -> dict:
    """-> {culprit: 'RTL'|'TB', diagnosis, code}. Defaults to RTL if the model forgets the tag."""
    culprit = "TB" if re.search(r"CULPRIT:\s*`?TB", text, re.I) else "RTL"
    diagnosis = ""
    for line in text.splitlines():
        s = line.strip().strip("`")
        if s and not s.upper().startswith("CULPRIT") and not s.startswith("```"):
            diagnosis = s
            break
    code = extract_code(text) if "```" in text else ""
    return {"culprit": culprit, "diagnosis": diagnosis[:200], "code": code}


def debug_user(d: dict) -> str:
    hist = "\n".join(f"- {h}" for h in d.get("history") or []) or "- (none)"
    return (f"{spec_text(d['spec'])}\n\nRTL:\n{d['rtl']}\n\nTESTBENCH:\n{d['tb']}\n\n"
            f"LOG ({d['stage']}):\n{d['log']}\n\n"
            f"PREVIOUS RETRIES (short-term memory; do not repeat a fix that already failed):\n{hist}")


def make_debug_chain(llm):
    prompt = make_prompt(DEBUG_SYSTEM)
    return (RunnableLambda(lambda d: {"user": debug_user(d)})
            | prompt | llm.with_retry(**RETRY) | StrOutputParser()
            | RunnableLambda(parse_debug)).with_config(run_name="debugger")


# ---------------------------------------------------------------- 9. Report Writer
def make_report_chain(llm):
    prompt = make_prompt(REPORT_SYSTEM)
    return (RunnableLambda(lambda bundle: {"user": json.dumps(bundle, indent=1, default=str)})
            | prompt | llm.with_retry(**RETRY) | StrOutputParser()).with_config(run_name="report_writer")
