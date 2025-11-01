import json
from pathlib import Path

def load_json_file(filepath: Path):
    """Load JSON data from a file and return as Python object."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)
