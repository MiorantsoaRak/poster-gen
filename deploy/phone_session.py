"""The owner's first session on his own phone, before any server is rented (D-HOSTED-PILOT-006).

Run from backend/, and stay in front of it for the whole session:

    uv run python ../deploy/phone_session.py <password-file>

It opens a temporary public HTTPS address (a Cloudflare quick tunnel) to this machine, starts the application on
the test data (backend/data-probe) with the real providers and a one-off password, and prints the address.
Generating a poster there costs money from the test ledger. Ctrl-C closes the address: nothing stays exposed.

Needs `cloudflared` on the PATH and a built frontend (frontend/dist).
"""
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from decimal import Decimal
from pathlib import Path

# The test budget is USD 100 in all (user decision 2026-11-13, ADR-067), and 5.277673 of it was spent by study scripts outside the application's ledger
# (HANDOFF "Spend"). The ledger alone must therefore stop at 100 - 5.28, or the session could overspend unseen.
LEDGER_CAP_USD = Decimal("94.72")
ADDRESS = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
LOCAL = "http://127.0.0.1:5173"


def find_address(line: str) -> str | None:
    found = ADDRESS.search(line)
    return found.group(0) if found else None


def open_tunnel(wait_seconds: float = 60) -> tuple[subprocess.Popen, str]:
    """Starts the tunnel and returns it with its public address, or stops it and raises after the wait."""
    tunnel = subprocess.Popen(["cloudflared", "tunnel", "--no-autoupdate", "--url", LOCAL],
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    address: list[str] = []
    ready = threading.Event()

    def read():  # keeps reading after the address is found, so the tunnel never blocks on a full pipe
        for line in tunnel.stderr:
            if not address and (found := find_address(line)):
                address.append(found)
                ready.set()
        ready.set()  # the tunnel ended

    threading.Thread(target=read, daemon=True).start()
    if not ready.wait(wait_seconds) or not address:
        tunnel.terminate()
        raise SystemExit("No public address from cloudflared within the wait: nothing was exposed. "
                         "Run `cloudflared tunnel --url http://127.0.0.1:5173` by hand to see its error.")
    return tunnel, address[0]


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit(__doc__)
    if shutil.which("cloudflared") is None:
        raise SystemExit("cloudflared is not installed (or not on the PATH). Nothing was started.")

    # Imported here: the checks above must work, and be testable, without the application's settings.
    import uvicorn
    from pydantic import SecretStr

    from affiche.api import UVICORN, create_app
    from affiche.config import BACKEND_DIR, load_settings
    from affiche.posters.auth import PASSWORDS

    frontend = BACKEND_DIR.parent / "frontend"
    if not (frontend / "dist" / "index.html").is_file():
        raise SystemExit("frontend/dist is missing: build the frontend first. Nothing was started.")

    tunnel, origin = open_tunnel()
    children = {"the tunnel": tunnel}
    try:
        password = secrets.token_urlsafe(18)
        Path(argv[1]).write_text(password, encoding="utf-8")
        settings = load_settings().model_copy(update={
            "data_dir": BACKEND_DIR / "data-probe", "image_provider": "openai", "stub_fail": None,
            "openai_image_model": "gpt-image-2", "openai_image_quality": "high", "planner_provider": "claude",
            "app_origin": origin, "shop_password_hash": SecretStr(PASSWORDS.hash(password))})
        settings = settings.model_copy(update={"spend_cap_usd": min(settings.spend_cap_usd, LEDGER_CAP_USD)})
        # The production build, on loopback. Vite refuses unknown Host headers; the tunnel's host is allowed by name.
        children["the page server"] = subprocess.Popen(
            ["node", str(frontend / "node_modules/vite/bin/vite.js"), "preview", "--host", "127.0.0.1",
             "--port", "5173", "--strictPort"], cwd=frontend,
            env={**os.environ, "__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS": origin.removeprefix("https://")},
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        server = uvicorn.Server(uvicorn.Config(create_app(settings), **UVICORN, log_level="warning"))

        def watch():  # the address must not outlive a dead part, nor the application a dead address
            while not server.should_exit:
                for name, child in children.items():
                    if child.poll() is not None:
                        print(f"{name} stopped (exit {child.returncode}): closing the session.", flush=True)
                        server.should_exit = True
                time.sleep(1)

        threading.Thread(target=watch, daemon=True).start()
        print(f"\nAddress for the phone: {origin}\nPassword: in {argv[1]}\nCtrl-C ends the session.\n", flush=True)
        server.run()
    finally:
        for child in children.values():  # the tunnel first: the public address closes before anything else
            child.terminate()
        for name, child in children.items():
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                print(f"{name} did not stop and was killed.", flush=True)
        print("Session closed: the public address no longer answers.", flush=True)


if __name__ == "__main__":
    main(sys.argv)
