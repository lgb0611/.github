"""Prepare the local Python environment only when its dependency lock changes."""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent

def main():
    if sys.version_info < (3, 10):
        print('Python 3.10 or newer is required.')
        return 1
    folder = ROOT / '.venv'
    python = folder / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    lock = ROOT / 'requirements.lock.txt'
    marker = folder / '.requirements.sha256'
    digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    try:
        if not python.exists():
            print('Creating the local Python environment...')
            venv.EnvBuilder(with_pip=True).create(folder)
        if not marker.exists() or marker.read_text().strip() != digest:
            print('Installing the tested dependencies. Internet is needed once...')
            subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(lock)], check=True)
            marker.write_text(digest)
        return subprocess.call([str(python), str(ROOT / 'launch.py')], cwd=ROOT)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'Startup failed: {exc}')
        return 1

if __name__ == '__main__':
    sys.exit(main())
