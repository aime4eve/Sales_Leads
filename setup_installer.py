#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import subprocess
from pathlib import Path

# 安装包配置
APP_NAME = "HKT Sales Leads"
APP_VERSION = "1.0.0"
APP_PUBLISHER = "HKT"
APP_WEBSITE = "https://www.example.com"
APP_DESCRIPTION = "外贸销售线索自动化工具"
OUTPUT_DIR = "installer"
DIST_DIR = "dist"

# NSIS脚本模板
NSIS_SCRIPT_TEMPLATE = r"""
; 基本设置
!include "MUI2.nsh"
!include "FileFunc.nsh"
Unicode true

; 定义应用信息
Name "{app_name}"
OutFile "{output_dir}\{app_name}_Setup_{app_version}.exe"
InstallDir "$PROGRAMFILES\{app_name}"
InstallDirRegKey HKLM "Software\{app_name}" "Install_Dir"

; 请求应用程序管理员权限
RequestExecutionLevel admin

; 版本信息
VIProductVersion "{app_version}.0"
VIAddVersionKey "ProductName" "{app_name}"
VIAddVersionKey "CompanyName" "{app_publisher}"
VIAddVersionKey "LegalCopyright" "© {app_publisher}"
VIAddVersionKey "FileDescription" "{app_description}"
VIAddVersionKey "FileVersion" "{app_version}"
VIAddVersionKey "ProductVersion" "{app_version}"

; 界面设置
!define MUI_ICON "{icon_path}"
!define MUI_UNICON "{icon_path}"
!define MUI_WELCOMEFINISHPAGE_BITMAP "{installer_image}"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "{header_image}"
!define MUI_ABORTWARNING

; 安装界面
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "{license_file}"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; 卸载界面
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; 语言设置
!insertmacro MUI_LANGUAGE "SimpChinese"

; 安装部分
Section "安装程序文件" SecMain
  SetOutPath "$INSTDIR"
  
  ; 添加文件
  File /r "{dist_dir}\*.*"
  
  ; 创建卸载程序
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  ; 创建开始菜单快捷方式
  CreateDirectory "$SMPROGRAMS\{app_name}"
  CreateShortcut "$SMPROGRAMS\{app_name}\{app_name}.lnk" "$INSTDIR\sync_hktlora.exe"
  CreateShortcut "$SMPROGRAMS\{app_name}\卸载 {app_name}.lnk" "$INSTDIR\uninstall.exe"
  
  ; 创建桌面快捷方式
  CreateShortcut "$DESKTOP\{app_name}.lnk" "$INSTDIR\sync_hktlora.exe"
  
  ; 写入注册表信息
  WriteRegStr HKLM "Software\{app_name}" "Install_Dir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_name}" "DisplayName" "{app_name}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_name}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_name}" "DisplayIcon" "$INSTDIR\sync_hktlora.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_name}" "DisplayVersion" "{app_version}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_name}" "Publisher" "{app_publisher}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_name}" "URLInfoAbout" "{app_website}"
  
  ; 计算安装大小
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_name}" "EstimatedSize" "$0"
SectionEnd

; 卸载部分
Section "Uninstall"
  ; 删除程序文件
  RMDir /r "$INSTDIR"
  
  ; 删除快捷方式
  Delete "$DESKTOP\{app_name}.lnk"
  Delete "$SMPROGRAMS\{app_name}\*.*"
  RMDir "$SMPROGRAMS\{app_name}"
  
  ; 删除注册表项
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_name}"
  DeleteRegKey HKLM "Software\{app_name}"
SectionEnd
"""

def create_installer():
    """创建安装包"""
    print("开始创建安装包...")
    
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 准备资源文件
    icon_path = "sources/kw.ico"
    if not os.path.exists(icon_path):
        icon_path = "installer/default.ico"
        os.makedirs(os.path.dirname(icon_path), exist_ok=True)
        # 创建一个默认图标文件
        shutil.copy("dist/sync_hktlora.exe", icon_path)
    
    # 创建许可证文件
    license_file = "installer/license.txt"
    os.makedirs(os.path.dirname(license_file), exist_ok=True)
    with open(license_file, "w", encoding="utf-8") as f:
        f.write(f"{APP_NAME} 软件许可协议\n\n")
        f.write("本软件仅供内部使用，未经授权不得分发。\n")
        f.write("使用本软件即表示您同意遵守本协议的所有条款。\n")
    
    # 创建安装程序图像
    installer_image = "installer/installer.bmp"
    header_image = "installer/header.bmp"
    
    # 如果没有图像，使用默认的
    if not os.path.exists(installer_image):
        # 这里应该创建默认图像，但为简化，我们使用空文件
        with open(installer_image, "wb") as f:
            f.write(b"")
    
    if not os.path.exists(header_image):
        # 这里应该创建默认图像，但为简化，我们使用空文件
        with open(header_image, "wb") as f:
            f.write(b"")
    
    # 生成NSIS脚本
    nsis_script = NSIS_SCRIPT_TEMPLATE.format(
        app_name=APP_NAME,
        app_version=APP_VERSION,
        app_publisher=APP_PUBLISHER,
        app_website=APP_WEBSITE,
        app_description=APP_DESCRIPTION,
        output_dir=OUTPUT_DIR,
        dist_dir=DIST_DIR,
        icon_path=icon_path,
        installer_image=installer_image,
        header_image=header_image,
        license_file=license_file
    )
    
    # 保存NSIS脚本
    nsis_script_path = os.path.join(OUTPUT_DIR, "installer.nsi")
    with open(nsis_script_path, "w", encoding="utf-8") as f:
        f.write(nsis_script)
    
    # 检查是否安装了NSIS
    nsis_path = r"C:\Program Files (x86)\NSIS\makensis.exe"
    if not os.path.exists(nsis_path):
        print("错误: 未找到NSIS安装。请先安装NSIS: https://nsis.sourceforge.io/Download")
        print("安装后，请将NSIS安装路径添加到系统PATH环境变量中。")
        return False
    
    # 运行NSIS编译器
    try:
        print(f"正在编译NSIS脚本: {nsis_script_path}")
        subprocess.run([nsis_path, nsis_script_path], check=True)
        print(f"安装包创建成功: {OUTPUT_DIR}/{APP_NAME}_Setup_{APP_VERSION}.exe")
        return True
    except subprocess.CalledProcessError as e:
        print(f"编译NSIS脚本时出错: {e}")
        return False
    except Exception as e:
        print(f"创建安装包时出错: {e}")
        return False

def create_batch_file():
    """创建批处理文件以运行此脚本"""
    batch_content = """@echo off
chcp 65001 > nul
echo =================================================================
echo.
echo  正在创建安装包...
echo  这个过程可能需要几分钟，请耐心等待。
echo.
echo =================================================================
echo.

python setup_installer.py

if %ERRORLEVEL% neq 0 (
    echo 错误: 创建安装包失败。
    pause
    exit /b 1
)

echo.
echo =================================================================
echo.
echo  安装包创建成功！
echo  安装包位于 installer 目录下。
echo.
echo =================================================================
echo.
pause
exit /b 0
"""
    
    with open("create_installer.bat", "w", encoding="utf-8") as f:
        f.write(batch_content)
    
    print("已创建批处理文件: create_installer.bat")

if __name__ == "__main__":
    # 创建安装包
    success = create_installer()
    
    # 创建批处理文件
    create_batch_file()
    
    if success:
        print("安装包创建过程完成。")
    else:
        print("安装包创建失败，请查看上面的错误信息。")
        sys.exit(1) 