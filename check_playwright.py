import sys
import os
import subprocess
from importlib import util
from pathlib import Path

def check_with_importlib():
    """使用importlib检查playwright是否已安装"""
    return util.find_spec("playwright") is not None

def check_direct_import():
    """尝试直接导入playwright"""
    try:
        import playwright
        return True
    except ImportError:
        return False

def check_browser_installation():
    """检查playwright浏览器是否已安装"""
    try:
        # 检查浏览器目录是否存在
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        browser_path = Path(local_appdata) / "ms-playwright"
        
        # 检查打包环境中的浏览器
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
            bundled_browser_path = exe_dir / "playwright" / "driver" / "package" / ".local-browsers"
            
            if bundled_browser_path.exists():
                # 检查打包的浏览器文件
                has_bundled_browser = any(bundled_browser_path.glob("chromium-*"))
                if has_bundled_browser:
                    return True, f"打包的浏览器: {bundled_browser_path}"
        
        # 检查本地安装的浏览器
        if not browser_path.exists():
            return False, str(browser_path)
            
        # 检查是否有浏览器文件
        chromium_path = browser_path / "chromium-"
        has_chromium = any(chromium_path.parent.glob(f"{chromium_path.name}*"))
        
        if has_chromium:
            return True, str(browser_path)
        else:
            return False, str(browser_path)
    except Exception as e:
        return False, str(e)

def check_pip_show():
    """使用pip show检查playwright是否已安装"""
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "show", "playwright"], 
                               capture_output=True, text=True)
        return "Version" in result.stdout
    except Exception:
        return False

def main():
    """主函数"""
    python_path = sys.executable
    venv_path = sys.exec_prefix
    
    print("Playwright 环境检查工具")
    print("=" * 50)
    print(f"当前Python路径: {python_path}")
    print(f"虚拟环境路径: {venv_path}")
    print(f"打包状态: {'已打包' if getattr(sys, 'frozen', False) else '未打包'}")
    print("-" * 50)
    
    # 检查playwright模块
    importlib_check = check_with_importlib()
    direct_import = check_direct_import()
    pip_check = check_pip_show()
    
    print(f"1. Playwright模块检查:")
    print(f"   - importlib检测: {'✓' if importlib_check else '✗'}")
    print(f"   - 直接导入检测: {'✓' if direct_import else '✗'}")
    print(f"   - pip show检测: {'✓' if pip_check else '✗'}")
    
    # 检查浏览器安装
    browser_installed, browser_path = check_browser_installation()
    print(f"\n2. Playwright浏览器检查:")
    print(f"   - 浏览器安装状态: {'✓' if browser_installed else '✗'}")
    print(f"   - 浏览器路径: {browser_path}")
    
    # 综合结果
    all_checks = [importlib_check or direct_import, browser_installed]
    if all(all_checks):
        print("\n✅ 检查结果: Playwright环境正常!")
    else:
        print("\n❌ 检查结果: Playwright环境存在问题!")
        
        print("\n修复建议:")
        if not any([importlib_check, direct_import]):
            print("1. 安装Playwright模块:")
            print(f"   {python_path} -m pip install playwright")
        
        if not browser_installed:
            print("2. 安装Playwright浏览器:")
            print(f"   {python_path} -m playwright install chromium")
            
        print("\n或者直接运行安装脚本:")
        print("   install_browser.bat")

if __name__ == "__main__":
    main()
