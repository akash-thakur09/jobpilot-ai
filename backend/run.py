import sys
from pathlib import Path

# Ensure project root (parent directory of backend) is in sys.path
backend_dir = Path(__file__).resolve().parent
project_root = backend_dir.parent
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
