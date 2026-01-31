"""Main FastAPI Application for the Multi-Agent Research System.

This is the entry point for the A2A protocol-based research agent system,
providing REST and streaming endpoints for:
- Agent discovery (agent cards)
- Task execution
- Research workflows
- Real-time status updates
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.config import get_config
from src.a2a.protocol import A2AProtocol, AgentCard
from src.a2a.messages import A2AMessage, TaskRequest, TaskResponse
from src.a2a.task_manager import Task, TaskManager
from src.agents.base import AgentRegistry, ProviderPriority
from src.agents.cards import AGENT_CARDS, get_agent_card
from src.agents.perplexity import PerplexityAgent
from src.agents.claude import ClaudeAgent
from src.agents.openai import OpenAIAgent
from src.agents.ollama import OllamaAgent
from src.agents.orchestrator import OrchestratorAgent
from src.workflows.research import ResearchWorkflow, ResearchConfig, ResearchDepth, OutputFormat
from src.admin import AdminAuth, SettingsManager, admin_router
from src.admin.routes import init_admin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global instances
task_manager = TaskManager()
agent_registry = AgentRegistry()
research_workflow: Optional[ResearchWorkflow] = None
settings_manager: Optional[SettingsManager] = None
admin_auth: Optional[AdminAuth] = None


# =============================================================================
# Request/Response Models
# =============================================================================

class ResearchRequest(BaseModel):
    """Request to execute a research workflow."""
    query: str = Field(..., description="Research query or topic")
    depth: str = Field(default="standard", description="Research depth: quick, standard, deep")
    output_format: str = Field(default="report", description="Output format: report, summary, bullets, raw")
    stream: bool = Field(default=False, description="Enable streaming responses")


class TaskSendRequest(BaseModel):
    """A2A tasks/send request."""
    id: Optional[str] = Field(default=None, description="Task ID")
    message: dict = Field(..., description="Message content")
    skill_id: Optional[str] = Field(default=None, alias="skillId")
    metadata: dict = Field(default_factory=dict)


class A2ARequest(BaseModel):
    """JSON-RPC 2.0 request wrapper."""
    jsonrpc: str = "2.0"
    method: str
    params: dict = Field(default_factory=dict)
    id: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    agents: dict[str, Any]
    version: str = "1.0.0"


# =============================================================================
# Application Lifecycle
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info("Starting Multi-Agent Research System...")
    config = get_config()

    # Initialize settings manager and admin auth
    global settings_manager, admin_auth
    settings_manager = SettingsManager()
    settings = settings_manager.load()

    # Initialize admin auth with stored password hash
    admin_auth = AdminAuth(
        password_hash=settings.admin_password_hash,
        session_timeout_hours=settings.session_timeout_hours
    )

    # Initialize admin module
    init_admin(
        auth=admin_auth,
        settings=settings_manager,
        get_registry_callback=lambda: agent_registry
    )
    logger.info("Admin module initialized")

    # Initialize agents based on available API keys
    if config.api.perplexity_api_key:
        perplexity = PerplexityAgent(api_key=config.api.perplexity_api_key)
        try:
            await perplexity.initialize()
            agent_registry.register(perplexity)
            logger.info("✓ Perplexity agent initialized")
        except Exception as e:
            logger.warning(f"✗ Perplexity agent failed to initialize: {e}")

    if config.api.anthropic_api_key:
        claude = ClaudeAgent(
            api_key=config.api.anthropic_api_key,
            model=config.agent.claude_model
        )
        try:
            await claude.initialize()
            agent_registry.register(claude)
            logger.info("✓ Claude agent initialized")
        except Exception as e:
            logger.warning(f"✗ Claude agent failed to initialize: {e}")

    if config.api.openai_api_key:
        openai_agent = OpenAIAgent(
            api_key=config.api.openai_api_key,
            model=config.agent.openai_model
        )
        try:
            await openai_agent.initialize()
            agent_registry.register(openai_agent)
            logger.info("✓ OpenAI agent initialized")
        except Exception as e:
            logger.warning(f"✗ OpenAI agent failed to initialize: {e}")

    # Initialize Ollama agent if enabled in settings
    ollama_config = settings_manager.get_ollama_config()
    if ollama_config.enabled:
        ollama = OllamaAgent(
            base_url=ollama_config.base_url,
            model=ollama_config.model
        )
        try:
            await ollama.initialize()
            agent_registry.register(ollama)
            logger.info(f"✓ Ollama agent initialized (model: {ollama_config.model})")
        except Exception as e:
            logger.warning(f"✗ Ollama agent failed to initialize: {e}")
    else:
        logger.info("○ Ollama agent disabled (enable in admin panel)")

    # Apply provider priorities from settings
    priorities_config = settings_manager.get_priorities()
    priorities = {}
    for skill_id, config_data in priorities_config.items():
        priorities[skill_id] = ProviderPriority(
            skill_id=skill_id,
            primary=config_data.get("primary", "claude"),
            fallbacks=config_data.get("fallbacks", [])
        )
    agent_registry.set_priorities(priorities)
    logger.info(f"Applied provider priorities for {len(priorities)} skills")

    # Initialize orchestrator
    orchestrator = OrchestratorAgent(agent_registry, task_manager)
    await orchestrator.initialize()
    agent_registry.register(orchestrator)
    logger.info("✓ Orchestrator agent initialized")

    # Initialize research workflow
    global research_workflow
    research_workflow = ResearchWorkflow(agent_registry, task_manager)
    await research_workflow.initialize()

    logger.info(f"System ready with {len(agent_registry)} agents")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await agent_registry.shutdown_all()
    logger.info("Shutdown complete")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Multi-Agent Research System",
    description="A2A Protocol-based research system using Perplexity, Claude, and Gemini",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount admin router
app.include_router(admin_router)


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check system health and agent status."""
    agents_health = await agent_registry.health_check_all()
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        agents=agents_health
    )


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the research UI as homepage."""
    try:
        with open("static/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>UI not available</h1><p>Static files not found.</p>",
            status_code=404
        )


@app.get("/api/info")
async def api_info():
    """API endpoint with system info."""
    config = get_config()
    return {
        "name": "Multi-Agent Research System",
        "version": "1.0.0",
        "description": "A2A Protocol research system with Perplexity, Claude, and Gemini",
        "agents": {
            "registered": [a.agent_id for a in agent_registry.list_agents()],
            "available": config.api.get_available_agents()
        },
        "endpoints": {
            "health": "/health",
            "agents": "/agents",
            "research": "/research",
            "a2a": "/a2a",
            "api_info": "/api/info"
        }
    }


# =============================================================================
# Agent Discovery Endpoints (A2A Protocol)
# =============================================================================

@app.get("/agents")
async def list_agents():
    """List all registered agents and their cards."""
    agents = []
    for agent in agent_registry.list_agents():
        agents.append({
            "id": agent.agent_id,
            "name": agent.name,
            "initialized": agent._initialized,
            "skills": [s.id for s in agent.card.skills]
        })
    return {"agents": agents}


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details and card."""
    agent = agent_registry.get(agent_id)
    if not agent:
        # Try to get card from predefined cards
        card = get_agent_card(agent_id)
        if card:
            return {"card": card.model_dump(by_alias=True), "registered": False}
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return {
        "card": agent.card.model_dump(by_alias=True),
        "registered": True,
        "initialized": agent._initialized
    }


@app.get("/agents/{agent_id}/card")
async def get_agent_card_endpoint(agent_id: str):
    """Get agent card (A2A Protocol agent/card method)."""
    agent = agent_registry.get(agent_id)
    if agent:
        return agent.card.model_dump(by_alias=True)

    card = get_agent_card(agent_id)
    if card:
        return card.model_dump(by_alias=True)

    raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")


# =============================================================================
# Research Workflow Endpoints
# =============================================================================

@app.post("/research")
async def execute_research(request: ResearchRequest):
    """Execute a research workflow."""
    if not research_workflow:
        raise HTTPException(status_code=503, detail="Research workflow not initialized")

    config = ResearchConfig(
        depth=ResearchDepth(request.depth),
        output_format=OutputFormat(request.output_format)
    )

    if request.stream:
        return EventSourceResponse(
            stream_research(request.query, config),
            media_type="text/event-stream"
        )

    result = await research_workflow.execute(request.query, config)

    return {
        "success": result.success,
        "query": result.query,
        "report": result.report,
        "sources_count": len(result.sources),
        "duration_seconds": result.duration_seconds,
        "error": result.error
    }


async def stream_research(query: str, config: ResearchConfig):
    """Generator for streaming research progress."""
    async for response in research_workflow.execute_streaming(query, config):
        data = {
            "id": response.id,
            "status": response.status,
            "progress": response.progress
        }
        if response.message:
            data["message"] = response.message.get_text()
        if response.error:
            data["error"] = response.error

        yield {
            "event": "progress",
            "data": str(data)
        }


@app.get("/research/{workflow_id}")
async def get_research_status(workflow_id: str):
    """Get status of a research workflow."""
    if not research_workflow:
        raise HTTPException(status_code=503, detail="Research workflow not initialized")

    status = research_workflow.get_status(workflow_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_id}")

    return status


# =============================================================================
# Export Endpoints (PDF/DOCX Download)
# =============================================================================

class ExportRequest(BaseModel):
    """Request to export research results."""
    query: str = Field(..., description="The research query")
    report: str = Field(..., description="The report content (markdown)")
    sources_count: Optional[int] = Field(default=None, description="Number of sources")
    duration_seconds: Optional[float] = Field(default=None, description="Research duration")


@app.post("/export/pdf")
async def export_pdf(request: ExportRequest):
    """Export research results as PDF."""
    from src.export import export_to_pdf
    from fastapi.responses import Response

    try:
        pdf_bytes = export_to_pdf(
            query=request.query,
            report=request.report,
            sources_count=request.sources_count,
            duration_seconds=request.duration_seconds
        )

        filename = f"research_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        logger.error(f"PDF export failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)}")


@app.post("/export/docx")
async def export_docx(request: ExportRequest):
    """Export research results as DOCX."""
    from src.export import export_to_docx
    from fastapi.responses import Response

    try:
        docx_bytes = export_to_docx(
            query=request.query,
            report=request.report,
            sources_count=request.sources_count,
            duration_seconds=request.duration_seconds
        )

        filename = f"research_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"

        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        logger.error(f"DOCX export failed: {e}")
        raise HTTPException(status_code=500, detail=f"DOCX export failed: {str(e)}")


# =============================================================================
# A2A Protocol Endpoints (JSON-RPC)
# =============================================================================

@app.post("/a2a")
async def a2a_endpoint(request: A2ARequest):
    """A2A Protocol JSON-RPC endpoint."""
    # Validate request
    valid, error = A2AProtocol.validate_request(request.model_dump())
    if not valid:
        return A2AProtocol.create_error(request.id, A2AProtocol.ERROR_INVALID_REQUEST, error)

    method = request.method
    params = request.params

    try:
        if method == A2AProtocol.METHOD_TASK_SEND:
            return await handle_task_send(request.id, params)
        elif method == A2AProtocol.METHOD_TASK_GET:
            return await handle_task_get(request.id, params)
        elif method == A2AProtocol.METHOD_TASK_CANCEL:
            return await handle_task_cancel(request.id, params)
        elif method == A2AProtocol.METHOD_AGENT_CARD:
            return await handle_agent_card(request.id, params)
        else:
            return A2AProtocol.create_error(
                request.id,
                A2AProtocol.ERROR_METHOD_NOT_FOUND,
                f"Unknown method: {method}"
            )
    except Exception as e:
        logger.error(f"A2A request failed: {e}")
        return A2AProtocol.create_error(request.id, A2AProtocol.ERROR_INTERNAL, str(e))


async def handle_task_send(request_id: str, params: dict) -> dict:
    """Handle tasks/send method."""
    task_id = params.get("id", str(uuid.uuid4()))
    message_data = params.get("message", {})
    skill_id = params.get("skillId")
    metadata = params.get("metadata", {})
    agent_id = params.get("agentId", "orchestrator")

    # Get target agent
    agent = agent_registry.get(agent_id)
    if not agent:
        return A2AProtocol.create_error(
            request_id,
            A2AProtocol.ERROR_TASK_NOT_FOUND,
            f"Agent not found: {agent_id}"
        )

    # Create message
    message_parts = message_data.get("parts", [])
    text_content = ""
    for part in message_parts:
        if part.get("type") == "text":
            text_content += part.get("text", "")

    if not text_content and isinstance(message_data, str):
        text_content = message_data

    # Create task
    task_request = TaskRequest(
        id=task_id,
        message=A2AMessage.user_text(text_content),
        skill_id=skill_id,
        metadata=metadata
    )

    task = await task_manager.create_task(task_request, agent_id=agent_id)

    # Execute task
    response = await agent.execute(task)

    return A2AProtocol.create_response(request_id, {
        "id": task.id,
        "status": response.status,
        "message": {
            "role": "agent",
            "parts": [{"type": "text", "text": response.message.get_text() if response.message else ""}]
        },
        "artifacts": [
            {
                "name": a.name,
                "type": a.type,
                "parts": [{"type": "text", "text": str(p)} for p in a.parts]
            }
            for a in response.artifacts
        ]
    })


async def handle_task_get(request_id: str, params: dict) -> dict:
    """Handle tasks/get method."""
    task_id = params.get("id")
    if not task_id:
        return A2AProtocol.create_error(
            request_id,
            A2AProtocol.ERROR_INVALID_PARAMS,
            "Missing task id"
        )

    task = await task_manager.get_task(task_id)
    if not task:
        return A2AProtocol.create_error(
            request_id,
            A2AProtocol.ERROR_TASK_NOT_FOUND,
            f"Task not found: {task_id}"
        )

    return A2AProtocol.create_response(request_id, {
        "id": task.id,
        "status": task.state.status.value,
        "progress": task.state.progress,
        "message": task.state.message
    })


async def handle_task_cancel(request_id: str, params: dict) -> dict:
    """Handle tasks/cancel method."""
    task_id = params.get("id")
    if not task_id:
        return A2AProtocol.create_error(
            request_id,
            A2AProtocol.ERROR_INVALID_PARAMS,
            "Missing task id"
        )

    task = await task_manager.cancel_task(task_id)
    if not task:
        return A2AProtocol.create_error(
            request_id,
            A2AProtocol.ERROR_TASK_NOT_FOUND,
            f"Task not found: {task_id}"
        )

    return A2AProtocol.create_response(request_id, {
        "id": task.id,
        "status": "cancelled"
    })


async def handle_agent_card(request_id: str, params: dict) -> dict:
    """Handle agent/card method."""
    agent_id = params.get("agentId", "orchestrator")
    agent = agent_registry.get(agent_id)

    if agent:
        return A2AProtocol.create_response(
            request_id,
            agent.card.model_dump(by_alias=True)
        )

    card = get_agent_card(agent_id)
    if card:
        return A2AProtocol.create_response(
            request_id,
            card.model_dump(by_alias=True)
        )

    return A2AProtocol.create_error(
        request_id,
        A2AProtocol.ERROR_TASK_NOT_FOUND,
        f"Agent not found: {agent_id}"
    )


# =============================================================================
# Direct Agent Endpoints
# =============================================================================

@app.post("/agents/{agent_id}/execute")
async def execute_agent_task(agent_id: str, request: TaskSendRequest):
    """Execute a task directly on a specific agent."""
    agent = agent_registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    if not agent._initialized:
        raise HTTPException(status_code=503, detail=f"Agent not initialized: {agent_id}")

    # Extract text from message
    text_content = ""
    parts = request.message.get("parts", [])
    for part in parts:
        if part.get("type") == "text":
            text_content += part.get("text", "")

    if not text_content:
        text_content = str(request.message)

    task = Task(
        id=request.id or str(uuid.uuid4()),
        request=TaskRequest(
            message=A2AMessage.user_text(text_content),
            skill_id=request.skill_id,
            metadata=request.metadata
        )
    )

    response = await agent.execute(task)

    return {
        "id": task.id,
        "status": response.status,
        "message": response.message.get_text() if response.message else None,
        "error": response.error,
        "artifacts": [
            {"name": a.name, "type": a.type}
            for a in response.artifacts
        ]
    }


# =============================================================================
# Static Files & UI
# =============================================================================

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    logger.warning("Static files directory not found, UI may not be available")


@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    """Serve the demo UI."""
    try:
        with open("static/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>UI not available</h1><p>Static files not found.</p>",
            status_code=404
        )


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """Run the server."""
    import uvicorn
    config = get_config()
    uvicorn.run(
        "src.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=config.server.debug
    )


if __name__ == "__main__":
    main()
