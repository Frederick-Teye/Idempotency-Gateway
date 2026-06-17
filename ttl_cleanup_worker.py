#!/usr/bin/env python
"""
Background TTL cleanup process for idempotency records.
Run this in a separate terminal/process: python ttl_cleanup_worker.py
"""

import os
import django
import time
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from django.core.management import call_command

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def cleanup_expired_records():
    """Run the cleanup command"""
    try:
        logger.info("Starting idempotency record cleanup...")
        call_command("cleanup_expired_records", ttl=3600)  # 1 hour TTL
        logger.info("Cleanup completed successfully")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")


def main():
    """Start the background scheduler"""
    scheduler = BlockingScheduler()

    # Run cleanup every 10 minutes
    scheduler.add_job(
        cleanup_expired_records,
        "interval",
        minutes=10,
        id="cleanup_job",
        name="Cleanup expired idempotency records",
    )

    logger.info("TTL Cleanup Worker started")
    logger.info("Running cleanup every 10 minutes with 1 hour TTL")
    logger.info("Press Ctrl+C to stop")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("TTL Cleanup Worker stopped")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
