import asyncio
import logging
from typing import Any, Coroutine

from telegram import Chat
from telegram.constants import ChatAction

logger = logging.getLogger(__name__)


async def run_with_typing(chat: Chat, coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine while periodically sending ChatAction.TYPING every 4s per D-11."""
    stop_event = asyncio.Event()

    async def _keep_typing() -> None:
        while not stop_event.is_set():
            try:
                await chat.send_action(ChatAction.TYPING)
            except Exception as e:
                logger.debug("Failed to send typing chat action: %s", e)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=4.0)
            except asyncio.TimeoutError:
                pass

    typing_task = asyncio.create_task(_keep_typing())
    try:
        return await coro
    finally:
        stop_event.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass
