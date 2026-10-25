import functools
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes


class UserRole(StrEnum):
    """Administrative user role hierarchy."""

    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    STAFF = "STAFF"


ROLE_HIERARCHY: dict[UserRole, int] = {
    UserRole.SUPER_ADMIN: 3,
    UserRole.ADMIN: 2,
    UserRole.STAFF: 1,
}


def get_user_role(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> UserRole:
    """Resolve user role from bot_data cache with fallback to STAFF."""
    settings = context.bot_data.get("settings")
    super_admin_id = getattr(settings, "telegram_super_admin_id", None)
    if super_admin_id is not None and user_id == super_admin_id:
        return UserRole.SUPER_ADMIN
    admin_roles: dict[int, UserRole] = context.bot_data.get("admin_roles", {})
    return admin_roles.get(user_id, UserRole.STAFF)


def require_role(min_role: UserRole) -> Callable:
    """Decorator to enforce minimum role requirement across slash commands and callback queries.

    Halts execution and returns immediate feedback:
    - Callback queries: Pop-up alert via query.answer(show_alert=True).
    - Message commands: HTML-formatted reply text detailing the required role.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any
        ) -> Any:
            user = update.effective_user
            if user is None:
                return None

            user_role = get_user_role(context, user.id)
            user_rank = ROLE_HIERARCHY.get(user_role, 0)
            required_rank = ROLE_HIERARCHY[min_role]

            if user_rank < required_rank:
                denial_alert = (
                    f"⛔ Bạn không có quyền thực hiện thao tác này (Yêu cầu: {min_role.value})."
                )
                if update.callback_query:
                    await update.callback_query.answer(denial_alert, show_alert=True)
                elif update.effective_message:
                    await update.effective_message.reply_text(
                        f"⛔ <b>Từ chối truy cập</b>\n"
                        f"Bạn không có quyền thực hiện thao tác này.\n"
                        f"Yêu cầu thẩm quyền tối thiểu: <b>{min_role.value}</b>.",
                        parse_mode="HTML",
                    )
                return None

            return await func(update, context, *args, **kwargs)

        return wrapper

    return decorator


async def whitelist_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Security gate running at group -1.

    Allows whitelisted users to pass through.
    Politely rejects strangers with their Telegram User ID and raises
    ApplicationHandlerStop to halt execution before any handlers in group 0.
    """
    user = update.effective_user
    if user is None:
        raise ApplicationHandlerStop()

    whitelist: set[int] = context.bot_data.get("whitelist_user_ids", set())
    if user.id not in whitelist:
        if update.callback_query:
            await update.callback_query.answer(
                f"⛔ Bạn không có quyền truy cập bot này (ID: {user.id})",
                show_alert=True,
            )

        if update.effective_message:
            await update.effective_message.reply_text(
                f"⛔ Bạn không có quyền truy cập bot này.\n"
                f"Telegram User ID của bạn: `{user.id}`\n"
                f"Vui lòng gửi mã này cho quản trị viên để được cấp quyền.",
                parse_mode="Markdown",
            )

        raise ApplicationHandlerStop()

    # Enforce maintenance mode right after whitelist check
    await maintenance_gate(update, context)


async def maintenance_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maintenance mode gate running at group -1 right after whitelist_gate.

    When maintenance mode is active:
    - SUPER_ADMIN users bypass and can use the bot normally.
    - Other users (ADMIN, STAFF, etc.) are notified that bot is in maintenance mode,
      and ApplicationHandlerStop is raised to halt execution.
    """
    is_maintenance: bool = context.bot_data.get("maintenance_mode", False)
    if not is_maintenance:
        return

    user = update.effective_user
    if user is None:
        raise ApplicationHandlerStop()

    user_role = get_user_role(context, user.id)
    if user_role == UserRole.SUPER_ADMIN:
        return

    # Non-super-admin blocked during maintenance
    maint_text = (
        "🚧 <b>Hệ thống đang bảo trì</b>\n"
        "Hiện tại bot đang tạm dừng để bảo trì hệ thống. Vui lòng quay lại sau!"
    )
    if update.callback_query:
        await update.callback_query.answer(
            "🚧 Bot đang tạm dừng để bảo trì. Vui lòng quay lại sau!",
            show_alert=True,
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            maint_text,
            parse_mode="HTML",
        )

    raise ApplicationHandlerStop()
