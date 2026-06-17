import logging

from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
from states import UserFSM
from config import REFERRAL_BONUS_THRESHOLD

router = Router(name="user")


async def is_subscribed(bot, channel_id: str, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logging.warning(f"Не удалось проверить подписку для {user_id}: {e}")
        return False


# ─── /start (+ реферальные deep links) ────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext, command: CommandObject):
    await state.clear()

    referrer_id = None
    if command.args and command.args.startswith("ref"):
        try:
            referrer_id = int(command.args.replace("ref", ""))
        except ValueError:
            referrer_id = None

    is_new = db.register_user(message.from_user.id, referrer_id)
    db.track("start", message.from_user.id)

    text = "👋 Привет!\n\nЧтобы получить доступ к боту — подпишись на наш канал и нажми «Проверить подписку»."
    if is_new and referrer_id:
        text = "👋 Привет! Ты пришёл по приглашению друга 🤝\n\n" + text

    await message.answer(text, reply_markup=kb.kb_page1())


# ─── Проверка подписки ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: types.CallbackQuery):
    db.track("check_sub", callback.from_user.id)

    from config import CHANNEL_ID
    if await is_subscribed(callback.bot, CHANNEL_ID, callback.from_user.id):
        # Засчитываем переход на страницу 2 как факт конверсии
        db.track("referral_join", callback.from_user.id)
        await callback.message.edit_text(
            "✅ Подписка подтверждена!\n\nДобро пожаловать. Выбери действие:",
            reply_markup=kb.kb_page2()
        )
    else:
        await callback.answer(
            "❌ Ты ещё не подписан на канал.\nПодпишись и попробуй снова!",
            show_alert=True
        )


@router.callback_query(F.data == "back_to_page1")
async def cb_back_page1(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👋 Привет!\n\nЧтобы получить доступ к боту — подпишись на наш канал и нажми «Проверить подписку».",
        reply_markup=kb.kb_page1()
    )


@router.callback_query(F.data == "back_to_page2")
async def cb_back_page2(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "✅ Главное меню:",
        reply_markup=kb.kb_page2()
    )


# ─── Ввод ключа ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "enter_key")
async def cb_enter_key(callback: types.CallbackQuery, state: FSMContext):
    db.track("enter_key", callback.from_user.id)

    from config import CHANNEL_ID
    if not await is_subscribed(callback.bot, CHANNEL_ID, callback.from_user.id):
        await callback.answer("❌ Сначала подпишись на канал!", show_alert=True)
        return

    await state.set_state(UserFSM.waiting_key)
    await callback.message.answer("🔑 Введи 5-значный код:", reply_markup=kb.kb_cancel_key())
    await callback.answer()


@router.callback_query(F.data == "cancel_key")
async def cb_cancel_key(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=kb.kb_page2())


@router.message(UserFSM.waiting_key)
async def process_key(message: types.Message, state: FSMContext):
    code = message.text.strip() if message.text else ""
    entry = db.get_code(code)

    if not entry:
        await message.answer("❌ Неверный код. Попробуй ещё раз:", reply_markup=kb.kb_cancel_key())
        return

    ctype = entry["type"]
    content = entry["content"]
    caption = entry.get("caption", "") or f"Код: {code}"

    await state.clear()

    if ctype in ("text", "link"):
        await message.answer(f"✅ *Код {code}:*\n\n{content}", parse_mode="Markdown")
    elif ctype == "photo":
        await message.answer_photo(content, caption=caption)
    elif ctype == "video":
        await message.answer_video(content, caption=caption)
    elif ctype == "file":
        await message.answer_document(content, caption=caption)

    await message.answer("Главное меню:", reply_markup=kb.kb_page2())


# ─── Реферальная программа ─────────────────────────────────────────────────────

@router.callback_query(F.data == "referral_info")
async def cb_referral_info(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    count = db.get_referral_count(user_id)

    remaining = max(0, REFERRAL_BONUS_THRESHOLD - count)
    if remaining == 0:
        bonus_text = "🎉 Ты выполнил условие для бонуса! Напиши нам, чтобы получить награду."
    else:
        bonus_text = f"Пригласи ещё *{remaining}* друзей, чтобы получить бонус!"

    text = (
        "🤝 *Реферальная программа*\n\n"
        f"Твоя ссылка:\n`{ref_link}`\n\n"
        f"Приглашено друзей: *{count}*\n"
        f"{bonus_text}"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.kb_back_to_page2())
