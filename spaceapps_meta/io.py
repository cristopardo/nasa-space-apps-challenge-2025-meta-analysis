from __future__ import annotations
import csv
import re
from pathlib import Path
from typing import List, Optional

GITHUB_URL_RE = re.compile(
    r"https?://(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/|$)",
    re.IGNORECASE
)


def read_repo_urls(csv_path: Path, url_col: str = "Github") -> List[str]:
    csv_path = Path(csv_path)
    urls: List[str] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if url_col not in reader.fieldnames:
            raise ValueError(f"Column '{url_col}' not found. Available: {reader.fieldnames}")
        for row in reader:
            url = (row.get(url_col) or '').strip()
            if url:
                urls.append(url)
    return urls


def parse_slug(repo_url: str) -> Optional[str]:
    m = GITHUB_URL_RE.match(repo_url.strip())
    if not m:
        return None
    owner, name = m.group(1), m.group(2)
    return f"{owner}/{name}"
