"""Set up the optional caption reader separately from the paid API environment."""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def main():
    if not (3, 10) <= sys.version_info < (3, 15):
        print('Python 3.10 through 3.14 is required for the optional caption reader.')
        return 1
    folder = ROOT / '.youtube-venv'
    python = folder / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    requirements = ROOT / 'requirements.youtube.txt'
    marker = folder / '.requirements.sha256'
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    try:
        if not python.exists():
            print('Preparing the free YouTube caption reader...')
            venv.EnvBuilder(with_pip=True).create(folder)
        if not marker.exists() or marker.read_text().strip() != digest:
            print('One-time download from PyPI. No API key or paid account required.')
            subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(requirements)], check=True)
            marker.write_text(digest)
        return subprocess.call([str(python), str(ROOT / 'free_server.py')], cwd=ROOT)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'Setup failed: {exc}\nUse OPEN_ME.html with pasted captions, or start_free_windows.bat.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
