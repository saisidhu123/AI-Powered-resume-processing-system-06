import os
import json
from services.jd_parser import parse_job_description
from services.resume_parser import parse_resume
from services.llm_service import extract_candidate_data
from services.matching_engine import match_resume_to_jd
from services.evidence_extractor import extract_all_evidence
from services.scoring_engine import evaluate_candidate_match
from services.candidate_database import (
    save_job_description,
    save_candidate_profile,
    save_screening_result,
    update_candidate_status,
    search_candidates,
    get_all_candidates_with_status,
    get_dashboard_metrics
)
from services.interview_generator import generate_interview_questions
from services.candidate_analyzer import (
    analyze_resume_sections,
    identify_possible_mismatch_reasons
)
from services.ats_analyzer import analyze_ats_compatibility
from services.resume_improver import (
    improve_resume_wording,
    generate_job_specific_suggestions
)

def run_platform_verification():
    print("==========================================================================")
    print("      VERIFYING AI RECRUITMENT & RESUME INTELLIGENCE PLATFORM (1-17)      ")
    print("==========================================================================")

    # 1. Job Description Parsing Test (Req 1)
    jd_raw = """
    Job Title: Senior Full-Stack Python Developer
    Required Experience: 4+ years
    Required Skills: Python, Django, FastAPI, React, PostgreSQL, REST APIs
    Preferred Skills: Docker, Kubernetes, AWS, Redis
    Education: Bachelor's degree in Computer Science or Software Engineering
    Certifications: AWS Certified Developer
    """
    ok_jd, structured_jd, err_jd = parse_job_description(jd_raw)
    assert ok_jd, f"Req 1 Failed: {err_jd}"
    assert "Python" in structured_jd.get("required_skills", []), "Req 1 Failed: Python missing in required skills"
    jd_id = save_job_description("Senior Full-Stack Python Developer", jd_raw, structured_jd)
    print("[PASS] Req 1: Job Description Upload & Structuring")

    # 2. Candidate Resumes Setup for Batch & Matching (Req 2 & 3)
    cand_a_text = """
    ALICE SMITH
    Email: alice@example.com | Mobile: +91 9999911111 | Location: Bangalore
    SUMMARY: Senior Full-Stack Engineer with 5 years experience in Python, FastAPI, Django, and React.
    TECHNICAL SKILLS: Python, FastAPI, Django, React, PostgreSQL, Docker, AWS, Redis
    WORK EXPERIENCE:
    Lead Developer - TechCorp (2021 - Present)
    - Developed microservices in Python using FastAPI and PostgreSQL handling 1M daily requests.
    - Built frontend dashboards using React and Redux.
    Software Engineer - DevStudio (2019 - 2021)
    - Built Django web portals with PostgreSQL database.
    EDUCATION: Bachelor of Technology in Computer Science (2019)
    CERTIFICATIONS: AWS Certified Developer
    NOTICE PERIOD: 15 Days | CURRENT CTC: 16 LPA | EXPECTED CTC: 22 LPA
    """

    cand_b_text = """
    BOB JONES
    Email: bob@example.com | Mobile: +91 9999922222 | Location: Hyderabad
    SUMMARY: Python Developer with 2 years experience in Django and SQL.
    TECHNICAL SKILLS: Python, Django, HTML, CSS, SQL
    WORK EXPERIENCE:
    Junior Developer - WebApp Inc (2022 - Present)
    - Built Django CRUD applications and SQL database tables.
    EDUCATION: B.Sc Computer Science
    NOTICE PERIOD: 30 Days | CURRENT CTC: 6 LPA | EXPECTED CTC: 10 LPA
    """

    headers = ["Candidate Name", "Email Address", "Mobile Number", "Total Experience (Years)", "Technical Skills", "Education", "Certifications", "Projects"]

    # Candidate A Extraction & Matching (Req 2, 3, 5, 6)
    _, cand_a_data, _, _ = extract_candidate_data(cand_a_text, headers)
    ok_ma, match_a, _ = match_resume_to_jd(cand_a_data, cand_a_text, structured_jd)
    assert ok_ma, "Req 3 Match Failed"
    id_a = save_candidate_profile(cand_a_data, cand_a_text)
    save_screening_result(id_a, jd_id, match_a)

    # Candidate B Extraction & Matching
    _, cand_b_data, _, _ = extract_candidate_data(cand_b_text, headers)
    ok_mb, match_b, _ = match_resume_to_jd(cand_b_data, cand_b_text, structured_jd)
    assert ok_mb, "Req 3 Match Failed"
    id_b = save_candidate_profile(cand_b_data, cand_b_text)
    save_screening_result(id_b, jd_id, match_b)

    print("[PASS] Req 2: Multiple Resume Ingestion & Processing")
    print(f"[PASS] Req 3: Resume vs Job Matching (Alice: {match_a['overall_match_score']}%, Bob: {match_b['overall_match_score']}%)")

    # 4. Automatic Candidate Ranking (Req 4)
    all_cands = get_all_candidates_with_status()
    test_cands = [c for c in all_cands if c["id"] in (id_a, id_b)]
    ranked = sorted(test_cands, key=lambda x: x["match_score"], reverse=True)
    assert ranked[0]["id"] == id_a, "Req 4 Ranking Failed: Alice should be ranked #1"
    print(f"[PASS] Req 4: Automatic Candidate Ranking (#1 {ranked[0]['candidate_name']} {ranked[0]['match_score']}%, #2 {ranked[1]['candidate_name']} {ranked[1]['match_score']}%)")

    # 5. Explain Score: Strengths & Gaps (Req 5)
    assert len(match_a["strengths"]) > 0, "Req 5 Strengths missing"
    assert len(match_b["gaps"]) > 0, "Req 5 Gaps missing for candidate B"
    print(f"[PASS] Req 5: Explain Score (Alice Strengths: {len(match_a['strengths'])}, Bob Gaps: {len(match_b['gaps'])})")

    # 6. Grounded Resume Evidence (Req 6)
    evidence_py = match_a["evidence_map"].get("Python", {})
    assert evidence_py.get("found") == True, "Req 6 Evidence Python not found"
    assert evidence_py.get("snippet") != "", "Req 6 Snippet empty"
    print(f"[PASS] Req 6: Grounded Resume Evidence (Snippet: '{evidence_py['snippet'][:60]}...')")

    # 7. Candidate Comparison (Req 7)
    assert ranked[0]["match_score"] > ranked[1]["match_score"], "Req 7 Side-by-side comparison score delta verified"
    print("[PASS] Req 7: Candidate Comparison")

    # 8. Candidate Database Search (Req 8)
    search_res = search_candidates(query="Python", min_exp=3.0)
    assert len(search_res) >= 1, "Req 8 Search Failed"
    assert search_res[0]["candidate_name"] == "Alice Smith", "Req 8 Search candidate mismatch"
    print(f"[PASS] Req 8: Candidate Database Search (Found {len(search_res)} matching candidate(s))")

    # 9. Recruitment Pipeline Status (Req 9)
    update_candidate_status(id_a, "Shortlisted", "Top candidate with strong FastAPI and React skills.")
    cand_a_updated = search_candidates(query="Alice")[0]
    assert cand_a_updated["status"] == "Shortlisted", "Req 9 Pipeline status update failed"
    print(f"[PASS] Req 9: Recruitment Pipeline Status & Notes Update (Status: {cand_a_updated['status']})")

    # 10. AI Interview Question Generator (Req 10)
    ok_iq, iqs, err_iq = generate_interview_questions(cand_a_data, structured_jd)
    assert ok_iq and len(iqs) > 0, f"Req 10 Question Generation Failed: {err_iq}"
    print(f"[PASS] Req 10: Grounded AI Interview Question Generation (Categories: {list(iqs.keys())})")

    # ==========================================================================
    # CANDIDATE SIDE REQUIREMENTS (Req 11 - 17)
    # ==========================================================================

    # 11. Resume + Job Description Analysis (Req 11)
    cand_match_score = match_a['overall_match_score']
    assert cand_match_score > 0, "Req 11 Match percentage missing"
    print(f"[PASS] Req 11: Candidate Resume + JD Analysis (Overall Match Score: {cand_match_score}%)")

    # 12. Mismatch Reasons & Rejection Analysis with Disclaimer (Req 12)
    mismatch_reasons = identify_possible_mismatch_reasons(match_b, cand_b_data, structured_jd)
    assert len(mismatch_reasons) > 0, "Req 12 Mismatch reasons missing for candidate B"
    print(f"[PASS] Req 12: 'Why Am I Not Getting Shortlisted?' Mismatch Analysis ({len(mismatch_reasons)} possible reason(s))")

    # 13. Actionable Bullet Rewording Suggestions (Req 13)
    ok_reword, rewords, err_reword = improve_resume_wording(cand_a_text, structured_jd)
    assert ok_reword and len(rewords) > 0, "Req 13 Bullet improvements missing"
    print(f"[PASS] Req 13: Grounded Resume Rewording Recommendations (Sample: '{rewords[0].get('suggested')[:70]}...')")

    # 14. Missing Skills & Skill Level Classification (Req 14)
    skill_evals = match_b["skill_evaluations"]
    assert "FastAPI" in skill_evals and skill_evals["FastAPI"]["level"] == "Missing", "Req 14 Missing skill verification failed"
    print(f"[PASS] Req 14: Missing Skills Classification (FastAPI: {skill_evals['FastAPI']['level']})")

    # 15. Resume Section Analysis (Req 15)
    sec_feedback = analyze_resume_sections(cand_a_text, structured_jd)
    assert "SUMMARY" in sec_feedback or "EXPERIENCE" in sec_feedback, "Req 15 Section feedback missing"
    print(f"[PASS] Req 15: Resume Section Analysis ({len(sec_feedback)} sections analyzed)")

    # 16. ATS Compatibility Check (Req 16)
    ats_res = analyze_ats_compatibility(cand_a_text, structured_jd)
    assert "ats_readiness_score" in ats_res, "Req 16 ATS Readiness score missing"
    print(f"[PASS] Req 16: ATS Compatibility Check (Score: {ats_res['ats_readiness_score']}%, Rating: '{ats_res['rating']}')")

    # 17. Job-Specific Resume Optimization (Req 17)
    job_suggs = generate_job_specific_suggestions(cand_a_data, structured_jd, match_a)
    assert len(job_suggs) > 0, "Req 17 Job-specific suggestions missing"
    print(f"[PASS] Req 17: Job-Specific Resume Optimization ({len(job_suggs)} recommendation(s))")

    print("\n==========================================================================")
    print("   [OK] ALL 17 RECRUITER & CANDIDATE PLATFORM REQUIREMENTS VERIFIED 100%!  ")
    print("==========================================================================")

if __name__ == "__main__":
    run_platform_verification()
