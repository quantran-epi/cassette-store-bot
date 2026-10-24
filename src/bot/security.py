from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes


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
