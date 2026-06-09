#!/usr/bin/env python3
"""
千问全自动同步方案 v2.0 - 完善版
自动检测、提取、保存、验证全流程
"""
import subprocess
import json
from datetime import datetime
import os
import re

OUTPUT_DIR = "/Users/xiaoxi/Documents/LLM_Wiki_Projects/My_Knowledge_Base/wiki/sources"
LOG_FILE = "/Users/xiaoxi/Documents/LLM_Wiki_Projects/My_Knowledge_Base/wiki/log.md"

def run_applescript(script):
    result = subprocess.run(['osascript', '-e', script], 
                          capture_output=True, text=True, timeout=30)
    return result.stdout.strip(), result.stderr.strip()

def activate_and_copy():
    """激活 Chrome 并复制内容"""
    print("1️⃣ 激活 Chrome...")
    run_applescript('tell application "Google Chrome" to activate')
    
    print("2️⃣ 发送 Cmd+A (全选)...")
    run_applescript('tell application "System Events" to keystroke "a" using command down')
    
    import time
    time.sleep(0.5)
    
    print("3️⃣ 发送 Cmd+C (复制)...")
    run_applescript('tell application "System Events" to keystroke "c" using command down')
    
    time.sleep(0.5)
    print("✅ 内容已复制到剪贴板")

def get_clipboard():
    """读取剪贴板"""
    result = subprocess.run(['pbpaste'], capture_output=True, text=True)
    return result.stdout

def extract_messages(text):
    """智能提取消息"""
    lines = text.split('\n')
    messages = []
    
    # 导航关键词
    skip_words = ['新建对话', '关于千问', 'API', '下载', '协议', '隐私政策', 
                  '智能体', '我的空间', '暂无对话', 'Google Chrome', '系统偏好设置']
    
    for line in lines:
        line = line.strip()
        # 过滤条件
        if len(line) < 20 or len(line) > 5000:
            continue
        if any(skip in line for skip in skip_words):
            continue
        if line.startswith('http') and len(line) < 100:
            continue
            
        messages.append(line)
    
    # 去重
    unique = []
    seen = set()
    for msg in messages:
        if msg not in seen:
            unique.append(msg)
            seen.add(msg)
    
    return unique[:50]  # 最多50条

def get_title(text):
    """从内容中提取标题"""
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if len(line) > 10 and len(line) < 100:
            if not any(skip in line for skip in ['http', 'Chrome', '新建']):
                return line[:60]
    return "千问对话"

def save_to_wiki(title, messages):
    """保存到 LLM-Wiki"""
    if not messages:
        return None
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    safe_title = re.sub(r'[^\w\s-]', '', title).strip()[:50]
    safe_title = re.sub(r'[-\s]+', '-', safe_title)
    
    if not safe_title:
        safe_title = "conversation"
    
    filename = f"{date_str}-qwen-{safe_title}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # 避免重复
    counter = 1
    while os.path.exists(filepath):
        filename = f"{date_str}-qwen-{safe_title}-{counter}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)
        counter += 1
    
    # 生成 Markdown
    content = f"""---
type: source
origin: qwen-chat
date: {date_str}
time: {datetime.now().strftime('%H:%M:%S')}
title: {title}
tags:
  - llm-wiki/source
  - source/qwen
---

# {title}

"""
    
    for i, msg in enumerate(messages):
        role = "**用户**" if i % 2 == 0 else "**千问**"
        content += f"{role}: {msg}\n\n"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 更新 log
    log_entry = f"""
## [{date_str}] 摄取 | 千问同步: {title}

- **摘要**: 从千问同步对话
- **来源**: [[sources/{filename}|{filename}]]
- **时间**: {datetime.now().strftime('%H:%M')}
- **方法**: 全自动化同步 v2

"""
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_entry)
    
    return filename, filepath, len(messages)

def verify_sync(filepath):
    """验证同步结果"""
    if not os.path.exists(filepath):
        return False, "文件不存在"
    
    size = os.path.getsize(filepath)
    if size < 100:
        return False, f"文件太小 ({size} 字节)"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if '**用户**' not in content or '**千问**' not in content:
        return False, "未找到对话标记"
    
    return True, f"文件正常 ({size} 字节)"

def main():
    print("=" * 70)
    print("🚀 千问全自动同步 v2.0 - 完善版")
    print("=" * 70)
    
    # 步骤 1: 激活并复制
    print("\n📋 步骤 1: 从 Chrome 获取内容")
    activate_and_copy()
    
    # 步骤 2: 读取剪贴板
    print("\n📋 步骤 2: 读取剪贴板内容")
    text = get_clipboard()
    
    if not text or len(text) < 100:
        print("❌ 剪贴板为空或内容太短")
        print("请确保 Chrome 中已打开千问对话页面")
        return False
    
    print(f"✅ 获取到 {len(text)} 字符")
    
    # 步骤 3: 提取消息
    print("\n📋 步骤 3: 提取对话消息")
    messages = extract_messages(text)
    print(f"✅ 提取到 {len(messages)} 条唯一消息")
    
    if len(messages) == 0:
        print("❌ 未提取到有效消息")
        return False
    
    # 显示预览
    print("\n📄 消息预览:")
    for i, msg in enumerate(messages[:3]):
        print(f"   {i+1}. {msg[:80]}...")
    
    # 步骤 4: 获取标题
    print("\n📋 步骤 4: 提取对话标题")
    title = get_title(text)
    print(f"✅ 标题: {title}")
    
    # 步骤 5: 保存
    print("\n📋 步骤 5: 保存到 LLM-Wiki")
    filename, filepath, count = save_to_wiki(title, messages)
    print(f"✅ 已保存: {filename}")
    print(f"   路径: {filepath}")
    
    # 步骤 6: 验证
    print("\n📋 步骤 6: 验证同步结果")
    success, msg = verify_sync(filepath)
    
    if success:
        print(f"✅ 验证通过: {msg}")
    else:
        print(f"⚠️ 验证警告: {msg}")
    
    # 汇总
    print("\n" + "=" * 70)
    print("📊 同步汇总")
    print("=" * 70)
    print(f"   原始字符: {len(text)}")
    print(f"   提取消息: {count} 条")
    print(f"   保存文件: {filename}")
    print(f"   文件大小: {os.path.getsize(filepath)} 字节")
    print(f"   完整路径: {filepath}")
    print(f"   验证状态: {'✅ 成功' if success else '⚠️ 需检查'}")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
