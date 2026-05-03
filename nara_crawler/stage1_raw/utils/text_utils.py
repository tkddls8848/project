import re
from typing import Union, Dict, List, Set, Any

def clean_text(text: Any) -> Any:
    """Removes HTML tags and normalizes whitespace."""
    if not isinstance(text, str):
        return text
    text = re.sub(r'[\n\r\t]+', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

def clean_text_preserve_tags(text: Any) -> Any:
    """Normalizes whitespace but preserves HTML tags."""
    if not isinstance(text, str):
        return text
    text = re.sub(r'[\n\r\t]+', '', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

def clean_all_text(obj: Any, skip_keys: Set[str] = None) -> Any:
    """Recursively cleans all strings in a dictionary or list."""
    if skip_keys is None:
        skip_keys = set()
    elif not isinstance(skip_keys, set):
        skip_keys = set(skip_keys)

    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k in skip_keys:
                if isinstance(v, str):
                    result[k] = clean_text_preserve_tags(v)
                elif isinstance(v, (dict, list)):
                    result[k] = clean_all_text(v, skip_keys)
                else:
                    result[k] = v
            else:
                result[k] = clean_all_text(v, skip_keys)
        return result
    elif isinstance(obj, list):
        return [clean_all_text(v, skip_keys) for v in obj]
    elif isinstance(obj, str):
        return clean_text(obj)
    else:
        return obj
