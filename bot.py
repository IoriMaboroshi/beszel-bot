"""Beszel Telegram Bot - Interactive server monitoring."""
import asyncio
import logging
import os
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from beszel_api import BeszelAPI
from formatter import (
    format_overview,
    format_system_detail,
    format_system_short,
    format_alerts,
    format_top,
    format_containers,
    format_containers_top,
    format_container_detail_list,
    format_briefing,
    generate_chart,
    extract_container_metric,
    extract_server_cpu_from_stats,
    bar,
    uptime_str,
)

load_dotenv()

# Config
BOT_TOKEN = os.environ["BOT_TOKEN"]
BESZEL_URL = os.environ.get("BESZEL_URL", "http://10.126.126.110:8090")
BESZEL_USER = os.environ.get("BESZEL_USER", "admin@beszel.local")
BESZEL_PASS = os.environ.get("BESZEL_PASS", "BeszelAdmin123")
ALLOWED_USERS = os.environ.get("ALLOWED_USERS", "").split(",")
BRIEFING_CHAT_ID = os.environ.get("BRIEFING_CHAT_ID", "")

# System name -> ID mapping (for quick lookup)
SYSTEM_NAME_MAP = {
    "istoreos": "0obg7n91sync13c",
    "azurehk1": "4onr47wnf12rula",
    "alibj1": "5loa366g5f060rs",
    "aligg1": "7f66xuk2necu38u",
    "dosg1": "89uuz9lg1i8efmt",
    "alibj2": "a3dqt744yl8lzyx",
    "alihk1": "bckuznprksj0ohh",
    "aliwh1": "vdvo5om2si195n7",
    "azurehk2": "wtn6k2lhj4wko0x",
    "aligd1": "zbn6ffvg23qpy71",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("beszel-bot")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
api = BeszelAPI(BESZEL_URL, BESZEL_USER, BESZEL_PASS)
scheduler = AsyncIOScheduler()


def check_access(user_id: int) -> bool:
    if not ALLOWED_USERS or ALLOWED_USERS == [""]:
        return True
    return str(user_id) in ALLOWED_USERS


def resolve_system_id(name: str, systems: list[dict] = None) -> str | None:
    """Resolve a system name to its ID. Tries exact map first, then fuzzy search."""
    key = name.strip().lower()
    # Direct map lookup
    if key in SYSTEM_NAME_MAP:
        return SYSTEM_NAME_MAP[key]
    # Fuzzy search in systems list
    if systems:
        matched = [s for s in systems if key in s.get("name", "").lower()]
        if matched:
            return matched[0]["id"]
    return None




# ── Scheduled briefing ────────────────────────────────────

async def scheduled_briefing():
    """Send daily briefing to configured chat."""
    if not BRIEFING_CHAT_ID:
        log.warning("BRIEFING_CHAT_ID not set, skipping scheduled briefing")
        return

    try:
        log.info("Running scheduled briefing...")

        # 1. Get all systems
        systems = await api.get_systems()

        # 2. Get container stats (try multiple stat types)
        container_stats = []
        for st in ["1m", "10m", "20m"]:
            container_stats = await api.get_container_stats(stat_type=st)
            if container_stats:
                break

        # 3. Get recent alerts
        alerts_data = await api.get_alerts(per_page=20)

        # 4. Format and send briefing
        text = format_briefing(systems, container_stats, alerts_data)
        chat_id = int(BRIEFING_CHAT_ID)
        await bot.send_message(chat_id, text, parse_mode="HTML")
        log.info(f"Daily briefing sent to chat {chat_id}")

    except Exception as e:
        log.error(f"Failed to send scheduled briefing: {e}", exc_info=True)

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
        "/containers — Docker 容器列表\n"
        "/ctop cpu — 容器 CPU 排行\n"
        "/ctop mem — 容器 RAM 排行\n"
        "/chart container cpu <code>容器名</code> [服务器] — 容器CPU趋势图\n"
        "/chart container mem <code>容器名</code> [服务器] — 容器内存趋势图\n"
        "/chart server cpu [服务器] — 服务器CPU聚合趋势图\n"
        "/proc [服务器] — 容器详细排行\n"
        "/briefing — 每日服务器简报\n"
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
    msg.text = "/all"
    await cmd_all(msg)


@dp.message(Command("containers"))
async def cmd_containers(msg: Message):
    if not check_access(msg.from_user.id):
        return
    args = msg.text.split(maxsplit=1)
    target = args[1].strip() if len(args) > 1 else None

    msg_obj = await msg.answer("⏳ 加载中...")
    try:
        if target:
            systems = await api.get_systems()
            matched = [s for s in systems if target.lower() in s.get("name", "").lower()]
            if not matched:
                await msg_obj.edit_text(f"❌ 找不到服务器: {target}")
                return
            system_id = matched[0]["id"]
            system_name = matched[0]["name"]
            containers = await api.get_containers(system_id)
        else:
            containers = await api.get_containers()
            system_name = None

        text = format_containers(containers, system_name)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 刷新", callback_data="refresh_containers"),
                InlineKeyboardButton(text="📊 Top CPU", callback_data="ctop_cpu"),
            ],
            [
                InlineKeyboardButton(text="🧠 Top RAM", callback_data="ctop_mem"),
                InlineKeyboardButton(text="🖥️ 服务器总览", callback_data="refresh_all"),
            ],
        ])
        await msg_obj.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        log.error(f"Error in /containers: {e}")
        await msg_obj.edit_text(f"❌ 获取容器数据失败: {e}")


@dp.message(Command("ctop"))
async def cmd_ctop(msg: Message):
    if not check_access(msg.from_user.id):
        return
    args = msg.text.split(maxsplit=1)
    metric = args[1].strip().lower() if len(args) > 1 else "cpu"

    if metric not in ("cpu", "mem"):
        await msg.answer("用法: /ctop <code>cpu|mem</code>", parse_mode="HTML")
        return

    msg_obj = await msg.answer("⏳ 加载中...")
    try:
        containers = await api.get_containers()
        label_map = {"cpu": "CPU", "mem": "RAM"}
        text = format_containers_top(containers, metric, label_map[metric])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 刷新", callback_data=f"ctop_{metric}"),
                InlineKeyboardButton(text="🐳 容器列表", callback_data="refresh_containers"),
            ],
        ])
        await msg_obj.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        log.error(f"Error in /ctop: {e}")
        await msg_obj.edit_text(f"❌ 获取容器数据失败: {e}")


# ── New commands: /chart, /proc, /briefing ────────────────

@dp.message(Command("chart"))
async def cmd_chart(msg: Message):
    """Generate historical trend chart.

    Usage:
        /chart container cpu <name> [server]
        /chart container mem <name> [server]
        /chart server cpu [server]
    """
    if not check_access(msg.from_user.id):
        return
    args = msg.text.split()
    if len(args) < 3:
        await msg.answer(
            "📈 <b>用法:</b>\n"
            "/chart container cpu <code>容器名</code> [服务器]\n"
            "/chart container mem <code>容器名</code> [服务器]\n"
            "/chart server cpu [服务器]",
            parse_mode="HTML",
        )
        return

    msg_obj = await msg.answer("📈 生成图表中...")

    try:
        target_type = args[1].lower()
        metric = args[2].lower()

        if target_type not in ("container", "server"):
            await msg_obj.edit_text("❌ 类型必须是 <code>container</code> 或 <code>server</code>", parse_mode="HTML")
            return
        if metric not in ("cpu", "mem"):
            await msg_obj.edit_text("❌ 指标必须是 <code>cpu</code> 或 <code>mem</code>", parse_mode="HTML")
            return

        # Parse optional server name and container name
        system_id = None
        system_name = None
        container_name = None

        if target_type == "container":
            if len(args) < 4:
                await msg_obj.edit_text("❌ 用法: /chart container <code>cpu|mem</code> <code>容器名</code> [服务器]", parse_mode="HTML")
                return
            container_name = args[3]
            if len(args) >= 5:
                server_arg = " ".join(args[4:])
                systems = await api.get_systems()
                system_id = resolve_system_id(server_arg, systems)
                if system_id:
                    matched = [s for s in systems if s.get("id") == system_id]
                    system_name = matched[0]["name"] if matched else server_arg
                else:
                    await msg_obj.edit_text(f"❌ 找不到服务器: {server_arg}", parse_mode="HTML")
                    return
        elif target_type == "server":
            if len(args) >= 4:
                server_arg = " ".join(args[3:])
                systems = await api.get_systems()
                system_id = resolve_system_id(server_arg, systems)
                if system_id:
                    matched = [s for s in systems if s.get("id") == system_id]
                    system_name = matched[0]["name"] if matched else server_arg
                else:
                    await msg_obj.edit_text(f"❌ 找不到服务器: {server_arg}", parse_mode="HTML")
                    return

        # Fetch stats data - try 1m first (most granular), fallback to 10m, then 20m
        stats_data = []
        for st in ["1m", "10m", "20m"]:
            stats_data = await api.get_container_stats(system_id=system_id, stat_type=st)
            if stats_data:
                break

        if not stats_data:
            await msg_obj.edit_text("❌ 没有找到历史数据", parse_mode="HTML")
            return

        # Extract data and generate chart
        if target_type == "container":
            timestamps, values = extract_container_metric(stats_data, container_name, metric, system_id)
            if not timestamps:
                await msg_obj.edit_text(
                    f"❌ 没有找到容器 <code>{container_name}</code> 的{metric.upper()}数据",
                    parse_mode="HTML",
                )
                return
            label = system_name or "全部"
            title = f"{container_name} — {metric.upper()} 趋势 ({label})"
            ylabel = "CPU %" if metric == "cpu" else "Memory (MB)"
        else:
            # Server CPU aggregation
            if system_id:
                timestamps, values = extract_server_cpu_from_stats(stats_data, system_id)
            else:
                # Aggregate all servers
                timestamps, values = [], []
                systems = await api.get_systems()
                for sys in systems:
                    ts, vals = extract_server_cpu_from_stats(stats_data, sys["id"])
                    # This is per-server; for all-servers we need a different approach
                    # Let's just show per-system as a comment
                    pass
                # Fallback: aggregate all containers across all systems
                from collections import defaultdict
                ts_map = defaultdict(float)
                for record in stats_data:
                    created = record.get("created", "")
                    if not created:
                        continue
                    try:
                        ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        continue
                    stats = record.get("stats", [])
                    total_cpu = sum(ct.get("c", 0) for ct in stats)
                    ts_map[ts] += total_cpu
                if ts_map:
                    combined = sorted(ts_map.items(), key=lambda x: x[0])
                    timestamps = [c[0] for c in combined]
                    values = [c[1] for c in combined]

            if not timestamps:
                await msg_obj.edit_text("❌ 没有找到服务器CPU数据", parse_mode="HTML")
                return
            label = system_name or "全部服务器"
            title = f"服务器 CPU 聚合趋势 ({label})"
            ylabel = "CPU %"

        # Generate chart image
        chart_buf = generate_chart(timestamps, values, title, ylabel)

        # Send as photo
        photo = BufferedInputFile(chart_buf.read(), filename="chart.png")
        caption = f"📈 {title}\n数据点: {len(values)} | 范围: {timestamps[0].strftime('%H:%M')}-{timestamps[-1].strftime('%H:%M')}"
        await bot.send_photo(msg.chat.id, photo=photo, caption=caption)

        # Delete the loading message
        try:
            await msg_obj.delete()
        except Exception:
            pass

    except Exception as e:
        log.error(f"Error in /chart: {e}")
        await msg_obj.edit_text(f"❌ 生成图表失败: {e}")


@dp.message(Command("proc"))
async def cmd_proc(msg: Message):
    """Container detailed ranking for a server.

    Usage:
        /proc [server_name]
    """
    if not check_access(msg.from_user.id):
        return
    args = msg.text.split(maxsplit=1)
    target = args[1].strip() if len(args) > 1 else None

    msg_obj = await msg.answer("⏳ 加载容器详情...")

    try:
        systems = await api.get_systems()
        target_system = None

        if target:
            matched = [s for s in systems if target.lower() in s.get("name", "").lower()]
            if not matched:
                await msg_obj.edit_text(
                    f"❌ 找不到服务器: <code>{target}</code>\n"
                    f"可用: {', '.join(s['name'] for s in systems)}",
                    parse_mode="HTML",
                )
                return
            target_system = matched[0]

        if target_system:
            # Single server
            system_id = target_system["id"]
            system_name = target_system["name"]
            stats_data = await api.get_container_stats(system_id=system_id, stat_type="1m")
            if not stats_data:
                stats_data = await api.get_container_stats(system_id=system_id, stat_type="10m")

            text = format_container_detail_list(stats_data, system_id, system_name)
            await msg_obj.edit_text(text, parse_mode="HTML")
        else:
            # All servers - show each one
            all_texts = []
            for sys in systems:
                system_id = sys["id"]
                system_name = sys["name"]
                stats_data = await api.get_container_stats(system_id=system_id, stat_type="1m")
                if not stats_data:
                    stats_data = await api.get_container_stats(system_id=system_id, stat_type="10m")

                # Only include servers that have container data
                if stats_data:
                    # Get latest record
                    for record in stats_data:
                        if record.get("system") == system_id:
                            if record.get("stats"):
                                all_texts.append(
                                    format_container_detail_list(stats_data, system_id, system_name)
                                )
                            break

            if all_texts:
                combined = "\n\n".join(all_texts)
                # Telegram message limit is 4096 chars
                if len(combined) > 4000:
                    # Send in chunks
                    await msg_obj.edit_text(all_texts[0], parse_mode="HTML")
                    for t in all_texts[1:]:
                        await msg.answer(t, parse_mode="HTML")
                else:
                    await msg_obj.edit_text(combined, parse_mode="HTML")
            else:
                await msg_obj.edit_text("📭 没有找到容器数据", parse_mode="HTML")

    except Exception as e:
        log.error(f"Error in /proc: {e}")
        await msg_obj.edit_text(f"❌ 获取容器详情失败: {e}")


@dp.message(Command("briefing"))
async def cmd_briefing(msg: Message):
    """Generate daily server briefing."""
    if not check_access(msg.from_user.id):
        return
    msg_obj = await msg.answer("📊 生成简报...")

    try:
        # 1. Get all systems
        systems = await api.get_systems()

        # 2. Get container stats (try multiple stat types)
        container_stats = []
        for st in ["1m", "10m", "20m"]:
            container_stats = await api.get_container_stats(stat_type=st)
            if container_stats:
                break

        # 3. Get recent alerts
        alerts_data = await api.get_alerts(per_page=20)

        # 4. Format briefing
        text = format_briefing(systems, container_stats, alerts_data)
        await msg_obj.edit_text(text, parse_mode="HTML")

    except Exception as e:
        log.error(f"Error in /briefing: {e}")
        await msg_obj.edit_text(f"❌ 生成简报失败: {e}")


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


@dp.callback_query(F.data == "refresh_containers")
async def cb_refresh_containers(cb: CallbackQuery):
    try:
        containers = await api.get_containers()
        text = format_containers(containers)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 刷新", callback_data="refresh_containers"),
                InlineKeyboardButton(text="📊 Top CPU", callback_data="ctop_cpu"),
            ],
            [
                InlineKeyboardButton(text="🧠 Top RAM", callback_data="ctop_mem"),
                InlineKeyboardButton(text="🖥️ 服务器总览", callback_data="refresh_all"),
            ],
        ])
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        await cb.message.edit_text(f"❌ 刷新失败: {e}")
    await cb.answer()


@dp.callback_query(F.data.startswith("ctop_"))
async def cb_ctop(cb: CallbackQuery):
    metric = cb.data.replace("ctop_", "")
    try:
        containers = await api.get_containers()
        label_map = {"cpu": "CPU", "mem": "RAM"}
        text = format_containers_top(containers, metric, label_map.get(metric, metric))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 刷新", callback_data=f"ctop_{metric}"),
                InlineKeyboardButton(text="🐳 容器列表", callback_data="refresh_containers"),
            ],
        ])
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        await cb.message.edit_text(f"❌ 刷新失败: {e}")
    await cb.answer()


# ── Bot commands registration ────────────────────────────

async def set_bot_commands():
    commands = [
        BotCommand(command="all", description="所有服务器总览"),
        BotCommand(command="status", description="服务器详情"),
        BotCommand(command="top", description="资源使用排行"),
        BotCommand(command="containers", description="Docker容器列表"),
        BotCommand(command="ctop", description="容器资源排行"),
        BotCommand(command="chart", description="历史趋势图"),
        BotCommand(command="proc", description="容器详细排行"),
        BotCommand(command="briefing", description="每日服务器简报"),
        BotCommand(command="alerts", description="最近告警"),
        BotCommand(command="refresh", description="刷新数据"),
        BotCommand(command="help", description="帮助"),
    ]
    await bot.set_my_commands(commands)
    log.info("Bot commands registered")


# ── Main ─────────────────────────────────────────────────

async def main():
    # Register scheduled jobs
    scheduler.add_job(
        scheduled_briefing,
        CronTrigger(hour=8, minute=0, timezone="Asia/Shanghai"),
        id="daily_briefing",
        name="每日简报",
        replace_existing=True,
    )
    scheduler.start()
    if BRIEFING_CHAT_ID:
        log.info(f"Scheduler started - daily briefing at 08:00 CST -> chat {BRIEFING_CHAT_ID}")
    else:
        log.warning("Scheduler started but BRIEFING_CHAT_ID is not set!")

    await set_bot_commands()
    log.info("Beszel Bot started")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
