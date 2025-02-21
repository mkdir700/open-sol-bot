import asyncio
import time
from typing import Optional

import backoff
import httpx
from common.cp.swap_event import SwapEventConsumer
from common.cp.swap_result import SwapResultProducer
from common.log import logger
from common.prestart import pre_start
from common.types.swap import SwapEvent, SwapResult
from db.redis import RedisClient
from trading.copytrade import CopyTradeProcessor
from trading.executor import TradingExecutor
from trading.settlement import SwapSettlementProcessor
from trading.utils import get_async_client


class Trading:
    def __init__(self):
        self.redis = RedisClient.get_instance()
        self.rpc_client = get_async_client()
        self.trading_executor = TradingExecutor(self.rpc_client)
        self.swap_settlement_processor = SwapSettlementProcessor()
        # 创建多个消费者实例
        self.num_consumers = 3  # 可以根据需要调整消费者数量
        self.swap_event_consumers = []
        for i in range(self.num_consumers):
            consumer = SwapEventConsumer(
                self.redis,
                "trading:swap_event",
                f"trading:new_swap_event:{i}",  # 为每个消费者创建唯一的名称
            )
            consumer.register_callback(self._process_swap_event)
            self.swap_event_consumers.append(consumer)

        self.copytrade_processor = CopyTradeProcessor()

        self.swap_result_producer = SwapResultProducer(self.redis)
        # 添加任务池和信号量
        self.task_pool = set()
        self.max_concurrent_tasks = 10
        self.semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

    async def _process_single_swap_event(self, swap_event: SwapEvent):
        """处理单个交易事件的核心逻辑"""
        async with self.semaphore:
            logger.info(f"Processing swap event: {swap_event}")

            try:
                sig = await self._execute_swap(swap_event)
                swap_result = await self._record_swap_result(sig, swap_event)
                logger.info(f"Successfully processed swap event: {swap_event}")
                return swap_result
            except (httpx.ConnectTimeout, httpx.ConnectError):
                logger.error("Connection error")
                await self._record_failed_swap(swap_event)
                return
            except Exception as e:
                logger.exception(f"Failed to process swap event: {swap_event}")
                # 即使发生错误也要记录结果
                await self._record_failed_swap(swap_event)
                raise e

    @backoff.on_exception(
        backoff.expo,
        (httpx.ConnectTimeout, httpx.ConnectError),
        max_tries=3,
        base=1.5,
        factor=0.1,
        max_time=2,
    )
    async def _execute_swap(self, swap_event: SwapEvent) -> Optional[str]:
        """执行交易并返回签名"""
        sig = await self.trading_executor.exec(swap_event)
        logger.info(f"Transaction submitted: {sig}")
        return sig

    @backoff.on_exception(
        backoff.expo,
        (httpx.ConnectTimeout, httpx.ConnectError),
        max_tries=2,
        base=1.5,
        factor=0.1,
        max_time=2,
    )
    async def _record_swap_result(
        self, sig: Optional[str], swap_event: SwapEvent
    ) -> SwapResult:
        """记录交易结果"""
        if not sig:
            return await self._record_failed_swap(swap_event)

        swap_record = await self.swap_settlement_processor.process(sig, swap_event)

        swap_result = SwapResult(
            swap_event=swap_event,
            swap_record=swap_record,
            user_pubkey=swap_event.user_pubkey,
            transaction_hash=str(sig),
            submmit_time=int(time.time()),
        )

        await self.swap_result_producer.produce(swap_result)
        logger.info(f"Recorded transaction: {sig}")
        return swap_result

    async def _record_failed_swap(self, swap_event: SwapEvent) -> SwapResult:
        """记录失败的交易结果"""
        swap_result = SwapResult(
            swap_event=swap_event,
            user_pubkey=swap_event.user_pubkey,
            transaction_hash=None,
            submmit_time=int(time.time()),
        )
        await self.swap_result_producer.produce(swap_result)
        return swap_result

    async def _process_swap_event(self, swap_event: SwapEvent):
        """创建新的任务来处理交易事件"""
        task = asyncio.create_task(self._process_single_swap_event(swap_event))
        self.task_pool.add(task)
        task.add_done_callback(self.task_pool.discard)

    async def start(self):
        asyncio.create_task(self.copytrade_processor.start())
        # 启动所有消费者
        for consumer in self.swap_event_consumers:
            await consumer.start()

    async def stop(self):
        """优雅关闭所有消费者"""
        # 停止跟单交易
        self.copytrade_processor.stop()

        # 停止所有消费者
        for consumer in self.swap_event_consumers:
            consumer.stop()

        if self.task_pool:
            logger.info("Waiting for remaining tasks to complete...")
            await asyncio.gather(*self.task_pool, return_exceptions=True)
        logger.info("All consumers stopped")


if __name__ == "__main__":
    pre_start()
    trading = Trading()
    try:
        asyncio.run(trading.start())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        asyncio.run(trading.stop())
        logger.info("Shutdown complete")
