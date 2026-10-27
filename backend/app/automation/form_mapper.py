"""
JobPilot AI - Conservative Form Mapper
Inspects detected form fields and maps only verified candidate data.
Never fabricates missing values, never guesses answers to employer questions,
and strictly prohibits inferring legal declarations, sponsorship, or demographic answers.
"""

import re
from typing import Any, Dict, List, Optional, Set
from backend.app.automation.types import (
    DetectedFormField,
    FormFieldType,
    FormInspectionReport,
    FormMappingPlan,
)
from backend.app.workflow.schemas import PreparedApplicationFormData
from backend.app.core.logging import logger


class FormMapper:
    """
    Conservative form mapper that binds verified candidate facts to detected form fields.
    """

    # Prohibited inference keywords: Legal, EEO/demographics, sponsorship/work-auth declarations
    PROHIBITED_INFERENCE_KEYWORDS: Set[str] = {
        "sponsorship",
        "visa",
        "work_auth",
        "work_authorization",
        "authorized_to_work",
        "citizen",
        "citizenship",
        "clearance",
        "gender",
        "race",
        "ethnicity",
        "veteran",
        "disability",
        "eeo",
        "demographic",
        "felony",
        "criminal",
        "background_check",
        "drug_test",
        "legal_declaration",
        "terms",
        "consent",
        "signature",
        "declaration",
    }

    # Employer-specific or ambiguous question patterns
    AMBIGUOUS_QUESTION_KEYWORDS: Set[str] = {
        "why_hire",
        "why_work_here",
        "salary",
        "compensation",
        "cover_letter",
        "custom_question",
        "additional_info",
        "tell_us_about",
        "describe",
        "motivation",
        "pitch",
    }

    @classmethod
    def _normalize_token(cls, text: Optional[str]) -> str:
        if not text:
            return ""
        # Convert non-alphanumeric to underscores and lowercase
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
        return cleaned

    @classmethod
    def _is_prohibited_inference(cls, field: DetectedFormField) -> bool:
        combined = f"{cls._normalize_token(field.name)} {cls._normalize_token(field.label)} {cls._normalize_token(field.field_id)} {cls._normalize_token(field.placeholder)}"
        for kw in cls.PROHIBITED_INFERENCE_KEYWORDS:
            if kw in combined:
                return True
        return False

    @classmethod
    def _is_ambiguous_question(cls, field: DetectedFormField) -> bool:
        combined = f"{cls._normalize_token(field.name)} {cls._normalize_token(field.label)} {cls._normalize_token(field.field_id)} {cls._normalize_token(field.placeholder)}"
        for kw in cls.AMBIGUOUS_QUESTION_KEYWORDS:
            if kw in combined:
                return True
        return False

    @classmethod
    def build_mapping_plan(
        cls,
        inspection_report: FormInspectionReport,
        prepared_form_data: PreparedApplicationFormData,
    ) -> FormMappingPlan:
        """
        Builds a safe, conservative mapping plan from verified candidate data
        to detected form fields.
        """
        fields_to_fill: Dict[str, Any] = {}
        provenance: Dict[str, str] = {}
        file_upload_selector: Optional[str] = None
        unmapped_required: List[str] = []
        intervention_reasons: List[str] = []
        requires_human = False

        prepared_fields = prepared_form_data.fields

        for field in inspection_report.detected_fields:
            field_name_token = cls._normalize_token(field.name)
            field_label_token = cls._normalize_token(field.label)
            field_id_token = cls._normalize_token(field.field_id)
            combined_tokens = f"{field_id_token} {field_name_token} {field_label_token}"

            # 1. File Upload Field (Resume PDF)
            if (
                field.field_type == FormFieldType.FILE
                or "resume" in combined_tokens
                or "cv" in combined_tokens
                or "attachment" in combined_tokens
            ):
                if not file_upload_selector:
                    file_upload_selector = field.selector
                    continue

            # 2. Strict Prohibition: Legal, Work Auth/Sponsorship declarations, EEO/Demographics
            if cls._is_prohibited_inference(field):
                # Never infer legal, sponsorship, or demographic answers
                if field.is_required:
                    requires_human = True
                    reason = (
                        f"Field '{field.label or field.name or field.field_id}' requires "
                        "explicit legal, work authorization, or demographic declaration and cannot be inferred."
                    )
                    intervention_reasons.append(reason)
                    unmapped_required.append(field.field_id)
                continue

            # 3. Ambiguous or Employer-Specific Questions
            if cls._is_ambiguous_question(field):
                # Do not invent answers
                if field.is_required:
                    requires_human = True
                    reason = (
                        f"Ambiguous or employer-specific question '{field.label or field.name or field.field_id}' "
                        "requires human input."
                    )
                    intervention_reasons.append(reason)
                    unmapped_required.append(field.field_id)
                continue

            # 4. Checkboxes: Do not auto-select optional checkboxes without explicit verified preference
            if field.field_type == FormFieldType.CHECKBOX:
                if field.is_required:
                    requires_human = True
                    reason = f"Required checkbox '{field.label or field.name or field.field_id}' requires explicit human confirmation."
                    intervention_reasons.append(reason)
                    unmapped_required.append(field.field_id)
                continue

            # 5. Full Name / First Name / Last Name
            if (
                any(token in combined_tokens.split() for token in ["first_name", "firstname", "given_name"])
                and "full_name" in prepared_fields
            ):
                full_name_val = str(prepared_fields["full_name"].value or "").strip()
                first_name_val = full_name_val.split()[0] if full_name_val else ""
                if first_name_val:
                    fields_to_fill[field.selector] = first_name_val
                    provenance[field.selector] = f"{prepared_fields['full_name'].provenance}[split_first]"
                    continue

            if (
                any(token in combined_tokens.split() for token in ["last_name", "lastname", "family_name", "surname"])
                and "full_name" in prepared_fields
            ):
                full_name_val = str(prepared_fields["full_name"].value or "").strip()
                parts = full_name_val.split()
                last_name_val = " ".join(parts[1:]) if len(parts) > 1 else ""
                if last_name_val:
                    fields_to_fill[field.selector] = last_name_val
                    provenance[field.selector] = f"{prepared_fields['full_name'].provenance}[split_last]"
                    continue

            if (
                any(k in combined_tokens.split() for k in ["name", "full_name", "fullname", "applicant_name"])
                and "full_name" in prepared_fields
            ):
                val = prepared_fields["full_name"].value
                if val:
                    fields_to_fill[field.selector] = str(val)
                    provenance[field.selector] = prepared_fields["full_name"].provenance
                    continue

            # 6. Email Address
            if (
                field.field_type == FormFieldType.EMAIL
                or any(k in combined_tokens.split() for k in ["email", "e_mail", "email_address"])
            ) and "email" in prepared_fields:
                val = prepared_fields["email"].value
                if val:
                    fields_to_fill[field.selector] = str(val)
                    provenance[field.selector] = prepared_fields["email"].provenance
                    continue

            # 7. Phone Number
            if (
                field.field_type == FormFieldType.TEL
                or any(k in combined_tokens.split() for k in ["phone", "mobile", "tel", "telephone", "phone_number"])
            ) and "phone" in prepared_fields:
                val = prepared_fields["phone"].value
                if val:
                    fields_to_fill[field.selector] = str(val)
                    provenance[field.selector] = prepared_fields["phone"].provenance
                    continue

            # 8. Location / City
            if (
                any(k in combined_tokens.split() for k in ["location", "city", "address"])
                and "location" in prepared_fields
            ):
                val = prepared_fields["location"].value
                if val:
                    fields_to_fill[field.selector] = str(val)
                    provenance[field.selector] = prepared_fields["location"].provenance
                    continue

            # 9. LinkedIn URL
            if "linkedin" in combined_tokens and "linkedin_url" in prepared_fields:
                val = prepared_fields["linkedin_url"].value
                if val:
                    fields_to_fill[field.selector] = str(val)
                    provenance[field.selector] = prepared_fields["linkedin_url"].provenance
                    continue

            # 10. GitHub URL
            if "github" in combined_tokens and "github_url" in prepared_fields:
                val = prepared_fields["github_url"].value
                if val:
                    fields_to_fill[field.selector] = str(val)
                    provenance[field.selector] = prepared_fields["github_url"].provenance
                    continue

            # 11. Portfolio / Website URL
            if (
                any(k in combined_tokens for k in ["portfolio", "website", "personal_website"])
                and "portfolio_url" in prepared_fields
            ):
                val = prepared_fields["portfolio_url"].value
                if val:
                    fields_to_fill[field.selector] = str(val)
                    provenance[field.selector] = prepared_fields["portfolio_url"].provenance
                    continue

            # 12. Years of Experience
            if (
                any(k in combined_tokens for k in ["experience", "years_experience", "yoe"])
                and "years_of_experience" in prepared_fields
            ):
                val = prepared_fields["years_of_experience"].value
                if val is not None:
                    fields_to_fill[field.selector] = str(val)
                    provenance[field.selector] = prepared_fields["years_of_experience"].provenance
                    continue

            # 13. If required field could not be mapped, do not fabricate!
            if field.is_required:
                requires_human = True
                unmapped_required.append(field.field_id)
                reason = (
                    f"Required field '{field.label or field.name or field.field_id}' "
                    "cannot be mapped to verified candidate facts."
                )
                intervention_reasons.append(reason)

        return FormMappingPlan(
            fields_to_fill=fields_to_fill,
            provenance=provenance,
            file_upload_selector=file_upload_selector,
            unmapped_required_fields=unmapped_required,
            requires_human_intervention=requires_human,
            intervention_reasons=intervention_reasons,
        )
