# Release 流程

本文档描述 OpenClaw 项目的版本发布流程。

## 版本号规则

采用语义化版本 (Semantic Versioning):

```
MAJOR.MINOR.PATCH
```

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向后兼容的新功能
- **PATCH**: 向后兼容的 Bug 修复

例如: `1.2.3` = Major 1, Minor 2, Patch 3

## 发布周期

- **补丁版本**: 每周或有需要时发布
- **次版本**: 每 2-4 周发布
- **主版本**: 每 6-12 个月评估是否需要

## 发布流程

### 1. 准备发布

```bash
# 确保在 main 分支
git checkout main
git pull origin main

# 运行完整测试
pytest --cov=services tests/

# 更新版本号
# 修改 setup.py 或 pyproject.toml 中的版本
```

### 2. 更新 CHANGELOG

```markdown
## [1.2.0] - 2026-03-27

### Added
- 新功能描述

### Changed
- 变更描述

### Fixed
- 修复描述

### Removed
- 移除的功能
```

### 3. 创建 Git Tag

```bash
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin v1.2.0
```

### 4. 构建发布

```bash
# 构建 sdist 和 wheel
python -m build

# 上传到 PyPI
twine upload dist/*
```

### 5. 创建 GitHub Release

在 GitHub 上创建 Release，包含：
- 版本号
- CHANGELOG 内容
- 下载链接

## 回滚流程

如需回滚:

```bash
# 撤销 tag
git push origin :refs/tags/v1.2.0

# 撤销 commit
git revert <commit-hash>
git push origin main
```

## 快速修复发布

对于紧急 Bug 修复:

```bash
# 创建 hotfix 分支
git checkout -b hotfix/fix-description

# 修复后
git checkout main
git merge hotfix/fix-description

# 打 tag
git tag -a v1.2.1 -m "Hotfix version 1.2.1"
git push origin v1.2.1
```

## 发布清单

- [ ] 所有测试通过
- [ ] 文档已更新
- [ ] CHANGELOG 已更新
- [ ] 版本号已更新
- [ ] Git tag 已创建
- [ ] PyPI 已发布
- [ ] GitHub Release 已创建
- [ ] 社区已通知

---

**维护者**: OpenClaw Team
**版本**: 1.0