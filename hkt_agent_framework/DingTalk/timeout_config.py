#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 作者：伍志勇
# 版本：1.0.0
# 日期：2025-05-16
# 描述：超时设置配置文件，为不同类型的请求设置差异化的超时时间

# 超时设置配置
TIMEOUT_CONFIG = {
    # 基础操作超时设置
    "default": 15,             # 默认超时时间（秒）
    "token": 20,               # 获取Access Token的超时时间
    "check_record": 12,        # 验证记录存在性的超时时间
    
    # 数据读取超时设置
    "get_views": 15,           # 获取表格视图列表的超时时间
    "get_records": 15,         # 获取表格记录的超时时间
    
    # 数据写入超时设置
    "update_record": 40,       # 更新表格记录的超时时间（增加到40秒）
    
    # 请求类型差异化超时设置
    "light_request": 10,       # 轻量级请求超时时间
    "normal_request": 20,      # 普通请求超时时间（增加到20秒）
    "heavy_request": 45,       # 重量级请求超时时间（增加到45秒）
    "very_heavy_request": 60,  # 特重级请求超时时间
    
    # API调用超时设置
    "dify_api": 300,           # Dify API的超时时间
    
    # 重试配置
    "connect_timeout": 10,     # 连接超时时间
    "read_timeout": 30,        # 读取超时时间
}

# 超时错误信息映射
TIMEOUT_ERROR_MESSAGES = {
    "token": "获取Access Token超时，请检查网络连接或服务器状态",
    "check_record": "验证记录存在性超时，可能是网络延迟或服务器负载过高",
    "get_views": "获取表格视图列表超时，建议稍后重试",
    "get_records": "获取表格记录超时，可能是记录数量过多或网络延迟",
    "update_record": "更新表格记录超时，建议检查网络连接并稍后重试",
    "default": "请求超时，请检查网络连接并稍后重试"
}

# 自动超时优化设置
TIMEOUT_AUTO_ADJUST = {
    "enabled": True,            # 是否启用自动调整
    "success_reduce_factor": 0.9,  # 成功请求后缩减系数（降低超时时间）
    "failure_increase_factor": 1.5,  # 失败请求后增加系数（提高超时时间）
    "min_timeout": 5,           # 最小超时时间（秒）
    "max_timeout": 120,         # 最大超时时间（秒）
    "reset_after_failures": 3   # 连续失败多少次后重置超时时间
}

def get_timeout(request_type, default_value=None):
    """
    获取指定类型请求的超时时间
    
    参数:
        request_type (str): 请求类型，如'token', 'get_records'等
        default_value (int, optional): 自定义默认值，如果不提供则使用配置中的default值
        
    返回:
        int: 超时时间（秒）
    """
    if request_type in TIMEOUT_CONFIG:
        return TIMEOUT_CONFIG[request_type]
    else:
        return default_value if default_value is not None else TIMEOUT_CONFIG["default"]

def get_error_message(request_type):
    """
    获取指定类型请求的超时错误信息
    
    参数:
        request_type (str): 请求类型，如'token', 'get_records'等
        
    返回:
        str: 错误信息
    """
    if request_type in TIMEOUT_ERROR_MESSAGES:
        return TIMEOUT_ERROR_MESSAGES[request_type]
    else:
        return TIMEOUT_ERROR_MESSAGES["default"]

def get_timeout_tuple(request_type):
    """
    获取连接超时和读取超时的元组
    
    参数:
        request_type (str): 请求类型，如'token', 'get_records'等
        
    返回:
        tuple: (连接超时, 读取超时)
    """
    # 对于不同类型的请求，可以返回不同的连接超时和读取超时
    if request_type == "dify_api":
        # Dify API调用需要更长的读取超时
        return (TIMEOUT_CONFIG["connect_timeout"], TIMEOUT_CONFIG["dify_api"])
    elif request_type in ["get_records", "update_record"]:
        # 表格记录操作需要更长的读取超时
        return (TIMEOUT_CONFIG["connect_timeout"], TIMEOUT_CONFIG[request_type])
    else:
        # 一般请求使用默认设置
        return (TIMEOUT_CONFIG["connect_timeout"], get_timeout(request_type))

def adjust_timeout(current_timeout, success=True):
    """
    根据请求成功或失败自动调整超时时间
    
    参数:
        current_timeout (int): 当前超时时间
        success (bool): 请求是否成功
        
    返回:
        int: 调整后的超时时间
    """
    if not TIMEOUT_AUTO_ADJUST["enabled"]:
        return current_timeout
        
    if success:
        # 成功请求后适当减少超时时间
        new_timeout = max(
            int(current_timeout * TIMEOUT_AUTO_ADJUST["success_reduce_factor"]),
            TIMEOUT_AUTO_ADJUST["min_timeout"]
        )
    else:
        # 失败请求后适当增加超时时间
        new_timeout = min(
            int(current_timeout * TIMEOUT_AUTO_ADJUST["failure_increase_factor"]),
            TIMEOUT_AUTO_ADJUST["max_timeout"]
        )
    
    return new_timeout

# 超时重试策略配置
RETRY_STRATEGIES = {
    "default": {
        "max_retries": 3,
        "initial_backoff": 1,
        "max_backoff": 30,
        "backoff_factor": 2
    },
    "token": {
        "max_retries": 3,
        "initial_backoff": 2,
        "max_backoff": 20,
        "backoff_factor": 2
    },
    "record_operation": {
        "max_retries": 4,
        "initial_backoff": 2,
        "max_backoff": 40,
        "backoff_factor": 2
    },
    "dify_api": {
        "max_retries": 3,
        "initial_backoff": 3,
        "max_backoff": 60,
        "backoff_factor": 3
    }
}

def get_retry_strategy(strategy_type="default"):
    """
    获取指定类型的重试策略
    
    参数:
        strategy_type (str): 策略类型，如'default', 'token'等
        
    返回:
        dict: 重试策略参数
    """
    if strategy_type in RETRY_STRATEGIES:
        return RETRY_STRATEGIES[strategy_type]
    else:
        return RETRY_STRATEGIES["default"] 