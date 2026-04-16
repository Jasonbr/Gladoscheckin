import requests
import json
import os
import logging
import datetime
import time
from typing import Dict, List, Optional, Tuple
from pypushdeer import PushDeer

def beijing_time_converter(timestamp):
    utc_dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    beijing_tz = datetime.timezone(datetime.timedelta(hours=8))
    beijing_dt = utc_dt.astimezone(beijing_tz)
    return beijing_dt.timetuple()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

root_logger = logging.getLogger()
for handler in root_logger.handlers:
    if hasattr(handler, 'formatter') and handler.formatter is not None:
        handler.formatter.converter = beijing_time_converter

logger = logging.getLogger(__name__)


# ENVIRONMENT
ENV_PUSH_KEY = "PUSHDEER_SENDKEY"
ENV_COOKIES = "GLADOS_COOKIES"
ENV_EXCHANGE_PLAN = "GLADOS_EXCHANGE_PLAN"

# API URLs (GLaDOS 已更换域名为 glados.one)
CHECKIN_URL = "https://glados.one/api/user/checkin"
STATUS_URL = "https://glados.one/api/user/status"
POINTS_URL = "https://glados.one/api/user/points"
EXCHANGE_URL = "https://glados.one/api/user/exchange"

# POST DATA
CHECKIN_DATA = {"token": "glados.cloud"} 

# Request Headers
HEADERS_TEMPLATE = {
    'referer': 'https://glados.one/console/checkin',
    'origin': "https://glados.one",
    'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    'content-type': 'application/json;charset=UTF-8',
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin'
}

# Exchange Plan Points
EXCHANGE_POINTS = {"plan100": 100, "plan200": 200, "plan500": 500} 

def load_config() -> Tuple[str, List[str], str]:
    push_key_env = os.environ.get(ENV_PUSH_KEY)
    raw_cookies_env = os.environ.get(ENV_COOKIES)
    exchange_plan_env = os.environ.get(ENV_EXCHANGE_PLAN)

    if not push_key_env:
        logger.warning(f"环境变量 '{ENV_PUSH_KEY}' 未设置。")
        push_key = ''
    else:
        push_key = push_key_env

    if not raw_cookies_env:
        logger.warning(f"环境变量 '{ENV_COOKIES}' 未设置。")
        cookies_list = []
    else:
        cookies_list = [cookie.strip() for cookie in raw_cookies_env.split('&') if cookie.strip()]
        if not cookies_list:
            raise ValueError(f"环境变量 '{ENV_COOKIES}' 已设置，但未包含任何有效的 Cookie。")

    if not exchange_plan_env:
        logger.warning(f"环境变量 '{ENV_EXCHANGE_PLAN}' 未设置，将使用默认兑换计划 'plan500'。")
        exchange_plan = "plan500"
    else: 
        if exchange_plan_env in EXCHANGE_POINTS:
             exchange_plan = exchange_plan_env
             logger.info(f"使用指定的兑换计划: {exchange_plan}")
        else:
            logger.warning(f"环境变量 '{ENV_EXCHANGE_PLAN}' 的值 '{exchange_plan_env}' 无效，将使用默认兑换计划 'plan500'。")
            exchange_plan = "plan500"


    logger.info(f"共加载了 {len(cookies_list)} 个 Cookie 用于签到。")
    logger.info(f"当前 {ENV_PUSH_KEY} {'已设置' if push_key_env else '未设置'}。")
    logger.info(f"当前 {ENV_EXCHANGE_PLAN}: {exchange_plan}。")

    return push_key, cookies_list, exchange_plan


def make_request(url: str, method: str, headers: Dict[str, str], data: Optional[Dict] = None, cookies: str = "", max_retries: int = 3) -> Optional[requests.Response]:
    """发送 HTTP 请求，支持重试机制"""
    session_headers = headers.copy()
    session_headers['cookie'] = cookies

    for attempt in range(max_retries):
        try:
            if method.upper() == 'POST':
                response = requests.post(url, headers=session_headers, data=json.dumps(data) if data else None, timeout=30)
            elif method.upper() == 'GET':
                response = requests.get(url, headers=session_headers, timeout=30)
            else:
                logger.error(f"不支持的 HTTP 方法: {method}")
                return None

            if response.ok:
                return response
            else:
                logger.warning(f"向 {url} 发起的请求失败，状态码 {response.status_code}。尝试 {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
        except requests.exceptions.Timeout as e:
            logger.warning(f"请求 {url} 超时 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            logger.error(f"向 {url} 发起请求时发生网络错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    logger.error(f"请求 {url} 在 {max_retries} 次尝试后仍然失败")
    return None


def checkin_and_process(cookie: str, exchange_plan: str) -> Tuple[str, str, str, str, str]:

    status_msg = "签到请求失败"
    points_gained = "0"
    remaining_days = "获取剩余天数失败"
    remaining_points = "获取剩余积分失败"
    exchange_msg = "兑换跳过或失败"

    # 验证 cookie 格式
    if not cookie or len(cookie) < 10:
        logger.error(f"Cookie 格式无效或为空")
        return "Cookie 无效", points_gained, remaining_days, remaining_points, exchange_msg

    checkin_response = make_request(CHECKIN_URL, 'POST', HEADERS_TEMPLATE, CHECKIN_DATA, cookies=cookie)
    if not checkin_response:
        return status_msg, points_gained, remaining_days, remaining_points, exchange_msg

    try:
        checkin_data = checkin_response.json()
        logger.debug(f"签到响应: {checkin_data}")

        response_code = checkin_data.get('code', -1)
        response_message = checkin_data.get('message', '无消息字段')
        points_gained = str(checkin_data.get('points', 0))

        # 根据 code 和 message 判断签到结果
        if response_code == 0:
            if "Checkin! Got" in response_message:
                status_msg = f"签到成功，获得 {points_gained} 积分"
            elif "Checkin Repeats!" in response_message:
                status_msg = "重复签到，明天再来"
                points_gained = "0"
            else:
                status_msg = f"签到成功: {response_message}"
        elif response_code == -2:
            status_msg = f"登录已过期，请更新 Cookie"
            logger.error(f"Cookie 已过期，响应: {checkin_data}")
        elif response_code == -1:
            status_msg = f"签到失败: {response_message}"
            points_gained = "0"
        else:
            status_msg = f"签到失败 (code={response_code}): {response_message}"
            points_gained = "0"
    except json.JSONDecodeError as e:
        logger.error(f"解析签到响应 JSON 失败: {e}")
        logger.error(f"响应内容: {checkin_response.text[:500]}")
        return status_msg, points_gained, remaining_days, remaining_points, exchange_msg
    except Exception as e:
        logger.error(f"处理签到响应时发生错误: {e}")
        return status_msg, points_gained, remaining_days, remaining_points, exchange_msg

    status_response = make_request(STATUS_URL, 'GET', HEADERS_TEMPLATE, cookies=cookie)
    if status_response:
        try:
            status_data = status_response.json()
            logger.debug(f"状态响应: {status_data}")

            # 检查响应 code
            status_code = status_data.get('code', -1)
            if status_code != 0:
                logger.warning(f"状态查询返回非成功码: {status_code}, message: {status_data.get('message', 'unknown')}")
                remaining_days = "获取剩余天数失败 (API返回错误)"
            else:
                data = status_data.get('data', {})
                left_days_float = data.get('leftDays', None)
                if left_days_float is not None:
                    try:
                        remaining_days = f"{int(float(left_days_float))} 天"
                    except (ValueError, TypeError) as e:
                        logger.error(f"解析剩余天数时出错: {left_days_float}, 错误: {e}")
                        remaining_days = "获取剩余天数失败 (数值转换错误)"
                else:
                    remaining_days = "获取剩余天数失败 (响应结构异常)"
        except json.JSONDecodeError as e:
            logger.error(f"解析状态响应 JSON 失败: {e}")
            logger.error(f"响应内容: {status_response.text[:500]}")
            remaining_days = "获取剩余天数失败 (JSON解析错误)"
        except Exception as e:
            logger.error(f"处理状态响应时发生错误: {e}")
            remaining_days = "获取剩余天数失败 (处理异常)"
    else:
        remaining_days = "获取剩余天数失败 (HTTP请求失败)"

    points_response = make_request(POINTS_URL, 'GET', HEADERS_TEMPLATE, cookies=cookie)
    points_data = {}  # 初始化 points_data 用于后续兑换判断
    if points_response:
        try:
            points_data = points_response.json()
            logger.debug(f"积分响应: {points_data}")

            # 检查响应 code
            points_code = points_data.get('code', -1)
            if points_code != 0:
                logger.warning(f"积分查询返回非成功码: {points_code}, message: {points_data.get('message', 'unknown')}")
                remaining_points = "获取剩余积分失败 (API返回错误)"
            else:
                points_float = points_data.get('points', None)
                if points_float is not None:
                    try:
                        remaining_points = f"{int(float(points_float))} 积分"
                    except (ValueError, TypeError) as e:
                        logger.error(f"解析剩余积分时出错: {points_float}, 错误: {e}")
                        remaining_points = "获取剩余积分失败 (数值转换错误)"
                else:
                    remaining_points = "获取剩余积分失败 (响应结构异常)"
        except json.JSONDecodeError as e:
            logger.error(f"解析积分响应 JSON 失败: {e}")
            logger.error(f"响应内容: {points_response.text[:500]}")
            remaining_points = "获取剩余积分失败 (JSON解析错误)"
        except Exception as e:
            logger.error(f"处理积分响应时发生错误: {e}")
            remaining_points = "获取剩余积分失败 (处理异常)"
    else:
        remaining_points = "获取剩余积分失败 (HTTP请求失败)"

    current_points_numeric = 0
    try:
        current_points_numeric = int(float(points_data.get('points', 0)))
    except (ValueError, TypeError):
        logger.warning(f"无法解析当前积分数值，可能影响兑换判断: {remaining_points}")

    required_points = EXCHANGE_POINTS.get(exchange_plan, 500)
    if current_points_numeric >= required_points:
        logger.info(f"开始兑换 {exchange_plan} 计划 (需要 {required_points} 积分)")
        exchange_response = make_request(EXCHANGE_URL, 'POST', HEADERS_TEMPLATE, {"planType": exchange_plan}, cookies=cookie)
        if exchange_response:
            try:
                exchange_data = exchange_response.json()
                logger.debug(f"兑换响应: {exchange_data}")
                code = exchange_data.get('code', -1)
                message = exchange_data.get('message', '未知错误')
                if code == 0:
                    exchange_msg = f"兑换成功：{exchange_plan}"
                elif code == -2:
                    exchange_msg = f"兑换失败：登录已过期"
                    logger.error(f"兑换时 Cookie 过期")
                elif code == -1:
                    exchange_msg = f"兑换失败: {message}"
                else:
                    exchange_msg = f"兑换失败: {exchange_plan}, 错误代码: {code}, 详情: {message}"
            except json.JSONDecodeError as e:
                logger.error(f"解析兑换响应 JSON 失败: {e}")
                logger.error(f"响应内容: {exchange_response.text[:500]}")
                exchange_msg = f"兑换响应解析失败: {exchange_plan}"
            except Exception as e:
                logger.error(f"处理兑换响应时发生错误: {e}")
                exchange_msg = f"兑换处理异常: {exchange_plan}"
        else:
            exchange_msg = f"兑换请求失败：{exchange_plan}"
    else:
        logger.info(f"积分不足以兑换 {exchange_plan}。所需: {required_points}, 当前: {current_points_numeric}")
        exchange_msg = f"积分不足，未兑换: {exchange_plan}"

    return status_msg, points_gained, remaining_days, remaining_points, exchange_msg


def format_push_content(results: List[Dict[str, str]]) -> Tuple[str, str]:

    success_count = sum(1 for r in results if "成功" in r['status'])
    fail_count = sum(1 for r in results if "失败" in r['status'] or "失败" in r['exchange'])
    repeat_count = sum(1 for r in results if "重复" in r['status'])

    title = f'GLaDOS 签到, 成功{success_count}, 失败{fail_count}, 重复{repeat_count}'

    content_lines = []
    for i, res in enumerate(results, 1):
        line_parts = [
            f"账号{i}:",
            f"P:{res['points']}",
            f"剩余天数:{res['days']}",
            f"总积分:{res['points_total']}",
            f"| {res['status']}",
            f"; {res['exchange']}"
        ]
        line = " ".join(line_parts)
        content_lines.append(line)

    content = "\n".join(content_lines)
    return title, content


def main():
    try:
        push_key, cookies_list, exchange_plan = load_config()

        if not cookies_list:
            logger.error("未找到有效的 Cookie，退出程序。")
            title, content = "# 未找到 cookies!", ""
        else:
            results = []
            for idx, cookie in enumerate(cookies_list, 1):
                logger.info(f"正在处理第 {idx} 个账户...")
                status, points, days, points_total, exchange = checkin_and_process(cookie, exchange_plan)
                results.append({
                    'status': status,
                    'points': points,
                    'days': days,
                    'points_total': points_total,
                    'exchange': exchange
                })

            title, content = format_push_content(results)
            logger.info(f"推送标题: {title}")
            logger.info(f"推送内容:\n{content}")

    except Exception as e:
        logger.error(f"主程序执行过程中发生未预期的错误: {e}")
        title, content = "# 脚本执行出错", str(e)

    if not push_key:
        logger.info(f"未设置 '{ENV_PUSH_KEY}'，跳过推送通知。")
    else:
        try:
            pushdeer = PushDeer(pushkey=push_key)
            pushdeer.send_text(title, desp=content)
            logger.info("推送通知发送成功。")
        except Exception as e:
            logger.error(f"发送推送通知失败: {e}")


if __name__ == '__main__':
    main()
