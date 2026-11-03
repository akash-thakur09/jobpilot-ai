from typing import Optional, Dict, Any


def normalize_job_salary_to_lpa(
    salary_val: Optional[float],
    currency: Optional[str] = "INR",
) -> Optional[float]:
    """
    Normalizes an Indian job salary amount to annual INR in Lakhs Per Annum (LPA).
    Returns None for foreign currencies or missing values to avoid false comparisons.
    """
    if salary_val is None or salary_val <= 0:
        return None

    curr = (currency or "INR").upper().strip()
    if curr != "INR":
        # Foreign currency (e.g. USD, EUR, GBP) - do not falsely interpret as INR LPA
        return None

    # Already in LPA format (e.g. 6.0, 10.5, 25.0 LPA)
    if salary_val < 200.0:
        return round(float(salary_val), 2)

    # Annual INR figure (e.g. 600,000 -> 6.0 LPA; 1,800,000 -> 18.0 LPA)
    if salary_val >= 100_000.0:
        return round(float(salary_val) / 100_000.0, 2)

    # Monthly INR amount (e.g. 50,000 to 99,999 / month -> 6.0 to 11.99 LPA)
    if 10_000.0 <= salary_val < 100_000.0:
        return round((float(salary_val) * 12.0) / 100_000.0, 2)

    return None


def evaluate_salary_compatibility(
    job_salary_min: Optional[float],
    job_salary_max: Optional[float],
    job_currency: Optional[str] = "INR",
    candidate_min_lpa: Optional[float] = None,
    candidate_min_usd: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Safely evaluates salary compatibility between a job posting and a candidate.
    - Missing salary is treated as UNDISCLOSED (neutral, never rejects).
    - Foreign currency against INR LPA target is treated as FOREIGN_CURRENCY (neutral, never false mismatch).
    - LPA ranges are checked against target LPA.
    """
    curr = (job_currency or "USD").upper().strip()
    has_job_salary = (job_salary_min is not None and job_salary_min > 0) or (
        job_salary_max is not None and job_salary_max > 0
    )

    # 1. Undisclosed salary
    if not has_job_salary:
        return {
            "status": "UNDISCLOSED",
            "satisfies_target": None,
            "is_compatible": True,
            "score": 75.0,
            "explanation": "Compensation not disclosed; evaluated neutrally without penalty",
        }

    # 2. Candidate has target INR LPA
    if candidate_min_lpa is not None and candidate_min_lpa > 0:
        if curr != "INR":
            # Foreign currency: do not compare numerically to INR LPA
            return {
                "status": "FOREIGN_CURRENCY",
                "satisfies_target": None,
                "is_compatible": True,
                "score": 75.0,
                "explanation": f"Disclosed in foreign currency ({curr}); evaluated neutrally without assuming mismatch",
            }

        job_min_lpa = normalize_job_salary_to_lpa(job_salary_min, curr)
        job_max_lpa = normalize_job_salary_to_lpa(job_salary_max, curr)

        # If job has max LPA that is below candidate min
        if job_max_lpa is not None and job_max_lpa < candidate_min_lpa:
            deficit_pct = (candidate_min_lpa - job_max_lpa) / candidate_min_lpa
            score = max(20.0, round(70.0 - (deficit_pct * 100.0), 1))
            return {
                "status": "BELOW_TARGET",
                "satisfies_target": False,
                "is_compatible": False,
                "score": score,
                "explanation": f"Disclosed package ({job_max_lpa} LPA) is below target minimum of {candidate_min_lpa} LPA",
                "job_min_lpa": job_min_lpa,
                "job_max_lpa": job_max_lpa,
            }

        # If job meets target (either max >= target or min >= target)
        if (job_max_lpa is not None and job_max_lpa >= candidate_min_lpa) or (
            job_min_lpa is not None and job_min_lpa >= candidate_min_lpa
        ):
            return {
                "status": "MEETS_TARGET",
                "satisfies_target": True,
                "is_compatible": True,
                "score": 95.0,
                "explanation": f"Disclosed package meets minimum target of {candidate_min_lpa} LPA",
                "job_min_lpa": job_min_lpa,
                "job_max_lpa": job_max_lpa,
            }

        # Disclosed but could not be parsed to LPA
        return {
            "status": "UNDETERMINED",
            "satisfies_target": None,
            "is_compatible": True,
            "score": 75.0,
            "explanation": "Compensation disclosed but format not recognized; evaluated neutrally",
        }

    # 3. Fallback for legacy USD preference if candidate has no LPA but has USD target
    if candidate_min_usd is not None and candidate_min_usd > 0:
        if curr == "USD":
            if job_salary_max and job_salary_max < candidate_min_usd:
                deficit_pct = (candidate_min_usd - job_salary_max) / candidate_min_usd
                score = max(10.0, round(70.0 - (deficit_pct * 100.0), 1))
                return {
                    "status": "BELOW_TARGET",
                    "satisfies_target": False,
                    "is_compatible": False,
                    "score": score,
                    "explanation": f"Disclosed salary (${job_salary_max:,.0f}) is below target minimum of ${candidate_min_usd:,.0f}",
                }
            if (job_salary_max and job_salary_max >= candidate_min_usd) or (
                job_salary_min and job_salary_min >= candidate_min_usd
            ):
                return {
                    "status": "MEETS_TARGET",
                    "satisfies_target": True,
                    "is_compatible": True,
                    "score": 95.0,
                    "explanation": f"Disclosed salary meets minimum requirement of ${candidate_min_usd:,.0f}",
                }

    # 4. No salary preference specified
    return {
        "status": "NO_PREFERENCE",
        "satisfies_target": None,
        "is_compatible": True,
        "score": 80.0,
        "explanation": "No minimum compensation preference specified",
    }

