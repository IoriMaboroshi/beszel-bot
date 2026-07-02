"""Beszel Telegram Bot - Interactive server monitoring."""
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)
from dotenv import load_dotenv

from beszel_api import BeszelAPI
from formatter import (
    format_overview,
    format_system_detail,
    format_system_short,
    format_alerts,
    format_top,
    bar,
    uptime_str,
)

load_dotenv()

# Config
BOT_TOKEN = os.environ["BOT_TOKEN"]
BESZEL_URL = os.environ.get("BESZEL_URL", "")
BESZEL_USER = os.environ.get("BESZEL_USER", "")
BESZEL_PASS = os.environ.get("BESZEL_PASS", "")
ALLOWED_USERS = os.environ.get("ALLOWED_USERS", "").split(",")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("beszel-bot")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
api = BeszelAPI(BESZEL_URL, BESZEL_USER, BESZEL_PASS)


def check_access(user_id: int) -> bool:
    if not ALLOWED_USERS or ALLOWED_USERS == [""]:
        return True
    return str(user_id) in ALLOWED_USERS


# ── Commands ─────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    if not check_access(msg.from_user.id):
        return
    await msg.answer(
        "🖥 <b>Beszel Monitor Bot</b>\n\n"
        "服务器集群监控机器人\n"
        "使用 /help 查看所有命令",
        parse_mode="HTML",
    )


@dp.message(Command("help"))
async def cmd_help(msg: Message):
    if not check_access(msg.from_user.id):
        return
    text = (
        "📋 <b>命令列表</b>\n\n"
        "/all — 所有服务器总览\n"
        "/status <code>名称</code> — 服务器详情\n"
        "/top cpu — CPU 使用排行\n"
        "/top mem — 内存使用排行\n"
        "/top disk — 磁盘使用排行\n"
        "/alerts — 最近告警\n"
        "/refresh — 刷新数据"
    )
    await msg.answer(text, parse_mode="HTML")


@dp.message(Command("all"))
async def cmd_all(msg: Message):
    if not check_access(msg.from_user.id):
        return
    msg_obj = await msg.answer("⏳ 加载中...")
    try:
        systems = await api.get_systems()
        text = format_overview(systems)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔄 刷新", callback_data="refresh_all"),
                    InlineKeyboardButton(text="📊 Top CPU", callback_data="top_cpu"),
                ],
                [
                    InlineKeyboardButton(text="🧠 Top RAM", callback_data="top_mem"),
                    InlineKeyboardButton(text="💾 Top Disk", callback_data="top_disk"),
                ],
            ]
        )
        await msg_obj.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        log.error(f"Error in /all: {e}")
        await msg_obj.edit_text(f"❌ 获取数据失败: {e}")


@dp.message(Command("status"))
async def cmd_status(msg: Message):
    if not check_access(msg.from_user.id):
        return
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("用法: /status <code>服务器名称</code>\n\n例如: /status aliBJ1", parse_mode="HTML")
        return

    target = args[1].strip().lower()
    msg_obj = await msg.answer("⏳ 加载中...")
    try:
        systems = await api.get_systems()
        matched = [s for s in systems if target in s.get("name", "").lower()]

        if not matched:
            await msg_obj.edit_text(f"❌ 找不到服务器: <code>{target}</code>\n可用: {', '.join(s['name'] for s in systems)}", parse_mode="HTML")
            return

        sys = matched[0]
        text = format_system_detail(sys)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 返回总览", callback_data="refresh_all")],
            ]
        )
        await msg_obj.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        log.error(f"Error in /status: {e}")
        await msg_obj.edit_text(f"❌ 获取数据失败: {e}")


@dp.message(Command("top"))
async def cmd_top(msg: Message):
    if not check_access(msg.from_user.id):
        return
    args = msg.text.split(maxsplit=1)
    metric = args[1].strip().lower() if len(args) > 1 else "cpu"

    if metric not in ("cpu", "mem", "disk"):
        await msg.answer("用法: /top <code>cpu|mem|disk</code>", parse_mode="HTML")
        return

    msg_obj = await msg.answer("⏳ 加载中...")
    try:
        systems = await api.get_systems()
        label_map = {"cpu": "CPU", "mem": "Memory", "disk": "Disk"}
        text = format_top(systems, metric, label_map[metric])
        await msg_obj.edit_text(text, parse_mode="HTML")
    except Exception as e:
        log.error(f"Error in /top: {e}")
        await msg_obj.edit_text(f"❌ 获取数据失败: {e}")


@dp.message(Command("alerts"))
async def cmd_alerts(msg: Message):
    if not check_access(msg.from_user.id):
        return
    msg_obj = await msg.answer("⏳ 加载中...")
    try:
        data = await api.get_alerts()
        alerts = data.get("items", [])
        text = format_alerts(alerts)
        await msg_obj.edit_text(text, parse_mode="HTML")
    except Exception as e:
        log.error(f"Error in /alerts: {e}")
        await msg_obj.edit_text(f"❌ 获取告警失败: {e}")


@dp.message(Command("refresh"))
async def cmd_refresh(msg: Message):
    if not check_access(msg.from_user.id):
        return
    # Reuse /all logic
    msg.text = "/all"
    await cmd_all(msg)


# ── Callback handlers ────────────────────────────────────

@dp.callback_query(F.data == "refresh_all")
async def cb_refresh_all(cb: CallbackQuery):
    try:
        systems = await api.get_systems()
        text = format_overview(systems)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔄 刷新", callback_data="refresh_all"),
                    InlineKeyboardButton(text="📊 Top CPU", callback_data="top_cpu"),
                ],
                [
                    InlineKeyboardButton(text="🧠 Top RAM", callback_data="top_mem"),
                    InlineKeyboardButton(text="💾 Top Disk", callback_data="top_disk"),
                ],
            ]
        )
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        await cb.message.edit_text(f"❌ 刷新失败: {e}")
    await cb.answer()


@dp.callback_query(F.data.startswith("top_"))
async def cb_top(cb: CallbackQuery):
    metric = cb.data.replace("top_", "")
    try:
        systems = await api.get_systems()
        label_map = {"cpu": "CPU", "mem": "Memory", "disk": "Disk"}
        text = format_top(systems, metric, label_map.get(metric, metric))
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 返回总览", callback_data="refresh_all")],
            ]
        )
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        await cb.message.edit_text(f"❌ 获取失败: {e}")
    await cb.answer()


# ── Bot commands registration ────────────────────────────

async def set_bot_commands():
    commands = [
        BotCommand(command="all", description="所有服务器总览"),
        BotCommand(command="status", description="服务器详情"),
        BotCommand(command="top", description="资源使用排行"),
        BotCommand(command="alerts", description="最近告警"),
        BotCommand(command="refresh", description="刷新数据"),
        BotCommand(command="help", description="帮助"),
    ]
    await bot.set_my_commands(commands)
    log.info("Bot commands registered")


# ── Main ─────────────────────────────────────────────────

async def main():
    await set_bot_commands()
    log.info("Beszel Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
