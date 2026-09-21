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
    """

    text = text.lower()

    found_skills = []

    for skill in SKILLS:

        if skill.lower() in text:
            found_skills.append(skill)

    return sorted(set(found_skills))


def compare_skills(resume_skills, job_skills):
    """
    Compare resume skills with job description skills.
    """

    resume_skills = set(resume_skills)
    job_skills = set(job_skills)

    matched = sorted(resume_skills.intersection(job_skills))

    missing = sorted(job_skills - resume_skills)

    return matched, missing