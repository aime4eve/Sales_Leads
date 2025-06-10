import sys
import subprocess
from importlib import util

def check_with_importlib():
    return util.find_spec("playwright") is not None

def check_direct_import():
    try:
        import playwright
        return True
    except ImportError:
        return False

def check_pip_show(venv_path):
    pip_path = f"{venv_path}/Scripts/pip.exe"
    command = [pip_path, "show", "playwright"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return "Version" in result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def main():
    venv_path = sys.exec_prefix.replace("\\", "/")
    
    print(f"当前Python路径: {sys.executable}")
    print(f"虚拟环境路径: {venv_path}")
    print("-" * 50)
    
    print(f"importlib检测: {'✔' if check_with_importlib() else '❌'}")
    print(f"直接导入检测: {'✔' if check_direct_import() else '❌'}")
    print(f"pip show检测: {'✔' if check_pip_show(venv_path) else '❌'}")
    
    if not all([check_with_importlib(), check_direct_import(), check_pip_show(venv_path)]):
        print("\n⚠️ 环境修复建议：")
        print("1. 检查系统PATH环境变量是否包含虚拟环境路径")
        print(f"   临时修复: $env:PATH += ';{venv_path}/Scripts'")
        print("2. 尝试初始化浏览器: playwright install")
        print("3. 重装Python环境 (v3.8+) 并禁用全局包安装")

if __name__ == "__main__":
    main()
