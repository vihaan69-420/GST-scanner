#!/usr/bin/env python3
"""
Launcher script for GST Scanner Bot
Handles path setup and starts the bot
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Now import and run the bot
from bot.telegram_bot import main

if __name__ == "__main__":
    main()
