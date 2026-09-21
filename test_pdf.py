from src.pdf_extractor import extract_text_from_pdf


with open("sample_resume.pdf", "rb") as file:
    text = extract_text_from_pdf(file)

print(text)