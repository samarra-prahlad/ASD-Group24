"""Configuration for the shared multi-agent server (all overridable by environment variables)."""
import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "qwen2.5:0.5b")
WORKER_MODEL = os.getenv("WORKER_MODEL", "qwen2.5:0.5b")
REVIEWER_MODEL = os.getenv("REVIEWER_MODEL", "llama3.1:8b")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "180"))  # seconds per agent call

DATA_DIR = os.getenv("MULTI_AGENT_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
HOST = os.getenv("MULTI_AGENT_HOST", "0.0.0.0")
PORT = int(os.getenv("MULTI_AGENT_PORT", "7002"))

MAX_EVIDENCE_RECORDS = 20
MAX_EVIDENCE_CHARS = 6000
