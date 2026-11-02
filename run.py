import sys
import os
import subprocess
from pathlib import Path

# Auto-delegate to project virtual environment if invoked with global python
root_dir = Path(__file__).resolve().parent
venv_python = root_dir / "backend" / ".venv" / "Scripts" / "python.exe"
if not venv_python.exists():
    venv_python = root_dir / "backend" / ".venv" / "bin" / "python"

if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    result = subprocess.run([str(venv_python)] + sys.argv)
    sys.exit(result.returncode)

# Ensure project root is in sys.path
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("  JobPilot AI Backend Server")
    print("  URL: http://127.0.0.1:8000")
    print("  Docs: http://127.0.0.1:8000/docs")
    print("=" * 60)
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
