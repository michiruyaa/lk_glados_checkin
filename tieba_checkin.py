#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度贴吧自动签到脚本（基于 TiebaLite API）

功能：
- 使用浏览器复制的完整 Cookie 自动提取 BDUSS + STOKEN 登录
- 获取关注吧列表及签到状态
- 对未签到的吧逐个触发签到

Cookie 提供方式（按优先级）：
1. 环境变量 TIEBA_COOKIE（适合 GitHub Actions）
2. 同目录下 tieba_cookie.txt 文件（推荐本地测试，直接粘贴浏览器 Cookie）
"""

import hashlib
import logging
import os
import random
import re
import sys
import time
import uuid
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Optional

import requests

# ==================== 日志配置 ====================

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ==================== 常量定义 ====================

BASE_URL = "http://c.tieba.baidu.com"
HEADERS = {
    "User-Agent": "bdtb for Android 12.41.7.1",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cookie": "ka=open",
    "Pragma": "no-cache",
}
APP_SECRET = "tiebaclient!!!"
CLIENT_VERSION = "12.41.7.1"


# ==================== 工具函数 ====================

def load_cookie() -> str:
    """
    读取原始 Cookie 字符串。
    优先级：环境变量 TIEBA_COOKIE > tieba_cookie.txt
    """
    # 1. 环境变量
    env_cookie = os.environ.get("TIEBA_COOKIE", "").strip()
    if env_cookie:
        log.info("从环境变量 TIEBA_COOKIE 读取 Cookie")
        return env_cookie

    # 2. 同目录下的 tieba_cookie.txt
    txt_path = Path(__file__).parent / "tieba_cookie.txt"
    if txt_path.exists():
        cookie = txt_path.read_text(encoding="utf-8").strip()
        if cookie:
            log.info(f"从文件 {txt_path.name} 读取 Cookie")
            return cookie

    return ""


def parse_cookie_string(cookie_str: str) -> dict[str, str]:
    """
    从 Cookie 字符串中解析出 BDUSS 和 STOKEN。
    支持格式: "BDUSS=xxx; STOKEN=yyy" 或单条 Cookie 值。
    """
    jar: dict[str, str] = {}
    cookie_str = (cookie_str or "").strip()
    if not cookie_str:
        return jar

    # 尝试标准 Cookie 解析
    try:
        c = SimpleCookie()
        c.load(cookie_str)
        for k, morsel in c.items():
            jar[k] = morsel.value
        if "BDUSS" in jar or "STOKEN" in jar:
            return jar
    except Exception:
        pass

    # 兜底：正则提取 key=value
    for match in re.finditer(r"([A-Za-z0-9_]+)=([^;]+)", cookie_str):
        jar[match.group(1)] = match.group(2).strip()

    return jar


def calculate_sign(params: dict[str, str]) -> str:
    """
    计算贴吧 API 签名。
    规则：将所有参数按 key=value 字符串排序后拼接（无 & 分隔符），
    末尾追加 APP_SECRET，再取 MD5。
    """
    # 过滤空值，按 key=value 字符串排序
    pairs = sorted([f"{k}={v}" for k, v in params.items() if v is not None])
    raw = "".join(pairs) + APP_SECRET
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def build_request_body(
    extra_params: dict[str, str], bduss: str, stoken: str
) -> dict[str, str]:
    """构建请求体：合并通用参数、额外参数、st 参数，并计算 sign"""
    # 通用参数（参考 TiebaLite OFFICIAL_TIEBA_API）
    common = {
        "BDUSS": bduss,
        "stoken": stoken,
        "_client_type": "2",
        "_client_version": CLIENT_VERSION,
        "_client_id": f"wappc_{int(time.time() * 1000)}_{random.randint(0, 999)}",
        "_phone_imei": "000000000000000",
        "net_type": "1",
        "cuid": uuid.uuid4().hex[:16].upper(),
        "cuid_galaxy2": uuid.uuid4().hex[:16].upper(),
        "cuid_gid": "",
        "from": "tieba",
        "timestamp": str(int(time.time() * 1000)),
        "_os_version": "14",
        "model": "PythonScript",
        "brand": "Python",
        "baiduid": uuid.uuid4().hex,
        "cmode": "1",
        "mac": "02:00:00:00:00:00",
    }

    merged = {**common, **extra_params}

    # 添加 st 参数（参考 StParamInterceptor）
    num = random.randint(100, 850)
    merged["stErrorNums"] = "1"
    merged["stMethod"] = "1"
    merged["stMode"] = "1"
    merged["stTimesNum"] = "1"
    merged["stTime"] = str(num)
    merged["stSize"] = str(int((random.random() * 8 + 0.4) * num))

    # 计算签名
    merged["sign"] = calculate_sign(merged)
    return merged


def parse_api_response(resp: requests.Response) -> dict[str, Any]:
    """解析 API 响应"""
    try:
        data = resp.json()
    except Exception as e:
        raise ValueError(f"响应解析失败: {e}, 内容: {resp.text[:200]}")
    if not isinstance(data, dict):
        raise ValueError(f"响应不是 JSON 对象: {data!r}")
    return data


# ==================== API 客户端 ====================

class TiebaClient:
    def __init__(self, bduss: str, stoken: str, timeout: int = 30):
        self.bduss = bduss
        self.stoken = stoken
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.tbs: Optional[str] = None
        self.uid: Optional[str] = None
        self.user_name: Optional[str] = None

    def _post(self, path: str, extra_params: dict[str, str], retry: int = 3) -> dict[str, Any]:
        """发送 POST 请求"""
        url = f"{BASE_URL}{path}"
        body = build_request_body(extra_params, self.bduss, self.stoken)

        last_err: Optional[Exception] = None
        for attempt in range(1, retry + 1):
            try:
                resp = self.session.post(url, data=body, timeout=self.timeout)
                resp.raise_for_status()
                return parse_api_response(resp)
            except Exception as e:
                last_err = e
                log.warning(f"请求失败 {path} (尝试 {attempt}/{retry}): {e}")
        raise RuntimeError(f"请求失败 {path}: {last_err}")

    def login(self) -> bool:
        """
        使用 BDUSS + STOKEN 获取 tbs 和用户信息。
        对应 TiebaLite 的 /c/s/login。
        """
        log.info("正在获取登录信息...")
        data = self._post(
            "/c/s/login",
            {
                "bdusstoken": f"{self.bduss}|null",
                "user_id": "",
                "channel_id": "",
                "channel_uid": "",
                "authsid": "",
            },
        )

        error_code = str(data.get("error_code", ""))
        if error_code != "0":
            log.error(f"登录失败: {data.get('error_msg', '未知错误')} (code={error_code})")
            return False

        anti = data.get("anti", {})
        self.tbs = anti.get("tbs", "")
        user = data.get("user", {})
        self.uid = str(user.get("id", ""))
        self.user_name = user.get("name", "")

        if not self.tbs:
            log.error("登录成功但未获取到 tbs")
            return False

        log.info(f"登录成功: {self.user_name} (uid={self.uid})")
        return True

    def get_forum_guide(self) -> list[dict[str, Any]]:
        """
        获取关注吧列表及签到状态。
        对应 TiebaLite 的 /c/f/forum/forumGuide。
        """
        if not self.tbs:
            raise RuntimeError("未获取 tbs，请先调用 login()")

        log.info("正在获取关注吧列表...")
        data = self._post(
            "/c/f/forum/forumGuide",
            {
                "sort_type": "3",
                "call_from": "4",
                "page_no": "0",
                "res_num": "200",
                "top_forum_num": "0",
                "tbs": self.tbs,
            },
        )

        error_code = str(data.get("error_code", ""))
        if error_code != "0":
            log.error(f"获取关注吧失败: {data.get('error_msg', '未知错误')} (code={error_code})")
            return []

        like_forum = data.get("like_forum", [])
        log.info(f"共获取到 {len(like_forum)} 个关注吧")
        return like_forum

    def sign(self, forum_id: str, forum_name: str) -> tuple[bool, str]:
        """
        对指定吧进行签到。
        对应 TiebaLite 的 /c/c/forum/sign。
        返回: (是否成功, 提示信息)
        """
        if not self.tbs:
            raise RuntimeError("未获取 tbs，请先调用 login()")

        data = self._post(
            "/c/c/forum/sign",
            {
                "fid": forum_id,
                "kw": forum_name,
                "tbs": self.tbs,
            },
        )

        error_code = str(data.get("error_code", ""))
        error_msg = data.get("error_msg", "")

        if error_code == "0":
            user_info = data.get("user_info", {})
            sign_rank = user_info.get("user_sign_rank", "")
            cont_sign_num = user_info.get("cont_sign_num", "")
            return True, f"签到成功 (排名: {sign_rank}, 连续: {cont_sign_num}天)"

        # 160002 是常见的"已经签到"错误码
        if error_code in ("160002", "340006") or "已经签到" in error_msg or "已签到" in error_msg:
            return True, f"已签到 ({error_msg})"

        return False, f"签到失败: {error_msg} (code={error_code})"


# ==================== 签到主逻辑 ====================

def run_checkin() -> tuple[bool, str]:
    timeout = int(os.environ.get("TIEBA_TIMEOUT", "30").strip() or "30")

    # 读取原始 Cookie 字符串
    cookie_str = load_cookie()
    if not cookie_str:
        return (
            False,
            "未找到 Cookie，请通过以下任一方式配置：\n"
            "1. 环境变量 TIEBA_COOKIE\n"
            "2. 同目录下 tieba_cookie.txt",
        )

    cookies = parse_cookie_string(cookie_str)
    bduss = cookies.get("BDUSS", "")
    stoken = cookies.get("STOKEN", "")

    if not bduss:
        return False, "Cookie 中未找到 BDUSS"
    if not stoken:
        return False, "Cookie 中未找到 STOKEN"

    client = TiebaClient(bduss=bduss, stoken=stoken, timeout=timeout)

    # 1. 登录获取 tbs
    if not client.login():
        return False, "登录失败，请检查 BDUSS 和 STOKEN 是否有效"

    # 2. 获取关注吧列表
    forums = client.get_forum_guide()
    if not forums:
        return True, "没有获取到关注吧列表，无需签到"

    # 3. 过滤未签到的吧
    unsigned_forums = [f for f in forums if f.get("is_sign") != 1]
    signed_count = sum(1 for f in forums if f.get("is_sign") == 1)
    log.info(f"已签到: {signed_count} 个, 待签到: {len(unsigned_forums)} 个")

    if not unsigned_forums:
        return True, f"所有 {len(forums)} 个关注吧均已签到"

    # 4. 逐个签到
    success_count = 0
    fail_count = 0
    already_signed_count = 0
    results: list[str] = []

    for idx, forum in enumerate(unsigned_forums, 1):
        forum_name = forum.get("forum_name", "")
        forum_id = str(forum.get("forum_id", ""))
        if not forum_id or not forum_name:
            continue

        log.info(f"[{idx}/{len(unsigned_forums)}] 正在签到: {forum_name} ...")
        ok, msg = client.sign(forum_id, forum_name)

        if ok:
            if "已签到" in msg:
                already_signed_count += 1
            else:
                success_count += 1
            log.info(f"  -> {msg}")
        else:
            fail_count += 1
            log.warning(f"  -> {msg}")

        results.append(f"{forum_name}: {msg}")

        # 避免请求过快
        if idx < len(unsigned_forums):
            time.sleep(random.uniform(2.0, 4.0))

    summary = (
        f"贴吧签到完成\n"
        f"用户: {client.user_name or '未知'}\n"
        f"成功: {success_count} 个\n"
        f"已签到: {already_signed_count + signed_count} 个\n"
        f"失败: {fail_count} 个"
    )

    log.info("=" * 40)
    log.info(summary.replace("\n", " | "))
    log.info("=" * 40)

    return fail_count == 0, summary


def main() -> None:
    log.info("=" * 50)
    log.info("========== 贴吧签到开始 ==========")
    log.info("=" * 50)

    try:
        success, message = run_checkin()
        if not success:
            sys.exit(1)
    except Exception as e:
        log.exception(f"签到异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
