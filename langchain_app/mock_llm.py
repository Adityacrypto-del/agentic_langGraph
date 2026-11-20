"""MOCK LLM (scripted) — EDA results are real.

An offline chat model for the exhibition fallback (no Wi-Fi / API down) and for tests.
It is a real BaseChatModel subclass that supports bind_tools, so the REAL pipeline, the real
agent loop, the real verify loop and the real iverilog/yosys tool server all run unchanged.
It recognises which role is calling from the system prompt. Supports S1 and S5 only.

Scripted story for S1 (shows BOTH loops):
  agent turn 1: lint_verilog(code with a syntax error: missing ';')  -> LINT ERRORS
  agent turn 2: lint_verilog(code that compiles but WRAPS 3->0)      -> LINT OK
  agent turn 3: final answer with that (still buggy) code
  testbench  : a correct, spec-derived testbench (catches the wrap bug)
  simulate   : FAIL -> debugger: CULPRIT: RTL + saturating fix -> simulate PASS
Never use mock results in the benchmark.
"""
import json
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool

from common.prompts import DEBUG_SYSTEM, REPORT_SYSTEM, RTL_SYSTEM, SPEC_SYSTEM, TB_SYSTEM

MOCK_LABEL = "MOCK LLM (scripted) — EDA results are real"
CALL_LOG: list[dict] = []          # every call (role + user text) for tests, e.g. TB isolation

S1_SPEC = {
    "needs_clarification": False, "questions": [],
    "module_name": "excursion_alarm",
    "summary": "Raises alarm after 3 consecutive out-of-range temperature readings.",
    "parameters": [],
    "ports": [
        {"name": "clk", "dir": "input", "width": 1, "meaning": "32768 Hz sampling clock"},
        {"name": "rst_n", "dir": "input", "width": 1, "meaning": "active-low asynchronous reset"},
        {"name": "sample_valid", "dir": "input", "width": 1, "meaning": "high for one cycle per new reading"},
        {"name": "temp", "dir": "input", "width": 8, "meaning": "signed two's complement, 0.5 degC/LSB"},
        {"name": "alarm", "dir": "output", "width": 1, "meaning": "1 when the count equals 3"},
    ],
    "reset": {"name": "rst_n", "kind": "async", "active": "low"},
    "rules": [
        "1. rst_n=0 immediately sets count=0 (alarm=0).",
        "2. Readings are evaluated only on a posedge where sample_valid=1.",
        "3. A reading is out-of-range if temp < 4 or temp > 16 (signed comparison).",
        "4. Out-of-range reading: count = min(count+1, 3) (saturates at 3).",
        "5. In-range reading (4 <= temp <= 16): count = 0.",
        "6. alarm = 1 whenever count == 3, else 0.",
    ],
    "test_scenarios": [
        {"name": "reset", "inputs": "rst_n=0", "expected": "alarm=0"},
        {"name": "three hot", "inputs": "17,20,40 valid", "expected": "alarm 0,0,1"},
        {"name": "saturation", "inputs": "4th and 5th bad readings", "expected": "alarm stays 1"},
        {"name": "upper boundary", "inputs": "16 valid", "expected": "in range, alarm=0"},
        {"name": "lower boundary out", "inputs": "3,3,3 valid", "expected": "alarm 0,0,1"},
        {"name": "lower boundary in", "inputs": "4 valid", "expected": "count resets"},
        {"name": "negative", "inputs": "-2,-2,-128 valid", "expected": "alarm=1 after third"},
        {"name": "invalid ignored", "inputs": "17, (valid=0 x2), 17, 17", "expected": "alarm only after 3rd valid bad"},
        {"name": "invalid out-of-range ignored", "inputs": "valid=0 temp=100 x3", "expected": "alarm=0"},
        {"name": "async reset", "inputs": "alarm=1 then rst_n=0 between edges", "expected": "alarm=0 immediately"},
    ],
    "clk_hz": 32768,
    "power_budget_nw": 100,
}

S5_SPEC = {
    "needs_clarification": True,
    "questions": [
        "What temperature encoding and units does the sensor provide (e.g. signed 8-bit, 0.5 degC per LSB)?",
        "What exact temperature counts as 'too warm' (the numeric threshold)?",
        "How many consecutive readings, or how long, above the threshold before warning?",
        "Should the warning latch until acknowledged/reset, or clear when the temperature recovers?",
    ],
}

_HEAD = """module excursion_alarm (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              sample_valid,
    input  wire signed [7:0] temp,
    output wire              alarm
);
    reg [1:0] count;
    wire out_of_range = (temp < 8'sd4) || (temp > 8'sd16);   // signed compare
"""
RTL_SYNTAX_ERR = _HEAD + """    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) count <= 2'd0
        else if (sample_valid) begin
            if (!out_of_range) count <= 2'd0;
            else count <= count + 2'd1;
        end
    end
    assign alarm = (count == 2'd3);
endmodule
"""
RTL_WRAP_BUG = RTL_SYNTAX_ERR.replace("count <= 2'd0\n", "count <= 2'd0;\n")
RTL_FIXED = RTL_WRAP_BUG.replace("else count <= count + 2'd1;",
                                 "else if (count != 2'd3) count <= count + 2'd1;  // saturate at 3")

S1_TB = r"""`timescale 1ns/1ps
module tb;
  integer total = 0, failed = 0;
  reg clk = 0;
  reg rst_n = 0;
  reg sample_valid = 0;
  reg signed [7:0] temp = 0;
  wire alarm;
  always #5 clk = ~clk;
  task check(input [63:0] exp, input [63:0] act, input [255:0] label);
    begin
      total = total + 1;
      if (exp !== act) begin
        failed = failed + 1;
        $display("FAIL: %0s exp=%0d act=%0d t=%0t", label, exp, act, $time);
      end
    end
  endtask
  excursion_alarm dut(.clk(clk), .rst_n(rst_n), .sample_valid(sample_valid), .temp(temp), .alarm(alarm));
  // drive one input on the negedge, then wait until 1 ns after the posedge that samples it
  task drive(input v, input signed [7:0] t);
    begin
      @(negedge clk); sample_valid = v; temp = t;
      @(posedge clk); #1;
    end
  endtask
  initial begin
    $dumpfile("wave.vcd"); $dumpvars(0, tb);
    #12 check(0, alarm, "reset: alarm low");
    @(negedge clk); rst_n = 1;
    drive(1, 17); check(0, alarm, "1st hot (17)");
    drive(1, 20); check(0, alarm, "2nd hot (20)");
    drive(1, 40); check(1, alarm, "3rd hot -> alarm");
    drive(1, 50); check(1, alarm, "4th bad: saturates, alarm stays");
    drive(1, 60); check(1, alarm, "5th bad: still saturated");
    drive(1, 16); check(0, alarm, "16 (8C) is in range: clears");
    drive(1, 3);  drive(1, 3); check(0, alarm, "2 x temp=3: no alarm yet");
    drive(1, 4);  check(0, alarm, "temp=4 (2C) in range resets count");
    drive(1, 3);  drive(1, 3); drive(1, 3); check(1, alarm, "3 x temp=3 -> alarm");
    drive(1, 10); check(0, alarm, "in range clears");
    drive(1, -2); drive(1, -2); drive(1, -128); check(1, alarm, "negative temps are out of range (signed)");
    drive(1, 4);  check(0, alarm, "clear after negatives");
    drive(1, 17); drive(0, 4); drive(0, 4); drive(1, 17); check(0, alarm, "invalid cycles ignored: 2 bad");
    drive(1, 17); check(1, alarm, "3rd valid bad across ignored cycles");
    drive(1, 4);  drive(0, 100); drive(0, 100); drive(0, 100); check(0, alarm, "invalid out-of-range ignored");
    drive(1, 17); drive(1, 17); drive(1, 17); check(1, alarm, "alarm before async reset");
    #2 rst_n = 0; #1 check(0, alarm, "async reset clears without a clock edge");
    @(negedge clk); rst_n = 1;
    drive(1, 17); check(0, alarm, "count restarted after reset");
    sample_valid = 0;
    if (failed == 0) $display("TEST_RESULT: PASS total=%0d failed=%0d", total, failed);
    else $display("TEST_RESULT: FAIL total=%0d failed=%0d", total, failed);
    $finish;
  end
  initial begin #2000000; $display("TEST_RESULT: FAIL total=0 failed=1 timeout"); $finish; end
endmodule
"""


def _fence(code: str) -> str:
    return "```verilog\n" + code + "```"


def _report_md(bundle: dict) -> str:
    sim, syn, pwr = bundle.get("sim", {}), bundle.get("synth", {}), bundle.get("power", {})
    hist = "\n".join(f"- {h}" for h in bundle.get("history", [])) or "- none"
    rules = "\n".join(f"- {r}" for r in bundle.get("spec", {}).get("rules", []))
    return f"""> **{MOCK_LABEL}.** The LLM text was scripted; every tool number below came from real iverilog/yosys runs.

# Report: {bundle.get('spec', {}).get('module_name', '?')}

## Summary
Status: **{bundle.get('status')}** after {bundle.get('retries')} verify retries.

## Spec rules
{rules}

## Design decisions
2-bit saturating counter of consecutive out-of-range readings; signed comparison against 4 and 16.

## Verification result
passed={sim.get('passed')} total={sim.get('total')} failed={sim.get('failed')}

## Synthesis result
cells={syn.get('cells')} dffs={syn.get('dffs')} area_ge={syn.get('area_ge')}

## Power estimate
{pwr.get('dynamic_nw')} nW vs budget {pwr.get('budget_nw')} nW (within budget: {pwr.get('within_budget')}).
This is a switching-activity estimate, not silicon power.

## Retry history
{hist}

## Limitations
Generic-gate synthesis; power is a switching-activity estimate; simulation only.
"""


class MockChatModel(BaseChatModel):
    """Scripted chat model. Detects the caller's role from the system prompt."""

    @property
    def _llm_type(self) -> str:
        return "frostbyte-mock"

    def bind_tools(self, tools, **kwargs):
        return self.bind(tools=[convert_to_openai_tool(t) for t in tools], **kwargs)

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        system = messages[0].content if messages else ""
        user = next((m.content for m in messages if m.type == "human"), "")
        role = ("spec" if system == SPEC_SYSTEM else
                "rtl" if system.startswith(RTL_SYSTEM) else
                "tb" if system == TB_SYSTEM else
                "debug" if system == DEBUG_SYSTEM else
                "report" if system == REPORT_SYSTEM else "unknown")
        CALL_LOG.append({"role": role, "system": system, "user": user})
        msg = getattr(self, f"_{role}")(messages, user)
        return ChatResult(generations=[ChatGeneration(message=msg)])

    # ---- one method per role
    def _spec(self, messages, user):
        if "too warm" in user:
            return AIMessage(content=json.dumps(S5_SPEC))
        if "excursion alarm" in user:
            return AIMessage(content=json.dumps(S1_SPEC, indent=1))
        raise ValueError(f"{MOCK_LABEL}: the mock only supports specs S1 and S5")

    def _rtl(self, messages, user):
        n_tool = sum(isinstance(m, ToolMessage) for m in messages)
        if n_tool == 0:
            return self._tool_call(RTL_SYNTAX_ERR, 1)
        if n_tool == 1:
            return self._tool_call(RTL_WRAP_BUG, 2)
        return AIMessage(content=_fence(RTL_WRAP_BUG))

    @staticmethod
    def _tool_call(code: str, n: int) -> AIMessage:
        return AIMessage(content="", tool_calls=[{"name": "lint_verilog", "args": {"rtl_code": code},
                                                  "id": f"mock_call_{n}", "type": "tool_call"}])

    def _tb(self, messages, user):
        return AIMessage(content=_fence(S1_TB))

    def _debug(self, messages, user):
        return AIMessage(content="CULPRIT: RTL\nThe count wraps from 3 to 0 on a 4th out-of-range "
                                 "reading instead of saturating at 3 as rule 4 requires.\n"
                         + _fence(RTL_FIXED))

    def _report(self, messages, user):
        return AIMessage(content=_report_md(json.loads(user)))

    def _unknown(self, messages, user):
        raise ValueError(f"{MOCK_LABEL}: unrecognised system prompt")
