"""
Cleanup Worker - Automatically delete old clip files
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("cleanup_worker")


async def cleanup_old_clips():
    """
    Delete clip files older than CLIP_RETENTION_HOURS.

    This runs periodically to free up storage space.
    """
    retention_hours = settings.CLIP_RETENTION_HOURS
    cutoff_time = datetime.now() - timedelta(hours=retention_hours)

    outputs_dir = settings.OUTPUTS_DIR

    if not outputs_dir.exists():
        return

    deleted_count = 0

    for file_path in outputs_dir.glob("*.mp4"):
        try:
            # Get file modification time
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

            if file_mtime < cutoff_time:
                file_path.unlink()
                deleted_count += 1
                logger.info(f"Deleted old clip: {file_path.name}")
        except Exception as e:
            logger.warning(f"Could not delete {file_path}: {e}")

    if deleted_count > 0:
        logger.info(f"Cleanup complete: deleted {deleted_count} old clips")


async def run_cleanup_loop():
    """
    Background loop that runs cleanup every 10 minutes.
    """
    logger.info(f"Cleanup worker started (retention: {settings.CLIP_RETENTION_HOURS} hours)")

    while True:
        try:
            await cleanup_old_clips()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

        # Wait 10 minutes before next cleanup
        await asyncio.sleep(600)
