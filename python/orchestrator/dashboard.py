"""Simple web dashboard for debugging LLM Civ V runs.

Reads from JSONL logs and displays:
- Full LLM conversation organized by turn
- Tool calls with pass/fail status
- Token usage stats

Run: python -m orchestrator.dashboard
Add ?debug=1 to URL to see parse diagnostics
Add ?verbose=1 to see game events and internal messages
"""

import json
import logging
import queue
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import time as _time

from flask import Flask, Response, render_template_string, request

_broadcaster = None


def init(broadcaster) -> None:
    """Connect dashboard to the orchestrator's EventBroadcaster for live push updates."""
    global _broadcaster
    _broadcaster = broadcaster

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

LOG_DIR = Path(__file__).parent.parent / "logs"

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Civ V LLM Dashboard</title>
    <style>
        :root {
            --bg:           #0d0d18;
            --panel:        #181828;
            --panel-alt:    #1e1e30;
            --border:       #2a2a42;
            --border-hi:    #3a3a58;
            --text:         #e0e0e8;
            --dim:          #888898;
            --muted:        #4a4a60;
            --green:        #3ddc84;
            --blue:         #5aabff;
            --cyan:         #20d0e8;
            --amber:        #e8a020;
            --red:          #ff5a5a;
            --purple:       #a06ef0;
            --orange:       #e87820;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { height: 100%; overflow: hidden; }

        body {
            font-family: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', monospace;
            background: var(--bg);
            color: var(--text);
            font-size: 13px;
            line-height: 1.5;
            display: flex;
            flex-direction: column;
        }

        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--muted); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--dim); }

        /* ── Header ── */
        .header {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 9px 14px;
            border-bottom: 1px solid var(--border);
            flex-shrink: 0;
            background: var(--panel);
        }
        .brand {
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 2px;
            color: var(--amber);
            flex-shrink: 0;
        }
        .sep { color: var(--muted); }
        .status-dot {
            width: 7px; height: 7px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .status-dot.green { background: var(--green); box-shadow: 0 0 5px var(--green); }
        .status-dot.red   { background: var(--red); }
        .turn-chip { font-size: 12px; color: var(--dim); }
        .turn-chip strong { color: var(--text); font-weight: 600; }
        .header-right {
            margin-left: auto;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .cost-info { font-size: 11px; color: var(--dim); }
        .cost-val  { color: var(--green); font-weight: 600; }
        .last-update { font-size: 10px; color: var(--muted); }

        /* game selector */
        .game-selector { position: relative; }
        .game-selector-btn {
            background: none;
            border: 1px solid var(--border);
            color: var(--dim);
            font-family: inherit;
            font-size: 11px;
            padding: 3px 9px;
            border-radius: 4px;
            cursor: pointer;
        }
        .game-selector-btn:hover { border-color: var(--border-hi); color: var(--text); }
        .game-selector-dropdown {
            display: none;
            position: absolute;
            top: calc(100% + 4px);
            right: 0;
            background: var(--panel);
            border: 1px solid var(--border-hi);
            border-radius: 6px;
            min-width: 170px;
            z-index: 200;
            box-shadow: 0 4px 16px rgba(0,0,0,0.5);
        }
        .game-selector:hover .game-selector-dropdown { display: block; }
        .game-selector-item {
            display: flex;
            justify-content: space-between;
            padding: 7px 11px;
            font-size: 11px;
            color: var(--dim);
            text-decoration: none;
            border-bottom: 1px solid var(--border);
        }
        .game-selector-item:last-child { border-bottom: none; }
        .game-selector-item:hover { background: var(--panel-alt); color: var(--text); }
        .game-selector-item.current { color: var(--cyan); }
        .msg-count { color: var(--muted); font-size: 10px; }

        /* ── Layout ── */
        .columns {
            display: grid;
            grid-template-columns: 3fr 2fr;
            gap: 10px;
            flex: 1;
            min-height: 0;
            padding: 10px;
        }
        .right-column {
            display: flex;
            flex-direction: column;
            gap: 10px;
            min-height: 0;
        }

        /* ── Panel ── */
        .panel {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 7px;
            display: flex;
            flex-direction: column;
            min-height: 0;
            overflow: hidden;
        }
        .panel.half { flex: 1 1 0; min-height: 0; }
        .panel-header {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-bottom: 1px solid var(--border);
            flex-shrink: 0;
        }
        .panel-title {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--dim);
            font-weight: 600;
        }
        .count-badge {
            font-size: 10px;
            background: var(--panel-alt);
            border: 1px solid var(--border);
            padding: 1px 6px;
            border-radius: 8px;
            color: var(--muted);
        }
        .panel-scroll {
            overflow-y: auto;
            flex: 1;
            padding: 8px;
        }

        /* ── Turn cards ── */
        .turn-card {
            border: 1px solid var(--border);
            border-radius: 5px;
            margin-bottom: 6px;
            background: var(--panel-alt);
        }
        .turn-card.expanded { border-color: var(--border-hi); }

        .turn-card-header {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 10px;
            cursor: pointer;
            user-select: none;
        }
        .turn-card-header:hover { background: rgba(255,255,255,0.02); }
        .caret { color: var(--muted); font-size: 9px; flex-shrink: 0; }
        .turn-card.expanded .caret  { color: var(--amber); }

        .turn-num {
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.8px;
            color: var(--dim);
            flex-shrink: 0;
        }
        .turn-card.expanded .turn-num { color: var(--amber); }

        .badge {
            font-size: 9px;
            padding: 1px 6px;
            border-radius: 8px;
            font-weight: 600;
            letter-spacing: 0.3px;
            text-transform: uppercase;
            flex-shrink: 0;
        }
        .badge.active { color: var(--green);  border: 1px solid rgba(61,220,132,0.35); background: rgba(61,220,132,0.1); }
        .badge.done   { color: var(--muted);  border: 1px solid var(--border); }
        .badge.error  { color: var(--red);    border: 1px solid rgba(255,90,90,0.3); background: rgba(255,90,90,0.08); }

        .turn-stats { font-size: 10px; color: var(--muted); margin-left: auto; }

        /* Card body */
        .turn-card-body {
            padding: 8px 10px 10px;
            border-top: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        /* Briefing */
        .briefing-toggle {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--blue);
            cursor: pointer;
            user-select: none;
        }
        .briefing-toggle:hover { color: var(--cyan); }
        .briefing-text {
            margin-top: 5px;
            font-size: 11px;
            color: var(--dim);
            white-space: pre-wrap;
            line-height: 1.5;
            max-height: 180px;
            overflow-y: auto;
            padding: 7px 9px;
            background: rgba(0,0,0,0.25);
            border-radius: 4px;
            border-left: 2px solid var(--border-hi);
        }

        /* Reasoning */
        .reasoning-label {
            font-size: 9px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--green);
            margin-bottom: 3px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .tok-badge { color: var(--muted); font-weight: normal; text-transform: none; letter-spacing: 0; }
        .reasoning-text { font-size: 12px; color: var(--text); white-space: pre-wrap; line-height: 1.6; }
        .show-more { color: var(--blue); cursor: pointer; font-size: 10px; }
        .show-more:hover { color: var(--cyan); }

        /* Actions row */
        .actions-row { display: flex; flex-wrap: wrap; gap: 5px; }
        .action-pill {
            font-size: 10px;
            padding: 2px 7px;
            border-radius: 3px;
            border: 1px solid;
        }
        .action-pill.ok      { color: var(--amber);  border-color: rgba(232,160,32,0.35); background: rgba(232,160,32,0.08); }
        .action-pill.err     { color: var(--red);    border-color: rgba(255,90,90,0.3);  background: rgba(255,90,90,0.08); }
        .action-pill.end_turn{ color: var(--green);  border-color: rgba(61,220,132,0.3); background: rgba(61,220,132,0.08); }

        /* ── Tool list ── */
        .turn-group-label {
            font-size: 9px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 4px 2px 2px;
            border-top: 1px solid var(--border);
            margin: 4px 0 3px;
        }
        .turn-group-label:first-child { border-top: none; margin-top: 0; padding-top: 0; }

        .tool-item {
            display: grid;
            grid-template-columns: 15px 1fr;
            grid-template-rows: auto auto;
            column-gap: 6px;
            row-gap: 1px;
            padding: 5px 7px;
            border-radius: 4px;
            margin-bottom: 2px;
            cursor: pointer;
            border: 1px solid transparent;
        }
        .tool-item:hover { background: var(--panel-alt); border-color: var(--border); }

        .tool-icon {
            grid-row: 1 / 3;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            color: var(--dim);
            align-self: center;
        }
        .tool-item.query  .tool-icon { color: var(--blue); }
        .tool-item.action .tool-icon { color: var(--amber); }
        .tool-item.error  .tool-icon { color: var(--red); }

        .tool-name { font-size: 11px; font-weight: 600; color: var(--text); }
        .tool-result { font-size: 10px; }
        .tool-result.ok  { color: var(--dim); }
        .tool-result.err { color: var(--red); }

        /* ── Notifications ── */
        .notif-item {
            display: flex;
            gap: 7px;
            align-items: baseline;
            padding: 4px 0;
            border-bottom: 1px solid var(--border);
            font-size: 11px;
        }
        .notif-item:last-child { border-bottom: none; }
        .notif-turn { font-size: 9px; color: var(--muted); flex-shrink: 0; min-width: 22px; }
        .notif-text { color: var(--dim); }

        /* ── Empty ── */
        .empty { color: var(--muted); font-size: 11px; text-align: center; padding: 22px; font-style: italic; }

        /* ── Modal ── */
        .modal-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.78);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .modal-overlay.visible { display: flex; }
        .modal-content {
            background: var(--panel);
            border: 1px solid var(--border-hi);
            border-radius: 8px;
            max-width: 860px;
            max-height: 90vh;
            width: 100%;
            display: flex;
            flex-direction: column;
            box-shadow: 0 8px 32px rgba(0,0,0,0.6);
        }
        .modal-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 13px 17px;
            border-bottom: 1px solid var(--border);
        }
        .modal-title { font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .modal-close {
            background: none; border: none; color: var(--dim);
            font-size: 18px; cursor: pointer; padding: 2px 6px; border-radius: 3px;
        }
        .modal-close:hover { background: var(--panel-alt); color: var(--text); }
        .modal-body { padding: 16px; overflow-y: auto; flex: 1; display: flex; flex-direction: column; gap: 14px; }
        .modal-section-label {
            font-size: 10px; text-transform: uppercase; letter-spacing: 1px;
            color: var(--cyan); margin-bottom: 7px;
        }
        .modal-json {
            background: #09090f;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 11px;
            font-size: 11px;
            line-height: 1.6;
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
            color: var(--dim);
            font-family: inherit;
        }

        /* ── Toggle buttons ── */
        .toggle-buttons {
            position: fixed;
            bottom: 12px;
            right: 12px;
            display: flex;
            gap: 6px;
            z-index: 100;
        }
        .toggle-btn {
            background: var(--panel);
            border: 1px solid var(--border);
            color: var(--dim);
            padding: 5px 12px;
            border-radius: 14px;
            font-size: 10px;
            font-family: inherit;
            text-decoration: none;
            cursor: pointer;
        }
        .toggle-btn:hover { border-color: var(--border-hi); color: var(--text); }
        .toggle-btn.active { border-color: var(--purple); color: var(--purple); }

        /* ── Debug panel ── */
        .debug-panel {
            margin: 0 10px 10px;
            background: var(--panel-alt);
            border: 1px solid var(--purple);
            border-radius: 6px;
            padding: 12px;
            font-size: 11px;
        }
        .debug-panel h3 {
            color: var(--purple); font-size: 10px; text-transform: uppercase;
            letter-spacing: 1px; margin-bottom: 10px;
        }
        .debug-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
        .debug-section { background: rgba(0,0,0,0.2); padding: 10px; border-radius: 4px; }
        .debug-section h4 { color: var(--dim); font-size: 10px; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.5px; }
        .debug-item { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,0.04); }
        .debug-item:last-child { border-bottom: none; }
        .debug-key { color: var(--muted); }
        .debug-val { color: var(--cyan); font-weight: 500; }
        .debug-val.warn { color: var(--amber); }
        .debug-val.err  { color: var(--red); }
    </style>
</head>
<body>

<!-- Header -->
<div class="header">
    <span class="brand">◈ CIV V</span>
    <span class="sep">│</span>
    <span class="status-dot {{ 'green' if connected else 'red' }}"></span>
    <span class="turn-chip">Turn <strong class="turn-display">{{ current_turn or '—' }}</strong></span>
    {% if available_games %}
    <span class="sep">│</span>
    <div class="game-selector">
        <button class="game-selector-btn">Game {{ game_id or '—' }} ▾</button>
        <div class="game-selector-dropdown">
            {% for game in available_games %}
            <a href="?game_id={{ game.game_id }}{% if debug_mode %}&debug=1{% endif %}{% if verbose_mode %}&verbose=1{% endif %}"
               class="game-selector-item {{ 'current' if game.is_current else '' }}">
                <span>{{ game.game_id }}</span>
                <span class="msg-count">{{ game.message_count }} msgs</span>
            </a>
            {% endfor %}
        </div>
    </div>
    {% endif %}
    <div class="header-right">
        <span class="cost-info">
            <span class="cost-val">${{ "%.4f"|format(estimated_cost) }}</span>
            &thinsp;·&thinsp; {{ total_requests }} req
            &thinsp;·&thinsp; {{ "{:,}".format(total_tokens) }} tok
        </span>
        <span class="last-update last-update-text">{{ last_update }}</span>
    </div>
</div>

{% if debug_mode %}
<div class="debug-panel">
    <h3>🔍 Parse Diagnostics</h3>
    <div class="debug-grid">
        <div class="debug-section">
            <h4>File</h4>
            <div class="debug-item"><span class="debug-key">name</span><span class="debug-val">{{ debug.log_file_name }}</span></div>
            <div class="debug-item"><span class="debug-key">exists</span><span class="debug-val {% if not debug.file_exists %}err{% endif %}">{{ 'yes' if debug.file_exists else 'no' }}</span></div>
            <div class="debug-item"><span class="debug-key">lines</span><span class="debug-val">{{ debug.total_lines }}</span></div>
            <div class="debug-item"><span class="debug-key">parse errors</span><span class="debug-val {% if debug.parse_errors > 0 %}err{% endif %}">{{ debug.parse_errors }}</span></div>
        </div>
        <div class="debug-section">
            <h4>Message Types</h4>
            {% for t, n in debug.type_counts.items() %}
            <div class="debug-item"><span class="debug-key">{{ t or '(none)' }}</span><span class="debug-val">{{ n }}</span></div>
            {% endfor %}
        </div>
        <div class="debug-section">
            <h4>Display Limits</h4>
            <div class="debug-item"><span class="debug-key">conv (max 50)</span><span class="debug-val {% if debug.conversation_before_limit > 50 %}warn{% endif %}">{{ debug.conversation_before_limit }} → {{ debug.conversation_after_limit }}</span></div>
            <div class="debug-item"><span class="debug-key">tools (max 100)</span><span class="debug-val {% if debug.tools_before_limit > 100 %}warn{% endif %}">{{ debug.tools_before_limit }} → {{ debug.tools_after_limit }}</span></div>
            <div class="debug-item"><span class="debug-key">notifs (max 50)</span><span class="debug-val {% if debug.notifs_before_limit > 50 %}warn{% endif %}">{{ debug.notifs_before_limit }} → {{ debug.notifs_after_limit }}</span></div>
        </div>
        {% if debug.unrecognized_types %}
        <div class="debug-section">
            <h4>Unrecognized Types</h4>
            {% for t in debug.unrecognized_types %}
            <div class="debug-item"><span class="debug-key" style="color:var(--amber)">{{ t }}</span></div>
            {% endfor %}
        </div>
        {% endif %}
    </div>
</div>
{% endif %}

<!-- Main layout -->
<div class="columns">
    <!-- Left: Turn cards -->
    <div class="panel">
        <div class="panel-header">
            <span class="panel-title">Turns</span>
            <span class="count-badge" id="turns-count">0</span>
        </div>
        <div class="panel-scroll" id="turns-container">
            <div class="empty">Waiting for game data…</div>
        </div>
    </div>

    <!-- Right: Tools + Notifications -->
    <div class="right-column">
        <div class="panel half">
            <div class="panel-header">
                <span class="panel-title">Tools</span>
                <span class="count-badge" id="tools-count">0</span>
            </div>
            <div class="panel-scroll" id="tools-container">
                <div class="empty">No tool calls yet</div>
            </div>
        </div>
        <div class="panel half">
            <div class="panel-header">
                <span class="panel-title" id="notifs-title">{{ 'Game Events' if verbose_mode else 'Notifications' }}</span>
                <span class="count-badge" id="notifs-count">0</span>
            </div>
            <div class="panel-scroll" id="notifs-container">
                <div class="empty">None yet</div>
            </div>
        </div>
    </div>
</div>

<!-- Toggle buttons -->
<div class="toggle-buttons">
    <a href="?{% if game_id %}game_id={{ game_id }}&{% endif %}{% if not debug_mode %}debug=1{% endif %}{% if verbose_mode %}&verbose=1{% endif %}"
       class="toggle-btn {% if debug_mode %}active{% endif %}">🔍 Debug</a>
    <a href="?{% if game_id %}game_id={{ game_id }}&{% endif %}{% if debug_mode %}debug=1&{% endif %}{% if not verbose_mode %}verbose=1{% endif %}"
       class="toggle-btn {% if verbose_mode %}active{% endif %}">📋 Verbose</a>
</div>

<!-- Tool modal -->
<div class="modal-overlay" id="toolModal">
    <div class="modal-content">
        <div class="modal-header">
            <div class="modal-title">
                <span id="modalIcon"></span>
                <span id="modalToolName"></span>
            </div>
            <button class="modal-close" onclick="closeModal()">×</button>
        </div>
        <div class="modal-body">
            <div>
                <div class="modal-section-label">Arguments</div>
                <pre class="modal-json" id="modalArguments"></pre>
            </div>
            <div>
                <div class="modal-section-label">Response</div>
                <pre class="modal-json" id="modalResult"></pre>
            </div>
        </div>
    </div>
</div>

<script>
    // ── Initial page data (server-rendered) ──
    const PAGE_DATA = {{ page_data_json|safe }};

    // ── Interaction state ──
    const expandedTurns = new Set();
    const briefingOpen  = new Set();
    const fullMsgOpen   = new Set();
    let toolData        = [];
    let lastData        = PAGE_DATA;
    const verboseMode   = PAGE_DATA.verbose_mode;

    // ── Helpers ──
    function esc(s) {
        if (s == null) return '';
        const d = document.createElement('div');
        d.textContent = String(s);
        return d.innerHTML;
    }

    function fmtTok(n) {
        if (!n) return '';
        return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n);
    }

    // ── Turn grouping ──
    // conversation is newest-first; tool_calls is newest-first
    function buildTurnGroups(conversation, toolCalls) {
        const map = new Map();

        for (const msg of conversation) {
            const t = msg.turn || 0;
            if (!map.has(t)) {
                map.set(t, {turn: t, messages: [], tools: [], tokenCount: 0,
                            queryCount: 0, actionCount: 0, hasError: false});
            }
            if (msg.type !== 'turn_divider') {
                map.get(t).messages.push(msg);
                map.get(t).tokenCount += (msg.tokens || 0);
            }
        }

        for (const tool of toolCalls) {
            const t = tool.turn || 0;
            if (!map.has(t)) {
                map.set(t, {turn: t, messages: [], tools: [], tokenCount: 0,
                            queryCount: 0, actionCount: 0, hasError: false});
            }
            const g = map.get(t);
            g.tools.push(tool);
            if (tool.category === 'query') g.queryCount++;
            else if (tool.category === 'action') g.actionCount++;
            if (!tool.ok) g.hasError = true;
        }

        return [...map.values()].sort((a, b) => b.turn - a.turn);
    }

    const ACTION_NAMES = new Set([
        'move_unit', 'unit_found_city', 'unit_sleep', 'unit_skip',
        'set_city_production', 'choose_tech', 'adopt_policy', 'send_action', 'end_turn',
        'city_capture_decision', 'select_pantheon', 'found_religion', 'enhance_religion',
    ]);

    function renderTurnCard(group, isActive) {
        const {turn, messages, tools, tokenCount, queryCount, actionCount, hasError} = group;
        const isExpanded = expandedTurns.has(turn);

        const parts = [];
        if (queryCount)  parts.push(queryCount  + 'q');
        if (actionCount) parts.push(actionCount + 'a');
        const tok = fmtTok(tokenCount);
        if (tok) parts.push(tok + ' tok');
        const stats = parts.join(' · ');

        const statusBadge = isActive
            ? '<span class="badge active">active</span>'
            : '<span class="badge done">done</span>';
        const errBadge = hasError ? '<span class="badge error">err</span>' : '';
        const caret = isExpanded ? '▼' : '▶';

        let bodyHtml = '';
        if (isExpanded) {
            // messages within a turn are newest-first; reverse to display chronologically
            const chrono = [...messages].reverse();
            const userMsgs   = chrono.filter(m => m.role === 'user');
            const assistMsgs = chrono.filter(m => m.role === 'assistant');

            // User briefing (collapsible)
            if (userMsgs.length > 0) {
                const latest = userMsgs[userMsgs.length - 1];
                const open   = briefingOpen.has(turn);
                const arrow  = open ? '▾' : '▸';
                const txt    = open
                    ? `<div class="briefing-text">${esc(latest.content)}</div>`
                    : '';
                bodyHtml += `
                    <div>
                        <span class="briefing-toggle" onclick="toggleBriefing(event,${turn})">
                            Turn briefing ${arrow}
                        </span>${txt}
                    </div>`;
            }

            // Assistant reasoning
            for (let i = 0; i < assistMsgs.length; i++) {
                const msg = assistMsgs[i];
                if (!msg.content || !msg.content.trim()) continue;
                const key  = turn + '_' + i;
                const open = fullMsgOpen.has(key);
                const LIM  = 500;
                const long = msg.content.length > LIM;
                const text = (long && !open) ? msg.content.slice(0, LIM) + '\u2026' : msg.content;
                const more = (long && !open)
                    ? `<span class="show-more" onclick="toggleFullMsg(event,'${key}')">[show more]</span>`
                    : '';
                const tok  = msg.tokens ? `<span class="tok-badge">${msg.tokens} tok</span>` : '';
                bodyHtml += `
                    <div>
                        <div class="reasoning-label">assistant ${tok}</div>
                        <div class="reasoning-text">${esc(text)}${more}</div>
                    </div>`;
            }

            // Action pills
            const actionTools = tools.filter(t => ACTION_NAMES.has(t.name));
            if (actionTools.length > 0) {
                const pills = actionTools.map(t => {
                    const cls = t.name === 'end_turn' ? 'end_turn' : (t.ok ? 'ok' : 'err');
                    return `<span class="action-pill ${cls}">${esc(t.name)}</span>`;
                }).join('');
                bodyHtml += `<div class="actions-row">${pills}</div>`;
            }
        }

        return `
            <div class="turn-card ${isExpanded ? 'expanded' : ''}" id="turn-card-${turn}">
                <div class="turn-card-header" onclick="toggleTurn(event,${turn})">
                    <span class="caret">${caret}</span>
                    <span class="turn-num">TURN ${turn}</span>
                    ${statusBadge}${errBadge}
                    <span class="turn-stats">${esc(stats)}</span>
                </div>
                ${isExpanded ? `<div class="turn-card-body">${bodyHtml}</div>` : ''}
            </div>`;
    }

    function renderTurns(data) {
        const groups = buildTurnGroups(data.conversation, data.tool_calls);
        document.getElementById('turns-count').textContent = groups.length;

        // Auto-expand latest turn on first render
        if (expandedTurns.size === 0 && groups.length > 0) {
            expandedTurns.add(groups[0].turn);
        }

        const activeTurn = data.current_turn;
        let html = '';
        for (const g of groups) {
            html += renderTurnCard(g, g.turn === activeTurn);
        }

        const container = document.getElementById('turns-container');
        const scrollTop = container.scrollTop;
        container.innerHTML = html || '<div class="empty">No turns yet — waiting for game data…</div>';
        container.scrollTop = scrollTop;
    }

    function toggleTurn(e, turn) {
        e.stopPropagation();
        if (expandedTurns.has(turn)) expandedTurns.delete(turn);
        else expandedTurns.add(turn);
        renderTurns(lastData);
    }

    function toggleBriefing(e, turn) {
        e.stopPropagation();
        if (briefingOpen.has(turn)) briefingOpen.delete(turn);
        else briefingOpen.add(turn);
        renderTurns(lastData);
    }

    function toggleFullMsg(e, key) {
        e.stopPropagation();
        if (fullMsgOpen.has(key)) fullMsgOpen.delete(key);
        else fullMsgOpen.add(key);
        renderTurns(lastData);
    }

    // ── Tools panel ──
    function renderTools(data) {
        toolData = data.tool_calls;
        document.getElementById('tools-count').textContent = toolData.length;
        const container = document.getElementById('tools-container');
        const scrollTop = container.scrollTop;

        if (toolData.length === 0) {
            container.innerHTML = '<div class="empty">No tool calls yet</div>';
        } else {
            let html = '';
            let lastTurn = null;
            for (let i = 0; i < toolData.length; i++) {
                const tool = toolData[i];
                if (tool.turn !== lastTurn) {
                    html += `<div class="turn-group-label">T${tool.turn}</div>`;
                    lastTurn = tool.turn;
                }
                const errCls = tool.ok ? '' : 'error';
                const resCls = tool.ok ? 'ok' : 'err';
                const resHtml = tool.result_summary
                    ? `<div class="tool-result ${resCls}">${esc(tool.result_summary)}</div>` : '';
                html += `
                    <div class="tool-item ${tool.category} ${errCls}" onclick="openToolModal(${i})">
                        <span class="tool-icon">${tool.icon}</span>
                        <span class="tool-name">${esc(tool.name)}</span>
                        ${resHtml}
                    </div>`;
            }
            container.innerHTML = html;
        }
        container.scrollTop = scrollTop;
    }

    // ── Notifications / game events panel ──
    function renderNotifs(data) {
        const items = verboseMode ? data.game_events : data.notifications;
        document.getElementById('notifs-count').textContent = items.length;
        const container = document.getElementById('notifs-container');
        const scrollTop = container.scrollTop;

        if (items.length === 0) {
            container.innerHTML = '<div class="empty">None yet</div>';
        } else {
            let html = '';
            for (const item of items) {
                const label = verboseMode ? item.event_type : item.summary;
                html += `
                    <div class="notif-item">
                        <span class="notif-turn">T${item.turn}</span>
                        <span class="notif-text">${esc(label)}</span>
                    </div>`;
            }
            container.innerHTML = html;
        }
        container.scrollTop = scrollTop;
    }

    // ── Header update ──
    function updateHeader(data) {
        const dot = document.querySelector('.status-dot');
        if (dot) dot.className = 'status-dot ' + (data.connected ? 'green' : 'red');
        const td = document.querySelector('.turn-display');
        if (td) td.textContent = data.current_turn || '—';
        const cv = document.querySelector('.cost-val');
        if (cv) cv.textContent = '$' + data.estimated_cost.toFixed(4);
        const lu = document.querySelector('.last-update-text');
        if (lu) lu.textContent = data.last_update;
    }

    // ── Full render ──
    function renderAll(data) {
        lastData = data;
        updateHeader(data);
        renderTurns(data);
        renderTools(data);
        renderNotifs(data);
    }

    // ── Modal ──
    function openToolModal(index) {
        const tool = toolData[index];
        if (!tool) return;
        document.getElementById('modalIcon').textContent = tool.icon;
        document.getElementById('modalToolName').textContent = tool.name;
        const args   = tool.arguments || {};
        const result = tool.result    || {};
        document.getElementById('modalArguments').textContent = JSON.stringify(args, null, 2);
        if (result.map && typeof result.map === 'string') {
            const {map, ...rest} = result;
            let txt = '=== ASCII Map ===\n\n' + map;
            if (Object.keys(rest).length) txt += '\n\n=== Other Data ===\n\n' + JSON.stringify(rest, null, 2);
            document.getElementById('modalResult').textContent = txt;
        } else {
            document.getElementById('modalResult').textContent = JSON.stringify(result, null, 2);
        }
        document.getElementById('toolModal').classList.add('visible');
    }

    function closeModal() {
        document.getElementById('toolModal').classList.remove('visible');
    }

    function isModalOpen() {
        return document.getElementById('toolModal').classList.contains('visible');
    }

    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
    document.getElementById('toolModal').addEventListener('click', e => {
        if (e.target === document.getElementById('toolModal')) closeModal();
    });

    // ── SSE ──
    const params = new URLSearchParams(window.location.search);
    const evtSource = new EventSource('/api/stream?' + params.toString());
    evtSource.addEventListener('update', e => {
        if (isModalOpen()) return;
        try { renderAll(JSON.parse(e.data)); }
        catch (err) { console.error('SSE parse error:', err); }
    });
    evtSource.onerror = () => console.warn('SSE connection lost, reconnecting…');

    // ── Initial render ──
    renderAll(PAGE_DATA);
</script>
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
    "force_end_turn",
    # Map visualization tools
    "get_visible_tiles",
    "get_map_view",
    "get_unit_build_options",
    "get_reachable_tiles",
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
    # Map visualization tools
    "get_visible_tiles",
    "get_map_view",
    "get_unit_build_options",
    "get_reachable_tiles",
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


def filter_tool_calls_from_text(text: str) -> str:
    """Remove mcp_call() and other tool invocation lines from text.

    This filters out lines like:
    - mcp_call(tool="...", arguments={...})
    - end_turn(turn=N)
    - Other tool-related syntax

    We want to show only the LLM's reasoning and natural language responses,
    since tool calls are already visualized in the Tool Activity panel.
    """
    if not text:
        return text

    lines = text.split('\n')
    filtered_lines = []

    # Tool patterns to filter out
    tool_patterns = [
        "mcp_call(",
        "end_turn(",
        "send_action(",
        "move_unit(",
        "unit_found_city(",
        "unit_sleep(",
        "unit_skip(",
        "set_city_production(",
        "choose_tech(",
        "adopt_policy(",
        "get_units(",
        "get_cities(",
        "get_city_production(",
        "get_available_techs(",
        "get_available_policies(",
        "get_turn_blockers(",
        "get_notifications(",
        "force_end_turn(",
        # Map visualization tools
        "get_visible_tiles(",
        "get_map_view(",
        "get_unit_build_options(",
        "get_reachable_tiles(",
    ]

    for line in lines:
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            filtered_lines.append(line)
            continue

        # Skip lines that match tool call patterns
        is_tool_call = any(stripped.startswith(pattern) for pattern in tool_patterns)
        if is_tool_call:
            continue

        filtered_lines.append(line)

    result = '\n'.join(filtered_lines).strip()

    # Clean up excessive blank lines (more than 2 consecutive)
    while '\n\n\n' in result:
        result = result.replace('\n\n\n', '\n\n')

    return result


def parse_logs(debug_mode: bool = False, verbose_mode: bool = False, game_id: int | None = None) -> dict[str, Any]:
    """Parse JSONL logs and build conversation + tool call list.

    Args:
        debug_mode: Show debug diagnostics panel
        verbose_mode: Show game events instead of notifications
        game_id: Filter to specific game_id (None = auto-select most recent)
    """
    debug = DebugInfo()
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
        "game_id": game_id,
        "available_games": [],
    }

    # Scan for game_*.jsonl files in the logs directory
    if not LOG_DIR.exists():
        logger.warning(f"Log directory not found: {LOG_DIR}")
        if debug_mode:
            debug.log_file_name = "(no log dir)"
            debug.file_exists = False
            data["debug"] = debug.__dict__
        return data

    game_files = list(LOG_DIR.glob("game_*.jsonl"))
    if not game_files:
        logger.info("No game log files found in logs directory")
        if debug_mode:
            debug.log_file_name = "(no game files)"
            debug.file_exists = False
            data["debug"] = debug.__dict__
        return data

    # Extract game_ids from filenames and sort by modification time (most recent first)
    game_info = []
    for file_path in game_files:
        try:
            # Extract game_id from filename: game_12345.jsonl -> 12345
            gid = int(file_path.stem.split("_")[1])
            mtime = file_path.stat().st_mtime
            game_info.append((gid, file_path, mtime))
        except (ValueError, IndexError):
            logger.warning(f"Skipping malformed game file: {file_path.name}")
            continue

    if not game_info:
        logger.warning("No valid game files found")
        if debug_mode:
            debug.log_file_name = "(no valid files)"
            debug.file_exists = False
            data["debug"] = debug.__dict__
        return data

    # Sort by mtime (most recent first)
    game_info.sort(key=lambda x: x[2], reverse=True)

    # Auto-select most recent game if not specified
    if game_id is None:
        game_id = game_info[0][0]
        logger.info(f"Auto-selected most recent game_id: {game_id}")

    # Find the log file for selected game
    log_file = None
    for gid, file_path, _ in game_info:
        if gid == game_id:
            log_file = file_path
            break

    if log_file is None:
        logger.warning(f"Game {game_id} not found in logs")
        if debug_mode:
            debug.log_file_name = f"game_{game_id}.jsonl (not found)"
            debug.file_exists = False
            data["debug"] = debug.__dict__
        return data

    # Update debug info
    debug.log_file_name = log_file.name
    debug.file_exists = log_file.exists()
    data["game_id"] = game_id

    # Parse all messages from selected game file
    messages = []
    with open(log_file, "r", encoding="utf-8") as f:
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

    # Build list of available games from scanned files
    available_games = []
    for gid, file_path, mtime in game_info:
        # Count messages in this game file (only for display)
        msg_count = sum(1 for line in open(file_path, "r") if line.strip())
        available_games.append({
            "game_id": gid,
            "message_count": msg_count,
            "is_current": gid == game_id,
        })
    data["available_games"] = available_games

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
                # Filter out tool call syntax - those are shown in Tool Activity panel
                filtered_response = filter_tool_calls_from_text(response)

                # Only add to conversation if there's meaningful content after filtering
                if filtered_response:
                    conversation.append({
                        "type": "message",
                        "role": "assistant",
                        "content": filtered_response,
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
            arguments = msg.get("arguments", {})

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
                # Map visualization tools
                elif tool_name == "get_visible_tiles":
                    tiles = result.get("tiles", [])
                    map_width = result.get("map_width", 0)
                    map_height = result.get("map_height", 0)
                    result_summary = f"{len(tiles)} tiles ({map_width}×{map_height} map)"
                elif tool_name == "get_map_view":
                    center = result.get("center")
                    num_tiles = result.get("num_tiles", 0)
                    num_units = result.get("num_units", 0)
                    center_str = f"({center[0]},{center[1]})" if center else "?"
                    result_summary = f"Map @ {center_str}: {num_tiles} tiles, {num_units} units"
                elif tool_name == "get_unit_build_options":
                    tiles = result.get("tiles", [])
                    total_builds = sum(len(t.get("available_builds", [])) for t in tiles)
                    result_summary = f"{len(tiles)} tiles, {total_builds} build options"
                elif tool_name == "get_reachable_tiles":
                    tiles = result.get("tiles", [])
                    attackable = sum(1 for t in tiles if t.get("can_attack"))
                    result_summary = f"{len(tiles)} tiles ({attackable} attackable)"

            tool_calls.append({
                "name": tool_name,
                "ok": is_ok,
                "category": category,
                "icon": icon,
                "result_summary": result_summary,
                "turn": turn or 0,
                "arguments": arguments,
                "result": result,
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
            game_events.append({
                "event_type": "Turn Start",
                "content": f"Turn {turn} started",
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

    # Create JSON-safe version of tool_calls for backward compat
    data["tool_calls_json"] = json.dumps(data["tool_calls"])

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
    game_id_str = request.args.get("game_id")
    game_id = int(game_id_str) if game_id_str else None
    data = parse_logs(debug_mode=debug_mode, verbose_mode=verbose_mode, game_id=game_id)
    # Build page_data_json for initial JS render (excludes tool_calls_json to avoid redundancy)
    data["page_data_json"] = json.dumps({k: v for k, v in data.items() if k not in ("tool_calls_json",)})
    return render_template_string(TEMPLATE, **data)


@app.route("/api/data")
def api_data():
    """JSON endpoint for programmatic access."""
    debug_mode = request.args.get("debug") == "1"
    verbose_mode = request.args.get("verbose") == "1"
    game_id_str = request.args.get("game_id")
    game_id = int(game_id_str) if game_id_str else None
    return parse_logs(debug_mode=debug_mode, verbose_mode=verbose_mode, game_id=game_id)


def _log_mtime(game_id=None) -> float:
    """Return the most recent mtime of the relevant log file(s).

    Used by the SSE stream to detect when logs change without re-parsing them.
    """
    if not LOG_DIR.exists():
        return 0.0
    if game_id:
        f = LOG_DIR / f"game_{game_id}.jsonl"
        return f.stat().st_mtime if f.exists() else 0.0
    files = list(LOG_DIR.glob("game_*.jsonl"))
    return max((f.stat().st_mtime for f in files), default=0.0)


@app.route("/api/stream")
def api_stream():
    """SSE stream: push fresh data on each game event.

    When run embedded in the orchestrator, subscribes to the shared EventBroadcaster
    and pushes immediately on any event. When run standalone, falls back to watching
    log file mtime at 0.5s intervals.
    """
    debug_mode = request.args.get("debug") == "1"
    verbose_mode = request.args.get("verbose") == "1"
    game_id_str = request.args.get("game_id")
    game_id = int(game_id_str) if game_id_str else None

    def generate():
        # Send initial snapshot immediately so the page populates on connect
        data = parse_logs(debug_mode=debug_mode, verbose_mode=verbose_mode, game_id=game_id)
        yield f"event: update\ndata: {json.dumps(data)}\n\n"

        if _broadcaster:
            q = _broadcaster.subscribe()
            try:
                while True:
                    try:
                        q.get(timeout=30)
                    except queue.Empty:
                        yield ": keepalive\n\n"
                        continue
                    # Log is already flushed before broadcaster fires — parse fresh data
                    data = parse_logs(debug_mode=debug_mode, verbose_mode=verbose_mode, game_id=game_id)
                    yield f"event: update\ndata: {json.dumps(data)}\n\n"
            finally:
                _broadcaster.unsubscribe(q)
        else:
            # Fallback: file-mtime polling (standalone mode)
            last_mtime = _log_mtime(game_id)
            while True:
                _time.sleep(0.5)
                mtime = _log_mtime(game_id)
                if mtime != last_mtime:
                    last_mtime = mtime
                    data = parse_logs(debug_mode=debug_mode, verbose_mode=verbose_mode, game_id=game_id)
                    yield f"event: update\ndata: {json.dumps(data)}\n\n"
                else:
                    yield ": keepalive\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║         Civ V LLM Dashboard                      ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  URL:      http://localhost:5000                 ║")
    print(f"║  Debug:    http://localhost:5000?debug=1         ║")
    print(f"║  Verbose:  http://localhost:5000?verbose=1       ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Log dir:  {str(LOG_DIR):<37} ║")
    print("╚══════════════════════════════════════════════════╝")

    if not LOG_DIR.exists():
        logger.warning(f"Log directory does not exist yet: {LOG_DIR}")
    else:
        game_files = list(LOG_DIR.glob("game_*.jsonl"))
        logger.info(f"Found {len(game_files)} game log files in {LOG_DIR}")

    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
