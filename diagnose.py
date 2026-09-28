#!/usr/bin/env python3
"""诊断 GLaDOS 签到问题的脚本"""

import requests
import json
import sys
import os

# 配置
CHECKIN_URL = "https://glados.space/api/user/checkin"
STATUS_URL = "https://glados.space/api/user/status"
POINTS_URL = "https://glados.space/api/user/points"

HEADERS_TEMPLATE = {
    'referer': 'https://glados.space/console/checkin',
    'origin': 'https://glados.space',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'content-type': 'application/json;charset=UTF-8',
    'accept': 'application/json, text/plain, */*',
}

CHECKIN_DATA = {"token": "glados.one"}

def diagnose():
    print("=" * 60)
    print("GLaDOS 签到诊断工具")
    print("=" * 60)
    
    # 1. 检查环境变量
    print("\n📋 环境变量检查:")
    print("-" * 60)
    
    push_key = os.environ.get('PUSHDEER_SENDKEY', '未设置')
    cookies = os.environ.get('GLADOS_COOKIES', '')
    exchange_plan = os.environ.get('GLADOS_EXCHANGE_PLAN', '未设置')
    
    print(f"  PUSHDEER_SENDKEY: {'✓ 已设置' if push_key != '未设置' else '✗ 未设置'}")
    print(f"  GLADOS_COOKIES: {'✓ 已设置 (' + str(len(cookies)) + ' 字符)' if cookies else '✗ 未设置'}")
    print(f"  GLADOS_EXCHANGE_PLAN: {exchange_plan}")
    
    if not cookies:
        print("\n⚠️ 警告: GLADOS_COOKIES 环境变量未设置，无法进行签到测试")
        print("\n请按以下步骤获取 Cookie:")
        print("  1. 登录 https://glados.space")
        print("  2. 进入签到页面")
        print("  3. 按 F12 打开开发者工具")
        print("  4. 切换到 Network 标签")
        print("  5. 刷新页面")
        print("  6. 找到 checkin 请求")
        print("  7. 复制 Request Headers 中的 Cookie 值")
        return False
    
    # 2. 测试 Cookie 有效性
    print("\n\n🔍 Cookie 有效性测试:")
    print("-" * 60)
    
    # 测试状态查询
    headers = HEADERS_TEMPLATE.copy()
    headers['cookie'] = cookies
    
    try:
        response = requests.get(STATUS_URL, headers=headers, timeout=10)
        result = response.json()
        
        if result.get('code') == 0:
            data = result.get('data', {})
            email = data.get('email', '未知')
            left_days = data.get('leftDays', '未知')
            level = data.get('level', '未知')
            
            print(f"  ✓ Cookie 有效!")
            print(f"  用户邮箱: {email}")
            print(f"  剩余天数: {left_days}")
            print(f"  等级: {level}")
        else:
            print(f"  ✗ Cookie 无效或已过期")
            print(f"  错误代码: {result.get('code')}")
            print(f"  错误信息: {result.get('message')}")
            print("\n⚠️ 请更新您的 GLADOS_COOKIES 环境变量")
            return False
    except Exception as e:
        print(f"  ✗ 请求失败: {e}")
        return False
    
    # 3. 测试签到（如果今天还没签到）
    print("\n\n📡 签到测试:")
    print("-" * 60)
    
    try:
        response = requests.post(CHECKIN_URL, headers=headers, json=CHECKIN_DATA, timeout=10)
        result = response.json()
        
        code = result.get('code')
        message = result.get('message', '')
        
        if code == 0:
            if "Checkin! Got" in message:
                points = result.get('points', 0)
                print(f"  ✓ 签到成功!")
                print(f"  获得积分: {points}")
            elif "Checkin Repeats" in message:
                print(f"  ✓ 今天已经签到过了")
                print(f"  提示: {message}")
            else:
                print(f"  ✓ 签到请求成功")
                print(f"  响应: {message}")
        elif code == 1:
            print(f"  ✓ 今天已经签到过了")
            print(f"  提示: {message}")
        elif code == 4:
            reason = result.get('reason', 'unknown')
            login_device = result.get('loginDevice', 'unknown')
            current_device = result.get('currentDevice', 'unknown')
            print(f"  ✗ 设备不匹配 (device-mismatch)")
            print(f"  登录设备: {login_device}, 当前设备: {current_device}")
            print(f"  提示: {message}")
        elif code == -2:
            print(f"  ✗ Cookie 过期")
            print(f"  提示: {message}")
        else:
            print(f"  ? 未知的响应代码: {code}")
            print(f"  消息: {message}")
    except Exception as e:
        print(f"  ✗ 签到请求失败: {e}")
    
    # 4. 查询积分
    print("\n\n💰 积分查询:")
    print("-" * 60)
    
    try:
        response = requests.get(POINTS_URL, headers=headers, timeout=10)
        result = response.json()
        
        if result.get('code') == 0:
            points = result.get('points', 0)
            print(f"  当前积分: {points}")
        else:
            print(f"  无法获取积分: {result.get('message')}")
    except Exception as e:
        print(f"  请求失败: {e}")
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)
    return True

if __name__ == '__main__':
    diagnose()
