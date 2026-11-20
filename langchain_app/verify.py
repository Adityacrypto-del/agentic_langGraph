"""The self-healing verify loop: lint -> simulate -> (on failure) debug -> repeat.

Agentic AI concepts:
  REFLECTION / SELF-HEALING  real compiler and simulator errors drive each fix (max MAX_RETRIES)
  CRITIC                     the debugger names the CULPRIT (RTL or TB), judged against the spec
  SHORT-TERM MEMORY          the retry history goes back into every debug prompt
  GUARDRAIL                  a TB "fix" that removes checks or the TEST_RESULT line is rejected
It is a RunnableLambda(fn) where fn(state, config) passes config into every inner .invoke(),
so the debugger and tool calls appear NESTED under verify_debug_loop in traces.
"""
from langchain_core.callbacks.manager import dispatch_custom_event
from langchain_core.runnables import RunnableLambda

from common import tools_client as T

# The EDA tools wrapped as named Runnables so they show up in traces.
lint_step = RunnableLambda(lambda rtl: T.lint(rtl)).with_config(run_name="lint")
sim_step = RunnableLambda(lambda d: T.simulate(d["rtl"], d["tb"])).with_config(run_name="simulate")


def weakened(old_tb: str, new_tb: str) -> bool:
    """True if the new testbench has fewer check( calls or lost its TEST_RESULT line."""
    return new_tb.count("check(") < old_tb.count("check(") or "TEST_RESULT" not in new_tb


def looks_like_tb(code: str) -> bool:
    """A testbench, not a design: dumps a VCD or prints the TEST_RESULT line."""
    return "$dumpfile" in code or "TEST_RESULT" in code


def _event(kind: str, data: dict, config) -> None:
    """Custom callback event (shown by tracing.py on the live console and in trace.jsonl)."""
    try:
        dispatch_custom_event(kind, data, config=config)
    except RuntimeError:          # no callback manager attached (e.g. direct unit call)
        pass


def make_verify_loop(debug_chain, max_retries: int = 3):
    def verify(state: dict, config) -> dict:
        agent = state["rtl"]                       # output of the RTL agent
        rtl, tb, spec = agent["rtl"], state["tb"], state["spec"]
        retries, history, verify_lints = 0, [], 0
        lint, sim, stage, log = None, None, "", ""

        while True:
            lint = lint_step.invoke(rtl, config)
            verify_lints += 1
            if lint["ok"]:
                sim = sim_step.invoke({"rtl": rtl, "tb": tb}, config)
                stage = "sim" if sim["stage"] == "run" else "compile"
                _event("sim_result", {"passed": sim["passed"], "total": sim["total"],
                                      "failed": sim["failed"], "stage": stage}, config)
                if sim["passed"]:
                    break
                log = sim["log"]
            else:
                stage, log, sim = "lint", lint["log"], None
                _event("lint_result", {"ok": False, "log": log}, config)

            if retries >= max_retries:             # retry cap reached -> give up honestly
                _event("retries_exhausted", {"retries": retries}, config)
                break
            retries += 1
            fix = debug_chain.invoke({"spec": spec, "rtl": rtl, "tb": tb, "log": log,
                                      "stage": stage, "history": history}, config)
            culprit = "RTL" if stage == "lint" else fix["culprit"]   # lint errors are always RTL
            code = fix["code"]

            if "module" not in code:
                msg = f"retry {retries} ({stage}): rejected: debugger returned no code"
            elif culprit == "RTL" and looks_like_tb(code):   # GUARDRAIL: never put a TB in design.v
                msg = f"retry {retries} ({stage}): rejected: RTL fix was testbench code"
            elif culprit == "TB" and weakened(tb, code):
                msg = f"retry {retries} ({stage}): rejected: weakened testbench"
            else:
                if culprit == "TB":
                    tb = code
                else:
                    rtl = code
                msg = f"retry {retries} ({stage}): fixed {culprit} – {fix['diagnosis']}"
            history.append(msg)
            _event("retry", {"n": retries, "stage": stage, "culprit": culprit, "msg": msg}, config)

        passed = bool(sim and sim["passed"])
        return {**state, "rtl": rtl, "tb": tb, "lint": lint, "sim": sim, "passed": passed,
                "retries": retries, "history": history, "verify_lints": verify_lints,
                "agent_steps": agent["agent_steps"], "lint_calls": agent["lint_calls"],
                "agent_rtl": agent["rtl"]}

    return RunnableLambda(verify).with_config(run_name="verify_debug_loop")
