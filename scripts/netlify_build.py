import json
import os
from pathlib import Path

base_url = os.getenv("FREETUVE_API_BASE_URL", "").strip().rstrip("/")
Path("frontend/config.js").write_text(
    "window.FREETUVE_API_BASE_URL = " + json.dumps(base_url) + ";\n",
    encoding="utf-8",
)
