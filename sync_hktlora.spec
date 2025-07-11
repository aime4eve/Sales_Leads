# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
import site
import glob

# 获取playwright核心组件路径
try:
    import playwright
    playwright_path = Path(playwright.__file__).parent
except ImportError:
    # 如果无法导入，使用默认路径
    site_packages = site.getsitepackages()[1]  # 使用第二个路径
    playwright_path = Path(site_packages) / "playwright"

# 浏览器路径 - 仅包含必要的Chromium组件 (优化大小)
browser_path = Path(os.environ.get('LOCALAPPDATA', '')) / "ms-playwright"
browser_datas = []

# 添加必要的Playwright浏览器文件
if os.path.exists(browser_path):
    # 添加Chromium浏览器核心文件
    chromium_paths = list(browser_path.glob("chromium-*"))
    if chromium_paths:
        chromium_path = chromium_paths[0]
        # 添加浏览器核心文件，但排除一些不必要的大文件
        for root, dirs, files in os.walk(str(chromium_path)):
            # 跳过一些不必要的目录，如开发工具、PDF插件等
            if any(x in root for x in [
                'chrome_100_percent', 'chrome_200_percent',
                'locales', 'swiftshader', 'MEIPreload',
                'PepperFlash', 'pnacl', 'resources'
            ]):
                continue
                
            # 只包含必要的文件
            for file in files:
                if file.endswith(('.pak', '.bin', '.dat', '.dll', '.exe')):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, str(browser_path))
                    browser_datas.append((file_path, f"playwright/driver/package/.local-browsers/{rel_path}"))

# 定义要包含的配置文件
config_files = [
    ('hkt_agent_framework/LLM/inquiry_replay_flow.json', 'hkt_agent_framework/LLM'),
    ('hkt_agent_framework/DingTalk/dingtalk_config.json', 'hkt_agent_framework/DingTalk'),
    ('version.txt', '.')
]

a = Analysis(
    ['sync_hktlora.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 配置文件
        *config_files,
        # Playwright核心组件 (仅包含必要部分)
        (str(playwright_path / "driver" / "package" / "bin"), "playwright/driver/package/bin"),
        (str(playwright_path / "__init__.py"), "playwright"),
        (str(playwright_path / "sync_api" / "__init__.py"), "playwright/sync_api"),
        (str(playwright_path / "async_api" / "__init__.py"), "playwright/async_api"),
        # 浏览器文件 (仅包含必要组件)
        *browser_datas,
    ],
    hiddenimports=[
        'playwright.sync_api', 
        'playwright.async_api',
        'hkt_agent_framework.DingTalk.DingTalk',
        'hkt_agent_framework.DingTalk.Notable',
        'hkt_agent_framework.DingTalk.Organization',
        'hkt_agent_framework.Tools'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'PyQt5', 'PySide2', 'PIL', 
        'tkinter', 'wx', 'pydoc', 'doctest', 'pdb', 'difflib',
        'lib2to3', 'pygments', 'IPython', 'jinja2'
    ],
    noarchive=False,
)

# 使用UPX压缩以减小文件大小
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='sync_hktlora',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # 剥离符号表以减小大小
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
) 