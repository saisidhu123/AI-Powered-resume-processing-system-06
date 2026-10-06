"""
services/candidate_analyzer.py

Candidate-Facing Resume Section & Rejection Factors Analyzer.

Analyzes individual resume sections:
- Professional Summary / Objective
- Technical & Core Skills
- Work Experience / History
- Projects
- Education & Qualifications
- Certifications

Also identifies POSSIBLE reasons why a resume may not be getting shortlisted for a target JD.

DISCLAIMER GUARDRAIL:
Explicitly states that rejection reasons are POSSIBLE factors since only actual employers
know specific rejection criteria unless feedback was provided.
"""

from typing import Dict, Any, List, Tuple
from services.section_detector import segment_resume_sections
from services.llm_service import call_hf_llm
from utils.helpers import extract_json_from_response


def analyze_resume_sections(
    resume_text: str,
    jd_requirements: Dict[str, Any] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Analyzes each major section of a candidate's resume and provides actionable feedback.
    """
    sections = segment_resume_sections(resume_text)
    jd_title = jd_requirements.get("job_title", "Target Position") if jd_requirements else "Target Position"
    req_skills = jd_requirements.get("required_skills", []) if jd_requirements else []

    prompt = f"""You are a Career Coach & Resume Expert.
Analyze the following resume sections against target position '{jd_title}'.

RESUME SECTIONS EXTRACTED:
{sections}

TARGET JD REQUIRED SKILLS: {req_skills}

For each section present in the resume (SUMMARY, SKILLS, EXPERIENCE, PROJECTS, EDUCATION, CERTIFICATIONS), provide:
1. "good": What is well-presented.
2. "weak": What is weak or missing.
3. "improvement_suggestion": Actionable advice to strengthen this section for '{jd_title}'.
4. "jd_relevance": High / Medium / Low.

JSON Schema:
{{
  "SUMMARY": {{ "good": "Clear overview", "weak": "Lacks specific metrics", "improvement_suggestion": "Quantify past achievements", "jd_relevance": "High" }},
  "SKILLS": {{ "good": "Good technical range", "weak": "Missing cloud tools", "improvement_suggestion": "Group by category (Languages, Databases, Tools)", "jd_relevance": "High" }},
  "EXPERIENCE": {{ "good": "Relevant job titles", "weak": "Bullet points read like job duties rather than results", "improvement_suggestion": "Use Action Verb + Impact + Metric format", "jd_relevance": "High" }},
  "PROJECTS": {{ "good": "Hands-on projects listed", "weak": "Repository links or live demos missing", "improvement_suggestion": "Include technology stack details for each project", "jd_relevance": "Medium" }},
  "EDUCATION": {{ "good": "Degree clearly stated", "weak": "Graduation year or major unstated", "improvement_suggestion": "State degree and field of study clearly", "jd_relevance": "Medium" }},
  "CERTIFICATIONS": {{ "good": "Listed", "weak": "Missing target certs", "improvement_suggestion": "Add issuer and completion date", "jd_relevance": "Low" }}
}}
"""

    ok, raw_resp, err = call_hf_llm(prompt, temperature=0.1)
    
    if ok and raw_resp:
        parsed = extract_json_from_response(raw_resp)
        if isinstance(parsed, dict) and any(k in parsed for k in ["SUMMARY", "SKILLS", "EXPERIENCE"]):
            return parsed

    # Rule-based fallback if LLM response is unparseable
    fallback_analysis = {}
    for sec_name, sec_text in sections.items():
        if sec_name in ["HEADER", "NOTICE_PERIOD", "COMPENSATION"]:
            continue
        fallback_analysis[sec_name] = {
            "good": f"Section contains {len(sec_text.splitlines())} line(s) of content.",
            "weak": "Could benefit from stronger action verbs and quantifiable results.",
            "improvement_suggestion": f"Tailor your {sec_name.lower()} section to highlight keywords from the job description.",
            "jd_relevance": "High" if sec_name in ["SKILLS", "EXPERIENCE"] else "Medium"
        }

    return fallback_analysis


def identify_possible_mismatch_reasons(
    match_result: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    jd_requirements: Dict[str, Any]
) -> List[Dict[str, str]]:
    """
    Identifies POSSIBLE factors why candidate's resume may not match the target JD.
    
    DISCLAIMER: Always states that these are potential factors and not official employer feedback.
    """
    reasons = []

    # 1. Missing Required Skills
    gaps = match_result.get("gaps", [])
    missing_skills = [g.replace("Missing required skill: ", "") for g in gaps if "Missing required skill:" in g]
    if missing_skills:
        reasons.append({
            "category": "Skill Gap",
            "reason": f"Required skills missing: {', '.join(missing_skills[:4])}.",
            "impact": "High",
            "suggestion": "If you possess any of these skills, ensure they are explicitly listed in your Skills and Experience sections."
        })

    # 2. Experience Gap
    exp_eval = match_result.get("experience_evaluation", {})
    if exp_eval.get("status") == "Gap":
        cand_yrs = exp_eval.get("candidate_years", 0)
        req_yrs = exp_eval.get("required_years", 0)
        reasons.append({
            "category": "Experience Level",
            "reason": f"JD requires {req_yrs} years of experience, but your resume demonstrates {cand_yrs} years.",
            "impact": "High",
            "suggestion": "Emphasize key responsibilities, project ownership, and depth of technical involvement to demonstrate senior-level capability."
        })

    # 3. Generic Wording or Duty-focused Bullets
    cand_projects = candidate_profile.get("Projects", candidate_profile.get("_projects", ""))
    if not cand_projects or str(cand_projects).strip() in ["None", "Not specified", "(Blank)"]:
        reasons.append({
            "category": "Project Evidence",
            "reason": "Resume lacks detailed technical projects demonstrating hands-on skill application.",
            "impact": "Medium",
            "suggestion": "Add 2-3 technical project descriptions detailing the stack used, your specific role, and measurable outcomes."
        })

    # 4. Certification / Education Gap
    cert_gaps = [g for g in gaps if "certification" in g.lower() or "education" in g.lower()]
    if cert_gaps:
        reasons.append({
            "category": "Qualifications",
            "reason": cert_gaps[0],
            "impact": "Low",
            "suggestion": "List ongoing certifications or relevant coursework alignable with the role."
        })

    if not reasons:
        reasons.append({
            "category": "Strong Match",
            "reason": "Your resume shows strong overall alignment with this position. Any non-shortlisting would depend on external candidate pool competition.",
            "impact": "Info",
            "suggestion": "Focus on customizing your cover summary and preparing for technical interview rounds."
        })

    return reasons
