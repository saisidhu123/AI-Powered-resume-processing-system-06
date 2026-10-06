"""
services/jd_parser.py

Parses Job Descriptions (raw text or uploaded PDF/DOCX files) and extracts structured requirements:
- Job Title
- Required Skills
- Preferred Skills
- Required Experience (Years & Domain)
- Education Requirements
- Certifications
- Important Technologies & Tools
- Domain Specific Requirements
- Responsibilities / Overview

Uses a combination of LLM structured JSON extraction and deterministic rule parsing.
Never fabricates requirements; flags ambiguous items as uncertain.
"""

import os
import re
import json
from typing import Dict, Any, Tuple, List
from services.resume_parser import parse_resume
from services.llm_service import call_hf_llm
from utils.helpers import extract_json_from_response


def extract_jd_text(source: str) -> Tuple[bool, str, str]:
    """
    Extract text from a Job Description file path or raw text string.
    Returns (success, text, error_message).
    """
    if not source or not str(source).strip():
        return False, "", "Job Description text or file is empty."
    
    source_str = str(source).strip()
    
    # If source is a valid file path, parse it using existing document parsing
    if os.path.exists(source_str) and os.path.isfile(source_str):
        return parse_resume(source_str)
    
    # Otherwise treat as raw text
    return True, source_str, ""


def parse_job_description(source: str) -> Tuple[bool, Dict[str, Any], str]:
    """
    Parses a Job Description source (file path or raw text) and extracts structured requirements.
    
    Returns:
        (success, structured_requirements_dict, error_message)
    """
    ok, jd_text, err = extract_jd_text(source)
    if not ok or not jd_text.strip():
        return False, {}, f"Failed to extract JD text: {err}"
    
    # Limit text length sent to LLM to stay safely within token limits while preserving core content
    truncated_jd = jd_text[:2500]
    
    prompt = f"""You are an expert HR Recruitment Specialist.
Analyze the following Job Description (JD) text and extract structured candidate requirements in strict JSON format.

RULES:
1. Differentiate between MANDATORY/REQUIRED skills and PREFERRED/DESIRABLE skills whenever the JD text provides sufficient context.
2. If a skill is listed as optional, nice-to-have, plus, or preferred, place it under "preferred_skills". Otherwise put core technical/functional requirements under "required_skills".
3. Extract required experience in years (e.g. 3, 5, 0 if entry level). If unstated, set required_experience_years to null.
4. Extract minimum education requirement (e.g. "Bachelor's degree in CS", "Master's").
5. Extract required or preferred certifications.
6. Extract key technologies/tools mentioned.
7. Do not invent requirements not mentioned in the JD.

JSON Schema to return:
{{
  "job_title": "extracted title or General Role",
  "required_skills": ["Skill1", "Skill2"],
  "preferred_skills": ["Skill3", "Skill4"],
  "required_experience_years": 3,
  "experience_description": "3+ years in software engineering and Python",
  "education_requirements": ["Bachelor's degree in Computer Science or related field"],
  "certifications": ["AWS Certified Developer"],
  "technologies_tools": ["Python", "Docker", "Git", "PostgreSQL"],
  "domain_requirements": "Fintech / Cloud Infrastructure",
  "key_responsibilities": ["Design REST APIs", "Optimize database queries"],
  "uncertain_or_ambiguous": ["Any unclear requirement"]
}}

Job Description Text:
\"\"\"
{truncated_jd}
\"\"\"
"""
    
    llm_ok, raw_resp, llm_err = call_hf_llm(prompt, temperature=0.0)
    
    structured_data: Dict[str, Any] = {}
    if llm_ok and raw_resp:
        extracted_json = extract_json_from_response(raw_resp)
        if isinstance(extracted_json, dict):
            structured_data = extracted_json
    
    # Deterministic fallback / normalization
    if not structured_data.get("job_title"):
        structured_data["job_title"] = extract_fallback_title(jd_text)
    
    if not isinstance(structured_data.get("required_skills"), list):
        structured_data["required_skills"] = extract_fallback_skills(jd_text)
    if not isinstance(structured_data.get("preferred_skills"), list):
        structured_data["preferred_skills"] = []
    if not isinstance(structured_data.get("education_requirements"), list):
        structured_data["education_requirements"] = []
    if not isinstance(structured_data.get("certifications"), list):
        structured_data["certifications"] = []
    if not isinstance(structured_data.get("technologies_tools"), list):
        structured_data["technologies_tools"] = []
    if not isinstance(structured_data.get("key_responsibilities"), list):
        structured_data["key_responsibilities"] = []
    if not isinstance(structured_data.get("uncertain_or_ambiguous"), list):
        structured_data["uncertain_or_ambiguous"] = []

    # Clean up empty strings
    structured_data["required_skills"] = [str(s).strip() for s in structured_data["required_skills"] if str(s).strip()]
    structured_data["preferred_skills"] = [str(s).strip() for s in structured_data["preferred_skills"] if str(s).strip()]
    structured_data["raw_text"] = jd_text
    
    return True, structured_data, ""


def extract_fallback_title(text: str) -> str:
    """Fallback title extractor using common job title patterns."""
    first_few_lines = [l.strip() for l in text.splitlines()[:5] if l.strip()]
    for line in first_few_lines:
        if len(line) < 50 and any(kw in line.lower() for kw in ["engineer", "developer", "manager", "analyst", "architect", "lead", "specialist"]):
            return line
    return "Job Position"


def extract_fallback_skills(text: str) -> List[str]:
    """Fallback skill extractor scanning text for common tech keywords."""
    common_skills = [
        "Python", "Java", "C++", "JavaScript", "TypeScript", "React", "Node.js", "SQL",
        "PostgreSQL", "MongoDB", "AWS", "Azure", "Docker", "Kubernetes", "Git", "CI/CD",
        "Machine Learning", "Data Analysis", "REST API", "FastAPI", "Django", "Flask",
        "HTML", "CSS", "Agile", "Scrum", "DevOps", "Linux", "Spring Boot", "Spark"
    ]
    found = []
    text_lower = text.lower()
    for sk in common_skills:
        pattern = r"\b" + re.escape(sk.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.append(sk)
    return found
