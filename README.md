# Multi-Agent Research System

A production-ready research platform that orchestrates multiple AI agents — **Claude**, **GPT-4**, and **Perplexity** — using the [A2A (Agent-to-Agent) Protocol](https://github.com/google/A2A) to deliver comprehensive, cited research reports in real time.

**[Live Demo](https://feedyourresearch.online)** | **[API Docs](https://feedyourresearch.online/docs)**

---

## How It Works

A user submits a research query. The **Orchestrator** breaks it into sub-tasks and dispatches them to specialized agents via the A2A protocol. Each agent does what it's best at, and the results are assembled into a structured report.

```
                        User Query
                            │
                            ▼
                    ┌───────────────┐
                    │  Orchestrator │
                    │  (Planning &  │
                    │   Routing)    │
                    └──────┬────────┘
               ┌───────────┼───────────┐
               ▼           ▼           ▼
        ┌────────────┐ ┌────────┐ ┌──────────┐
        │ Perplexity │ │ Claude │ │  OpenAI  │
        │ Web Search │ │Analysis│ │Validation│
        └─────┬──────┘ └───┬────┘ └────┬─────┘
              └─────────────┼──────────┘
                            ▼
                     Final Report
                 (PDF / DOCX / Markdown)
```

### Workflow Phases

| Phase | Agent | What Happens |
|-------|-------|--------------|
| **1. Planning** | Orchestrator | Parses query, identifies sub-topics, creates research plan |
| **2. Discovery** | Perplexity | Searches the web for relevant sources and citations |
| **3. Analysis** | Claude | Deep analysis, reasoning, and structured synthesis |
| **4. Validation** | OpenAI GPT-4 | Cross-validates claims, checks consistency |
| **5. Synthesis** | Claude | Assembles final report with sources and follow-up questions |

---

## Features

- **A2A Protocol** — JSON-RPC 2.0 based agent-to-agent communication with discoverable agent cards and typed skill schemas
- **Real-Time Streaming** — Server-Sent Events deliver live progress as agents collaborate
- **Multi-Format Export** — Download results as PDF, DOCX, Markdown, HTML, or JSON
- **Provider Fallbacks** — Configurable priority chains with automatic failover per skill
- **Local Ollama Support** — Offline operation using local models as fallback
- **Admin Panel** — Web UI to configure agents, set provider priorities, and manage settings
- **Showcase Mode** — Static demo page that works without API keys

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12, FastAPI, asyncio, Pydantic |
| **AI Providers** | Anthropic Claude, OpenAI GPT-4, Perplexity, Ollama |
| **Protocol** | A2A (Agent-to-Agent) with JSON-RPC 2.0 |
| **Streaming** | Server-Sent Events via sse-starlette |
| **Export** | fpdf2 (PDF), python-docx (DOCX) |
| **Frontend** | Vanilla JS, CSS3 (dark/light themes), marked.js |
| **Server** | Uvicorn, Nginx, Let's Encrypt |

---

## Getting Started

### Prerequisites

- Python 3.10+
- At least one API key (or Ollama for local-only operation)

### Installation

```bash
git clone https://github.com/tedrubin80/researchagent.git
cd researchagent

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your API keys
```

The system starts with whatever keys are available. Missing providers are skipped gracefully.

### Run

```bash
python -m src.main
```

Open **http://localhost:8000** for the showcase page, or use the API directly.

---

## API Reference

### Research

```bash
# Execute a research workflow
POST /research
Content-Type: application/json

{
    "query": "Impact of AI on healthcare in 2024",
    "depth": "standard",        # quick | standard | deep
    "output_format": "report",  # report | summary | bullets
    "stream": true              # Enable SSE streaming
}
```

### A2A Protocol (JSON-RPC)

```bash
# Send a task to a specific agent
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

### All Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Showcase page (HTML) |
| `/research` | POST | Execute research workflow |
| `/a2a` | POST | A2A Protocol JSON-RPC endpoint |
| `/agents` | GET | List registered agents |
| `/agents/{id}` | GET | Agent details |
| `/agents/{id}/card` | GET | Agent card (A2A discovery) |
| `/agents/{id}/execute` | POST | Execute task on specific agent |
| `/export/pdf` | POST | Download report as PDF |
| `/export/docx` | POST | Download report as DOCX |
| `/health` | GET | System health check |
| `/api/info` | GET | System information |
| `/admin` | GET | Admin panel |

---

## Project Structure

```
researchagent/
├── src/
│   ├── main.py                 # FastAPI app, endpoints, lifespan
│   ├── config.py               # Environment-based configuration
│   ├── export.py               # PDF and DOCX generation
│   ├── a2a/
│   │   ├── protocol.py         # A2A types: AgentCard, TaskStatus, AgentSkill
│   │   ├── messages.py         # A2AMessage, TaskRequest, TaskResponse, Artifact
│   │   └── task_manager.py     # Task lifecycle and state management
│   ├── agents/
│   │   ├── base.py             # BaseAgent ABC, AgentRegistry, ProviderPriority
│   │   ├── cards.py            # Predefined agent card definitions
│   │   ├── claude.py           # Anthropic Claude agent
│   │   ├── openai.py           # OpenAI GPT-4 agent
│   │   ├── perplexity.py       # Perplexity search agent
│   │   ├── ollama.py           # Local Ollama fallback agent
│   │   └── orchestrator.py     # Workflow orchestrator (task routing)
│   ├── workflows/
│   │   └── research.py         # ResearchWorkflow, ResearchConfig, ResearchResult
│   └── admin/
│       ├── auth.py             # Admin authentication
│       ├── routes.py           # Admin API endpoints
│       └── settings.py         # Runtime settings management
├── static/
│   ├── index.html              # Showcase page
│   ├── style.css               # Styles (dark/light themes)
│   ├── app.js                  # Simulated demo + theme toggle
│   └── admin/                  # Admin panel UI
├── tests/
│   └── test_a2a.py             # Protocol tests
├── docs/
│   └── technical_decisions.md  # Architecture decisions and trade-offs
├── .env.example                # Environment template
├── requirements.txt
├── pyproject.toml
└── LICENSE                     # MIT
```

---

## Architecture Decisions

Key design choices documented in [`docs/technical_decisions.md`](docs/technical_decisions.md):

- **OpenAI over Gemini** — Clearer pricing and more stable API
- **SSE over WebSockets** — Research progress is unidirectional; SSE is simpler and firewall-friendly
- **fpdf2 over WeasyPrint** — Pure Python, no system dependencies
- **Vanilla JS over React** — Single page, no build step needed
- **Graceful degradation** — Missing providers are skipped; Ollama provides local fallback
- **A2A Protocol** — Standardized agent interop with JSON-RPC 2.0 and skill-based routing

---

## Provider Priority System

Each skill has a configurable fallback chain:

```python
# Example: synthesis skill tries Claude first, falls back to Ollama
ProviderPriority(
    skill_id="synthesis",
    primary="claude",
    fallbacks=["ollama"]
)

# Web search has no fallback (requires internet)
ProviderPriority(
    skill_id="web-search",
    primary="perplexity",
    fallbacks=[]
)
```

Priorities are configurable via the admin panel or `data/settings.json`.

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Format code
black src/
ruff check src/
```

---

## License

[MIT](LICENSE)

---

## Acknowledgments

- [A2A Protocol](https://github.com/google/A2A) — Agent-to-Agent communication specification
- [Anthropic](https://anthropic.com) — Claude AI
- [OpenAI](https://openai.com) — GPT-4
- [Perplexity](https://perplexity.ai) — Perplexity AI
- [Ollama](https://ollama.ai) — Local model runtime
