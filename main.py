# -*- coding: utf-8 -*-
"""本地脚本 → QQ 播报桥。

把任意本地脚本写进「播报队列文件」的每一行，直接发到指定 QQ 会话。
全程只读文件、调平台接口，不经过大模型，因此不产生任何 token 消耗。

典型用法：配合一个本地巡检脚本，脚本只在状态发生变化时往队列里追加一行，
插件轮询到新内容就原样发出去。
"""
import asyncio
import os

from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.star import Context, Star

# 兜底默认值，配置文件 _conf_schema.json 里填了就以配置为准。
# 发布到公开仓库前，请把 DEFAULT_SESSION 清空。
DEFAULT_QUEUE = "~/logs/.netwatch_pending"
DEFAULT_SESSION = ""
DEFAULT_INTERVAL = 20


class ScriptNotify(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self._cfg = config
        self._task = None

    # ---------------- 配置读取 ----------------
    def _get(self, key, default):
        try:
            if self._cfg is None:
                return default
            value = self._cfg.get(key, default)
            return default if value in (None, "") else value
        except Exception:
            return default

    @property
    def queue_path(self) -> str:
        return os.path.expanduser(str(self._get("queue_path", DEFAULT_QUEUE)))

    @property
    def target_session(self) -> str:
        return str(self._get("target_session", DEFAULT_SESSION))

    @property
    def interval(self) -> int:
        try:
            return max(5, int(self._get("poll_interval", DEFAULT_INTERVAL)))
        except Exception:
            return DEFAULT_INTERVAL

    # ---------------- 生命周期 ----------------
    async def initialize(self):
        if not self.target_session:
            logger.warning("[脚本播报] 未配置 target_session，收到内容也不会发送")
        self._task = asyncio.create_task(self._loop())
        logger.info("[脚本播报] 已启动，监听 %s", self.queue_path)

    async def terminate(self):
        if self._task:
            self._task.cancel()
            self._task = None

    # ---------------- 主循环 ----------------
    async def _loop(self):
        await asyncio.sleep(15)
        while True:
            try:
                await self._flush()
            except Exception:
                logger.warning("[脚本播报] 处理队列失败", exc_info=True)
            await asyncio.sleep(self.interval)

    async def _flush(self):
        path = self.queue_path
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return
        # 先清空再逐条发，避免中途异常导致重复播报
        with open(path, "w", encoding="utf-8"):
            pass
        if not self.target_session:
            logger.warning("[脚本播报] 丢弃 %d 条内容：target_session 未配置", len(lines))
            return
        for line in lines:
            try:
                await self.context.send_message(
                    self.target_session, MessageChain().message(line)
                )
                logger.info("[脚本播报] 已发送: %s", line)
            except Exception:
                logger.warning("[脚本播报] 单条发送失败: %s", line, exc_info=True)
