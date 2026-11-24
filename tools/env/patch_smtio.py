"""Hash-guarded logging-only repair for backward host wall-clock steps."""
import hashlib
import json
from pathlib import Path


def patched(data,manifest):
    digest=lambda value:hashlib.sha256(value).hexdigest()
    if digest(data)!=manifest['source_sha256']:
        raise ValueError('Unexpected upstream smtio source')
    old=b'from time import time\n';new=b'from time import monotonic as time\n'
    if data.count(old)!=1:raise ValueError('Ambiguous timestamp clock import')
    result=data.replace(old,new)
    if digest(result)!=manifest['patched_sha256']:
        raise ValueError('Unexpected patched smtio source')
    return result


def main():
    here=Path(__file__).resolve().parent
    manifest=json.loads((here/'smtio-monotonic.json').read_text())
    target=Path(manifest['path']);original=target.read_bytes()
    result=patched(original,manifest)
    # Retain the licensed original inside the pinned image for the behavioral
    # negative control. Never edit an installed image at runtime.
    (here/'smtio-unpatched.py').write_bytes(original)
    target.write_bytes(result)


if __name__=='__main__':main()
