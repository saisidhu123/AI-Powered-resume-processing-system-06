import os
import time
import shutil
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from services.llm_service import check_llm_status, extract_candidate_data, HF_MODEL, GROQ_MODEL
from services.resume_parser import parse_resume
from services.excel_service import (
    read_excel_headers,
    read_existing_candidate_rows,
    populate_excel_template,
    populate_excel_template_batch,
    generate_duplicate_report,
    generate_error_and_missing_report,
    generate_classification_report,
    create_batch_zip_package
)
from services.duplicate_detector import check_duplicate
from services.batch_processor import process_resume_batch

# Platform Services Imports
from services.jd_parser import parse_job_description, extract_jd_text
from services.matching_engine import match_resume_to_jd
from services.scoring_engine import evaluate_candidate_match
from services.evidence_extractor import extract_all_evidence
from services.candidate_database import (
    save_job_description,
    save_candidate_profile,
    save_screening_result,
    update_candidate_status,
    get_all_candidates_with_status,
    search_candidates,
    get_dashboard_metrics,
    get_db_connection,
    clear_candidate_database
)
from services.interview_generator import generate_interview_questions
from services.candidate_analyzer import analyze_resume_sections, identify_possible_mismatch_reasons
from services.ats_analyzer import analyze_ats_compatibility
from services.resume_improver import improve_resume_wording, generate_job_specific_suggestions


app = FastAPI(
    title="AI Recruitment & Resume Intelligence Platform API",
    description="REST API for AI-powered candidate screening, JD parsing, evidence extraction, candidate ranking, database search, pipeline status tracking, ATS evaluation, and interview question generation.",
    version="2.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev flexibility
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models for Request Validation
class JDParseTextRequest(BaseModel):
    jd_text: str

class CandidateStatusRequest(BaseModel):
    candidate_id: int
    status: str
    notes: Optional[str] = ""

class CompareCandidatesRequest(BaseModel):
    candidate_ids: List[int]

class InterviewQuestionsRequest(BaseModel):
    candidate_id: Optional[int] = None
    jd_id: Optional[int] = None
    candidate_profile: Optional[dict] = None
    jd_requirements: Optional[dict] = None

class CandidateAnalysisRequest(BaseModel):
    resume_text: Optional[str] = None
    jd_text: Optional[str] = None

class SectionAnalysisRequest(BaseModel):
    resume_text: str
    jd_text: Optional[str] = None

class ATSCheckRequest(BaseModel):
    resume_text: str
    jd_text: Optional[str] = None

class ImproveResumeRequest(BaseModel):
    resume_text: str
    jd_text: Optional[str] = None

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
OUTPUT_DIR = os.path.join(os.getcwd(), "outputs")
FRONTEND_DIST = os.path.join(os.getcwd(), "frontend", "dist")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.get("/api/status")
async def get_status():
    is_online, status_msg, available_models = check_llm_status()
    return {
        "is_online": is_online,
        "status_msg": status_msg,
        "available_models": available_models,
        "llm_provider": "Hugging Face Inference API",
        "target_model": HF_MODEL
    }


@app.post("/api/upload-template")
async def upload_template(file: UploadFile = File(...)):
    """Upload Excel column template and extract headers."""
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx Excel files are supported.")
    
    template_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(template_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    success, headers, error_msg = read_excel_headers(template_path)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to read headers: {error_msg}")
        
    return {
        "filename": file.filename,
        "headers": headers,
        "count": len(headers)
    }


@app.post("/api/process-single")
async def process_single_resume(
    resume: UploadFile = File(...),
    template: UploadFile = File(...)
):
    """Process a single resume against an Excel column template."""
    is_online, status_msg, _ = check_llm_status()
    if not is_online:
        raise HTTPException(status_code=503, detail=f"LLM API offline: {status_msg}")

    # Save resume
    resume_path = os.path.join(UPLOAD_DIR, resume.filename)
    with open(resume_path, "wb") as buffer:
        shutil.copyfileobj(resume.file, buffer)

    # Save template
    template_path = os.path.join(UPLOAD_DIR, template.filename)
    with open(template_path, "wb") as buffer:
        shutil.copyfileobj(template.file, buffer)

    # Read template headers
    success_hdr, headers, hdr_err = read_excel_headers(template_path)
    if not success_hdr:
        raise HTTPException(status_code=400, detail=f"Template header error: {hdr_err}")

    # Step 1: Parse resume text
    parsed_ok, resume_text, parse_err = parse_resume(resume_path)
    if not parsed_ok:
        raise HTTPException(status_code=400, detail=f"Resume parsing error: {parse_err}")

    # Step 2: Extract candidate data with LLM
    llm_ok, candidate_data, raw_llm, llm_err = extract_candidate_data(resume_text, headers)
    if not llm_ok:
        raise HTTPException(status_code=500, detail=f"AI extraction error: {llm_err}")

    # Step 3: Check duplicate against existing template records
    existing_records = read_existing_candidate_rows(template_path)
    is_dup, dup_warning, dup_details = check_duplicate(candidate_data, existing_records)

    # Step 4: Populate output Excel
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate_name_clean = str(candidate_data.get("Candidate Name", "Candidate")).replace(" ", "_")
    output_filename = f"Processed_{candidate_name_clean}_{timestamp}.xlsx"
    output_filepath = os.path.join(OUTPUT_DIR, output_filename)

    pop_ok, pop_err = populate_excel_template(template_path, candidate_data, output_filepath)
    if not pop_ok:
        raise HTTPException(status_code=500, detail=f"Excel population error: {pop_err}")

    # Build response data structures
    extracted_fields = []
    missing_fields = []
    for h in headers:
        val = candidate_data.get(h, "")
        if val != "" and val is not None and str(val).strip():
            extracted_fields.append({"column": h, "value": str(val).strip(), "status": "Extracted"})
        else:
            extracted_fields.append({"column": h, "value": "(Blank)", "status": "Missing / Blank"})
            missing_fields.append(h)

    return {
        "candidate_name": candidate_data.get("Candidate Name", "Unknown"),
        "is_duplicate": is_dup,
        "duplicate_warning": dup_warning if is_dup else None,
        "duplicate_details": dup_details if is_dup else None,
        "tech_domains": candidate_data.get("_tech_domains", ["Others"]),
        "exp_bucket": candidate_data.get("_exp_bucket", "Fresher"),
        "ai_screening": {
            "summary": candidate_data.get("_ai_screening_summary", "N/A"),
            "oracle_exp": candidate_data.get("_oracle_exp", "No"),
            "suitable_roles": candidate_data.get("_suitable_roles", "General Tech Role")
        },
        "diagnostics": {
            "exp_confidence": candidate_data.get("_exp_confidence", 0),
            "exp_notes": candidate_data.get("_exp_notes", "N/A"),
            "skills_confidence": candidate_data.get("_skills_confidence", 0),
            "cleaned_text": candidate_data.get("_cleaned_text", ""),
            "raw_text": candidate_data.get("_raw_text", "")
        },
        "extracted_fields": extracted_fields,
        "missing_fields": missing_fields,
        "output_filename": output_filename,
        "download_url": f"/api/download/{output_filename}"
    }


@app.post("/api/process-batch")
async def process_batch_resumes(
    template: UploadFile = File(...),
    resumes: List[UploadFile] = File(...)
):
    """Process multiple resumes in parallel and generate comprehensive report files."""
    if not resumes:
        raise HTTPException(status_code=400, detail="No resume files uploaded.")

    # Save template
    template_path = os.path.join(UPLOAD_DIR, template.filename)
    with open(template_path, "wb") as buffer:
        shutil.copyfileobj(template.file, buffer)

    success_hdr, headers, hdr_err = read_excel_headers(template_path)
    if not success_hdr:
        raise HTTPException(status_code=400, detail=f"Excel template error: {hdr_err}")

    # Save resume files
    file_paths = []
    for r in resumes:
        save_p = os.path.join(UPLOAD_DIR, r.filename)
        with open(save_p, "wb") as buffer:
            shutil.copyfileobj(r.file, buffer)
        file_paths.append(save_p)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    start_t = time.time()

    # Process batch
    batch_output = process_resume_batch(
        file_paths=file_paths,
        excel_headers=headers,
        template_path=template_path,
        progress_callback=None,
        max_workers=4
    )
    elapsed_sec = round(time.time() - start_t, 2)

    # Generate Output Files
    master_fname = f"Master_Candidates_{timestamp}.xlsx"
    dup_fname = f"Duplicate_Report_{timestamp}.xlsx"
    err_fname = f"Error_Log_{timestamp}.xlsx"
    class_fname = f"Classification_Analytics_{timestamp}.xlsx"
    zip_fname = f"Batch_Reports_{timestamp}.zip"

    master_path = os.path.join(OUTPUT_DIR, master_fname)
    dup_path = os.path.join(OUTPUT_DIR, dup_fname)
    err_path = os.path.join(OUTPUT_DIR, err_fname)
    class_path = os.path.join(OUTPUT_DIR, class_fname)
    zip_path = os.path.join(OUTPUT_DIR, zip_fname)

    populate_excel_template_batch(template_path, batch_output["unique_candidates"], master_path)
    generate_duplicate_report(batch_output["duplicate_candidates"], headers, dup_path)
    generate_error_and_missing_report(batch_output["failed_resumes"], batch_output["missing_fields_log"], err_path)
    generate_classification_report(batch_output["tech_stats"], batch_output["exp_stats"], class_path)

    report_files = [
        (master_path, master_fname),
        (dup_path, dup_fname),
        (err_path, err_fname),
        (class_path, class_fname)
    ]
    create_batch_zip_package(report_files, zip_path)

    return {
        "elapsed_seconds": elapsed_sec,
        "total_processed": batch_output["total_processed"],
        "unique_count": len(batch_output["unique_candidates"]),
        "duplicate_count": len(batch_output["duplicate_candidates"]),
        "failed_count": len(batch_output["failed_resumes"]),
        "headers": headers,
        "unique_candidates": batch_output["unique_candidates"],
        "duplicate_candidates": batch_output["duplicate_candidates"],
        "failed_resumes": batch_output["failed_resumes"],
        "missing_fields_log": batch_output["missing_fields_log"],
        "tech_stats": batch_output["tech_stats"],
        "exp_stats": batch_output["exp_stats"],
        "downloads": {
            "master_excel": f"/api/download/{master_fname}",
            "duplicate_report": f"/api/download/{dup_fname}",
            "error_log": f"/api/download/{err_fname}",
            "classification_analytics": f"/api/download/{class_fname}",
            "zip_package": f"/api/download/{zip_fname}"
        }
    }


# ==============================================================================
# NEW RECRUITER & CANDIDATE PLATFORM REST API ENDPOINTS
# ==============================================================================

@app.post("/api/parse-jd-text")
async def api_parse_jd_text(req: JDParseTextRequest):
    """Parse raw Job Description text into structured requirements."""
    ok, structured_data, err = parse_job_description(req.jd_text)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Failed to parse JD: {err}")
    jd_id = save_job_description(structured_data.get("job_title", "Position"), req.jd_text, structured_data)
    return {"jd_id": jd_id, "structured_requirements": structured_data}


@app.post("/api/parse-jd-file")
async def api_parse_jd_file(file: UploadFile = File(...)):
    """Upload and parse a Job Description file (PDF/DOCX/TXT)."""
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    ok, structured_data, err = parse_job_description(save_path)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Failed to parse JD file: {err}")
    jd_id = save_job_description(structured_data.get("job_title", file.filename), structured_data.get("raw_text", ""), structured_data)
    return {"jd_id": jd_id, "filename": file.filename, "structured_requirements": structured_data}


@app.post("/api/match-candidate-jd")
async def api_match_candidate_jd(
    resume: UploadFile = File(...),
    jd_text: Optional[str] = Form(None),
    jd_id: Optional[int] = Form(None)
):
    """Match a single candidate resume against a target Job Description."""
    # Save uploaded resume
    resume_path = os.path.join(UPLOAD_DIR, resume.filename)
    with open(resume_path, "wb") as buffer:
        shutil.copyfileobj(resume.file, buffer)

    ok_parse, resume_text, err_parse = parse_resume(resume_path)
    if not ok_parse:
        raise HTTPException(status_code=400, detail=f"Resume parse error: {err_parse}")

    # Step 1: Parse candidate fields
    headers = ["Candidate Name", "Email Address", "Mobile Number", "Total Experience (Years)", "Technical Skills", "Education", "Certifications", "Projects"]
    _, cand_data, _, _ = extract_candidate_data(resume_text, headers)
    cand_data["_raw_text"] = resume_text

    # Step 2: Get or parse target JD
    if jd_text:
        _, jd_reqs, _ = parse_job_description(jd_text)
        saved_jd_id = save_job_description(jd_reqs.get("job_title", "Job Position"), jd_text, jd_reqs)
    elif jd_id:
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM job_descriptions WHERE id = ?", (jd_id,)).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Specified JD ID not found.")
        import json
        jd_reqs = json.loads(row["structured_requirements"])
        saved_jd_id = jd_id
    else:
        raise HTTPException(status_code=400, detail="Must provide either jd_text or jd_id.")

    # Step 3: Run Match Engine
    ok_m, match_res, err_m = match_resume_to_jd(cand_data, resume_text, jd_reqs)
    if not ok_m:
        raise HTTPException(status_code=500, detail=f"Match calculation error: {err_m}")

    # Step 4: Persist in SQLite
    cand_id = save_candidate_profile(cand_data, resume_text)
    save_screening_result(cand_id, saved_jd_id, match_res)

    return {
        "candidate_id": cand_id,
        "jd_id": saved_jd_id,
        "candidate_profile": cand_data,
        "match_result": match_res
    }


@app.post("/api/batch-match-jd")
async def api_batch_match_jd(
    resumes: List[UploadFile] = File(...),
    jd_text: Optional[str] = Form(None)
):
    """Batch match multiple candidate resumes against a JD and return ranked candidates."""
    if not resumes:
        raise HTTPException(status_code=400, detail="No resume files provided.")
    if not jd_text or not jd_text.strip():
        raise HTTPException(status_code=400, detail="Job Description text required for batch matching.")

    ok_jd, jd_reqs, err_jd = parse_job_description(jd_text)
    if not ok_jd:
        raise HTTPException(status_code=400, detail=f"JD parsing error: {err_jd}")
    
    jd_id = save_job_description(jd_reqs.get("job_title", "Batch Role"), jd_text, jd_reqs)
    
    headers = ["Candidate Name", "Email Address", "Mobile Number", "Total Experience (Years)", "Technical Skills", "Education", "Certifications", "Projects"]
    
    ranked_candidates = []
    failures = []

    for r in resumes:
        try:
            save_p = os.path.join(UPLOAD_DIR, r.filename)
            with open(save_p, "wb") as buffer:
                shutil.copyfileobj(r.file, buffer)

            ok_p, r_text, err_p = parse_resume(save_p)
            if not ok_p or not r_text.strip():
                failures.append({"filename": r.filename, "error": err_p or "Empty resume file"})
                continue

            _, cand_data, _, _ = extract_candidate_data(r_text, headers)
            ok_m, match_res, err_m = match_resume_to_jd(cand_data, r_text, jd_reqs)
            
            if not ok_m:
                failures.append({"filename": r.filename, "error": err_m})
                continue

            cand_id = save_candidate_profile(cand_data, r_text)
            save_screening_result(cand_id, jd_id, match_res)

            ranked_candidates.append({
                "candidate_id": cand_id,
                "filename": r.filename,
                "candidate_name": cand_data.get("Candidate Name", r.filename),
                "email": cand_data.get("Email Address", ""),
                "total_experience": cand_data.get("Total Experience (Years)", 0),
                "skills": cand_data.get("Technical Skills", []),
                "overall_match_score": match_res["overall_match_score"],
                "scoring_breakdown": match_res["scoring_breakdown"],
                "strengths": match_res["strengths"],
                "gaps": match_res["gaps"],
                "evidence_map": match_res["evidence_map"],
                "status": "AI Screened"
            })
        except Exception as file_err:
            failures.append({"filename": r.filename, "error": str(file_err)})

    # Sort automatically by overall match score descending
    ranked_candidates.sort(key=lambda x: x["overall_match_score"], reverse=True)

    return {
        "jd_id": jd_id,
        "job_title": jd_reqs.get("job_title"),
        "total_submitted": len(resumes),
        "total_processed": len(ranked_candidates),
        "total_failed": len(failures),
        "ranked_candidates": ranked_candidates,
        "failures": failures
    }


@app.get("/api/candidates")
def api_get_candidates(
    query: str = "",
    min_exp: float = 0.0,
    skills: str = "",
    status: str = "ALL"
):
    """Retrieve and filter candidates in SQLite database."""
    skill_list = [s.strip() for s in skills.split(",") if s.strip()] if skills else None
    results = search_candidates(query=query, min_exp=min_exp, required_skills=skill_list, status_filter=status)
    return {"candidates": results, "count": len(results)}


@app.put("/api/candidates/status")
def api_update_candidate_status(req: CandidateStatusRequest):
    """Update candidate pipeline status and recruiter notes."""
    ok = update_candidate_status(req.candidate_id, req.status, req.notes)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to update candidate status.")
    return {"success": True, "message": "Candidate status updated successfully."}


@app.delete("/api/candidates/clear")
def api_clear_candidate_database():
    """Deletes all candidate records, screening results, and pipeline entries."""
    ok = clear_candidate_database()
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to clear candidate database.")
    return {"success": True, "message": "Candidate database cleared successfully."}


@app.post("/api/compare-candidates")
def api_compare_candidates(req: CompareCandidatesRequest):
    """Compare multiple candidates side-by-side."""
    if not req.candidate_ids:
        raise HTTPException(status_code=400, detail="No candidate IDs provided for comparison.")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    comparison_list = []
    import json
    for cid in req.candidate_ids:
        cursor.execute("""
            SELECT c.*, p.status, s.match_score, s.scoring_breakdown, s.strengths, s.gaps
            FROM candidates c
            LEFT JOIN recruitment_pipeline p ON c.id = p.candidate_id
            LEFT JOIN screening_results s ON c.id = s.candidate_id
            WHERE c.id = ?
        """, (cid,))
        row = cursor.fetchone()
        if row:
            comparison_list.append({
                "id": row["id"],
                "candidate_name": row["candidate_name"],
                "email": row["email"],
                "phone": row["phone"],
                "total_experience": row["total_experience"],
                "skills": json.loads(row["skills"]) if row["skills"] else [],
                "education": row["education"],
                "certifications": row["certifications"],
                "status": row["status"] or "Applied",
                "match_score": row["match_score"] or 0.0,
                "scoring_breakdown": json.loads(row["scoring_breakdown"]) if row["scoring_breakdown"] else {},
                "strengths": json.loads(row["strengths"]) if row["strengths"] else [],
                "gaps": json.loads(row["gaps"]) if row["gaps"] else []
            })
    conn.close()
    return {"compared_candidates": comparison_list}


@app.post("/api/generate-interview-questions")
def api_generate_interview_questions(req: InterviewQuestionsRequest):
    """Generate interview questions for candidate and JD."""
    cand_profile = req.candidate_profile or {}
    jd_reqs = req.jd_requirements or {}

    if req.candidate_id:
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (req.candidate_id,)).fetchone()
        conn.close()
        if row:
            import json
            cand_profile = {
                "Candidate Name": row["candidate_name"],
                "Total Experience (Years)": row["total_experience"],
                "Technical Skills": json.loads(row["skills"]) if row["skills"] else [],
                "Education": row["education"],
                "Certifications": row["certifications"],
                "Projects": "Documented candidate projects"
            }

    if req.jd_id and not jd_reqs:
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM job_descriptions WHERE id = ?", (req.jd_id,)).fetchone()
        conn.close()
        if row:
            import json
            jd_reqs = json.loads(row["structured_requirements"])

    ok, questions_dict, err = generate_interview_questions(cand_profile, jd_reqs)
    if not ok:
        raise HTTPException(status_code=500, detail=f"Failed to generate interview questions: {err}")

    return {"questions": questions_dict}


@app.get("/api/dashboard-stats")
def api_get_dashboard_stats():
    """Retrieve recruitment pipeline analytics for dashboard metrics."""
    return get_dashboard_metrics()


# CANDIDATE SIDE APIS
@app.post("/api/candidate-analysis")
async def api_candidate_full_analysis(
    resume: UploadFile = File(...),
    jd_text: str = Form(...)
):
    """Full candidate resume + JD analysis."""
    save_p = os.path.join(UPLOAD_DIR, resume.filename)
    with open(save_p, "wb") as buffer:
        shutil.copyfileobj(resume.file, buffer)

    ok_p, r_text, err_p = parse_resume(save_p)
    if not ok_p:
        raise HTTPException(status_code=400, detail=f"Resume parse error: {err_p}")

    ok_jd, jd_reqs, err_jd = parse_job_description(jd_text)
    if not ok_jd:
        raise HTTPException(status_code=400, detail=f"JD parse error: {err_jd}")

    headers = ["Candidate Name", "Email Address", "Mobile Number", "Total Experience (Years)", "Technical Skills", "Education", "Certifications", "Projects"]
    _, cand_data, _, _ = extract_candidate_data(r_text, headers)
    
    ok_m, match_res, err_m = match_resume_to_jd(cand_data, r_text, jd_reqs)
    mismatch_reasons = identify_possible_mismatch_reasons(match_res, cand_data, jd_reqs)
    section_feedback = analyze_resume_sections(r_text, jd_reqs)
    ats_res = analyze_ats_compatibility(r_text, jd_reqs)
    _, rewordings, _ = improve_resume_wording(r_text, jd_reqs)
    job_suggs = generate_job_specific_suggestions(cand_data, jd_reqs, match_res)

    return {
        "candidate_name": cand_data.get("Candidate Name", "Candidate"),
        "match_result": match_res,
        "mismatch_reasons": mismatch_reasons,
        "section_feedback": section_feedback,
        "ats_analysis": ats_res,
        "bullet_improvements": rewordings,
        "job_specific_suggestions": job_suggs
    }


@app.post("/api/section-analysis")
def api_section_analysis(req: SectionAnalysisRequest):
    """Analyze resume section by section."""
    _, jd_reqs, _ = parse_job_description(req.jd_text) if req.jd_text else (True, {}, "")
    feedback = analyze_resume_sections(req.resume_text, jd_reqs)
    return {"section_feedback": feedback}


@app.post("/api/ats-check")
def api_ats_check(req: ATSCheckRequest):
    """Check ATS compatibility."""
    _, jd_reqs, _ = parse_job_description(req.jd_text) if req.jd_text else (True, {}, "")
    res = analyze_ats_compatibility(req.resume_text, jd_reqs)
    return res


@app.post("/api/improve-resume")
def api_improve_resume(req: ImproveResumeRequest):
    """Get grounded bullet point rewording suggestions."""
    _, jd_reqs, _ = parse_job_description(req.jd_text) if req.jd_text else (True, {}, "")
    ok, improvements, err = improve_resume_wording(req.resume_text, jd_reqs)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    return {"improvements": improvements}


@app.get("/api/download/{filename}")
def download_file(filename: str):
    """Download output report file."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        # Also check upload directory if requested
        filepath = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="Requested file not found.")

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/octet-stream"
    )

# Mount React static frontend dist directory at root
if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")

