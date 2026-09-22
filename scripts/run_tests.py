from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
failed = False
for name in ('original', 'lc_v1', 'lc_v1_1', 'lc_v2'):
    folder = ROOT/'variants'/name
    print(f'\nRunning preserved tests: {name}', flush=True)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT), str(folder)]))
    result = subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q'], cwd=folder, env=env)
    failed |= result.returncode != 0
print('\nRunning release integration tests', flush=True)
result = subprocess.run([sys.executable, '-m', 'pytest', 'tests', '-q'], cwd=ROOT)
raise SystemExit(1 if failed or result.returncode else 0)
