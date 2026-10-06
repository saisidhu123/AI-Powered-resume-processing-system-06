import os
import openpyxl
import fitz # PyMuPDF
from services.resume_parser import parse_resume
from services.excel_service import read_excel_headers, populate_excel_template, read_existing_candidate_rows
from services.llm_service import extract_candidate_data, check_llm_status
from services.duplicate_detector import check_duplicate

def run_test():
    print("--- 1. Testing Hugging Face LLM Status ---")
    online, msg, models = check_llm_status()
    print(f"Hugging Face LLM Online: {online}, Message: {msg}")

    # Create dummy PDF resume
    sample_pdf_path = "uploads/test_resume.pdf"
    doc = fitz.open()
    page = doc.new_page()
    sample_text = """
    JOHN DOE
    Email: john.doe@example.com
    Mobile: +91 9876543210
    LinkedIn: linkedin.com/in/johndoe
    Location: Bangalore, India

    SUMMARY:
    Senior Python & AI Engineer with 6.5 years of total experience building web applications and ML models.

    TECHNICAL SKILLS:
    Python, Django, FastAPI, PyTorch, Docker, Kubernetes, AWS, SQL

    WORK EXPERIENCE:
    Lead AI Engineer - Acme Corp (2021 - Present)
    - Developed LLM pipelines and automated document processing systems.

    NOTICE PERIOD: 30 Days
    CURRENT CTC: 18 LPA
    EXPECTED CTC: 24 LPA
    """
    page.insert_text((50, 50), sample_text)
    doc.save(sample_pdf_path)
    doc.close()
    print(f"Sample PDF created at {sample_pdf_path}")

    # Create dummy Excel Template
    sample_template_path = "uploads/test_template.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = [
        "Candidate Name", "Mobile Number", "Email Address", "Total Experience",
        "Preferred Location", "Skills", "Notice Period", "Current CTC",
        "Expected CTC", "LinkedIn Profile", "Remarks"
    ]
    ws.append(headers)
    wb.save(sample_template_path)
    wb.close()
    print(f"Sample Excel template created at {sample_template_path}")

    # Test Step 1: Parsing Resume
    print("--- 2. Parsing Resume ---")
    ok, resume_text, parse_err = parse_resume(sample_pdf_path)
    assert ok, f"Resume parsing failed: {parse_err}"
    print(f"Extracted resume text length: {len(resume_text)} characters")

    # Test Step 2: Read Excel Headers
    print("--- 3. Reading Excel Headers ---")
    ok, read_hdrs, hdr_err = read_excel_headers(sample_template_path)
    assert ok, f"Reading headers failed: {hdr_err}"
    print(f"Detected Headers: {read_hdrs}")

    # Test Step 3: LLM Extraction
    print("--- 4. Extracting Data via Hugging Face LLM ---")
    llm_ok, cand_data, raw_llm, llm_err = extract_candidate_data(resume_text, read_hdrs)
    assert cand_data and len(cand_data) > 0, f"Extraction failed: {llm_err}"

    print("\n--- Extracted Results ---")
    for k in read_hdrs:
        print(f"  {k}: {cand_data.get(k)}")

    print(f"  Tech Domains: {cand_data.get('_tech_domains')}")
    print(f"  Experience Bucket: {cand_data.get('_exp_bucket')}")

    # Explicit field extractions assertion checks
    assert cand_data.get("Candidate Name") != "", "Candidate Name must NOT be blank!"
    assert cand_data.get("Mobile Number") != "", "Mobile Number must NOT be blank!"
    assert cand_data.get("Skills") != "", "Skills must NOT be blank!"
    assert cand_data.get("Notice Period") != "", "Notice Period must NOT be blank!"
    assert cand_data.get("Total Experience") != "", "Total Experience must NOT be blank!"

    print("\n[OK] Field Extractions Assertion Passed: NAME, MOBILE, SKILLS, NOTICE PERIOD, EXPERIENCE are all non-blank!")

    # Test Step 4: Duplicate Detection
    print("\n--- 5. Duplicate Detection Test ---")
    is_dup, warning, details = check_duplicate(cand_data, [cand_data])
    print(f"Duplicate detected on self-match: {is_dup}")
    if is_dup:
        print(details)

    # Test Step 5: Populate Excel
    print("\n--- 6. Populating Excel Output ---")
    out_xlsx = "outputs/test_output.xlsx"
    pop_ok, pop_err = populate_excel_template(sample_template_path, cand_data, out_xlsx)
    assert pop_ok, f"Populate Excel failed: {pop_err}"
    print(f"Populated output saved to {out_xlsx}")

    # Verify Excel read-back
    wb_out = openpyxl.load_workbook(out_xlsx)
    ws_out = wb_out.active
    row2_vals = [cell.value for cell in ws_out[2]]
    print("\n--- Excel Row 2 Values ---")
    for h, val in zip(read_hdrs, row2_vals):
        print(f"  {h}: {val}")
    wb_out.close()

    assert row2_vals[0] != None and row2_vals[0] != "", "Excel Candidate Name must NOT be empty!"
    assert row2_vals[1] != None and row2_vals[1] != "", "Excel Mobile Number must NOT be empty!"
    assert row2_vals[3] != None and row2_vals[3] != "", "Excel Total Experience must NOT be empty!"
    assert row2_vals[5] != None and row2_vals[5] != "", "Excel Skills must NOT be empty!"
    assert row2_vals[6] != None and row2_vals[6] != "", "Excel Notice Period must NOT be empty!"

    print("\n[OK] ALL END-TO-END INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_test()
