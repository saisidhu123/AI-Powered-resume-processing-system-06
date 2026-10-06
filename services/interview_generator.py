"""
services/interview_generator.py

AI-Powered Grounded Interview Question Generator.

Generates targeted, highly relevant interview questions based on:
- Job Description Requirements
- Candidate's Resume Details (Projects, Experience, Skills)

Categorizes questions into:
1. Technical Verification
2. Project-Based Deep Dive
3. Experience & Behavioral
4. Skill Verification
5. Role-Specific Scenario

STRICT GUARDRAIL:
Never fabricates candidate projects or experience. Questions must reference actual resume items and JD requirements.
"""

from typing import Dict, Any, List, Tuple
from services.llm_service import call_hf_llm
from utils.helpers import extract_json_from_response


def generate_interview_questions(
    candidate_profile: Dict[str, Any],
    jd_requirements: Dict[str, Any]
) -> Tuple[bool, Dict[str, List[Dict[str, str]]], str]:
    """
    Generates interview questions categorized by topic.
    
    Returns:
        (success, questions_dict, error_message)
    """
    cand_name = candidate_profile.get("Candidate Name", candidate_profile.get("name", "Candidate"))
    cand_skills = candidate_profile.get("Technical Skills", candidate_profile.get("skills", []))
    cand_exp = candidate_profile.get("Total Experience (Years)", candidate_profile.get("experience", "Not specified"))
    cand_projects = candidate_profile.get("Projects", candidate_profile.get("_projects", "Not specified"))

    jd_title = jd_requirements.get("job_title", "Target Role")
    jd_req_skills = jd_requirements.get("required_skills", [])
    jd_pref_skills = jd_requirements.get("preferred_skills", [])

    prompt = f"""You are an expert Technical Recruiter & Hiring Manager.
Generate targeted, grounded interview questions for candidate '{cand_name}' applying for position '{jd_title}'.

CANDIDATE DETAILS:
- Name: {cand_name}
- Total Experience: {cand_exp} years
- Key Skills: {cand_skills}
- Documented Projects/Work: {cand_projects}

JOB DESCRIPTION REQUIREMENTS:
- Job Title: {jd_title}
- Required Skills: {jd_req_skills}
- Preferred Skills: {jd_pref_skills}

RULES:
1. Questions MUST reference specific skills and projects from the candidate's resume and connect them to the job requirements.
2. DO NOT invent fake projects or experience that the candidate does not have.
3. Provide expected answers or key evaluation points for the interviewer for each question.
4. Categorize questions into: "technical", "project_based", "experience_based", "skill_verification", "role_specific".

JSON Schema to return:
{{
  "technical": [
    {{"question": "How did you use Python and scikit-learn in your ML models?", "purpose": "Verify core technical proficiency", "evaluation_criteria": "Look for explanation of data pre-processing and hyperparameter tuning"}}
  ],
  "project_based": [
    {{"question": "Can you walk us through your NLP project listed on your resume?", "purpose": "Assess architectural decisions", "evaluation_criteria": "Check clarity on model selection and deployment"}}
  ],
  "experience_based": [
    {{"question": "Given your 4 years of experience, describe a complex challenge you solved.", "purpose": "Evaluate problem-solving depth", "evaluation_criteria": "Look for structured STAR method response"}}
  ],
  "skill_verification": [
    {{"question": "The JD emphasizes AWS, but your resume lists GCP. How would you transfer your cloud skills?", "purpose": "Gauge adaptability", "evaluation_criteria": "Look for willingness and familiarity with equivalent services"}}
  ],
  "role_specific": [
    {{"question": "How would you design a scalable microservice for this {jd_title} position?", "purpose": "Role readiness", "evaluation_criteria": "Look for clean REST API design principles"}}
  ]
}}
"""

    ok, raw_resp, err = call_hf_llm(prompt, temperature=0.2)
    
    if ok and raw_resp:
        parsed_json = extract_json_from_response(raw_resp)
        if isinstance(parsed_json, dict) and any(k in parsed_json for k in ["technical", "project_based", "experience_based"]):
            return True, parsed_json, ""

    # Fallback questions if LLM response is unparseable
    fallback_qs = {
        "technical": [
            {
                "question": f"Can you explain your experience with {', '.join(cand_skills[:3]) if cand_skills else 'your core technical skills'}?",
                "purpose": "Verify foundational technical depth",
                "evaluation_criteria": "Candidate provides concrete implementation examples."
            }
        ],
        "project_based": [
            {
                "question": "Can you describe a recent project you built, your role, and the key technical decisions you made?",
                "purpose": "Evaluate practical project execution",
                "evaluation_criteria": "Look for ownership and clear architectural understanding."
            }
        ],
        "experience_based": [
            {
                "question": f"How has your {cand_exp} years of technical experience prepared you for the {jd_title} role?",
                "purpose": "Assess career progression and maturity",
                "evaluation_criteria": "Look for relevant achievements and growth."
            }
        ],
        "skill_verification": [
            {
                "question": f"How do your skills align with our required tech stack ({', '.join(jd_req_skills[:3]) if jd_req_skills else 'the JD'})?",
                "purpose": "Verify requirement overlap",
                "evaluation_criteria": "Candidate connects past skills to current needs."
            }
        ],
        "role_specific": [
            {
                "question": f"What approaches would you use in your first 90 days as a {jd_title}?",
                "purpose": "Evaluate role readiness and strategic onboarding",
                "evaluation_criteria": "Candidate demonstrates proactive learning and domain focus."
            }
        ]
    }

    return True, fallback_qs, ""
