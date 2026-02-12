#!/usr/bin/env python3
"""
GST Scanner Bot - Main Launcher
Clean startup with proper path handling for the new directory structure
"""
import sys
import os
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

# Fix encoding for Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def main():
    """Main entry point"""
    try:
        # Import after path is set
        from config import validate_config
        import config
        from utils.logger import get_logger
        from utils.metrics_tracker import get_metrics_tracker
        from utils.health_server import HealthServer
        from bot.telegram_bot import GSTScannerBot
        
        print("\n" + "="*80)
        print("GST SCANNER BOT")
        print("="*80)
        print(f"Project Root: {PROJECT_ROOT}")
        print("="*80 + "\n")
        
        # Validate configuration
        validate_config()
        print("[OK] Configuration validated")
        
        # Initialize monitoring
        logger = get_logger(log_level=config.LOG_LEVEL)
        metrics = get_metrics_tracker()
        logger.info("Starting GST Scanner Bot", component="Main")
        
        # Decide HTTP server strategy:
        # - When FastAPI is enabled, it serves as the HTTP server (has /health)
        #   so the separate health server is redundant (especially on Cloud Run
        #   where only one port receives traffic).
        # - When FastAPI is disabled, the health server runs as before.
        api_handles_http = config.FEATURE_API_ENABLED

        # Start health server only when FastAPI is NOT handling HTTP
        health_server = None
        if config.HEALTH_SERVER_ENABLED and not api_handles_http:
            health_server = HealthServer(
                port=config.HEALTH_SERVER_PORT,
                bot_instance=None,  # Will be set after bot creation
                metrics_tracker=metrics,
                logger=logger
            )
            if health_server.start():
                logger.info(f"Health server running on port {config.HEALTH_SERVER_PORT}", component="Health")
        
        # Create and run bot
        bot = GSTScannerBot()
        
        # Update health server with bot reference
        if health_server:
            from utils.health_server import HealthCheckHandler
            HealthCheckHandler.bot_instance = bot
        
        # Start FastAPI REST API if enabled (runs alongside the bot)
        if config.FEATURE_API_ENABLED:
            if not config.API_JWT_SECRET:
                raise ValueError("API_JWT_SECRET must be set when FEATURE_API_ENABLED=true")
            import threading
            import uvicorn
            from api.main import create_app
            
            api_app = create_app()
            api_thread = threading.Thread(
                target=uvicorn.run,
                args=(api_app,),
                kwargs={"host": config.API_HOST, "port": config.API_PORT, "log_level": "info"},
                daemon=True,
                name="FastAPI-Server",
            )
            api_thread.start()
            logger.info(
                f"REST API running on http://{config.API_HOST}:{config.API_PORT} (Swagger: /docs)",
                component="API",
            )
            if os.getenv('K_SERVICE'):
                logger.info(
                    f"Cloud Run detected: FastAPI is the primary HTTP server on PORT {config.API_PORT}",
                    component="API",
                )
        
        logger.info("Bot started successfully", component="Main")
        bot.run()
        
    except Exception as e:
        print(f"\n[FAIL] Failed to start bot: {str(e)}")
        if 'logger' in locals():
            logger.critical(f"Bot startup failed: {str(e)}", component="Main", exc_info=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Bot stopped by user")
        print("✅ Shutdown complete")
        sys.exit(0)
