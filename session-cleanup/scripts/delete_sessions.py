#!/usr/bin/env python3
"""
跨平台删除指定会话
支持: macOS, Linux, Windows

用法:
  python delete_sessions.py --indices 2 3 4
  python delete_sessions.py --all-except 1

特性:
- 自动跳过当前会话（双重保护）
- 使用 shutil.rmtree 跨平台删除
- 处理 Windows 文件占用错误
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path


def validate_session_path(session_path: Path) -> tuple[bool, str]:
    """
    验证会话路径安全性
    返回: (是否有效, 错误信息)
    """
    # 1. 路径必须是绝对路径
    if not session_path.is_absolute():
        return False, "路径必须是绝对路径"
    
    # 2. 获取基础目录
    kimi_dir = get_kimi_dir()
    sessions_base = (kimi_dir / "sessions").resolve()
    
    # 3. 解析真实路径（消除符号链接），处理不存在的路径
    try:
        real_path = session_path.resolve()
        real_base = sessions_base.resolve()
    except (OSError, ValueError) as e:
        return False, f"路径解析失败: {e}"
    
    # 4. 必须是真实目录，不能是符号链接本身
    try:
        if session_path.exists() and session_path.resolve() != session_path:
            # 如果是链接，检查是否指向预期范围内
            try:
                real_path.relative_to(real_base)
            except ValueError:
                return False, "拒绝访问符号链接指向的外部目录"
    except OSError:
        pass
    
    # 5. 路径必须在 sessions 目录下
    try:
        real_path.relative_to(real_base)
    except ValueError:
        return False, f"路径超出允许范围: {real_path} 不在 {real_base} 下"
    
    # 6. 路径深度验证：必须是 sessions/<32位hash>/<session_id>
    try:
        relative = real_path.relative_to(real_base)
        parts = relative.parts
        
        if len(parts) != 2:
            return False, f"路径格式错误：期望 2 层目录，实际 {len(parts)} 层"
        
        hash_dir, session_id = parts
        
        # hash 必须是 32 位十六进制（MD5）
        if len(hash_dir) != 32:
            return False, f"hash 目录长度错误: {len(hash_dir)} (期望 32)"
        
        if not all(c in '0123456789abcdef' for c in hash_dir.lower()):
            return False, "hash 目录包含非法字符"
        
        # session_id 基本格式检查（不能包含路径分隔符）
        if '/' in session_id or '\\' in session_id or '..' in session_id:
            return False, "session ID 包含非法字符"
        
    except Exception as e:
        return False, f"路径验证异常: {e}"
    
    return True, ""


def get_extended_path(path: Path) -> Path:
    r"""
    Windows 长路径处理
    超过 240 字符时添加 \\?\ 前缀绕过 MAX_PATH 限制
    """
    if sys.platform != "win32":
        return path
    
    # 已经是扩展路径则不再处理
    path_str = str(path)
    if path_str.startswith("\\\\?\\"):
        return path
    
    # 必须是绝对路径才能添加前缀
    abs_path = path.resolve()
    abs_str = str(abs_path)
    
    if len(abs_str) > 240:
        # 使用 \\?\ 前缀启用长路径支持
        extended = "\\\\?\\" + abs_str
        return Path(extended)
    
    return abs_path


def get_kimi_dir() -> Path:
    """获取跨平台的 kimi 数据目录"""
    share_dir = os.environ.get("KIMI_SHARE_DIR")
    if share_dir:
        return Path(share_dir)
    return Path.home() / ".kimi"


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def delete_session(session_path: Path) -> dict:
    """
    跨平台删除会话目录（带安全验证）
    使用 shutil.rmtree 支持 Windows/macOS/Linux
    删除后会清理空的工作目录（hash目录）
    """
    result = {
        "path": str(session_path),
        "success": False,
        "error": None,
        "parent_removed": False
    }
    
    # 安全验证
    is_valid, error_msg = validate_session_path(session_path)
    if not is_valid:
        result["error"] = f"安全验证失败: {error_msg}"
        return result
    
    if not session_path.exists():
        result["error"] = "Session does not exist"
        return result
    
    # Windows 长路径处理
    extended_path = get_extended_path(session_path)
    parent_dir = extended_path.parent
    
    try:
        # shutil.rmtree 跨平台删除目录树
        shutil.rmtree(extended_path)
        result["success"] = True
        
        # 清理空的工作目录（hash目录）
        # 如果父目录为空或只包含 .DS_Store，则一并删除
        if parent_dir.exists() and parent_dir.name != "sessions":
            try:
                remaining = list(parent_dir.iterdir())
                # 过滤掉 .DS_Store 文件
                remaining = [f for f in remaining if f.name != ".DS_Store"]
                
                if not remaining:
                    # 目录为空，删除
                    shutil.rmtree(parent_dir)
                    result["parent_removed"] = True
            except Exception:
                # 清理父目录失败不影响主结果
                pass
                
    except PermissionError as e:
        # Windows 常见错误：文件被占用
        result["error"] = f"Permission denied (file may be in use): {e}"
    except OSError as e:
        # 其他系统错误
        result["error"] = f"OS error: {e}"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Delete Kimi sessions")
    parser.add_argument("--indices", nargs="+", type=int,
                        help="Session indices to delete")
    parser.add_argument("--all-except", type=int,
                        help="Delete all sessions except this index")
    
    args = parser.parse_args()
    
    if not args.indices and not args.all_except:
        parser.error("Must specify --indices or --all-except")
    
    # 导入 list_sessions 获取映射
    sys.path.insert(0, str(Path(__file__).parent))
    from list_sessions import scan_all_sessions
    
    sessions_data = scan_all_sessions()
    
    # 构建索引到会话的映射
    idx_to_session = {}
    for wd in sessions_data["work_dirs"]:
        for s in wd["sessions"]:
            idx_to_session[s["idx"]] = {
                **s,
                "work_dir": wd["path"]
            }
    
    # 确定要删除的索引
    to_delete = []
    if args.all_except:
        to_delete = [idx for idx in idx_to_session.keys() if idx != args.all_except]
    elif args.indices:
        to_delete = args.indices
    
    # 去重并保持顺序
    to_delete = list(dict.fromkeys(to_delete))
    
    # 执行删除
    results = {
        "deleted": [],
        "skipped": [],
        "failed": [],
        "total_freed_bytes": 0
    }
    
    kimi_dir = get_kimi_dir()
    
    for idx in to_delete:
        session = idx_to_session.get(idx)
        if not session:
            results["failed"].append({
                "idx": idx,
                "error": "Session not found"
            })
            continue
        
        # 保护当前会话（双重保护）
        if session.get("is_current"):
            results["skipped"].append({
                "idx": idx,
                "id": session["id"],
                "title": session.get("title", "Unknown"),
                "reason": "Current session (protected)"
            })
            continue
        
        # 保护不可删除的会话
        if not session.get("deletable", True):
            results["skipped"].append({
                "idx": idx,
                "id": session["id"],
                "title": session.get("title", "Unknown"),
                "reason": "Protected session"
            })
            continue
        
        # 查找实际路径
        session_path = None
        if "path" in session and session["path"]:
            session_path = Path(session["path"])
        else:
            # 从 work_dir 和 id 构建路径
            work_dir_hash = None
            for wd in sessions_data["work_dirs"]:
                for s in wd["sessions"]:
                    if s["idx"] == idx:
                        # 从原始路径提取 hash
                        if "path" in s:
                            work_dir_hash = Path(s["path"]).parent.name
                        break
                if work_dir_hash:
                    break
            
            if work_dir_hash:
                session_path = kimi_dir / "sessions" / work_dir_hash / session["id"]
        
        if not session_path or not session_path.exists():
            results["failed"].append({
                "idx": idx,
                "id": session.get("id", "Unknown"),
                "error": "Session path not found"
            })
            continue
        
        # 执行删除
        delete_result = delete_session(session_path)
        
        if delete_result["success"]:
            results["deleted"].append({
                "idx": idx,
                "id": session["id"],
                "title": session.get("title", "Unknown"),
                "size_human": session.get("stats", {}).get("size_human", "0 B"),
                "path": str(session_path)
            })
            results["total_freed_bytes"] += session.get("stats", {}).get("size_bytes", 0)
        else:
            results["failed"].append({
                "idx": idx,
                "id": session.get("id", "Unknown"),
                "title": session.get("title", "Unknown"),
                "error": delete_result["error"]
            })
    
    # 添加总计信息
    results["total_freed_human"] = format_size(results["total_freed_bytes"])
    results["delete_count"] = len(results["deleted"])
    results["skip_count"] = len(results["skipped"])
    results["fail_count"] = len(results["failed"])
    
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
