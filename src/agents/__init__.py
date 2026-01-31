"""Agent implementations for A2A Protocol."""

from .base import BaseAgent, AgentRegistry, ProviderPriority
from .cards import AGENT_CARDS, get_agent_card
from .perplexity import PerplexityAgent
from .claude import ClaudeAgent
from .gemini import GeminiAgent
from .ollama import OllamaAgent
from .orchestrator import OrchestratorAgent

__all__ = [
    "BaseAgent",
    "AgentRegistry",
    "ProviderPriority",
    "AGENT_CARDS",
    "get_agent_card",
    "PerplexityAgent",
    "ClaudeAgent",
    "GeminiAgent",
    "OllamaAgent",
    "OrchestratorAgent",
]
