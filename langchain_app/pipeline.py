"""The whole FrostByte pipeline as ONE composed LCEL Runnable.

Because it is a single Runnable it can be .invoke()d, .stream()ed, traced with callbacks and
drawn with .get_graph(). Every step has a run_name so traces and diagrams read like the pipeline.

Agentic AI concepts by primitive:
  RunnablePassthrough.assign  -> PLANNING / task decomposition (state grows step by step)
  RunnableBranch              -> ROUTING (clarification gate, sim passed?, approved?)
  RunnableParallel            -> PARALLELIZATION (RTL || TB, synth || power)
  RunnableLambda              -> custom steps: the self-healing loop and the HUMAN-IN-THE-LOOP gate
"""
from operator import itemgetter

from langchain_core.runnables import (RunnableBranch, RunnableLambda,
                                      RunnablePassthrough)

from common import tools_client as T
from common.utils import module_name

from .chains import (make_debug_chain, make_report_chain, make_spec_chain,
                     make_testbench_chain)
from .rtl_agent import make_rtl_agent
from .verify import make_verify_loop

TB_CLK_NS = 10.0      # TB_SYSTEM mandates a 10 ns testbench clock


# ------------------------------------------------------------- conditions for RunnableBranch
def needs_clarification(s: dict) -> bool:
    return bool(s["spec"].get("needs_clarification"))


def sim_passed(s: dict) -> bool:
    return bool(s.get("passed"))


def approved(s: dict) -> bool:
    return bool(s.get("approved"))


# ------------------------------------------------------------- simple steps
def clarify(s: dict) -> dict:
    """GUARDRAIL: ambiguous request -> return the questions and STOP (no RTL is written)."""
    return {**s, "status": "clarification", "questions": s["spec"].get("questions", [])}


def synth_fn(s: dict) -> dict:
    top = module_name(s["rtl"], s["spec"].get("module_name", ""))   # real name in the RTL
    return T.synthesize(s["rtl"], top)


def power_fn(s: dict) -> dict:
    sp = s["spec"]
    return T.power(s["sim"]["run_id"], clk_hz=sp.get("clk_hz") or 32768,
                   budget_nw=sp.get("power_budget_nw"), tb_clk_ns=TB_CLK_NS)


def make_human_approval(auto_approve: bool, ask=input):
    """HUMAN-IN-THE-LOOP: a person sees the real numbers and approves before the report."""
    def gate(s: dict) -> dict:
        sim, syn, pwr = s.get("sim") or {}, s.get("synth") or {}, s.get("pwr") or {}
        print("\n" + "=" * 64)
        print(f" HUMAN APPROVAL   sim passed={s.get('passed')} total={sim.get('total')} "
              f"failed={sim.get('failed')} retries={s.get('retries')}")
        print(f"                  cells={syn.get('cells')} dffs={syn.get('dffs')} "
              f"area_ge={syn.get('area_ge')}")
        print(f"                  power={pwr.get('dynamic_nw')} nW  budget={pwr.get('budget_nw')} nW "
              f"within_budget={pwr.get('within_budget')}")
        print("=" * 64)
        if auto_approve:
            print(" approved_by: auto (--auto-approve)")
            return {**s, "approved": True, "approved_by": "auto"}
        ok = ask("Approve and write report? [y/N] ").strip().lower() == "y"
        return {**s, "approved": ok, "approved_by": "human" if ok else "declined"}
    return RunnableLambda(gate).with_config(run_name="human_approval")


def report_bundle(s: dict) -> dict:
    """Only real tool numbers go to the report writer (it must not invent results)."""
    sim = s.get("sim") or {}
    syn = {k: v for k, v in (s.get("synth") or {}).items() if k not in ("log", "ctx")}
    return {"status": "PASS" if s.get("passed") else "FAILED after retries",
            "spec": s["spec"],
            "sim": {k: sim.get(k) for k in ("passed", "total", "failed", "log")},
            "synth": syn,
            "power": {k: v for k, v in (s.get("pwr") or {}).items() if k != "ctx"},
            "history": s.get("history", []), "retries": s.get("retries", 0),
            "agent_lint_calls": s.get("lint_calls", 0)}


# ------------------------------------------------------------- composition
def build_pipeline(llm, max_retries: int = 3, auto_approve: bool = False, ask=input):
    spec_chain = make_spec_chain(llm)
    testbench_chain = make_testbench_chain(llm)
    rtl_designer_agent = make_rtl_agent(llm)
    verify_debug_loop = make_verify_loop(make_debug_chain(llm), max_retries)
    report_chain = make_report_chain(llm)

    passthrough = RunnablePassthrough()

    # RTL Designer and Testbench Writer run in PARALLEL; both receive ONLY the spec.
    design_parallel = RunnablePassthrough.assign(
        rtl=itemgetter("spec") | rtl_designer_agent,
        tb=itemgetter("spec") | testbench_chain,
    ).with_config(run_name="design_parallel")

    # Synthesis and power estimation run in PARALLEL. .assign() wraps a RunnableParallel and
    # merges its outputs into the state (a bare RunnableParallel would drop the other keys).
    implement_parallel = RunnablePassthrough.assign(
        synth=RunnableLambda(synth_fn).with_config(run_name="synthesize"),
        pwr=RunnableLambda(power_fn).with_config(run_name="power_estimate"),
    ).with_config(run_name="implement_parallel")

    write_report = RunnablePassthrough.assign(
        report=RunnableLambda(report_bundle) | report_chain)

    build_and_verify = (
        design_parallel
        | verify_debug_loop
        | RunnableBranch((sim_passed, implement_parallel), passthrough)
        | make_human_approval(auto_approve, ask)
        | RunnableBranch((approved, write_report), passthrough)
    )

    frostbyte = (
        RunnablePassthrough.assign(spec=itemgetter("request") | spec_chain)        # 1 Spec Analyst
        | RunnableBranch(                                                             # 2 gate
            (needs_clarification, RunnableLambda(clarify).with_config(run_name="clarify_and_stop")),
            build_and_verify,
        ).with_config(run_name="clarification_gate")
    ).with_config(run_name="frostbyte")
    return frostbyte
