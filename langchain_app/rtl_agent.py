"""The RTL Designer AGENT: an LLM that decides by itself when to call the lint tool.

Agentic AI concept: TOOL-CALLING AGENT (ReAct: reason -> act -> observe -> repeat).
We write the loop ourselves (no LangGraph, no create_agent) so every step is visible:
  1. call the model (with the lint_verilog tool bound)
  2. if it returns tool_calls -> run each tool, append ToolMessages, call again
  3. stop when it answers without a tool call, or after max_iter turns
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool

from common import tools_client as T
from common.prompts import RTL_SYSTEM
from common.utils import extract_code

AGENT_INSTRUCTION = ("\n\nBefore answering, call lint_verilog on your code. Fix any reported errors "
                     "(at most 3 attempts), then output only the final ```verilog block.")


@tool
def lint_verilog(rtl_code: str) -> str:
    """Compile Verilog with Icarus Verilog (iverilog -g2012 -Wall).
    Returns 'LINT OK' or 'LINT ERRORS' followed by the compiler messages."""
    r = T.lint(rtl_code)
    return "LINT OK" if r["ok"] else "LINT ERRORS:\n" + r["log"]


def _text(msg) -> str:
    c = msg.content
    if isinstance(c, str):
        return c
    return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)


def make_rtl_agent(llm, max_iter: int = 6):
    # ORDER MATTERS: bind_tools first, then with_retry (a RunnableRetry has no .bind_tools()).
    model = llm.bind_tools([lint_verilog]).with_retry(stop_after_attempt=5,
                                                     wait_exponential_jitter=True)

    def run_agent(spec: dict, config) -> dict:
        msgs = [SystemMessage(content=RTL_SYSTEM + AGENT_INSTRUCTION),
                HumanMessage(content="SPEC:\n" + json.dumps(spec, indent=1))]
        steps, last_code, ai = [], "", None
        for _ in range(max_iter):
            ai = model.invoke(msgs, config)                 # REASON
            msgs.append(ai)
            if not ai.tool_calls:                           # final answer -> stop
                break
            for tc in ai.tool_calls:                        # ACT
                if tc["name"] != "lint_verilog":
                    msgs.append(ToolMessage(content=f"Unknown tool {tc['name']}",
                                            tool_call_id=tc["id"]))
                    continue
                last_code = tc["args"].get("rtl_code", "") or last_code
                out = lint_verilog.invoke(tc, config)       # OBSERVE (returns a ToolMessage)
                msgs.append(out)
                steps.append({"tool": "lint_verilog", "ok": out.content.startswith("LINT OK")})

        final = _text(ai) if ai is not None and not ai.tool_calls else ""
        if "```" in final:
            rtl = extract_code(final)
        elif last_code:                                     # robustness fallback
            rtl = last_code.strip() + "\n"
        else:
            rtl = extract_code(final)
        return {"rtl": rtl, "agent_steps": steps, "lint_calls": len(steps)}

    return RunnableLambda(run_agent).with_config(run_name="rtl_designer_agent")
