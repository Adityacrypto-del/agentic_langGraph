"""Shared parsing helpers (handbook 6.1, verbatim) plus module-name detection.

Agentic AI concept: structured-output parsing is a guardrail between the LLM and the tools."""
import json, re

def extract_code(text: str) -> str:
    m = re.search(r"```(?:verilog|systemverilog|sv|v)?\s*\n(.*?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip() + "\n"

def extract_json(text: str) -> dict:
    t = re.sub(r"```(?:json)?", "", text)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])


def module_name(verilog: str, default: str = "") -> str:
    """Return the first module name declared in the code (used as the Yosys top)."""
    m = re.search(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)", verilog, re.M)
    return m.group(1) if m else default
