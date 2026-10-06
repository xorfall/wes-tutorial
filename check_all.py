#!/usr/bin/env python3
"""Run every chapter check in order and report each result; exit non-zero if any fails."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
TIMEOUT_SECONDS = 1800


def main():
    checks = sorted(REPO.glob('[0-9][0-9]-*/check.py'))
    failed = []
    for check in checks:
        result = subprocess.run([sys.executable, str(check)], cwd=REPO, text=True,
                                capture_output=True, timeout=TIMEOUT_SECONDS)
        lines = (result.stdout + result.stderr).strip().splitlines()
        summary = lines[-1] if lines else '(no output)'
        print(f'{check.parent.name}: {summary}')
        if result.returncode != 0:
            failed.append(check.parent.name)
    if failed:
        print(f'FAILED: {", ".join(failed)}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
