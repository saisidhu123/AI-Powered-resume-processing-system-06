import re
import json
from typing import Dict, Any, List

def extract_json_from_response(text_response: str) -> Dict[str, Any]:
    """
    Extract JSON object from LLM response.
    Handles plain JSON, markdown, and extra text.
    """

    if not text_response or not text_response.strip():
        print("[ERROR] LLM response is EMPTY")
        return {}

    cleaned = text_response.strip()

    try:
        print("\n========== RESPONSE BEFORE JSON PARSING ==========")
        print(repr(cleaned).encode("ascii", errors="replace").decode("ascii"))
        print("===================================================")
    except Exception:
        pass

    # Remove ```json and ``` if present
    cleaned = re.sub(r"```json\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*", "", cleaned)

    # Find JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1:
        print("[ERROR] No { found in LLM response")
        return {}

    if end == -1 or end <= start:
        print("[ERROR] No valid closing } found in LLM response")
        return {}

    json_text = cleaned[start:end + 1].strip()

    try:
        print("\n========== JSON SENT TO json.loads ==========")
        print(json_text.encode("ascii", errors="replace").decode("ascii"))
        print("==============================================")
    except Exception:
        pass

    try:
        data = json.loads(json_text)

        if isinstance(data, dict):
            print("\n[OK] JSON PARSED SUCCESSFULLY")
            try:
                print(str(data).encode("ascii", errors="replace").decode("ascii"))
            except Exception:
                pass
            return data

        print("[ERROR] Parsed JSON is not a dictionary")
        return {}

    except json.JSONDecodeError as e:
        print("\n[ERROR] JSON PARSING FAILED")
        print("Error:", e)
        print("Position:", e.pos)
        print("JSON text:", json_text)
        return {}


SUPPORTED_DOMAINS = [
    "Java",
    "Python",
    "Oracle",
    "Data Engineering",
    "AI/ML",
    "DevOps",
    "Salesforce",
    "SAP",
    "Testing",
    "Full Stack",
    "Cloud",
    "Others"
]


def classify_technology(resume_text: str, skills_str: str = "") -> List[str]:
    """
    Classify candidate skills and text into supported technology domains:
    Java, Python, Oracle, Data Engineering, AI/ML, DevOps, Salesforce, SAP, Testing, Full Stack, Cloud, Others

    Rules:
    - Uses both extracted resume text and extracted skills.
    - Zero additional LLM latency (deterministic regex).
    - Prevents false positives (e.g. JavaScript does NOT classify as Java).
    - Supports multiple technology classifications.
    - Returns ['Others'] if no supported domain is confidently matched.
    """
    raw_combined = f"{resume_text or ''} {skills_str or ''}".lower()
    # Normalize extra whitespace and hyphens
    combined = re.sub(r"\s+", " ", raw_combined)
    domains = []

    # 1. Java Domain (Strict: must not trigger on JavaScript / JS)
    text_without_javascript = re.sub(r"\bjava\s*script\b|\bjavascript\b|\bjs\b", " ", combined)
    java_patterns = [
        r"\bjava\b",
        r"\bspring\b",
        r"\bspring\s*boot\b",
        r"\bspringboot\b",
        r"\bhibernate\b",
        r"\bj2ee\b",
        r"\bjee\b"
    ]
    if any(re.search(pat, text_without_javascript) for pat in java_patterns):
        domains.append("Java")

    # 2. Python Domain
    python_patterns = [
        r"\bpython\b",
        r"\bdjango\b",
        r"\bflask\b",
        r"\bfastapi\b",
        r"\bpandas\b",
        r"\bnumpy\b"
    ]
    if any(re.search(pat, combined) for pat in python_patterns):
        domains.append("Python")

    # 3. Oracle Domain
    oracle_patterns = [
        r"\boracle\b",
        r"\bpl\s*/?\s*sql\b",
        r"\bplsql\b",
        r"\boracle\s*(?:db|database)\b",
        r"\bsql\s*\*?\s*plus\b"
    ]
    if any(re.search(pat, combined) for pat in oracle_patterns):
        domains.append("Oracle")

    # 4. Data Engineering Domain
    data_eng_patterns = [
        r"\bdata\s+engineering\b",
        r"\bdata\s+engineer\b",
        r"\bspark\b",
        r"\bpyspark\b",
        r"\bhadoop\b",
        r"\bkafka\b",
        r"\bairflow\b",
        r"\betl\b",
        r"\bdatabricks\b",
        r"\bhive\b",
        r"\bsnowflake\b"
    ]
    if any(re.search(pat, combined) for pat in data_eng_patterns):
        domains.append("Data Engineering")

    # 5. AI/ML Domain
    ai_ml_patterns = [
        r"\bartificial\s+intelligence\b",
        r"\bai\b",
        r"\bml\b",
        r"\bmachine\s+learning\b",
        r"\bdeep\s+learning\b",
        r"\bllm\b",
        r"\bllms\b",
        r"\bnlp\b",
        r"\bpytorch\b",
        r"\btensorflow\b",
        r"\bscikit(?:-learn)?\b",
        r"\bgenerative\s+ai\b",
        r"\bgenai\b",
        r"\blangchain\b",
        r"\brag\b",
        r"\bcomputer\s+vision\b",
        r"\bneural\s+networks?\b"
    ]
    if any(re.search(pat, combined) for pat in ai_ml_patterns):
        domains.append("AI/ML")

    # 6. DevOps Domain
    devops_patterns = [
        r"\bdevops\b",
        r"\bdocker\b",
        r"\bkubernetes\b",
        r"\bk8s\b",
        r"\bjenkins\b",
        r"\bterraform\b",
        r"\bansible\b",
        r"\bci\s*/\s*cd\b",
        r"\bgitlab\s*ci\b",
        r"\bhelm\b"
    ]
    if any(re.search(pat, combined) for pat in devops_patterns):
        domains.append("DevOps")

    # 7. Salesforce Domain
    salesforce_patterns = [
        r"\bsalesforce\b",
        r"\bapex\b",
        r"\blwc\b",
        r"\bsoql\b",
        r"\bvisualforce\b",
        r"\bsfdc\b"
    ]
    if any(re.search(pat, combined) for pat in salesforce_patterns):
        domains.append("Salesforce")

    # 8. SAP Domain
    sap_patterns = [
        r"\bsap\b",
        r"\babap\b",
        r"\bhana\b",
        r"\bfiori\b",
        r"\bsap\s+erp\b"
    ]
    if any(re.search(pat, combined) for pat in sap_patterns):
        domains.append("SAP")

    # 9. Testing Domain
    testing_patterns = [
        r"\btesting\b",
        r"\bqa\b",
        r"\bselenium\b",
        r"\bcypress\b",
        r"\bjunit\b",
        r"\btestng\b",
        r"\bautomation\s+testing\b",
        r"\bmanual\s+testing\b",
        r"\btest\s+automation\b",
        r"\bquality\s+assurance\b",
        r"\bplaywright\b"
    ]
    if any(re.search(pat, combined) for pat in testing_patterns):
        domains.append("Testing")

    # 10. Full Stack Domain
    fullstack_patterns = [
        r"\bfull\s*stack\b",
        r"\bfullstack\b",
        r"\bmern\b",
        r"\bmean\b",
        r"\breact\b.*?\bnode\b",
        r"\bnode\b.*?\breact\b",
        r"\bangular\b.*?\bjava\b",
        r"\bjava\b.*?\bangular\b",
        r"\bvue\b.*?\bnode\b"
    ]
    if any(re.search(pat, combined) for pat in fullstack_patterns):
        domains.append("Full Stack")

    # 11. Cloud Domain
    cloud_patterns = [
        r"\baws\b",
        r"\bazure\b",
        r"\bgcp\b",
        r"\bgoogle\s+cloud\b",
        r"\bamazon\s+web\s+services\b",
        r"\bcloud\b",
        r"\bcloud\s+computing\b"
    ]
    if any(re.search(pat, combined) for pat in cloud_patterns):
        domains.append("Cloud")

    # 12. Fallback to Others
    if not domains:
        domains.append("Others")

    return domains


def classify_experience(exp_input: Any, resume_text: str = "") -> str:
    """
    Classify candidate total experience into buckets:
    Fresher, 1–3 Years, 3–5 Years, 5–8 Years, 8+ Years
    """
    exp_str = str(exp_input or "").lower().strip()
    resume_lower = resume_text.lower()

    if exp_str == "fresher":
        return "Fresher"

    # Search for numbers in input
    digits = re.findall(r"\d+(?:\.\d+)?", exp_str)
    years = None
    if digits:
        try:
            years = float(digits[0])
            # If input mentions months e.g. "6 months", "11 months"
            if "month" in exp_str or "mo" in exp_str:
                years = round(years / 12.0, 1)
        except ValueError:
            years = None

    if years is None:
        # Check explicit fresher keyword
        if any(k in exp_str for k in ["fresher", "fresh graduate", "no work experience"]):
            return "Fresher"
        if any(k in resume_lower for k in ["fresher", "fresh graduate", "no work experience"]):
            return "Fresher"
        return "Fresher"

    if years == 0:
        return "Fresher"
    elif years < 3:
        return "1–3 Years"
    elif 3 <= years < 5:
        return "3–5 Years"
    elif 5 <= years <= 8:
        return "5–8 Years"
    else:
        return "8+ Years"


def clean_phone_number(phone_str: str) -> str:
    """
    Extract normalized digits for phone comparison.
    """
    if not phone_str:
        return ""
    digits = re.sub(r"\D", "", str(phone_str))
    # If starts with country code like 91, keep last 10 digits for local comparison
    if len(digits) > 10:
        return digits[-10:]
    return digits


def clean_email(email_str: str) -> str:
    """
    Normalize email address for duplicate checking.
    """
    if not email_str:
        return ""
    return str(email_str).strip().lower()


def clean_name(name_str: str) -> str:
    """
    Normalize candidate name for matching.
    """
    if not name_str:
        return ""
    cleaned = re.sub(r"[^a-zA-Z\s]", "", str(name_str)).strip().lower()
    return " ".join(cleaned.split())


def format_skills(sk: Any, max_items: int = 0) -> str:
    """
    Safely format skills into a clean, comma-separated string.
    Prevents string slicing bugs (e.g. slicing 'Python' as ['P', 'y', 't', 'h', 'o']).
    """
    if not sk:
        return "N/A"

    if isinstance(sk, str):
        if sk.strip().startswith("[") and sk.strip().endswith("]"):
            try:
                parsed = json.loads(sk)
                if isinstance(parsed, list):
                    sk = parsed
            except Exception:
                pass

    if isinstance(sk, list):
        clean_list = [str(x).strip() for x in sk if str(x).strip()]
        if max_items > 0 and len(clean_list) > max_items:
            clean_list = clean_list[:max_items]
        return ", ".join(clean_list) if clean_list else "N/A"

    if isinstance(sk, str):
        parts = [p.strip() for p in sk.split(",") if p.strip()]
        if max_items > 0 and len(parts) > max_items:
            parts = parts[:max_items]
        return ", ".join(parts) if parts else "N/A"

    return str(sk)

