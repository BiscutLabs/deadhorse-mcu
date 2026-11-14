"""Container startup: direct outputs/caches to the mounted repository."""
import os
from pathlib import Path
import sys

root = Path('/work')
if not (root / 'tools/env/lock.json').is_file():
    sys.exit('ENV_ROOT: mount the repository at /work')
for name in ('home', 'tmp', 'cache'):
    (root / 'build/env' / name).mkdir(parents=True, exist_ok=True)
os.environ.update(HOME='/work/build/env/home', TMPDIR='/work/build/env/tmp',
                  XDG_CACHE_HOME='/work/build/env/cache',
                  COURSIER_CACHE='/work/build/env/cache/coursier',
                  SBT_OPTS='-Dsbt.global.base=/work/build/env/cache/sbt -Dsbt.boot.directory=/work/build/env/cache/sbt-boot -Dsbt.ivy.home=/work/build/env/cache/ivy')
os.chdir(root)
os.execvp(sys.argv[1], sys.argv[1:])
