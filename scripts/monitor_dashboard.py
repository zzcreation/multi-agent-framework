#!/usr/bin/env python3
"""
多 Agent 协作框架 - 网页监控面板
提供系统健康状态、远程 Agent 状态、任务执行统计
"""

import json
import subprocess
import time
import psutil
from pathlib import Path
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# 配置路径
PARENT_DIR = Path(__file__).parent.parent
CONFIG_DIR = PARENT_DIR / "config"
LOG_FILE = "/tmp/remote_executor.log"


def get_system_health():
    """获取系统健康状态"""
    try:
        # CPU 使用率
        cpu_percent = psutil.cpu_percent(interval=0.5)
        
        # 内存使用情况
        memory = psutil.virtual_memory()
        
        # 磁盘使用情况
        disk = psutil.disk_usage('/')
        
        # 本地 Gateway 状态
        gateway_status = "unknown"
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'openclaw-gateway'],
                capture_output=True, text=True, timeout=5
            )
            gateway_status = result.stdout.strip()
        except Exception:
            pass
    
    except Exception as e:
        return {'error': str(e)}
    
    return {
        'cpu_percent': cpu_percent,
        'memory_percent': memory.percent,
        'memory_used_gb': round(memory.used / (1024**3), 2),
        'memory_total_gb': round(memory.total / (1024**3), 2),
        'disk_percent': disk.percent,
        'disk_used_gb': round(disk.used / (1024**3), 2),
        'disk_total_gb': round(disk.total / (1024**3), 2),
        'gateway_status': gateway_status,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }


def get_remote_agent_status():
    """获取远程 Agent 状态"""
    remote_status = {
        'reachable': False,
        'openclaw_version': None,
        'uptime': None,
        'skills_count': 0,
        'error': None
    }
    
    try:
        # SSH 连接测试
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=10', '-p', '2222', 
             'zzc@192.168.130.33', 'echo "ok"'],
            capture_output=True, text=True, timeout=15
        )
        
        if result.returncode == 0:
            remote_status['reachable'] = True
            
            # 获取 OpenClaw 版本
            ver_result = subprocess.run(
                ['ssh', '-o', 'ConnectTimeout=10', '-p', '2222',
                 'zzc@192.168.130.33', 
                 'export NVM_DIR=/home/zzc/.nvm && '
                 '$HOME/.nvm/versions/node/v22.22.1/bin/openclaw --version'],
                capture_output=True, text=True, timeout=15
            )
            if ver_result.returncode == 0:
                remote_status['openclaw_version'] = ver_result.stdout.strip()
                
    except subprocess.TimeoutExpired:
        remote_status['error'] = 'SSH connection timeout'
    except Exception as e:
        remote_status['error'] = str(e)
    
    return remote_status


def get_task_statistics():
    """获取任务执行统计"""
    stats = {
        'total_tasks': 0,
        'successful_tasks': 0,
        'failed_tasks': 0,
        'recent_tasks': []
    }
    
    if not Path(LOG_FILE).exists():
        return stats
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 简单统计
        for line in lines:
            if 'execute_task' in line and '成功' in line:
                stats['successful_tasks'] += 1
            elif 'execute_task' in line and '失败' in line:
                stats['failed_tasks'] += 1
        
        stats['total_tasks'] = stats['successful_tasks'] + stats['failed_tasks']
        
        # 最近 5 条任务
        task_lines = [l for l in lines if 'execute_task' in l][-5:]
        for line in task_lines:
            stats['recent_tasks'].append(line.strip())
            
    except Exception as e:
        stats['error'] = str(e)
    
    return stats


# HTML 模板
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>多 Agent 协作框架 - 监控面板</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
              margin: 0; padding: 20px; background: #f5f5f5; }
        h1 { color: #333; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px;
              box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
                gap: 20px; }
        .stat { font-size: 32px; font-weight: bold; color: #2196F3; }
        .label { color: #666; font-size: 14px; }
        .status-ok { color: #4CAF50; }
        .status-error { color: #f44336; }
        .status-warning { color: #FF9800; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #fafafa; }
        .refresh-btn { 
            background: #2196F3; color: white; border: none; padding: 10px 20px; 
            border-radius: 4px; cursor: pointer; font-size: 14px; }
        .refresh-btn:hover { background: #1976D2; }
    </style>
</head>
<body>
    <h1>📊 多 Agent 协作框架 - 监控面板</h1>
    <button class="refresh-btn" onclick="location.reload()">🔄 刷新</button>
    
    <div class="grid" style="margin-top: 20px;">
        <div class="card">
            <h2>🖥️ 系统健康状态</h2>
            <table>
                <tr><td class="label">CPU 使用率</td><td class="stat">{{ system.cpu_percent }}%</td></tr>
                <tr><td class="label">内存使用</td><td>{{ system.memory_used_gb }} GB / {{ system.memory_total_gb }} GB</td></tr>
                <tr><td class="label">内存使用率</td><td>{{ system.memory_percent }}%</td></tr>
                <tr><td class="label">磁盘使用</td><td>{{ system.disk_used_gb }} GB / {{ system.disk_total_gb }} GB ({{ system.disk_percent }}%)</td></tr>
                <tr><td class="label">Gateway 状态</td><td class="{{ 'status-ok' if system.gateway_status == 'active' else 'status-warning'}}">{{ system.gateway_status }}</td></tr>
                <tr><td class="label">更新时间</td><td>{{ system.timestamp }}</td></tr>
            </table>
        </div>
        
        <div class="card">
            <h2>🌐 远程 Agent 状态</h2>
            <table>
                <tr><td class="label">连接状态</td>
                    <td class="{{ 'status-ok' if remote.reachable else 'status-error' }}">
                        {{ '✅ 在线' if remote.reachable else '❌ 离线' }}
                    </td></tr>
                <tr><td class="label">OpenClaw 版本</td><td>{{ remote.openclaw_version or '-' }}</td></tr>
                <tr><td class="label">错误信息</td><td>{{ remote.error or '-' }}</td></tr>
            </table>
        </div>
        
        <div class="card">
            <h2>📈 任务执行统计</h2>
            <table>
                <tr><td class="label">总任务数</td><td class="stat">{{ stats.total_tasks }}</td></tr>
                <tr><td class="label">成功</td><td class="status-ok">{{ stats.successful_tasks }}</td></tr>
                <tr><td class="label">失败</td><td class="status-error">{{ stats.failed_tasks }}</td></tr>
                <tr><td class="label">成功率</td><td>
                    {% if stats.total_tasks > 0 %}
                        {{ "%.1f"|format(stats.successful_tasks / stats.total_tasks * 100) }}%
                    {% else %}-
                    {% endif %}
                </td></tr>
            </table>
            
            {% if stats.recent_tasks %}
            <h3>最近任务</h3>
            <ul>
            {% for task in stats.recent_tasks %}
                <li style="font-size: 12px; color: #666; word-break: break-all;">{{ task[:100] }}...</li>
            {% endfor %}
            </ul>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""


@app.route('/')
def index():
    """主页"""
    system_health = get_system_health()
    remote_status = get_remote_agent_status()
    task_stats = get_task_statistics()
    
    return render_template_string(DASHBOARD_HTML, 
                           system=system_health, 
                           remote=remote_status, 
                           stats=task_stats)


@app.route('/api/status')
def api_status():
    """API: 返回 JSON 格式状态"""
    return jsonify({
        'system': get_system_health(),
        'remote': get_remote_agent_status(),
        'stats': get_task_statistics()
    })


if __name__ == '__main__':
    PORT = 8877
    
    print(f"""
🎉 启动监控面板...
📍 访问地址: http://localhost:{PORT}
""")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)