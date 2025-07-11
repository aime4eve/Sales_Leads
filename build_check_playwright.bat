@echo off
chcp 65001 > nul
echo =================================================================
echo.
echo  正在打包 check_playwright.py 为可执行文件...
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

echo 正在执行打包...
python -m PyInstaller check_playwright.spec --clean

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
echo =================================================================
echo.
goto :end

:error
echo.
echo 打包过程中出现错误，请查看上面的错误信息。

:end
pause
exit 