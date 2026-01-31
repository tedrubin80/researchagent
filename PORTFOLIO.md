# Multi-Agent Research System

A production-ready research platform that orchestrates multiple AI agents (Claude, OpenAI GPT-4, Perplexity) using the A2A (Agent-to-Agent) protocol to deliver comprehensive, cited research reports.

## Overview

This system demonstrates modern AI orchestration patterns by coordinating specialized agents, each with distinct capabilities:

- **Perplexity** - Real-time web search and source discovery
- **Claude** - Deep analysis, reasoning, and synthesis
- **OpenAI GPT-4** - Multimodal processing and cross-validation
- **Orchestrator** - Workflow coordination and task routing

## Key Features

- **Multi-Agent Orchestration**: Implements the A2A protocol for standardized agent communication
- **Real-Time Streaming**: Server-Sent Events (SSE) for live progress updates
- **Flexible Output Formats**: Full reports, summaries, or bullet points
- **Export Capabilities**: Download results as PDF or DOCX
- **Admin Panel**: Configure agents, set provider priorities, manage API keys
- **Fallback Support**: Local Ollama integration for offline operation

## Technical Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, Python 3.12, asyncio |
| AI Providers | Anthropic Claude, OpenAI GPT-4, Perplexity |
| Protocol | A2A (Agent-to-Agent) with JSON-RPC 2.0 |
| Frontend | Vanilla JS, CSS3, marked.js for Markdown |
| Export | fpdf2 (PDF), python-docx (DOCX) |
| Streaming | SSE via sse-starlette |

## Architecture Highlights

```
┌─────────────────────────────────────────────────────────┐
│                    Research UI                          │
│              (Query Input, Progress, Results)           │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                   FastAPI Backend                        │
│         /research  /export  /api/info  /admin           │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                Research Orchestrator                     │
│            (Task Distribution & Synthesis)               │
└───────┬─────────────────┼─────────────────┬─────────────┘
        │                 │                 │
   ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
   │Perplexity│       │ Claude  │       │ OpenAI  │
   │(Search)  │       │(Analysis)│      │(Validate)│
   └──────────┘       └──────────┘       └──────────┘
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Research interface (HTML) |
| `/api/info` | GET | System info and available agents |
| `/research` | POST | Execute research workflow |
| `/export/pdf` | POST | Download results as PDF |
| `/export/docx` | POST | Download results as DOCX |
| `/agents` | GET | List registered agents |
| `/health` | GET | System health check |
| `/a2a` | POST | A2A protocol JSON-RPC endpoint |

## Live Demo

Visit the application at your deployment URL to:
1. Enter a research query
2. Watch agents collaborate in real-time
3. Receive a comprehensive report with citations
4. Export results in your preferred format

## Source Code

[GitHub Repository Link]

---

*Built with FastAPI, Python, and modern AI orchestration patterns.*
