from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import os
from langgraph.checkpoint.sqlite import SqliteSaver


class CheckpointManager:
    def __init__(self, root):
        if os.environ.get("GRAPH_HOST_COUNT", "1") != "1":
            raise RuntimeError("SQLite graph checkpoints require a single host")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, tenant_id):
        return self.root / (sha256(tenant_id.encode()).hexdigest() + ".sqlite")

    @contextmanager
    def open(self, tenant_id):
        with SqliteSaver.from_conn_string(str(self.path(tenant_id))) as saver:
            yield saver
