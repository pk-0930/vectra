import json
import os
from pathlib import Path


def load_local_settings() -> None:
    settings_path = Path(__file__).resolve().parent.parent / "local.settings.json"
    if not settings_path.exists():
        return

    with settings_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    for key, value in payload.get("Values", {}).items():
        if key not in os.environ and value is not None:
            os.environ[key] = str(value)
