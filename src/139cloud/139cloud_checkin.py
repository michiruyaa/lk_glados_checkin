#!/usr/bin/env python3
"""
中国移动云盘（原和彩云）自动签到脚本
=============================================
功能：自动签到、公众号签到、通知任务、云朵汇总

使用方法：
  1. 先在本地运行 src/139cloud/capture.bat 从小程序抓包获取 Authorization
  2. 将 captured_auth.txt 的完整内容添加到 GitHub Secrets: CAPTURED_AUTH
  3. 或直接在本地运行 python src/139cloud/139cloud_checkin.py

captured_auth.txt 格式（自动生成的）：
  auth = Basic xxxxxxxx
  phone = 13800138000
  device_id = xxxxx

API 逆向分析来源：
- 中国移动云盘微信小程序 / APP
- m.mcloud.139.com 域名下的接口
"""

import json
import time
import os
import sys
import random
import uuid
from typing import Optional, Dict, Tuple

import requests

# Windows GBK 终端兼容：强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# 配置参数
# ============================================================

CAPTURED_AUTH_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "captured_auth.txt")

UA = (
    "Mozilla/5.0 (Linux; Android 12; Mi 10 Pro Build/SKQ1.211006.001; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/99.0.4844.88 "
    "Mobile Safari/537.36 MCloudApp/10.3.0"
)
MIN_SLEEP = 1
MAX_SLEEP = 2
REQ_TIMEOUT = 15


# ============================================================
# 配置加载（优先从环境变量 CAPTURED_AUTH 读取，兼容本地文件）
# ============================================================

def load_captured_auth(path: str = CAPTURED_AUTH_PATH) -> Dict[str, str]:
    """从环境变量 CAPTURED_AUTH 或本地 captured_auth.txt 读取抓包凭证
    
    GitHub Actions 中使用 Secrets 时，将 captured_auth.txt 的内容
    设置为 CAPTURED_AUTH 环境变量即可。
    
    支持格式：
      auth = Basic xxxxxxxx
      phone = 13800138000
      device_id = xxxxx
    """
    config = {}

    # 优先从环境变量读取（GitHub Secrets）
    env_auth = os.environ.get("CAPTURED_AUTH", "").strip()
    if env_auth:
        for line in env_auth.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
        if config.get("auth"):
            return config

    # 降级：从本地文件读取
    if not os.path.exists(path):
        log_error("未找到认证凭证文件: captured_auth.txt")
        print()
        log_info("请按以下步骤获取 Authorization：")
        log_info("  1. 关闭微信 PC 版")
        log_info("  2. 双击 src/139cloud/capture.bat 启动抓包工具")
        log_info("  3. 打开微信，进入'中国移动云盘'小程序")
        log_info("  4. 点击'云朵中心'或刷新页面")
        log_info("  5. 看到 [OK] 成功捕获 后按 Ctrl+C 关闭")
        log_info("  6. 再运行 python 139cloud_checkin.py")
        print()
        log_info("GitHub Actions 配置：")
        log_info("  将 captured_auth.txt 的完整内容添加到 Secrets: CAPTURED_AUTH")
        print()
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

    return config


# ============================================================
# 颜色输出
# ============================================================

class Colors:
    GREEN = ""
    RED = ""
    YELLOW = ""
    BLUE = ""
    CYAN = ""
    RESET = ""
    BOLD = ""


def log_success(msg: str):
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {msg}")


def log_error(msg: str):
    print(f"{Colors.RED}[ERR]{Colors.RESET} {msg}")


def log_info(msg: str):
    print(f"{Colors.BLUE}[*]{Colors.RESET} {msg}")


def log_warn(msg: str):
    print(f"{Colors.YELLOW}[!]{Colors.RESET} {msg}")


def log_title(msg: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}  {msg}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}\n")


# ============================================================
# 认证服务
# ============================================================

class CaiYunAuth:
    """中国移动云盘认证服务
    
    认证链路: Basic Token -> SSO Token -> JWT Token
    """

    SSO_TOKEN_URL = "https://orches.yun.139.com/orchestration/auth-rebuild/token/v1.0/querySpecToken"
    SSO_TOKEN_URL_V2 = "https://user-njs.yun.139.com/user/querySpecToken"
    
    JWT_TOKEN_URLS = [
        "https://caiyun.feixin.10086.cn/portal/auth/tyrzLogin.action",
        "https://caiyun.feixin.10086.cn:7071/portal/auth/tyrzLogin.action",
    ]

    def __init__(self, phone: str, auth_token: str):
        self.phone = str(phone)
        self.auth_token = auth_token.replace("Basic ", "").strip()
        self.sso_token: Optional[str] = None
        self.jwt_token: Optional[str] = None
        self.session = requests.Session()

    def fetch_sso_token(self) -> bool:
        """第一步：用 Basic Token + 手机号获取 SSO Token"""
        log_info("正在获取 SSO Token...")
        headers = {
            "Authorization": f"Basic {self.auth_token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Host": "orches.yun.139.com",
            "Referer": "https://orches.yun.139.com/",
            "User-Agent": UA,
        }
        data = {"account": self.phone, "toSourceId": "001005"}
        try:
            resp = self.session.post(
                self.SSO_TOKEN_URL, headers=headers, json=data, timeout=REQ_TIMEOUT
            )
            result = resp.json()
            if result.get("success") and result.get("data", {}).get("token"):
                self.sso_token = result["data"]["token"]
                log_success("SSO Token 获取成功")
                return True
            log_warn(f"主端点失败: {result.get('message', '未知错误')}，尝试备选端点...")
            return self._fetch_sso_token_v2()
        except Exception as e:
            log_error(f"SSO Token 获取异常: {e}")
            return self._fetch_sso_token_v2()

    def _fetch_sso_token_v2(self) -> bool:
        """备选 SSO Token 端点（旧版）"""
        headers = {
            "Authorization": f"Basic {self.auth_token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Host": "user-njs.yun.139.com",
            "User-Agent": UA,
        }
        data = {"phoneNumber": self.phone, "toSourceId": "001003"}
        try:
            resp = self.session.post(
                self.SSO_TOKEN_URL_V2, headers=headers, json=data, timeout=REQ_TIMEOUT
            )
            result = resp.json()
            if result.get("success") and result.get("data", {}).get("token"):
                self.sso_token = result["data"]["token"]
                log_success("SSO Token 获取成功 (备选端点)")
                return True
            log_error(f"备选端点也失败: {result.get('message', '未知错误')}")
            return False
        except Exception as e:
            log_error(f"备选端点异常: {e}")
            return False

    def fetch_jwt_token(self) -> bool:
        """第二步：用 SSO Token 换取 JWT Token"""
        if not self.sso_token:
            log_error("缺少 SSO Token，无法获取 JWT Token")
            return False
        log_info("正在获取 JWT Token...")
        for url in self.JWT_TOKEN_URLS:
            try:
                headers = {
                    "User-Agent": UA,
                    "Content-Type": "application/json",
                    "Accept": "*/*",
                    "Host": "caiyun.feixin.10086.cn",
                    "Referer": "https://caiyun.feixin.10086.cn/",
                }
                full_url = f"{url}?ssoToken={self.sso_token}"
                for method in ["POST", "GET"]:
                    resp = self.session.request(
                        method, full_url, headers=headers, timeout=REQ_TIMEOUT
                    )
                    result = resp.json()
                    if result.get("code") == 0 and result.get("result", {}).get("token"):
                        self.jwt_token = result["result"]["token"]
                        log_success(f"JWT Token 获取成功 ({method})")
                        return True
                log_info(f"端点返回: {result.get('msg', '未知')}")
            except Exception as e:
                log_info(f"端点异常: {e}")
                continue
        log_error("所有 JWT 端点均失败")
        return False

    def authenticate(self) -> bool:
        """完整认证流程"""
        log_title("认证流程")
        if not self.fetch_sso_token():
            log_error("SSO Token 获取失败，无法继续认证")
            return False
        time.sleep(1)
        if self.fetch_jwt_token():
            return True
        log_warn("JWT 失败，尝试旧版 SSO 端点...")
        if self._fetch_sso_token_v2():
            time.sleep(1)
            if self.fetch_jwt_token():
                return True
        return False

    def get_headers(self) -> Dict[str, str]:
        """获取带认证信息的请求头"""
        return {
            "jwtToken": self.jwt_token or "",
            "User-Agent": UA,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Host": "caiyun.feixin.10086.cn",
            "Referer": "https://caiyun.feixin.10086.cn/",
        }

    def get_cookies(self) -> Dict[str, str]:
        """获取带认证信息的 Cookie"""
        return {
            "jwtToken": self.jwt_token or "",
            "SSO_TOKEN": self.sso_token or "",
        }


# ============================================================
# 签到服务
# ============================================================

class SignInService:
    """签到服务"""

    BASE_URL = "https://m.mcloud.139.com"

    def __init__(self, auth: CaiYunAuth, client_type: str = "mini", device_id: Optional[str] = None):
        self.auth = auth
        self.client_type = client_type
        self.device_id = device_id or self._generate_device_id()

    def _generate_device_id(self) -> str:
        """生成设备ID（模拟小程序设备标识）"""
        import base64
        raw = uuid.uuid4().hex[:16]
        return base64.b64encode(raw.encode()).decode()

    def _sleep(self, min_d: float = MIN_SLEEP, max_d: float = MAX_SLEEP):
        """随机延迟"""
        time.sleep(random.uniform(min_d, max_d))

    def _request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """统一请求方法"""
        headers = self.auth.get_headers()
        # 新接口使用 jwttoken（小写）和 deviceid
        headers["jwttoken"] = headers.pop("jwtToken", self.auth.jwt_token or "")
        headers["deviceid"] = self.device_id
        headers["activityid"] = "sign_in_3"
        headers["appversion"] = "0.0.0.0"
        cookies = self.auth.get_cookies()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        if "cookies" in kwargs:
            cookies.update(kwargs.pop("cookies"))
        kwargs.setdefault("timeout", REQ_TIMEOUT)
        try:
            resp = self.auth.session.request(
                method, url, headers=headers, cookies=cookies, **kwargs
            )
            resp.raise_for_status()
            return resp
        except Exception as e:
            log_info(f"请求异常: {e}")
            return None

    # --------------------------------------------------------
    # 1. 签到
    # --------------------------------------------------------
    def signin_status(self) -> bool:
        """签到主流程"""
        self._sleep()
        # 查询签到状态（新接口）
        check_url = f"{self.BASE_URL}/ycloud/signin/page/startSignIn?client=mini"
        resp = self._request("GET", check_url)
        if not resp:
            log_error("签到状态查询失败")
            return False
        check_data = resp.json()
        if check_data.get("code") != 0:
            log_warn(f"签到状态查询: {check_data.get('msg', '未知')}")
            return False
        today_sign_in = check_data.get("result", {}).get("todaySignIn", False)
        if today_sign_in:
            log_success("今日已签到")
            return True
        # 执行签到（新接口）
        log_info("今日未签到，开始执行签到...")
        signin_url = f"{self.BASE_URL}/ycloud/signin/page/doTaskPost"
        payload = {
            "client": "mini",
            "deviceId": self.device_id
        }
        sign_resp = self._request("POST", signin_url, json=payload)
        if not sign_resp:
            log_error("签到执行失败")
            return False
        sign_data = sign_resp.json()
        if sign_data.get("code") == 0:
            log_success("签到成功")
            return True
        elif "已经签到" in str(sign_data.get("msg", "")) or "已签到" in str(sign_data.get("msg", "")):
            log_success("今日已签到")
            return True
        else:
            log_error(f"签到失败: {sign_data.get('msg')}")
            return False

    # --------------------------------------------------------
    # 2. 139邮箱任务
    # --------------------------------------------------------
    def get_email_tasklist(self):
        """获取139邮箱任务并自动执行"""
        task_url = f"{self.BASE_URL}/ycloud/signin/task/taskListV2"
        payload = {
            "marketname": "newsign_139mail",
            "clientVersion": "",
            "group": "new"
        }
        resp = self._request("POST", task_url, json=payload)
        if not resp:
            log_error("获取邮箱任务列表失败")
            return
        self._sleep()
        data = resp.json()
        if data.get("code") != 0:
            log_warn(f"邮箱任务列表返回: {data.get('msg', '未知')}")
            return
        task_list = data.get("result", {})
        if not task_list or not isinstance(task_list, dict):
            log_info("email_app无任务数据")
            return
        for task_type, tasks in task_list.items():
            if task_type in ["new", "hidden", "hiddenabc"]:
                continue
            if task_type == "month":
                log_title("139邮箱每月任务")
                skip_ids = [1004, 1005, 1015, 1020]
            else:
                continue
            for task in tasks:
                task_id = task.get("id")
                task_name = task.get("name", "未知任务")
                task_status = task.get("state", "")
                if task_id in skip_ids:
                    log_info(f"跳过任务：{task_name}（ID：{task_id}）")
                    continue
                if task_status == "FINISH":
                    log_info(f"已完成：{task_name}")
                    continue
                log_info(f"去完成：{task_name}（ID：{task_id}）")
                self.do_task(task_id, task_type)
                self._sleep(2, 3)

    # --------------------------------------------------------
    # 3. 执行单个任务
    # --------------------------------------------------------
    def do_task(self, task_id: int, task_type: str):
        """执行任务"""
        self._sleep()
        task_url = f"{self.BASE_URL}/ycloud/signin/task/click?key=task&id={task_id}"
        self._request("GET", task_url)

    # --------------------------------------------------------
    # 4. 公众号签到
    # --------------------------------------------------------
    def wxsign(self):
        """公众号签到"""
        self._sleep()
        url = f"{self.BASE_URL}/ycloud/playoffic/followSignInfo?isWx=true"
        resp = self._request("GET", url)
        if not resp:
            log_error("公众号签到状态查询失败")
            return
        data = resp.json()
        if data.get("code") != 0:
            log_error(f"公众号签到失败: {data.get('msg')}")
            return
        if data.get("result", {}).get("todaySignIn"):
            log_success("公众号今日已签到")
        else:
            log_warn("公众号签到失败：可能未绑定公众号")

    # --------------------------------------------------------
    # 5. 云朵汇总
    # --------------------------------------------------------
    def receive(self):
        """云朵汇总"""
        log_title("云朵汇总")
        # 查询待领取云朵（新接口 receiveV2）
        receive_url = f"{self.BASE_URL}/ycloud/signin/page/receiveV2?client=mini"
        resp = self._request("GET", receive_url)
        if not resp:
            log_warn("云朵汇总接口查询失败")
        else:
            data = resp.json()
            if data.get("code") == 0:
                receive_amount = data.get("result", {}).get("receive", "0")
                total_amount = data.get("result", {}).get("total", "0")
                log_info(f"待领取云朵: {receive_amount}")
                log_info(f"当前总云朵: {total_amount}")
            else:
                log_warn(f"云朵汇总查询: {data.get('msg', '未知')}")
        # 查询信息汇总
        self._sleep()
        info_url = f"{self.BASE_URL}/ycloud/signin/page/infoV3?client=mini"
        info_resp = self._request("GET", info_url)
        if info_resp:
            info_data = info_resp.json()
            if info_data.get("code") == 0:
                sign_count = info_data.get("result", {}).get("signCount", 0)
                month_days = info_data.get("result", {}).get("monthDays", 0)
                log_info(f"本月签到次数: {sign_count} / {month_days}")

    # --------------------------------------------------------
    # 6. 通知任务
    # --------------------------------------------------------
    def open_send(self):
        """通知任务"""
        log_title("通知任务")
        send_url = f"{self.BASE_URL}/ycloud/msgPushOn/task/status"
        resp = self._request("GET", send_url)
        if not resp:
            log_error("通知任务状态查询失败")
            return
        data = resp.json()
        if data.get("code") != 0:
            log_warn(f"通知任务查询: {data.get('msg', '未知')}")
            return
        push_on = data.get("result", {}).get("pushOn", 0)
        first_status = data.get("result", {}).get("firstTaskStatus", 0)
        second_status = data.get("result", {}).get("secondTaskStatus", 0)
        on_duration = data.get("result", {}).get("onDuaration", 0)
        if push_on == 1:
            log_info(f"通知已开启（已开启{on_duration}天）")
            reward_url = f"{self.BASE_URL}/ycloud/msgPushOn/task/obtain"
            if first_status != 3:
                log_info("领取通知任务1奖励")
                r1 = self._request("POST", reward_url, json={"type": 1})
                if r1:
                    d1 = r1.json()
                    if d1.get("code") == 0:
                        desc = d1.get("result", {}).get("description", "领取成功")
                        log_info(f"任务1奖励: {desc}")
                    else:
                        log_warn(f"任务1领取失败: {d1.get('msg')}")
            else:
                log_info("通知任务1奖励已领取")
            if second_status == 2:
                log_info("领取通知任务2奖励")
                r2 = self._request("POST", reward_url, json={"type": 2})
                if r2:
                    d2 = r2.json()
                    if d2.get("code") == 0:
                        desc = d2.get("result", {}).get("description", "领取成功")
                        log_info(f"任务2奖励: {desc}")
                    else:
                        log_warn(f"任务2领取失败: {d2.get('msg')}")
            else:
                log_info("通知任务2奖励已领取或未满足条件")
        else:
            log_warn(f"通知未开启（状态: {push_on}），无法领取奖励")


# ============================================================
# 主程序
# ============================================================

def main():
    log_title("中国移动云盘 自动签到脚本")

    # 从 captured_auth.txt 或环境变量 CAPTURED_AUTH 加载凭证
    config = load_captured_auth()
    auth_token = config.get("auth", "").strip()
    phone = config.get("phone", "").strip()

    # 校验凭证
    if not auth_token:
        log_error("auth 为空，抓包可能未成功")
        sys.exit(1)

    if not phone or phone == "13800138000":
        log_warn("phone 为空或默认值")

    print(f"  手机号: {phone[:3]}****{phone[-4:] if len(phone) >= 4 else '****'}")
    print(f"  Auth: {auth_token[:30]}...{auth_token[-10:] if len(auth_token) > 40 else ''}")
    print()

    # 认证
    auth = CaiYunAuth(phone, auth_token)
    if not auth.authenticate():
        log_error("认证失败，请重新运行 capture/capture.bat 获取最新 Authorization")
        sys.exit(1)

    # 签到服务
    service = SignInService(auth, client_type="mini", device_id=config.get("device_id", ""))

    # ===== 执行流程 =====

    # 1. 签到
    service.signin_status()

    # 2. 公众号签到
    log_title("公众号任务")
    service.wxsign()

    # 3. 通知任务
    service.open_send()

    # 4. 139邮箱任务
    service.get_email_tasklist()

    # 5. 云朵汇总
    service.receive()

    # 总结
    log_title("执行完毕")
    log_success("签到脚本运行完成！")


if __name__ == "__main__":
    main()
