"""
services/scoring_engine.py

Transparent, Deterministic Resume vs Job Description Scoring Engine.

Calculates candidate match scores using configurable category weights:
- Required Skills (Default: 40%)
- Experience Match (Default: 25%)
- Preferred Skills (Default: 15%)
- Education Match (Default: 10%)
- Certifications (Default: 5%)
- Projects & Relevant Experience (Default: 5%)

Strictly avoids arbitrary LLM guesses; computes reproducible scores grounded in candidate data.
"""

from typing import Dict, Any, List, Tuple

DEFAULT_WEIGHTS = {
    "required_skills": 40.0,
    "experience": 25.0,
    "preferred_skills": 15.0,
    "education": 10.0,
    "certifications": 5.0,
    "projects_other": 5.0
}


def evaluate_candidate_match(
    candidate_profile: Dict[str, Any],
    jd_requirements: Dict[str, Any],
    skill_evaluations: Dict[str, Dict[str, Any]],
    weights: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Evaluates candidate against JD requirements and returns transparent score breakdown.
    
    Args:
        candidate_profile: Structured dict with Candidate Name, Experience, Skills, Education, Certs, Projects.
        jd_requirements: Structured dict with required_skills, preferred_skills, required_experience_years, etc.
        skill_evaluations: Dict mapping skill names to {"level": "Strong"|"Good"|"Limited"|"Missing"|"Unknown", "evidence": "..."}
        weights: Optional custom category weights (must sum to 100.0)
        
    Returns:
        Structured evaluation dict with overall_score, breakdown, strengths, gaps.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS.copy()
        
    # Ensure weight normalization
    total_w = sum(weights.values()) or 100.0
    norm_weights = {k: (v / total_w) * 100.0 for k, v in weights.items()}

    strengths: List[str] = []
    gaps: List[str] = []

    # 1. EVALUATE REQUIRED SKILLS (Max: norm_weights['required_skills'])
    req_skills = jd_requirements.get("required_skills", [])
    max_req_w = norm_weights["required_skills"]
    
    req_score = 0.0
    req_matched_count = 0
    
    if req_skills:
        per_skill_val = max_req_w / len(req_skills)
        for sk in req_skills:
            eval_info = skill_evaluations.get(sk, {})
            lvl = eval_info.get("level", "Missing")
            
            if lvl == "Strong":
                req_score += per_skill_val * 1.0
                req_matched_count += 1
            elif lvl == "Good":
                req_score += per_skill_val * 0.8
                req_matched_count += 1
            elif lvl == "Limited":
                req_score += per_skill_val * 0.5
                req_matched_count += 1
            elif lvl == "Missing":
                gaps.append(f"Missing required skill: {sk}")
            else: # Unknown
                gaps.append(f"Required skill unverified: {sk}")
                
        if req_matched_count > 0:
            strengths.append(f"Matched {req_matched_count}/{len(req_skills)} required technical skills")
    else:
        req_score = max_req_w  # Default if no specific required skills listed

    # 2. EVALUATE PREFERRED SKILLS (Max: norm_weights['preferred_skills'])
    pref_skills = jd_requirements.get("preferred_skills", [])
    max_pref_w = norm_weights["preferred_skills"]
    
    pref_score = 0.0
    pref_matched_count = 0
    
    if pref_skills:
        per_pref_val = max_pref_w / len(pref_skills)
        for sk in pref_skills:
            eval_info = skill_evaluations.get(sk, {})
            lvl = eval_info.get("level", "Missing")
            
            if lvl in ["Strong", "Good"]:
                pref_score += per_pref_val * 1.0
                pref_matched_count += 1
            elif lvl == "Limited":
                pref_score += per_pref_val * 0.5
                pref_matched_count += 1
                
        if pref_matched_count > 0:
            strengths.append(f"Demonstrates preferred skills ({pref_matched_count}/{len(pref_skills)})")
    else:
        pref_score = max_pref_w

    # 3. EVALUATE EXPERIENCE (Max: norm_weights['experience'])
    max_exp_w = norm_weights["experience"]
    cand_exp = candidate_profile.get("Total Experience (Years)", candidate_profile.get("years_of_experience", 0))
    try:
        cand_exp_val = float(str(cand_exp).replace("+", "").replace("years", "").replace("yrs", "").strip())
    except Exception:
        cand_exp_val = 0.0

    req_exp_val = jd_requirements.get("required_experience_years")
    if req_exp_val is None or str(req_exp_val).strip() == "":
        req_exp_val = 0.0
    else:
        try:
            req_exp_val = float(req_exp_val)
        except Exception:
            req_exp_val = 0.0

    if req_exp_val == 0:
        exp_score = max_exp_w
        if cand_exp_val > 0:
            strengths.append(f"Has {cand_exp_val:.1f} years of relevant experience")
    else:
        if cand_exp_val >= req_exp_val:
            exp_score = max_exp_w
            strengths.append(f"Meets or exceeds experience requirement ({cand_exp_val:.1f} yrs vs {req_exp_val:.1f} yrs required)")
        elif cand_exp_val > 0:
            ratio = cand_exp_val / req_exp_val
            exp_score = max_exp_w * max(0.4, ratio)
            gaps.append(f"Has {cand_exp_val:.1f} years experience (less than {req_exp_val:.1f} years required)")
        else:
            exp_score = 0.0
            gaps.append(f"No clear experience details found (requires {req_exp_val:.1f} years)")

    # 4. EVALUATE EDUCATION (Max: norm_weights['education'])
    max_edu_w = norm_weights["education"]
    cand_edu = str(candidate_profile.get("Education", "")).strip()
    req_edu_list = jd_requirements.get("education_requirements", [])
    
    if not req_edu_list or not any(req_edu_list):
        edu_score = max_edu_w
    else:
        if cand_edu and cand_edu != "Not specified" and cand_edu != "(Blank)":
            edu_score = max_edu_w
            strengths.append(f"Education requirement satisfied ({cand_edu})")
        else:
            edu_score = max_edu_w * 0.5
            gaps.append("Education background not explicitly detailed")

    # 5. EVALUATE CERTIFICATIONS (Max: norm_weights['certifications'])
    max_cert_w = norm_weights["certifications"]
    cand_certs = str(candidate_profile.get("Certifications", "")).strip()
    req_certs = jd_requirements.get("certifications", [])

    if not req_certs:
        cert_score = max_cert_w
        if cand_certs and cand_certs not in ["None", "Not specified", "(Blank)"]:
            strengths.append(f"Has relevant certifications ({cand_certs})")
    else:
        if cand_certs and cand_certs not in ["None", "Not specified", "(Blank)"]:
            cert_score = max_cert_w
            strengths.append(f"Holds required/preferred certifications ({cand_certs})")
        else:
            cert_score = 0.0
            gaps.append("Missing target certifications listed in JD")

    # 6. EVALUATE PROJECTS & OTHER (Max: norm_weights['projects_other'])
    max_proj_w = norm_weights["projects_other"]
    cand_projects = candidate_profile.get("Projects", candidate_profile.get("_projects", ""))
    if cand_projects and str(cand_projects).strip() not in ["None", "Not specified", "(Blank)"]:
        proj_score = max_proj_w
        strengths.append("Has documented hands-on practical project work")
    else:
        proj_score = max_proj_w * 0.5

    # OVERALL CALCULATED SCORE
    overall_score = round(req_score + pref_score + exp_score + edu_score + cert_score + proj_score, 1)
    overall_score = min(100.0, max(0.0, overall_score))

    breakdown = {
        "required_skills": {"score": round(req_score, 1), "max": round(max_req_w, 1)},
        "preferred_skills": {"score": round(pref_score, 1), "max": round(max_pref_w, 1)},
        "experience": {"score": round(exp_score, 1), "max": round(max_exp_w, 1)},
        "education": {"score": round(edu_score, 1), "max": round(max_edu_w, 1)},
        "certifications": {"score": round(cert_score, 1), "max": round(max_cert_w, 1)},
        "projects_other": {"score": round(proj_score, 1), "max": round(max_proj_w, 1)}
    }

    return {
        "overall_score": overall_score,
        "scoring_breakdown": breakdown,
        "strengths": strengths,
        "gaps": gaps
    }
