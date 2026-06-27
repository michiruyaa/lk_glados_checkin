#!/usr/bin/env python3
"""
mitmproxy 插件：自动拦截微信小程序请求并提取 Authorization
===============================================================
使用方法：
  mitmproxy -s capture_auth.py -p 8080

此脚本会：
  1. 拦截所有经过代理的 HTTPS 请求
  2. 从请求头中提取 Authorization
  3. 如果域名匹配移动云盘相关域名，自动保存到 config.ini
"""

import os
import re
from urllib.parse import urlparse
from mitmproxy import http, ctx

# 目标域名（移动云盘相关）
TARGET_DOMAINS = [
    "orches.yun.139.com",
    "caiyun.feixin.10086.cn",
    "user-njs.yun.139.com",
    "yun.139.com",
    "aas.caiyun.feixin.10086.cn",
    "m.mcloud.139.com",
]

# 保存路径
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CONFIG_PATH = os.path.join(SAVE_DIR, "config.ini")
AUTH_FILE = os.path.join(SAVE_DIR, "captured_auth.txt")

_captured = False
_captured_device_id = None

def _is_target_domain(host: str) -> bool:
    """检查是否为目标域名"""
    host = host.lower()
    for domain in TARGET_DOMAINS:
        if domain in host:
            return True
    return False

def _extract_phone_from_auth(auth: str) -> str:
    """从 Authorization 中尝试提取手机号"""
    # 常见格式: Basic base64(phone:token) 或 Basic base64(phone)
    import base64
    try:
        # 去掉 Basic 前缀
        b64 = auth.replace("Basic ", "").replace("basic ", "").strip()
        decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
        # 尝试找手机号
        match = re.search(r"1[3-9]\d{9}", decoded)
        if match:
            return match.group(0)
    except Exception:
        pass
    return ""

def _save_auth(auth: str, host: str, device_id: str = ""):
    """保存提取到的 Authorization"""
    global _captured
    if _captured:
        return
    _captured = True

    phone = _extract_phone_from_auth(auth)

    # 1. 保存到独立文件
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 抓取时间: {os.environ.get('TIME', 'unknown')}\n")
        f.write(f"# 来源域名: {host}\n")
        f.write(f"# 手机号: {phone if phone else 'unknown'}\n")
        f.write(f"auth = {auth}\n")
        f.write(f"phone = {phone if phone else '13800138000'}\n")
        if device_id:
            f.write(f"device_id = {device_id}\n")

    # 2. 尝试更新 config.ini
    try:
        import configparser
        cfg = configparser.ConfigParser()
        if os.path.exists(CONFIG_PATH):
            cfg.read(CONFIG_PATH, encoding="utf-8")
        else:
            cfg.add_section("account")
            cfg.add_section("advanced")
        cfg.set("account", "auth", auth)
        if phone:
            cfg.set("account", "phone", phone)
        if device_id:
            cfg.set("account", "device_id", device_id)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            cfg.write(f)
    except Exception as e:
        ctx.log.warn(f"更新 config.ini 失败: {e}")

    ctx.log.info(f"=" * 60)
    ctx.log.info("  [OK] 成功捕获 Authorization！")
    ctx.log.info(f"  来源: {host}")
    ctx.log.info(f"  已保存到: {AUTH_FILE}")
    ctx.log.info(f"  已更新: {CONFIG_PATH}")
    if device_id:
        ctx.log.info(f"  设备ID: {device_id[:30]}...")
    ctx.log.info(f"=" * 60)
    ctx.log.info("  现在可以关闭代理，运行 139cloud_checkin.py 进行签到了")
    ctx.log.info(f"=" * 60)


def request(flow: http.HTTPFlow) -> None:
    """处理每个请求"""
    host = flow.request.pretty_host
    global _captured_device_id

    # 检查是否为目标域名
    if not _is_target_domain(host):
        return

    # 提取 deviceid
    if not _captured_device_id:
        did = flow.request.headers.get("deviceid", "")
        if not did:
            did = flow.request.headers.get("deviceId", "")
        if did and len(did) > 10:
            _captured_device_id = did
            ctx.log.info(f"[捕获] {host} - device_id: {did[:30]}...")

    # 提取 Authorization 头
    auth = flow.request.headers.get("Authorization", "")
    if not auth:
        auth = flow.request.headers.get("authorization", "")

    if auth and len(auth) > 20:  # 确保不是空值或短值
        ctx.log.info(f"[捕获] {host} - Authorization: {auth[:50]}...")
        _save_auth(auth, host, _captured_device_id or "")
