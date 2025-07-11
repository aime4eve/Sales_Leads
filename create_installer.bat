@echo off
chcp 65001 > nul
echo =================================================================
echo.
echo  正在创建安装包...
echo  这个过程可能需要几分钟，请耐心等待。
echo.
echo =================================================================
echo.

rem 检查是否已安装NSIS
if not exist "C:\Program Files (x86)\NSIS\makensis.exe" (
    echo 错误: 未找到NSIS安装。
    echo 请先安装NSIS: https://nsis.sourceforge.io/Download
    echo 安装后，请将NSIS安装路径添加到系统PATH环境变量中。
    goto :error
)

python setup_installer.py

if %ERRORLEVEL% neq 0 (
    echo 错误: 创建安装包失败。
    goto :error
)

echo.
echo =================================================================
echo.
echo  安装包创建成功！
echo  安装包位于 installer 目录下。
echo.
echo =================================================================
echo.
goto :end

:error
echo.
echo 创建安装包过程中出现错误，请查看上面的错误信息。

:end
pause
exit 