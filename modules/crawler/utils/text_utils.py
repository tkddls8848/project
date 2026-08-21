import re
from typing import Any

def clean_text(text: Any) -> Any:
    """Removes HTML tags and normalizes whitespace."""
    if not isinstance(text, str):
        return text
    text = re.sub(r'[\n\r\t]+', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()
