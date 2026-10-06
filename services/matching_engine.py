"""
services/matching_engine.py

Comprehensive Resume vs Job Description Matching Engine.

Coordinates:
- Structured Candidate Profile Extraction
- JD Requirement Evaluation
- Semantic Skill & Experience Verification
- Grounded Evidence Extraction
- Transparent Score Calculation
- Strengths & Gaps Synthesis

Designed to be completely decoupled from UI code and fully reusable across single screening,
batch ranking, candidate comparison, and candidate search.
"""

from typing import Dict, Any, Tuple, List, Optional
from services.jd_parser import parse_job_description
from services.evidence_extractor import extract_all_evidence
from services.scoring_engine import evaluate_candidate_match
from services.llm_service import call_hf_llm
from utils.helpers import extract_json_from_response


def match_resume_to_jd(
    candidate_profile: Dict[str, Any],
    resume_text: str,
    jd_source: Any,  # Can be raw JD text or parsed JD dict
    custom_weights: Optional[Dict[str, float]] = None
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Evaluates a candidate's resume against a target Job Description.
    
    Returns:
        (success, match_result_dict, error_message)
    """
    if not candidate_profile or not resume_text:
        return False, {}, "Candidate profile or resume text is missing."

    # Step 1: Ensure JD is parsed into structured requirements
    if isinstance(jd_source, dict) and "required_skills" in jd_source:
        jd_requirements = jd_source
    else:
        ok_jd, jd_requirements, err_jd = parse_job_description(str(jd_source))
        if not ok_jd:
            return False, {}, f"Failed to parse Job Description: {err_jd}"

    req_skills = jd_requirements.get("required_skills", [])
    pref_skills = jd_requirements.get("preferred_skills", [])
    all_target_skills = list(dict.fromkeys(req_skills + pref_skills))

    # Step 2: Extract Grounded Evidence from resume text
    evidence_map = extract_all_evidence(all_target_skills, resume_text)

    # Step 3: Semantic LLM Verification for Skill Levels (Strong / Good / Limited / Missing)
    skill_evaluations: Dict[str, Dict[str, Any]] = {}
    
    # Pre-populate with deterministic evidence evaluation
    for sk in all_target_skills:
        ev = evidence_map.get(sk, {})
        skill_evaluations[sk] = {
            "level": ev.get("match_level", "Missing"),
            "evidence": ev.get("snippet", ""),
            "section": ev.get("section", "UNKNOWN")
        }

    # Step 4: Run Scoring Engine with deterministic formula
    scoring_res = evaluate_candidate_match(
        candidate_profile=candidate_profile,
        jd_requirements=jd_requirements,
        skill_evaluations=skill_evaluations,
        weights=custom_weights
    )

    # Build final match result object
    match_result = {
        "candidate_name": candidate_profile.get("Candidate Name", candidate_profile.get("name", "Unknown Candidate")),
        "job_title": jd_requirements.get("job_title", "Target Role"),
        "overall_match_score": scoring_res["overall_score"],
        "scoring_breakdown": scoring_res["scoring_breakdown"],
        "strengths": scoring_res["strengths"],
        "gaps": scoring_res["gaps"],
        "skill_evaluations": skill_evaluations,
        "evidence_map": evidence_map,
        "jd_requirements": jd_requirements,
        "experience_evaluation": {
            "candidate_years": candidate_profile.get("Total Experience (Years)", 0),
            "required_years": jd_requirements.get("required_experience_years", 0),
            "status": "Met" if scoring_res["scoring_breakdown"]["experience"]["score"] >= 20.0 else "Gap"
        }
    }

    return True, match_result, ""
