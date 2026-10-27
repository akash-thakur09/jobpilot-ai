"""
JobPilot AI - Synthetic Browser Automation Adapter
Implements the browser automation layer for the local synthetic test portal.
Includes strict origin whitelisting, defensive element selection, CAPTCHA/MFA detection,
and proof-of-submission verification.
"""

from typing import List, Optional, Tuple
from urllib.parse import urlparse
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from backend.app.automation.base_adapter import BaseBrowserAdapter
from backend.app.automation.types import (
    AutomationExecutionResult,
    DetectedFormField,
    FillFieldResult,
    FormFieldType,
    FormInspectionReport,
    FormMappingPlan,
    SafetyBarrierType,
)
from backend.app.models.enums import SubmissionOutcome
from backend.app.core.logging import logger


class SyntheticBrowserAdapter(BaseBrowserAdapter):
    """
    Playwright browser adapter for local synthetic mock portal.
    """

    ALLOWED_HOSTS = {"127.0.0.1", "localhost"}

    def __init__(self, adapter_identifier: str = "synthetic_mock_adapter"):
        super().__init__(adapter_identifier=adapter_identifier)

    def _verify_origin_safety(self, url: str) -> bool:
        """Enforces origin whitelist policy to prevent external navigation."""
        try:
            parsed = urlparse(url)
            return parsed.hostname in self.ALLOWED_HOSTS
        except Exception:
            return False

    async def detect_safety_barriers(self, page: Page) -> Optional[SafetyBarrierType]:
        """
        Detects anti-bot barriers, CAPTCHA, MFA, or unauthorized external navigation.
        """
        current_url = page.url
        if not self._verify_origin_safety(current_url):
            logger.warning(f"Safety barrier triggered: External navigation detected to {current_url}")
            return SafetyBarrierType.EXTERNAL_NAVIGATION

        # 1. Access Denied / Cloudflare / Bot blocks
        cf_challenge = await page.query_selector("#cf-challenge, #security-notice")
        if cf_challenge:
            return SafetyBarrierType.ACCESS_DENIED

        title = await page.title()
        if "access denied" in title.lower() or "403 forbidden" in title.lower():
            return SafetyBarrierType.ACCESS_DENIED

        # 2. CAPTCHA Detection
        captcha_el = await page.query_selector(
            "#captcha-barrier, .g-recaptcha, iframe[src*='recaptcha'], iframe[title*='challenge'], #cf-turnstile"
        )
        if captcha_el:
            return SafetyBarrierType.CAPTCHA

        # 3. MFA / Two-Factor Prompt Detection
        mfa_el = await page.query_selector("#mfa-container, #mfa-form, input[name*='mfa'], input[name*='2fa']")
        if mfa_el:
            return SafetyBarrierType.MFA

        return None

    async def inspect_form(self, page: Page) -> FormInspectionReport:
        """
        Inspects application page for form inputs and barriers.
        """
        url = page.url
        barrier = await self.detect_safety_barriers(page)

        if barrier:
            return FormInspectionReport(
                url=url,
                form_detected=False,
                safety_barrier=barrier,
                has_captcha=(barrier == SafetyBarrierType.CAPTCHA),
                has_mfa=(barrier == SafetyBarrierType.MFA),
                issues=[f"Safety barrier detected: {barrier.value}"],
            )

        form_el = await page.query_selector("form#application-form, form")
        if not form_el:
            return FormInspectionReport(
                url=url,
                form_detected=False,
                issues=["No application form element found on page."],
            )

        detected_fields: List[DetectedFormField] = []
        input_elements = await page.query_selector_all("input, textarea, select")

        for el in input_elements:
            field_id = await el.get_attribute("id") or ""
            name = await el.get_attribute("name") or field_id
            placeholder = await el.get_attribute("placeholder") or ""
            raw_type = await el.get_attribute("type") or "text"
            is_required = (await el.get_attribute("required")) is not None
            current_value = await el.input_value() if raw_type not in ["file", "submit", "button"] else ""

            tag_name = await el.evaluate("e => e.tagName.toLowerCase()")

            # Determine form field type
            if tag_name == "textarea":
                field_type = FormFieldType.TEXTAREA
            elif tag_name == "select":
                field_type = FormFieldType.SELECT
            elif raw_type == "email":
                field_type = FormFieldType.EMAIL
            elif raw_type in ("tel", "phone"):
                field_type = FormFieldType.TEL
            elif raw_type == "file":
                field_type = FormFieldType.FILE
            elif raw_type == "checkbox":
                field_type = FormFieldType.CHECKBOX
            elif raw_type == "radio":
                field_type = FormFieldType.RADIO
            elif raw_type in ("submit", "button", "hidden"):
                continue
            else:
                field_type = FormFieldType.TEXT

            # Determine label text
            label_text = None
            if field_id:
                label_el = await page.query_selector(f"label[for='{field_id}']")
                if label_el:
                    label_text = await label_el.inner_text()

            # Selector
            selector = f"#{field_id}" if field_id else f"[name='{name}']"

            detected_fields.append(
                DetectedFormField(
                    field_id=field_id or name,
                    name=name,
                    label=label_text,
                    placeholder=placeholder,
                    field_type=field_type,
                    is_required=is_required,
                    selector=selector,
                    current_value=current_value,
                )
            )

        return FormInspectionReport(
            url=url,
            form_detected=True,
            form_selector="form#application-form",
            detected_fields=detected_fields,
        )

    async def fill_fields(
        self, page: Page, mapping_plan: FormMappingPlan
    ) -> List[FillFieldResult]:
        """
        Fills the mapped fields on the page.
        """
        results: List[FillFieldResult] = []

        for selector, value in mapping_plan.fields_to_fill.items():
            prov = mapping_plan.provenance.get(selector)
            try:
                el = await page.query_selector(selector)
                if not el:
                    results.append(
                        FillFieldResult(
                            selector=selector,
                            field_name=selector,
                            value_preview="[NOT_FOUND]",
                            success=False,
                            provenance=prov,
                            error=f"Element not found for selector: {selector}",
                        )
                    )
                    continue

                await page.fill(selector, str(value))
                preview = str(value)[:30] + ("..." if len(str(value)) > 30 else "")
                results.append(
                    FillFieldResult(
                        selector=selector,
                        field_name=selector,
                        value_preview=preview,
                        success=True,
                        provenance=prov,
                    )
                )
            except Exception as e:
                results.append(
                    FillFieldResult(
                        selector=selector,
                        field_name=selector,
                        value_preview="[ERROR]",
                        success=False,
                        provenance=prov,
                        error=str(e),
                    )
                )

        return results

    async def upload_resume(
        self, page: Page, selector: str, file_path: str
    ) -> bool:
        """
        Uploads the resume PDF file to the file input.
        """
        el = await page.query_selector(selector)
        if not el:
            raise FileNotFoundError(f"File upload element not found with selector: {selector}")

        await page.set_input_files(selector, file_path)
        return True

    async def validate_form(self, page: Page) -> Tuple[bool, List[str]]:
        """
        Checks for HTML5 client-side validation errors or visible error banners.
        """
        error_banner = await page.query_selector("#error-banner")
        if error_banner:
            is_visible = await error_banner.is_visible()
            if is_visible:
                text = (await error_banner.inner_text()).strip()
                if text:
                    return False, [text]

        # Check required fields validity via DOM
        invalid_fields = await page.evaluate(
            """
            () => {
                const form = document.querySelector('form#application-form') || document.querySelector('form');
                if (!form) return [];
                const invalids = [];
                for (const el of form.elements) {
                    if (el.willValidate && !el.checkValidity()) {
                        invalids.push(el.name || el.id || 'unknown_field');
                    }
                }
                return invalids;
            }
            """
        )
        if invalid_fields:
            return False, [f"Invalid or missing required fields: {', '.join(invalid_fields)}"]

        return True, []

    async def submit_and_verify(self, page: Page) -> AutomationExecutionResult:
        """
        Clicks submit and verifies the confirmation page.
        Distinguishes SUCCESS, FAILED, NEEDS_HUMAN_ACTION, and OUTCOME_UNKNOWN.
        """
        submit_btn = await page.query_selector("#submit-btn, button[type='submit']")
        if not submit_btn:
            return AutomationExecutionResult(
                outcome=SubmissionOutcome.FAILED,
                adapter_identifier=self.adapter_identifier,
                error_message="Submit button (#submit-btn) not found on application page.",
                diagnostics={"step": "submit_button_missing"},
            )

        try:
            # Trigger form submit
            await submit_btn.click()
            # Wait for either response navigation or DOM update
            await page.wait_for_load_state("load", timeout=5000)
        except PlaywrightTimeoutError:
            # Timeout during submission click
            logger.warning("Timeout while waiting for post-submission page load.")
            return AutomationExecutionResult(
                outcome=SubmissionOutcome.OUTCOME_UNKNOWN,
                adapter_identifier=self.adapter_identifier,
                error_message="Timeout after submit click. Outcome could not be verified.",
                diagnostics={"reason": "PLAYWRIGHT_NAVIGATION_TIMEOUT_POST_SUBMIT"},
            )
        except Exception as e:
            return AutomationExecutionResult(
                outcome=SubmissionOutcome.FAILED,
                adapter_identifier=self.adapter_identifier,
                error_message=f"Browser error during submission: {str(e)}",
                diagnostics={"exception": str(e)},
            )

        # 1. Check for post-submit safety barriers
        barrier = await self.detect_safety_barriers(page)
        if barrier:
            return AutomationExecutionResult(
                outcome=SubmissionOutcome.BLOCKED_SAFETY if barrier != SafetyBarrierType.CAPTCHA else SubmissionOutcome.NEEDS_HUMAN_ACTION,
                adapter_identifier=self.adapter_identifier,
                error_message=f"Safety barrier detected after submission: {barrier.value}",
                diagnostics={"barrier": barrier.value},
            )

        # 2. Check for validation error banner on response
        error_banner = await page.query_selector("#error-banner, .error-banner")
        if error_banner:
            is_visible = await error_banner.is_visible()
            if is_visible:
                err_text = (await error_banner.inner_text()).strip()
                return AutomationExecutionResult(
                    outcome=SubmissionOutcome.FAILED,
                    adapter_identifier=self.adapter_identifier,
                    error_message=f"Portal rejected submission: {err_text}",
                    diagnostics={"error_banner": err_text},
                )

        # 3. Check for synthetic confirmation panel and receipt ID
        receipt_el = await page.query_selector("#receipt-id")
        conf_el = await page.query_selector("#application-confirmation, #confirmation-panel")

        if receipt_el and conf_el:
            receipt_id = (await receipt_el.inner_text()).strip()
            conf_text = (await conf_el.inner_text()).strip()

            if receipt_id.startswith("SYNTH-"):
                return AutomationExecutionResult(
                    outcome=SubmissionOutcome.SUCCESS,
                    adapter_identifier=self.adapter_identifier,
                    confirmation_reference=receipt_id,
                    confirmation_payload={
                        "receipt_id": receipt_id,
                        "status": "confirmed",
                        "confirmation_text": conf_text[:200],
                        "is_synthetic": True,
                    },
                    diagnostics={"verified_receipt": receipt_id},
                    is_synthetic=True,
                )

        # 4. If neither confirmation nor error banner was detected, outcome is UNKNOWN!
        logger.warning("Submission clicked, but no confirmation receipt or validation error detected.")
        return AutomationExecutionResult(
            outcome=SubmissionOutcome.OUTCOME_UNKNOWN,
            adapter_identifier=self.adapter_identifier,
            error_message="Submission outcome cannot be verified. Portal did not provide valid receipt.",
            diagnostics={"reason": "NO_RECEIPT_OR_ERROR_BANNER"},
        )
