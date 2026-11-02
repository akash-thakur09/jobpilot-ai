import sys
import os
import subprocess
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
project_root = backend_dir.parent

# Auto-delegate to project virtual environment if invoked with global python
venv_python = backend_dir / ".venv" / "Scripts" / "python.exe"
if not venv_python.exists():
    venv_python = backend_dir / ".venv" / "bin" / "python"

if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    result = subprocess.run([str(venv_python)] + sys.argv)
    sys.exit(result.returncode)

for path in [str(project_root), str(backend_dir)]:
    if path not in sys.path:
        sys.path.insert(0, path)

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("  JobPilot AI Backend Server")
    print("  URL: http://127.0.0.1:8000")
    print("  Docs: http://127.0.0.1:8000/docs")
    print("=" * 60)
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
