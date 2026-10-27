"""
JobPilot AI - Browser Automation Types and Result Schemas
Typed models and enums for form inspection, field mapping, safety barriers,
and execution results.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.models.enums import SubmissionOutcome


class FormFieldType(str, Enum):
    TEXT = "text"
    EMAIL = "email"
    TEL = "tel"
    FILE = "file"
    TEXTAREA = "textarea"
    CHECKBOX = "checkbox"
    SELECT = "select"
    RADIO = "radio"
    UNKNOWN = "unknown"


class SafetyBarrierType(str, Enum):
    CAPTCHA = "CAPTCHA"
    MFA = "MFA"
    BOT_CHALLENGE = "BOT_CHALLENGE"
    ACCESS_DENIED = "ACCESS_DENIED"
    EXTERNAL_NAVIGATION = "EXTERNAL_NAVIGATION"


class DetectedFormField(BaseModel):
    field_id: str
    name: Optional[str] = None
    label: Optional[str] = None
    placeholder: Optional[str] = None
    field_type: FormFieldType = FormFieldType.TEXT
    is_required: bool = False
    selector: str
    current_value: Optional[str] = None
    options: List[str] = Field(default_factory=list)


class FormInspectionReport(BaseModel):
    url: str
    form_detected: bool = False
    form_selector: Optional[str] = None
    detected_fields: List[DetectedFormField] = Field(default_factory=list)
    safety_barrier: Optional[SafetyBarrierType] = None
    has_captcha: bool = False
    has_mfa: bool = False
    issues: List[str] = Field(default_factory=list)


class FormMappingPlan(BaseModel):
    fields_to_fill: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, str] = Field(default_factory=dict)
    file_upload_selector: Optional[str] = None
    unmapped_required_fields: List[str] = Field(default_factory=list)
    requires_human_intervention: bool = False
    intervention_reasons: List[str] = Field(default_factory=list)


class FillFieldResult(BaseModel):
    selector: str
    field_name: str
    value_preview: str
    success: bool
    provenance: Optional[str] = None
    error: Optional[str] = None


class AutomationExecutionResult(BaseModel):
    outcome: SubmissionOutcome
    adapter_identifier: str
    confirmation_reference: Optional[str] = None
    confirmation_payload: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    is_synthetic: bool = True
