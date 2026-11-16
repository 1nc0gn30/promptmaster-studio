#!/usr/bin/env python3
"""
PromptMaster Studio Local Workbench Server (:8123)
Serves public/ and full REST API via promptmaster_studio.ui_server.
"""
import sys, os, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
PUBLIC_DIR = ROOT / "public"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from promptmaster_studio.ui_server import start_server

def main():
    parser = argparse.ArgumentParser(description="PromptMaster Studio Local Server")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true", default=True)
    args, _ = parser.parse_known_args()

    start_server(
        host=args.host,
        port=args.port,
        open_browser=False,
        public_dir=PUBLIC_DIR if PUBLIC_DIR.exists() else None,
    )

if __name__ == "__main__":
    main()
