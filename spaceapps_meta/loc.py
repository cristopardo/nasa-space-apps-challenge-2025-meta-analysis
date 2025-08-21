from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def _run(cmd, cwd: Path = None) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    return p.returncode, p.stdout or "", p.stderr or ""


def has_cloc() -> bool:
    return shutil.which("cloc") is not None


def count_lines_with_cloc(repo_dir: Path) -> Optional[int]:
    print(f"🧮 [cloc] Counting lines in {repo_dir.name}...")
    r, out, err = _run(['cloc', '--json', '--quiet', '--git', '.'], cwd=repo_dir)
    if r != 0:
        return None
    try:
        data = json.loads(out)
        if 'SUM' in data and 'code' in data['SUM']:
            return int(data['SUM']['code'])
    except Exception:
        return None
    return None


def count_lines_with_wc(repo_dir: Path) -> int:
    # Sum wc -l over text files tracked by git; skip common binary extensions
    print(f"🧮 [wc] Counting lines in {repo_dir.name}...")
    r, out, err = _run(['git', 'ls-files', '-z'], cwd=repo_dir)
    files = [f for f in out.split('\x00') if f]
    total = 0
    bin_ext = {
        '.png','.jpg','.jpeg','.gif','.webp','.svg','.pdf','.zip','.gz','.tar','.7z',
        '.exe','.dll','.so','.dylib','.bin','.mp4','.mov','.avi','.mkv','.ogg','.mp3',
        '.wav','.flac','.ico','.ttf','.otf'
    }
    for rel in files:
        if Path(rel).suffix.lower() in bin_ext:
            continue
        r2, out2, err2 = _run(['wc', '-l', rel], cwd=repo_dir)
        if r2 == 0 and out2.strip():
            tok = out2.strip().split()[0]
            try:
                total += int(tok)
            except Exception:
                pass
    return total
