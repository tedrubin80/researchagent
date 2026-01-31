"""Authentication management for the admin panel."""

import secrets
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import bcrypt

logger = logging.getLogger(__name__)

# Default password (must be changed on first login)
DEFAULT_PASSWORD = "admin"


@dataclass
class Session:
    """Admin session information."""
    token: str
    created_at: datetime
    expires_at: datetime
    ip_address: Optional[str] = None

    def is_valid(self) -> bool:
        """Check if session is still valid."""
        return datetime.utcnow() < self.expires_at


class AdminAuth:
    """Authentication manager for admin panel.

    Features:
    - Password hashing with bcrypt
    - Session token management
    - Configurable session timeout
    """

    def __init__(
        self,
        password_hash: Optional[str] = None,
        session_timeout_hours: int = 24
    ):
        self._password_hash = password_hash
        self._session_timeout_hours = session_timeout_hours
        self._sessions: dict[str, Session] = {}
        self._is_default_password = password_hash is None

        # Initialize with default password if not provided
        if self._password_hash is None:
            self._password_hash = self.hash_password(DEFAULT_PASSWORD)
            self._is_default_password = True

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

    def verify_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        if not self._password_hash:
            return False
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self._password_hash.encode('utf-8')
        )

    def change_password(self, current_password: str, new_password: str) -> bool:
        """Change the admin password.

        Args:
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            True if password was changed successfully
        """
        if not self.verify_password(current_password):
            return False

        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters")

        self._password_hash = self.hash_password(new_password)
        self._is_default_password = False
        logger.info("Admin password changed successfully")
        return True

    def set_password_hash(self, password_hash: str) -> None:
        """Set password hash directly (used when loading from settings)."""
        self._password_hash = password_hash
        self._is_default_password = False

    def get_password_hash(self) -> Optional[str]:
        """Get current password hash for persistence."""
        return self._password_hash

    @property
    def is_default_password(self) -> bool:
        """Check if using default password (security warning)."""
        return self._is_default_password

    @property
    def session_timeout_hours(self) -> int:
        """Get session timeout in hours."""
        return self._session_timeout_hours

    @session_timeout_hours.setter
    def session_timeout_hours(self, hours: int) -> None:
        """Set session timeout in hours."""
        if hours < 1:
            raise ValueError("Session timeout must be at least 1 hour")
        self._session_timeout_hours = hours

    def create_session(self, ip_address: Optional[str] = None) -> Session:
        """Create a new admin session.

        Args:
            ip_address: Client IP address for logging

        Returns:
            New Session object with token
        """
        # Clean up expired sessions first
        self._cleanup_expired_sessions()

        token = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        session = Session(
            token=token,
            created_at=now,
            expires_at=now + timedelta(hours=self._session_timeout_hours),
            ip_address=ip_address
        )
        self._sessions[token] = session
        logger.info(f"Admin session created from {ip_address}")
        return session

    def validate_session(self, token: str) -> bool:
        """Validate a session token.

        Args:
            token: Session token to validate

        Returns:
            True if token is valid and not expired
        """
        session = self._sessions.get(token)
        if not session:
            return False

        if not session.is_valid():
            # Remove expired session
            del self._sessions[token]
            return False

        return True

    def invalidate_session(self, token: str) -> bool:
        """Invalidate a session (logout).

        Args:
            token: Session token to invalidate

        Returns:
            True if session was found and invalidated
        """
        if token in self._sessions:
            del self._sessions[token]
            logger.info("Admin session invalidated")
            return True
        return False

    def get_session(self, token: str) -> Optional[Session]:
        """Get session information.

        Args:
            token: Session token

        Returns:
            Session object if valid, None otherwise
        """
        if not self.validate_session(token):
            return None
        return self._sessions.get(token)

    def _cleanup_expired_sessions(self) -> int:
        """Remove all expired sessions.

        Returns:
            Number of sessions removed
        """
        expired = [
            token for token, session in self._sessions.items()
            if not session.is_valid()
        ]
        for token in expired:
            del self._sessions[token]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired sessions")

        return len(expired)

    def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        self._cleanup_expired_sessions()
        return len(self._sessions)

    def login(self, password: str, ip_address: Optional[str] = None) -> Optional[Session]:
        """Authenticate and create a session.

        Args:
            password: Password to verify
            ip_address: Client IP address

        Returns:
            Session if successful, None if authentication failed
        """
        if not self.verify_password(password):
            logger.warning(f"Failed login attempt from {ip_address}")
            return None

        return self.create_session(ip_address)

    def logout(self, token: str) -> bool:
        """Logout by invalidating session.

        Args:
            token: Session token

        Returns:
            True if logout was successful
        """
        return self.invalidate_session(token)
