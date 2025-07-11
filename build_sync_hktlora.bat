@echo off
chcp 65001 > nul
echo =================================================================
echo.
echo  正在打包 sync_hktlora.py 为可执行文件...
echo  这个过程可能需要几分钟，请耐心等待。
echo.
echo =================================================================
echo.

rem 检查是否已安装pyinstaller
python -c "import PyInstaller" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo 正在安装PyInstaller...
    python -m pip install pyinstaller
    if %ERRORLEVEL% neq 0 (
        echo 错误: PyInstaller安装失败。
        goto :error
    )
)

echo 正在检查Playwright是否已安装...
python -c "import playwright" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo 错误: 未检测到Playwright。请先安装Playwright:
    echo python -m pip install playwright
    echo python -m playwright install chromium
    goto :error
)

echo 正在执行打包...
python -m PyInstaller sync_hktlora.spec --clean --noconfirm

if %ERRORLEVEL% neq 0 (
    echo 错误: 打包过程中出现错误。
    goto :error
)

echo.
echo =================================================================
echo.
echo  打包完成！
echo  可执行文件位于 dist 目录下。
echo.
echo  注意：此版本包含最小化的Playwright和Chromium浏览器。
echo  如果在新环境中运行时遇到问题，请使用install_browser.bat安装完整的浏览器。
echo.
echo =================================================================
echo.
goto :end

:error
echo.
echo 打包过程中出现错误，请查看上面的错误信息。

:end
pause
exit 