"""LLM factory: one switch for every provider (Groq, Gemini, Ollama) or the offline mock.

Agentic AI concept: RELIABILITY. A client-side rate limiter keeps us under free-tier limits;
.with_retry() (added in chains.py / rtl_agent.py) handles transient errors with backoff.
Provider packages are imported lazily, so you only need the one you use.
"""
import os

from dotenv import load_dotenv
from langchain_core.rate_limiters import InMemoryRateLimiter

load_dotenv()

TEMPERATURE = 0.2          # same on every platform (fairness rule)


def model_label(mock: bool = False) -> str:
    """Human-readable 'provider/model' string for reports and the poster."""
    if mock:
        return "mock/scripted"
    return f"{os.getenv('LLM_PROVIDER', 'groq')}/{os.getenv('LLM_MODEL', '?')}"


def get_llm(mock: bool = False):
    if mock:
        from .mock_llm import MockChatModel
        return MockChatModel()

    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    model = os.getenv("LLM_MODEL")
    if not model:
        raise RuntimeError("Set LLM_MODEL in .env (see .env.example)")
    # ~0.5 requests/second by default: friendly to free tiers
    limiter = InMemoryRateLimiter(requests_per_second=float(os.getenv("LLM_RPS", "0.5")),
                                  check_every_n_seconds=0.1, max_bucket_size=1)

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, temperature=TEMPERATURE, rate_limiter=limiter)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, temperature=TEMPERATURE, rate_limiter=limiter)
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model, temperature=TEMPERATURE, rate_limiter=limiter,
                          base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                          num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "16384")))  # long debug prompts
    raise ValueError(f"Unknown LLM_PROVIDER={provider!r} (use groq, gemini or ollama)")
