"""
JobPilot AI - Browser Automation Module
Provides Playwright-based browser automation adapters, conservative form mapping,
synthetic portal harnesses, and safety-gated execution runners.
"""

from backend.app.automation.base_adapter import BaseBrowserAdapter
from backend.app.automation.browser_runner import BrowserAutomationRunner
from backend.app.automation.form_mapper import FormMapper
from backend.app.automation.mock_portal.server import MockPortalServer, create_mock_portal_app
from backend.app.automation.synthetic_adapter import SyntheticBrowserAdapter
from backend.app.automation.types import (
    AutomationExecutionResult,
    DetectedFormField,
    FillFieldResult,
    FormFieldType,
    FormInspectionReport,
    FormMappingPlan,
    SafetyBarrierType,
)

__all__ = [
    "BaseBrowserAdapter",
    "BrowserAutomationRunner",
    "FormMapper",
    "MockPortalServer",
    "create_mock_portal_app",
    "SyntheticBrowserAdapter",
    "AutomationExecutionResult",
    "DetectedFormField",
    "FillFieldResult",
    "FormFieldType",
    "FormInspectionReport",
    "FormMappingPlan",
    "SafetyBarrierType",
]
