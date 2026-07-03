"""Message formatting for Telegram bot."""
from datetime import datetime, timezone
from typing import Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
from io import BytesIO

# Configure Chinese font support
_CJK_FONT = None
for _fname in fm.findSystemFonts():
    if 'NotoSansCJK-Regular' in _fname or 'NotoSansSC-Regular' in _fname:
        _CJK_FONT = fm.FontProperties(fname=_fname)
        break
# Fallback: search by name
if _CJK_FONT is None:
    for f in fm.fontManager.ttflist:
        if f.name == 'Noto Sans CJK SC':
            _CJK_FONT = fm.FontProperties(fname=f.fname)
            break
# Set global rcParams as well
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'SimHei', 'WenQuanYi Micro Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


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


def fmt_bytes_total(kb: float) -> str:
    """Format KB (total) to human readable."""
    if kb < 1024:
        return f"{kb:.1f} KB"
    if kb < 1048576:
        return f"{kb / 1024:.2f} MB"
    return f"{kb / 1048576:.2f} GB"


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


def format_containers(containers: list[dict], system_name: str = None) -> str:
    """Format container list."""
    if not containers:
        return "没有找到容器"

    title = f"🐳 Docker 容器"
    if system_name:
        title += f" ({system_name})"
    title += f"  共 {len(containers)} 个"

    lines = [title, ""]

    sorted_ct = sorted(containers, key=lambda c: c.get("cpu", 0), reverse=True)

    for c in sorted_ct:
        name = c.get("name", "?")
        status = c.get("status", "?")
        cpu = c.get("cpu", 0)
        mem = c.get("memory", 0)
        image = c.get("image", "?")
        ports = c.get("ports", "")

        if "Up" in status:
            emoji = "🟢"
        elif "Exited" in status:
            emoji = "🔴"
        else:
            emoji = "🟡"

        lines.append(f"{emoji} <b>{name}</b>")
        lines.append(f"  Image: <code>{image}</code>")
        lines.append(f"  CPU  {bar(cpu)} {cpu:.1f}%")
        lines.append(f"  RAM  {mem:.1f} MB")
        if ports:
            lines.append(f"  Ports: {ports}")
        lines.append("")

    return "\n".join(lines).strip()


def format_containers_top(containers: list[dict], metric: str, label: str) -> str:
    """Format top containers by metric."""
    if not containers:
        return "没有找到容器"

    if metric == "cpu":
        key = "cpu"
        unit = "%"
    elif metric == "mem":
        key = "memory"
        unit = "MB"
    else:
        return "不支持的指标"

    sorted_ct = sorted(containers, key=lambda c: c.get(key, 0), reverse=True)

    lines = [f"🐳 <b>Top {label} 容器</b>", ""]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, c in enumerate(sorted_ct[:10], 1):
        name = c.get("name", "?")
        val = c.get(key, 0)
        medal = medals[i-1] if i <= 5 else f"{i}."
        lines.append(f"{medal} <b>{name}</b>  {val:.1f}{unit}  {bar(val, 8)}")

    return "\n".join(lines)


# ── Chart generation ──────────────────────────────────────

def generate_chart(
    timestamps: list,
    values: list,
    title: str,
    ylabel: str,
    color: str = "#00d4ff",
    fill: bool = True,
    figsize: tuple = (10, 4),
) -> BytesIO:
    """Generate a dark-themed trend chart as PNG BytesIO buffer.

    Args:
        timestamps: list of datetime objects
        values: list of numeric values
        title: chart title
        ylabel: Y-axis label
        color: line color (hex)
        fill: whether to fill area under curve
        figsize: figure size (width, height)
    """
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#16213e')

    ax.plot(timestamps, values, color=color, linewidth=1.5, marker='.', markersize=3)
    if fill:
        ax.fill_between(timestamps, values, alpha=0.3, color=color)

    title_kwargs = {'color': 'white', 'fontsize': 14, 'fontweight': 'bold'}
    ylabel_kwargs = {'color': 'white', 'fontsize': 11}
    if _CJK_FONT:
        title_kwargs['fontproperties'] = _CJK_FONT
        ylabel_kwargs['fontproperties'] = _CJK_FONT
    ax.set_title(title, **title_kwargs)
    ax.set_ylabel(ylabel, **ylabel_kwargs)

    # Format x-axis time
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=30)

    ax.tick_params(colors='white', labelsize=9)
    ax.grid(True, alpha=0.3, color='#ffffff')

    # Style spines
    for spine in ax.spines.values():
        spine.set_color('#333355')

    # Add min/max annotations
    annot_kwargs = {'fontsize': 9, 'ha': 'center', 'fontweight': 'bold'}
    if _CJK_FONT:
        annot_kwargs['fontproperties'] = _CJK_FONT
    if values:
        max_val = max(values)
        min_val = min(values)
        max_idx = values.index(max_val)
        min_idx = values.index(min_val)
        ax.annotate(f'{max_val:.1f}', xy=(timestamps[max_idx], max_val),
                    xytext=(0, 10), textcoords='offset points',
                    color='#ff6b6b', **annot_kwargs)
        ax.annotate(f'{min_val:.1f}', xy=(timestamps[min_idx], min_val),
                    xytext=(0, -15), textcoords='offset points',
                    color='#51cf66', **annot_kwargs)

    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    return buf


def extract_container_metric(
    stats_data: list[dict],
    container_name: str,
    metric: str = "cpu",
    system_id: str = None,
) -> tuple[list, list]:
    """Extract timestamp/value pairs for a specific container from stats data.

    Args:
        stats_data: list of container_stats records
        container_name: container name to filter
        metric: "cpu" or "mem"
        system_id: optional system ID to filter

    Returns:
        (timestamps, values) tuple of lists
    """
    timestamps = []
    values = []

    for record in stats_data:
        if system_id and record.get("system") != system_id:
            continue

        created = record.get("created", "")
        if not created:
            continue

        try:
            ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        stats = record.get("stats", [])
        for ct in stats:
            if ct.get("n") == container_name:
                if metric == "cpu":
                    val = ct.get("c", 0)
                elif metric == "mem":
                    # Memory in MB from stats
                    val = ct.get("m", 0)
                else:
                    val = ct.get("c", 0)
                timestamps.append(ts)
                values.append(val)
                break

    # Sort by time ascending
    combined = sorted(zip(timestamps, values), key=lambda x: x[0])
    if combined:
        timestamps, values = zip(*combined)
        return list(timestamps), list(values)
    return [], []


def extract_server_cpu_from_stats(stats_data: list[dict], system_id: str) -> tuple[list, list]:
    """Aggregate all container CPUs for a server at each timestamp."""
    timestamps = []
    values = []

    for record in stats_data:
        if system_id and record.get("system") != system_id:
            continue

        created = record.get("created", "")
        if not created:
            continue

        try:
            ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        stats = record.get("stats", [])
        total_cpu = sum(ct.get("c", 0) for ct in stats)
        timestamps.append(ts)
        values.append(total_cpu)

    combined = sorted(zip(timestamps, values), key=lambda x: x[0])
    if combined:
        timestamps, values = zip(*combined)
        return list(timestamps), list(values)
    return [], []


# ── Container detailed format ─────────────────────────────

def format_container_detail_list(stats_data: list[dict], system_id: str, system_name: str) -> str:
    """Format detailed container ranking from latest stats record.

    Shows CPU, memory, network IO for each container, sorted by CPU.
    """
    # Get the most recent record for this system
    latest = None
    for record in stats_data:
        if record.get("system") == system_id:
            latest = record
            break

    if not latest:
        return f"❌ 没有找到 {system_name} 的容器数据"

    stats = latest.get("stats", [])
    if not stats:
        return f"📭 {system_name} 没有运行中的容器"

    # Sort by CPU descending
    sorted_stats = sorted(stats, key=lambda c: c.get("c", 0), reverse=True)

    lines = [
        f"🐳 <b>{system_name} 容器详情</b>",
        f"  数据时间: {latest.get('created', '?')[:19].replace('T', ' ')}",
        f"  容器数: {len(sorted_stats)}",
        "",
    ]

    medals = ["🥇", "🥈", "🥉"]
    for i, c in enumerate(sorted_stats):
        name = c.get("n", "?")
        cpu = c.get("c", 0)
        mem = c.get("m", 0)
        net_in = c.get("b", [0, 0])[0] if isinstance(c.get("b"), list) and len(c.get("b", [])) >= 2 else 0
        net_out = c.get("b", [0, 0])[1] if isinstance(c.get("b"), list) and len(c.get("b", [])) >= 2 else 0

        medal = medals[i] if i < 3 else f"{i+1}."

        # Status indicator
        if cpu > 100:
            cpu_emoji = "🔴"
        elif cpu > 50:
            cpu_emoji = "🟧"
        elif cpu > 10:
            cpu_emoji = "🟡"
        else:
            cpu_emoji = "🟢"

        lines.append(f"{medal} <b>{name}</b>")
        lines.append(f"  {cpu_emoji} CPU {cpu:.1f}%  |  RAM {mem:.1f} MB")
        lines.append(f"  📥 In {fmt_bytes_total(net_in)}  |  📤 Out {fmt_bytes_total(net_out)}")
        lines.append("")

    return "\n".join(lines).strip()


# ── Briefing format ───────────────────────────────────────

def format_briefing(systems: list[dict], container_stats: list[dict], alerts_data: dict) -> str:
    """Generate daily briefing text.

    Args:
        systems: list of system records
        container_stats: latest container stats records
        alerts_data: alerts API response dict (with 'items')
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d %H:%M")
    alerts = alerts_data.get("items", []) if alerts_data else []

    lines = [
        f"📊 <b>每日服务器简报</b> ({date_str})",
        "",
        "🖥 <b>服务器状态</b>",
    ]

    for sys in systems:
        info = sys.get("info") or {}
        name = sys.get("name", "?")
        status = sys.get("status", "?")
        emoji = status_emoji(status)
        cpu = info.get("cpu", 0)
        mem = info.get("mp", 0)
        disk = info.get("dp", 0)
        la = info.get("la", [0, 0, 0])
        uptime = info.get("u", 0)

        lines.append(
            f"  {emoji} {name}: CPU {cpu:.1f}% | RAM {mem:.1f}% | "
            f"Disk {disk:.1f}% | Load {la[0]:.1f} | ⏱{uptime_str(uptime)}"
        )

    # Abnormal containers (CPU > 50% or mem > 1GB)
    abnormal = []
    for record in container_stats:
        stats = record.get("stats", [])
        system_id = record.get("system", "")
        # Find system name
        sys_name = next((s.get("name", "?") for s in systems if s.get("id") == system_id), system_id[:8])
        for ct in stats:
            cpu = ct.get("c", 0)
            mem = ct.get("m", 0)
            if cpu > 50 or mem > 1024:
                abnormal.append({
                    "name": ct.get("n", "?"),
                    "system": sys_name,
                    "cpu": cpu,
                    "mem": mem,
                })

    if abnormal:
        # Deduplicate by (name, system)
        seen = set()
        unique_abnormal = []
        for a in abnormal:
            key = (a["name"], a["system"])
            if key not in seen:
                seen.add(key)
                unique_abnormal.append(a)

        # Sort by CPU descending
        unique_abnormal.sort(key=lambda x: x["cpu"], reverse=True)

        lines.append("")
        lines.append("🐳 <b>异常容器</b>（CPU>50% 或内存>1GB）")
        for a in unique_abnormal[:10]:
            warn = "⚠️" if a["cpu"] > 100 else ""
            lines.append(
                f"  • {a['name']} ({a['system']}): CPU {a['cpu']:.1f}% | RAM {a['mem']:.0f}MB {warn}"
            )
    else:
        lines.append("")
        lines.append("🐳 <b>容器状态</b>")
        lines.append("  ✅ 所有容器运行正常")

    # Alert summary
    lines.append("")
    lines.append(f"⚠️ <b>告警摘要</b>")
    if alerts:
        lines.append(f"  最近告警: {len(alerts)} 条")
        for alert in alerts[:3]:
            text = alert.get("text", "")
            created = alert.get("created", "")[:16].replace("T", " ")
            lines.append(f"  • <code>{created}</code> {text[:60]}")
    else:
        lines.append("  ✅ 没有告警")

    return "\n".join(lines)
