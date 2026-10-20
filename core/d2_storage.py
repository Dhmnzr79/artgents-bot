"""Single server-owned location of the durable D2 store."""
import os
from pathlib import Path

from core.client_runtime import per_client_data_dir


def dialogue_store_path(client_id: str) -> Path:
    configured = os.getenv("D2_DIALOGUE_DB_PATH")
    return Path(configured) if configured else Path(per_client_data_dir(client_id)) / "d2_dialogue.sqlite"
