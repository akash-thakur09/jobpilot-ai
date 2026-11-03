import re
import html
from typing import Optional, Tuple, List, Dict, Any
from backend.app.models.enums import RemoteType


def strip_html_tags(text: Optional[str]) -> str:
    """
    Strips raw HTML tags, scripts, and unescapes entities safely.
    """
    if not text:
        return ""
    # Remove script and style tags and contents
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", str(text))
    # Remove remaining HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Collapse whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    return html.unescape(cleaned).strip()


def sanitize_canonical_url(url: Optional[str], fallback_domain: str, external_id: str) -> str:
    """
    Validates canonical URL ensuring HTTP/HTTPS protocol, with deterministic fallback.
    """
    if url and isinstance(url, str):
        cleaned = url.strip()
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned
    return f"https://www.{fallback_domain}.com/job/{external_id}"


def parse_inr_salary_text(text: Optional[str]) -> Tuple[Optional[float], Optional[float], str]:
    """
    Parses compensation text commonly found on Indian job boards into min and max annual figures.
    Returns (salary_min_lpa, salary_max_lpa, currency).
    Figures under 200 are interpreted as LPA (Lakhs Per Annum).
    """
    if not text or not str(text).strip():
        return None, None, "INR"

    cleaned = strip_html_tags(str(text))
    lowered = cleaned.lower()

    if any(term in lowered for term in ["not disclosed", "undisclosed", "confidential", "best in industry"]):
        return None, None, "INR"

    # Check for USD / EUR / GBP foreign currencies
    if "$" in cleaned or "usd" in lowered:
        usd_matches = re.findall(r"(\d+(?:,\d{3})*(?:\.\d+)?)", cleaned.replace(",", ""))
        if len(usd_matches) >= 2:
            return float(usd_matches[0]), float(usd_matches[1]), "USD"
        elif len(usd_matches) == 1:
            return float(usd_matches[0]), float(usd_matches[0]), "USD"
        return None, None, "USD"

    # Monthly salary: e.g. "50,000 - 80,000 per month" or "/ month"
    if "month" in lowered:
        inr_cleaned = cleaned.replace("₹", "").replace("rs.", "").replace("rs", "").replace(",", "").strip()
        month_vals = re.findall(r"(\d+(?:\.\d+)?)", inr_cleaned)
        if len(month_vals) >= 2:
            m1 = float(month_vals[0]) * 12.0 / 100_000.0
            m2 = float(month_vals[1]) * 12.0 / 100_000.0
            return round(min(m1, m2), 2), round(max(m1, m2), 2), "INR"
        elif len(month_vals) == 1:
            m = float(month_vals[0]) * 12.0 / 100_000.0
            return round(m, 2), round(m, 2), "INR"

    # Check for LPA / Lacs / Lakhs pattern: e.g. "12 - 25 Lacs P.A.", "15-28 LPA", "6.5 LPA"
    lpa_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:lacs|lac|lakhs|lakh|lpa|pa|p\.a\.)?",
        lowered,
    )
    if lpa_match and ("lpa" in lowered or "lac" in lowered or "lakh" in lowered or "p.a" in lowered or "pa" in lowered):
        min_val = float(lpa_match.group(1))
        max_val = float(lpa_match.group(2))
        return min(min_val, max_val), max(min_val, max_val), "INR"

    single_lpa = re.search(r"(\d+(?:\.\d+)?)\s*(?:lacs|lac|lakhs|lakh|lpa)", lowered)
    if single_lpa:
        val = float(single_lpa.group(1))
        return val, val, "INR"

    # Check for full annual INR amounts: e.g. "₹ 15,00,000 - ₹ 25,00,000" or "1500000 - 2500000"
    inr_cleaned = cleaned.replace("₹", "").replace("rs.", "").replace("rs", "").replace(",", "").strip()
    full_inr = re.findall(r"(\d{5,8})", inr_cleaned)
    if len(full_inr) >= 2:
        val1 = float(full_inr[0]) / 100_000.0
        val2 = float(full_inr[1]) / 100_000.0
        return min(val1, val2), max(val1, val2), "INR"
    elif len(full_inr) == 1:
        val = float(full_inr[0]) / 100_000.0
        return val, val, "INR"

    return None, None, "INR"


def parse_experience_text(text: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """
    Parses experience text (e.g. '2-5 Yrs', '3 - 6 Years', '5+ Yrs') into (min_yrs, max_yrs).
    """
    if not text:
        return None, None

    cleaned = strip_html_tags(str(text)).lower().strip()
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:yrs|years|year|yr)?", cleaned)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))

    single_match = re.search(r"(\d+(?:\.\d+)?)\+?\s*(?:yrs|years|year|yr)", cleaned)
    if single_match:
        return float(single_match.group(1)), None

    return None, None


def parse_location_and_remote(location_text: Optional[str]) -> Tuple[str, RemoteType]:
    """
    Extracts location name and RemoteType from Indian location descriptions.
    """
    if not location_text:
        return "India", RemoteType.UNKNOWN

    raw = strip_html_tags(str(location_text))
    lowered = raw.lower()

    # Determine remote type
    if "hybrid" in lowered:
        remote_type = RemoteType.HYBRID
    elif "remote" in lowered or "work from home" in lowered or "wfh" in lowered:
        remote_type = RemoteType.REMOTE
    elif any(city in lowered for city in [
        "bengaluru", "bangalore", "pune", "hyderabad", "gurugram", "gurgaon",
        "noida", "mumbai", "delhi", "chennai", "kolkata", "ahmedabad"
    ]):
        remote_type = RemoteType.ON_SITE
    else:
        remote_type = RemoteType.UNKNOWN

    # Clean location city
    clean_loc = re.sub(r"\(.*?\)", "", raw).strip()
    clean_loc = re.sub(r"(?i)\b(remote|hybrid|wfh|work from home|onsite|on-site)\b", "", clean_loc).strip()
    clean_loc = clean_loc.strip(" ,/-")
    if not clean_loc:
        clean_loc = "Remote" if remote_type == RemoteType.REMOTE else "India"

    return clean_loc, remote_type


def parse_email_alert_jobs(payload_text: str, source_identifier: str) -> List[Dict[str, Any]]:
    """
    Parses raw email alert text, HTML, or structured JSON text into raw job dictionaries.
    Strips raw HTML tags and sanitizes fields.
    """
    import json
    results: List[Dict[str, Any]] = []

    # If valid JSON string
    stripped = payload_text.strip()
    if (stripped.startswith("[") and stripped.endswith("]")) or (
        stripped.startswith("{") and stripped.endswith("}")
    ):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                for idx, item in enumerate(parsed):
                    if isinstance(item, dict):
                        item.setdefault("id", f"{source_identifier}_{idx+1}")
                        results.append(item)
                return results
            elif isinstance(parsed, dict) and "jobs" in parsed and isinstance(parsed["jobs"], list):
                for idx, item in enumerate(parsed["jobs"]):
                    if isinstance(item, dict):
                        item.setdefault("id", f"{source_identifier}_{idx+1}")
                        results.append(item)
                return results
        except Exception:
            pass

    # Strip excessive HTML containers if raw email HTML is provided
    sanitized_text = strip_html_tags(payload_text)

    # Deterministic line / regex parser for email alert text
    cards = re.split(r"(?:\r?\n\s*\r?\n|\-{3,}|\={3,})", sanitized_text)
    for idx, card in enumerate(cards):
        card = card.strip()
        if len(card) < 20:
            continue

        title_m = re.search(r"(?:title|role|position|job)\s*:\s*([^\r\n]+)", card, re.I)
        comp_m = re.search(r"(?:company|employer|organization)\s*:\s*([^\r\n]+)", card, re.I)
        loc_m = re.search(r"(?:location|city)\s*:\s*([^\r\n]+)", card, re.I)
        sal_m = re.search(r"(?:salary|ctc|package|compensation)\s*:\s*([^\r\n]+)", card, re.I)
        exp_m = re.search(r"(?:exp|experience)\s*:\s*([^\r\n]+)", card, re.I)
        url_m = re.search(r"(?:url|link|apply)\s*:\s*(https?://[^\s\r\n]+)", card, re.I)
        skills_m = re.search(r"(?:skills|tech stack|tags)\s*:\s*([^\r\n]+)", card, re.I)

        title = title_m.group(1).strip() if title_m else None
        company = comp_m.group(1).strip() if comp_m else None

        # Fallback heuristic: First line is title, second line is company
        if not title:
            lines = [l.strip() for l in card.splitlines() if l.strip()]
            if lines and len(lines) >= 2:
                title = lines[0]
                company = lines[1] if not comp_m else comp_m.group(1).strip()

        if title and company:
            raw_url = url_m.group(1).strip() if url_m else None
            safe_url = sanitize_canonical_url(raw_url, source_identifier, f"alert_{idx+1}")

            results.append({
                "id": f"{source_identifier}_alert_{idx+1}",
                "title": strip_html_tags(title),
                "company": strip_html_tags(company),
                "location": strip_html_tags(loc_m.group(1).strip()) if loc_m else "India",
                "salary_text": sal_m.group(1).strip() if sal_m else None,
                "experience_text": exp_m.group(1).strip() if exp_m else None,
                "url": safe_url,
                "skills": [strip_html_tags(s.strip()) for s in skills_m.group(1).split(",")] if skills_m else [],
                "description": card,
            })

    return results
