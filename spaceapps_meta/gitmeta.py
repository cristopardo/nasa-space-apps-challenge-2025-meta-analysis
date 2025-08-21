from __future__ import annotations
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from .io import parse_slug
from .loc import has_cloc, count_lines_with_cloc, count_lines_with_wc


def _run(cmd, cwd: Path = None) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    return p.returncode, p.stdout or "", p.stderr or ""


def _safe_git_global_safe_dir(path: Path):
    _run(['git', 'config', '--global', '--add', 'safe.directory', str(path)])


def _dir_size_mb(path: Path) -> float:
    total = 0
    for p in path.rglob('*'):
        if p.is_file():
            try:
                total += p.stat().st_size
            except Exception:
                pass
    return round(total / (1024*1024), 2)


@dataclass
class RepoMetrics:
    repo_url: str
    repo_slug: str
    contributors_count: Optional[int] = None
    commits_count: Optional[int] = None
    first_commit_iso: Optional[str] = None
    last_commit_iso: Optional[str] = None
    total_lines: Optional[int] = None
    avg_lines_changed_per_commit: Optional[float] = None
    default_branch: Optional[str] = None
    size_on_disk_mb: Optional[float] = None
    clone_status: str = "PENDING"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def analyze_repo(repo_url: str, keep_workdir: bool = False) -> Dict[str, Any]:
    import time
    from datetime import datetime

    def log(msg: str):
        print(f"[{datetime.now().isoformat(timespec='seconds')}] ▶️ {msg}")

    slug = parse_slug(repo_url)
    metrics = RepoMetrics(repo_url=repo_url, repo_slug=slug or '')
    if not slug:
        metrics.clone_status = "ERROR: invalid GitHub URL"
        return metrics.as_dict()

    tmpdir = Path(tempfile.mkdtemp(prefix='repo_meta_'))
    repo_dir = tmpdir / slug.replace('/', '__')

    log(f"Cloning {repo_url} → {repo_dir}")

    try:
        t0 = time.time()
        r, out, err = _run(['git', '-c', 'protocol.version=2', 'clone', '--no-tags', repo_url, str(repo_dir)])
        if r != 0:
            msg = (err or out).strip()
            metrics.clone_status = f"ERROR: {msg[:240]}"
            return metrics.as_dict()
        log(f"✅ Cloned {slug} in {round(time.time()-t0, 2)}s")

        _safe_git_global_safe_dir(repo_dir)

        r, out, err = _run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo_dir)
        metrics.default_branch = out.strip() if r == 0 else None

        r, out, err = _run(['git', 'rev-list', '--count', 'HEAD'], cwd=repo_dir)
        commits_count = int(out.strip()) if r == 0 and out.strip().isdigit() else None
        metrics.commits_count = commits_count

        log(f"📦 {slug} → {commits_count} commits")

        r, out, err = _run(['git', 'log', '--reverse', '--format=%aI'], cwd=repo_dir)
        if r == 0:
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            if lines:
                metrics.first_commit_iso = lines[0]
                metrics.last_commit_iso = lines[-1]

        r, out, err = _run(['git', 'shortlog', '-sne'], cwd=repo_dir)
        if r == 0:
            contributors = [l for l in out.splitlines() if l.strip()]
            metrics.contributors_count = len(contributors)

        r, out, err = _run(['git', 'log', '--pretty=tformat:', '--numstat'], cwd=repo_dir)
        if r == 0:
            adds = dels = 0
            for line in out.splitlines():
                parts = line.strip().split('\t')
                if len(parts) >= 3:
                    a, d = parts[0], parts[1]
                    aa = int(a) if a.isdigit() else 0
                    dd = int(d) if d.isdigit() else 0
                    adds += aa; dels += dd
            total_changes = adds + dels
            if commits_count and commits_count > 0:
                metrics.avg_lines_changed_per_commit = round(total_changes / commits_count, 2)

        log(f"📈 {slug} → Calculating LOC...")

        total_lines = None
        if has_cloc():
            total_lines = count_lines_with_cloc(repo_dir)
            log(f"🔢 LOC via cloc: {total_lines}")
        if total_lines is None:
            total_lines = count_lines_with_wc(repo_dir)
            log(f"🔢 LOC via wc: {total_lines}")

        metrics.total_lines = int(total_lines) if total_lines is not None else None
        metrics.size_on_disk_mb = _dir_size_mb(repo_dir)
        metrics.clone_status = "OK"
        return metrics.as_dict()
    finally:
        if not keep_workdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
