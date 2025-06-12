"""
版本管理模块
用于存储和更新程序版本号
"""

import os
import re

VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'version.txt')

def get_version():
    """获取当前版本号"""
    if not os.path.exists(VERSION_FILE):
        # 默认版本号
        set_version('0.6.1')
        return '0.6.1'
    
    with open(VERSION_FILE, 'r', encoding='utf-8') as f:
        version = f.read().strip()
        return version

def set_version(version):
    """设置版本号"""
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        f.write(version)

def increment_version():
    """增加版本号的最后一位"""
    current_version = get_version()
    match = re.match(r'v?(\d+)\.(\d+)\.(\d+)', current_version)
    
    if match:
        major, minor, patch = map(int, match.groups())
        new_version = f'v{major}.{minor}.{patch + 1}'
    else:
        # 如果版本号格式不符合预期，返回默认版本号并增加1
        new_version = 'v0.6.2'
    
    set_version(new_version)
    return new_version 