"""Starts the API and the UI together:  python run.py
Press Ctrl+C to stop both."""
import os
import socket
import subprocess
import sys
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
API_PORT, UI_PORT = 8000, 8501


def port_busy(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_for(port: int, timeout: int = 40) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if port_busy(port):
            return True
        time.sleep(0.5)
    return False


def main() -> None:
    os.chdir(ROOT)
    if not os.path.exists(".env"):
        sys.exit(".env not found. Run: copy .env.example .env  (then fill in your keys)")
    for port in (API_PORT, UI_PORT):
        if port_busy(port):
            sys.exit(f"Port {port} is already in use. Stop the old server first (Ctrl+C).")

    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(API_PORT)]
    )
    ui = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "streamlit_app.py",
         "--server.port", str(UI_PORT), "--server.headless", "true",
         "--server.address", "localhost"]
    )
    if wait_for(UI_PORT):
        webbrowser.open(f"http://localhost:{UI_PORT}")
    print(f"\nUI : http://localhost:{UI_PORT}\nAPI: http://127.0.0.1:{API_PORT}/docs\nPress Ctrl+C to stop\n")

    try:
        while api.poll() is None and ui.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in (api, ui):
            if p.poll() is None:
                p.terminate()
        for p in (api, ui):
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
