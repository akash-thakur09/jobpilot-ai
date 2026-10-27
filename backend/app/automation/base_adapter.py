"""
JobPilot AI - Base Browser Automation Adapter
Defines the abstract interface for inspecting forms, filling fields, uploading resumes,
validating inputs, detecting safety barriers, and verifying submissions.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from playwright.async_api import Page

from backend.app.automation.types import (
    AutomationExecutionResult,
    FillFieldResult,
    FormInspectionReport,
    FormMappingPlan,
    SafetyBarrierType,
)


class BaseBrowserAdapter(ABC):
    """
    Abstract interface for portal-specific browser automation adapters.
    """

    def __init__(self, adapter_identifier: str = "base_adapter"):
        self.adapter_identifier = adapter_identifier

    @abstractmethod
    async def inspect_form(self, page: Page) -> FormInspectionReport:
        """
        Inspects the loaded page to discover application form elements, input fields,
        file upload inputs, and any existing safety barriers.
        """
        pass

    @abstractmethod
    async def fill_fields(
        self, page: Page, mapping_plan: FormMappingPlan
    ) -> List[FillFieldResult]:
        """
        Fills mapped fields on the page in accordance with the mapping plan.
        """
        pass

    @abstractmethod
    async def upload_resume(
        self, page: Page, selector: str, file_path: str
    ) -> bool:
        """
        Sets the file input to upload the verified resume PDF artifact.
        """
        pass

    @abstractmethod
    async def validate_form(self, page: Page) -> Tuple[bool, List[str]]:
        """
        Validates form state before submission, checking for visible validation errors.
        Returns (is_valid, list_of_errors).
        """
        pass

    @abstractmethod
    async def detect_safety_barriers(
        self, page: Page
    ) -> Optional[SafetyBarrierType]:
        """
        Detects anti-bot barriers such as CAPTCHAs, MFA prompts, or access restrictions.
        """
        pass

    @abstractmethod
    async def submit_and_verify(
        self, page: Page
    ) -> AutomationExecutionResult:
        """
        Submits the application form and verifies the resulting page for confirmation evidence.
        Does NOT assume clicking submit implies success.
        """
        pass
