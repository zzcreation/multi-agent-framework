# OpenClaw 贡献指南

感谢您对 OpenClaw 项目的兴趣！我们欢迎各种形式的贡献。

## 如何贡献

### 报告 Bug

1. 搜索现有 issues 确认没有重复
2. 使用 Bug 模板创建 issue
3. 提供复现步骤和环境信息

### 提出新功能

1. 搜索现有 issues 和 PRs
2. 使用 Feature Request 模板创建 issue
3. 说明用例和期望行为

### 提交代码

1. Fork 本仓库
2. 创建功能分支: `git checkout -b feature/your-feature`
3. 编写代码并添加测试
4. 提交更改: `git commit -m 'Add some feature'`
5. Push 分支: `git push origin feature/your-feature`
6. 创建 Pull Request

## 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/zzcreation/multi-agent-framework.git
cd multi-agent-framework

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 启动开发服务器
python -m services.control_plane.server
```

## 代码规范

### Python

- 使用 Black 格式化代码
- 使用 isort 排序导入
- 使用类型注解
- 遵循 PEP 8

```bash
# 格式化
black .
isort .
mypy .
```

### 提交信息格式

```
type(scope): description

[optional body]

[optional footer]
```

类型 (type):
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 维护

示例:
```
feat(worker): 添加 worker 健康检查

- 添加 heartbeat 端点
- 实现健康状态报告
- 添加单元测试

Closes #123
```

## Pull Request 流程

1. 确保所有测试通过
2. 更新相关文档
3. 添加详细的 PR 描述
4. 等待 code review
5. 根据反馈修改
6. 合并后删除分支

## 命名规范

### 分支命名

- `feature/xxx` - 新功能
- `fix/xxx` - Bug 修复
- `docs/xxx` - 文档
- `refactor/xxx` - 重构

### 变量命名

- 变量: `snake_case`
- 常量: `UPPER_SNAKE_CASE`
- 类名: `PascalCase`
- 函数: `snake_case`

## 测试要求

- 新功能必须包含单元测试
- Bug 修复必须包含回归测试
- 保持测试覆盖率 > 80%

## 许可证

通过贡献代码，您同意将您的代码按 MIT 许可证发布。

---

感谢您的贡献！