from __future__ import annotations
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from .io import parse_slug
from .loc import has_cloc, count_lines_with_cloc, count_lines_with_wc
from datetime import datetime


def _run(cmd, cwd: Path = None, timeout: int = 60) -> Tuple[int, str, str]:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] 🟡 Running: {' '.join(cmd)}", flush=True)
    try:
        p = subprocess.run(cmd, cwd=cwd, timeout=timeout, check=False, capture_output=True, text=True)
        print(f"[{datetime.now().isoformat(timespec='seconds')}] ✅ Done: {' '.join(cmd)} (rc={p.returncode})", flush=True)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        print(f"[{datetime.now().isoformat(timespec='seconds')}] ❌ Timeout: {' '.join(cmd)}", flush=True)
        return 1, "", f"Timeout after {timeout}s"



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

    def log(step: str):
        print(f"[{datetime.now().isoformat(timespec='seconds')}] ▶️ {step}", flush=True)

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

        log(f"{slug} → Setting safe.directory")
        _safe_git_global_safe_dir(repo_dir)

        log(f"{slug} → Getting default branch")
        r, out, err = _run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo_dir)
        metrics.default_branch = out.strip() if r == 0 else None

        log(f"{slug} → Counting commits")
        r, out, err = _run(['git', 'rev-list', '--count', 'HEAD'], cwd=repo_dir)
        commits_count = int(out.strip()) if r == 0 and out.strip().isdigit() else None
        metrics.commits_count = commits_count
        log(f"{slug} → {commits_count} commits")

        log(f"{slug} → Getting commit date range")
        r, out, err = _run(['git', 'log', '--reverse', '--format=%aI'], cwd=repo_dir)
        if r == 0:
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            if lines:
                metrics.first_commit_iso = lines[0]
                metrics.last_commit_iso = lines[-1]
                log(f"{slug} → First commit: {metrics.first_commit_iso}, Last commit: {metrics.last_commit_iso}")

        log(f"{slug} → Getting contributor count")
        r, out, err = _run(['git', 'shortlog', '-sne'], cwd=repo_dir)
        if r == 0:
            contributors = [l for l in out.splitlines() if l.strip()]
            metrics.contributors_count = len(contributors)
            log(f"{slug} → Contributors: {metrics.contributors_count}")

        log(f"{slug} → Analyzing lines changed per commit (git log --numstat)")
        r, out, err = _run(['git', 'log', '--pretty=tformat:', '--numstat'], cwd=repo_dir)
        if r == 0:
            adds = dels = 0
            for line in out.splitlines():
                parts = line.strip().split('\t')
                if len(parts) >= 3:
                    a, d = parts[0], parts[1]
                    aa = int(a) if a.isdigit() else 0
                    dd = int(d) if d.isdigit() else 0
                    adds += aa
                    dels += dd
            total_changes = adds + dels
            if commits_count and commits_count > 0:
                metrics.avg_lines_changed_per_commit = round(total_changes / commits_count, 2)
                log(f"{slug} → Avg lines changed per commit: {metrics.avg_lines_changed_per_commit}")
            else:
                log(f"{slug} → No valid commit count for average")

        log(f"{slug} → Counting lines of code (cloc or wc)")
        total_lines = None
        if has_cloc():
            total_lines = count_lines_with_cloc(repo_dir)
            log(f"{slug} → LOC via cloc: {total_lines}")
        if total_lines is None:
            total_lines = count_lines_with_wc(repo_dir)
            log(f"{slug} → LOC via wc: {total_lines}")

        metrics.total_lines = int(total_lines) if total_lines is not None else None
        metrics.size_on_disk_mb = _dir_size_mb(repo_dir)
        log(f"{slug} → Size on disk: {metrics.size_on_disk_mb} MB")
        metrics.clone_status = "OK"

        return metrics.as_dict()
    finally:
        if not keep_workdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def analyze_repo_local(repo_url: str, local_base: str = "repos") -> Dict[str, Any]:
    def log(step: str):
        print(f"[{datetime.now().isoformat(timespec='seconds')}] ▶️ {step}", flush=True)

    slug = parse_slug(repo_url)
    metrics = RepoMetrics(repo_url=repo_url, repo_slug=slug or '')
    if not slug:
        metrics.clone_status = "ERROR: invalid GitHub URL"
        return metrics.as_dict()

    repo_dir = Path(local_base) / slug.replace('/', '_')

    if not repo_dir.exists():
        log(f"❌ Local repo not found: {repo_dir}")
        metrics.clone_status = "ERROR: not found locally"
        return metrics.as_dict()

    log(f"🔍 Analyzing local repo: {repo_dir}")
    try:
        log(f"{slug} → Setting safe.directory")
        _safe_git_global_safe_dir(repo_dir)

        log(f"{slug} → Getting default branch")
        r, out, err = _run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo_dir)
        metrics.default_branch = out.strip() if r == 0 else None

        log(f"{slug} → Counting commits")
        r, out, err = _run(['git', 'rev-list', '--count', 'HEAD'], cwd=repo_dir)
        commits_count = int(out.strip()) if r == 0 and out.strip().isdigit() else None
        metrics.commits_count = commits_count
        log(f"{slug} → {commits_count} commits")

        log(f"{slug} → Getting commit date range")
        r, out, err = _run(['git', 'log', '--reverse', '--format=%aI'], cwd=repo_dir)
        if r == 0:
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            if lines:
                metrics.first_commit_iso = lines[0]
                metrics.last_commit_iso = lines[-1]
                log(f"{slug} → First: {metrics.first_commit_iso}, Last: {metrics.last_commit_iso}")

        log(f"{slug} → Getting contributor count")
        r, out, err = _run(['git', 'shortlog', '-sne'], cwd=repo_dir)
        if r == 0:
            contributors = [l for l in out.splitlines() if l.strip()]
            metrics.contributors_count = len(contributors)
            log(f"{slug} → Contributors: {metrics.contributors_count}")

        log(f"{slug} → Analyzing lines changed per commit (git log --numstat)")
        r, out, err = _run(['git', 'log', '--pretty=tformat:', '--numstat'], cwd=repo_dir)
        if r == 0:
            adds = dels = 0
            for line in out.splitlines():
                parts = line.strip().split('\t')
                if len(parts) >= 3:
                    a, d = parts[0], parts[1]
                    aa = int(a) if a.isdigit() else 0
                    dd = int(d) if d.isdigit() else 0
                    adds += aa
                    dels += dd
            total_changes = adds + dels
            if commits_count and commits_count > 0:
                metrics.avg_lines_changed_per_commit = round(total_changes / commits_count, 2)
                log(f"{slug} → Avg lines changed per commit: {metrics.avg_lines_changed_per_commit}")

        log(f"{slug} → Counting lines of code")
        total_lines = None
        if has_cloc():
            total_lines = count_lines_with_cloc(repo_dir)
            log(f"{slug} → LOC via cloc: {total_lines}")
        if total_lines is None:
            total_lines = count_lines_with_wc(repo_dir)
            log(f"{slug} → LOC via wc: {total_lines}")

        metrics.total_lines = int(total_lines) if total_lines is not None else None
        metrics.size_on_disk_mb = _dir_size_mb(repo_dir)
        log(f"{slug} → Size on disk: {metrics.size_on_disk_mb} MB")
        metrics.clone_status = "OK"
        return metrics.as_dict()

    except Exception as e:
        log(f"{slug} → ERROR: {e}")
        metrics.clone_status = f"ERROR: {e}"
        return metrics.as_dict()
