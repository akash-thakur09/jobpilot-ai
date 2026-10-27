"""
JobPilot AI - Mock Portal Package
Provides local synthetic test portal for automated browser testing.
"""

from backend.app.automation.mock_portal.server import (
    MockPortalServer,
    create_mock_portal_app,
)

__all__ = ["MockPortalServer", "create_mock_portal_app"]
