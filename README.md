# Multi-Agent Research System

A sophisticated research assistant powered by the A2A (Agent-to-Agent) Protocol, combining the strengths of Perplexity, Claude, and Gemini AI agents.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER QUERY                                    │
│         "Research the impact of AI on healthcare in 2024"       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR AGENT                             │
│    • Parses query intent                                        │
│    • Creates research plan                                      │
│    • Assigns subtasks via A2A                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   PERPLEXITY     │ │     CLAUDE       │ │     GEMINI       │
│                  │ │                  │ │                  │
│ Task: Discovery  │ │ Task: Analysis   │ │ Task: Validation │
│                  │ │                  │ │                  │
│ • Search web     │ │ • Analyze docs   │ │ • Cross-check    │
│ • Find sources   │ │ • Identify gaps  │ │ • Process images │
│ • Get citations  │ │ • Synthesize     │ │ • Verify claims  │
└──────────────────┘ └──────────────────┘ └──────────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FINAL SYNTHESIS                               │
│              (Claude assembles final report)                    │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Roles & Capabilities

| Agent | Primary Role | Strengths |
|-------|--------------|-----------|
| **Perplexity** | Web Research & Source Discovery | Real-time web search, citation gathering, fact verification |
| **Claude** | Analysis & Synthesis | Deep reasoning, nuanced writing, document analysis, structured outputs |
| **Gemini** | Multimodal Processing & Validation | Image/video analysis, large context windows, cross-referencing |

## Features

- **A2A Protocol**: Standardized JSON-RPC based communication between agents
- **Agent Cards**: Discoverable capability manifests for each agent
- **Parallel Execution**: Efficient task distribution and parallel processing
- **Streaming Progress**: Real-time updates during research workflows
- **Web UI**: Interactive demo interface for research queries
- **RESTful API**: Complete API for programmatic access

## Installation

### Prerequisites

- Python 3.10+
- API keys for at least one provider:
  - Anthropic API key (for Claude)
  - Google API key (for Gemini)
  - Perplexity API key (for Perplexity)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/tedrubin80/researchagent.git
cd researchagent
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

5. Run the server:
```bash
python -m src.main
```

6. Open the web UI at http://localhost:8000/ui

## Configuration

Edit `.env` file with your settings:

```env
# API Keys
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
PERPLEXITY_API_KEY=your_perplexity_key

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Agent Settings
DEFAULT_ORCHESTRATOR=claude
MAX_PARALLEL_TASKS=3
TASK_TIMEOUT_SECONDS=120
```

## API Reference

### Research Endpoint

Execute a research workflow:

```bash
POST /research
Content-Type: application/json

{
    "query": "Impact of AI on healthcare in 2024",
    "depth": "standard",  // quick, standard, deep
    "output_format": "report",  // report, summary, bullets
    "stream": false
}
```

### A2A Protocol Endpoint

JSON-RPC endpoint for A2A communication:

```bash
POST /a2a
Content-Type: application/json

{
    "jsonrpc": "2.0",
    "method": "tasks/send",
    "params": {
        "id": "task-001",
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": "Search for AI healthcare developments"}]
        },
        "skillId": "web-search",
        "agentId": "perplexity"
    },
    "id": "req-001"
}
```

### Agent Endpoints

- `GET /agents` - List all agents
- `GET /agents/{id}` - Get agent details
- `GET /agents/{id}/card` - Get agent card (A2A protocol)
- `POST /agents/{id}/execute` - Execute task on specific agent

### Health Check

```bash
GET /health
```

## Workflow Phases

1. **Planning**: Parse query, create research plan
2. **Discovery**: Web search via Perplexity
3. **Analysis**: Deep analysis via Claude
4. **Validation**: Cross-validation via Gemini
5. **Synthesis**: Final report assembly via Claude

## A2A Message Flow Example

```json
// 1. Orchestrator → Perplexity (Discovery)
{
    "jsonrpc": "2.0",
    "method": "tasks/send",
    "params": {
        "id": "task-001",
        "message": {
            "role": "user",
            "parts": [{
                "type": "text",
                "text": "Search for AI healthcare FDA approvals 2024"
            }]
        },
        "skillId": "web-search"
    }
}

// 2. Perplexity → Orchestrator (Results)
{
    "jsonrpc": "2.0",
    "result": {
        "id": "task-001",
        "status": "completed",
        "artifacts": [{
            "type": "application/json",
            "parts": [{"type": "data", "data": {"sources": [...]}}]
        }]
    }
}
```

## Project Structure

```
researchagent/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── a2a/
│   │   ├── protocol.py      # A2A protocol types
│   │   ├── messages.py      # Message structures
│   │   └── task_manager.py  # Task lifecycle management
│   ├── agents/
│   │   ├── base.py          # Base agent interface
│   │   ├── cards.py         # Agent card definitions
│   │   ├── perplexity.py    # Perplexity agent
│   │   ├── claude.py        # Claude agent
│   │   ├── gemini.py        # Gemini agent
│   │   └── orchestrator.py  # Workflow orchestrator
│   └── workflows/
│       └── research.py      # Research workflow
├── static/
│   ├── index.html           # Web UI
│   ├── style.css
│   └── app.js
├── tests/
│   └── test_a2a.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/
ruff check src/
```

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- [A2A Protocol](https://github.com/google/A2A) - Agent-to-Agent communication protocol
- [Anthropic](https://anthropic.com) - Claude AI
- [Google](https://deepmind.google) - Gemini AI
- [Perplexity](https://perplexity.ai) - Perplexity AI
