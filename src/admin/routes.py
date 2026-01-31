"""FastAPI routes for admin panel."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, Depends, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .auth import AdminAuth
from .settings import SettingsManager, OllamaSettings

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/admin", tags=["admin"])

# Global instances (set by main.py on startup)
_auth: Optional[AdminAuth] = None
_settings: Optional[SettingsManager] = None
_get_agent_registry = None  # Callback to get agent registry


def init_admin(
    auth: AdminAuth,
    settings: SettingsManager,
    get_registry_callback=None
) -> None:
    """Initialize admin module with auth and settings instances.

    Args:
        auth: AdminAuth instance
        settings: SettingsManager instance
        get_registry_callback: Callback to get agent registry for status
    """
    global _auth, _settings, _get_agent_registry
    _auth = auth
    _settings = settings
    _get_agent_registry = get_registry_callback
    logger.info("Admin module initialized")


# =============================================================================
# Request/Response Models
# =============================================================================

class LoginRequest(BaseModel):
    """Login request body."""
    password: str


class LoginResponse(BaseModel):
    """Login response."""
    success: bool
    token: Optional[str] = None
    message: str
    requires_password_change: bool = False


class ChangePasswordRequest(BaseModel):
    """Change password request body."""
    current_password: str = Field(..., alias="currentPassword")
    new_password: str = Field(..., alias="newPassword")

    class Config:
        populate_by_name = True


class PriorityUpdateRequest(BaseModel):
    """Priority update request body."""
    priorities: dict[str, dict[str, Any]]


class OllamaConfigRequest(BaseModel):
    """Ollama configuration request body."""
    enabled: bool
    base_url: str = Field(..., alias="baseUrl")
    model: str

    class Config:
        populate_by_name = True


class SessionTimeoutRequest(BaseModel):
    """Session timeout update request."""
    timeout_hours: int = Field(..., alias="timeoutHours", ge=1)

    class Config:
        populate_by_name = True


# =============================================================================
# Authentication Dependency
# =============================================================================

async def require_auth(authorization: Optional[str] = Header(None)) -> str:
    """Dependency to require valid authentication.

    Returns the session token if valid.
    """
    if not _auth:
        raise HTTPException(status_code=500, detail="Admin not initialized")

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    token = parts[1]
    if not _auth.validate_session(token):
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return token


# =============================================================================
# Authentication Endpoints
# =============================================================================

@router.post("/api/login", response_model=LoginResponse)
async def login(request: LoginRequest, req: Request):
    """Authenticate and create session."""
    if not _auth:
        raise HTTPException(status_code=500, detail="Admin not initialized")

    client_ip = req.client.host if req.client else None
    session = _auth.login(request.password, ip_address=client_ip)

    if not session:
        return LoginResponse(
            success=False,
            token=None,
            message="Invalid password"
        )

    return LoginResponse(
        success=True,
        token=session.token,
        message="Login successful",
        requires_password_change=_auth.is_default_password
    )


@router.post("/api/logout")
async def logout(token: str = Depends(require_auth)):
    """End session."""
    _auth.logout(token)
    return {"success": True, "message": "Logged out"}


@router.get("/api/session")
async def validate_session(token: str = Depends(require_auth)):
    """Validate current session."""
    session = _auth.get_session(token)
    return {
        "valid": True,
        "expires_at": session.expires_at.isoformat() if session else None,
        "requires_password_change": _auth.is_default_password
    }


# =============================================================================
# Settings Endpoints
# =============================================================================

@router.get("/api/settings")
async def get_settings(token: str = Depends(require_auth)):
    """Get all settings."""
    if not _settings:
        raise HTTPException(status_code=500, detail="Settings not initialized")

    return _settings.export_settings()


@router.put("/api/settings/priorities")
async def update_priorities(
    request: PriorityUpdateRequest,
    token: str = Depends(require_auth)
):
    """Update provider priorities."""
    if not _settings:
        raise HTTPException(status_code=500, detail="Settings not initialized")

    if _settings.set_priorities(request.priorities):
        return {"success": True, "message": "Priorities updated"}

    raise HTTPException(status_code=500, detail="Failed to save priorities")


@router.put("/api/settings/ollama")
async def update_ollama_config(
    request: OllamaConfigRequest,
    token: str = Depends(require_auth)
):
    """Update Ollama configuration."""
    if not _settings:
        raise HTTPException(status_code=500, detail="Settings not initialized")

    config = OllamaSettings(
        enabled=request.enabled,
        base_url=request.base_url,
        model=request.model
    )

    if _settings.set_ollama_config(config):
        return {
            "success": True,
            "message": "Ollama configuration updated",
            "note": "Restart the application to apply changes"
        }

    raise HTTPException(status_code=500, detail="Failed to save Ollama configuration")


@router.put("/api/settings/password")
async def change_password(
    request: ChangePasswordRequest,
    token: str = Depends(require_auth)
):
    """Change admin password."""
    if not _auth or not _settings:
        raise HTTPException(status_code=500, detail="Admin not initialized")

    try:
        if not _auth.change_password(request.current_password, request.new_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        # Save new password hash
        _settings.set_password_hash(_auth.get_password_hash())

        return {"success": True, "message": "Password changed successfully"}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/api/settings/session-timeout")
async def update_session_timeout(
    request: SessionTimeoutRequest,
    token: str = Depends(require_auth)
):
    """Update session timeout."""
    if not _auth or not _settings:
        raise HTTPException(status_code=500, detail="Admin not initialized")

    try:
        _auth.session_timeout_hours = request.timeout_hours
        _settings.set_session_timeout(request.timeout_hours)
        return {
            "success": True,
            "message": f"Session timeout set to {request.timeout_hours} hours"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Status Endpoints
# =============================================================================

@router.get("/api/status")
async def get_system_status(token: str = Depends(require_auth)):
    """Get system and agent status."""
    status = {
        "admin": {
            "active_sessions": _auth.get_active_sessions_count() if _auth else 0,
            "default_password_in_use": _auth.is_default_password if _auth else True
        },
        "settings": {
            "loaded": _settings is not None,
            "path": str(_settings.path) if _settings else None
        },
        "agents": {}
    }

    # Get agent status if registry is available
    if _get_agent_registry:
        try:
            registry = _get_agent_registry()
            if registry:
                for agent in registry.list_agents():
                    health = await agent.health_check()
                    status["agents"][agent.agent_id] = health
        except Exception as e:
            logger.error(f"Error getting agent status: {e}")
            status["agents"]["error"] = str(e)

    return status


@router.get("/api/status/ollama")
async def get_ollama_status(token: str = Depends(require_auth)):
    """Get Ollama-specific status."""
    if not _settings:
        raise HTTPException(status_code=500, detail="Settings not initialized")

    config = _settings.get_ollama_config()
    status = {
        "enabled": config.enabled,
        "base_url": config.base_url,
        "model": config.model,
        "connected": False,
        "available_models": []
    }

    if config.enabled and _get_agent_registry:
        try:
            registry = _get_agent_registry()
            if registry:
                ollama_agent = registry.get("ollama")
                if ollama_agent:
                    health = await ollama_agent.health_check()
                    status["connected"] = health.get("ollama_available", False)
        except Exception as e:
            logger.error(f"Error checking Ollama status: {e}")
            status["error"] = str(e)

    return status


# =============================================================================
# Admin UI Endpoint
# =============================================================================

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def serve_admin_ui():
    """Serve the admin panel UI."""
    try:
        with open("static/admin/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Admin UI not available</h1><p>Static files not found.</p>",
            status_code=404
        )
