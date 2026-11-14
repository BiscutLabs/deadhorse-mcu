"""Local check gate. Invoke through tools/env/run.py run."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    for command in ([sys.executable, 'tools/env/check.py'],
                    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tools', '-p', 'test_*.py', '-v'],
                    [sys.executable, 'tools/check_structure.py', '--include-untracked'],
                    ['bash', 'sw/flight/loop-measurement/check.sh']):
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode: return result.returncode
    print('PASS', flush=True)
    return 0


if __name__ == '__main__': sys.exit(main())
