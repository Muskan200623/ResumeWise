
import re

try:
    from spellchecker import SpellChecker
except ImportError:
    SpellChecker = None


# ---------------------------------------------------------
# COMMON RESUME, TECHNICAL AND DIGITAL TERMS
# ---------------------------------------------------------

PROTECTED_WORDS = {
    # Names and common personal terms
    "ananya",
    "sharma",

    # Email and online platforms
    "gmail",
    "email",
    "github",
    "linkedin",
    "gitlab",
    "stackoverflow",
    "netlify",
    "streamlit",

    # Programming languages and technologies
    "python",
    "java",
    "javascript",
    "typescript",
    "html",
    "css",
    "react",
    "reactjs",
    "node",
    "nodejs",
    "express",
    "django",
    "flask",
    "c",
    "cpp",
    "sql",

    # Data and machine learning terms
    "pandas",
    "numpy",
    "scikit",
    "sklearn",
    "tensorflow",
    "pytorch",
    "machine",
    "learning",
    "deep",
    "analytics",
    "analysis",
    "analyst",
    "dataset",
    "datasets",
    "dataframe",
    "visualization",
    "preprocessing",
    "preprocess",
    "kmeans",
    "means",

    # Resume-related terms
    "resume",
    "resumes",
    "experience",
    "experiences",
    "internship",
    "internships",
    "developer",
    "developers",
    "development",
    "engineering",
    "engineer",
    "project",
    "projects",
    "certification",
    "certifications",
    "achievement",
    "achievements",
    "btech",
    "cgpa",

    # Tools and platforms
    "firebase",
    "mongodb",
    "mysql",
    "postgresql",
    "api",
    "apis",
    "json",
    "rest",
    "aws",
    "docker",
    "streamlit",
    "wordPress",
    "vite",
    "render",
}


# ---------------------------------------------------------
# COMMON VALID TECHNICAL PHRASES
# ---------------------------------------------------------

PROTECTED_PHRASES = {
    "k-means",
    "machine learning",
    "deep learning",
    "data analysis",
    "data analytics",
    "data science",
    "scikit-learn",
    "react.js",
    "node.js",
    "power bi",
    "microsoft excel",
    "github",
    "linkedin",
}


# ---------------------------------------------------------
# KNOWN TYPOS
# These are intentional corrections.
# ---------------------------------------------------------

KNOWN_CORRECTIONS = {
    "experiance": "experience",
    "experince": "experience",
    "developement": "development",
    "devolopment": "development",
    "responsiblity": "responsibility",
    "responsibilty": "responsibility",
    "acheivement": "achievement",
    "achievment": "achievement",
    "analitics": "analytics",
    "analytcs": "analytics",
    "programing": "programming",
    "programmming": "programming",
    "managment": "management",
    "communiction": "communication",
}


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def normalize_word(word):
    """
    Normalize a word for comparison.
    """
    return re.sub(r"[^a-zA-Z]", "", word).lower()


def is_protected_word(word):
    """
    Check whether a word belongs to the protected dictionary.
    """
    normalized = normalize_word(word)

    return (
        normalized in PROTECTED_WORDS
        or word.lower() in PROTECTED_WORDS
    )


def is_likely_proper_name(word, previous_word=""):
    """
    Avoid false positives for names.

    Capitalized words are commonly names, company names,
    college names, or technology names.
    """

    if not word:
        return False

    # Ignore words with an initial capital letter.
    # Example: Ananya, Sharma, Banasthali
    if word[0].isupper() and not word.isupper():
        return True

    return False


def mask_sensitive_content(text):
    """
    Replace email addresses and URLs before spelling analysis.
    This prevents words such as gmail, com, github, etc.
    from being checked independently.
    """

    email_pattern = r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b"
    url_pattern = r"https?://\S+|www\.\S+"

    text = re.sub(email_pattern, " ", text)
    text = re.sub(url_pattern, " ", text)

    return text


def get_context(text, start_index, end_index, window=80):
    """
    Return nearby text to help the user understand
    where the suspected spelling issue occurred.
    """

    start = max(0, start_index - window)
    end = min(len(text), end_index + window)

    context = text[start:end].replace("\n", " ")

    return context.strip()


# ---------------------------------------------------------
# MAIN SPELLING CHECKER
# ---------------------------------------------------------

def check_spelling(text):
    """
    Check spelling while reducing false positives.

    Returns a list of dictionaries containing:
    - found word
    - suggested correction
    - approximate line
    - context
    - priority
    """

    if not text or not text.strip():
        return []

    if SpellChecker is None:
        return []

    spell = SpellChecker(
        distance=1
    )

    original_text = text
    analysis_text = mask_sensitive_content(text)

    issues = []

    # Detect words while preserving their locations.
    word_pattern = r"\b[A-Za-z][A-Za-z'-]*\b"

    for match in re.finditer(word_pattern, analysis_text):

        word = match.group()
        normalized_word = normalize_word(word)

        if not normalized_word:
            continue

        # Ignore very short words.
        if len(normalized_word) <= 2:
            continue

        # Ignore protected technical and resume words.
        if is_protected_word(word):
            continue

        # Ignore proper names and organization names.
        if is_likely_proper_name(word):
            continue

        # Ignore words that contain numbers.
        if any(character.isdigit() for character in word):
            continue

        # Ignore known valid technical words and phrases.
        if word.lower() in {
            phrase.lower()
            for phrase in PROTECTED_PHRASES
        }:
            continue

        # First check manually known spelling mistakes.
        if normalized_word in KNOWN_CORRECTIONS:

            suggestion = KNOWN_CORRECTIONS[normalized_word]

            line_number = (
                original_text[:match.start()].count("\n") + 1
            )

            context = get_context(
                original_text,
                match.start(),
                match.end()
            )

            issues.append({
                "type": "Spelling",
                "word": word,
                "suggestion": suggestion,
                "line": line_number,
                "context": context,
                "priority": "High",
            })

            continue

        # Check the word using pyspellchecker.
        unknown_words = spell.unknown([normalized_word])

        if normalized_word not in unknown_words:
            continue

        suggestions = spell.candidates(normalized_word)

        if not suggestions:
            continue

        suggestion = spell.correction(normalized_word)

        if not suggestion:
            continue

        # Do not report if the suggested word is identical.
        if suggestion.lower() == normalized_word.lower():
            continue

        # Avoid suspicious or very different suggestions.
        if abs(len(suggestion) - len(normalized_word)) > 3:
            continue

        # Ignore very short or unreliable corrections.
        if len(suggestion) <= 2:
            continue

        line_number = (
            original_text[:match.start()].count("\n") + 1
        )

        context = get_context(
            original_text,
            match.start(),
            match.end()
        )

        issues.append({
            "type": "Possible spelling",
            "word": word,
            "suggestion": suggestion,
            "line": line_number,
            "context": context,
            "priority": "Review",
        })

    # Remove duplicate results.
    unique_issues = []
    seen = set()

    for issue in issues:

        key = (
            issue["word"].lower(),
            issue["suggestion"].lower(),
            issue["line"]
        )

        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    return unique_issues