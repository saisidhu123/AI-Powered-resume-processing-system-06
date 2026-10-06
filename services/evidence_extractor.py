"""
services/evidence_extractor.py

Grounded Evidence Extractor Module.

Locates exact text snippets, bullet points, and sentences directly from the raw resume text
and parsed sections to support skill matching and requirement claims.

CRITICAL GUARDRAIL:
Strictly grounded in authentic resume text. Never invents quotes or fake evidence.
If no direct mention or context is found in the resume, explicitly returns "No direct text evidence found".
"""

import re
from typing import Dict, Any, List, Optional
from services.section_detector import segment_resume_sections


def extract_evidence_for_skill(
    skill_name: str,
    resume_text: str,
    sections: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Extracts direct quotes and section origin from the resume supporting a specific skill claim.
    
    Returns:
        {
            "skill": "Python",
            "found": True/False,
            "match_level": "Strong" | "Good" | "Limited" | "Missing",
            "section": "EXPERIENCE" | "PROJECTS" | "SKILLS" | "SUMMARY" | "FULL_TEXT",
            "snippet": "Developed NLP application using Python and FastAPI..."
        }
    """
    if not skill_name or not resume_text:
        return {
            "skill": skill_name,
            "found": False,
            "match_level": "Missing",
            "section": "UNKNOWN",
            "snippet": "No text content provided"
        }

    skill_clean = skill_name.strip()
    skill_pattern = r"\b" + re.escape(skill_clean.lower()) + r"\b"
    
    if sections is None:
        sections = segment_resume_sections(resume_text)
        
    best_section = "FULL_TEXT"
    found_snippets: List[str] = []
    highest_match_level = "Missing"

    # Search section by section in priority order (EXPERIENCE > PROJECTS > SKILLS > SUMMARY > OTHER)
    section_priority = ["EXPERIENCE", "PROJECTS", "SKILLS", "SUMMARY", "CERTIFICATIONS", "EDUCATION"]
    
    # Check ordered sections first
    for sec in section_priority:
        sec_text = sections.get(sec, "")
        if not sec_text:
            continue
            
        if re.search(skill_pattern, sec_text.lower()):
            best_section = sec
            snippets = extract_matching_lines(sec_text, skill_clean)
            if snippets:
                found_snippets.extend(snippets)
                
                if sec in ["EXPERIENCE", "PROJECTS"]:
                    highest_match_level = "Strong"
                elif sec == "SKILLS":
                    highest_match_level = "Good" if highest_match_level != "Strong" else "Strong"
                else:
                    highest_match_level = "Good" if highest_match_level not in ["Strong", "Good"] else highest_match_level
                break

    # If not found in priority sections, search full text
    if not found_snippets:
        lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
        for line in lines:
            if re.search(skill_pattern, line.lower()):
                found_snippets.append(line[:250])
                highest_match_level = "Limited"
                best_section = "GENERAL_TEXT"
                if len(found_snippets) >= 2:
                    break

    if found_snippets:
        return {
            "skill": skill_clean,
            "found": True,
            "match_level": highest_match_level,
            "section": best_section,
            "snippet": " | ".join(found_snippets[:2])
        }
    else:
        return {
            "skill": skill_clean,
            "found": False,
            "match_level": "Missing",
            "section": "NOT_FOUND",
            "snippet": f"No direct mention of '{skill_clean}' found in resume text."
        }


def extract_matching_lines(text: str, keyword: str) -> List[str]:
    """Extracts up to 2 clean lines or bullet points containing the keyword."""
    keyword_pat = r"\b" + re.escape(keyword.lower()) + r"\b"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    matches = []
    
    for line in lines:
        if re.search(keyword_pat, line.lower()):
            clean_line = re.sub(r"^[•\*\-\s]+", "", line).strip()
            if len(clean_line) > 10:
                matches.append(clean_line[:300])
            if len(matches) >= 2:
                break
                
    return matches


def extract_all_evidence(
    jd_skills: List[str],
    resume_text: str,
    sections: Optional[Dict[str, str]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Builds complete evidence map for a list of JD skills against a candidate's resume.
    """
    if sections is None:
        sections = segment_resume_sections(resume_text)
        
    evidence_map = {}
    for skill in jd_skills:
        if skill and str(skill).strip():
            evidence_map[str(skill).strip()] = extract_evidence_for_skill(str(skill).strip(), resume_text, sections)
            
    return evidence_map
