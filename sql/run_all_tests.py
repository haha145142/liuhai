"""Run PostgreSQL schema checks.

Always runs the static verifier. Runs the E2E test when DATABASE_URL is set;
otherwise reports the E2E step as pending rather than pretending it passed.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run(script: str) -> bool:
    print(f'\n==> {script}')
    return subprocess.run([sys.executable, str(ROOT / script)], check=False).returncode == 0

ok = run('verify_pg.py')
if not ok:
    raise SystemExit(1)

if os.getenv('DATABASE_URL'):
    if not run('test_e2e_pg.py'):
        raise SystemExit(1)
    print('\nALL PASS')
else:
    print('\nSTATIC PASS; E2E PENDING (set DATABASE_URL to run against PostgreSQL)')
