import asyncio
import time
from loguru import logger

from core.registrar import register_one
from core.email_client import TempMailClient
from core.api_client import CDKApiClient


class WorkerPool:

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.concurrency = cfg["worker"]["concurrency"]
        self.total_count = cfg["worker"]["total_count"]
        self.worker_name = cfg["worker"]["worker_name"]
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self.success = 0
        self.failed = 0
        self.running = True
        self.mail_client = TempMailClient(
            base_url=cfg["tempmail"]["base_url"],
            mail_domain=cfg["tempmail"].get("mail_domain", ""),
            poll_interval=cfg["tempmail"]["poll_interval"],
            poll_timeout=cfg["tempmail"]["poll_timeout"],
        )
        self.api_client = CDKApiClient(
            base_url=cfg["cdk_api"]["base_url"],
            api_token=cfg["cdk_api"]["api_token"],
        )

    async def _heartbeat_loop(self):
        while self.running:
            try:
                await self.api_client.worker_heartbeat(self.worker_name, "register")
            except Exception as e:
                logger.debug(f"Heartbeat failed: {e}")
            await asyncio.sleep(60)

    async def _run_task(self, task_id: int):
        async with self.semaphore:
            if not self.running:
                return
            result = await register_one(self.cfg, self.mail_client, self.api_client, task_id)
            if result and result.get("auth_token"):
                self.success += 1
            else:
                self.failed += 1
            logger.info(f"Progress: {self.success} success / {self.failed} failed / {self.success + self.failed} total")

    async def run(self):
        start = time.time()
        logger.info(f"Starting worker pool: concurrency={self.concurrency}, count={'unlimited' if self.total_count <= 0 else self.total_count}")

        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        try:
            if self.total_count > 0:
                tasks = [asyncio.create_task(self._run_task(i + 1)) for i in range(self.total_count)]
                await asyncio.gather(*tasks)
            else:
                task_id = 0
                pending: set[asyncio.Task] = set()
                while self.running:
                    while len(pending) < self.concurrency and self.running:
                        task_id += 1
                        t = asyncio.create_task(self._run_task(task_id))
                        pending.add(t)
                    if pending:
                        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            logger.info("Worker pool cancelled")
        finally:
            self.running = False
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            await self.mail_client.close()
            await self.api_client.close()

        elapsed = time.time() - start
        logger.info(f"Finished: {self.success} success, {self.failed} failed in {elapsed:.1f}s")

    def stop(self):
        self.running = False
