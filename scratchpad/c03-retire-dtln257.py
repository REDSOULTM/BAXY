"""Remove only obsolete DTLN dependencies from the registered voice venv."""
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import subprocess
import sys
from packaging.requirements import Requirement

expected = Path('C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe').resolve()
assert Path(sys.executable).resolve() == expected
targets = {'ai-edge-litert', 'backports-strenum', 'ml-dtypes'}
def canonical(name):
    return re.sub('[-_.]+', '-', name).lower()
parents = []
for package in metadata.distributions():
    parent = canonical(package.metadata['Name'])
    for raw in package.requires or []:
        req = Requirement(raw)
        if canonical(req.name) in targets and parent not in targets and (req.marker is None or req.marker.evaluate()):
            parents.append((parent, raw))
assert not parents, parents
before = {name: metadata.version(name) for name in sorted(targets)}
print(json.dumps({'removedVersions': before, 'otherActiveParents': parents}), flush=True)
subprocess.run([sys.executable, '-m', 'pip', 'uninstall', '-y', *sorted(targets)], check=True)
for name in targets:
    try:
        metadata.distribution(name)
    except metadata.PackageNotFoundError:
        continue
    raise AssertionError(name)
subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
print('obsolete_dtln_dependencies_removed_and_pip_check_passed', flush=True)
