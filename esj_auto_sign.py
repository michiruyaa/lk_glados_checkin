"""ESJ论坛自动水经验脚本"""
import json
import os
import random
import time
import sys
import io
from playwright.sync_api import sync_playwright

# Ensure stdout/stderr use UTF-8 to avoid encoding errors on Windows consoles
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
except Exception:
    pass

# ESJ论坛配置
ESJ_LOGIN_URL = "https://www.esjzone.one/my/login"
ESJ_POST_URLS = [
    "https://www.esjzone.one/forum/1585405223/103280.html",
    "https://www.esjzone.one/forum/1585405223/80242.html"
]
ESJ_COMMENT_POOL = [
    "(゜∀゜*)",
    "(⁠・⁠∀⁠・⁠)",
    "(⁠ ⁠╹⁠▽╹⁠ ⁠)",
    "(´・ω・｀)",
    "₍˄·͈༝·͈˄*₎◞ ̑̑",
    "(・ω・)",
    "(*╹▽╹*)",
    "(¦3[▓▓]",
    "Ciallo～(∠・ω< )⌒☆",
]


def get_esj_credentials():
    """从环境变量获取ESJ账号密码"""
    username = os.environ.get('ESJ_USERNAME')
    password = os.environ.get('ESJ_PASSWORD')

    if not username or not password:
        print("Error: 未设置ESJ_USERNAME或ESJ_PASSWORD环境变量")
        return None, None

    return username, password


def auto_login_esj(page, username, password):
    """自动登录ESJ，返回 True 表示成功"""
    try:
        page.goto(ESJ_LOGIN_URL, wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(2000)
        print("访问ESJ登录页")

        email_input = page.locator("form.login-box input[name='email'][type='email']").first
        if not email_input.is_visible(timeout=5000):
            print("未找到邮箱输入框")
            return False

        email_input.fill(username)
        page.wait_for_timeout(500)

        password_input = page.locator("form.login-box input[name='pwd'][type='password']").first
        if not password_input.is_visible(timeout=5000):
            print("未找到密码输入框")
            return False

        password_input.fill(password)
        page.wait_for_timeout(500)
        print("已填写邮箱和密码")

        login_button = page.locator("form.login-box a.btn-send[data-form='login-box'][data-send='mem_login']").first
        if not login_button.is_visible(timeout=3000):
            login_button = page.locator("form.login-box a:has-text('登入')").first

        if not login_button.is_visible(timeout=2000):
            login_button = page.locator("a.btn.btn-primary.btn-send").first

        if login_button.is_visible():
            try:
                login_button.click(timeout=10000)
                print("点击登录按钮")
            except Exception as click_error:
                print(f"点击登录按钮失败，尝试JavaScript点击: {click_error}")
                page.evaluate("document.querySelector('form.login-box a.btn-send[data-form=\\'login-box\\'][data-send=\\'mem_login\\']')?.click()")
                print("已通过JavaScript点击登录按钮")

            page.wait_for_timeout(6000)
        else:
            print("未找到登录按钮")
            return False

        current_url = page.url
        if "login" not in current_url.lower():
            print(f"自动登录成功，当前URL: {current_url}")
            return True

        try:
            user_name = page.locator(".user-name").first
            if user_name.is_visible(timeout=3000) and user_name.inner_text().strip():
                print("自动登录成功（检测到用户名）")
                return True
        except Exception:
            pass

        try:
            user_profile = page.locator("a[href='/my/profile.html']").first
            if user_profile.is_visible(timeout=3000):
                print("自动登录成功（检测到用户个人中心链接）")
                return True
        except Exception:
            pass

        print(f"自动登录失败，当前URL: {current_url}")
        return False
    except Exception as e:
        error_msg = str(e).encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        print(f"自动登录过程中出现异常: {error_msg}")
        return False


def wait_for_exp_popup(page, max_wait_seconds=15):
    """等待并检测經驗值+xxx弹窗，返回 (是否找到, 弹窗文本)"""
    print("等待弹窗提示...")
    for attempt in range(max_wait_seconds):
        try:
            # 尝试多种可能的选择器
            possible_selectors = [
                "div.swal2-popup div.swal2-html-container",
                "div.swal2-popup .swal2-content",
                "div.swal2-modal .swal2-content",
                "div.swal2-container .swal2-html-container",
                ".swal2-popup",
                ".swal2-modal",
            ]
            for sel in possible_selectors:
                try:
                    popup = page.locator(sel).first
                    if popup.is_visible(timeout=500):
                        text = popup.inner_text(timeout=1000).strip()
                        if text and "經驗值" in text:
                            print(f"检测到弹窗: {text}")
                            return True, text
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(1)
        print(f"  等待弹窗中... ({attempt + 1}/{max_wait_seconds})")
    return False, ""


def click_last_page_and_verify(page, expected_comments, timeout_seconds=30):
    """点击最后一页，验证是否存在指定的评论"""
    print("\n点击最后一页检查评论...")
    try:
        # 查找分页区域的最后一页链接
        # 先尝试找包含 "»" 或最后一个数字页码的链接
        last_page_links = page.locator("ul.pagination li a").all()
        if not last_page_links:
            print("未找到分页链接")
            return False

        # 通常最后一页是倒数第二个（最后一个是下一页箭头）
        # 尝试点击数字页码中最大的那个
        max_page_num = -1
        target_link = None
        for link in last_page_links:
            try:
                text = link.inner_text(timeout=1000).strip()
                if text.isdigit():
                    num = int(text)
                    if num > max_page_num:
                        max_page_num = num
                        target_link = link
            except Exception:
                continue

        if target_link and max_page_num > 1:
            print(f"点击第 {max_page_num} 页")
            target_link.click(timeout=10000)
            page.wait_for_timeout(3000)
        else:
            print("只有一页或无法找到最后一页链接")

        # 检查页面上是否存在三次发送的评论
        page_text = page.inner_text("body", timeout=10000)
        all_found = True
        for comment in expected_comments:
            if comment in page_text:
                print(f"  ✓ 找到评论: {comment}")
            else:
                print(f"  ✗ 未找到评论: {comment}")
                all_found = False
        return all_found
    except Exception as e:
        error_msg = str(e).encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        print(f"检查最后一页时出错: {error_msg}")
        return False


def post_comment(page, comment_text):
    """发送一次评论，返回 (是否成功, 弹窗文本)"""
    print(f"\n本次评论内容: {comment_text}")

    # 确保评论编辑器可见
    comment_editor = page.locator("#commentEditor").first
    if not comment_editor.is_visible(timeout=10000):
        comment_editor = page.locator("div[contenteditable='true']").first
    if not comment_editor.is_visible(timeout=10000):
        print("未找到评论编辑器")
        return False, ""

    # 设置评论内容
    js_code = """
        const text = %s;
        const editorWrapper = document.querySelector('#commentEditor');
        const editable = editorWrapper?.querySelector('.fr-element.fr-view') || editorWrapper?.querySelector('.fr-element') || editorWrapper;
        const updateEditable = (el) => {
            el.innerHTML = text;
            el.textContent = text;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
            el.dispatchEvent(new Event('blur', { bubbles: true }));
        };
        if (window.jQuery && window.jQuery('#commentEditor').data('froala.editor')) {
            try {
                window.jQuery('#commentEditor').froalaEditor('html.set', text, true);
            } catch (e) {
                console.warn('froalaEditor set failed', e);
            }
        }
        if (editable) {
            updateEditable(editable);
        }
        const contentInput = document.querySelector('input[name="content"]');
        if (contentInput) {
            contentInput.value = text;
            contentInput.dispatchEvent(new Event('change', { bubbles: true }));
            contentInput.dispatchEvent(new Event('input', { bubbles: true }));
            contentInput.dispatchEvent(new Event('blur', { bubbles: true }));
        }
    """ % json.dumps(comment_text)
    page.evaluate(js_code)
    print("已设置评论内容")
    page.wait_for_timeout(1000)

    # 点击送出按钮
    submit_btn = None
    submit_selectors = [
        "a.btn.btn-pill.btn-primary.btn-send[data-form='commentEditor'][data-send='forum_reply']",
        "a.btn.btn-pill.btn-primary.btn-send",
        "a.btn-send[data-send='forum_reply']",
        "a.btn-send",
    ]
    for selector in submit_selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=2000):
                submit_btn = btn
                print(f"找到送出按钮: {selector}")
                break
        except Exception:
            continue

    if not submit_btn or not submit_btn.is_visible(timeout=2000):
        print("未找到送出按钮")
        return False, ""

    print("点击送出按钮...")
    try:
        submit_btn.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        submit_btn.click(timeout=10000)
        print("已点击送出按钮")
    except Exception as click_error:
        print(f"点击送出按钮失败: {click_error}")
        try:
            submit_btn.click(force=True, timeout=10000)
            print("已通过 force 点击送出按钮")
        except Exception as force_error:
            print(f"force 点击失败: {force_error}")
            page.evaluate("document.querySelector('a.btn.btn-pill.btn-primary.btn-send[data-form=\\'commentEditor\\'][data-send=\\'forum_reply\\']')?.click()")
            print("已通过 JavaScript 点击送出按钮")

    # 等待并检测弹窗
    page.wait_for_timeout(2000)
    popup_found, popup_text = wait_for_exp_popup(page, max_wait_seconds=15)

    # 如果弹窗检测失败，也尝试检查页面内容是否包含經驗值
    if not popup_found:
        try:
            page_content = page.content()
            if "經驗值" in page_content:
                print("页面内容中包含'經驗值'关键字，判定为成功")
                popup_found = True
        except Exception:
            pass

    return popup_found, popup_text


def esj_sign():
    """执行ESJ论坛水经验流程，返回 True 表示成功，False 表示失败"""
    username, password = get_esj_credentials()
    if not username or not password:
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print("\n=== 开始ESJ论坛水经验 ===")

            if not auto_login_esj(page, username, password):
                print("登录失败，无法继续水经验")
                return False

            post_url = random.choice(ESJ_POST_URLS)
            print(f"随机选择帖子: {post_url}")
            page.goto(post_url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(3000)

            nickname_input = page.locator("input[name='nickname'][placeholder*='暱稱']").first
            if nickname_input.is_visible(timeout=3000):
                print("检测到昵称输入框，说明当前未登录")
                print("尝试重新登录...")
                if not auto_login_esj(page, username, password):
                    print("重新登录失败")
                    return False
                page.goto(post_url, wait_until='domcontentloaded', timeout=60000)
                page.wait_for_timeout(3000)
                nickname_input = page.locator("input[name='nickname'][placeholder*='暱稱']").first
                if nickname_input.is_visible(timeout=3000):
                    print("重新登录后仍未登录成功")
                    return False
                print("重新登录成功")

            posted_comments = []
            for i in range(1, 4):
                print(f"\n--- 第 {i} 次评论 ---")
                comment_text = random.choice(ESJ_COMMENT_POOL)
                success, popup_text = post_comment(page, comment_text)
                if success:
                    print(f"第 {i} 次评论成功 (弹窗: {popup_text})")
                    posted_comments.append(comment_text)
                else:
                    print(f"第 {i} 次评论失败：未检测到成功标志")
                    return False
                # 每次评论后稍作等待，避免请求过快
                if i < 3:
                    page.wait_for_timeout(3000)

            # 三次评论完成后，点击最后一页验证
            print("\n--- 三次评论完成，开始验证 ---")
            verified = click_last_page_and_verify(page, posted_comments)
            if verified:
                print("\n✓ 最后一页验证通过，三次评论均已存在")
            else:
                print("\n✗ 最后一页验证未完全通过")

            print("\nESJ论坛水经验流程执行完毕（三次评论成功）")
            return True
        except Exception as e:
            error_msg = str(e).encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            print(f"水经验过程中出现异常: {error_msg}")
            return False
        finally:
            browser.close()
            print("已关闭浏览器")


def main():
    """主函数"""
    success = esj_sign()
    print("\nESJ论坛水经验流程执行完毕")
    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
