from __future__ import annotations
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from .io import read_repo_urls
from .gitmeta import analyze_repo


def analyze_from_csv(csv_path: str, url_col: str = "Github", jobs: int = None) -> pd.DataFrame:
    csv_path = Path(csv_path)
    jobs = jobs or (os.cpu_count() or 4)
    urls: List[str] = read_repo_urls(csv_path, url_col=url_col)
    rows: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        futs = {ex.submit(analyze_repo, url): url for url in urls}
        for fut in as_completed(futs):
            try:
                rows.append(fut.result())
            except Exception as e:
                rows.append({'repo_url': futs[fut], 'clone_status': f'ERROR: {e}'})

    df = pd.DataFrame(rows)
    col_order = [
        'repo_url','repo_slug','contributors_count','commits_count',
        'first_commit_iso','last_commit_iso','total_lines',
        'avg_lines_changed_per_commit','default_branch','size_on_disk_mb','clone_status'
    ]
    for c in col_order:
        if c not in df.columns:
            df[c] = None
    df = df[col_order]
    return df


def save_dataframe(df: pd.DataFrame, out_path: str) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding='utf-8')
