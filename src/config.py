"""Configuration management for the Research Agent system."""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class APIConfig:
    """API key configuration for AI providers."""
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    perplexity_api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "APIConfig":
        """Load API configuration from environment variables."""
        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            perplexity_api_key=os.getenv("PERPLEXITY_API_KEY")
        )

    def validate(self) -> dict[str, bool]:
        """Check which API keys are configured."""
        return {
            "anthropic": bool(self.anthropic_api_key),
            "google": bool(self.google_api_key),
            "perplexity": bool(self.perplexity_api_key)
        }

    def get_available_agents(self) -> list[str]:
        """Get list of agents with valid API keys."""
        agents = []
        if self.anthropic_api_key:
            agents.append("claude")
        if self.google_api_key:
            agents.append("gemini")
        if self.perplexity_api_key:
            agents.append("perplexity")
        return agents


@dataclass
class ServerConfig:
    """Server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = field(default_factory=lambda: ["*"])

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Load server configuration from environment variables."""
        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            debug=os.getenv("DEBUG", "false").lower() == "true"
        )


@dataclass
class AgentConfig:
    """Agent behavior configuration."""
    default_orchestrator: str = "claude"
    max_parallel_tasks: int = 3
    task_timeout_seconds: int = 120
    enable_streaming: bool = True
    claude_model: str = "claude-sonnet-4-20250514"
    gemini_model: str = "gemini-1.5-pro"
    perplexity_model: str = "llama-3.1-sonar-large-128k-online"

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load agent configuration from environment variables."""
        return cls(
            default_orchestrator=os.getenv("DEFAULT_ORCHESTRATOR", "claude"),
            max_parallel_tasks=int(os.getenv("MAX_PARALLEL_TASKS", "3")),
            task_timeout_seconds=int(os.getenv("TASK_TIMEOUT_SECONDS", "120")),
            enable_streaming=os.getenv("ENABLE_STREAMING", "true").lower() == "true"
        )


@dataclass
class Config:
    """Main configuration container."""
    api: APIConfig
    server: ServerConfig
    agent: AgentConfig

    @classmethod
    def from_env(cls) -> "Config":
        """Load all configuration from environment variables."""
        return cls(
            api=APIConfig.from_env(),
            server=ServerConfig.from_env(),
            agent=AgentConfig.from_env()
        )

    def summary(self) -> dict:
        """Get configuration summary (safe for logging)."""
        return {
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "debug": self.server.debug
            },
            "agents": {
                "available": self.api.get_available_agents(),
                "default_orchestrator": self.agent.default_orchestrator,
                "max_parallel_tasks": self.agent.max_parallel_tasks
            }
        }


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment."""
    global _config
    load_dotenv(override=True)
    _config = Config.from_env()
    return _config
