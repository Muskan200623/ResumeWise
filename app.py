import html
import re
from collections import Counter

import streamlit as st
from pypdf import PdfReader

from src.pdf_extractor import extract_text_from_pdf
from src.text_preprocessor import clean_text
from src.skill_extractor import extract_skills, compare_skills
from src.matcher import calculate_similarity

try:
    from spellchecker import SpellChecker
    SPELLCHECKER_AVAILABLE = True
except ImportError:
    SpellChecker = None
    SPELLCHECKER_AVAILABLE = False


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="ResumeWise | Resume Analyzer",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# HELPERS
# =========================================================

TECHNICAL_WORDS = {
    "python", "java", "javascript", "typescript", "html", "css", "sql",
    "react", "reactjs", "node", "nodejs", "express", "pandas", "numpy",
    "scikit", "learn", "tensorflow", "pytorch", "streamlit", "firebase",
    "mongodb", "mysql", "git", "github", "docker", "aws", "api", "apis",
    "ui", "ux", "dbms", "kmeans", "tfidf", "css", "vite", "fastapi",
    "flask", "django", "excel", "powerbi", "machine", "learning",
    "analytics", "analytic", "ananya", "sharma", "gmail", "email",
    "mail", "k-means", "means", "customer", "customers", "dataset",
    "datasets", "dashboard", "dashboards", "insights", "preprocess",
    "preprocessing", "visualization", "visualizations", "linkedin",
    "portfolio", "purnea", "bihar", "rajasthan", "banasthali",
}

SECTION_ALIASES = {
    "Professional Summary": ["summary", "objective", "profile", "about me"],
    "Education": ["education", "academic background", "qualification"],
    "Skills": ["skills", "technical skills", "core competencies"],
    "Projects": ["projects", "academic projects", "personal projects"],
    "Experience": ["experience", "work experience", "internship", "employment"],
    "Certifications": ["certifications", "certificates", "courses"],
    "Achievements": ["achievements", "accomplishments", "awards"],
}

ACTION_VERBS = {
    "developed", "created", "designed", "implemented", "built", "improved",
    "managed", "led", "analyzed", "automated", "optimized", "integrated",
    "tested", "deployed", "configured", "maintained", "collaborated",
    "engineered", "delivered", "organized",
}

COMMON_TYPO_MAP = {
    "experiance": "experience",
    "experince": "experience",
    "develpment": "development",
    "developement": "development",
    "managment": "management",
    "teh": "the",
    "recieve": "receive",
    "seperate": "separate",
    "acheivement": "achievement",
    "acheivements": "achievements",
    "responsibilites": "responsibilities",
    "proffesional": "professional",
    "communicaton": "communication",
    "analaysis": "analysis",
    "langauge": "language",
    "javscript": "javascript",
    "javasript": "javascript",
    "pyhton": "python",
    "machne": "machine",
    "learnng": "learning",
}


def safe_text(value):
    return html.escape(str(value))


def make_badges(items, badge_class):
    if not items:
        return '<span class="empty-state">None detected</span>'

    return "".join(
        f'<span class="skill-badge {badge_class}">{safe_text(item)}</span>'
        for item in items
    )


def normalize_words(text):
    return re.findall(r"[A-Za-z][A-Za-z'-]{2,}", text.lower())


def detect_resume_sections(text):
    lowered = text.lower()
    results = {}

    for section, aliases in SECTION_ALIASES.items():
        results[section] = any(
            re.search(r"\b" + re.escape(alias) + r"\b", lowered)
            for alias in aliases
        )

    return results


def extract_pdf_links(pdf_file):
    """Read clickable URLs embedded in the uploaded PDF."""
    links = []

    if pdf_file is None:
        return links

    try:
        pdf_file.seek(0)
        reader = PdfReader(pdf_file)

        for page in reader.pages:
            annotations = page.get("/Annots") or []

            for annotation in annotations:
                annotation_object = annotation.get_object()
                action = annotation_object.get("/A")

                if action and action.get("/S") == "/URI":
                    uri = action.get("/URI")
                    if uri:
                        links.append(str(uri))
    except Exception:
        # Link extraction is an enhancement. Text analysis should still work
        # if a PDF has unusual annotations.
        return []
    finally:
        try:
            pdf_file.seek(0)
        except Exception:
            pass

    return sorted(set(links))


def detect_contact_information(text, pdf_links=None):
    """Detect contact labels and verify clickable PDF links when available."""
    lowered = text.lower()
    pdf_links = [link.lower() for link in (pdf_links or [])]

    email_found = bool(
        re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    ) or any(link.startswith("mailto:") for link in pdf_links)

    phone_found = bool(
        re.search(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)", text)
    )

    linkedin_found = (
        "linkedin.com" in lowered
        or "linkedin" in lowered
        or any("linkedin.com" in link for link in pdf_links)
    )

    github_found = (
        "github.com" in lowered
        or "github" in lowered
        or any("github.com" in link for link in pdf_links)
    )

    portfolio_found = (
        "portfolio" in lowered
        or any("netlify.app" in link or "vercel.app" in link for link in pdf_links)
    )

    return {
        "Email": email_found,
        "Phone": phone_found,
        "LinkedIn": linkedin_found,
        "GitHub": github_found,
        "Portfolio": portfolio_found,
    }


def calculate_resume_quality(text, sections, contact_info):
    checks = []

    section_score = sum(sections.values()) / len(sections) * 30
    contact_score = sum(contact_info.values()) / len(contact_info) * 20

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    word_count = len(text.split())

    length_score = 10 if 250 <= word_count <= 1200 else 5 if word_count >= 120 else 2

    bullet_lines = sum(
        line.startswith(("-", "•", "*")) or bool(re.match(r"^\d+[.)]", line))
        for line in lines
    )
    bullet_score = 10 if bullet_lines >= 3 else 5 if bullet_lines > 0 else 0

    number_count = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
    quant_score = 10 if number_count >= 5 else 5 if number_count >= 2 else 0

    action_count = sum(
        1 for word in normalize_words(text) if word in ACTION_VERBS
    )
    action_score = 10 if action_count >= 4 else 5 if action_count >= 1 else 0

    total = round(
        min(100, section_score + contact_score + length_score +
            bullet_score + quant_score + action_score)
    )

    checks.extend([
        ("Section completeness", round(section_score / 30 * 100), section_score >= 21),
        ("Contact information", round(contact_score / 20 * 100), contact_score >= 15),
        ("Resume length", round(length_score / 10 * 100), length_score >= 5),
        ("Bullet-point usage", round(bullet_score / 10 * 100), bullet_score >= 5),
        ("Quantified content", round(quant_score / 10 * 100), quant_score >= 5),
        ("Action verbs", round(action_score / 10 * 100), action_score >= 5),
    ])

    return total, checks


def make_text_context(text, start, end, window=48):
    """Return a short context snippet and an approximate line number."""
    line_number = text[:start].count("\n") + 1
    context_start = max(0, start - window)
    context_end = min(len(text), end + window)
    snippet = re.sub(r"\s+", " ", text[context_start:context_end]).strip()
    return snippet, line_number


def is_protected_dictionary_word(text, word, match):
    """Return True when a word should not be flagged as a spelling error.

    This avoids false positives for names, email addresses, URLs, and
    common technical/resume vocabulary.
    """
    normalized = word.lower().strip(".-_")

    protected_words = TECHNICAL_WORDS | {
        "resume", "resumes", "btech", "cgpa", "pvt", "ltd",
        "banasthali", "vidyapith", "purnea", "bihar", "rajasthan",
        "firebase", "wordpress", "concrete", "nasscom", "thingqbator",
        "flipkart", "grid", "produscope", "khadi", "aarohini",
        "appcrave", "technovations", "muskan", "kumari", "ananya",
        "sharma", "gmail", "email", "mail", "analytics", "analytic",
        "kmeans", "k-means", "means", "linkedin", "github", "netlify",
        "javascript", "typescript", "mysql", "oracle", "dbms", "dsa",
        "ai", "ml", "data", "analyst", "analysis", "experience",
    }

    if normalized in protected_words or len(normalized) <= 3:
        return True

    start, end = match.span()
    before = text[max(0, start - 80):start]
    after = text[end:min(len(text), end + 80)]

    # Do not check parts of email addresses, URLs, or handles.
    nearby = before + text[start:end] + after
    if "@" in nearby or "http" in nearby.lower() or "www." in nearby.lower():
        return True

    # Proper names are commonly missing from English dictionaries.
    original = match.group(0)
    if original[:1].isupper() and not original.isupper():
        return True

    # Avoid flagging words that are part of hyphenated technical terms.
    if (start > 0 and text[start - 1] == "-") or (end < len(text) and text[end] == "-"):
        return True

    return False


def spelling_and_writing_review(text):
    """Find possible spelling and writing issues with location/context."""
    findings = []

    def add_finding(issue_type, original, suggestion, severity, start, end):
        context, line_number = make_text_context(text, start, end)
        findings.append({
            "type": issue_type,
            "original": original,
            "suggestion": suggestion,
            "severity": severity,
            "line": line_number,
            "context": context,
        })

    lowered = text.lower()

    # 1. Known typo detection with the exact occurrence and location.
    for wrong, correct in COMMON_TYPO_MAP.items():
        pattern = re.compile(r"\b" + re.escape(wrong) + r"\b", re.IGNORECASE)
        for match in pattern.finditer(text):
            add_finding(
                "Spelling",
                match.group(0),
                correct,
                "High",
                match.start(),
                match.end(),
            )

    # 2. Optional dictionary-based suggestions.
    if SPELLCHECKER_AVAILABLE:
        spell = SpellChecker()
        words = normalize_words(text)
        unknown_words = spell.unknown(words)

        for word in sorted(unknown_words):
            # Always skip protected resume vocabulary before asking the
            # dictionary for a correction. This prevents false positives such
            # as Ananya -> banana and Sharma -> dharma.
            if word in TECHNICAL_WORDS or len(word) <= 3:
                continue

            # Find the original occurrence so that we can inspect capitalization
            # and surrounding email/URL text before showing a suggestion.
            match = re.search(r"\b" + re.escape(word) + r"\b", text, re.IGNORECASE)
            if not match:
                continue

            # Skip names, email addresses, URLs, and known resume terms.
            # This check must happen before spell.correction().
            if is_protected_dictionary_word(text, word, match):
                continue

            suggestion = spell.correction(word)
            if not suggestion or suggestion == word:
                continue

            # pyspellchecker can suggest unrelated words for names and domain
            # terms. Only show suggestions that are reasonably close.
            candidates = spell.candidates(word) or set()
            if suggestion not in candidates:
                continue

            add_finding(
                "Possible spelling",
                match.group(0),
                suggestion,
                "Review",
                match.start(),
                match.end(),
            )

    # 3. Repeated spaces can be a formatting issue. We deliberately do not
    # flag missing spaces after punctuation because PDF extraction frequently
    # joins text fragments and creates false positives.
    repeated_space_match = re.search(r" {2,}", text)
    if repeated_space_match:
        add_finding(
            "Formatting",
            "Repeated spaces",
            "Use single spaces consistently.",
            "Review",
            repeated_space_match.start(),
            repeated_space_match.end(),
        )

    # 4. Repeated words, shown with the word and approximate location.
    word_matches = list(re.finditer(r"[A-Za-z][A-Za-z'-]{2,}", text.lower()))
    word_counts = Counter(match.group(0) for match in word_matches)

    for word, count in sorted(word_counts.items()):
        if count < 8 or len(word) <= 4 or word in TECHNICAL_WORDS:
            continue

        first_match = next(
            match for match in word_matches if match.group(0) == word
        )
        add_finding(
            "Style",
            f"Repeated word: {word}",
            "Check whether the wording can be varied.",
            "Review",
            first_match.start(),
            first_match.end(),
        )

    # Remove duplicates while keeping order.
    unique_findings = []
    seen = set()
    for finding in findings:
        key = (
            finding["type"],
            finding["original"].lower(),
            finding["suggestion"].lower(),
        )
        if key not in seen:
            seen.add(key)
            unique_findings.append(finding)

    return unique_findings[:30]


def build_improvement_suggestions(
    missing_skills,
    sections,
    contact_info,
    quality_checks,
    writing_findings,
):
    suggestions = []

    if missing_skills:
        suggestions.append(
            "Add missing job-relevant skills only if you genuinely have "
            "experience or learning exposure to them."
        )

    if not sections.get("Professional Summary", False):
        suggestions.append(
            "Add a concise 2–3 line professional summary tailored to the target role."
        )

    if not sections.get("Projects", False):
        suggestions.append(
            "Add a projects section with technologies, your contribution, and outcomes."
        )

    if not sections.get("Experience", False):
        suggestions.append(
            "Include internship, work, volunteer, or relevant practical experience "
            "when applicable."
        )

    if not contact_info.get("LinkedIn", False):
        suggestions.append("Consider adding a professional LinkedIn profile link.")

    if not contact_info.get("GitHub", False):
        suggestions.append("Add GitHub if you have relevant public coding projects.")

    for name, percentage, passed in quality_checks:
        if not passed:
            if name == "Quantified content":
                suggestions.append(
                    "Add truthful measurable details such as project scale, "
                    "features, performance, users, or time saved."
                )
            elif name == "Action verbs":
                suggestions.append(
                    "Begin experience and project bullets with strong action verbs "
                    "such as developed, implemented, analyzed, or designed."
                )
            elif name == "Bullet-point usage":
                suggestions.append(
                    "Use concise bullet points instead of long paragraphs."
                )
            elif name == "Resume length":
                suggestions.append(
                    "Review the resume length and remove unnecessary or repetitive content."
                )

    if writing_findings:
        suggestions.append(
            "Review the spelling and writing findings before submitting the resume."
        )

    if not suggestions:
        suggestions.append(
            "The basic checks passed. Tailor your summary and project bullets "
            "to the exact job description for better relevance."
        )

    return list(dict.fromkeys(suggestions))


# =========================================================
# CUSTOM CSS
# =========================================================

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #f7f5ff 0%, #f5f9ff 48%, #f1fbfa 100%);
        color: #172033;
    }

    .main .block-container {
        max-width: 1250px;
        padding-top: 2rem;
        padding-bottom: 3rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }

    #MainMenu, footer { visibility: hidden; }

    .main-title {
        font-size: 2.45rem;
        font-weight: 850;
        color: #24234a;
        letter-spacing: -1px;
        margin-bottom: .15rem;
    }

    .main-subtitle {
        color: #68728a;
        font-size: .95rem;
        margin-bottom: 1.6rem;
    }

    .section-heading {
        font-size: 1.3rem;
        font-weight: 800;
        color: #24234a;
        margin-top: .8rem;
        margin-bottom: .25rem;
    }

    .section-text {
        color: #707b91;
        font-size: .86rem;
        margin-bottom: .8rem;
    }

    .input-label {
        font-size: .95rem;
        font-weight: 750;
        color: #25253f;
        margin-bottom: .35rem;
    }

    [data-testid="stFileUploader"] {
        background: white;
        border: 2px solid #ddd9ff;
        border-radius: 16px;
        padding: .7rem;
        box-shadow: 0 5px 18px rgba(78,70,160,.07);
    }

    [data-testid="stFileUploaderDropzone"] {
        background: linear-gradient(135deg,#faf9ff,#f4f7ff);
        border: 2px dashed #aaa4ee;
        border-radius: 12px;
    }

    [data-testid="stTextArea"] textarea {
        background: white;
        border: 2px solid #cfe1ff;
        border-radius: 14px;
        color: #20243a;
        font-size: .9rem;
        padding: .85rem;
    }

    div.stButton > button {
        width: 100%;
        min-height: 3rem;
        border-radius: 12px;
        border: none;
        color: white;
        font-size: .95rem;
        font-weight: 750;
        background: linear-gradient(90deg,#665ee8,#477df5,#25a8a0);
        box-shadow: 0 7px 18px rgba(85,91,220,.22);
        transition: transform .2s ease, box-shadow .2s ease;
    }

    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 24px rgba(85,91,220,.3);
    }

    .result-header {
        margin-top: 2rem;
        padding-top: 1.3rem;
        border-top: 1px solid #dddff0;
    }

    .result-title {
        font-size: 1.65rem;
        font-weight: 850;
        color: #25234d;
        margin-bottom: .2rem;
    }

    .result-subtitle {
        font-size: .84rem;
        color: #707b91;
        margin-bottom: 1rem;
    }

    [data-testid="stMetric"] {
        background: white;
        border-radius: 15px;
        padding: 1rem 1.15rem;
        border: 1px solid #e4e4f3;
        box-shadow: 0 6px 20px rgba(45,48,100,.06);
    }

    [data-testid="stMetricLabel"] {
        color: #70788e !important;
        font-size: .78rem !important;
        font-weight: 650 !important;
    }

    [data-testid="stMetricValue"] {
        color: #5b54d8 !important;
        font-size: 2rem !important;
        font-weight: 850 !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: white;
        border-radius: 15px;
        border: 1px solid #e2e4ef;
        box-shadow: 0 6px 20px rgba(45,48,100,.055);
        padding: .4rem;
    }

    .skill-heading {
        font-size: 1rem;
        font-weight: 800;
        color: #25253f;
        margin-bottom: .2rem;
    }

    .skill-description {
        font-size: .78rem;
        color: #7a8397;
        margin-bottom: .7rem;
    }

    .skill-badge {
        display: inline-block;
        padding: 6px 11px;
        margin: 3px 5px 3px 0;
        border-radius: 20px;
        font-size: .75rem;
        font-weight: 650;
    }

    .matched-badge {
        background: #e6f8f1;
        color: #19865e;
        border: 1px solid #bfead7;
    }

    .missing-badge {
        background: #fff0ec;
        color: #d35b45;
        border: 1px solid #f2cfc6;
    }

    .resume-badge {
        background: #eef0ff;
        color: #5a55d6;
        border: 1px solid #d4d7ff;
    }

    .empty-state {
        color: #8b94a8;
        font-size: .8rem;
    }

    .method-box {
        background: linear-gradient(135deg,#f2efff,#edf7ff);
        border: 1px solid #d8d8fa;
        border-left: 5px solid #665ee8;
        border-radius: 12px;
        padding: .9rem 1rem;
        color: #58627a;
        font-size: .82rem;
        margin-top: 1rem;
    }

    .quality-pass {
        color: #19865e;
        font-weight: 700;
    }

    .quality-review {
        color: #d35b45;
        font-weight: 700;
    }

    .link-text {
        color: #4f5bd5;
        font-size: .82rem;
        overflow-wrap: anywhere;
    }

    .issue-card {
        background: #fffaf5;
        border: 1px solid #f3d9b9;
        border-left: 4px solid #ef9d43;
        border-radius: 10px;
        padding: .8rem 1rem;
        margin-bottom: .55rem;
    }

    .suggestion-card {
        background: #f4f7ff;
        border: 1px solid #d8e0ff;
        border-left: 4px solid #6685f5;
        border-radius: 10px;
        padding: .75rem 1rem;
        margin-bottom: .55rem;
        color: #45516c;
        font-size: .86rem;
    }

    .custom-footer {
        text-align: center;
        margin-top: 2.5rem;
        padding-top: 1rem;
        border-top: 1px solid #dddfea;
        color: #8b94a8;
        font-size: .74rem;
    }

    [data-testid="stExpander"] {
        background: white;
        border: 1px solid #e0e3ee;
        border-radius: 11px;
        margin-top: .5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HEADER
# =========================================================

st.markdown('<div class="main-title">ResumeWise</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="main-subtitle">'
    'Analyze job relevance, resume quality, and writing improvements in one place.'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown('<div class="section-heading">Candidate Information</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-text">'
    'Upload a text-based PDF resume and paste the target job description.'
    '</div>',
    unsafe_allow_html=True,
)

left_column, right_column = st.columns([1, 1], gap="large")

with left_column:
    st.markdown('<div class="input-label">Candidate Resume</div>', unsafe_allow_html=True)
    uploaded_resume = st.file_uploader(
        "Upload PDF resume",
        type=["pdf"],
        label_visibility="collapsed",
    )

    if uploaded_resume:
        st.success(f"{uploaded_resume.name} uploaded successfully.")

with right_column:
    st.markdown('<div class="input-label">Job Description</div>', unsafe_allow_html=True)
    job_description = st.text_area(
        "Paste job description",
        height=205,
        placeholder=(
            "Example:\n\n"
            "We are looking for a Python Developer with experience "
            "in Python, SQL, Pandas, Machine Learning and Git."
        ),
        label_visibility="collapsed",
    )

st.write("")
analyze_button = st.button("Analyze Resume", type="primary")


# =========================================================
# ANALYSIS
# =========================================================

if analyze_button:
    if uploaded_resume is None:
        st.error("Please upload a PDF resume before analyzing.")
        st.stop()

    if not job_description.strip():
        st.error("Please enter a job description before analyzing.")
        st.stop()

    with st.spinner("Analyzing resume quality, skills, and writing..."):
        try:
            resume_text = extract_text_from_pdf(uploaded_resume)

            if not resume_text.strip():
                st.error(
                    "No readable text was found in this PDF. "
                    "Please upload a text-based resume."
                )
                st.stop()

            cleaned_resume = clean_text(resume_text)
            cleaned_job_description = clean_text(job_description)

            resume_skills = extract_skills(cleaned_resume)
            job_skills = extract_skills(cleaned_job_description)

            matched_skills, missing_skills = compare_skills(
                resume_skills,
                job_skills,
            )

            similarity_score = calculate_similarity(
                cleaned_resume,
                cleaned_job_description,
            )

            skill_score = (
                len(matched_skills) / len(job_skills) * 100
                if job_skills
                else 0
            )

            pdf_links = extract_pdf_links(uploaded_resume)
            sections = detect_resume_sections(resume_text)
            contact_info = detect_contact_information(resume_text, pdf_links)

            quality_score, quality_checks = calculate_resume_quality(
                resume_text,
                sections,
                contact_info,
            )

            writing_findings = spelling_and_writing_review(resume_text)

            suggestions = build_improvement_suggestions(
                missing_skills,
                sections,
                contact_info,
                quality_checks,
                writing_findings,
            )

        except Exception as error:
            st.error(f"Something went wrong while analyzing the resume: {error}")
            st.stop()

    # =====================================================
    # SCREENING RESULT
    # =====================================================

    st.markdown(
        '<div class="result-header">'
        '<div class="result-title">Screening Dashboard</div>'
        '<div class="result-subtitle">'
        'A combined view of job relevance, resume quality, and improvement areas.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    score_column, quality_column, skill_column, issue_column = st.columns(
        [1, 1, 1, 1],
        gap="medium",
    )

    with score_column:
        with st.container(border=True):
            st.metric("Text Similarity", f"{similarity_score:.1f}%")
            st.progress(min(max(similarity_score / 100, 0.0), 1.0))
            st.caption("TF-IDF + cosine similarity")

    with quality_column:
        with st.container(border=True):
            st.metric("Resume Health", f"{quality_score}/100")
            st.progress(min(max(quality_score / 100, 0.0), 1.0))
            st.caption("Project-defined quality checks")

    with skill_column:
        with st.container(border=True):
            st.metric("Skill Coverage", f"{skill_score:.1f}%")
            st.progress(min(max(skill_score / 100, 0.0), 1.0))
            st.caption("Matched job skills / detected job skills")

    with issue_column:
        with st.container(border=True):
            st.metric("Writing Findings", len(writing_findings))
            st.caption("Possible spelling, grammar, and style issues")

    st.markdown('<div class="section-heading">Skill Match Overview</div>', unsafe_allow_html=True)

    matched_column, missing_column = st.columns([1, 1], gap="medium")

    with matched_column:
        with st.container(border=True):
            st.markdown('<div class="skill-heading">Matched Skills</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="skill-description">'
                'Skills detected in both the resume and job description.'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown(make_badges(matched_skills, "matched-badge"), unsafe_allow_html=True)

    with missing_column:
        with st.container(border=True):
            st.markdown('<div class="skill-heading">Missing Skills</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="skill-description">'
                'Skills required by the job but not detected in the resume.'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown(make_badges(missing_skills, "missing-badge"), unsafe_allow_html=True)

    # =====================================================
    # TABBED REVIEW
    # =====================================================

    st.markdown('<div class="section-heading">Resume Review</div>', unsafe_allow_html=True)

    tab_quality, tab_writing, tab_suggestions, tab_skills = st.tabs(
        ["Resume Quality", "Spelling & Writing", "Suggestions", "Detected Skills"]
    )

    with tab_quality:
        quality_left, quality_right = st.columns([1, 1], gap="large")

        with quality_left:
            st.markdown("#### Resume Sections")
            for section, found in sections.items():
                status = "Found" if found else "Not detected"
                icon = "✅" if found else "⚠️"
                st.write(f"{icon} **{section}:** {status}")

            st.markdown("#### Contact Information")
            for field, found in contact_info.items():
                status = "Found" if found else "Not detected"
                icon = "✅" if found else "⚠️"
                st.write(f"{icon} **{field}:** {status}")

            st.markdown("#### Clickable Links Found in PDF")
            if pdf_links:
                for link in pdf_links:
                    safe_link = safe_text(link)
                    st.markdown(f"- <span class=\"link-text\">{safe_link}</span>", unsafe_allow_html=True)
            else:
                st.caption("No clickable PDF URLs were detected.")

        with quality_right:
            st.markdown("#### Quality Checklist")
            for name, percentage, passed in quality_checks:
                status_text = "Pass" if passed else "Review"
                status_class = "quality-pass" if passed else "quality-review"
                st.markdown(
                    f"**{safe_text(name)}** — "
                    f'<span class="{status_class}">{status_text}</span>',
                    unsafe_allow_html=True,
                )
                st.progress(min(max(percentage / 100, 0.0), 1.0))

    with tab_writing:
        if not writing_findings:
            st.success(
                "No issues were detected by the current basic spelling and writing checks. "
                "Manual proofreading is still recommended."
            )
        else:
            st.warning(
                "These are possible findings, not guaranteed errors. "
                "Review each suggestion before changing your resume."
            )

            for finding in writing_findings:
                st.markdown(
                    '<div class="issue-card">'
                    f'<strong>{safe_text(finding["type"])}</strong><br>'
                    f'<b>Found:</b> {safe_text(finding["original"])}<br>'
                    f'<b>Suggestion:</b> {safe_text(finding["suggestion"])}<br>'
                    f'<b>Approx. line:</b> {safe_text(finding.get("line", "Not available"))}<br>'
                    f'<b>Context:</b> {safe_text(finding.get("context", "Not available"))}<br>'
                    f'<b>Priority:</b> {safe_text(finding["severity"])}'
                    '</div>',
                    unsafe_allow_html=True,
                )

        if not SPELLCHECKER_AVAILABLE:
            st.info(
                "Dictionary-based spelling checks are optional. Known technical terms, names, "
                "emails, URLs, and hyphenated terms are ignored to reduce false positives."
            )

    with tab_suggestions:
        st.markdown("#### Recommended Improvements")
        for suggestion in suggestions:
            st.markdown(
                f'<div class="suggestion-card">💡 {safe_text(suggestion)}</div>',
                unsafe_allow_html=True,
            )

        if missing_skills:
            st.markdown("#### Priority Skills to Review")
            for skill in missing_skills:
                st.write(f"• **{skill}** — add it only if you have genuine knowledge or experience.")

        st.info(
            "The suggestions are guidance generated from simple rules and detected keywords. "
            "They should not invent skills, experience, or achievements."
        )

    with tab_skills:
        st.markdown("#### Skills Detected in Resume")
        st.markdown(make_badges(resume_skills, "resume-badge"), unsafe_allow_html=True)

        if not resume_skills:
            st.info("No predefined skills were detected in the resume.")

    # =====================================================
    # METHOD NOTE AND OPTIONAL DETAILS
    # =====================================================

    st.markdown(
        '<div class="method-box">'
        '<strong>How this analysis works:</strong> '
        'Text similarity is calculated using TF-IDF and cosine similarity. '
        'Skills are matched using the project skill dictionary. '
        'Resume Health is a project-defined checklist, while spelling and grammar '
        'findings are basic suggestions and should be manually verified.'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.expander("View extracted resume text"):
        st.text(resume_text)

    with st.expander("View detected job requirements"):
        if job_skills:
            st.write(", ".join(job_skills))
        else:
            st.write("No predefined skills were detected.")

# =========================================================
# FOOTER
# =========================================================

st.markdown(
    '<div class="custom-footer">'
    'ResumeWise · TF-IDF · Skill Matching · Resume Quality Review'
    '</div>',
    unsafe_allow_html=True,
)
