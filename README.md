# AI Recruitment & Resume Intelligence Platform

An enterprise-ready, dual-sided AI recruitment platform for **Recruiters / HR** and **Candidates / Job Seekers**, powered by **Groq Cloud LLM** (`groq/compound-mini` / `llama-3.3-70b-versatile`), Streamlit, FastAPI, React (Vite + Tailwind CSS), and SQLite.

---

## 🎯 Platform Purpose & Overview

Recruitment teams face high administrative overhead manually reviewing candidate resumes, comparing them to complex Job Descriptions (JDs), tracking candidates across recruitment pipelines, and building screening reports. At the same time, job seekers lack transparency into why their resume may not match a job description, what skills they are missing, how ATS parsers read their resume, and how to reword bullet points for maximum impact.

This upgraded **AI Recruitment & Resume Intelligence Platform** answers two major questions:

- **RECRUITER:** *"Which candidates are most suitable for this job, why are they matched, and what evidence supports this claim?"*
- **CANDIDATE:** *"Why may my resume not be matching this job description, what exact skills are missing, and how can I improve my resume without fabricating experience?"*

---

## ✨ Key Capabilities & Dual-Sided Features

### 👔 1. RECRUITER / HR PORTAL
- **Job Description Requirement Extractor**: Upload or paste JD text/file; automatically extracts structured required vs preferred skills, experience years, education, certifications, and responsibilities.
- **Single & Batch Resume Screening**: Process 1 to 100+ resumes concurrently against any target JD.
- **Transparent Weighted Match Scoring**: Calculates deterministic match scores (Required Skills 40%, Experience 25%, Preferred Skills 15%, Education 10%, Certifications 5%, Projects 5%) rather than random LLM percentages.
- **Grounded "View Evidence"**: Displays exact quotes extracted directly from the candidate's resume for every matched skill claim.
- **Automatic Candidate Ranking**: Ranks incoming candidate batches by match score with filter controls.
- **Side-by-Side Candidate Comparison**: Compare selected candidate profiles side-by-side.
- **Persistent Candidate Database & Search**: SQLite candidate storage (`candidate_db.sqlite`) with multi-attribute filtering (skills, experience, status) and search.
- **Recruitment Pipeline Status Tracker**: Track status (`Applied` → `AI Screened` → `Shortlisted` → `Interview` → `Selected` → `Rejected`) and record recruiter audit notes.
- **Grounded AI Interview Question Generator**: Generates targeted questions categorized by Technical, Project-based, Experience-based, Skill verification, and Role-specific topics.

### 🎯 2. CANDIDATE / JOB SEEKER PORTAL
- **Resume + JD Match Analysis**: Instant match score breakdown against any job description.
- **"Why May My Resume Not Match?"**: Identifies potential mismatch factors (missing skills, experience gaps, generic project descriptions) with clear disclaimers that employer feedback is unknown.
- **Missing Skills Breakdown**: Distinguishes `Strong`, `Good`, `Limited`, and `Missing` skills.
- **Section-by-Section Analysis**: Evaluates Summary, Skills, Experience, Projects, Education, and Certifications for strengths, weaknesses, and actionable fixes.
- **ATS Compatibility & Readability Checker**: Evaluates document word count, standard section headings, special glyph risks, date formatting, and keyword density.
- **Grounded Wording Improvements**: Provides action-oriented bullet point rewording while strictly preserving 100% factual accuracy (never fabricates fake skills or experience).
- **Job-Specific Resume Optimization**: Recommends targeted adjustments for the selected position.

---

## 📊 Transparent Scoring Methodology

The overall candidate match score is **reproducible and deterministic**, computed using category weights:

$$\text{Overall Score} = S_{\text{req}} + S_{\text{exp}} + S_{\text{pref}} + S_{\text{edu}} + S_{\text{cert}} + S_{\text{proj}}$$

| Category | Default Weight | Description |
| :--- | :--- | :--- |
| **Required Skills** | **40%** | Evaluates presence and depth of mandatory JD technical skills (`Strong`: 100%, `Good`: 80%, `Limited`: 50%, `Missing`: 0%). |
| **Experience** | **25%** | Compares candidate total/relevant experience years against minimum JD requirements. |
| **Preferred Skills** | **15%** | Evaluates nice-to-have/desirable skills listed in the JD. |
| **Education** | **10%** | Checks minimum degree requirement satisfaction. |
| **Certifications** | **5%** | Evaluates required or preferred certifications. |
| **Projects & Other** | **5%** | Checks documented technical project execution. |

---

## 💻 Technology Stack

- **AI/LLM Provider**: Groq Cloud API (`groq/compound-mini`, `llama-3.3-70b-versatile`)
- **Primary Streamlit Interface**: Python Streamlit (`app.py`)
- **Full-Stack Web Interface**: React (Vite + Tailwind CSS) in `frontend/`
- **Backend & REST API**: FastAPI, Uvicorn in `server.py`
- **Database & Persistence**: SQLite (`candidate_db.sqlite`) via `services/candidate_database.py`
- **Document Parsing**: PyMuPDF (PDF), python-docx (DOCX)
- **Data & Excel Processing**: Pandas, OpenPyXL
- **Runtime**: Python 3.10+

---

## 🔒 Configuration & Environment Variables

Copy `.env.example` to `.env`:

```ini
HF_TOKEN=your_huggingface_token_here
HF_MODEL=meta-llama/Llama-3.2-3B-Instruct
```

*For Streamlit Cloud deployment, set `HF_TOKEN` and `HF_MODEL` under **App Settings -> Secrets**.*

---

## 🚀 How to Run Locally

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch Primary Streamlit Interface (Recruiter & Candidate Portals)
```bash
streamlit run app.py
```
Access in browser at: `http://localhost:8501`

### 3. Launch Full-Stack FastAPI + React Interface
```bash
# Build React frontend assets
cd frontend
npm install
npm run build
cd ..

# Start FastAPI Uvicorn server
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```
Access full-stack web app in browser at: `http://127.0.0.1:8000`

---

## 🤝 Human-in-the-Loop & Anti-Hallucination Guardrails

- **Final Hiring Decisions**: AI outputs decision-support scores and grounded evidence quotes. The recruiter/interviewer makes all hiring decisions.
- **Anti-Hallucination**: Evidence snippets are extracted directly from raw resume text. Missing skills or details are flagged as "Missing" or "Unable to determine". Rewording tools never introduce fake skills, metrics, or achievements.

---

## 🛡️ License & Maintenance

Built for enterprise recruitment automation and candidate empowerment.
