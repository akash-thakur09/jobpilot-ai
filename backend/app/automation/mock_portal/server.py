"""
JobPilot AI - Synthetic Mock Portal Server
Local-only test server rendering realistic job application forms and simulating
various portal scenarios (confirmation, validation failure, CAPTCHA, MFA, server error, unknown outcome).
Never sends application data to external endpoints.
"""

import socket
import threading
import time
import uuid
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, PlainTextResponse
import uvicorn

from backend.app.core.logging import logger


def find_free_port() -> int:
    """Finds an available local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def create_mock_portal_app() -> FastAPI:
    """
    Creates the mock portal FastAPI application.
    """
    app = FastAPI(title="JobPilot Synthetic Portal", docs_url=None, redoc_url=None)

    @app.get("/health")
    async def health():
        return {"status": "ok", "portal": "synthetic_mock_portal"}

    @app.get("/jobs/{job_id}/apply", response_class=HTMLResponse)
    async def get_application_form(job_id: str, scenario: str = "default"):
        """
        Renders the application form for the given scenario.
        Supported scenarios:
        - default: Standard clean application form.
        - ambiguous: Form with an ambiguous employer question.
        - captcha: Form with synthetic reCAPTCHA barrier.
        - mfa: MFA / two-factor authentication prompt.
        - server_error: 500 error page.
        - access_denied: Cloudflare / bot block page.
        """
        if scenario == "server_error":
            raise HTTPException(status_code=500, detail="Internal Server Error: Synthetic portal failure.")

        if scenario == "access_denied":
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>Access Denied</title></head>
                <body>
                    <div id="cf-challenge">
                        <h1>403 Forbidden - Access Denied</h1>
                        <p id="security-notice">Cloudflare Security Check: Automated requests are blocked.</p>
                    </div>
                </body>
                </html>
                """,
                status_code=403,
            )

        if scenario == "mfa":
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>Two-Factor Authentication Required</title></head>
                <body>
                    <div id="mfa-container">
                        <h1>Security Verification</h1>
                        <p>A verification code has been sent to your device.</p>
                        <form id="mfa-form" action="/mfa/verify" method="POST">
                            <label for="mfa_code">Verification Code</label>
                            <input type="text" id="mfa_code" name="mfa_code" required />
                            <button type="submit" id="mfa-submit">Verify</button>
                        </form>
                    </div>
                </body>
                </html>
                """
            )

        captcha_html = ""
        if scenario == "captcha":
            captcha_html = """
            <div id="captcha-barrier" class="g-recaptcha" data-sitekey="synthetic-test-key">
                <p>Please complete the security challenge below to proceed:</p>
                <iframe title="recaptcha challenge" src="about:blank" style="width:300px; height:80px; border:1px solid #ccc;"></iframe>
            </div>
            """

        ambiguous_html = ""
        if scenario == "ambiguous":
            ambiguous_html = """
            <div class="form-group">
                <label for="why_hire">Why are you the perfect fit for this position? *</label>
                <textarea id="why_hire" name="why_hire" required placeholder="Describe your unique motivation"></textarea>
            </div>
            """

        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>Apply for Synthetic Job #{job_id}</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #f8fafc; }}
                    .container {{ max-width: 650px; margin: 0 auto; background: #fff; padding: 32px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
                    h1 {{ margin-top: 0; color: #0f172a; font-size: 24px; }}
                    .form-group {{ margin-bottom: 20px; }}
                    label {{ display: block; margin-bottom: 6px; font-weight: 600; color: #334155; }}
                    input[type="text"], input[type="email"], input[type="tel"], textarea {{
                        width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; font-size: 14px;
                    }}
                    button[type="submit"] {{
                        background: #2563eb; color: #fff; font-weight: 600; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px;
                    }}
                    button[type="submit"]:hover {{ background: #1d4ed8; }}
                    .notice {{ background: #f1f5f9; padding: 12px; border-left: 4px solid #3b82f6; margin-bottom: 24px; font-size: 13px; color: #475569; }}
                    .error-banner {{ background: #fee2e2; border-left: 4px solid #ef4444; color: #991b1b; padding: 12px; margin-bottom: 20px; display: none; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="notice">
                        <strong>TEST ENVIRONMENT:</strong> This is a synthetic application harness. No external data will be transmitted.
                    </div>
                    <h1>Job Application: Position #{job_id}</h1>
                    <div id="error-banner" class="error-banner"></div>

                    <form id="application-form" action="/jobs/{job_id}/apply?scenario={scenario}" method="POST" enctype="multipart/form-data">
                        <div class="form-group">
                            <label for="full_name">Full Name *</label>
                            <input type="text" id="full_name" name="full_name" required placeholder="Jane Doe" />
                        </div>

                        <div class="form-group">
                            <label for="email">Email Address *</label>
                            <input type="email" id="email" name="email" required placeholder="jane.doe@example.com" />
                        </div>

                        <div class="form-group">
                            <label for="phone">Phone Number</label>
                            <input type="tel" id="phone" name="phone" placeholder="+1-555-0199" />
                        </div>

                        <div class="form-group">
                            <label for="location">Location / City</label>
                            <input type="text" id="location" name="location" placeholder="San Francisco, CA" />
                        </div>

                        <div class="form-group">
                            <label for="linkedin_url">LinkedIn Profile</label>
                            <input type="text" id="linkedin_url" name="linkedin_url" placeholder="https://linkedin.com/in/janedoe" />
                        </div>

                        <div class="form-group">
                            <label for="resume">Attach Resume PDF *</label>
                            <input type="file" id="resume" name="resume" accept=".pdf" required />
                        </div>

                        {ambiguous_html}
                        {captcha_html}

                        <button type="submit" id="submit-btn">Submit Application</button>
                    </form>
                </div>
            </body>
            </html>
            """
        )

    @app.post("/jobs/{job_id}/apply", response_class=HTMLResponse)
    async def submit_application_form(
        job_id: str,
        scenario: str = "default",
        full_name: Optional[str] = Form(None),
        email: Optional[str] = Form(None),
        phone: Optional[str] = Form(None),
        location: Optional[str] = Form(None),
        linkedin_url: Optional[str] = Form(None),
        why_hire: Optional[str] = Form(None),
        resume: Optional[UploadFile] = File(None),
    ):
        """
        Handles simulated form submission.
        """
        # Scenario: Server Error
        if scenario == "server_error":
            raise HTTPException(status_code=500, detail="Synthetic portal 500 error.")

        # Scenario: Unknown Outcome (e.g. timeout / hang / ambiguous redirect)
        if scenario == "unknown_outcome":
            # Returns a page without any receipt or confirmation evidence
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>Processing Request</title></head>
                <body>
                    <div id="generic-pending">
                        <h2>Processing...</h2>
                        <p>Your request has been received by our proxy and is awaiting processing.</p>
                    </div>
                </body>
                </html>
                """
            )

        # Validation: Required fields
        errors = []
        if not full_name or not full_name.strip():
            errors.append("Full Name is required.")
        if not email or "@" not in email:
            errors.append("A valid Email Address is required.")
        if not resume or not resume.filename:
            errors.append("Resume PDF upload is required.")
        elif not resume.filename.lower().endswith(".pdf"):
            errors.append("Only PDF files are accepted.")
        if scenario == "ambiguous" and (not why_hire or not why_hire.strip()):
            errors.append("Why are you the perfect fit is required.")

        if errors or scenario == "validation_error":
            error_message = "; ".join(errors) if errors else "Validation failed: Invalid form fields."
            return HTMLResponse(
                content=f"""
                <!DOCTYPE html>
                <html>
                <head><title>Validation Error</title></head>
                <body style="font-family: sans-serif; padding: 40px;">
                    <div id="error-banner" class="error-banner" style="background:#fee2e2; border-left:4px solid #ef4444; color:#991b1b; padding:16px;">
                        <h3>Form Submission Rejected</h3>
                        <p id="error-message">{error_message}</p>
                    </div>
                    <a href="/jobs/{job_id}/apply">Go back to form</a>
                </body>
                </html>
                """,
                status_code=400,
            )

        # Successful Submission Simulation
        synthetic_receipt_id = f"SYNTH-APP-{uuid.uuid4().hex[:8].upper()}"
        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>Application Received</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 50px; background: #f8fafc; }}
                    .card {{ max-width: 600px; margin: 0 auto; background: #fff; padding: 40px; border-radius: 8px; border-top: 5px solid #22c55e; }}
                    .badge {{ display: inline-block; background: #dcfce7; color: #15803d; font-weight: bold; padding: 6px 12px; border-radius: 9999px; font-size: 14px; margin-bottom: 16px; }}
                    .receipt {{ background: #f1f5f9; padding: 16px; border-radius: 6px; font-family: monospace; font-size: 16px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="card" id="confirmation-panel">
                    <span class="badge">SIMULATED SUBMISSION</span>
                    <h1 id="confirmation-heading">Application Submitted Successfully</h1>
                    <div id="application-confirmation">
                        Your test application for Position #{job_id} has been recorded (TEST-ONLY SIMULATION).
                    </div>
                    <div class="receipt">
                        <strong>Receipt ID:</strong> <span id="receipt-id">{synthetic_receipt_id}</span>
                    </div>
                    <p>Applicant: <strong>{full_name}</strong> ({email})</p>
                    <p>Resume: <strong>{resume.filename}</strong></p>
                </div>
            </body>
            </html>
            """
        )

    return app


class MockPortalServer:
    """
    Manages a background uvicorn server running the synthetic portal on a free local port.
    """

    def __init__(self, host: str = "127.0.0.1", port: Optional[int] = None):
        self.host = host
        self.port = port or find_free_port()
        self.app = create_mock_portal_app()
        self.server: Optional[uvicorn.Server] = None
        self.thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> str:
        """Starts the mock portal server in a background thread."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="error",
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()

        # Wait briefly for server startup
        time.sleep(0.4)
        logger.info(f"Synthetic Mock Portal started at {self.base_url}")
        return self.base_url

    def stop(self) -> None:
        """Stops the mock portal server."""
        if self.server:
            self.server.should_exit = True
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        logger.info("Synthetic Mock Portal stopped.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
