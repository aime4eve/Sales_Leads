@echo off
chcp 65001 > nul
echo =================================================================
echo.
echo  正在为您安装程序所需的浏览器组件 (Playwright Chromium)...
echo  这个过程可能需要几分钟，请保持网络连接通畅。
echo.
echo =================================================================
echo.

rem 检查是否已安装Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo 错误: 未检测到Python安装，请先安装Python 3.8或更高版本。
    goto :error
)

rem 检查是否已安装pip
python -m pip --version >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo 错误: 未检测到pip，请确保Python安装正确。
    goto :error
)

rem 检查是否已安装playwright
python -c "import playwright" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo 正在安装playwright模块...
    python -m pip install playwright
    if %ERRORLEVEL% neq 0 (
        echo 错误: playwright安装失败。
        goto :error
    )
)

echo 正在安装Playwright Chromium浏览器...
python -m playwright install chromium
if %ERRORLEVEL% neq 0 (
    echo 错误: Playwright Chromium浏览器安装失败。
    goto :error
)

echo.
echo =================================================================
echo.
echo  浏览器组件安装完成！
echo  现在您可以关闭这个窗口，并运行主程序了。
echo.
echo =================================================================
echo.
goto :end

:error
echo.
echo 安装过程中出现错误，请查看上面的错误信息。
echo 如需帮助，请联系技术支持。

:end
pause
exit 