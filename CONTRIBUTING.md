# 贡献指南

感谢您对 OpenClaw Multi-Agent Framework 的关注！本指南将帮助您了解如何为项目做出贡献。

## 行为准则

我们承诺为社区提供无骚扰的体验。所有参与者应遵守以下原则：

- 使用友好和包容的语言
- 尊重不同的观点和经验
- 优雅地接受建设性批评
- 关注社区的最佳利益
- 对其他社区成员表现出同理心

## 如何贡献

### 报告 Bug

1. 搜索现有 Issue 确保没有重复
2. 使用 Bug 报告模板创建新 Issue
3. 包含以下信息：
   - 清晰的标题和描述
   - 重现步骤
   - 预期行为和实际行为
   - 环境信息（OS、Python 版本等）

### 提出新功能

1. 搜索现有 Feature Request
2. 使用功能请求模板创建 Issue
3. 详细描述：
   - 功能的用例
   - 建议的实现方式
   - 任何相关的设计文档

### 提交代码

#### 开发流程

```bash
# 1. 克隆仓库
git clone https://github.com/zzcreation/multi-agent-framework.git
cd multi-agent-framework

# 2. 创建功能分支
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name

# 3. 开发并测试
# ... 实现您的功能 ...

# 4. 提交更改
git add .
git commit -m "feat: 添加新功能描述"

# 5. 推送分支
git push -u origin feature/your-feature-name

# 6. 创建 Pull Request
```

#### 提交信息规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

类型 (type)：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `perf`: 性能优化
- `test`: 测试
- `chore`: 构建过程或辅助工具变动

示例：
```
feat(scheduler): 添加任务优先级支持

添加基于优先级的任务调度算法，支持高优先级任务优先执行。

Closes #123
```

#### 代码规范

- 遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- 使用 type hints
- 添加 docstrings
- 确保新代码有测试覆盖

#### 测试要求

- 单元测试：使用 `pytest`
- 运行测试：`pytest tests/`
- 测试覆盖率：新增代码覆盖率 > 80%

### Pull Request 流程

1. 创建 PR 并填写模板
2. 等待代码审查
3. 根据反馈修改代码
4. 获得批准后由维护者合并

## 开发环境设置

```bash
# 克隆项目
git clone https://github.com/zzcreation/multi-agent-framework.git
cd multi-agent-framework

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 运行测试
pytest

# 启动开发服务器
python main.py
```

## 文档贡献

- 使用 Markdown 格式
- 保持语言简洁明了
- 包含代码示例
- 翻译需要帮助请联系维护者

## 财务贡献

如果您想以其他方式支持项目，请联系维护者。

## 联系方式

- GitHub Issues: https://github.com/zzcreation/multi-agent-framework/issues
- 讨论区: https://github.com/zzcreation/multi-agent-framework/discussions

感谢您的贡献！