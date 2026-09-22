"""Start the unified application with the selected default variant."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=['original','lc_v1','lc_v1_1','lc_v2'], default='lc_v2')
    parser.add_argument('--port', type=int, default=8501)
    args = parser.parse_args()
    env = dict(os.environ, BONE_VARIANT=args.variant)
    raise SystemExit(subprocess.call([sys.executable, '-m', 'streamlit', 'run', 'streamlit_app.py',
                                    '--server.port', str(args.port), '--server.address', '127.0.0.1'],
                                   cwd=Path(__file__).resolve().parent, env=env))

