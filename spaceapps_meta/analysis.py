from __future__ import annotations
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from .io import read_repo_urls
from .gitmeta import analyze_repo_local
import time
from datetime import datetime


def analyze_from_csv(csv_path: str, url_col: str = "Github", jobs: int = None) -> pd.DataFrame:
    csv_path = Path(csv_path)
    jobs = jobs or (os.cpu_count() or 4)
    urls: List[str] = read_repo_urls(csv_path, url_col=url_col)
    rows: List[Dict[str, Any]] = []

    print(f"[{datetime.now().isoformat(timespec='seconds')}] 🔍 Analyzing {len(urls)} repositories with {jobs} threads...")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        futs = {ex.submit(analyze_repo_local, url, "repos"): url for url in urls}
        for idx, fut in enumerate(as_completed(futs), 1):
            url = futs[fut]
            try:
                result = fut.result()
                print(f"[{datetime.now().isoformat(timespec='seconds')}] ✅ [{idx}/{len(urls)}] {url} → {result.get('clone_status')}")
                rows.append(result)
            except Exception as e:
                print(f"[{datetime.now().isoformat(timespec='seconds')}] ❌ [{idx}/{len(urls)}] {url} → ERROR: {e}")
                rows.append({'repo_url': url, 'clone_status': f'ERROR: {e}'})

    elapsed = round(time.time() - start_time, 2)
    print(f"[{datetime.now().isoformat(timespec='seconds')}] ✅ Finished in {elapsed} seconds.")

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
