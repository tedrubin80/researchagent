"""Agent Card Definitions for Perplexity, Claude, and Gemini.

These agent cards describe the capabilities and skills of each AI provider
in the A2A protocol format.
"""

from typing import Optional
from src.a2a.protocol import AgentCard, AgentCapabilities, AgentSkill


# =============================================================================
# PERPLEXITY AGENT CARD
# Primary Role: Web Research & Source Discovery
# Strengths: Real-time web search, citation gathering, fact verification
# =============================================================================

PERPLEXITY_CARD = AgentCard(
    name="Perplexity Research Agent",
    description="Web search and source discovery specialist. Excels at finding current information, gathering citations, and verifying facts from multiple web sources.",
    version="1.0.0",
    url="http://localhost:8000/agents/perplexity",
    provider="Perplexity AI",
    capabilities=AgentCapabilities(
        streaming=True,
        push_notifications=False,
        batch_processing=True,
        multimodal=False,
        long_context=False
    ),
    skills=[
        AgentSkill(
            id="web-search",
            name="Web Search",
            description="Search the web for current information with citations and sources",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_sources": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of sources to return"
                    },
                    "recency": {
                        "type": "string",
                        "enum": ["day", "week", "month", "year", "all"],
                        "default": "month",
                        "description": "Time filter for search results"
                    },
                    "focus": {
                        "type": "string",
                        "enum": ["web", "academic", "news", "youtube"],
                        "default": "web",
                        "description": "Search focus area"
                    }
                },
                "required": ["query"]
            },
            tags=["search", "web", "research"]
        ),
        AgentSkill(
            id="fact-check",
            name="Fact Verification",
            description="Verify claims against multiple authoritative sources",
            input_schema={
                "type": "object",
                "properties": {
                    "claim": {
                        "type": "string",
                        "description": "The claim to verify"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context for the claim"
                    }
                },
                "required": ["claim"]
            },
            tags=["verification", "fact-check"]
        ),
        AgentSkill(
            id="source-discovery",
            name="Source Discovery",
            description="Find authoritative sources on a topic",
            input_schema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to find sources for"
                    },
                    "source_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Preferred source types (academic, news, official)"
                    }
                },
                "required": ["topic"]
            },
            tags=["sources", "research"]
        )
    ],
    metadata={
        "rate_limit": "100 requests/minute",
        "context_window": 4096,
        "strengths": [
            "Real-time web search",
            "Citation gathering",
            "Fact verification",
            "Current events"
        ]
    }
)


# =============================================================================
# CLAUDE AGENT CARD
# Primary Role: Analysis & Synthesis
# Strengths: Deep reasoning, nuanced writing, document analysis, structured outputs
# =============================================================================

CLAUDE_CARD = AgentCard(
    name="Claude Analysis Agent",
    description="Deep analysis, reasoning, and synthesis specialist. Excels at understanding complex topics, identifying patterns, and creating well-structured documents.",
    version="1.0.0",
    url="http://localhost:8000/agents/claude",
    provider="Anthropic",
    capabilities=AgentCapabilities(
        streaming=True,
        push_notifications=True,
        batch_processing=True,
        multimodal=True,
        long_context=True
    ),
    skills=[
        AgentSkill(
            id="document-analysis",
            name="Document Analysis",
            description="Analyze and extract insights from documents, identifying key themes and information",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Document content to analyze"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["summary", "detailed", "themes", "entities"],
                        "default": "detailed"
                    },
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific areas to focus on"
                    }
                },
                "required": ["content"]
            },
            tags=["analysis", "documents"]
        ),
        AgentSkill(
            id="synthesis",
            name="Research Synthesis",
            description="Combine multiple sources into coherent, well-structured analysis",
            input_schema={
                "type": "object",
                "properties": {
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "citation": {"type": "string"},
                                "relevance": {"type": "number"}
                            }
                        },
                        "description": "Sources to synthesize"
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["report", "summary", "bullet_points", "narrative"],
                        "default": "report"
                    },
                    "target_length": {
                        "type": "string",
                        "enum": ["brief", "moderate", "comprehensive"],
                        "default": "moderate"
                    }
                },
                "required": ["sources"]
            },
            tags=["synthesis", "writing", "research"]
        ),
        AgentSkill(
            id="gap-identification",
            name="Gap Analysis",
            description="Identify missing information, contradictions, and areas needing more research",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to analyze for gaps"
                    },
                    "expected_coverage": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Topics that should be covered"
                    }
                },
                "required": ["content"]
            },
            tags=["analysis", "quality"]
        ),
        AgentSkill(
            id="structured-output",
            name="Structured Output Generation",
            description="Generate well-formatted outputs in various formats (JSON, markdown, etc.)",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to structure"
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["json", "markdown", "html", "csv"],
                        "default": "markdown"
                    },
                    "schema": {
                        "type": "object",
                        "description": "JSON schema for output structure"
                    }
                },
                "required": ["content"]
            },
            tags=["formatting", "output"]
        )
    ],
    metadata={
        "rate_limit": "50 requests/minute",
        "context_window": 200000,
        "model": "claude-3-opus-20240229",
        "strengths": [
            "Deep reasoning",
            "Nuanced writing",
            "Document analysis",
            "Structured outputs",
            "Large context handling"
        ]
    }
)


# =============================================================================
# OPENAI AGENT CARD
# Primary Role: Multimodal Processing & Validation
# Strengths: Image/video analysis, large context windows, cross-referencing
# =============================================================================

OPENAI_CARD = AgentCard(
    name="OpenAI GPT Agent",
    description="Multimodal processing and cross-validation specialist. Excels at analyzing images, processing large documents, and validating information across sources.",
    version="1.0.0",
    url="http://localhost:8000/agents/openai",
    provider="OpenAI",
    capabilities=AgentCapabilities(
        streaming=True,
        push_notifications=False,
        batch_processing=True,
        multimodal=True,
        long_context=True
    ),
    skills=[
        AgentSkill(
            id="image-analysis",
            name="Image Analysis",
            description="Extract information from charts, graphs, diagrams, and images",
            input_schema={
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "URL of the image to analyze"
                    },
                    "image_data": {
                        "type": "string",
                        "description": "Base64 encoded image data"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["general", "chart", "diagram", "text_extraction", "medical"],
                        "default": "general"
                    },
                    "questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific questions about the image"
                    }
                }
            },
            tags=["multimodal", "images", "vision"]
        ),
        AgentSkill(
            id="cross-validate",
            name="Cross Validation",
            description="Verify claims and information across multiple sources",
            input_schema={
                "type": "object",
                "properties": {
                    "claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "source": {"type": "string"}
                            }
                        },
                        "description": "Claims to validate"
                    },
                    "reference_sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional sources to check against"
                    }
                },
                "required": ["claims"]
            },
            tags=["validation", "verification"]
        ),
        AgentSkill(
            id="large-context",
            name="Large Document Processing",
            description="Process and analyze very long documents",
            input_schema={
                "type": "object",
                "properties": {
                    "documents": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "name": {"type": "string"}
                            }
                        },
                        "description": "Documents to process"
                    },
                    "task": {
                        "type": "string",
                        "description": "What to do with the documents"
                    }
                },
                "required": ["documents", "task"]
            },
            tags=["documents", "long-context"]
        ),
        AgentSkill(
            id="video-analysis",
            name="Video Analysis",
            description="Analyze video content and extract information",
            input_schema={
                "type": "object",
                "properties": {
                    "video_url": {
                        "type": "string",
                        "description": "URL of the video"
                    },
                    "timestamps": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Specific timestamps to analyze"
                    },
                    "task": {
                        "type": "string",
                        "description": "What to extract from the video"
                    }
                },
                "required": ["video_url"]
            },
            tags=["multimodal", "video"]
        )
    ],
    metadata={
        "rate_limit": "60 requests/minute",
        "context_window": 128000,
        "model": "gpt-4o",
        "strengths": [
            "Image/video analysis",
            "Large context windows",
            "Cross-referencing",
            "Multimodal understanding"
        ]
    }
)


# =============================================================================
# GEMINI AGENT CARD
# Primary Role: Multimodal Processing & Validation
# Strengths: Image/video analysis, large context windows, cross-referencing
# =============================================================================

# =============================================================================
# OLLAMA AGENT CARD
# Primary Role: Local LLM Fallback
# Strengths: Offline operation, privacy, no API costs
# =============================================================================

OLLAMA_CARD = AgentCard(
    name="Ollama Local Agent",
    description="Local LLM for offline research. Acts as a fallback provider when cloud APIs are unavailable. Runs entirely on local hardware for privacy and cost savings.",
    version="1.0.0",
    url="http://localhost:8000/agents/ollama",
    provider="Ollama (Local)",
    capabilities=AgentCapabilities(
        streaming=True,
        push_notifications=False,
        batch_processing=True,
        multimodal=False,
        long_context=False
    ),
    skills=[
        AgentSkill(
            id="synthesis",
            name="Research Synthesis",
            description="Combine multiple sources into coherent, well-structured analysis (fallback)",
            input_schema={
                "type": "object",
                "properties": {
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "citation": {"type": "string"},
                                "relevance": {"type": "number"}
                            }
                        },
                        "description": "Sources to synthesize"
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["report", "summary", "bullet_points", "narrative"],
                        "default": "report"
                    },
                    "target_length": {
                        "type": "string",
                        "enum": ["brief", "moderate", "comprehensive"],
                        "default": "moderate"
                    }
                },
                "required": ["sources"]
            },
            tags=["synthesis", "writing", "research", "fallback"]
        ),
        AgentSkill(
            id="document-analysis",
            name="Document Analysis",
            description="Analyze and extract insights from documents (fallback)",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Document content to analyze"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["summary", "detailed", "themes", "entities"],
                        "default": "detailed"
                    },
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific areas to focus on"
                    }
                },
                "required": ["content"]
            },
            tags=["analysis", "documents", "fallback"]
        ),
        AgentSkill(
            id="general-query",
            name="General Query",
            description="Handle general queries and questions",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to process"
                    }
                },
                "required": ["query"]
            },
            tags=["general", "query", "fallback"]
        )
    ],
    metadata={
        "rate_limit": "unlimited (local)",
        "context_window": 8192,
        "model": "llama3.1",
        "strengths": [
            "Offline operation",
            "No API costs",
            "Privacy (data stays local)",
            "Fallback availability"
        ],
        "limitations": [
            "Lower quality than cloud models",
            "Limited context window",
            "No multimodal support"
        ]
    }
)


GEMINI_CARD = AgentCard(
    name="Gemini Multimodal Agent",
    description="Multimodal processing and cross-validation specialist. Excels at analyzing images, videos, processing large documents, and validating information across sources.",
    version="1.0.0",
    url="http://localhost:8000/agents/gemini",
    provider="Google DeepMind",
    capabilities=AgentCapabilities(
        streaming=True,
        push_notifications=False,
        batch_processing=True,
        multimodal=True,
        long_context=True
    ),
    skills=[
        AgentSkill(
            id="image-analysis",
            name="Image Analysis",
            description="Extract information from charts, graphs, diagrams, and images",
            input_schema={
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "URL of the image to analyze"
                    },
                    "image_data": {
                        "type": "string",
                        "description": "Base64 encoded image data"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["general", "chart", "diagram", "text_extraction", "medical"],
                        "default": "general"
                    },
                    "questions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific questions about the image"
                    }
                }
            },
            tags=["multimodal", "images", "vision"]
        ),
        AgentSkill(
            id="cross-validate",
            name="Cross Validation",
            description="Verify claims and information across multiple sources",
            input_schema={
                "type": "object",
                "properties": {
                    "claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "source": {"type": "string"}
                            }
                        },
                        "description": "Claims to validate"
                    },
                    "reference_sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional sources to check against"
                    }
                },
                "required": ["claims"]
            },
            tags=["validation", "verification"]
        ),
        AgentSkill(
            id="large-context",
            name="Large Document Processing",
            description="Process and analyze very long documents (up to 1M tokens)",
            input_schema={
                "type": "object",
                "properties": {
                    "documents": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "name": {"type": "string"}
                            }
                        },
                        "description": "Documents to process"
                    },
                    "task": {
                        "type": "string",
                        "description": "What to do with the documents"
                    }
                },
                "required": ["documents", "task"]
            },
            tags=["documents", "long-context"]
        ),
        AgentSkill(
            id="video-analysis",
            name="Video Analysis",
            description="Analyze video content and extract information",
            input_schema={
                "type": "object",
                "properties": {
                    "video_url": {
                        "type": "string",
                        "description": "URL of the video"
                    },
                    "timestamps": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Specific timestamps to analyze"
                    },
                    "task": {
                        "type": "string",
                        "description": "What to extract from the video"
                    }
                },
                "required": ["video_url"]
            },
            tags=["multimodal", "video"]
        )
    ],
    metadata={
        "rate_limit": "60 requests/minute",
        "context_window": 1000000,
        "model": "gemini-1.5-pro",
        "strengths": [
            "Image/video analysis",
            "Large context windows (1M tokens)",
            "Cross-referencing",
            "Multimodal understanding"
        ]
    }
)


# =============================================================================
# ORCHESTRATOR AGENT CARD
# Role: Coordinate multi-agent workflows
# =============================================================================

ORCHESTRATOR_CARD = AgentCard(
    name="Research Orchestrator",
    description="Coordinates multi-agent research workflows, managing task distribution, progress tracking, and result synthesis.",
    version="1.0.0",
    url="http://localhost:8000/agents/orchestrator",
    provider="Research Agent System",
    capabilities=AgentCapabilities(
        streaming=True,
        push_notifications=True,
        batch_processing=True,
        multimodal=False,
        long_context=True
    ),
    skills=[
        AgentSkill(
            id="research-workflow",
            name="Research Workflow",
            description="Execute a full research workflow using multiple agents",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Research query or topic"
                    },
                    "depth": {
                        "type": "string",
                        "enum": ["quick", "standard", "deep"],
                        "default": "standard"
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["report", "summary", "raw"],
                        "default": "report"
                    }
                },
                "required": ["query"]
            },
            tags=["orchestration", "research"]
        ),
        AgentSkill(
            id="task-routing",
            name="Task Routing",
            description="Route tasks to appropriate agents based on requirements",
            input_schema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Task description"
                    },
                    "requirements": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Task requirements/capabilities needed"
                    }
                },
                "required": ["task"]
            },
            tags=["orchestration", "routing"]
        )
    ],
    metadata={
        "role": "coordinator",
        "managed_agents": ["perplexity", "claude", "gemini"]
    }
)


# All agent cards
AGENT_CARDS = {
    "perplexity": PERPLEXITY_CARD,
    "claude": CLAUDE_CARD,
    "openai": OPENAI_CARD,
    "gemini": GEMINI_CARD,
    "ollama": OLLAMA_CARD,
    "orchestrator": ORCHESTRATOR_CARD
}


def get_agent_card(agent_id: str) -> Optional[AgentCard]:
    """Get an agent card by ID."""
    return AGENT_CARDS.get(agent_id)


def list_agent_cards() -> dict[str, AgentCard]:
    """Get all agent cards."""
    return AGENT_CARDS.copy()
