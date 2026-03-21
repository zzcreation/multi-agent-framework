#!/usr/bin/env python3
"""
远程 Agent 执行器
负责与远程 OpenClaw Gateway 通信，执行任务并获取结果
"""

import json
import logging
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import threading

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/remote_executor.log'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger('RemoteExecutor')

# 重试配置
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2  # 秒

CONFIG_PATH = Path(__file__).parent.parent / "config" / "remote-agent.json"

# 远程 OpenClaw 路径配置
REMOTE_NODE_PATH = "/home/zzc/.nvm/versions/node/v22.22.1/bin/node"
REMOTE_OPENCLAW_PATH = "/home/zzc/.nvm/versions/node/v22.22.1/bin/openclaw"
REMOTE_NVM_DIR = "/home/zzc/.nvm"

# ========== 性能优化：连接池、缓存、并发 ==========

# SSH 连接池（保持长连接）
class SSHConnectionPool:
    """SSH 连接池，维护持久连接"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._connection = None
        self._last_used = 0
        self._connection_timeout = 300  # 连接保持 5 分钟
        self._pool_lock = threading.Lock()
    
    def get_connection(self, ssh_cmd: list) -> Optional[subprocess.Popen]:
        """获取或创建持久 SSH 连接"""
        with self._pool_lock:
            now = time.time()
            # 检查现有连接是否有效
            if self._connection is not None:
                if now - self._last_used < self._connection_timeout:
                    # 测试连接是否还活着
                    try:
                        self._connection.stdin.write(b'echo "alive"\n')
                        self._connection.stdin.flush()
                        self._last_used = now
                        logger.debug("复用 SSH 连接")
                        return self._connection
                    except:
                        pass  # 连接已断开，需要重建
            
            # 创建新连接（保持会话）
            logger.info("创建新的 SSH 持久连接")
            try:
                self._connection = subprocess.Popen(
                    ssh_cmd + ['bash -i'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                self._last_used = now
                # 等待连接就绪
                time.sleep(0.5)
                return self._connection
            except Exception as e:
                logger.error(f"创建 SSH 连接失败: {e}")
                return None
    
    def close(self):
        """关闭连接"""
        with self._pool_lock:
            if self._connection:
                self._connection.terminate()
                self._connection = None

# 缓存装饰器
def cached(ttl: int = 300):
    """带 TTL 的缓存装饰器"""
    def decorator(func):
        cache = {}
        cache_lock = threading.Lock()
        
        def wrapper(*args, **kwargs):
            # 生成缓存 key
            key = str(args) + str(sorted(kwargs.items()))
            now = time.time()
            
            with cache_lock:
                if key in cache:
                    result, timestamp = cache[key]
                    if now - timestamp < ttl:
                        logger.debug(f"缓存命中: {func.__name__}")
                        return result
            
            # 执行函数
            result = func(*args, **kwargs)
            
            with cache_lock:
                cache[key] = (result, now)
            
            return result
        return wrapper
    return decorator

# 任务执行结果缓存
_task_result_cache: Dict[str, tuple] = {}
_task_cache_lock = threading.Lock()


# ========== RemoteExecutor 类的性能优化方法 ==========


def with_retry(max_retries: int = DEFAULT_MAX_RETRIES, 
               retry_delay: int = DEFAULT_RETRY_DELAY,
               retry_on: Optional[Callable] = None):
    """
    重试装饰器
    
    Args:
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
        retry_on: 自定义重试条件函数，接收异常参数，返回是否重试
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    # 检查是否需要重试
                    if retry_on and not retry_on(e):
                        logger.error(f"{func.__name__} 失败，不重试: {e}")
                        raise
                    
                    if attempt < max_retries:
                        logger.warning(f"{func.__name__} 失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}, {retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"{func.__name__} 最终失败: {e}")
            raise last_exception
        return wrapper
    return decorator


class RemoteExecutor:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or CONFIG_PATH
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_openclaw_cmd_prefix(self) -> str:
        """获取远程 OpenClaw 调用前缀"""
        return f'NVM_DIR={REMOTE_NVM_DIR} {REMOTE_NODE_PATH} {REMOTE_OPENCLAW_PATH}'
    
    def get_ssh_command(self) -> list:
        """获取 SSH 命令"""
        ssh = self.config.get('ssh_config', {})
        host = ssh.get('host', '192.168.130.33')
        user = ssh.get('user', 'zzc')
        port = ssh.get('port', 2222)
        return [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=60',
            '-o', 'ServerAliveInterval=10',
            '-p', str(port),
            f'{user}@{host}'
        ]
    
    def check_remote_connection(self, max_retries: int = DEFAULT_MAX_RETRIES) -> bool:
        """
        检查远程连接（带重试机制）
        
        Args:
            max_retries: 最大重试次数
            
        Returns:
            连接是否成功
        """
        def should_retry(e: Exception) -> bool:
            """SSH 连接异常时重试"""
            error_msg = str(e).lower()
            # 超时、连接拒绝、可恢复错误重试
            retryable = ['timeout', 'connection refused', 'connection reset', 'no route']
            return any(r in error_msg for r in retryable)
        
        @with_retry(max_retries=max_retries, retry_on=should_retry)
        def _check_once():
            result = subprocess.run(
                self.get_ssh_command() + ['echo', 'ok'],
                capture_output=True,
                text=True,
                timeout=30  # 增加到 30 秒
            )
            if result.returncode != 0 or 'ok' not in result.stdout:
                raise ConnectionError(f"SSH 返回异常: returncode={result.returncode}")
            return True
        
        try:
            result = _check_once()
            logger.info("远程连接检查成功")
            return True
        except Exception as e:
            logger.error(f"远程连接检查失败: {e}")
            return False
    
    def get_remote_status(self) -> dict:
        """获取远程 OpenClaw 状态"""
        logger.info("获取远程 OpenClaw 状态")
        ssh_cmd = self.get_ssh_command()
        
        # 获取远程 openclaw status
        cmd = ssh_cmd + [
            'NVM_DIR=/home/zzc/.nvm',
            REMOTE_NODE_PATH,
            REMOTE_OPENCLAW_PATH,
            'status'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            logger.debug(f"远程状态: returncode={result.returncode}")
            return {
                'connected': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            }
        except subprocess.TimeoutExpired:
            logger.error("获取远程状态超时")
            return {'connected': False, 'error': '请求超时'}
        except Exception as e:
            logger.error(f"获取远程状态异常: {e}")
            return {'connected': False, 'error': str(e)}
    
    def execute_on_remote(self, command: str) -> dict:
        """在远程主机执行命令 - 通过 SSH Shell"""
        ssh_cmd = self.get_ssh_command()
        
        # 使用远程 WSL2 的 OpenClaw 执行任务
        remote_cmd = f'''
export PATH=/home/zzc/.nvm/versions/node/v22.22.1/bin:$PATH
{command}
'''
        
        cmd = ssh_cmd + ['bash', '-c', remote_cmd]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'method': 'ssh_shell'
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': '执行超时', 'method': 'ssh_shell'}
        except Exception as e:
            return {'success': False, 'error': str(e), 'method': 'ssh_shell'}
    
    def test_remote_openclaw(self) -> bool:
        """测试远程 OpenClaw 是否正常工作"""
        logger.info("测试远程 OpenClaw")
        ssh_cmd = self.get_ssh_command()
        
        # 直接调用，不使用 bash -c
        cmd = ssh_cmd + [
            'NVM_DIR=/home/zzc/.nvm',
            REMOTE_NODE_PATH,
            REMOTE_OPENCLAW_PATH,
            '--version'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            output = result.stdout.strip()
            if result.returncode == 0 and output:
                logger.info(f"远程 OpenClaw 版本: {output}")
                print(f"远程 OpenClaw 版本: {output}")
                return True
            else:
                logger.error(f"测试失败: returncode={result.returncode}")
                print(f"测试失败: returncode={result.returncode}, stdout={repr(result.stdout)}, stderr={repr(result.stderr)}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            logger.error("测试远程 OpenClaw 超时")
            print("测试超时", file=sys.stderr)
        except Exception as e:
            logger.error(f"测试异常: {e}")
            print(f"测试失败: {e}", file=sys.stderr)
        return False
    
    def execute_via_gateway_api(self, prompt: str, agent_type: str = "assistant") -> dict:
        """
        通过 OpenClaw Gateway HTTP API 调用远程 Agent（带日志）
        
        Args:
            prompt: 任务提示词
            agent_type: Agent 类型 (assistant/reviewer/sandbox)
            
        Returns:
            执行结果字典
        """
        logger.info(f"通过 Gateway API 调用远程 Agent (type={agent_type})")
        
        gateway = self.config.get('remote_gateway', '')
        
        # 将 ws:// 转换为 http://
        if gateway.startswith('ws://'):
            http_gateway = gateway.replace('ws://', 'http://')
        else:
            http_gateway = gateway
        
        # 构建请求
        url = f"{http_gateway}/api/agent/turn"
        
        payload = {
            "message": prompt,
            "agent": agent_type,
            "stream": False
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                result = response.read().decode('utf-8')
                logger.info("Gateway API 调用成功")
                return {
                    'success': True,
                    'result': json.loads(result),
                    'agent_type': agent_type
                }
        except urllib.error.HTTPError as e:
            logger.error(f"Gateway API HTTP 错误: {e.code} {e.reason}")
            return {
                'success': False,
                'error': f"Gateway API HTTP 错误: {e.code} {e.reason}",
                'agent_type': agent_type
            }
        except urllib.error.URLError as e:
            logger.error(f"Gateway API 连接失败: {e}")
            return {
                'success': False,
                'error': f"Gateway API 调用失败: {str(e)}",
                'agent_type': agent_type
            }
        except json.JSONDecodeError as e:
            logger.error(f"Gateway API 响应 JSON 解析失败: {e}")
            return {
                'success': False,
                'error': f"响应解析失败: {str(e)}",
                'agent_type': agent_type
            }
        except Exception as e:
            logger.error(f"Gateway API 未知异常: {e}")
            return {
                'success': False,
                'error': str(e),
                'agent_type': agent_type
            }
    
    def execute_via_ssh_shell(self, command: str) -> dict:
        """
        通过 SSH Shell 执行命令（传统方式）
        """
        ssh_cmd = self.get_ssh_command()
        
        remote_cmd = f'''
export PATH=/home/zzc/.nvm/versions/node/v22.22.1/bin:$PATH
{command}
'''
        
        cmd = ssh_cmd + ['bash', '-c', remote_cmd]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'method': 'ssh_shell'
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': '执行超时', 'method': 'ssh_shell'}
        except Exception as e:
            return {'success': False, 'error': str(e), 'method': 'ssh_shell'}
    
    def execute_task(self, task: str, agent_type: str = "assistant", prefer_api: bool = True) -> dict:
        """
        执行任务，通过 SSH 调用远程 OpenClaw agent 命令（带增强错误处理）
        
        Args:
            task: 任务描述
            agent_type: Agent 类型
            prefer_api: 是否优先使用 Gateway API (目前使用 SSH 调用 agent 命令)
            
        Returns:
            执行结果字典
        """
        logger.info(f"开始执行远程任务 (agent_type={agent_type})")
        
        # 从配置获取实际的 agent_id
        agent_config = self.config.get('agents', {}).get(agent_type, {})
        agent_id = agent_config.get('agent_id', 'main')
        
        # 构建远程 OpenClaw agent 命令
        # 使用正确的 openclaw agent --message 格式
        escaped_task = task.replace('"', '\\"').replace('\n', '\\n')
        
        # 通过 SSH 执行远程 openclaw agent 命令
        ssh_cmd = self.get_ssh_command()
        
        # 远程命令：设置环境变量后调用 openclaw agent
        remote_cmd = f'''
export NVM_DIR=/home/zzc/.nvm
export PATH=/home/zzc/.nvm/versions/node/v22.22.1/bin:$PATH
{REMOTE_OPENCLAW_PATH} agent --message "{escaped_task}" --agent {agent_id} --json --timeout 300
'''
        
        cmd = ssh_cmd + ['bash', '-c', remote_cmd]
        
        def should_retry_ssh(e: Exception) -> bool:
            """SSH 执行异常时重试"""
            error_msg = str(e).lower()
            retryable = ['timeout', 'connection refused', 'connection reset', 'no route', 'permission denied']
            return any(r in error_msg for r in retryable)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                env={**subprocess.os.environ}  # 继承当前环境
            )
            
            # 增强的结果解析处理
            return self._parse_agent_result(result, agent_type, agent_id)
                
        except subprocess.TimeoutExpired:
            logger.error("远程任务执行超时")
            return {
                'success': False, 
                'error': '执行超时 (超过 300 秒)', 
                'method': 'ssh_openclaw_agent',
                'agent_type': agent_type
            }
        except FileNotFoundError as e:
            logger.error(f"SSH 命令未找到: {e}")
            return {
                'success': False, 
                'error': f'SSH 命令未找到: {e}', 
                'method': 'ssh_openclaw_agent',
                'agent_type': agent_type
            }
        except Exception as e:
            logger.error(f"远程任务执行异常: {e}")
            return {
                'success': False, 
                'error': str(e), 
                'method': 'ssh_openclaw_agent',
                'agent_type': agent_type
            }
    
    def _parse_agent_result(self, result: subprocess.CompletedProcess, agent_type: str, agent_id: str) -> dict:
        """
        增强的结果解析处理
        
        Args:
            result: subprocess 执行结果
            agent_type: Agent 类型
            agent_id: Agent ID
            
        Returns:
            解析后的结果字典
        """
        logger.debug(f"命令执行完成, returncode={result.returncode}")
        
        # 尝试解析 JSON 输出
        try:
            output = json.loads(result.stdout.strip()) if result.stdout.strip() else {}
            logger.info("成功解析 JSON 输出")
            return {
                'success': result.returncode == 0,
                'result': output,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'method': 'ssh_openclaw_agent',
                'agent_type': agent_type,
                'agent_id': agent_id
            }
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}, 返回原始输出")
            # 尝试提取部分有效 JSON
            partial_result = self._try_extract_json(result.stdout)
            if partial_result is not None:
                return {
                    'success': result.returncode == 0,
                    'result': partial_result,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode,
                    'parse_error': str(e),
                    'method': 'ssh_openclaw_agent',
                    'agent_type': agent_type,
                    'agent_id': agent_id
                }
            return {
                'success': result.returncode == 0,
                'result': result.stdout if result.stdout else result.stderr,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'parse_error': str(e),
                'method': 'ssh_openclaw_agent',
                'agent_type': agent_type,
                'agent_id': agent_id
            }
    
    def _try_extract_json(self, text: str) -> Optional[dict]:
        """
        尝试从文本中提取 JSON 对象
        
        Args:
            text: 待解析文本
            
        Returns:
            提取的 JSON 对象，失败返回 None
        """
        import re
        
        # 尝试找到 JSON 对象
        json_patterns = [
            r'\{[^{}]*\}',  # 简单对象
            r'\{\s*".*":\s*.*\}',  # 带引号键值
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        return None
    
    # ========== 性能优化方法 ==========
    
    @cached(ttl=60)
    def get_remote_skills(self) -> List[str]:
        """获取远程 Agent 可用技能列表（带缓存）"""
        logger.info("获取远程技能列表（缓存 60 秒）")
        ssh_cmd = self.get_ssh_command()
        
        cmd = ssh_cmd + [
            f'NVM_DIR={REMOTE_NVM_DIR} {REMOTE_NODE_PATH} {REMOTE_OPENCLAW_PATH} skills list'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                # 解析技能列表
                skills = [s.strip() for s in result.stdout.strip().split('\n') if s.strip()]
                return skills
        except Exception as e:
            logger.error(f"获取技能列表失败: {e}")
        return []
    
    def execute_tasks_parallel(self, tasks: List[dict], max_workers: int = 3) -> List[dict]:
        """
        并发执行多个任务
        
        Args:
            tasks: 任务列表，每个任务包含 task, agent_type
            max_workers: 最大并发数
            
        Returns:
            结果列表
        """
        logger.info(f"开始并发执行 {len(tasks)} 个任务（最多 {max_workers} 并发）")
        
        results = []
        
        def execute_single(task_dict: dict) -> dict:
            """执行单个任务"""
            task = task_dict.get('task', '')
            agent_type = task_dict.get('agent_type', 'assistant')
            return self.execute_task(task, agent_type)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {
                executor.submit(execute_single, task): task 
                for task in tasks
            }
            
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"任务执行异常: {e}")
                    results.append({
                        'success': False,
                        'error': str(e),
                        'task': task.get('task', '')[:50]
                    })
        
        logger.info(f"并发任务完成，成功 {sum(1 for r in results if r.get('success'))}/{len(results)}")
        return results
    
    def get_cached_remote_status(self, use_cache: bool = True) -> dict:
        """获取远程状态（带缓存）"""
        if use_cache:
            return self._get_cached_status()
        
        return self.get_remote_status()
    
    @cached(ttl=30)
    def _get_cached_status(self) -> dict:
        """缓存的状态获取（内部使用）"""
        return self.get_remote_status()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='远程 Agent 执行器')
    parser.add_argument('--check', action='store_true', help='检查远程连接')
    parser.add_argument('--status', action='store_true', help='获取远程状态')
    parser.add_argument('--test-openclaw', action='store_true', help='测试远程 OpenClaw')
    parser.add_argument('--exec', type=str, help='执行远程命令')
    
    args = parser.parse_args()
    executor = RemoteExecutor()
    
    if args.check:
        result = executor.check_remote_connection()
        print(f"远程连接: {'✅ 正常' if result else '❌ 失败'}")
        
    if args.status:
        result = executor.get_remote_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    if args.test_openclaw:
        result = executor.test_remote_openclaw()
        print(f"远程 OpenClaw: {'✅ 正常' if result else '❌ 失败'}")
        
    if args.exec:
        result = executor.execute_on_remote(args.exec)
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()