#!/usr/bin/env python3
"""
GST Scanner - Dev Bot Launcher
------------------------------

Starts the *development* Telegram bot, which is:
- Isolated via BOT_ENV=dev and TELEGRAM_DEV_BOT_TOKEN
- Non-destructive (no OCR, parsing, or Google Sheets writes)
- Intended only for testing Order Upload & OCR flows incrementally.

Production launcher (start_bot.py) remains unchanged.
"""
import sys
from pathlib import Path

# Get project root directory and ensure src/ is on sys.path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Fix encoding for Windows
if sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main() -> None:
    """Main entry point for the dev bot."""
    # Load .env from project root
    from dotenv import load_dotenv
    load_dotenv(str(PROJECT_ROOT / ".env"))

    from bot.dev_telegram_bot import main as dev_main  # Local import after path setup

    dev_main()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[DEV BOT] Stopped by user")
        sys.exit(0)

