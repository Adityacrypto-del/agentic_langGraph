"""Observability: a LangChain callback handler for the live demo console and trace.jsonl.

Agentic AI concept: OBSERVABILITY. LangChain calls these hooks for every chain, LLM and tool
start/end. We
  (a) print a clean coloured live log of the NAMED pipeline steps, tool calls and retries,
  (b) record every event with a timestamp (written to outputs/<module>/trace.jsonl),
  (c) count LLM calls and tokens when the provider reports them.
"""
import json
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

STEPS = {"spec_analyst", "clarification_gate", "clarify_and_stop", "design_parallel",
         "rtl_designer_agent", "testbench_writer", "verify_debug_loop", "lint", "simulate",
         "debugger", "implement_parallel", "synthesize", "power_estimate", "human_approval",
         "report_writer"}

C = {"dim": "\033[2m", "b": "\033[1m", "g": "\033[32m", "r": "\033[31m", "y": "\033[33m",
     "c": "\033[36m", "m": "\033[35m", "x": "\033[0m"}
MOCK_LABEL = "MOCK LLM (scripted) — EDA results are real"


class FrostByteTracer(BaseCallbackHandler):
    raise_error = False

    def __init__(self, mock: bool = False, live: bool = True):
        self.mock, self.live = mock, live
        self.events: list[dict] = []
        self.open: dict[UUID, tuple[str, float, int]] = {}   # run_id -> (name, t0, depth)
        self.depth: dict[UUID, int] = {}
        self.parents: dict[UUID, UUID | None] = {}
        self.llm_calls = 0
        self.tokens = {"input": 0, "output": 0}
        self.t_start = time.time()
        if mock:
            self._say(f"{C['m']}{C['b']}*** {MOCK_LABEL} ***{C['x']}")

    # ------------------------------------------------------------ helpers
    def _say(self, text: str, depth: int = 0) -> None:
        if not self.live:
            return
        prefix = f"{C['m']}[MOCK]{C['x']} " if self.mock else ""
        print(f"{prefix}{C['dim']}{time.time() - self.t_start:6.1f}s{C['x']} {'  ' * depth}{text}",
              flush=True)

    def _log(self, kind: str, **data: Any) -> None:
        self.events.append({"t": round(time.time(), 3), "event": kind, **data})

    def _depth(self, run_id, parent_run_id) -> int:
        d = self.depth.get(parent_run_id, -1) + 1 if parent_run_id else 0
        self.depth[run_id] = d
        return d

    def _visible_depth(self, parent) -> int:
        """Indent only by the number of NAMED ancestors, so the console stays flat and readable."""
        n = 0
        while parent in self.open or parent in self.depth:
            if parent in self.open and self.open[parent][0] in STEPS:
                n += 1
            parent = self.parents.get(parent)
        return n

    # ------------------------------------------------------------ chains (our named steps)
    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kw):
        name = kw.get("name") or (serialized or {}).get("name") or "chain"
        self.parents[run_id] = parent_run_id
        self._depth(run_id, parent_run_id)
        vd = self._visible_depth(parent_run_id)
        self.open[run_id] = (name, time.time(), vd)
        self._log("chain_start", name=name, run_id=str(run_id),
                  parent=str(parent_run_id) if parent_run_id else None)
        if name in STEPS and name not in ("lint", "simulate"):
            self._say(f"{C['c']}▶ {name}{C['x']} …", vd)

    def on_chain_end(self, outputs, *, run_id, **kw):
        name, t0, vd = self.open.pop(run_id, ("chain", time.time(), 0))
        dt = time.time() - t0
        self._log("chain_end", name=name, run_id=str(run_id), seconds=round(dt, 3))
        if name == "lint" and isinstance(outputs, dict):
            ok = outputs.get("ok")
            self._say(f"🔍 lint (iverilog) → {C['g'] + 'OK' if ok else C['r'] + 'ERRORS'}{C['x']}", vd)
        elif name == "simulate" and isinstance(outputs, dict):
            p = outputs.get("passed")
            col = C["g"] if p else C["r"]
            self._say(f"🧪 simulate (vvp) → {col}{'PASS' if p else 'FAIL'}{C['x']} "
                      f"total={outputs.get('total')} failed={outputs.get('failed')}", vd)
        elif name == "synthesize" and isinstance(outputs, dict):
            self._say(f"🧱 yosys → cells={outputs.get('cells')} dffs={outputs.get('dffs')} "
                      f"area={outputs.get('area_ge')} GE", vd)
        elif name == "power_estimate" and isinstance(outputs, dict):
            self._say(f"⚡ power → {outputs.get('dynamic_nw')} nW "
                      f"(budget {outputs.get('budget_nw')} nW, within={outputs.get('within_budget')})", vd)
        elif name == "clarify_and_stop":
            self._say(f"{C['y']}✋ clarification needed — stopping, no RTL written{C['x']}", vd)
        if name in STEPS and name not in ("lint", "simulate"):
            self._say(f"{C['g']}✔ {name}{C['x']} {dt:.1f}s", vd)

    def on_chain_error(self, error, *, run_id, **kw):
        name, t0, vd = self.open.pop(run_id, ("chain", time.time(), 0))
        self._log("chain_error", name=name, run_id=str(run_id), error=repr(error)[:500])
        if name in STEPS:
            self._say(f"{C['r']}✘ {name}: {type(error).__name__}: {str(error)[:120]}{C['x']}", vd)

    # ------------------------------------------------------------ LLM calls
    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kw):
        self.llm_calls += 1
        self.parents[run_id] = parent_run_id
        self.open[run_id] = ("llm", time.time(), self._visible_depth(parent_run_id))
        self._log("llm_start", run_id=str(run_id), parent=str(parent_run_id) if parent_run_id else None,
                  n_messages=sum(len(m) for m in messages))

    def on_llm_end(self, response, *, run_id, **kw):
        _, t0, vd = self.open.pop(run_id, ("llm", time.time(), 0))
        tin = tout = 0
        tool_calls = []
        for gens in response.generations:
            for g in gens:
                msg = getattr(g, "message", None)
                um = getattr(msg, "usage_metadata", None) or {}
                tin += um.get("input_tokens", 0) or 0
                tout += um.get("output_tokens", 0) or 0
                tool_calls += [tc["name"] for tc in (getattr(msg, "tool_calls", None) or [])]
        self.tokens["input"] += tin
        self.tokens["output"] += tout
        self._log("llm_end", run_id=str(run_id), seconds=round(time.time() - t0, 3),
                  input_tokens=tin, output_tokens=tout, tool_calls=tool_calls)
        self._say(f"{C['dim']}💬 llm call {self.llm_calls} {time.time() - t0:.1f}s"
                  f"{' → tool call' if tool_calls else ''}{C['x']}", vd)

    def on_llm_error(self, error, *, run_id, **kw):
        self.open.pop(run_id, None)
        self._log("llm_error", run_id=str(run_id), error=repr(error)[:500])
        self._say(f"{C['y']}⚠ llm error (will retry with backoff): {type(error).__name__}{C['x']}")

    # ------------------------------------------------------------ tools (agent's lint_verilog)
    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kw):
        name = (serialized or {}).get("name") or kw.get("name") or "tool"
        self.parents[run_id] = parent_run_id
        self.open[run_id] = (name, time.time(), self._visible_depth(parent_run_id))
        self._log("tool_start", name=name, run_id=str(run_id), input_chars=len(input_str or ""))

    def on_tool_end(self, output, *, run_id, **kw):
        name, t0, vd = self.open.pop(run_id, ("tool", time.time(), 0))
        text = getattr(output, "content", output)
        text = text if isinstance(text, str) else str(text)
        ok = text.startswith("LINT OK")
        first_err = next((ln.strip() for ln in text.splitlines()[1:] if ln.strip()), "")
        self._log("tool_end", name=name, run_id=str(run_id), ok=ok, output=text[:1500],
                  seconds=round(time.time() - t0, 3))
        shown = f"{C['g']}LINT OK{C['x']}" if ok else f"{C['r']}LINT ERRORS{C['x']} ({first_err[:70]})"
        self._say(f"🔧 {name} → {shown}", vd)

    # ------------------------------------------------------------ custom events from verify.py
    def on_custom_event(self, name, data, *, run_id, **kw):
        self._log("custom", name=name, **{k: v for k, v in data.items() if k != "log"})
        vd = self._visible_depth(run_id) + 1
        if name == "retry":
            self._say(f"{C['y']}🔁 {data['msg']}{C['x']}", vd)
        elif name == "retries_exhausted":
            self._say(f"{C['r']}⛔ retry cap reached ({data['retries']}) — reporting failure honestly{C['x']}", vd)

    # ------------------------------------------------------------ output
    def write_jsonl(self, path: str) -> None:
        with open(path, "w") as f:
            for e in self.events:
                f.write(json.dumps(e, default=str) + "\n")
