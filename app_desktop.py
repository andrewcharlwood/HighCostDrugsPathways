"""Desktop entry point: Dash app inside a pywebview native window."""

import sys
import socket
import threading
import time
from pathlib import Path

# Ensure src/ is on sys.path so that core/, data_processing/, etc. are importable
_src_dir = str(Path(__file__).resolve().parent / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import webview
from dash_app.app import app


def find_free_port(start: int = 8050) -> int:
    """Find the first available port starting from *start*."""
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found")


def wait_for_server(port: int, timeout: float = 30.0) -> None:
    """Block until the Dash server accepts connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise TimeoutError(f"Server did not start within {timeout}s")


def main() -> None:
    port = find_free_port()

    server_thread = threading.Thread(
        target=app.run,
        kwargs={"debug": False, "port": port, "use_reloader": False},
        daemon=True,
    )
    server_thread.start()
    wait_for_server(port)

    webview.create_window(
        "NHS Pathway Analysis",
        f"http://127.0.0.1:{port}",
        width=1400,
        height=900,
    )
    webview.start()


if __name__ == "__main__":
    main()
