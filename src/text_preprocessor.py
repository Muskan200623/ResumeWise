import re


def clean_text(text):
    """
    Clean resume or job description text.
    """

    # Convert everything to lowercase
    text = text.lower()

    # Replace multiple spaces/new lines with one space
    text = re.sub(r"\s+", " ", text)

    # Keep letters, numbers and common programming symbols
    text = re.sub(r"[^a-zA-Z0-9+#.\- ]", "", text)

    return text.strip()