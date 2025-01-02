# Solana Smart Trader

⚠️⚠️⚠️⚠️⚠️

**当前项目已不再维护，因为作者最近在写一个类似 GMGN 那样的交易机器人（包含跟单功能）。新的 bot 目前处于私有，不过很快将会和大家见面，经过初步测试后仍会在此仓库中开源，感谢大家支持！**

**The current project is no longer maintained, as the author has recently been working on a trading bot similar to GMGN (including copy trading functionality). The new bot is currently private, but it will soon be available to everyone. After initial testing, it will still be open-sourced in this repository. Thank you all for your support!**

⚠️⚠️⚠️⚠️⚠️

## 简介

Solana Smart Trader 是一个用于监控 Solana 区块链上聪明钱钱包的工具。该程序能够实时跟踪这些钱包的交易信息，并自动执行跟随聪明钱的买入或卖出操作，帮助用户抓住投资机会。

## 特性

- **实时监控**：持续监控指定的聪明钱钱包，获取最新的交易信息，目前可在 5 秒内解析并推送交易详情
- **tgbot 报警**：通过 Telegram 机器人推送交易日志和警报，确保用户及时获取重要信息

### TODO 

- [ ] 订单模块：实现交易功能，包括买入和卖出
- [ ] 集成 GMGN 机器人：在 Telegram 上完成交易
- [ ] 动态配置：允许用户动态配置参数，而无需重启程序

## 程序架构

该程序由以下几个模块组成：

- **monitor**：监控聪明钱钱包，当被监控钱包产生新的交易时，会将消息发送至 Redis 队列。
- **parser**：解析模块，获取交易详情并解析出相关数据。
- **tgbot**：主要用于推送聪明钱的交易日志，确保用户及时获取交易信息。
- **order**：订单模块，用于交易活动（如买入或卖出等功能），该功能尚待实现。

## 安装

1. 确保你的系统上已安装 [Docker](https://www.docker.com/) 和 [Docker Compose](https://docs.docker.com/compose/)。
2. 克隆本仓库：
   ```bash
   git clone https://github.com/mkdir700/solana-smart-trader.git
   ```
3. 进入项目目录：
   ```bash
   cd solana-smart-trader
   ```
4. 运行以下命令以启动 Docker 容器：
   ```bash
   make up
   ```

## 配置

在项目目录中，你会找到一个名为 `config.toml.example` 的示例配置文件。请将其重命名为 `config.toml`，并根据你的需求进行修改。

### 配置文件示例

```toml
[general]
rpc_nodes = ["api.mainnet-beta.solana.com"]

[monitor]
smart_wallets = [
  "EARFf4ZxBRBuPJc1DyhNwXG5GJNJYSEZHNUJwTSGhzyQ",
]

[parser]

[order]
gmgn_bot_name = ""
tg_api_hash = ""
tg_api_id = 121212212

[tgbot]
token = ""  # 机器人 token
my_chat_id = 5049111111111  # 你与机器人之间的 chat_id
```

## 使用方法

1. 配置钱包地址：在 `config.toml` 文件中添加你想要监控的聪明钱钱包地址。
2. 程序将开始监控指定钱包的交易，并根据设定的策略自动执行交易。

## 贡献

欢迎任何形式的贡献！如果你有建议、bug 报告或功能请求，请提交 issue 或者直接发起 pull request。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。
