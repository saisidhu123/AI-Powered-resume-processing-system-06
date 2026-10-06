"""
services/candidate_database.py

SQLite Persistent Candidate Database & Recruitment Pipeline Storage.

Provides persistent storage for:
- Candidate profiles & parsed resume text
- Job Descriptions & extracted requirements
- Candidate screening match runs & scores
- Recruitment pipeline statuses (Applied -> AI Screened -> Shortlisted -> Interview -> Selected / Rejected)
- Recruiter audit notes
- Multi-field candidate search & natural language queries
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

DB_PATH = os.path.join(os.getcwd(), "candidate_db.sqlite")


def get_db_connection():
    """Returns a connection to the SQLite candidate database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initializes SQLite database tables if they do not exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Job Descriptions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_descriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_title TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                structured_requirements TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Candidates Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                total_experience REAL DEFAULT 0.0,
                skills TEXT,
                education TEXT,
                certifications TEXT,
                tech_domains TEXT,
                raw_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. Screening Runs / Matches Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screening_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                jd_id INTEGER NOT NULL,
                match_score REAL NOT NULL,
                scoring_breakdown TEXT,
                strengths TEXT,
                gaps TEXT,
                evidence_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id),
                FOREIGN KEY (jd_id) REFERENCES job_descriptions(id)
            )
        """)

        # 4. Recruitment Pipeline Status Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recruitment_pipeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                jd_id INTEGER DEFAULT 0,
                status TEXT DEFAULT 'AI Screened',
                recruiter_notes TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id)
            )
        """)
        
        conn.commit()


# Initialize database schema immediately on module load
init_database()


def save_job_description(job_title: str, raw_text: str, structured_requirements: Dict[str, Any]) -> int:
    """Saves a Job Description and returns its ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO job_descriptions (job_title, raw_text, structured_requirements) VALUES (?, ?, ?)",
            (job_title, raw_text, json.dumps(structured_requirements))
        )
        conn.commit()
        return cursor.lastrowid


def save_candidate_profile(candidate_data: Dict[str, Any], raw_text: str = "") -> int:
    """Saves candidate profile details and returns candidate ID."""
    name = candidate_data.get("Candidate Name", candidate_data.get("name", "Unknown Candidate"))
    email = candidate_data.get("Email Address", candidate_data.get("email", ""))
    phone = candidate_data.get("Mobile Number", candidate_data.get("phone", ""))
    
    try:
        exp = float(str(candidate_data.get("Total Experience (Years)", 0)).replace("+", "").strip())
    except Exception:
        exp = 0.0

    raw_skills = candidate_data.get("Technical Skills", candidate_data.get("skills", candidate_data.get("Skills", [])))
    if isinstance(raw_skills, str):
        skills_list = [s.strip() for s in raw_skills.split(",") if s.strip()]
    elif isinstance(raw_skills, list):
        skills_list = [str(s).strip() for s in raw_skills if str(s).strip()]
    else:
        skills_list = []
    skills = json.dumps(skills_list)
    edu = str(candidate_data.get("Education", ""))
    certs = str(candidate_data.get("Certifications", ""))
    domains = json.dumps(candidate_data.get("_tech_domains", ["General Tech"]))

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Check if email/phone candidate already exists
        if email:
            cursor.execute("SELECT id FROM candidates WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                return row["id"]

        cursor.execute(
            """INSERT INTO candidates 
               (candidate_name, email, phone, total_experience, skills, education, certifications, tech_domains, raw_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, email, phone, exp, skills, edu, certs, domains, raw_text)
        )
        conn.commit()
        cand_id = cursor.lastrowid
        
        # Initialize default pipeline status
        cursor.execute(
            "INSERT INTO recruitment_pipeline (candidate_id, status, recruiter_notes) VALUES (?, ?, ?)",
            (cand_id, "AI Screened", "Automatically ingested via AI processing.")
        )
        conn.commit()
        return cand_id


def save_screening_result(cand_id: int, jd_id: int, match_result: Dict[str, Any]) -> int:
    """Saves screening match results between candidate and JD."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        score = match_result.get("overall_match_score", 0.0)
        breakdown = json.dumps(match_result.get("scoring_breakdown", {}))
        strengths = json.dumps(match_result.get("strengths", []))
        gaps = json.dumps(match_result.get("gaps", []))
        evidence = json.dumps(match_result.get("evidence_map", {}))

        cursor.execute(
            """INSERT INTO screening_results 
               (candidate_id, jd_id, match_score, scoring_breakdown, strengths, gaps, evidence_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (cand_id, jd_id, score, breakdown, strengths, gaps, evidence)
        )
        conn.commit()
        return cursor.lastrowid


def update_candidate_status(cand_id: int, status: str, notes: str = "") -> bool:
    """Updates candidate recruitment status and recruiter notes."""
    valid_statuses = ["Applied", "AI Screened", "Shortlisted", "Interview", "Selected", "Rejected"]
    if status not in valid_statuses:
        status = "AI Screened"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM recruitment_pipeline WHERE candidate_id = ?", (cand_id,))
        row = cursor.fetchone()
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if row:
            cursor.execute(
                "UPDATE recruitment_pipeline SET status = ?, recruiter_notes = ?, updated_at = ? WHERE candidate_id = ?",
                (status, notes, now_str, cand_id)
            )
        else:
            cursor.execute(
                "INSERT INTO recruitment_pipeline (candidate_id, status, recruiter_notes, updated_at) VALUES (?, ?, ?, ?)",
                (cand_id, status, notes, now_str)
            )
        conn.commit()
        return True


def get_all_candidates_with_status() -> List[Dict[str, Any]]:
    """Retrieves all candidates stored in the database with their current pipeline status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT c.*, p.status as current_status, p.recruiter_notes, MAX(s.match_score) as match_score
            FROM candidates c
            LEFT JOIN recruitment_pipeline p ON c.id = p.candidate_id
            LEFT JOIN screening_results s ON c.id = s.candidate_id
            GROUP BY c.id
            ORDER BY c.id DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        results = []
        for r in rows:
            raw_sk = r["skills"]
            parsed_sk = []
            if raw_sk:
                try:
                    parsed = json.loads(raw_sk)
                    if isinstance(parsed, list):
                        parsed_sk = [str(x).strip() for x in parsed if str(x).strip()]
                    elif isinstance(parsed, str):
                        parsed_sk = [s.strip() for s in parsed.split(",") if s.strip()]
                except Exception:
                    if isinstance(raw_sk, str):
                        parsed_sk = [s.strip() for s in raw_sk.split(",") if s.strip()]

            results.append({
                "id": r["id"],
                "candidate_name": r["candidate_name"],
                "email": r["email"],
                "phone": r["phone"],
                "total_experience": r["total_experience"],
                "skills": parsed_sk,
                "education": r["education"],
                "certifications": r["certifications"],
                "status": r["current_status"] or "Applied",
                "notes": r["recruiter_notes"] or "",
                "match_score": r["match_score"] or 0.0,
                "created_at": r["created_at"]
            })
        return results


def clear_candidate_database() -> bool:
    """Deletes all candidate records, screening results, and recruitment pipeline entries."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM candidates")
        cursor.execute("DELETE FROM screening_results")
        cursor.execute("DELETE FROM recruitment_pipeline")
        conn.commit()
        return True



def search_candidates(
    query: str = "",
    min_exp: float = 0.0,
    required_skills: List[str] = None,
    status_filter: str = "ALL"
) -> List[Dict[str, Any]]:
    """Searches candidates using structured parameters."""
    all_cands = get_all_candidates_with_status()
    filtered = []
    
    query_lower = query.lower().strip() if query else ""
    req_skills_lower = [s.lower().strip() for s in (required_skills or []) if s.strip()]

    for c in all_cands:
        # Experience check
        if c["total_experience"] < min_exp:
            continue
            
        # Status filter check
        if status_filter != "ALL" and c["status"].lower() != status_filter.lower():
            continue

        # Text query check
        if query_lower:
            cand_str = f"{c['candidate_name']} {c['email']} {c['education']} {c['certifications']} {' '.join(c['skills'])}".lower()
            if query_lower not in cand_str:
                continue

        # Skills check
        if req_skills_lower:
            cand_skills_str = " ".join([str(s).lower() for s in c["skills"]])
            if not all(sk in cand_skills_str for sk in req_skills_lower):
                continue

        filtered.append(c)

    return filtered


def get_dashboard_metrics() -> Dict[str, Any]:
    """Computes overall recruitment analytics from database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM candidates")
        total_cand = cursor.fetchone()["total"]
        
        cursor.execute("SELECT status, COUNT(*) as count FROM recruitment_pipeline GROUP BY status")
        status_rows = cursor.fetchall()
        
        status_counts = {
            "Applied": 0,
            "AI Screened": 0,
            "Shortlisted": 0,
            "Interview": 0,
            "Selected": 0,
            "Rejected": 0
        }
        for r in status_rows:
            st_name = r["status"]
            if st_name in status_counts:
                status_counts[st_name] = r["count"]

        return {
            "total_candidates": total_cand,
            "status_counts": status_counts
        }
