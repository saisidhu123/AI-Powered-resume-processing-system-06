import os
import re
import json
import requests
from typing import Tuple, Dict, Any, List
from dotenv import load_dotenv

from utils.helpers import (
    extract_json_from_response,
    classify_technology,
    classify_experience
)
from services.experience_engine import evaluate_total_experience
from services.ctc_extractor import extract_current_and_expected_ctc, sanitize_ctc_pair, clean_and_validate_ctc
from services.notice_period_extractor import extract_notice_period, normalize_notice_period
from services.field_extractor import (
    clean_and_reconstruct_text,
    calculate_experience_from_dates,
    normalize_skills,
    extract_all_fields_fallback,
    extract_name,
    extract_mobile,
    extract_skills,
    extract_notice_period,
    extract_experience,
    run_ai_candidate_screening
)

# Load environment variables from .env if present
DEFAULT_LOCAL_MODEL_PATH = os.path.join(os.getcwd(), "scratch", "local_models", "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")

def get_local_model_path() -> str:
    """Retrieve LOCAL_MODEL_PATH from Streamlit Secrets or environment variables."""
    load_dotenv(override=True)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "LOCAL_MODEL_PATH" in st.secrets:
            path = str(st.secrets["LOCAL_MODEL_PATH"]).strip()
            if path:
                return path if os.path.isabs(path) else os.path.abspath(path)
    except Exception:
        pass
    path = os.getenv("LOCAL_MODEL_PATH", "").strip()
    if path:
        return path if os.path.isabs(path) else os.path.abspath(path)
    return DEFAULT_LOCAL_MODEL_PATH

def get_hf_token() -> str:
    """Retrieve HF_TOKEN securely from Streamlit Secrets or environment variables."""
    load_dotenv(override=True)
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            for var_name in ["HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HF_API_KEY"]:
                if var_name in st.secrets:
                    key = str(st.secrets[var_name]).strip()
                    if key:
                        return key
    except Exception:
        pass
    for var_name in ["HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HF_API_KEY"]:
        key = os.getenv(var_name, "").strip()
        if key:
            return key
    return ""

def get_hf_model() -> str:
    """Retrieve HF_MODEL securely from Streamlit Secrets or environment variables."""
    load_dotenv(override=True)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "HF_MODEL" in st.secrets:
            model = str(st.secrets["HF_MODEL"]).strip()
            if model:
                return model
    except Exception:
        pass
    model = os.getenv("HF_MODEL", "").strip()
    if model:
        return model
    return "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"

HF_MODEL = get_hf_model()

# Backward compatibility aliases
def get_groq_api_key() -> str:
    return get_hf_token()

def get_groq_model() -> str:
    return get_hf_model()

GROQ_MODEL = HF_MODEL

# Singleton Local LLM Storage
_LOCAL_LLM_INSTANCE = None
_LOCAL_LLM_LOADED_PATH = ""

def get_local_llm_instance():
    """Returns a shared, single instance of the local GGUF model loaded in RAM."""
    global _LOCAL_LLM_INSTANCE, _LOCAL_LLM_LOADED_PATH
    model_path = get_local_model_path()

    if not os.path.exists(model_path):
        return None, f"Local GGUF model file not found at: {model_path}"

    if _LOCAL_LLM_INSTANCE is not None and _LOCAL_LLM_LOADED_PATH == model_path:
        return _LOCAL_LLM_INSTANCE, ""

    try:
        from llama_cpp import Llama
        print(f"[LLM Service] Loading shared local GGUF model: {os.path.basename(model_path)} (n_gpu_layers=0, n_threads=4)...")
        _LOCAL_LLM_INSTANCE = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=4,
            n_gpu_layers=0,
            verbose=False
        )
        _LOCAL_LLM_LOADED_PATH = model_path
        return _LOCAL_LLM_INSTANCE, ""
    except Exception as e:
        return None, f"Failed to initialize local GGUF llama-cpp model: {str(e)}"

def sanitize_error_msg(err_msg: str, api_key: str = "") -> str:
    """Sanitize error messages to ensure API keys/tokens are never exposed in UI or logs."""
    if not err_msg:
        return ""
    if api_key:
        err_msg = err_msg.replace(api_key, "[REDACTED_API_KEY]")
    err_msg = re.sub(r"hf_[a-zA-Z0-9_-]+", "[REDACTED_API_KEY]", err_msg)
    err_msg = re.sub(r"gsk_[a-zA-Z0-9_-]+", "[REDACTED_API_KEY]", err_msg)
    err_msg = re.sub(r"Bearer\s+[a-zA-Z0-9_-]+", "Bearer [REDACTED_API_KEY]", err_msg, flags=re.IGNORECASE)
    return err_msg

def check_llm_status() -> Tuple[bool, str, List[str]]:
    """
    Check if local GGUF model file is present and operational.
    Returns (is_online, message, model_list).
    """
    model_path = get_local_model_path()
    if not os.path.exists(model_path):
        return False, f"Local GGUF model file not found: {os.path.basename(model_path)}", []
    
    # Quick instance test
    llm, err = get_local_llm_instance()
    if not llm:
        return False, f"Local model loading error: {err}", []

    model_name = os.path.basename(model_path)
    return True, f"Local GGUF LLM Online ({model_name})", [model_name]

def check_ollama_status() -> Tuple[bool, str, List[str]]:
    """Backward compatibility alias for check_llm_status."""
    return check_llm_status()

def call_local_llm(prompt: str, temperature: float = 0.0, max_tokens: int = 600) -> Tuple[bool, str, str]:
    """
    Execute structured completion request against the shared local Qwen2.5-Coder GGUF model.
    Returns (success, raw_text_response, error_message).
    """
    llm, err = get_local_llm_instance()
    if not llm:
        return False, "", err

    try:
        formatted_prompt = f"<|im_start|>system\nYou are a precise AI assistant. Respond directly and accurately.<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
        res = llm(
            formatted_prompt,
            max_tokens=max_tokens,
            temperature=max(temperature, 0.01) if temperature > 0 else 0.01,
            stop=["<|im_end|>"]
        )
        raw_text = res["choices"][0]["text"].strip()
        if raw_text:
            return True, raw_text, ""
        return False, "", "Empty output generated by local GGUF model."
    except Exception as e:
        return False, "", f"Local GGUF LLM generation error: {str(e)}"

def call_hf_llm(prompt: str, temperature: float = 0.0, max_tokens: int = 600) -> Tuple[bool, str, str]:
    """Execute request via local GGUF model."""
    return call_local_llm(prompt, temperature=temperature, max_tokens=max_tokens)

def call_groq_llm(prompt: str, temperature: float = 0.0) -> Tuple[bool, str, str]:
    """Backward compatibility alias calling local GGUF model."""
    return call_local_llm(prompt, temperature=temperature)

def classify_header_concept(header_str: str) -> str:
    """
    Map an arbitrary header name to its canonical semantic concept.
    Strictly differentiates Expected CTC vs Current CTC vs Experience vs Location.
    """
    if not header_str:
        return "UNKNOWN"
    h = str(header_str).strip().lower().replace("_", " ").replace("-", " ").replace(".", " ")
    h = re.sub(r"\s+", " ", h).strip()

    # 1. Email (Check before address/location)
    if "email" in h or "mail" in h:
        return "EMAIL_ADDRESS"

    # 2. LinkedIn (Check before link/url)
    if "linkedin" in h:
        return "LINKEDIN"

    # 3. Expected CTC / Salary (Check before Experience and before Current CTC!)
    if any(k in h for k in ["expected ctc", "exp ctc", "expected salary", "exp salary", "target ctc", "target salary", "desired ctc", "desired salary", "expected comp", "expected package", "expected remuneration"]):
        return "EXPECTED_CTC"
    if "expected" in h and any(c in h for c in ["ctc", "salary", "comp", "remuneration", "package", "lpa", "fixed"]):
        return "EXPECTED_CTC"
    if h.startswith("exp ") and any(c in h for c in ["ctc", "salary", "package", "comp"]):
        return "EXPECTED_CTC"

    # 4. Current CTC / Salary
    if any(k in h for k in ["current ctc", "present ctc", "fixed ctc", "current salary", "present salary", "annual salary", "current comp", "present comp"]):
        return "CURRENT_CTC"
    if any(k in h for k in ["ctc", "salary", "compensation", "remuneration", "package"]) and not any(k in h for k in ["expected", "target", "desired"]):
        return "CURRENT_CTC"

    # 5. Experience Category / Level / Bucket
    if any(k in h for k in ["exp level", "experience level", "experience category", "exp category", "experience bucket", "exp bucket"]):
        return "EXP_BUCKET"

    # 6. Skills (Check specific skills keywords before generic domain keywords)
    if any(k in h for k in ["technical skill", "key skill", "skill", "competenc", "tools", "programming language"]):
        return "SKILLS"

    # 7. Technology Domain / Category / Tech Stack
    if any(k in h for k in ["technology domain", "tech domain", "domain", "technology category", "tech category", "tech stack", "technology"]):
        return "TECH_DOMAIN"

    # 8. Relevant Experience (Check before Total Experience!)
    if any(k in h for k in ["relevant experience", "relevant exp", "rel experience", "rel exp", "related experience"]):
        return "RELEVANT_EXPERIENCE"
    if "relevant" in h and any(k in h for k in ["exp", "experience", "work"]):
        return "RELEVANT_EXPERIENCE"

    # 9. Total Experience / Work Experience
    if any(k in h for k in ["total experience", "total exp", "overall experience", "overall exp", "work experience", "total work experience", "years of experience", "years experience", "experience years", "experience duration"]):
        return "TOTAL_EXPERIENCE"
    if h in ["experience", "exp", "total experience (years)", "experience (years)", "exp (years)", "years of exp"]:
        return "TOTAL_EXPERIENCE"
    if "experience" in h and not any(k in h for k in ["relevant", "rel", "level", "category", "bucket"]):
        return "TOTAL_EXPERIENCE"

    # 10. Preferred Location (Check before Current Location!)
    if any(k in h for k in ["preferred location", "pref location", "target location", "preferred city", "desired location", "relocation"]):
        return "PREFERRED_LOCATION"

    # 11. Current Location
    if any(k in h for k in ["current location", "present location", "current city", "location", "city", "address", "based in", "residence"]):
        return "CURRENT_LOCATION"

    # 12. Candidate Name
    if any(k in h for k in ["candidate name", "full name", "applicant name", "person name"]) or h in ["name", "candidate", "applicant"]:
        return "CANDIDATE_NAME"

    # 13. Mobile / Phone
    if any(k in h for k in ["mobile", "phone", "contact number", "contact no", "cell"]) or h in ["contact"]:
        return "MOBILE_NUMBER"

    # 14. Notice Period / Availability
    if any(k in h for k in ["notice", "availability", "joining"]):
        return "NOTICE_PERIOD"

    # 15. Education
    if any(k in h for k in ["education", "qualification", "degree", "academic", "academics"]):
        return "EDUCATION"

    # 16. Certifications
    if any(k in h for k in ["certif", "course", "certified"]):
        return "CERTIFICATIONS"

    # 17. Remarks
    if any(k in h for k in ["remark", "comment", "note"]):
        return "REMARKS"

    return "UNKNOWN"


def validate_candidate_dictionary(candidate_dict: Dict[str, Any], source_text: str) -> Dict[str, Any]:
    """
    FINAL VALIDATION LAYER:
    Evaluates final candidate dictionary against strict cross-field independence rules:
    - Current CTC contains no notice-period values or bare notice numbers.
    - Current CTC contains no Expected CTC values.
    - Expected CTC contains no Current CTC values.
    - Notice Period contains no salary/CTC units.
    - Total Experience contains no CTC, LPA, or phone numbers.
    - Missing fields evaluate strictly to 'Not Specified' or 'Not specified'.
    """
    c_ctc = str(candidate_dict.get("Current CTC", "")).strip()
    e_ctc = str(candidate_dict.get("Expected CTC", "")).strip()
    np_val = str(candidate_dict.get("Notice Period", "")).strip()
    exp_val = str(candidate_dict.get("Total Experience", "")).strip()

    # 1. Sanitize CTC Pair
    san_curr, san_exp = sanitize_ctc_pair(c_ctc, e_ctc, source_text)
    candidate_dict["Current CTC"] = san_curr
    candidate_dict["Expected CTC"] = san_exp

    # 2. Sanitize Notice Period
    if np_val and np_val.lower() not in ["not specified", "none", "null", ""]:
        norm_np = normalize_notice_period(np_val)
        candidate_dict["Notice Period"] = norm_np

    # 3. Sanitize Total Experience against leakage
    if exp_val:
        exp_lower = exp_val.lower()
        if any(k in exp_lower for k in ["lpa", "lakh", "ctc", "salary", "inr", "₹"]):
            norm_e = evaluate_total_experience(source_text)
            candidate_dict["Total Experience"] = norm_e.display_str

    # 4. Standardize empty / missing string representations
    for k in ["Current CTC", "Expected CTC"]:
        v = str(candidate_dict.get(k, "")).strip()
        if not v or v.lower() in ["none", "null", "", "n/a", "na"]:
            candidate_dict[k] = "Not specified"

    for k in ["Notice Period", "Total Experience"]:
        v = str(candidate_dict.get(k, "")).strip()
        if not v or v.lower() in ["none", "null", "", "n/a", "na"]:
            candidate_dict[k] = "Not Specified"

    return candidate_dict


def extract_candidate_data(resume_text: str, excel_headers: List[str] = None) -> Tuple[bool, Dict[str, Any], str, str]:
    """
    Processing Architecture:
    Resume Text -> Text Cleanup & Word Reconstruction -> Local GGUF AI -> Experience Calculation -> Skills Normalization -> Mapping.
    Returns (success, candidate_dict, raw_response, error_message).
    """
    if excel_headers is None:
        excel_headers = ["Candidate Name", "Email ID", "Mobile No", "Total Experience", "Skills", "Education", "Current CTC", "Expected CTC", "Notice Period"]

    if not resume_text or not resume_text.strip():
        return False, {}, "", "Resume text is empty."

    # Step 1: Text Cleanup & Word Reconstruction
    cleaned_text = clean_and_reconstruct_text(resume_text)

    # Step 2: Pre-extract deterministic fallbacks & generic experience evaluation
    fallback_data = extract_all_fields_fallback(cleaned_text)
    norm_exp = evaluate_total_experience(cleaned_text)
    calc_exp, exp_conf, exp_notes = norm_exp.display_str, norm_exp.confidence, norm_exp.notes

    # Build exact JSON template schema for the prompt
    schema = {header: "" for header in excel_headers}
    schema_str = json.dumps(schema, indent=2)

    prompt = f"""You are an expert HR data extraction assistant.
Extract information from the provided candidate resume text to populate an Excel template.

CRITICAL INSTRUCTIONS:
1. Extract candidate information matching EXACTLY these required target keys:
{schema_str}

2. ABSOLUTE ACCURACY RULE: NEVER invent, hallucinate, or guess candidate details.
   - If a requested field is NOT explicitly mentioned or available in the resume, set its value to "".
   - Do NOT guess mobile numbers, email addresses, notice period, CTC, or experience if not present.
   - NEVER infer total experience from phone numbers, CTC, LPA, notice period, graduation years, or software version numbers (e.g. Java 8, HTML5, Python 3.10).

3. STRICT FIELD INDEPENDENCE & CTC/NOTICE RULES:
   - Extract current_ctc, expected_ctc, and notice_period independently.
   - "Current CTC" means ONLY present/current salary.
   - "Expected CTC" means ONLY expected/desired salary.
   - "Notice Period" means ONLY notice period or joining availability.
   - NEVER infer current_ctc from expected_ctc.
   - NEVER infer expected_ctc from current_ctc.
   - NEVER infer current_ctc from notice_period.
   - NEVER infer notice_period from CTC.
   - If Current CTC is explicitly "Not Specified", "N/A", "Not disclosed", "Not mentioned", "Not provided", or missing, set Current CTC to "Not Specified".
   - Expected CTC must NEVER be used as a fallback for Current CTC.
   - Do NOT manufacture missing values. If a field is missing, set its value to "Not Specified".

4. Output format: Respond ONLY with a valid JSON object matching the requested schema keys. Do not include markdown preamble or conversational text.

RESUME TEXT:
-------------------
{cleaned_text}
-------------------
"""

    raw_llm_text = ""
    extracted_dict = {}

    success_llm, raw_llm_text, err_llm = call_hf_llm(prompt, temperature=0.0)

    if success_llm and raw_llm_text:
        extracted_dict = extract_json_from_response(raw_llm_text)
    else:
        print(f"Warning: Hugging Face LLM API call failed ({err_llm}). Using deterministic extraction fallback.")

    # Step 3: Populate final_dict using Header Concept Mapping
    final_dict = {}
    final_dict = {}
    for excel_header in excel_headers:
        concept = classify_header_concept(excel_header)
        found_val = ""

        if extracted_dict:
            for k, v in extracted_dict.items():
                if v and (k.strip().lower() == excel_header.strip().lower() or classify_header_concept(k) == concept):
                    val_str = str(v).strip()
                    if val_str.lower() not in ["none", "null", "n/a", "na"]:
                        if concept in ["CURRENT_CTC", "EXPECTED_CTC"]:
                            val_str = clean_and_validate_ctc(val_str, source_segment=cleaned_text)
                        elif concept == "NOTICE_PERIOD":
                            val_str = normalize_notice_period(val_str)
                        if val_str and val_str.strip().lower() not in ["not specified", "none", "null", ""]:
                            found_val = val_str
                            break

        if not found_val:
            if concept == "CANDIDATE_NAME":
                found_val = fallback_data.get("Candidate Name", "")
            elif concept == "MOBILE_NUMBER":
                found_val = fallback_data.get("Mobile Number", "")
            elif concept == "EMAIL_ADDRESS":
                found_val = fallback_data.get("Email Address", "")
            elif concept == "TOTAL_EXPERIENCE":
                found_val = calc_exp
            elif concept == "RELEVANT_EXPERIENCE":
                found_val = calc_exp
            elif concept == "SKILLS":
                found_val = fallback_data.get("Skills", "")
            elif concept == "NOTICE_PERIOD":
                found_val = fallback_data.get("Notice Period", "")
            elif concept == "PREFERRED_LOCATION":
                found_val = fallback_data.get("Preferred Location", "")
            elif concept == "CURRENT_LOCATION":
                found_val = fallback_data.get("Current Location", "")
            elif concept == "CURRENT_CTC":
                found_val = fallback_data.get("Current CTC", "")
            elif concept == "EXPECTED_CTC":
                found_val = fallback_data.get("Expected CTC", "")
            elif concept == "LINKEDIN":
                found_val = fallback_data.get("LinkedIn Profile", "")
            elif concept == "EDUCATION":
                found_val = fallback_data.get("Education", "")
            elif concept == "CERTIFICATIONS":
                found_val = fallback_data.get("Certifications", "")
            elif concept == "TECH_DOMAIN":
                found_val = ", ".join(classify_technology(cleaned_text))
            elif concept == "EXP_BUCKET":
                found_val = classify_experience(calc_exp, cleaned_text)
            elif concept == "REMARKS":
                found_val = ""

        # 3. Semantic Guardrails & Field-Type Sanitization
        # Rule: EXPECTED CTC & CURRENT CTC must NEVER contain experience values
        if concept in ["EXPECTED_CTC", "CURRENT_CTC"]:
            val_lower = found_val.lower()
            if any(k in val_lower for k in ["fresher", "years", "yrs", "year", "month", "mos", "intern", "entry level"]):
                found_val = ""
            if concept == "EXPECTED_CTC" and found_val:
                # If expected CTC was mistakenly filled with current CTC and no expected keyword in text, clear it
                curr_ctc_val = fallback_data.get("Current CTC", "")
                if found_val == curr_ctc_val and not re.search(r"(?:expected|target|desired)\s*(?:ctc|salary|package)", cleaned_text, re.IGNORECASE):
                    found_val = ""

        # Rule: TOTAL_EXPERIENCE must receive only experience values and prioritize high-confidence deterministic evaluation
        elif concept == "TOTAL_EXPERIENCE":
            val_lower = found_val.lower()
            if any(k in val_lower for k in ["lpa", "lakh", "lac", "ctc", "salary", "inr"]) or not found_val or norm_exp.confidence >= 90.0:
                found_val = calc_exp

        # Rule: RELEVANT_EXPERIENCE must receive only experience values
        elif concept == "RELEVANT_EXPERIENCE":
            val_lower = found_val.lower()
            if any(k in val_lower for k in ["lpa", "lakh", "lac", "ctc", "salary", "inr"]):
                found_val = calc_exp

        final_dict[excel_header] = found_val

    # Step 3.5: Sanitize Notice Period & CTC pair to ensure fields are strictly independent
    np_hdr = None
    curr_ctc_hdr = None
    exp_ctc_hdr = None
    for h in excel_headers:
        c_concept = classify_header_concept(h)
        if c_concept == "NOTICE_PERIOD":
            np_hdr = h
        elif c_concept == "CURRENT_CTC":
            curr_ctc_hdr = h
        elif c_concept == "EXPECTED_CTC":
            exp_ctc_hdr = h

    det_np = extract_notice_period(cleaned_text)
    if np_hdr:
        llm_np = final_dict.get(np_hdr, "")
        if det_np != "Not Specified" or not llm_np or llm_np.lower() in ["not specified", "none", "null", "n/a", ""]:
            final_dict[np_hdr] = det_np

    c_val = final_dict.get(curr_ctc_hdr, "") if curr_ctc_hdr else fallback_data.get("Current CTC", "")
    e_val = final_dict.get(exp_ctc_hdr, "") if exp_ctc_hdr else fallback_data.get("Expected CTC", "")

    san_curr, san_exp = sanitize_ctc_pair(c_val, e_val, cleaned_text)
    if curr_ctc_hdr:
        final_dict[curr_ctc_hdr] = san_curr
    if exp_ctc_hdr:
        final_dict[exp_ctc_hdr] = san_exp

    # Step 4: Normalize extracted skills
    skills_header = None
    for h in excel_headers:
        if classify_header_concept(h) == "SKILLS":
            skills_header = h
            break

    raw_skills = final_dict.get(skills_header, "") if skills_header else fallback_data.get("Skills", "")
    norm_skills_str, skills_conf = normalize_skills(raw_skills)

    if skills_header and norm_skills_str:
        final_dict[skills_header] = norm_skills_str

    # Step 5: High Confidence Experience & Fresher Protection (Never overwrite deterministic result with "Not Specified")
    for header in excel_headers:
        c_concept = classify_header_concept(header)
        if c_concept == "TOTAL_EXPERIENCE":
            if norm_exp.confidence >= 90.0 or not final_dict.get(header) or final_dict.get(header).strip().lower() in ["not specified", "none", "null", ""]:
                final_dict[header] = calc_exp
        elif c_concept == "RELEVANT_EXPERIENCE":
            if norm_exp.confidence >= 90.0 and (not final_dict.get(header) or final_dict.get(header).strip().lower() in ["not specified", "none", "null", ""]):
                final_dict[header] = calc_exp

    # Step 6: Technology & Experience Classifications
    tech_domains = classify_technology(cleaned_text, norm_skills_str)
    tech_domain_str = ", ".join(tech_domains)
    exp_bucket = classify_experience(final_dict.get("Total Experience", calc_exp), cleaned_text)
    screening_res = run_ai_candidate_screening(cleaned_text, final_dict)

    # Populate domain / experience headers
    for header in excel_headers:
        c_concept = classify_header_concept(header)
        if c_concept == "TECH_DOMAIN":
            final_dict[header] = tech_domain_str
        elif c_concept == "EXP_BUCKET" and not final_dict[header]:
            final_dict[header] = exp_bucket

    # Step 7: Final Validation Layer (Cross-Field Independence & Rejection Guardrails)
    c_ctc = final_dict.get("Current CTC", "")
    e_ctc = final_dict.get("Expected CTC", "")
    san_curr, san_exp = sanitize_ctc_pair(c_ctc, e_ctc, cleaned_text)
    final_dict["Current CTC"] = san_curr
    final_dict["Expected CTC"] = san_exp

    if final_dict.get("Notice Period"):
        final_dict["Notice Period"] = normalize_notice_period(final_dict["Notice Period"])

    # Attach Debugging & Confidence Metadata
    final_dict["_raw_text"] = resume_text
    final_dict["_cleaned_text"] = cleaned_text
    final_dict["_exp_confidence"] = norm_exp.confidence
    final_dict["_exp_notes"] = norm_exp.notes
    final_dict["_exp_explicit"] = norm_exp.explicit_val or ""
    final_dict["_exp_calculated"] = norm_exp.calculated_val or ""
    final_dict["_exp_discrepancy"] = norm_exp.discrepancy_flag
    final_dict["_skills_confidence"] = skills_conf
    final_dict["_tech_domains"] = tech_domains
    final_dict["_exp_bucket"] = exp_bucket
    final_dict["_oracle_exp"] = screening_res["_oracle_exp"]
    final_dict["_suitable_roles"] = screening_res["_suitable_roles"]
    final_dict["_ai_screening_summary"] = screening_res["_ai_screening_summary"]

    return True, final_dict, raw_llm_text, ""
