"""Write the frozen API schema to backend-fastapi/openapi.json (tests fail if it drifts from the code)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.main import create_app  # noqa: E402

out = Path(__file__).resolve().parent.parent / "openapi.json"
out.write_text(json.dumps(create_app().openapi(), indent=1, sort_keys=True) + "\n")
print(f"wrote {out}")
