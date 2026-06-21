"""ESJ论坛自动水经验脚本"""
import os
import time
import random
from playwright.sync_api import sync_playwright

# ESJ论坛配置
ESJ_LOGIN_URL = "https://www.esjzone.one/my/login"
ESJ_POST_URLS = [
    "https://www.esjzone.one/forum/1585405223/103280.html",
    "https://www.esjzone.one/forum/1585405223/80242.html"
]
ESJ_COMMENT_POOL = [
    "(゜∀゜*)",
    "(⁠・⁠∀⁠・⁠)",
    "(⁠ ⁠╹⁠▽⁠╹⁠ ⁠)",
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
        # 访问登录页，等待网络空闲
        page.goto(ESJ_LOGIN_URL, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)
        print("访问ESJ登录页")

        # 填写邮箱和密码（更精确的选择器）
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

        # 点击登录按钮
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
                page.evaluate("document.querySelector('form.login-box a.btn-send[data-form=\\\'login-box\\\'][data-send=\\\'mem_login\\\']')?.click()")
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
        print(f"自动登录过程中出现异常: {e}")
        return False

def esj_sign():
    """执行ESJ论坛水经验流程，返回 True 表示成功，False 表示失败"""
    # 获取账号密码
    username, password = get_esj_credentials()
    if not username or not password:
        return False
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            print("\n=== 开始ESJ论坛水经验 ===")
            
            # 自动登录
            if not auto_login_esj(page, username, password):
                print("登录失败，无法继续水经验")
                return False
            
            # 随机选择一个帖子
            post_url = random.choice(ESJ_POST_URLS)
            print(f"随机选择帖子: {post_url}")
            page.goto(post_url, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            # 检查登录状态：如果存在昵称输入框，说明未登录
            nickname_input = page.locator("input[name='nickname'][placeholder*='暱稱']").first
            if nickname_input.is_visible():
                print("检测到昵称输入框，说明当前未登录")
                print("尝试重新登录...")
                
                # 重新登录
                if not auto_login_esj(page, username, password):
                    print("重新登录失败")
                    return False
                
                # 重新访问帖子
                page.goto(post_url, wait_until='domcontentloaded')
                page.wait_for_timeout(3000)
                
                # 再次检查登录状态
                nickname_input = page.locator("input[name='nickname'][placeholder*='暱稱']").first
                if nickname_input.is_visible():
                    print("重新登录后仍未登录成功")
                    return False
                print("重新登录成功")
            
            # 进行三次评论，每次必须成功才继续
            for i in range(1, 4):
                print(f"\n--- 第 {i} 次评论 ---")
                try:
                    # 等待评论编辑器元素
                    comment_editor = page.locator("#commentEditor").first
                    if not comment_editor.is_visible(timeout=10000):
                        comment_editor = page.locator("div[contenteditable='true']").first

                    if comment_editor.is_visible():
                        comment_text = random.choice(ESJ_COMMENT_POOL)
                        print(f"评论内容: {comment_text}")

                        try:
                            escaped_comment = comment_text.replace("'", "\\'").replace('"', '\\"')
                            js_code = f"""
                                const editor = document.querySelector('#commentEditor');
                                const contentInput = document.querySelector('input[name=\\'content\\']');
                                if (editor) {{
                                    editor.innerHTML = '{escaped_comment}';
                                    editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                }}
                                if (contentInput) {{
                                    contentInput.value = '{escaped_comment}';
                                    contentInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    contentInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                }}
                            """
                            page.evaluate(js_code)
                            print("已设置评论内容")
                        except Exception as js_error:
                            print(f"JavaScript 注入评论失败: {js_error}")
                            try:
                                comment_editor.click()
                                page.wait_for_timeout(500)
                                comment_editor.type(comment_text)
                                print("已通过 type 方法输入评论内容")
                            except Exception as type_error:
                                print(f"type 方法输入失败: {type_error}")
                                return False

                        page.wait_for_timeout(1000)

                        # 验证是否已设置内容
                        content_input = page.locator("input[name='content']").first
                        try:
                            if content_input.is_visible(timeout=2000):
                                current_value = content_input.input_value()
                                if comment_text not in current_value:
                                    print(f"✗ 隐藏内容未设置成功: {current_value}")
                                    return False
                                print(f"✓ 隐藏内容已设置: {current_value}")
                            else:
                                print("未找到隐藏评论内容输入框，继续尝试提交")
                        except Exception as e:
                            print(f"验证隐藏输入内容时出错: {e}")

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
                                    print(f"找到送出按钮使用选择器: {selector}")
                                    break
                            except Exception as e:
                                print(f"选择器 {selector} 错误: {e}")
                                continue

                        if submit_btn and submit_btn.is_visible():
                            print("点击送出按钮...")
                            try:
                                submit_btn.scroll_into_view_if_needed()
                                page.wait_for_timeout(500)
                                submit_btn.click(timeout=10000)
                                print("已点击送出按钮")
                            except Exception as click_error:
                                print(f"点击送出按钮失败，尝试 force 点击: {click_error}")
                                try:
                                    submit_btn.click(force=True, timeout=10000)
                                    print("已点击送出按钮（force方式）")
                                except Exception as force_error:
                                    print(f"force 点击失败，尝试 JavaScript 点击: {force_error}")
                                    page.evaluate("document.querySelector('a.btn.btn-pill.btn-primary.btn-send[data-form=\\'commentEditor\\'][data-send=\\'forum_reply\\']')?.click()")
                                    print("已通过 JavaScript 点击送出按钮")

                            page.wait_for_timeout(4000)
                            success = False
                            for attempt in range(15):
                                time.sleep(1)
                                try:
                                    current_value = content_input.input_value() if content_input.is_visible() else ''
                                    if not current_value or current_value != comment_text:
                                        success = True
                                        print(f"第 {i} 次评论成功（检测到内容已清空或变化）")
                                        break
                                except Exception:
                                    success = True
                                    break
                            if not success:
                                print(f"第 {i} 次评论失败：未检测到成功标志")
                                return False
                        else:
                            print("未找到送出按钮")
                            return False
                    else:
                        print("未找到评论编辑器")
                        return False
                except Exception as e:
                    print(f"第 {i} 次评论过程中出现异常: {e}")
                    return False
            
            print("ESJ论坛水经验流程执行完毕（三次评论成功）")
            return True
        except Exception as e:
            print(f"水经验过程中出现异常: {e}")
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
