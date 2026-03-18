#!/bin/bash
# 快速测试脚本

echo "============================================"
echo "多 Agent 协作框架 - 系统测试"
echo "============================================"

echo ""
echo "1. 测试 SSH 连接..."
if timeout 10 ssh -o StrictHostKeyChecking=no -p 2222 zzc@192.168.130.33 "echo OK" 2>/dev/null | grep -q OK; then
    echo "   ✅ SSH 连接正常"
else
    echo "   ❌ SSH 连接失败"
    exit 1
fi

echo ""
echo "2. 测试远程 Gateway 端口..."
if timeout 5 nc -zv 192.168.130.33 18789 2>&1 | grep -q succeeded; then
    echo "   ✅ Gateway 端口开放"
else
    echo "   ❌ Gateway 端口未开放"
    exit 1
fi

echo ""
echo "3. 测试远程 OpenClaw..."
if ssh -o StrictHostKeyChecking=no -p 2222 zzc@192.168.130.33 "export NVM_DIR=\"\$HOME/.nvm\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\" && openclaw --version" 2>&1 | grep -q "OpenClaw"; then
    echo "   ✅ 远程 OpenClaw 正常"
else
    echo "   ❌ 远程 OpenClaw 异常"
    exit 1
fi

echo ""
echo "4. 测试任务路由器..."
python3 -c "
from scripts.task_router import TaskRouter
router = TaskRouter()
tests = [
    ('检查代码', 'reviewer'),
    ('rm -rf /', 'sandbox'),
    ('写个项目', 'local'),
]
for task, expected in tests:
    result = router.route(task)
    status = '✅' if result['target'] == expected else '❌'
    print(f'   {status} {task} -> {result[\"target\"]}')
"

echo ""
echo "============================================"
echo "测试完成！"
echo "============================================"