import os
import sys
import re
import random
import time
import io
import requests

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
except Exception:
    pass

BASE_URL = "https://www.esjzone.one"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

POST_URLS = [
    "https://www.esjzone.one/forum/1585405223/103280.html",
    "https://www.esjzone.one/forum/1585405223/80242.html",
]

COMMENT_POOL = [
    "Ciallo～(∠・ω< )⌒☆",
    "水一下",
    "(゜∀゜*)",
    "(・ω・)",
    "(*╹▽╹*)",
    "签到打卡",
    "(´・ω・｀)",
    "₍˄·͈༝·͈˄*₎◞ ̑̑",
    "(¦3[▓▓]",
]


def get_credentials():
    email = os.environ.get('ESJ_USERNAME')
    pwd = os.environ.get('ESJ_PASSWORD')
    if email and pwd:
        return email, pwd
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for f in ['ESJ_USERNAME.txt', 'ESJ_PASSWORD.txt']:
        path = os.path.join(base, f)
        if not os.path.exists(path):
            print(f"Error: 未设置ESJ_USERNAME/ESJ_PASSWORD环境变量，也找不到 {path}")
            return None, None
    with open(os.path.join(base, 'ESJ_USERNAME.txt'), encoding='utf-8') as f:
        email = f.read().strip()
    with open(os.path.join(base, 'ESJ_PASSWORD.txt'), encoding='utf-8') as f:
        pwd = f.read().strip()
    return email, pwd


def login(session, email, pwd):
    resp = session.post(f"{BASE_URL}/inc/mem_login.php", headers={"User-Agent": UA, "Origin": BASE_URL},
                        data={"email": email, "pwd": pwd})
    try:
        j = resp.json()
    except Exception:
        print(f"登录响应解析失败: {resp.text[:200]}")
        return False
    if j.get("status") == 200:
        print("登录成功")
        return True
    print(f"登录失败: {j.get('msg', '')}")
    return False


def get_token(session, page_url):
    resp = session.post(page_url, headers={"User-Agent": UA}, data={"plxf": "getAuthToken"})
    m = re.search(r"<JinJing>(.*?)</JinJing>", resp.text)
    if m:
        return m.group(1)
    print(f"获取Token失败: {resp.text[:200]}")
    return None


def post_reply(session, page_url, content):
    token = get_token(session, page_url)
    if not token:
        return False
    m = re.search(r'/(\d+)\.html', page_url)
    fid = m.group(1) if m else "103280"
    resp = session.post(f"{BASE_URL}/inc/forum_reply.php",
                        headers={"User-Agent": UA, "authorization": token, "X-Requested-With": "XMLHttpRequest",
                                 "Referer": page_url, "Origin": BASE_URL},
                        data={"forum_id": fid, "content": content, "data": "forum", "nickname": ""})
    try:
        j = resp.json()
    except Exception:
        print(f"评论响应解析失败: {resp.text[:200]}")
        return False
    status = j.get("status")
    msg = j.get("msg", "")
    exp = j.get("exp", "")
    if status == 200:
        print(f"  + 评论成功: {content[:20]}")
        if exp:
            print(f"    经验值 +{exp}")
        return True
    if status == 214:
        print(f"  - 已达每日上限: {msg}")
        return False
    print(f"  评论失败(status={status}): {msg}")
    return False


def main():
    email, pwd = get_credentials()
    if not email:
        sys.exit(1)

    session = requests.Session()
    if not login(session, email, pwd):
        sys.exit(1)

    page_url = random.choice(POST_URLS)
    print(f"目标帖子: {page_url}")

    session.get(page_url, headers={"User-Agent": UA})

    success_count = 0
    for i in range(3):
        print(f"\n--- 第 {i+1} 次评论 ---")
        content = random.choice(COMMENT_POOL)
        print(f"评论内容: {content}")
        if post_reply(session, page_url, content):
            success_count += 1
        if i < 2:
            time.sleep(2)

    total_exp = success_count * 120
    print(f"\n完成: {success_count}/3 次评论成功, 共 +{total_exp} 经验值")
    if success_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
