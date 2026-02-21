#!/usr/bin/env python3
"""
跨平台会话列表扫描器
支持: macOS, Linux, Windows

功能：
- 扫描 ~/.kimi/sessions/ 下所有工作目录
- 统计消息数、大小
- 识别当前会话
- 输出 JSON 格式
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


def get_kimi_dir() -> Path:
    """获取跨平台的 kimi 数据目录"""
    share_dir = os.environ.get("KIMI_SHARE_DIR")
    if share_dir:
        return Path(share_dir)
    return Path.home() / ".kimi"


def normalize_path_for_hash(path: str) -> str:
    """
    统一路径格式用于计算哈希
    将 Windows 反斜杠转换为正斜杠，确保哈希一致
    """
    return Path(path).as_posix()


def get_workdir_hash(work_dir: str) -> str:
    """计算工作目录的 MD5 哈希（与 kimi-cli 一致）"""
    normalized = normalize_path_for_hash(work_dir)
    return hashlib.md5(normalized.encode()).hexdigest()


def get_file_info(file_path: Path) -> dict:
    """获取文件信息（跨平台）"""
    if not file_path.exists():
        return {"size": 0, "mtime": 0}
    
    stat = file_path.stat()
    return {
        "size": stat.st_size,
        "mtime": stat.st_mtime
    }


def format_size(size_bytes: int) -> str:
    """格式化文件大小（跨平台一致）"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_time(timestamp: float) -> str:
    """格式化时间（跨平台一致）"""
    if timestamp == 0:
        return "未知"
    
    dt = datetime.fromtimestamp(timestamp)
    now = datetime.now()
    
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    elif (now - dt).days == 1:
        return f"昨天 {dt.strftime('%H:%M')}"
    else:
        return dt.strftime("%m-%d")


def get_session_title(session_path: Path) -> str:
    """从 wire.jsonl 提取会话标题（第一条用户消息）"""
    wire_file = session_path / "wire.jsonl"
    if not wire_file.exists():
        return "未命名会话"
    
    try:
        with open(wire_file, 'r', encoding='utf-8', newline='') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    # 查找第一条用户消息
                    if data.get("role") == "user":
                        content = data.get("content", "")
                        # 处理 content 可能是 list 的情况
                        if isinstance(content, list):
                            content = "[复杂内容]"
                        elif isinstance(content, str):
                            content = content.strip().replace('\n', ' ')
                        else:
                            content = str(content)
                        # 清理内容，取前 20 字符
                        if len(content) > 20:
                            content = content[:20] + "..."
                        return content if content else "未命名会话"
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    
    return "未命名会话"


def get_last_preview(session_path: Path) -> str:
    """获取最后消息的预览"""
    context_file = session_path / "context.jsonl"
    if not context_file.exists():
        return ""
    
    try:
        with open(context_file, 'r', encoding='utf-8', newline='') as f:
            lines = f.readlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    role = data.get("role", "")
                    content = data.get("content", "")
                    
                    # 处理 content 可能是 list 的情况
                    if isinstance(content, list):
                        content = "[复杂内容]"
                    elif isinstance(content, str):
                        content = content.strip().replace('\n', ' ')
                    else:
                        content = str(content)
                    
                    if role == "user":
                        if len(content) > 30:
                            content = content[:30] + "..."
                        return f"用户说 \"{content}\"" if content else ""
                    elif role == "assistant":
                        if len(content) > 25:
                            content = content[:25] + "..."
                        return f"Kimi 回复了 {content}..." if content else ""
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    
    return ""


def count_messages(context_file: Path) -> int:
    """计算消息数"""
    if not context_file.exists():
        return 0
    
    try:
        with open(context_file, 'r', encoding='utf-8', newline='') as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def find_current_session(sessions: List[dict], cwd: str) -> Optional[str]:
    """
    识别当前会话
    1. 尝试环境变量 KIMI_SESSION_ID
    2. 当前目录最新会话
    """
    # 1. 环境变量
    current_id = os.environ.get("KIMI_SESSION_ID")
    if current_id:
        return current_id
    
    # 2. 当前目录最新会话
    cwd_hash = get_workdir_hash(cwd)
    cwd_sessions = [s for s in sessions if s.get("work_dir_hash") == cwd_hash]
    if cwd_sessions:
        return max(cwd_sessions, key=lambda s: s["mtime"])["id"]
    
    # 3. 全局最新（兜底）
    if sessions:
        return max(sessions, key=lambda s: s["mtime"])["id"]
    
    return None


def scan_all_sessions() -> dict:
    """
    跨平台扫描所有会话
    返回统一格式的数据结构
    """
    kimi_dir = get_kimi_dir()
    sessions_base = kimi_dir / "sessions"
    
    result = {
        "current_cwd": os.getcwd(),
        "kimi_dir": str(kimi_dir),
        "total": 0,
        "current_session_idx": None,
        "work_dirs": []
    }
    
    if not sessions_base.exists():
        return result
    
    # 读取 kimi.json 获取工作目录映射
    work_dirs_map = {}
    kimi_json = kimi_dir / "kimi.json"
    if kimi_json.exists():
        try:
            with open(kimi_json, 'r', encoding='utf-8', newline='') as f:
                data = json.load(f)
                for item in data.get("work_dirs", []):
                    path = item.get("path", "")
                    if path:
                        hash_val = get_workdir_hash(path)
                        work_dirs_map[hash_val] = path
        except Exception:
            pass
    
    # 扫描会话目录
    all_sessions = []
    
    for hash_dir in sessions_base.iterdir():
        if not hash_dir.is_dir():
            continue
        
        for session_dir in hash_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            context_file = session_dir / "context.jsonl"
            wire_file = session_dir / "wire.jsonl"
            
            # 获取统计信息
            ctx_info = get_file_info(context_file)
            wire_info = get_file_info(wire_file)
            
            all_sessions.append({
                "id": session_dir.name,
                "work_dir_hash": hash_dir.name,
                "path": str(session_dir),
                "mtime": wire_info["mtime"] or ctx_info["mtime"],
                "size": ctx_info["size"] + wire_info["size"],
                "message_count": count_messages(context_file),
                "title": get_session_title(session_dir),
                "last_preview": get_last_preview(session_dir)
            })
    
    # 识别当前会话
    current_id = find_current_session(all_sessions, os.getcwd())
    
    # 按工作目录分组并分配索引
    idx = 1
    processed_hashes = set()
    
    # 优先处理当前目录
    cwd_hash = get_workdir_hash(os.getcwd())
    if cwd_hash in [s["work_dir_hash"] for s in all_sessions]:
        processed_hashes.add(cwd_hash)
        dir_sessions = [s for s in all_sessions if s["work_dir_hash"] == cwd_hash]
        dir_sessions.sort(key=lambda x: x["mtime"], reverse=True)
        
        sessions_list = []
        for s in dir_sessions:
            is_current = (s["id"] == current_id)
            sessions_list.append({
                "idx": idx,
                "id": s["id"],
                "title": s["title"],
                "time": format_time(s["mtime"]),
                "is_current": is_current,
                "deletable": not is_current,
                "path": s["path"],
                "stats": {
                    "message_count": s["message_count"],
                    "size_human": format_size(s["size"]),
                    "size_bytes": s["size"]
                },
                "last_preview": s["last_preview"]
            })
            if is_current:
                result["current_session_idx"] = idx
            idx += 1
        
        work_dir = work_dirs_map.get(cwd_hash, f"<unknown:{cwd_hash}>")
        result["work_dirs"].append({
            "path": work_dir,
            "is_current_dir": True,
            "sessions": sessions_list
        })
        result["total"] += len(sessions_list)
    
    # 处理其他目录
    for hash_dir in sessions_base.iterdir():
        if not hash_dir.is_dir():
            continue
        if hash_dir.name in processed_hashes:
            continue
        
        dir_sessions = [s for s in all_sessions if s["work_dir_hash"] == hash_dir.name]
        if not dir_sessions:
            continue
        
        dir_sessions.sort(key=lambda x: x["mtime"], reverse=True)
        
        sessions_list = []
        for s in dir_sessions:
            is_current = (s["id"] == current_id)
            sessions_list.append({
                "idx": idx,
                "id": s["id"],
                "title": s["title"],
                "time": format_time(s["mtime"]),
                "is_current": is_current,
                "deletable": not is_current,
                "path": s["path"],
                "stats": {
                    "message_count": s["message_count"],
                    "size_human": format_size(s["size"]),
                    "size_bytes": s["size"]
                },
                "last_preview": s["last_preview"]
            })
            if is_current:
                result["current_session_idx"] = idx
            idx += 1
        
        work_dir = work_dirs_map.get(hash_dir.name, f"<unknown:{hash_dir.name}>")
        result["work_dirs"].append({
            "path": work_dir,
            "is_current_dir": False,
            "sessions": sessions_list
        })
        result["total"] += len(sessions_list)
    
    return result


if __name__ == "__main__":
    result = scan_all_sessions()
    print(json.dumps(result, indent=2, ensure_ascii=False))
