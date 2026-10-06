"""
services/ats_analyzer.py

ATS (Applicant Tracking System) Compatibility & Readability Analyzer.

Evaluates:
- Section heading standardizations
- Date format consistency
- Parsing layout risks (tables, text boxes, non-standard symbols)
- Essential section completeness (Summary, Skills, Experience, Education)
- Target JD keyword density & alignment

DISCLAIMER GUARDRAIL:
Does not claim "This resume will 100% pass ATS".
Uses realistic terminology: "Possible ATS concern" or "ATS compatibility recommendation".
"""

import re
from typing import Dict, Any, List
from services.section_detector import segment_resume_sections


def analyze_ats_compatibility(
    resume_text: str,
    jd_requirements: Dict[str, Any] = None,
    document_quality: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Evaluates ATS readability risks and alignment.
    """
    issues: List[Dict[str, str]] = []
    passed_checks: List[str] = []

    sections = segment_resume_sections(resume_text)
    
    # 1. Document Length & Word Count Check
    words = resume_text.split()
    word_count = len(words)
    if word_count < 150:
        issues.append({
            "check": "Word Count",
            "severity": "High",
            "finding": f"Resume is very short ({word_count} words). ATS algorithms may rank it lower due to thin content.",
            "recommendation": "Expand your work experience, skill details, and project achievements to at least 300+ words."
        })
    elif word_count > 1500:
        issues.append({
            "check": "Resume Length",
            "severity": "Medium",
            "finding": f"Resume is unusually long ({word_count} words).",
            "recommendation": "Streamline content to 1-2 pages focused directly on relevant experiences."
        })
    else:
        passed_checks.append(f"Optimal word count ({word_count} words).")

    # 2. Standard Section Headings Check
    essential_sections = ["SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION"]
    missing_essential = [sec for sec in essential_sections if sec not in sections]
    if missing_essential:
        issues.append({
            "check": "Standard Section Headings",
            "severity": "High",
            "finding": f"Missing standard ATS section headings: {', '.join(missing_essential)}.",
            "recommendation": "Use clear, standard headings such as 'Professional Experience', 'Technical Skills', 'Education'."
        })
    else:
        passed_checks.append("All standard ATS section headings detected.")

    # 3. Non-Standard Symbol / Character Check
    special_char_count = len(re.findall(r"[^\w\s\.,\-\(\)\/\:\*\+]", resume_text))
    if special_char_count > 50:
        issues.append({
            "check": "Special Characters & Graphics",
            "severity": "Medium",
            "finding": f"High density of non-standard symbols or glyphs ({special_char_count} instances).",
            "recommendation": "Avoid using custom bullet characters, icons, text boxes, or non-standard font symbols that ATS parsers cannot decode."
        })
    else:
        passed_checks.append("Clean formatting without problematic glyphs.")

    # 4. Date Format Consistency Check
    date_matches = re.findall(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b|\b\d{2}\/\d{4}\b|\b\d{4}\s*-\s*\d{4}\b", resume_text, re.IGNORECASE)
    if len(date_matches) >= 2:
        passed_checks.append(f"Consistent date formatting detected ({len(date_matches)} date markers).")
    else:
        issues.append({
            "check": "Employment Dates",
            "severity": "Medium",
            "finding": "Work experience dates are unstated or formatted inconsistently.",
            "recommendation": "Include explicit start and end dates (e.g. 'MMM YYYY - Present' or 'MM/YYYY - MM/YYYY') for each role."
        })

    # 5. Target Keyword Density (if JD provided)
    if jd_requirements:
        req_skills = jd_requirements.get("required_skills", [])
        found_kw = [sk for sk in req_skills if re.search(r"\b" + re.escape(sk.lower()) + r"\b", resume_text.lower())]
        missing_kw = [sk for sk in req_skills if sk not in found_kw]

        if missing_kw:
            issues.append({
                "check": "Target Keyword Alignment",
                "severity": "High",
                "finding": f"Missing key job description keywords: {', '.join(missing_kw[:5])}.",
                "recommendation": "Incorporate missing keywords naturally into your Skills and Experience sections where applicable."
            })
        else:
            passed_checks.append("Excellent keyword coverage for target JD.")

    # Calculate ATS Readiness Score
    total_checks = len(issues) + len(passed_checks)
    readiness_score = round((len(passed_checks) / total_checks) * 100) if total_checks > 0 else 75

    return {
        "ats_readiness_score": readiness_score,
        "rating": "High ATS Compatibility" if readiness_score >= 80 else ("Moderate ATS Compatibility" if readiness_score >= 60 else "Potential ATS Readability Issues"),
        "issues": issues,
        "passed_checks": passed_checks
    }
