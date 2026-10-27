"""
Unit tests for FormMapper conservative field mapping and safety guarantees.
"""

import pytest
from backend.app.automation.form_mapper import FormMapper
from backend.app.automation.types import (
    DetectedFormField,
    FormFieldType,
    FormInspectionReport,
)
from backend.app.workflow.schemas import (
    PreparedApplicationFormData,
    PreparedFormField,
)


@pytest.fixture
def sample_prepared_data():
    return PreparedApplicationFormData(
        fields={
            "full_name": PreparedFormField(
                value="Alex Mercer",
                provenance="candidate_profiles.full_name",
                is_verified=True,
            ),
            "email": PreparedFormField(
                value="alex.mercer@example.com",
                provenance="candidate_profiles.email",
                is_verified=True,
            ),
            "phone": PreparedFormField(
                value="+1-555-0188",
                provenance="candidate_profiles.phone",
                is_verified=True,
            ),
            "location": PreparedFormField(
                value="San Francisco, CA",
                provenance="candidate_profiles.location",
                is_verified=True,
            ),
            "linkedin_url": PreparedFormField(
                value="https://linkedin.com/in/alexmercer",
                provenance="candidate_profiles.linkedin_url",
                is_verified=True,
            ),
            "github_url": PreparedFormField(
                value="https://github.com/alexmercer",
                provenance="candidate_profiles.github_url",
                is_verified=True,
            ),
            "portfolio_url": PreparedFormField(
                value="https://alexmercer.dev",
                provenance="candidate_profiles.portfolio_url",
                is_verified=True,
            ),
            "years_of_experience": PreparedFormField(
                value=6,
                provenance="candidate_profiles.years_of_experience",
                is_verified=True,
            ),
        },
        unanswered_fields=[],
    )


def test_supported_verified_fields_mapped_correctly(sample_prepared_data):
    report = FormInspectionReport(
        url="http://127.0.0.1:8000/apply",
        form_detected=True,
        detected_fields=[
            DetectedFormField(field_id="full_name", name="full_name", selector="#full_name", is_required=True),
            DetectedFormField(field_id="email", name="email", field_type=FormFieldType.EMAIL, selector="#email", is_required=True),
            DetectedFormField(field_id="phone", name="phone", field_type=FormFieldType.TEL, selector="#phone"),
            DetectedFormField(field_id="location", name="location", selector="#location"),
            DetectedFormField(field_id="linkedin_url", name="linkedin_url", selector="#linkedin_url"),
            DetectedFormField(field_id="resume", name="resume", field_type=FormFieldType.FILE, selector="#resume", is_required=True),
        ],
    )

    plan = FormMapper.build_mapping_plan(report, sample_prepared_data)

    assert not plan.requires_human_intervention
    assert plan.fields_to_fill["#full_name"] == "Alex Mercer"
    assert plan.provenance["#full_name"] == "candidate_profiles.full_name"
    assert plan.fields_to_fill["#email"] == "alex.mercer@example.com"
    assert plan.fields_to_fill["#phone"] == "+1-555-0188"
    assert plan.fields_to_fill["#location"] == "San Francisco, CA"
    assert plan.fields_to_fill["#linkedin_url"] == "https://linkedin.com/in/alexmercer"
    assert plan.file_upload_selector == "#resume"
    assert len(plan.unmapped_required_fields) == 0


def test_missing_required_values_not_fabricated():
    # Prepared data lacks phone
    data = PreparedApplicationFormData(
        fields={
            "full_name": PreparedFormField(value="Alex Mercer", provenance="candidate_profiles.full_name"),
            "email": PreparedFormField(value="alex@example.com", provenance="candidate_profiles.email"),
        },
        unanswered_fields=["phone"],
    )

    report = FormInspectionReport(
        url="http://127.0.0.1:8000/apply",
        form_detected=True,
        detected_fields=[
            DetectedFormField(field_id="full_name", name="full_name", selector="#full_name", is_required=True),
            DetectedFormField(field_id="email", name="email", selector="#email", is_required=True),
            DetectedFormField(field_id="phone", name="phone", selector="#phone", is_required=True),
        ],
    )

    plan = FormMapper.build_mapping_plan(report, data)

    # Phone is required on form but missing from profile -> MUST NOT fabricate
    assert plan.requires_human_intervention is True
    assert "phone" in plan.unmapped_required_fields
    assert "#phone" not in plan.fields_to_fill
    assert any("phone" in r.lower() for r in plan.intervention_reasons)


def test_ambiguous_employer_questions_require_human_action(sample_prepared_data):
    report = FormInspectionReport(
        url="http://127.0.0.1:8000/apply",
        form_detected=True,
        detected_fields=[
            DetectedFormField(field_id="full_name", name="full_name", selector="#full_name", is_required=True),
            DetectedFormField(field_id="email", name="email", selector="#email", is_required=True),
            DetectedFormField(
                field_id="why_hire",
                name="why_hire",
                label="Why should we hire you for this role?",
                field_type=FormFieldType.TEXTAREA,
                selector="#why_hire",
                is_required=True,
            ),
        ],
    )

    plan = FormMapper.build_mapping_plan(report, sample_prepared_data)

    assert plan.requires_human_intervention is True
    assert "why_hire" in plan.unmapped_required_fields
    assert "#why_hire" not in plan.fields_to_fill
    assert any("ambiguous" in r.lower() or "why_hire" in r.lower() for r in plan.intervention_reasons)


def test_legal_and_sensitive_declarations_never_guessed(sample_prepared_data):
    prohibited_fields = [
        DetectedFormField(field_id="sponsorship", name="visa_sponsorship", label="Will you require visa sponsorship?", is_required=True, selector="#sponsorship"),
        DetectedFormField(field_id="gender", name="eeo_gender", label="What is your gender identity?", is_required=True, selector="#gender"),
        DetectedFormField(field_id="felony", name="criminal_record", label="Have you ever been convicted of a felony?", is_required=True, selector="#felony"),
        DetectedFormField(field_id="terms", name="legal_consent", label="I agree to mandatory arbitration", field_type=FormFieldType.CHECKBOX, is_required=True, selector="#terms"),
    ]

    for p_field in prohibited_fields:
        report = FormInspectionReport(
            url="http://127.0.0.1:8000/apply",
            form_detected=True,
            detected_fields=[
                DetectedFormField(field_id="full_name", name="full_name", selector="#full_name", is_required=True),
                DetectedFormField(field_id="email", name="email", selector="#email", is_required=True),
                p_field,
            ],
        )

        plan = FormMapper.build_mapping_plan(report, sample_prepared_data)
        assert plan.requires_human_intervention is True
        assert p_field.selector not in plan.fields_to_fill
        assert p_field.field_id in plan.unmapped_required_fields


def test_first_and_last_name_split_mapping(sample_prepared_data):
    report = FormInspectionReport(
        url="http://127.0.0.1:8000/apply",
        form_detected=True,
        detected_fields=[
            DetectedFormField(field_id="first_name", name="first_name", selector="#first_name", is_required=True),
            DetectedFormField(field_id="last_name", name="last_name", selector="#last_name", is_required=True),
            DetectedFormField(field_id="email", name="email", selector="#email", is_required=True),
        ],
    )

    plan = FormMapper.build_mapping_plan(report, sample_prepared_data)

    assert not plan.requires_human_intervention
    assert plan.fields_to_fill["#first_name"] == "Alex"
    assert plan.fields_to_fill["#last_name"] == "Mercer"
    assert "split_first" in plan.provenance["#first_name"]
    assert "split_last" in plan.provenance["#last_name"]


def test_optional_checkboxes_are_not_autoselected(sample_prepared_data):
    report = FormInspectionReport(
        url="http://127.0.0.1:8000/apply",
        form_detected=True,
        detected_fields=[
            DetectedFormField(field_id="full_name", name="full_name", selector="#full_name", is_required=True),
            DetectedFormField(field_id="email", name="email", selector="#email", is_required=True),
            DetectedFormField(field_id="subscribe", name="newsletter", field_type=FormFieldType.CHECKBOX, selector="#subscribe", is_required=False),
        ],
    )

    plan = FormMapper.build_mapping_plan(report, sample_prepared_data)
    assert "#subscribe" not in plan.fields_to_fill
    assert not plan.requires_human_intervention
