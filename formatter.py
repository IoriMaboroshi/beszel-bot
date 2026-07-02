"""Message formatting for Telegram bot."""
from typing import Optional


def bar(percent: float, length: int = 10) -> str:
    """Create a visual progress bar."""
    filled = round(percent / 100 * length)
    empty = length - filled
    if percent >= 90:
        color = "🟥"
    elif percent >= 70:
        color = "🟧"
    else:
        color = "🟩"
    return color * filled + "⬜" * empty


def uptime_str(seconds: int) -> str:
    """Convert seconds to human readable uptime."""
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    if seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    return f"{d}d {h}h"


def fmt_bytes(kb: float) -> str:
    """Format KB to human readable."""
    if kb < 1024:
        return f"{kb:.1f} KB/s"
    if kb < 1048576:
        return f"{kb / 1024:.2f} MB/s"
    return f"{kb / 1048576:.2f} GB/s"


def status_emoji(status: str) -> str:
    return "🟢" if status == "up" else "🔴"


def format_system_short(sys: dict) -> str:
    """Format a single system for overview."""
    info = sys.get("info") or {}
    name = sys.get("name", "?")
    status = sys.get("status", "?")

    cpu = info.get("cpu", 0)
    mem = info.get("mp", 0)
    disk = info.get("dp", 0)
    uptime = info.get("u", 0)
    la = info.get("la", [0, 0, 0])
    services = info.get("sv", None)

    lines = [
        f"{status_emoji(status)} <b>{name}</b>",
        f"  CPU  {bar(cpu)} {cpu:.1f}%",
        f"  RAM  {bar(mem)} {mem:.1f}%",
        f"  Disk {bar(disk)} {disk:.1f}%",
        f"  Load {la[0]:.2f} {la[1]:.2f} {la[2]:.2f}",
        f"  ⏱ {uptime_str(uptime)}",
    ]
    if services:
        total, failed = services
        svc_str = f"  📦 {total} services"
        if failed > 0:
            svc_str += f"  ⚠️ {failed} failed"
        lines.append(svc_str)

    return "\n".join(lines)


def format_system_detail(sys: dict) -> str:
    """Format detailed system info."""
    info = sys.get("info") or {}
    name = sys.get("name", "?")
    status = sys.get("status", "?")
    host = sys.get("host", "?")
    version = info.get("v", "?")

    cpu = info.get("cpu", 0)
    mem = info.get("mp", 0)
    disk = info.get("dp", 0)
    uptime = info.get("u", 0)
    la = info.get("la", [0, 0, 0])
    bw = info.get("bb", 0)
    cores = info.get("ct", "?")
    services = info.get("sv", None)

    lines = [
        f"{status_emoji(status)} <b>{name}</b>  <code>{host}</code>",
        "",
        f"<b>CPU</b>  {cpu:.1f}%  {bar(cpu, 12)}",
        f"  Cores: {cores}  Load: {la[0]:.2f} / {la[1]:.2f} / {la[2]:.2f}",
        "",
        f"<b>Memory</b>  {mem:.1f}%  {bar(mem, 12)}",
        "",
        f"<b>Disk</b>  {disk:.1f}%  {bar(disk, 12)}",
        "",
        f"<b>Network</b>  {fmt_bytes(bw)}",
        "",
        f"<b>Uptime</b>  {uptime_str(uptime)}",
        f"<b>Agent</b>  v{version}",
    ]
    if services:
        total, failed = services
        svc_status = f"✅ {total}" if failed == 0 else f"⚠️ {total} ({failed} failed)"
        lines.append(f"<b>Services</b>  {svc_status}")

    return "\n".join(lines)


def format_overview(systems: list[dict]) -> str:
    """Format all systems overview."""
    total = len(systems)
    up = sum(1 for s in systems if s.get("status") == "up")
    down = total - up

    lines = [
        f"🖥 <b>Beszel Cluster</b>  {up}/{total} online",
        "",
    ]

    # Sort by CPU usage descending
    sorted_sys = sorted(systems, key=lambda s: (s.get("info") or {}).get("cpu", 0), reverse=True)

    for sys in sorted_sys:
        lines.append(format_system_short(sys))
        lines.append("")

    return "\n".join(lines).strip()


def format_alerts(alerts: list[dict]) -> str:
    """Format alert history."""
    if not alerts:
        return "✅ 没有告警记录"

    lines = [f"🔔 <b>最近告警</b> ({len(alerts)} 条)", ""]
    for alert in alerts[:10]:
        created = alert.get("created", "")[:19].replace("T", " ")
        text = alert.get("text", "")
        lines.append(f"• <code>{created}</code>")
        lines.append(f"  {text}")
        lines.append("")

    return "\n".join(lines).strip()


def format_top(systems: list[dict], metric: str, label: str) -> str:
    """Format top consumers."""
    key_map = {"cpu": "cpu", "mem": "mp", "disk": "dp"}
    info_key = key_map.get(metric, metric)

    sorted_sys = sorted(
        systems,
        key=lambda s: (s.get("info") or {}).get(info_key, 0),
        reverse=True,
    )

    lines = [f"📊 <b>Top {label}</b>", ""]
    for i, sys in enumerate(sorted_sys[:5], 1):
        info = sys.get("info") or {}
        val = info.get(info_key, 0)
        name = sys.get("name", "?")
        medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i - 1] if i <= 5 else f"{i}."
        lines.append(f"{medal} <b>{name}</b>  {val:.1f}%  {bar(val, 8)}")

    return "\n".join(lines)
