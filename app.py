"""
AI Recruitment & Resume Intelligence Platform - Primary Streamlit Application.

Provides two distinct portal experiences:
1. 👔 RECRUITER PORTAL:
   - Dashboard & Pipeline Analytics
   - Job Description Extractor
   - Resume Screening (Single & Batch) with Transparent JD Matching
   - Automated Candidate Ranking & Comparison
   - Persistent Candidate Database & Multi-Criteria Search
   - Recruitment Pipeline Status Tracker & Audit Notes
   - Grounded AI Interview Question Generator
   
2. 🎯 CANDIDATE PORTAL:
   - Resume + JD Match Analysis & Score Breakdown
   - Missing Skills & "Why May My Resume Not Match?"
   - Section-by-Section Resume Analysis
   - ATS Readability & Compatibility Checker
   - Grounded Resume Improvement & Bullet Rewording
   - Job-Specific Resume Suggestions
"""

import os
import time
import json
import pandas as pd
import streamlit as st
import importlib
from datetime import datetime

# Existing Services
import utils.helpers
importlib.reload(utils.helpers)
from utils.helpers import format_skills
import services.field_extractor
import services.resume_parser
import services.excel_service
import services.duplicate_detector
import services.llm_service
importlib.reload(services.llm_service)
import services.batch_processor

from services.llm_service import check_llm_status, extract_candidate_data, HF_MODEL
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

# New Platform Services
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

# Page Configuration
st.set_page_config(
    page_title="AI Recruitment & Resume Intelligence Platform",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern UI design
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #38BDF8 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #94A3B8;
        margin-bottom: 1.5rem;
    }
    .status-badge-online {
        background-color: #DEF7EC;
        color: #03543F;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
        font-size: 0.88rem;
    }
    .status-badge-offline {
        background-color: #FDE8E8;
        color: #9B1C1C;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
        font-size: 0.88rem;
    }
    .metric-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: 800;
        color: #F8FAFC;
    }
    .metric-lbl {
        font-size: 0.85rem;
        color: #94A3B8;
        font-weight: 600;
    }
    .evidence-box {
        background-color: #1E293B;
        color: #E2E8F0;
        border-left: 4px solid #3B82F6;
        padding: 12px;
        border-radius: 6px;
        margin: 8px 0;
        font-size: 0.92rem;
    }
    .disclaimer-box {
        background-color: #FEF3C7;
        color: #78350F;
        border-left: 4px solid #F59E0B;
        padding: 12px 16px;
        border-radius: 6px;
        font-size: 0.9rem;
        font-weight: 500;
        margin-bottom: 15px;
    }
    .disclaimer-box b {
        color: #451A03;
    }
</style>
""", unsafe_allow_html=True)

# Directories setup
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
OUTPUT_DIR = os.path.join(os.getcwd(), "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- SIDEBAR PORTAL SELECTION ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=64)
st.sidebar.title("Platform Portal")

portal = st.sidebar.radio(
    "Select User Experience:",
    ["👔 RECRUITER PORTAL", "🎯 CANDIDATE PORTAL"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("System Health")

is_online, status_msg, available_models = check_llm_status()
if is_online:
    st.sidebar.markdown(f'<div class="status-badge-online">🟢 {status_msg}</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown(f'<div class="status-badge-offline">🔴 {status_msg}</div>', unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.info(f"**AI Model:** `{HF_MODEL}`\n\n**Storage Engine:** `SQLite (candidate_db.sqlite)`")
if st.sidebar.button("🧹 Clear Database Records", help="Purge all candidate profiles and screening history from SQLite database"):
    clear_candidate_database()
    st.sidebar.success("Database cleared successfully!")
    st.rerun()


# ==============================================================================
# 👔 RECRUITER PORTAL
# ==============================================================================
if portal == "👔 RECRUITER PORTAL":
    st.markdown('<div class="main-header">AI Recruitment & Screening Platform</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Automated Candidate Matching, Batch Ranking, Evidence Verification & Pipeline Management</div>', unsafe_allow_html=True)

    # Human-in-the-Loop Disclaimer
    st.markdown("""
    <div class="disclaimer-box">
        🤝 <b>Human-in-the-Loop Notice:</b> AI provides requirement extraction, match scoring, and evidence recommendations. <b>The Recruiter/Hiring Manager makes the final recruitment decision.</b>
    </div>
    """, unsafe_allow_html=True)

    recruiter_tab = st.tabs([
        "📊 Dashboard",
        "📋 JD Extractor",
        "⚡ Resume Screening (Single & Batch)",
        "🥇 Candidate Ranking",
        "⚖️ Side-by-Side Comparison",
        "🗄️ Candidate Database & Pipeline",
        "❓ AI Interview Qs"
    ])

    # ---------------------------------------------------------
    # TAB 1: DASHBOARD
    # ---------------------------------------------------------
    with recruiter_tab[0]:
        st.subheader("Recruitment Pipeline Analytics")
        metrics = get_dashboard_metrics()
        
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-val">{metrics["total_candidates"]}</div><div class="metric-lbl">Total Candidates</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-val">{metrics["status_counts"].get("Applied", 0)}</div><div class="metric-lbl">Applied</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-val">{metrics["status_counts"].get("AI Screened", 0)}</div><div class="metric-lbl">AI Screened</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="metric-card"><div class="metric-val">{metrics["status_counts"].get("Shortlisted", 0)}</div><div class="metric-lbl">Shortlisted</div></div>', unsafe_allow_html=True)
        with c5:
            st.markdown(f'<div class="metric-card"><div class="metric-val">{metrics["status_counts"].get("Interview", 0)}</div><div class="metric-lbl">Interview</div></div>', unsafe_allow_html=True)
        with c6:
            st.markdown(f'<div class="metric-card"><div class="metric-val">{metrics["status_counts"].get("Selected", 0)}</div><div class="metric-lbl">Selected</div></div>', unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("Recent Ingested Candidates")
        recent_cands = get_all_candidates_with_status()[:10]
        if recent_cands:
            df_rec = pd.DataFrame(recent_cands)[["id", "candidate_name", "email", "total_experience", "status", "match_score", "created_at"]]
            st.dataframe(df_rec, use_container_width=True, hide_index=True)
        else:
            st.info("No candidate profiles ingested yet. Upload resumes in the Screening tab.")

    # ---------------------------------------------------------
    # TAB 2: JD EXTRACTOR
    # ---------------------------------------------------------
    with recruiter_tab[1]:
        st.subheader("Job Description Requirement Extractor")
        jd_input_type = st.radio("Provide Job Description via:", ["Paste Raw Text", "Upload File (PDF/DOCX/TXT)"], horizontal=True)
        
        jd_text_val = ""
        if jd_input_type == "Paste Raw Text":
            jd_text_val = st.text_area("Paste Job Description Text:", height=200, placeholder="Paste job requirements, skills, experience needed...")
        else:
            uploaded_jd = st.file_uploader("Upload Job Description File", type=["pdf", "docx", "txt"])
            if uploaded_jd:
                save_p = os.path.join(UPLOAD_DIR, uploaded_jd.name)
                with open(save_p, "wb") as f:
                    f.write(uploaded_jd.getbuffer())
                ok_p, jd_text_val, err_p = parse_resume(save_p)

        if st.button("🔍 Extract Structured JD Requirements", type="primary"):
            if not jd_text_val.strip():
                st.error("Please provide Job Description text or file.")
            else:
                with st.spinner("Analyzing Job Description with AI..."):
                    ok_jd, structured_jd, err_jd = parse_job_description(jd_text_val)
                    if ok_jd:
                        save_job_description(structured_jd.get("job_title", "Position"), jd_text_val, structured_jd)
                        st.success(f"Extracted requirements for **{structured_jd.get('job_title')}**")
                        
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown("#### 🎯 Required Skills (Mandatory)")
                            for sk in structured_jd.get("required_skills", []):
                                st.markdown(f"- **{sk}**")
                            st.markdown(f"**Required Experience:** {structured_jd.get('required_experience_years', 'Unstated')} years")
                            st.markdown(f"**Education:** {', '.join(structured_jd.get('education_requirements', ['Not specified']))}")
                        with col_b:
                            st.markdown("#### 🌟 Preferred Skills (Nice-to-Have)")
                            for sk in structured_jd.get("preferred_skills", []):
                                st.markdown(f"- {sk}")
                            st.markdown(f"**Certifications:** {', '.join(structured_jd.get('certifications', ['None']))}")
                            st.markdown(f"**Domain:** {structured_jd.get('domain_requirements', 'General')}")
                            
                        st.session_state["active_jd_requirements"] = structured_jd
                        st.session_state["active_jd_text"] = jd_text_val
                    else:
                        st.error(f"Failed to extract JD requirements: {err_jd}")

    # ---------------------------------------------------------
    # TAB 3: RESUME SCREENING
    # ---------------------------------------------------------
    with recruiter_tab[2]:
        st.subheader("Resume Screening & Transparent Matching")
        
        # Select active JD
        conn = get_db_connection()
        jds = conn.execute("SELECT id, job_title, created_at FROM job_descriptions ORDER BY id DESC").fetchall()
        conn.close()
        
        jd_options = {f"#{row['id']} - {row['job_title']} ({row['created_at'][:10]})": row['id'] for row in jds}
        
        if not jd_options and "active_jd_text" not in st.session_state:
            st.warning("Please extract a Job Description in the 'JD Extractor' tab first.")
        else:
            selected_jd_label = st.selectbox("Select Target Job Description:", list(jd_options.keys()) if jd_options else ["Active Extracted JD"])
            
            screening_mode = st.radio("Screening Mode:", ["🚀 Single Candidate Screening", "⚡ Batch Screening (Multiple Resumes)"], horizontal=True)

            if screening_mode == "🚀 Single Candidate Screening":
                single_resume = st.file_uploader("Upload Candidate Resume (PDF/DOCX)", type=["pdf", "docx", "doc"], key="single_screen")
                if single_resume and st.button("Run Transparent Matching", type="primary"):
                    save_p = os.path.join(UPLOAD_DIR, single_resume.name)
                    with open(save_p, "wb") as f:
                        f.write(single_resume.getbuffer())
                        
                    with st.spinner("Processing candidate & evaluating evidence..."):
                        ok_p, r_text, err_p = parse_resume(save_p)
                        headers = ["Candidate Name", "Email Address", "Mobile Number", "Total Experience (Years)", "Technical Skills", "Education", "Certifications", "Projects"]
                        _, cand_data, _, _ = extract_candidate_data(r_text, headers)
                        
                        target_jd_id = jd_options[selected_jd_label] if jd_options else None
                        target_jd_text = st.session_state.get("active_jd_text", "")
                        
                        if target_jd_id:
                            conn = get_db_connection()
                            row = conn.execute("SELECT * FROM job_descriptions WHERE id = ?", (target_jd_id,)).fetchone()
                            conn.close()
                            jd_reqs = json.loads(row["structured_requirements"])
                        else:
                            _, jd_reqs, _ = parse_job_description(target_jd_text)

                        ok_m, match_res, err_m = match_resume_to_jd(cand_data, r_text, jd_reqs)
                        
                        if ok_m:
                            cand_id = save_candidate_profile(cand_data, r_text)
                            if target_jd_id:
                                save_screening_result(cand_id, target_jd_id, match_res)

                            st.success(f"Analysis Complete for **{cand_data.get('Candidate Name')}**")
                            st.metric("Overall Match Score", f"{match_res['overall_match_score']}%")

                            # Scoring breakdown
                            st.markdown("#### 📊 Transparent Score Breakdown")
                            sb = match_res["scoring_breakdown"]
                            col_b1, col_b2, col_b3 = st.columns(3)
                            col_b1.write(f"**Required Skills:** {sb['required_skills']['score']} / {sb['required_skills']['max']}")
                            col_b2.write(f"**Experience:** {sb['experience']['score']} / {sb['experience']['max']}")
                            col_b3.write(f"**Preferred Skills:** {sb['preferred_skills']['score']} / {sb['preferred_skills']['max']}")

                            # Strengths & Gaps
                            c_str, c_gap = st.columns(2)
                            with c_str:
                                st.markdown("#### ✅ Grounded Strengths")
                                for s in match_res["strengths"]:
                                    st.markdown(f"- {s}")
                            with c_gap:
                                st.markdown("#### ⚠️ Identified Gaps")
                                for g in match_res["gaps"]:
                                    st.markdown(f"- {g}")

                            # View Evidence Feature
                            st.markdown("#### 🔍 Grounded Text Evidence (View Evidence)")
                            for sk, ev in match_res["evidence_map"].items():
                                with st.expander(f"Skill: {sk} — Match: {ev.get('match_level')} ({ev.get('section')})"):
                                    st.markdown(f'<div class="evidence-box"><b>Exact Resume Quote:</b><br>"{ev.get("snippet")}"</div>', unsafe_allow_html=True)
                        else:
                            st.error(f"Matching failed: {err_m}")

            else:  # Batch Screening
                batch_resumes = st.file_uploader("Upload Multiple Candidate Resumes", type=["pdf", "docx", "doc"], accept_multiple_files=True, key="batch_screen")
                if batch_resumes and st.button("🚀 Process Batch & Rank Candidates", type="primary"):
                    target_jd_id = jd_options[selected_jd_label] if jd_options else None
                    conn = get_db_connection()
                    row = conn.execute("SELECT * FROM job_descriptions WHERE id = ?", (target_jd_id,)).fetchone()
                    conn.close()
                    jd_reqs = json.loads(row["structured_requirements"])
                    
                    headers = ["Candidate Name", "Email Address", "Mobile Number", "Total Experience (Years)", "Technical Skills", "Education", "Certifications", "Projects"]
                    
                    progress_bar = st.progress(0)
                    ranked = []
                    
                    for idx, r_file in enumerate(batch_resumes):
                        save_p = os.path.join(UPLOAD_DIR, r_file.name)
                        with open(save_p, "wb") as f:
                            f.write(r_file.getbuffer())
                        
                        ok_p, r_text, _ = parse_resume(save_p)
                        if ok_p and r_text.strip():
                            _, cand_data, _, _ = extract_candidate_data(r_text, headers)
                            ok_m, match_res, _ = match_resume_to_jd(cand_data, r_text, jd_reqs)
                            if ok_m:
                                cand_id = save_candidate_profile(cand_data, r_text)
                                save_screening_result(cand_id, target_jd_id, match_res)
                                ranked.append({
                                    "Candidate": cand_data.get("Candidate Name", r_file.name),
                                    "Score": match_res["overall_match_score"],
                                    "Experience": cand_data.get("Total Experience (Years)", 0),
                                    "Strengths": len(match_res["strengths"]),
                                    "Gaps": len(match_res["gaps"])
                                })
                        progress_bar.progress((idx + 1) / len(batch_resumes))

                    ranked.sort(key=lambda x: x["Score"], reverse=True)
                    st.success(f"Batch Processing Complete! Processed {len(ranked)} resumes.")
                    st.dataframe(pd.DataFrame(ranked), use_container_width=True, hide_index=True)

    # ---------------------------------------------------------
    # TAB 4: CANDIDATE RANKING & COMPARISON
    # ---------------------------------------------------------
    with recruiter_tab[3]:
        col_rank_head, col_rank_btn = st.columns([3, 1])
        with col_rank_head:
            st.subheader("Automatic Candidate Ranking")
        with col_rank_btn:
            if st.button("🧹 Clear Database", key="btn_clear_rank"):
                clear_candidate_database()
                st.success("Candidate database cleared!")
                st.rerun()

        cands = get_all_candidates_with_status()
        if not cands:
            st.info("No candidate profiles available for ranking.")
        else:
            formatted_cands = []
            for c in cands:
                c_copy = c.copy()
                c_copy["skills"] = format_skills(c_copy.get("skills"))
                formatted_cands.append(c_copy)
                
            df_rank = pd.DataFrame(formatted_cands).sort_values(by="match_score", ascending=False).reset_index(drop=True)
            df_rank["skills"] = df_rank["skills"].astype(str)
            st.dataframe(df_rank[["id", "candidate_name", "match_score", "total_experience", "status", "skills"]], use_container_width=True, hide_index=True)

    with recruiter_tab[4]:
        st.subheader("Side-by-Side Candidate Comparison")
        cands = get_all_candidates_with_status()
        cand_map = {f"#{c['id']} - {c['candidate_name']} ({c['match_score']}%)": c for c in cands}
        
        if len(cand_map) >= 2:
            selected_pair = st.multiselect("Select Candidates to Compare (2 or 3):", list(cand_map.keys()), max_selections=3)
            if len(selected_pair) >= 2:
                cols = st.columns(len(selected_pair))
                for idx, key in enumerate(selected_pair):
                    cand = cand_map[key]
                    with cols[idx]:
                        st.markdown(f"### {cand['candidate_name']}")
                        st.metric("Match Score", f"{cand['match_score']}%")
                        st.write(f"**Experience:** {cand['total_experience']} years")
                        st.write(f"**Status:** `{cand['status']}`")
                        st.write(f"**Education:** {cand['education']}")
                        st.write(f"**Skills:** {format_skills(cand['skills'], max_items=5)}")
        else:
            st.info("At least 2 candidates required for comparison.")

    # ---------------------------------------------------------
    # TAB 5: DATABASE & PIPELINE
    # ---------------------------------------------------------
    with recruiter_tab[5]:
        st.subheader("Candidate Database Search & Pipeline Status Tracker")
        
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            q_str = st.text_input("Search Name/Skills/Text:")
        with col_s2:
            min_exp_filter = st.number_input("Minimum Experience (Years):", min_value=0.0, step=0.5)
        with col_s3:
            status_filter = st.selectbox("Pipeline Status Filter:", ["ALL", "Applied", "AI Screened", "Shortlisted", "Interview", "Selected", "Rejected"])

        filtered_cands = search_candidates(query=q_str, min_exp=min_exp_filter, status_filter=status_filter)
        st.markdown(f"Found **{len(filtered_cands)}** candidate(s)")
        
        for idx, c in enumerate(filtered_cands):
            with st.expander(f"#{c['id']} - {c['candidate_name']} | Status: {c['status']} | Match: {c['match_score']}%"):
                st.write(f"**Email:** {c['email']} | **Phone:** {c['phone']} | **Exp:** {c['total_experience']} yrs")
                st.write(f"**Skills:** {format_skills(c['skills'])}")
                
                col_u1, col_u2 = st.columns([2, 3])
                with col_u1:
                    status_idx = ["Applied", "AI Screened", "Shortlisted", "Interview", "Selected", "Rejected"].index(c['status']) if c['status'] in ["Applied", "AI Screened", "Shortlisted", "Interview", "Selected", "Rejected"] else 0
                    new_st = st.selectbox("Update Status:", ["Applied", "AI Screened", "Shortlisted", "Interview", "Selected", "Rejected"], index=status_idx, key=f"st_{c['id']}_{idx}")
                with col_u2:
                    new_notes = st.text_input("Recruiter Notes:", value=c['notes'], key=f"notes_{c['id']}_{idx}")
                    
                if st.button("Save Updates", key=f"btn_{c['id']}_{idx}"):
                    update_candidate_status(c['id'], new_st, new_notes)
                    st.success(f"Updated status for #{c['id']} to {new_st}")
                    st.rerun()

    # ---------------------------------------------------------
    # TAB 6: INTERVIEW QUESTIONS
    # ---------------------------------------------------------
    with recruiter_tab[6]:
        st.subheader("Grounded AI Interview Question Generator")
        cands = get_all_candidates_with_status()
        cand_opts = {f"#{c['id']} - {c['candidate_name']}": c['id'] for c in cands}
        
        if cand_opts:
            sel_c_key = st.selectbox("Select Candidate for Interview:", list(cand_opts.keys()))
            if st.button("⚡ Generate Tailored Interview Questions", type="primary"):
                cand_id = cand_opts[sel_c_key]
                conn = get_db_connection()
                row = conn.execute("SELECT * FROM candidates WHERE id = ?", (cand_id,)).fetchone()
                conn.close()
                
                cand_prof = {
                    "Candidate Name": row["candidate_name"],
                    "Total Experience (Years)": row["total_experience"],
                    "Technical Skills": json.loads(row["skills"]) if row["skills"] else [],
                    "Education": row["education"]
                }
                
                ok_iq, iq_dict, err_iq = generate_interview_questions(cand_prof, {})
                if ok_iq:
                    for cat, qs in iq_dict.items():
                        st.markdown(f"### Category: {cat.replace('_', ' ').title()}")
                        for q_item in qs:
                            if isinstance(q_item, dict):
                                st.markdown(f"**Q:** {q_item.get('question')}")
                                st.markdown(f"_*Purpose:* {q_item.get('purpose')}_ | _*Evaluation Criteria:* {q_item.get('evaluation_criteria')}_")
                            else:
                                st.markdown(f"- {q_item}")
                            st.write("")


# ==============================================================================
# 🎯 CANDIDATE PORTAL
# ==============================================================================
else:
    st.markdown('<div class="main-header">Candidate Resume Intelligence Portal</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Analyze Your Resume Against Any Job Description, Identify Gaps, Check ATS Readability & Receive Grounded Improvements</div>', unsafe_allow_html=True)

    cand_tab = st.tabs([
        "🔍 Resume + JD Analysis",
        "❌ Mismatch Factors",
        "📑 Section Feedback",
        "🤖 ATS Compatibility",
        "✏️ Wording Improvements",
        "🎯 Job Optimization"
    ])

    with cand_tab[0]:
        st.subheader("Upload Your Resume & Target Job Description")
        c_resume_file = st.file_uploader("Upload Your Resume (PDF/DOCX)", type=["pdf", "docx", "doc"], key="cand_res")
        c_jd_text = st.text_area("Paste Target Job Description Text:", height=180, placeholder="Paste the job description you are targeting...")

        if st.button("🚀 Run Full Candidate Analysis", type="primary"):
            if not c_resume_file or not c_jd_text.strip():
                st.error("Please upload your resume and paste the target job description.")
            else:
                save_p = os.path.join(UPLOAD_DIR, c_resume_file.name)
                with open(save_p, "wb") as f:
                    f.write(c_resume_file.getbuffer())

                with st.spinner("Analyzing your resume against the target role..."):
                    ok_p, r_text, _ = parse_resume(save_p)
                    ok_jd, jd_reqs, _ = parse_job_description(c_jd_text)
                    
                    headers = ["Candidate Name", "Email Address", "Mobile Number", "Total Experience (Years)", "Technical Skills", "Education", "Certifications", "Projects"]
                    _, cand_data, _, _ = extract_candidate_data(r_text, headers)
                    
                    ok_m, match_res, _ = match_resume_to_jd(cand_data, r_text, jd_reqs)
                    mismatch_reasons = identify_possible_mismatch_reasons(match_res, cand_data, jd_reqs)
                    sec_feedback = analyze_resume_sections(r_text, jd_reqs)
                    ats_res = analyze_ats_compatibility(r_text, jd_reqs)
                    _, rewordings, _ = improve_resume_wording(r_text, jd_reqs)
                    job_suggs = generate_job_specific_suggestions(cand_data, jd_reqs, match_res)

                    st.session_state["cand_analysis_results"] = {
                        "match_res": match_res,
                        "mismatch_reasons": mismatch_reasons,
                        "sec_feedback": sec_feedback,
                        "ats_res": ats_res,
                        "rewordings": rewordings,
                        "job_suggs": job_suggs
                    }
                    st.rerun()

        res_data = st.session_state.get("cand_analysis_results")
        if res_data:
            match_res = res_data["match_res"]
            st.success("Analysis Complete!")
            st.metric("Your Target Match Score", f"{match_res['overall_match_score']}%")
            
            st.markdown("#### Skill Evaluation Summary")
            for sk, info in match_res["skill_evaluations"].items():
                lvl = info.get("level", "Missing")
                color = "🟢" if lvl == "Strong" else ("🔵" if lvl == "Good" else ("🟡" if lvl == "Limited" else "🔴"))
                st.markdown(f"{color} **{sk}**: `{lvl}`")

    with cand_tab[1]:
        st.subheader("Why May My Resume Not Be Getting Shortlisted?")
        st.markdown("""
        <div class="disclaimer-box">
            💡 <b>Note:</b> These are <b>POSSIBLE reasons</b> based on objective match against this specific Job Description. Only the employer knows actual selection reasons.
        </div>
        """, unsafe_allow_html=True)
        
        if res_data:
            for r in res_data["mismatch_reasons"]:
                with st.expander(f"[{r.get('impact', 'Medium')}] {r.get('category')} — {r.get('reason')}"):
                    st.info(f"**Recommendation:** {r.get('suggestion')}")
        else:
            st.info("Run full candidate analysis in the first tab to view mismatch factors.")

    with cand_tab[2]:
        st.subheader("Resume Section-by-Section Analysis")
        if res_data:
            for sec, fb in res_data["sec_feedback"].items():
                with st.expander(f"Section: {sec} (Relevance: {fb.get('jd_relevance')})"):
                    st.write(f"✅ **Good:** {fb.get('good')}")
                    st.write(f"⚠️ **Weakness:** {fb.get('weak')}")
                    st.write(f"💡 **Improvement Suggestion:** {fb.get('improvement_suggestion')}")
        else:
            st.info("Run full candidate analysis in the first tab to view section feedback.")

    with cand_tab[3]:
        st.subheader("ATS (Applicant Tracking System) Compatibility")
        if res_data:
            ats = res_data["ats_res"]
            st.metric("ATS Readiness Score", f"{ats['ats_readiness_score']}%", delta=ats['rating'])
            
            if ats["issues"]:
                st.markdown("#### ⚠️ ATS Readiness Warnings")
                for iss in ats["issues"]:
                    st.warning(f"**[{iss['check']}]** {iss['finding']}\n\n*Fix:* {iss['recommendation']}")
            
            if ats["passed_checks"]:
                st.markdown("#### ✅ Passed ATS Checks")
                for p in ats["passed_checks"]:
                    st.success(f"- {p}")
        else:
            st.info("Run full candidate analysis in the first tab to view ATS compatibility.")

    with cand_tab[4]:
        st.subheader("Grounded Resume Bullet Wording Improvements")
        st.markdown("_Enhance clarity and action verbs without fabricating fake skills or experience._")
        if res_data:
            for imp in res_data["rewordings"]:
                st.markdown(f"**Original Bullet:** `{imp.get('original')}`")
                st.markdown(f"**Suggested Rewording:** `{imp.get('suggested')}`")
                st.caption(f"Rationale: {imp.get('rationale')}")
                st.markdown("---")
        else:
            st.info("Run full candidate analysis in the first tab to view rewording suggestions.")

    with cand_tab[5]:
        st.subheader("Job-Specific Resume Optimization Suggestions")
        if res_data:
            for sug in res_data["job_suggs"]:
                st.info(f"**{sug.get('area')} - {sug.get('action')}**\n\n{sug.get('recommendation')}")
        else:
            st.info("Run full candidate analysis in the first tab to view job-specific suggestions.")
