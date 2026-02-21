#!/usr/bin/env python3
"""
获取指定会话的最后消息预览
支持: macOS, Linux, Windows

用法: python get_preview.py --indices 2 3 4
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import deque


def get_kimi_dir() -> Path:
    """获取跨平台的 kimi 数据目录"""
    share_dir = os.environ.get("KIMI_SHARE_DIR")
    if share_dir:
        return Path(share_dir)
    return Path.home() / ".kimi"


def format_time(timestamp: float) -> str:
    """格式化时间"""
    if timestamp == 0:
        return "未知"
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%H:%M")


def get_last_messages(session_path: Path, count: int = 2) -> list:
    """
    从 context.jsonl 读取最后 N 条消息（内存优化版）
    返回: [{"role": "user/assistant", "time": "...", "content": "..."}]
    """
    context_file = session_path / "context.jsonl"
    if not context_file.exists():
        return []
    
    messages = []
    try:
        # 内存优化：使用 deque 只保留最后 N*5 行
        # 假设最多有 80% 的无效行（工具消息、空行等）
        buffer_size = count * 5
        if buffer_size < 10:
            buffer_size = 10
        
        with open(context_file, 'r', encoding='utf-8', newline='') as f:
            last_lines = deque(f, maxlen=buffer_size)
        
        # 从后往前解析有效消息
        for line in reversed(last_lines):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                role = data.get("role", "")
                
                if role not in ["user", "assistant"]:
                    continue
                
                content = data.get("content", "")
                
                # 处理 content 可能是 list 的情况
                if isinstance(content, list):
                    content = "[复杂内容...]"
                elif isinstance(content, str):
                    content = content.strip()
                else:
                    content = str(content)
                
                # 截断内容
                if len(content) > 200:
                    content = content[:200] + "..."
                
                # 获取时间（从 wire.jsonl 或文件 mtime）
                time_str = ""
                wire_file = session_path / "wire.jsonl"
                if wire_file.exists():
                    time_str = format_time(wire_file.stat().st_mtime)
                
                messages.insert(0, {
                    "role": role,
                    "time": time_str,
                    "content": content
                })
                
                if len(messages) >= count:
                    break
                    
            except json.JSONDecodeError:
                continue
    except Exception as e:
        return [{"role": "error", "time": "", "content": str(e)}]
    
    return messages


def get_session_info(session_path: Path) -> dict:
    """获取会话基本信息"""
    context_file = session_path / "context.jsonl"
    
    message_count = 0
    if context_file.exists():
        try:
            with open(context_file, 'r', encoding='utf-8', newline='') as f:
                message_count = sum(1 for line in f if line.strip())
        except Exception:
            pass
    
    return {
        "message_count": message_count,
        "exists": session_path.exists()
    }


def main():
    parser = argparse.ArgumentParser(description="Get session preview")
    parser.add_argument("--indices", nargs="+", type=int, required=True,
                        help="Session indices to preview")
    args = parser.parse_args()
    
    # 导入 list_sessions 获取映射
    sys.path.insert(0, str(Path(__file__).parent))
    from list_sessions import scan_all_sessions
    
    sessions_data = scan_all_sessions()
    
    # 构建索引到路径的映射
    idx_to_session = {}
    for wd in sessions_data["work_dirs"]:
        for s in wd["sessions"]:
            idx_to_session[s["idx"]] = {
                **s,
                "work_dir": wd["path"]
            }
    
    # 获取预览
    previews = []
    kimi_dir = get_kimi_dir()
    
    for idx in args.indices:
        session = idx_to_session.get(idx)
        if not session:
            previews.append({
                "idx": idx,
                "error": "Session not found"
            })
            continue
        
        # 构建路径
        work_dir_hash = Path(session.get("path", "")).parent.name
        session_path = kimi_dir / "sessions" / work_dir_hash / session["id"]
        
        if not session_path.exists():
            previews.append({
                "idx": idx,
                "title": session.get("title", "Unknown"),
                "error": "Session directory not found"
            })
            continue
        
        info = get_session_info(session_path)
        messages = get_last_messages(session_path, count=2)
        
        previews.append({
            "idx": idx,
            "title": session.get("title", "Unknown"),
            "message_count": info["message_count"],
            "messages": messages
        })
    
    print(json.dumps({"previews": previews}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
