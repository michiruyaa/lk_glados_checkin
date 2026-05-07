/**
 * 获取百合会论坛 Cookie 的浏览器脚本
 * 
 * 使用方法：
 * 1. 登录 https://bbs.yamibo.com/
 * 2. 按 F12 打开开发者工具
 * 3. 切换到 Console（控制台）标签
 * 4. 复制粘贴以下代码并回车执行
 * 5. 复制输出的 Cookie 字符串
 */

(function() {
    'use strict';
    
    // 获取 Cookie
    const cookie = document.cookie;
    
    if (!cookie) {
        console.error('❌ 未找到 Cookie，请确保已登录百合会论坛');
        return;
    }
    
    // 检查是否包含必要的认证字段
    const requiredFields = ['EeqY_2132_auth', 'EeqY_2132_saltkey'];
    const missingFields = requiredFields.filter(field => !cookie.includes(field));
    
    if (missingFields.length > 0) {
        console.warn('⚠️ Cookie 可能不完整，缺少以下字段:', missingFields.join(', '));
    }
    
    // 输出结果
    console.log('%c百合会论坛 Cookie', 'font-size: 16px; font-weight: bold; color: #4CAF50;');
    console.log('%c请复制以下内容到 GitHub Secrets:', 'color: #666;');
    console.log('\n%c' + cookie + '\n', 'background: #f5f5f5; padding: 10px; border-radius: 4px; word-break: break-all;');
    
    // 尝试复制到剪贴板
    if (navigator.clipboard) {
        navigator.clipboard.writeText(cookie).then(() => {
            console.log('%c✅ Cookie 已复制到剪贴板', 'color: #4CAF50;');
        }).catch(err => {
            console.log('%c请手动复制上面的 Cookie 字符串', 'color: #FF9800;');
        });
    } else {
        console.log('%c请手动复制上面的 Cookie 字符串', 'color: #FF9800;');
    }
    
    // 显示关键字段
    console.log('\n%cCookie 字段分析:', 'font-weight: bold;');
    const fields = cookie.split(';').map(c => c.trim());
    fields.forEach(field => {
        const [name, value] = field.split('=');
        const isImportant = requiredFields.includes(name);
        const style = isImportant ? 'color: #4CAF50; font-weight: bold;' : 'color: #666;';
        const marker = isImportant ? '✓ ' : '  ';
        console.log(`%c${marker}${name}: ${value ? value.substring(0, 20) + '...' : '(空)'}`, style);
    });
    
})();
