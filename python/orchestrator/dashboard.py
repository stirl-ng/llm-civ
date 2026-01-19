"""Simple web dashboard for debugging LLM Civ V runs.

Reads from JSONL logs and displays:
- Full LLM conversation (system, user, assistant messages)
- Tool calls with pass/fail status
- Token usage stats

Run: python -m orchestrator.dashboard
Add ?debug=1 to URL to see parse diagnostics
Add ?verbose=1 to see game events and internal messages
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, render_template_string, request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

LOG_FILE = Path(__file__).parent.parent / "logs" / "messages.jsonl"

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Civ V LLM Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <style>
        :root {
            --bg-dark: #0f0f1a;
            --bg-panel: #1a1a2e;
            --bg-panel-alt: #16213e;
            --bg-input: #0d1526;
            --accent-green: #00ff88;
            --accent-blue: #4a9eff;
            --accent-cyan: #00d4ff;
            --accent-yellow: #ffd93d;
            --accent-red: #ff6b6b;
            --accent-purple: #a855f7;
            --accent-orange: #ff9f43;
            --text-primary: #e8e8e8;
            --text-secondary: #888;
            --text-muted: #555;
            --border-subtle: #2a2a4a;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        html, body {
            height: 100%;
            overflow: hidden;
        }

        body {
            font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace;
            background: var(--bg-dark);
            color: var(--text-primary);
            padding: 16px;
            line-height: 1.5;
            display: flex;
            flex-direction: column;
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: var(--bg-dark);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb {
            background: var(--border-subtle);
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }

        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 20px;
            background: linear-gradient(135deg, var(--bg-panel) 0%, var(--bg-panel-alt) 100%);
            border-radius: 12px;
            margin-bottom: 16px;
            flex-shrink: 0;
            border: 1px solid var(--border-subtle);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }

        .header h1 {
            font-size: 16px;
            font-weight: 600;
            letter-spacing: 2px;
            background: linear-gradient(90deg, var(--accent-green), var(--accent-cyan));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .status {
            display: flex;
            gap: 24px;
            font-size: 13px;
            align-items: center;
        }

        .status-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            animation: pulse 2s ease-in-out infinite;
        }
        .dot.green {
            background: var(--accent-green);
            box-shadow: 0 0 10px var(--accent-green);
        }
        .dot.red {
            background: var(--accent-red);
            box-shadow: 0 0 10px var(--accent-red);
            animation: none;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .turn-display {
            font-size: 20px;
            font-weight: 700;
            color: var(--accent-yellow);
        }

        /* Main layout */
        .columns {
            display: grid;
            grid-template-columns: 5fr 3fr;
            gap: 16px;
            flex: 1;
            min-height: 0;
        }

        .right-column {
            display: flex;
            flex-direction: column;
            gap: 16px;
            min-height: 0;
        }

        /* Panels */
        .panel {
            background: var(--bg-panel);
            border-radius: 12px;
            padding: 16px;
            overflow-y: auto;
            min-height: 0;
            border: 1px solid var(--border-subtle);
        }

        .panel.half {
            flex: 1 1 0;
            overflow-y: auto;
        }

        .panel h2 {
            font-size: 11px;
            text-transform: uppercase;
            color: var(--text-secondary);
            margin-bottom: 12px;
            letter-spacing: 1.5px;
            position: sticky;
            top: 0;
            background: var(--bg-panel);
            padding: 4px 0 8px 0;
            z-index: 10;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .panel h2::before {
            content: '';
            display: inline-block;
            width: 3px;
            height: 12px;
            background: var(--accent-cyan);
            border-radius: 2px;
        }

        .count-badge {
            font-size: 10px;
            background: var(--bg-input);
            padding: 2px 8px;
            border-radius: 10px;
            color: var(--text-muted);
            font-weight: normal;
        }

        /* Stats bar */
        .stats-bar {
            display: flex;
            gap: 24px;
            padding: 12px 16px;
            background: var(--bg-input);
            border-radius: 8px;
            margin-bottom: 16px;
            font-size: 12px;
            border: 1px solid var(--border-subtle);
        }

        .stat {
            color: var(--accent-cyan);
            font-weight: 600;
            font-size: 14px;
        }

        .stat-label {
            color: var(--text-muted);
            margin-left: 6px;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Chat messages */
        .chat-message {
            margin-bottom: 12px;
            padding: 12px 14px;
            border-radius: 8px;
            font-size: 12px;
            white-space: pre-wrap;
            word-wrap: break-word;
            border-left: 3px solid transparent;
            transition: transform 0.1s ease, box-shadow 0.1s ease;
        }

        .chat-message:hover {
            transform: translateX(2px);
        }

        .chat-message.system {
            background: linear-gradient(135deg, #252540 0%, #1a1a30 100%);
            border-left-color: var(--text-muted);
            font-size: 11px;
            color: var(--text-secondary);
            max-height: 150px;
            overflow-y: auto;
        }

        .chat-message.user {
            background: linear-gradient(135deg, #1a3a5c 0%, #152a45 100%);
            border-left-color: var(--accent-blue);
        }

        .chat-message.assistant {
            background: linear-gradient(135deg, #1a4a3a 0%, #153a2d 100%);
            border-left-color: var(--accent-green);
        }

        .chat-message .role {
            font-size: 9px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 6px;
            font-weight: 600;
        }

        .chat-message.system .role { color: var(--text-muted); }
        .chat-message.user .role { color: var(--accent-blue); }
        .chat-message.assistant .role { color: var(--accent-green); }

        .chat-message .tokens {
            font-size: 10px;
            color: var(--text-muted);
            font-weight: normal;
            margin-left: 8px;
        }

        .chat-message .content {
            line-height: 1.6;
        }

        /* Turn divider */
        .turn-divider {
            text-align: center;
            padding: 10px 16px;
            color: var(--accent-yellow);
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 2px;
            margin: 16px 0;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }

        .turn-divider::before,
        .turn-divider::after {
            content: '';
            flex: 1;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--accent-yellow), transparent);
        }

        /* Tool calls */
        .tool-call {
            padding: 10px 12px;
            margin-bottom: 8px;
            border-radius: 6px;
            font-size: 11px;
            transition: transform 0.1s ease;
        }

        .tool-call:hover {
            transform: translateX(2px);
        }

        .tool-call.query {
            background: linear-gradient(135deg, #1a2a4a 0%, #152238 100%);
            border-left: 3px solid var(--accent-blue);
        }

        .tool-call.action {
            background: linear-gradient(135deg, #3a2a1a 0%, #2d2215 100%);
            border-left: 3px solid var(--accent-orange);
        }

        .tool-call.error {
            background: linear-gradient(135deg, #3a1a1a 0%, #2d1515 100%);
            border-left: 3px solid var(--accent-red);
        }

        .tool-call-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 6px;
        }

        .tool-call .icon {
            font-size: 12px;
            width: 18px;
            height: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            flex-shrink: 0;
        }

        .tool-call.query .icon {
            background: rgba(74, 158, 255, 0.2);
            color: var(--accent-blue);
        }

        .tool-call.action .icon {
            background: rgba(255, 159, 67, 0.2);
            color: var(--accent-orange);
        }

        .tool-call.error .icon {
            background: rgba(255, 107, 107, 0.2);
            color: var(--accent-red);
        }

        .tool-call .name {
            flex: 1;
            font-weight: 600;
            font-family: inherit;
        }

        .tool-call .turn-badge {
            font-size: 9px;
            background: var(--bg-input);
            padding: 3px 8px;
            border-radius: 4px;
            color: var(--text-muted);
        }

        .tool-call-result {
            font-size: 10px;
            color: var(--text-secondary);
            padding-left: 28px;
            line-height: 1.4;
        }

        .tool-call-result.success {
            color: var(--accent-green);
        }

        .tool-call-result.error {
            color: var(--accent-red);
        }

        /* Notifications */
        .notification {
            padding: 10px 12px;
            margin-bottom: 8px;
            border-radius: 6px;
            font-size: 11px;
            background: linear-gradient(135deg, #1a2a4a 0%, #152238 100%);
            border-left: 3px solid var(--accent-blue);
            transition: transform 0.1s ease;
        }

        .notification:hover {
            transform: translateX(2px);
        }

        .notification .summary {
            font-weight: 600;
            color: var(--accent-blue);
            margin-bottom: 4px;
        }

        .notification .message {
            color: var(--text-secondary);
            font-size: 10px;
            line-height: 1.4;
        }

        .notification .meta {
            font-size: 9px;
            color: var(--text-muted);
            margin-top: 6px;
            display: flex;
            gap: 12px;
        }

        /* Game event */
        .game-event {
            padding: 10px 12px;
            margin-bottom: 8px;
            border-radius: 6px;
            font-size: 11px;
            background: linear-gradient(135deg, #2a1a4a 0%, #1f1538 100%);
            border-left: 3px solid var(--accent-purple);
        }

        .game-event .event-type {
            font-weight: 600;
            color: var(--accent-purple);
            margin-bottom: 4px;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .game-event .event-content {
            color: var(--text-secondary);
            font-size: 10px;
            line-height: 1.4;
        }

        .empty {
            color: var(--text-muted);
            font-style: italic;
            padding: 30px;
            text-align: center;
            font-size: 12px;
        }

        /* Debug panel */
        .debug-panel {
            background: linear-gradient(135deg, #2a1a3a 0%, #1a1528 100%);
            border: 1px solid var(--accent-purple);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            font-size: 11px;
        }

        .debug-panel h3 {
            color: var(--accent-purple);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .debug-panel h3::before {
            content: '🔍';
        }

        .debug-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
        }

        .debug-section {
            background: rgba(0, 0, 0, 0.2);
            padding: 12px;
            border-radius: 6px;
        }

        .debug-section h4 {
            color: var(--text-secondary);
            font-size: 10px;
            text-transform: uppercase;
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }

        .debug-item {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .debug-item:last-child {
            border-bottom: none;
        }

        .debug-key {
            color: var(--text-muted);
        }

        .debug-value {
            color: var(--accent-cyan);
            font-weight: 500;
        }

        .debug-value.warning {
            color: var(--accent-yellow);
        }

        .debug-value.error {
            color: var(--accent-red);
        }

        .debug-toggle {
            position: fixed;
            bottom: 16px;
            right: 16px;
            background: var(--bg-panel);
            border: 1px solid var(--border-subtle);
            color: var(--text-secondary);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 11px;
            text-decoration: none;
            transition: all 0.2s ease;
            z-index: 100;
        }

        .debug-toggle:hover {
            background: var(--bg-panel-alt);
            color: var(--accent-purple);
            border-color: var(--accent-purple);
        }

        /* Unrecognized types list */
        .unrecognized-list {
            font-family: inherit;
            font-size: 10px;
        }

        .unrecognized-item {
            color: var(--accent-yellow);
            padding: 2px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>◈ CIV V LLM DASHBOARD</h1>
        <div class="status">
            <div class="status-item">
                <span class="dot {{ 'green' if connected else 'red' }}"></span>
                {{ 'Connected' if connected else 'Disconnected' }}
            </div>
            <div class="status-item">
                Turn <span class="turn-display">{{ current_turn or '—' }}</span>
            </div>
            <div class="status-item" style="color: var(--text-muted);">
                {{ last_update }}
            </div>
        </div>
    </div>

    {% if debug_mode %}
    <div class="debug-panel">
        <h3>Parse Diagnostics</h3>
        <div class="debug-grid">
            <div class="debug-section">
                <h4>File Stats</h4>
                <div class="debug-item">
                    <span class="debug-key">Log file</span>
                    <span class="debug-value">{{ debug.log_file_name }}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-key">File exists</span>
                    <span class="debug-value {% if not debug.file_exists %}error{% endif %}">{{ 'Yes' if debug.file_exists else 'No' }}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-key">Total lines</span>
                    <span class="debug-value">{{ debug.total_lines }}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-key">Parse errors</span>
                    <span class="debug-value {% if debug.parse_errors > 0 %}error{% endif %}">{{ debug.parse_errors }}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-key">Empty lines</span>
                    <span class="debug-value">{{ debug.empty_lines }}</span>
                </div>
            </div>

            <div class="debug-section">
                <h4>Message Types Found</h4>
                {% for msg_type, count in debug.type_counts.items() %}
                <div class="debug-item">
                    <span class="debug-key">{{ msg_type or '(no type)' }}</span>
                    <span class="debug-value">{{ count }}</span>
                </div>
                {% endfor %}
            </div>

            <div class="debug-section">
                <h4>Display Limits</h4>
                <div class="debug-item">
                    <span class="debug-key">Conversation (max 50)</span>
                    <span class="debug-value {% if debug.conversation_before_limit > 50 %}warning{% endif %}">{{ debug.conversation_before_limit }} → {{ debug.conversation_after_limit }}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-key">Tool calls (max 100)</span>
                    <span class="debug-value {% if debug.tools_before_limit > 100 %}warning{% endif %}">{{ debug.tools_before_limit }} → {{ debug.tools_after_limit }}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-key">Game events (max 50)</span>
                    <span class="debug-value {% if debug.events_before_limit > 50 %}warning{% endif %}">{{ debug.events_before_limit }} → {{ debug.events_after_limit }}</span>
                </div>
                <div class="debug-item">
                    <span class="debug-key">Notifications (max 50)</span>
                    <span class="debug-value {% if debug.notifs_before_limit > 50 %}warning{% endif %}">{{ debug.notifs_before_limit }} → {{ debug.notifs_after_limit }}</span>
                </div>
            </div>

            {% if debug.unrecognized_types %}
            <div class="debug-section">
                <h4>Unrecognized Message Types</h4>
                <div class="unrecognized-list">
                    {% for t in debug.unrecognized_types %}
                    <div class="unrecognized-item">{{ t }}</div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        </div>
    </div>
    {% endif %}

    <div class="columns">
        <div class="panel">
            <h2>LLM Conversation <span class="count-badge">{{ conversation|length }}</span></h2>
            <div class="stats-bar">
                <span><span class="stat">{{ "{:,}".format(total_tokens) }}</span><span class="stat-label">tokens</span></span>
                <span><span class="stat">{{ total_requests }}</span><span class="stat-label">requests</span></span>
                <span><span class="stat">${{ "%.4f"|format(estimated_cost) }}</span><span class="stat-label">est cost</span></span>
            </div>

            {% if conversation %}
                {% for msg in conversation %}
                    {% if msg.type == 'turn_divider' %}
                    <div class="turn-divider">TURN {{ msg.turn }}</div>
                    {% else %}
                    <div class="chat-message {{ msg.role }}">
                        <div class="role">{{ msg.role }}{% if msg.tokens %}<span class="tokens">{{ msg.tokens }} tok</span>{% endif %}</div>
                        <div class="content">{{ msg.content }}</div>
                    </div>
                    {% endif %}
                {% endfor %}
            {% else %}
                <div class="empty">No conversation yet — waiting for LLM activity</div>
            {% endif %}
        </div>

        <div class="right-column">
            <div class="panel half">
                <h2>Tool Activity <span class="count-badge">{{ tool_calls|length }}</span></h2>
                {% if tool_calls %}
                    {% for tool in tool_calls %}
                    <div class="tool-call {{ tool.category }} {{ 'error' if not tool.ok else '' }}">
                        <div class="tool-call-header">
                            <span class="icon">{{ tool.icon }}</span>
                            <span class="name">{{ tool.name }}</span>
                            <span class="turn-badge">T{{ tool.turn }}</span>
                        </div>
                        {% if tool.result_summary %}
                        <div class="tool-call-result {{ 'success' if tool.ok else 'error' }}">{{ tool.result_summary }}</div>
                        {% endif %}
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty">No tool calls yet</div>
                {% endif %}
            </div>

            {% if verbose_mode %}
            <div class="panel half">
                <h2>Game Events <span class="count-badge">{{ game_events|length }}</span></h2>
                {% if game_events %}
                    {% for event in game_events %}
                    <div class="game-event">
                        <div class="event-type">{{ event.event_type }}</div>
                        <div class="event-content">{{ event.content }}</div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty">No game events yet</div>
                {% endif %}
            </div>
            {% else %}
            <div class="panel half">
                <h2>Notifications <span class="count-badge">{{ notifications|length }}</span></h2>
                {% if notifications %}
                    {% for notif in notifications %}
                    <div class="notification">
                        <div class="summary">{{ notif.summary }}</div>
                        {% if notif.message and notif.message != notif.summary %}
                        <div class="message">{{ notif.message }}</div>
                        {% endif %}
                        <div class="meta">
                            <span>T{{ notif.turn }}</span>
                            <span>Type {{ notif.notif_type }}</span>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="empty">No notifications yet</div>
                {% endif %}
            </div>
            {% endif %}
        </div>
    </div>

    <a href="?{% if debug_mode %}debug=1&{% endif %}{% if verbose_mode %}{% else %}verbose=1{% endif %}" class="debug-toggle">
        {{ '📋 Hide Verbose' if verbose_mode else ('🔍 Hide Debug' if debug_mode else '🔍 Debug') }}
    </a>
</body>
</html>
"""


@dataclass
class DebugInfo:
    """Diagnostic information about log parsing."""
    log_file_name: str = ""
    file_exists: bool = False
    total_lines: int = 0
    empty_lines: int = 0
    parse_errors: int = 0
    type_counts: dict = field(default_factory=dict)
    unrecognized_types: list = field(default_factory=list)
    conversation_before_limit: int = 0
    conversation_after_limit: int = 0
    tools_before_limit: int = 0
    tools_after_limit: int = 0
    events_before_limit: int = 0
    events_after_limit: int = 0
    notifs_before_limit: int = 0
    notifs_after_limit: int = 0


# Known message types we process
KNOWN_TYPES = {
    "turn_start_messages",
    "llm_request",
    "llm_response",
    "tool_request",
    "tool_response",
    "notification",
    "turn_start",
    "turn_complete",
    "heartbeat",
    "popup_choice_needed",
    "command_response",
    "game_start",
    # Tool command types (sent to DLL)
    "get_units",
    "get_cities",
    "get_city_production",
    "get_available_techs",
    "get_available_policies",
    "move_unit",
    "unit_found_city",
    "unit_sleep",
    "unit_skip",
    "set_city_production",
    "send_action",
    "end_turn",
}

# Query tools (read-only information gathering)
QUERY_TOOLS = {
    "get_units",
    "get_cities",
    "get_city_production",
    "get_available_techs",
    "get_available_policies",
    "get_turn_blockers",
    "get_notifications",
}

# Action tools (modify game state)
ACTION_TOOLS = {
    "move_unit",
    "unit_found_city",
    "unit_sleep",
    "unit_skip",
    "set_city_production",
    "choose_tech",
    "adopt_policy",
    "send_action",
    "end_turn",
}


def parse_logs(debug_mode: bool = False, verbose_mode: bool = False) -> dict[str, Any]:
    """Parse JSONL logs and build conversation + tool call list."""
    debug = DebugInfo()
    debug.log_file_name = LOG_FILE.name
    debug.file_exists = LOG_FILE.exists()
    debug.type_counts = defaultdict(int)

    data = {
        "connected": False,
        "current_turn": None,
        "total_tokens": 0,
        "total_requests": 0,
        "estimated_cost": 0.0,
        "conversation": [],
        "tool_calls": [],
        "game_events": [],
        "notifications": [],
        "last_update": datetime.now().strftime("%H:%M:%S"),
        "debug_mode": debug_mode,
        "verbose_mode": verbose_mode,
        "debug": {},
    }

    if not LOG_FILE.exists():
        logger.warning(f"Log file not found: {LOG_FILE}")
        if debug_mode:
            data["debug"] = debug.__dict__
        return data

    # Parse all messages
    messages = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            debug.total_lines += 1
            line = line.strip()
            if not line:
                debug.empty_lines += 1
                continue
            try:
                msg = json.loads(line)
                messages.append(msg)
                # Track message types
                msg_type = msg.get("type", "(no type)")
                debug.type_counts[msg_type] += 1
            except json.JSONDecodeError as e:
                debug.parse_errors += 1
                logger.warning(f"JSON parse error on line {debug.total_lines}: {e}")
                continue

    # Find unrecognized types
    for t in debug.type_counts:
        if t not in KNOWN_TYPES and t != "(no type)":
            debug.unrecognized_types.append(f"{t} ({debug.type_counts[t]})")

    if debug.parse_errors > 0:
        logger.warning(f"Found {debug.parse_errors} JSON parse errors in log file")

    if not messages:
        logger.info("Log file exists but contains no valid messages")
        if debug_mode:
            data["debug"] = debug.__dict__
        return data

    logger.info(f"Parsed {len(messages)} messages from {debug.total_lines} lines")

    # Get connection status and current turn
    for msg in reversed(messages):
        if msg.get("game_id"):
            data["connected"] = True
            break

    for msg in reversed(messages):
        if msg.get("turn") is not None:
            data["current_turn"] = msg["turn"]
            break

    # Build conversation, tool calls, notifications, and game events
    conversation = []
    tool_calls = []
    game_events = []
    notifications = []
    seen_turns = set()
    last_turn = None

    # Track tool requests to pair with responses
    pending_tools = {}  # uuid -> tool_name

    for msg in messages:
        msg_type = msg.get("type", "")
        turn = msg.get("turn")

        # Add turn divider when turn changes
        if turn is not None and turn != last_turn:
            if turn not in seen_turns:
                conversation.append({
                    "type": "turn_divider",
                    "turn": turn,
                    "role": "",
                    "content": "",
                })
                seen_turns.add(turn)
            last_turn = turn

        # === CONVERSATION MESSAGES ===

        # Turn start - system prompt only (briefing comes via llm_request)
        if msg_type == "turn_start_messages":
            system_prompt = msg.get("system_prompt", "")

            if system_prompt:
                conversation.append({
                    "type": "message",
                    "role": "system",
                    "content": system_prompt,
                    "turn": turn or 0,
                    "tokens": 0,
                })

        # LLM request - shows what was sent to the LLM
        if msg_type == "llm_request":
            uuid = msg.get("uuid")
            latest = msg.get("latest_message", {})
            role = latest.get("role", "user")
            content = latest.get("content", "")

            if content:
                # Truncate very long content for display
                display_content = content if len(content) < 2000 else content[:2000] + "\n\n[... truncated ...]"
                conversation.append({
                    "type": "message",
                    "role": role,
                    "content": display_content,
                    "turn": turn or 0,
                    "tokens": 0,
                })
            data["total_requests"] += 1

        # LLM response - shows what came back
        if msg_type == "llm_response":
            response = msg.get("response", "")
            tokens = msg.get("total_tokens", 0) or 0

            if response:
                conversation.append({
                    "type": "message",
                    "role": "assistant",
                    "content": response,
                    "turn": turn or 0,
                    "tokens": tokens,
                })

            data["total_tokens"] += tokens

        # === TOOL ACTIVITY ===

        # Tool request - orchestrator is about to call a tool
        if msg_type == "tool_request":
            tool_name = msg.get("tool", "?")
            uuid = msg.get("uuid")
            pending_tools[uuid] = tool_name

        # Tool response - result from DLL
        if msg_type == "tool_response":
            tool_name = msg.get("tool", "?")
            result = msg.get("result", {})

            # Determine if query or action
            category = "query" if tool_name in QUERY_TOOLS else "action"
            icon = "🔍" if category == "query" else "⚡"

            # Check various error indicators
            is_ok = result.get("ok", True)
            if result.get("type") == "error" or result.get("status") == "error" or result.get("error"):
                is_ok = False
                icon = "✗"

            # Generate result summary
            result_summary = ""
            if not is_ok:
                # Handle various error formats
                error_msg = result.get("message")
                if not error_msg:
                    error_field = result.get("error")
                    if isinstance(error_field, dict):
                        error_msg = error_field.get("message", "Unknown error")
                    elif isinstance(error_field, str):
                        error_msg = error_field
                    else:
                        error_msg = "Unknown error"
                result_summary = f"Error: {error_msg}"
            elif category == "action":
                # For actions, show what happened
                if result.get("success"):
                    if tool_name == "move_unit":
                        result_summary = "Unit moved"
                    elif tool_name == "unit_found_city":
                        result_summary = "City founded"
                    elif tool_name == "set_city_production":
                        item_name = result.get("item_name", "?")
                        result_summary = f"Building: {item_name}"
                    elif tool_name == "send_action":
                        action_type = result.get("type", "?")
                        result_summary = f"{action_type.replace('_', ' ').title()}"
                    elif tool_name == "end_turn":
                        result_summary = "Turn ended"
                    else:
                        result_summary = "Success"
            else:
                # For queries, show data summary
                if tool_name == "get_units":
                    units = result.get("units", [])
                    result_summary = f"{len(units)} unit(s)"
                elif tool_name == "get_cities":
                    cities = result.get("cities", [])
                    result_summary = f"{len(cities)} city/cities"
                elif tool_name == "get_available_techs":
                    techs = result.get("available_techs", [])
                    result_summary = f"{len(techs)} tech(s) available"
                elif tool_name == "get_city_production":
                    units = result.get("trainable_units", [])
                    buildings = result.get("constructable_buildings", [])
                    result_summary = f"{len(units)} units, {len(buildings)} buildings"

            tool_calls.append({
                "name": tool_name,
                "ok": is_ok,
                "category": category,
                "icon": icon,
                "result_summary": result_summary,
                "turn": turn or 0,
            })

        # === GAME EVENTS (verbose mode) ===

        if msg_type == "game_start":
            civ = msg.get("civilization", "Unknown")
            leader = msg.get("leader", "Unknown")
            trait = msg.get("trait_description", "")
            game_events.append({
                "event_type": "Game Start",
                "content": f"{leader} of {civ}\n{trait[:100]}...",
                "turn": turn or 0,
            })

        if msg_type == "turn_start":
            blockers = msg.get("blockers", [])
            blocker_types = [b.get("type", "?") for b in blockers]
            game_events.append({
                "event_type": "Turn Start",
                "content": f"{len(blockers)} blocker(s): {', '.join(blocker_types[:3])}",
                "turn": turn or 0,
            })

        if msg_type == "turn_complete":
            game_events.append({
                "event_type": "Turn Complete",
                "content": f"Turn {turn} ended",
                "turn": turn or 0,
            })

        # === NOTIFICATIONS ===

        if msg_type == "notification":
            notifications.append({
                "summary": msg.get("summary", ""),
                "message": msg.get("message", ""),
                "turn": msg.get("turn", 0),
                "notif_type": msg.get("notification_type", "?"),
                "x": msg.get("x"),
                "y": msg.get("y"),
            })

    # Track counts before limiting
    debug.conversation_before_limit = len(conversation)
    debug.tools_before_limit = len(tool_calls)
    debug.events_before_limit = len(game_events)
    debug.notifs_before_limit = len(notifications)

    # Only show last N messages to avoid overwhelming the UI
    max_messages = 50
    if len(conversation) > max_messages:
        conversation = conversation[-max_messages:]

    max_tools = 100
    if len(tool_calls) > max_tools:
        tool_calls = tool_calls[-max_tools:]

    max_events = 50
    if len(game_events) > max_events:
        game_events = game_events[-max_events:]

    max_notifs = 50
    if len(notifications) > max_notifs:
        notifications = notifications[-max_notifs:]

    # Track counts after limiting
    debug.conversation_after_limit = len(conversation)
    debug.tools_after_limit = len(tool_calls)
    debug.events_after_limit = len(game_events)
    debug.notifs_after_limit = len(notifications)

    # Reverse so newest is at top
    data["conversation"] = list(reversed(conversation))
    data["tool_calls"] = list(reversed(tool_calls))
    data["game_events"] = list(reversed(game_events))
    data["notifications"] = list(reversed(notifications))

    # Estimate cost (rough: $0.001 per 1K tokens for cheap models)
    data["estimated_cost"] = data["total_tokens"] * 0.000001

    if debug_mode:
        # Convert defaultdict to regular dict for JSON serialization
        debug.type_counts = dict(debug.type_counts)
        data["debug"] = debug.__dict__

    return data


@app.route("/")
def dashboard():
    debug_mode = request.args.get("debug") == "1"
    verbose_mode = request.args.get("verbose") == "1"
    data = parse_logs(debug_mode=debug_mode, verbose_mode=verbose_mode)
    return render_template_string(TEMPLATE, **data)


@app.route("/api/data")
def api_data():
    """JSON endpoint for programmatic access."""
    debug_mode = request.args.get("debug") == "1"
    verbose_mode = request.args.get("verbose") == "1"
    return parse_logs(debug_mode=debug_mode, verbose_mode=verbose_mode)


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║         Civ V LLM Dashboard                      ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  URL:      http://localhost:5000                 ║")
    print(f"║  Debug:    http://localhost:5000?debug=1         ║")
    print(f"║  Verbose:  http://localhost:5000?verbose=1       ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Log file: {LOG_FILE.name:<37} ║")
    print(f"║  Path:     {str(LOG_FILE.parent):<37} ║")
    print("╚══════════════════════════════════════════════════╝")

    if not LOG_FILE.exists():
        logger.warning(f"Log file does not exist yet: {LOG_FILE}")
    else:
        logger.info(f"Log file found: {LOG_FILE}")

    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    main()
