import argparse
import asyncio
import signal
import sys
from loguru import logger

from config import load_config
from worker import WorkerPool


def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{message}</cyan>",
        level="INFO",
    )
    logger.add(
        "twreg.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Twitch Account Registration Tool")
    parser.add_argument("-c", "--config", default="config.yaml", help="Config file path")
    parser.add_argument("-n", "--count", type=int, default=None, help="Number of accounts to create (0=unlimited)")
    parser.add_argument("-w", "--concurrency", type=int, default=None, help="Concurrent workers")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode (for debugging)")
    parser.add_argument("--api-url", default=None, help="CDK API base URL")
    parser.add_argument("--api-token", default=None, help="CDK API token")
    parser.add_argument("--mail-domain", default=None, help="Email domain for temp mail")
    return parser.parse_args()


async def main():
    setup_logging()
    args = parse_args()
    cfg = load_config(args.config)

    if args.count is not None:
        cfg["worker"]["total_count"] = args.count
    if args.concurrency is not None:
        cfg["worker"]["concurrency"] = args.concurrency
    if args.headed:
        cfg["browser"]["headless"] = False
    if args.api_url:
        cfg["cdk_api"]["base_url"] = args.api_url
    if args.api_token:
        cfg["cdk_api"]["api_token"] = args.api_token
    if args.mail_domain:
        cfg["tempmail"]["mail_domain"] = args.mail_domain

    logger.info("Twitch Registration Tool starting")
    logger.info(f"Config: concurrency={cfg['worker']['concurrency']}, count={cfg['worker']['total_count'] or 'unlimited'}")
    logger.info(f"Tempmail: {cfg['tempmail']['base_url']}")
    logger.info(f"CDK API: {cfg['cdk_api']['base_url'] or 'not configured'}")

    pool = WorkerPool(cfg)

    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, pool.stop)
        loop.add_signal_handler(signal.SIGTERM, pool.stop)

    try:
        await pool.run()
    except KeyboardInterrupt:
        logger.info("Interrupted, shutting down...")
        pool.stop()


if __name__ == "__main__":
    asyncio.run(main())
