from typing import Optional, Type

from common.log import logger
from common.utils.jito import JitoClient
from common.utils.utils import get_async_client
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair  # type: ignore
from solders.signature import Signature  # type: ignore

from trading.swap import SwapDirection, SwapInType
from trading.transaction.base import TransactionSender
from trading.transaction.builders.base import TransactionBuilder
from trading.transaction.builders.gmgn import GMGNTransactionBuilder
from trading.transaction.builders.pump import PumpTransactionBuilder
from trading.transaction.builders.ray_v4 import RaydiumV4TransactionBuilder
from trading.transaction.protocol import TradingRoute
from trading.transaction.sender import DefaultTransactionSender, JitoTransactionSender


class TransactionFactory:
    """交易工厂类，用于创建交易构建器和发送器的组合"""

    _builders: dict[TradingRoute, Type[TransactionBuilder]] = {
        TradingRoute.PUMP: PumpTransactionBuilder,
        TradingRoute.RAYDIUM_V4: RaydiumV4TransactionBuilder,
        TradingRoute.GMGN: GMGNTransactionBuilder,
    }

    def __init__(
        self,
        rpc_client: AsyncClient,
        jito_client: Optional[JitoClient] = None,
    ):
        """初始化交易工厂

        Args:
            rpc_client (AsyncClient): RPC 客户端
            jito_client (Optional[JitoClient], optional): Jito 客户端. Defaults to None.
        """
        self.rpc_client = rpc_client
        self.jito_client = jito_client

    def create_builder(self, route: TradingRoute) -> TransactionBuilder:
        """创建交易构建器

        Args:
            route (TradingRoute): 交易路由类型

        Returns:
            TransactionBuilder: 交易构建器

        Raises:
            ValueError: 如果交易路由类型不支持
        """
        if route not in self._builders:
            raise ValueError(
                f"Unsupported trading route: {route}. Must be one of: {list(self._builders.keys())}"
            )

        builder_class = self._builders[route]
        return builder_class(self.rpc_client)

    def create_sender(self, use_jito: bool = False) -> TransactionSender:
        """创建交易发送器

        Args:
            use_jito (bool, optional): 是否使用 Jito. Defaults to False.

        Returns:
            TransactionSender: 交易发送器

        Raises:
            ValueError: 如果要使用 Jito 但没有提供 Jito 客户端
        """
        if use_jito:
            if self.jito_client is None:
                raise ValueError("Cannot use Jito without a Jito client")
            logger.info("Using Jito transaction sender")
            return JitoTransactionSender(self.jito_client)
        else:
            logger.info("Using default transaction sender")
            return DefaultTransactionSender(self.rpc_client)

    @classmethod
    def register_builder(
        cls, route: TradingRoute, builder_class: Type[TransactionBuilder]
    ):
        """注册新的交易构建器

        Args:
            route (TradingRoute): 交易路由类型
            builder_class (Type[TransactionBuilder]): 构建器类
        """
        cls._builders[route] = builder_class
        logger.info(f"Registered builder for route: {route}")


class TradingService:
    """交易服务，协调交易的构建和执行"""

    def __init__(
        self,
        builder: TransactionBuilder,
        sender: TransactionSender,
    ):
        """初始化交易服务

        Args:
            builder (TransactionBuilder): 交易构建器
            sender (TransactionSender): 交易发送器
        """
        self.builder = builder
        self.sender = sender
        self.default_sender = DefaultTransactionSender(get_async_client())

    @classmethod
    def create(
        cls,
        route: TradingRoute,
        rpc_client: AsyncClient,
        use_jito: bool = False,
        jito_client: Optional[JitoClient] = None,
    ) -> "TradingService":
        """创建交易服务实例

        Args:
            route (TradingRoute): 交易路由类型
            rpc_client (AsyncClient): RPC 客户端
            use_jito (bool, optional): 是否使用 Jito. Defaults to False.
            jito_client (Optional[JitoClient], optional): Jito 客户端. Defaults to None.

        Returns:
            TradingService: 交易服务实例
        """
        factory = TransactionFactory(rpc_client, jito_client)
        builder = factory.create_builder(route)
        sender = factory.create_sender(use_jito)
        return cls(builder, sender)

    async def swap(
        self,
        keypair: Keypair,
        token_address: str,
        ui_amount: float,
        swap_direction: SwapDirection,
        slippage_bps: int,
        in_type: SwapInType | None = None,
        use_jito: bool = False,
        priority_fee: float | None = None,
    ) -> Optional[Signature]:
        """执行代币交换操作

        Args:
            keypair (Keypair): 钱包密钥对
            token_address (str): 代币地址
            ui_amount (float): 交易数量
            swap_direction (SwapDirection): 交易方向
            slippage_bps (int): 滑点，以 bps 为单位
            in_type (SwapInType | None, optional): 输入类型. Defaults to None.
            use_jito (bool, optional): 是否使用 Jito. Defaults to False.
            priority_fee (float | None, optional): 优先费用. Defaults to None.

        Returns:
            Optional[Signature]: 交易签名，如果交易失败则返回 None
        """
        transaction = await self.builder.build_swap_transaction(
            keypair=keypair,
            token_address=token_address,
            ui_amount=ui_amount,
            swap_direction=swap_direction,
            slippage_bps=slippage_bps,
            in_type=in_type,
            use_jito=use_jito,
            priority_fee=priority_fee,
        )

        if use_jito:
            sender = self.sender
        else:
            sender = self.default_sender

        logger.debug(f"Built swap transaction: {transaction}")
        signature = await sender.send_transaction(transaction)
        logger.info(f"Transaction sent successfully: {signature}")
        return signature