# Session Cleanup Skill

一个用于 [Kimi Code CLI](https://github.com/moonshot-ai/kimi-cli) 的 Skill，安全清理历史会话，保护当前会话不被误删。

```
┌─────────────────────────────────────────────────────────┐
│  💬 共发现 5 个会话，当前会话已标记保护                    │
│                                                         │
│  📁 /Users/<username>/project-a (当前目录)                       │
│     [1] 💬 09:04  Skill 开发讨论  ← 当前会话             │
│     [2]    22:07  代码审查                               │
│                                                         │
│  📁 /Users/<username>/project-b                                  │
│     [3] ⭐ 14:30  API 设计  ← 该目录最新                 │
│     [4]    11:20  文档编写                               │
│     [5]    昨天   测试调试                               │
│                                                         │
│  请选择操作:                                             │
│    [1] 删除其他所有会话  [2] 保留各目录最新              │
│    [3] 仅清理当前目录    [4] 删除指定编号  [q] 取消      │
└─────────────────────────────────────────────────────────┘
```

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🛡️ **当前会话保护** | 正在进行的会话自动排除，无法误删 |
| 🔒 **四步强制确认** | 展示 → 选择 → 确认 → 执行，避免误操作 |
| 💡 **智能引导** | 误指当前会话时，提供 `/clear`、切换会话等替代方案 |
| 👁️ **会话预览** | 删除前可预览最后消息，帮助决策 |
| 🖥️ **跨平台兼容** | 支持 macOS、Linux、Windows |

## 📦 安装

### 方式一：软链接安装（推荐）

适合开发调试，修改立即生效：

```bash
# macOS/Linux
ln -s /path/to/session-cleanup-project/session-cleanup ~/.kimi/skills/session-cleanup

# Windows (PowerShell 管理员)
New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.kimi\skills\session-cleanup" `
  -Target "C:\path\to\session-cleanup-project\session-cleanup"
```

### 方式二：复制安装

适合使用稳定版本：

```bash
# macOS/Linux
cp -r /path/to/session-cleanup-project/session-cleanup ~/.kimi/skills/

# Windows
xcopy "C:\path\to\session-cleanup-project\session-cleanup" `
      "%USERPROFILE%\.kimi\skills\session-cleanup" /E /I
```

### 验证安装

```bash
ls -la ~/.kimi/skills/
# 应看到 session-cleanup 目录
```

## 🚀 使用

启动 Kimi CLI 后，说以下任意一句话即可触发：

- `"清理 session"`
- `"删除其他会话"`
- `"清理历史"`
- `"删除会话 1 2 3"`

### 交互流程

```
1️⃣  展示列表          查看所有会话，当前会话标记 💬
        ↓
2️⃣  选择操作          [1]删其他 [2]保最新 [3]清当前 [4]指定 [q]取消
        ↓
3️⃣  确认详情          预览要删的会话，按 [p] 查看最后消息
        ↓
4️⃣  执行删除          完成后报告释放的空间和消息数
```

### 特殊场景：误指当前会话

如果选择 `[4]` 并输入了当前会话编号（如 `"1 2"` 中的 `1` 是当前会话）：

```
══════════════════════════════════════════════════════════
  ⚠️  无法删除当前会话
══════════════════════════════════════════════════════════

你指定的删除列表包含当前会话 [1] Skill 开发讨论。

请选择以下方式：
  [1] 使用 /clear 清空当前会话（推荐）
  [2] 退出并新建会话
  [3] 切换到其他会话
  [s] 跳过当前，继续删除其他指定的([2])
  [n] 返回重新选择
  [q] 取消
```

## 📄 License

MIT License - 详见项目仓库

---

> **提示**：Skill 安装后，随时说 `"清理 session"` 即可开始使用！
