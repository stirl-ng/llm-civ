"""
Flask Dashboard for Civilization V LLM Orchestrator

Provides a web interface for:
- Monitoring system status (DLL pipe, MCP server, game connection)
- Viewing detailed game state
- Tracking LLM activity (tool calls and messages)
- Viewing summary log
"""

import json
import time
from datetime import datetime
from typing import Optional

from flask import Flask, jsonify, render_template_string, request

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game_state import GameState

from .mcp_server import CivMCPServer


# HTML template for the dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Civ V LLM Dashboard</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
        }
        .header {
            background: #16213e;
            padding: 1rem 2rem;
            border-bottom: 2px solid #0f3460;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }
        .header h1 {
            color: #e94560;
            font-size: 1.5rem;
        }
        .status-bar {
            display: flex;
            gap: 1.5rem;
            align-items: center;
            flex-wrap: wrap;
        }
        .status-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.9rem;
        }
        .status-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #4ade80;
        }
        .status-indicator.disconnected {
            background: #ef4444;
        }
        .status-indicator.offline {
            background: #6b7280;
        }
        .status-label {
            color: #aaa;
            margin-right: 0.25rem;
        }
        .status-value {
            color: #eee;
            font-weight: 500;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 400px;
            gap: 1rem;
            padding: 1rem;
            min-height: calc(100vh - 120px);
        }
        .panel {
            background: #16213e;
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .panel-header {
            background: #0f3460;
            padding: 0.75rem 1rem;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }
        .panel-header:hover {
            background: #1a4b8c;
        }
        .panel-body {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
        }
        .section {
            margin-bottom: 1.5rem;
        }
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0;
            border-bottom: 1px solid #0f3460;
            margin-bottom: 0.75rem;
            cursor: pointer;
        }
        .section-header:hover {
            color: #e94560;
        }
        .section-title {
            color: #e94560;
            font-size: 0.95rem;
            font-weight: 600;
        }
        .section-toggle {
            color: #888;
            font-size: 0.8rem;
        }
        .section-content {
            display: block;
        }
        .section-content.collapsed {
            display: none;
        }
        .card {
            background: #1a1a2e;
            border-radius: 4px;
            padding: 0.75rem;
            margin-bottom: 0.5rem;
        }
        .card-title {
            color: #4ade80;
            font-weight: 600;
            margin-bottom: 0.25rem;
        }
        .card-detail {
            color: #aaa;
            font-size: 0.85rem;
            margin-top: 0.25rem;
        }
        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 0.4rem 0;
            border-bottom: 1px solid #0f3460;
        }
        .stat-row:last-child {
            border-bottom: none;
        }
        .stat-label {
            color: #888;
        }
        .stat-value {
            color: #eee;
            font-weight: 500;
        }
        .table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }
        .table th {
            background: #0f3460;
            padding: 0.5rem;
            text-align: left;
            color: #e94560;
            font-weight: 600;
        }
        .table td {
            padding: 0.5rem;
            border-bottom: 1px solid #0f3460;
        }
        .table tr:hover {
            background: #1a1a2e;
        }
        .tool-call {
            padding: 0.5rem;
            margin-bottom: 0.5rem;
            background: #1a1a2e;
            border-radius: 4px;
            border-left: 3px solid #3b82f6;
            font-size: 0.85rem;
        }
        .tool-call.error {
            border-left-color: #ef4444;
        }
        .tool-call.success {
            border-left-color: #4ade80;
        }
        .tool-call-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.25rem;
        }
        .tool-name {
            color: #4ade80;
            font-weight: 600;
        }
        .tool-timestamp {
            color: #888;
            font-size: 0.75rem;
        }
        .tool-args {
            color: #aaa;
            font-size: 0.8rem;
            margin-top: 0.25rem;
        }
        .message-log {
            max-height: 300px;
            overflow-y: auto;
        }
        .message-entry {
            padding: 0.4rem 0.6rem;
            margin-bottom: 0.25rem;
            background: #1a1a2e;
            border-radius: 4px;
            font-size: 0.8rem;
            font-family: 'Consolas', 'Monaco', monospace;
        }
        .message-entry .timestamp {
            color: #888;
            margin-right: 0.5rem;
        }
        .message-entry .direction {
            display: inline-block;
            padding: 0.1rem 0.4rem;
            border-radius: 3px;
            font-size: 0.7rem;
            margin-right: 0.5rem;
        }
        .message-entry .direction.incoming {
            background: #22c55e;
            color: #000;
        }
        .message-entry .direction.outgoing {
            background: #ef4444;
            color: #fff;
        }
        .summary-log {
            background: #16213e;
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem;
            max-height: 200px;
            overflow-y: auto;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 0.85rem;
        }
        .summary-log-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #0f3460;
        }
        .summary-log-header h3 {
            color: #e94560;
            font-size: 0.95rem;
        }
        .summary-entry {
            padding: 0.3rem 0;
            color: #aaa;
            border-bottom: 1px solid #0f3460;
        }
        .summary-entry:last-child {
            border-bottom: none;
        }
        .empty-state {
            color: #666;
            text-align: center;
            padding: 2rem;
        }
        .progress-bar {
            background: #0f3460;
            border-radius: 4px;
            height: 8px;
            overflow: hidden;
            margin-top: 0.25rem;
        }
        .progress-fill {
            background: #4ade80;
            height: 100%;
            transition: width 0.3s;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Civ V LLM Dashboard</h1>
        <div class="status-bar" id="statusBar">
            <div class="status-item">
                <div class="status-indicator" id="dllStatus"></div>
                <span class="status-label">DLL:</span>
                <span class="status-value" id="dllStatusText">Checking...</span>
            </div>
            <div class="status-item">
                <div class="status-indicator" id="mcpStatus"></div>
                <span class="status-label">MCP:</span>
                <span class="status-value" id="mcpStatusText">Checking...</span>
            </div>
            <div class="status-item">
                <div class="status-indicator" id="gameStatus"></div>
                <span class="status-label">Game:</span>
                <span class="status-value" id="gameStatusText">Checking...</span>
            </div>
            <div class="status-item">
                <span class="status-label">Turn:</span>
                <span class="status-value" id="turnNumber">-</span>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="panel">
            <div class="panel-header">
                <span>Game State</span>
            </div>
            <div class="panel-body" id="gameStatePanel">
                <div class="empty-state">Loading game state...</div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <span>LLM Activity</span>
            </div>
            <div class="panel-body" id="llmActivityPanel">
                <div class="section">
                    <div class="section-header" onclick="toggleSection('toolCallsSection')">
                        <span class="section-title">Recent Tool Calls</span>
                        <span class="section-toggle" id="toolCallsToggle">▼</span>
                    </div>
                    <div class="section-content" id="toolCallsSection">
                        <div id="toolCallsList">
                            <div class="empty-state">No tool calls yet</div>
                        </div>
                    </div>
                </div>
                <div class="section">
                    <div class="section-header" onclick="toggleSection('messageLogSection')">
                        <span class="section-title">Message Log</span>
                        <span class="section-toggle" id="messageLogToggle">▼</span>
                    </div>
                    <div class="section-content" id="messageLogSection">
                        <div class="message-log" id="messageLogList">
                            <div class="empty-state">No messages yet</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="summary-log">
        <div class="summary-log-header">
            <h3>Summary Log</h3>
        </div>
        <div id="summaryLogContent">
            <div class="summary-entry">Waiting for activity...</div>
        </div>
    </div>

    <script>
        const MCP_BASE = 'http://localhost:8765';
        const DASHBOARD_BASE = '';
        let refreshIntervals = {};

        function toggleSection(sectionId) {
            const section = document.getElementById(sectionId);
            const toggle = document.getElementById(sectionId.replace('Section', 'Toggle'));
            section.classList.toggle('collapsed');
            toggle.textContent = section.classList.contains('collapsed') ? '▶' : '▼';
        }

        function formatTimestamp(timestamp) {
            if (!timestamp) return 'N/A';
            const date = new Date(timestamp);
            return date.toLocaleTimeString();
        }

        function formatTimeAgo(timestamp) {
            if (!timestamp) return 'N/A';
            const date = new Date(timestamp);
            const now = new Date();
            const diff = Math.floor((now - date) / 1000);
            if (diff < 60) return `${diff}s ago`;
            if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
            return `${Math.floor(diff / 3600)}h ago`;
        }

        // System Status
        async function refreshSystemStatus() {
            try {
                const response = await fetch(`${DASHBOARD_BASE}/api/system_status`);
                const data = await response.json();
                
                // DLL Status
                const dllIndicator = document.getElementById('dllStatus');
                const dllText = document.getElementById('dllStatusText');
                if (data.dll_connected) {
                    dllIndicator.classList.remove('disconnected', 'offline');
                    dllText.textContent = 'Connected';
                } else {
                    dllIndicator.classList.add('disconnected');
                    dllIndicator.classList.remove('offline');
                    dllText.textContent = 'Disconnected';
                }

                // MCP Status
                const mcpIndicator = document.getElementById('mcpStatus');
                const mcpText = document.getElementById('mcpStatusText');
                if (data.mcp_online) {
                    mcpIndicator.classList.remove('disconnected', 'offline');
                    mcpText.textContent = 'Online';
                } else {
                    mcpIndicator.classList.add('offline');
                    mcpIndicator.classList.remove('disconnected');
                    mcpText.textContent = 'Offline';
                }

                // Game Status
                const gameIndicator = document.getElementById('gameStatus');
                const gameText = document.getElementById('gameStatusText');
                if (data.game_active) {
                    gameIndicator.classList.remove('disconnected', 'offline');
                    gameText.textContent = 'Active';
                } else {
                    gameIndicator.classList.add('offline');
                    gameIndicator.classList.remove('disconnected');
                    gameText.textContent = 'Inactive';
                }

                // Turn Number
                const turnNumber = document.getElementById('turnNumber');
                turnNumber.textContent = data.turn_number !== null ? data.turn_number : '-';
            } catch (e) {
                console.error('Failed to fetch system status:', e);
            }
        }

        // Game State
        async function refreshGameState() {
            try {
                const response = await fetch(`${DASHBOARD_BASE}/api/game_state_summary`);
                const data = await response.json();
                const panel = document.getElementById('gameStatePanel');

                if (data.error) {
                    panel.innerHTML = `<div class="empty-state">${data.error}</div>`;
                    return;
                }

                let html = '';

                // Session Info
                html += '<div class="section">';
                html += '<div class="section-header" onclick="toggleSection(\'sessionSection\')">';
                html += '<span class="section-title">Session Info</span>';
                html += '<span class="section-toggle" id="sessionToggle">▼</span>';
                html += '</div>';
                html += '<div class="section-content" id="sessionSection">';
                html += '<div class="card">';
                html += `<div class="stat-row"><span class="stat-label">Turn:</span><span class="stat-value">${data.turn_number !== null ? data.turn_number : 'N/A'}</span></div>`;
                html += `<div class="stat-row"><span class="stat-label">Player:</span><span class="stat-value">${data.player_name || 'N/A'}</span></div>`;
                html += `<div class="stat-row"><span class="stat-label">Game ID:</span><span class="stat-value">${data.game_id !== null ? data.game_id : 'N/A'}</span></div>`;
                html += `<div class="stat-row"><span class="stat-label">Session ID:</span><span class="stat-value">${data.session_id !== null ? data.session_id : 'N/A'}</span></div>`;
                html += '</div>';
                html += '</div>';
                html += '</div>';

                // Cities
                if (data.cities && data.cities.length > 0) {
                    html += '<div class="section">';
                    html += '<div class="section-header" onclick="toggleSection(\'citiesSection\')">';
                    html += `<span class="section-title">Cities (${data.cities.length})</span>`;
                    html += '<span class="section-toggle" id="citiesToggle">▼</span>';
                    html += '</div>';
                    html += '<div class="section-content" id="citiesSection">';
                    data.cities.forEach(city => {
                        html += '<div class="card">';
                        html += `<div class="card-title">${city.name || 'Unknown'}</div>`;
                        html += `<div class="card-detail">Pop: ${city.population || 'N/A'} | Production: ${city.current_production || city.producing || 'None'}</div>`;
                        if (city.food_per_turn !== undefined) {
                            html += `<div class="card-detail">Food: ${city.food_per_turn}/turn | Production: ${city.production_per_turn || 0}/turn</div>`;
                        }
                        html += '</div>';
                    });
                    html += '</div>';
                    html += '</div>';
                }

                // Units
                if (data.units && data.units.length > 0) {
                    html += '<div class="section">';
                    html += '<div class="section-header" onclick="toggleSection(\'unitsSection\')">';
                    html += `<span class="section-title">Units (${data.units.length})</span>`;
                    html += '<span class="section-toggle" id="unitsToggle">▼</span>';
                    html += '</div>';
                    html += '<div class="section-content" id="unitsSection">';
                    html += '<table class="table">';
                    html += '<thead><tr><th>Type</th><th>Position</th><th>Moves</th><th>HP</th></tr></thead>';
                    html += '<tbody>';
                    data.units.forEach(unit => {
                        const name = unit.unit_type_name || unit.name || unit.type || 'Unknown';
                        const moves = unit.moves_remaining ?? unit.moves ?? 'N/A';
                        const hp = unit.max_hit_points != null ? (unit.max_hit_points - (unit.damage || 0)) : (unit.hp ?? 'N/A');
                        const maxHp = unit.max_hit_points ?? unit.max_hp ?? 'N/A';
                        html += `<tr>`;
                        html += `<td>${name}</td>`;
                        html += `<td>(${unit.x}, ${unit.y})</td>`;
                        html += `<td>${moves}</td>`;
                        html += `<td>${hp}/${maxHp}</td>`;
                        html += `</tr>`;
                    });
                    html += '</tbody></table>';
                    html += '</div>';
                    html += '</div>';
                }

                // Technology
                if (data.current_tech || (data.available_techs && data.available_techs.length > 0)) {
                    html += '<div class="section">';
                    html += '<div class="section-header" onclick="toggleSection(\'techSection\')">';
                    html += '<span class="section-title">Technology</span>';
                    html += '<span class="section-toggle" id="techToggle">▼</span>';
                    html += '</div>';
                    html += '<div class="section-content" id="techSection">';
                    if (data.current_tech) {
                        html += '<div class="card">';
                        html += `<div class="card-title">Researching: ${data.current_tech.name || 'Unknown'}</div>`;
                        if (data.current_tech.turns !== undefined) {
                            html += `<div class="card-detail">Turns remaining: ${data.current_tech.turns}</div>`;
                        }
                        html += '</div>';
                    }
                    if (data.available_techs && data.available_techs.length > 0) {
                        html += '<div class="card">';
                        html += `<div class="card-title">Available Techs (${data.available_techs.length})</div>`;
                        data.available_techs.slice(0, 5).forEach(tech => {
                            html += `<div class="card-detail">${tech.name || 'Unknown'}${tech.turns ? ` (${tech.turns} turns)` : ''}</div>`;
                        });
                        if (data.available_techs.length > 5) {
                            html += `<div class="card-detail">... and ${data.available_techs.length - 5} more</div>`;
                        }
                        html += '</div>';
                    }
                    html += '</div>';
                    html += '</div>';
                }

                // Resources
                if (data.resources && (data.resources.strategic || data.resources.luxury)) {
                    html += '<div class="section">';
                    html += '<div class="section-header" onclick="toggleSection(\'resourcesSection\')">';
                    html += '<span class="section-title">Resources</span>';
                    html += '<span class="section-toggle" id="resourcesToggle">▼</span>';
                    html += '</div>';
                    html += '<div class="section-content" id="resourcesSection">';
                    if (data.resources.strategic && data.resources.strategic.length > 0) {
                        html += '<div class="card">';
                        html += '<div class="card-title">Strategic Resources</div>';
                        data.resources.strategic.forEach(res => {
                            html += `<div class="card-detail">${res.name || 'Unknown'}: ${res.amount || 0}</div>`;
                        });
                        html += '</div>';
                    }
                    if (data.resources.luxury && data.resources.luxury.length > 0) {
                        html += '<div class="card">';
                        html += '<div class="card-title">Luxury Resources</div>';
                        data.resources.luxury.forEach(res => {
                            html += `<div class="card-detail">${res.name || 'Unknown'}: ${res.amount || 0}</div>`;
                        });
                        html += '</div>';
                    }
                    html += '</div>';
                    html += '</div>';
                }

                if (html === '') {
                    html = '<div class="empty-state">No game state available</div>';
                }

                panel.innerHTML = html;
            } catch (e) {
                console.error('Failed to fetch game state:', e);
                document.getElementById('gameStatePanel').innerHTML = '<div class="empty-state">Error loading game state</div>';
            }
        }

        // LLM Activity
        async function refreshLLMActivity() {
            try {
                const response = await fetch(`${DASHBOARD_BASE}/api/llm_activity`);
                const data = await response.json();

                // Tool Calls
                const toolCallsList = document.getElementById('toolCallsList');
                if (data.tool_calls && data.tool_calls.length > 0) {
                    toolCallsList.innerHTML = data.tool_calls.map(call => {
                        const timestamp = formatTimestamp(call.timestamp);
                        const isError = call.result && (call.result.error || call.result.status === 'error');
                        const statusClass = isError ? 'error' : 'success';
                        const argsStr = call.arguments ? JSON.stringify(call.arguments).substring(0, 100) : '{}';
                        return `
                            <div class="tool-call ${statusClass}">
                                <div class="tool-call-header">
                                    <span class="tool-name">${call.tool || 'unknown'}</span>
                                    <span class="tool-timestamp">${timestamp}</span>
                                </div>
                                <div class="tool-args">Args: ${argsStr}${argsStr.length >= 100 ? '...' : ''}</div>
                            </div>
                        `;
                    }).join('');
                } else {
                    toolCallsList.innerHTML = '<div class="empty-state">No tool calls yet</div>';
                }

                // Message Log
                const messageLogList = document.getElementById('messageLogList');
                if (data.messages && data.messages.length > 0) {
                    messageLogList.innerHTML = data.messages.map(msg => {
                        const timestamp = formatTimestamp(msg.timestamp);
                        const direction = msg.direction || 'unknown';
                        const type = msg.type || 'unknown';
                        const summary = msg.summary || `${type} message`;
                        return `
                            <div class="message-entry">
                                <span class="timestamp">${timestamp}</span>
                                <span class="direction ${direction}">${direction}</span>
                                <span>${summary}</span>
                            </div>
                        `;
                    }).join('');
                } else {
                    messageLogList.innerHTML = '<div class="empty-state">No messages yet</div>';
                }
            } catch (e) {
                console.error('Failed to fetch LLM activity:', e);
            }
        }

        // Summary Log
        async function refreshSummaryLog() {
            try {
                const response = await fetch(`${DASHBOARD_BASE}/api/messages?limit=20&summary=true`);
                const data = await response.json();
                const content = document.getElementById('summaryLogContent');

                if (data.messages && data.messages.length > 0) {
                    content.innerHTML = data.messages.map(msg => {
                        const timestamp = formatTimestamp(msg.timestamp);
                        const summary = msg.summary || `${msg.type || 'message'}`;
                        return `<div class="summary-entry">[${timestamp}] ${summary}</div>`;
                    }).join('');
                    // Auto-scroll to bottom
                    const summaryLog = content.parentElement;
                    summaryLog.scrollTop = summaryLog.scrollHeight;
                } else {
                    content.innerHTML = '<div class="summary-entry">No activity yet</div>';
                }
            } catch (e) {
                console.error('Failed to fetch summary log:', e);
            }
        }

        // Setup auto-refresh
        function setupAutoRefresh() {
            // System status every 2 seconds
            refreshSystemStatus();
            refreshIntervals.systemStatus = setInterval(refreshSystemStatus, 2000);

            // Game state every 3 seconds
            refreshGameState();
            refreshIntervals.gameState = setInterval(refreshGameState, 3000);

            // LLM activity every 2 seconds
            refreshLLMActivity();
            refreshIntervals.llmActivity = setInterval(refreshLLMActivity, 2000);

            // Summary log every 2 seconds
            refreshSummaryLog();
            refreshIntervals.summaryLog = setInterval(refreshSummaryLog, 2000);
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            setupAutoRefresh();
        });
    </script>
</body>
</html>
"""


def create_dashboard_app(
    mcp_server: Optional[CivMCPServer] = None,
    game_state: Optional["GameState"] = None
) -> Flask:
    """Create and configure the Flask dashboard application.

    Args:
        mcp_server: CivMCPServer instance for tool execution
        game_state: GameState instance (single source of truth for metadata)
    """
    app = Flask(__name__)
    app.config["mcp_server"] = mcp_server
    app.config["game_state"] = game_state

    @app.route("/")
    def index():
        return render_template_string(DASHBOARD_HTML)

    @app.route("/api/system_status")
    def api_system_status():
        """Get system status (DLL pipe, MCP server, game connection)."""
        game_state_obj = app.config.get("game_state")
        mcp = app.config.get("mcp_server")

        # DLL connection status
        dll_connected = False
        if game_state_obj:
            dll_connected = game_state_obj.connected

        # MCP server status (check health endpoint)
        mcp_online = False
        if mcp:
            try:
                import urllib.request
                import urllib.error
                req = urllib.request.Request(f"http://localhost:8765/health", method="GET")
                with urllib.request.urlopen(req, timeout=1) as response:
                    if response.status == 200:
                        mcp_online = True
            except Exception:
                pass

        # Game active status
        game_active = False
        turn_number = None
        if game_state_obj:
            metadata = game_state_obj.get_metadata()
            game_active = metadata.get("turn_number") is not None and metadata.get("connected", False)
            turn_number = metadata.get("turn_number")

        return jsonify({
            "dll_connected": dll_connected,
            "mcp_online": mcp_online,
            "game_active": game_active,
            "turn_number": turn_number,
        })

    @app.route("/api/game_state_summary")
    def api_game_state_summary():
        """Get formatted game state summary."""
        mcp = app.config.get("mcp_server")
        game_state_obj = app.config.get("game_state")

        if not mcp:
            return jsonify({"error": "No MCP server available"})

        try:
            # Get game state from MCP server
            result = mcp.execute_tool("get_game_state", {})
            
            # Extract data from result
            state_data = result.get("result", result) if isinstance(result, dict) and "result" in result else result

            # Format response
            summary = {
                "turn_number": None,
                "player_name": None,
                "game_id": None,
                "session_id": None,
                "cities": [],
                "units": [],
                "current_tech": None,
                "available_techs": [],
                "resources": {
                    "strategic": [],
                    "luxury": []
                }
            }

            # Get metadata from game_state
            if game_state_obj:
                metadata = game_state_obj.get_metadata()
                summary["turn_number"] = metadata.get("turn_number")
                summary["player_name"] = metadata.get("player_name")
                summary["game_id"] = metadata.get("game_id")
                summary["session_id"] = metadata.get("session_id")

            # Extract cities
            if "cities" in state_data:
                summary["cities"] = state_data["cities"]
            elif "result" in state_data and "cities" in state_data["result"]:
                summary["cities"] = state_data["result"]["cities"]

            # Extract units
            if "units" in state_data:
                summary["units"] = state_data["units"]
            elif "result" in state_data and "units" in state_data["result"]:
                summary["units"] = state_data["result"]["units"]

            # Extract technology info
            if "current_tech" in state_data:
                summary["current_tech"] = state_data["current_tech"]
            elif "researching_tech" in state_data:
                summary["current_tech"] = state_data["researching_tech"]

            if "available_techs" in state_data:
                summary["available_techs"] = state_data["available_techs"]
            elif "researchable_techs" in state_data:
                summary["available_techs"] = state_data["researchable_techs"]

            # Extract resources (if available)
            if "resources" in state_data:
                summary["resources"] = state_data["resources"]
            elif "strategic_resources" in state_data or "luxury_resources" in state_data:
                summary["resources"] = {
                    "strategic": state_data.get("strategic_resources", []),
                    "luxury": state_data.get("luxury_resources", [])
                }

            return jsonify(summary)
        except Exception as e:
            return jsonify({"error": f"Failed to get game state: {e}"})

    @app.route("/api/llm_activity")
    def api_llm_activity():
        """Get recent LLM activity (tool calls and messages)."""
        from .game_logger import get_game_logger

        mcp = app.config.get("mcp_server")
        game_logger = get_game_logger()

        # Get recent tool requests
        tool_requests = game_logger.get_messages(
            message_type="tool_request"
        )

        # Get recent tool responses
        tool_responses = game_logger.get_messages(
            message_type="tool_response"
        )

        # Combine and sort by timestamp
        tool_calls = []
        tool_response_map = {}

        # Map responses by tool name and timestamp
        for response in tool_responses:
            tool_name = response.get("tool", "unknown")
            timestamp = response.get("timestamp", "")
            tool_response_map[tool_name] = response

        # Create tool call entries from requests
        for request in tool_requests[-30:]:  # Last 30 requests
            tool_name = request.get("tool", "unknown")
            timestamp = request.get("timestamp", "")
            arguments = request.get("arguments", {})
            
            # Find matching response
            result = None
            if tool_name in tool_response_map:
                result = tool_response_map[tool_name].get("result")

            tool_calls.append({
                "tool": tool_name,
                "timestamp": timestamp,
                "arguments": arguments,
                "result": result
            })

        # Sort by timestamp (most recent first)
        tool_calls.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        tool_calls = tool_calls[:30]  # Limit to 30

        # Get recent messages (tool_request and tool_response types)
        messages = []
        for msg_type in ["tool_request", "tool_response"]:
            msgs = game_logger.get_messages(message_type=msg_type)
            messages.extend(msgs)

        # Sort by timestamp and limit
        messages.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        messages = messages[:30]

        # Format messages with summary
        formatted_messages = []
        for msg in messages:
            msg_type = msg.get("type", "unknown")
            tool = msg.get("tool", "")
            direction = msg.get("direction", "unknown")
            
            if msg_type == "tool_request":
                summary = f"Tool request: {tool}"
            elif msg_type == "tool_response":
                result = msg.get("result", {})
                if result.get("error") or result.get("status") == "error":
                    summary = f"Tool response: {tool} (error)"
                else:
                    summary = f"Tool response: {tool} (success)"
            else:
                summary = f"{msg_type} message"

            formatted_messages.append({
                "timestamp": msg.get("timestamp"),
                "type": msg_type,
                "direction": direction,
                "summary": summary
            })

        return jsonify({
            "tool_calls": tool_calls,
            "messages": formatted_messages
        })

    @app.route("/api/messages")
    def api_messages():
        """Get messages from JSONL log with optional filters."""
        from .game_logger import get_game_logger

        message_type = request.args.get("type")
        direction = request.args.get("direction")
        turn_number = request.args.get("turn_number", type=int)
        player_id = request.args.get("player_id", type=int)
        game_id = request.args.get("game_id", type=int)
        session_id = request.args.get("session_id", type=int)
        current_game_only = request.args.get("current_game", type=bool, default=False)
        limit = int(request.args.get("limit", 100))
        summary_format = request.args.get("summary", type=bool, default=False)

        # Cap limit at 1000
        limit = min(limit, 1000)

        # If current_game_only and no explicit game_id, use current game from mcp_server
        mcp = app.config.get("mcp_server")
        if current_game_only and game_id is None and mcp:
            game_id = mcp.current_game_id

        # Get messages from singleton logger
        game_logger = get_game_logger()
        messages = game_logger.get_messages(
            message_type=message_type,
            player_id=player_id,
            game_id=game_id,
            session_id=session_id,
            turn_number=turn_number
        )

        # Filter by direction if specified
        if direction:
            messages = [msg for msg in messages if msg.get("direction") == direction]

        # Return most recent messages first, limited
        messages = list(reversed(messages))[:limit]

        # Format as summary if requested
        if summary_format:
            formatted_messages = []
            for msg in messages:
                msg_type = msg.get("type", "unknown")
                direction = msg.get("direction", "unknown")
                
                if msg_type == "turn_start":
                    turn = msg.get("turn", "?")
                    summary = f"Turn {turn} started"
                elif msg_type == "turn_complete":
                    turn = msg.get("turn", "?")
                    summary = f"Turn {turn} completed"
                elif msg_type == "notification":
                    notif_type = msg.get("notification_type", "notification")
                    summary = f"Notification: {notif_type}"
                elif msg_type == "action_result":
                    action_kind = msg.get("kind", "action")
                    success = msg.get("success", False)
                    summary = f"Action: {action_kind} ({'success' if success else 'failed'})"
                elif msg_type == "tool_request":
                    tool = msg.get("tool", "unknown")
                    summary = f"LLM called: {tool}"
                elif msg_type == "tool_response":
                    tool = msg.get("tool", "unknown")
                    result = msg.get("result", {})
                    if result.get("error") or result.get("status") == "error":
                        summary = f"Tool response: {tool} (error)"
                    else:
                        summary = f"Tool response: {tool} (success)"
                else:
                    summary = f"{msg_type} ({direction})"

                formatted_messages.append({
                    "timestamp": msg.get("timestamp"),
                    "type": msg_type,
                    "summary": summary
                })
            messages = formatted_messages

        return jsonify({
            "messages": messages,
            "count": len(messages),
            "game_id": game_id,
            "session_id": session_id,
            "filters": {
                "type": message_type,
                "direction": direction,
                "turn_number": turn_number,
                "player_id": player_id,
                "game_id": game_id,
                "session_id": session_id,
                "current_game_only": current_game_only,
                "limit": limit
            }
        })

    @app.route("/api/session")
    def api_session():
        """Get current game and session info."""
        game_state_obj = app.config.get("game_state")
        
        if game_state_obj:
            metadata = game_state_obj.get_metadata()
            return jsonify({
                "game_id": metadata["game_id"],
                "session_id": metadata["session_id"],
                "turn_number": metadata["turn_number"],
                "player_id": metadata["player_id"],
                "player_name": metadata["player_name"],
                "connected": metadata["connected"]
            })

        return jsonify({
            "game_id": None,
            "session_id": None,
            "turn_number": None,
            "player_id": None,
            "player_name": None,
            "connected": False
        })

    return app


def run_dashboard(
    host: str = "0.0.0.0",
    port: int = 5000,
    mcp_server: Optional[CivMCPServer] = None,
    debug: bool = False,
):
    """Run the Flask dashboard server.

    Args:
        host: Host to bind to
        port: Port to bind to
        mcp_server: CivMCPServer instance
        debug: Enable debug mode
    """
    app = create_dashboard_app(mcp_server)

    print(f"Dashboard running at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    import sys

    from .logging_setup import setup_logging

    setup_logging()

    host = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

    run_dashboard(host, port, debug=True)
