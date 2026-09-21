
import re


SKILLS = [
    "python",
    "java",
    "c++",
    "c",
    "sql",
    "html",
    "css",
    "javascript",
    "react",
    "react.js",
    "node.js",
    "node",
    "express",
    "pandas",
    "numpy",
    "scikit-learn",
    "machine learning",
    "deep learning",
    "tensorflow",
    "pytorch",
    "git",
    "github",
    "docker",
    "aws",
    "mongodb",
    "mysql",
    "firebase",
    "flask",
    "django",
    "streamlit",
    "excel",
    "power bi",
    "data analysis",
    "data science"
]


def extract_skills(text):
    """
    Extract known skills from text.

    Uses regular expressions to match complete skill names
    instead of matching skills inside unrelated words.
    """

    text = text.lower()

    found_skills = []

    # Check longer skills first, such as c++ before c.
    sorted_skills = sorted(SKILLS, key=len, reverse=True)

    for skill in sorted_skills:

        skill_lower = skill.lower()

        # Special handling for the single-letter C language.
        # Prevents matching the 'c' in words such as computer
        # and prevents matching 'c' separately in 'c++'.
        if skill_lower == "c":
            pattern = r"(?<![a-zA-Z0-9+#.])c(?![a-zA-Z0-9+#.]|[\+#])"

        else:
            # Match the complete skill name.
            # This prevents partial matches inside other words.
            pattern = (
                r"(?<![a-zA-Z0-9+#.])"
                + re.escape(skill_lower)
                + r"(?![a-zA-Z0-9+#.])"
            )

        if re.search(pattern, text):
            found_skills.append(skill)

    return sorted(set(found_skills))


def compare_skills(resume_skills, job_skills):
    """
    Compare resume skills with job description skills.

    Returns:
        matched: Skills found in both the resume and job description.
        missing: Skills required by the job but absent from the resume.
    """

    resume_skills = set(resume_skills)
    job_skills = set(job_skills)

    matched = sorted(resume_skills.intersection(job_skills))

    missing = sorted(job_skills - resume_skills)

    return matched, missing