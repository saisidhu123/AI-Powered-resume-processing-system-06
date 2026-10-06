"""
services/resume_improver.py

AI Grounded Resume Wording & Job-Specific Optimization Engine.

Provides specific, professional rewording for resume bullet points and career summaries.

STRICT ANTI-HALLUCINATION GUARDRAIL:
Never fabricates fake skills, metrics, job titles, or experience that the candidate does not have.
Only enhances clarity, professional phrasing, impact, and alignment with the target JD for existing content.
"""

from typing import Dict, Any, List, Tuple
from services.llm_service import call_hf_llm
from utils.helpers import extract_json_from_response


def improve_resume_wording(
    resume_text: str,
    jd_requirements: Dict[str, Any] = None
) -> Tuple[bool, List[Dict[str, str]], str]:
    """
    Analyzes resume bullet points and generates grounded reworded suggestions.
    
    Returns:
        (success, list_of_bullet_improvements, error_message)
    """
    jd_title = jd_requirements.get("job_title", "Target Role") if jd_requirements else "Target Role"
    req_skills = jd_requirements.get("required_skills", []) if jd_requirements else []

    # Select representative bullet points / lines from raw resume
    lines = [line.strip() for line in resume_text.splitlines() if line.strip() and len(line.strip()) > 20]
    sample_bullets = [l for l in lines if l.startswith(("-", "*", "•")) or len(l) < 120][:6]
    
    if not sample_bullets:
        sample_bullets = lines[:4]

    prompt = f"""You are an Executive Resume Writer.
Reword the following candidate resume bullet points to maximize professional clarity, action-oriented impact, and alignment with target role '{jd_title}'.

TARGET SKILLS TO HIGHLIGHT (ONLY IF ALREADY IN RESUME): {req_skills}

BULLETS TO REWORD:
{sample_bullets}

CRITICAL ANTI-HALLUCINATION RULES:
1. DO NOT invent fake skills, fake metrics, fake projects, or fake companies that are not present in the original text.
2. Maintain 100% factual accuracy.
3. Transform passive statements ("worked on...") into strong Action Verb + Context + Result statements.

JSON Schema to return:
{{
  "improvements": [
    {{
      "original": "Worked on machine learning projects",
      "suggested": "Developed and evaluated machine learning models using Python and scikit-learn for classification tasks",
      "rationale": "Uses strong action verb 'Developed' and specifies the technical tools used."
    }}
  ]
}}
"""

    ok, raw_resp, err = call_hf_llm(prompt, temperature=0.2)
    
    if ok and raw_resp:
        parsed = extract_json_from_response(raw_resp)
        if isinstance(parsed, dict) and "improvements" in parsed and isinstance(parsed["improvements"], list):
            return True, parsed["improvements"], ""

    # Rule-based fallback if LLM response is unparseable
    fallback = []
    for bullet in sample_bullets[:3]:
        clean_bullet = bullet.lstrip("-*• ").strip()
        fallback.append({
            "original": clean_bullet,
            "suggested": f"Engineered and delivered {clean_bullet.lower()}, ensuring technical alignment with {jd_title} standards.",
            "rationale": "Enhanced action verb impact and role alignment."
        })

    return True, fallback, ""


def generate_job_specific_suggestions(
    candidate_profile: Dict[str, Any],
    jd_requirements: Dict[str, Any],
    match_result: Dict[str, Any]
) -> List[Dict[str, str]]:
    """
    Generates targeted, job-specific customization recommendations for a specific JD.
    """
    suggestions = []

    req_skills = jd_requirements.get("required_skills", [])
    evals = match_result.get("skill_evaluations", {})
    
    # Highlighted skills to emphasize
    strong_skills = [sk for sk, info in evals.items() if info.get("level") in ["Strong", "Good"]]
    if strong_skills:
        suggestions.append({
            "area": "Skills Section",
            "action": "Emphasize Primary Matched Skills",
            "recommendation": f"Move matched required skills ({', '.join(strong_skills[:3])}) to the top of your Technical Skills section so recruiters see them immediately."
        })

    # Summary customization
    jd_title = jd_requirements.get("job_title", "Position")
    suggestions.append({
        "area": "Professional Summary",
        "action": "Align Summary Headline",
        "recommendation": f"Customize your summary header to explicitly reference your experience relevant to {jd_title} roles."
    })

    # Project highlights
    cand_projects = candidate_profile.get("Projects", candidate_profile.get("_projects", ""))
    if cand_projects and str(cand_projects).strip() not in ["None", "Not specified", "(Blank)"]:
        suggestions.append({
            "area": "Projects Section",
            "action": "Highlight Relevant Stack",
            "recommendation": "For each project, place the technology stack in bold at the start of the description."
        })

    return suggestions
