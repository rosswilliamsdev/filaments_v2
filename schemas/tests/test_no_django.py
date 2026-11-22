"""The schemas package must install and import without Django (the MCP server depends on it)."""

import subprocess
import sys

CHECK = """
import sys
import schemas, schemas.common, schemas.tags, schemas.filaments
loaded = sorted(m for m in sys.modules if m == "django" or m.startswith("django."))
assert not loaded, loaded
"""


def test_importing_schemas_does_not_load_django():
    # A fresh process: pytest-django has already imported Django into this one.
    result = subprocess.run([sys.executable, "-c", CHECK], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
