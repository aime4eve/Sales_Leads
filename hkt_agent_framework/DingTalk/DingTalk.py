# 作者：伍志勇
# 日期：2025-01-13
# 开发日志：从Notable.py中提取钉钉API相关方法

# 钉钉API访问对象

import logging
import json
import os
import requests
import time
from datetime import datetime, timedelta
import traceback
# 导入随机库，用于指数退避策略中的抖动
import random
# 导入超时配置
from timeout_config import get_timeout, get_error_message, get_retry_strategy

# 配置日志记录
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DingTalk")

# 定义重试装饰器
def retry_with_backoff(max_retries=3, initial_backoff=1, max_backoff=30, backoff_factor=2, retryable_errors=(requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
    """
    带有指数退避策略的重试装饰器
    
    参数:
        max_retries (int): 最大重试次数，默认为3
        initial_backoff (int): 初始等待时间（秒），默认为1
        max_backoff (int): 最大等待时间（秒），默认为30
        backoff_factor (int): 退避因子，默认为2
        retryable_errors (tuple): 可重试的错误类型，默认为超时和连接错误
        
    返回:
        function: 包装后的函数
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            backoff = initial_backoff
            
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # 判断是否为HTTP 500错误或超时错误
                    is_http_500 = (isinstance(e, requests.exceptions.HTTPError) and 
                                  hasattr(e, 'response') and 
                                  e.response is not None and 
                                  e.response.status_code >= 500)
                    
                    is_retryable = isinstance(e, retryable_errors) or is_http_500
                    
                    # 如果不是可重试的错误或已达到最大重试次数，则抛出异常
                    if not is_retryable or retries >= max_retries:
                        raise
                    
                    # 计算等待时间，使用指数退避 + 随机抖动（±20%）
                    jitter = random.uniform(0.8, 1.2)
                    wait_time = min(backoff * jitter, max_backoff)
                    
                    logger.warning(f"操作失败，将在 {wait_time:.2f} 秒后重试 (重试 {retries+1}/{max_retries}): {str(e)}")
                    
                    # 等待后重试
                    time.sleep(wait_time)
                    
                    # 更新重试计数和等待时间
                    retries += 1
                    backoff = min(backoff * backoff_factor, max_backoff)
        
        return wrapper
    
    return decorator


class DingTalk:
    """
    钉钉API访问类，负责处理Access Token获取和HTTP请求
    """
    
    def __init__(self, config_path=None, config_dict=None):
        """
        初始化钉钉API访问对象
        
        参数:
            config_path (str, optional): 配置文件路径
            config_dict (dict, optional): 配置字典
        """
        try:
            # 配置信息可以从参数传入的字典、指定路径的配置文件或默认位置的配置文件获取
            config = {}
            
            # 1. 如果直接传入配置字典，优先使用
            if config_dict and isinstance(config_dict, dict):
                config = config_dict
                logger.info("使用传入的配置字典")
            
            # 2. 如果指定了配置文件路径，尝试从该路径读取
            elif config_path and os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    # 检查是否有dingding键
                    if 'dingding' in config_data:
                        config = config_data['dingding']
                    else:
                        config = config_data
                logger.info(f"从指定路径读取配置：{config_path}")
            
            # 3. 尝试从默认路径读取配置文件
            else:
                # 尝试多个可能的配置文件位置
                possible_paths = [
                    # 当前目录
                    'config.json',
                    # 项目根目录
                    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dingtalk_config.json'),
                    # cost_estimate目录
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dingtalk_config.json')
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        try:
                            with open(path, 'r', encoding='utf-8') as f:
                                config_data = json.load(f)
                                # 检查是否有dingding键
                                if 'dingding' in config_data:
                                    config = config_data['dingding']
                                    logger.debug(f"从配置文件的dingding键获取数据: {path}")
                                else:
                                    config = config_data
                                    logger.debug(f"从配置文件根级别获取数据: {path}")
                            logger.info(f"从默认路径读取配置：{path}")
                            break
                        except Exception as e:
                            logger.error(f"读取配置文件 {path} 出错: {str(e)}")
                
                if not config:
                    logger.warning("未找到配置文件，将使用默认值")
                    # 设置默认配置值
                    config = {
                        "app_key": "dingfvqv5n3yxqqrgfdt",
                        "app_secret": "cdXiqOaIyzdsLeXTZdijumdEXZg2dgh_dYp2kQcenRfuJnSthYrBEVPTx7L65PGf",
                        "operatorId": "CMuBVSEounpxlYV4QORuNgiEiE",
                        "get_accessToken": "https://api.dingtalk.com/v1.0/oauth2/accessToken"
                    }
            
            logger.debug(f"配置内容: {json.dumps(config, ensure_ascii=False)}")
            
            # 获取钉钉OAuth2 API配置信息
            self.app_key = config.get('app_key')
            self.app_secret = config.get('app_secret')
            self.operator_id = config.get('operatorId')
            self.get_accessToken_url = config.get('get_accessToken')            

            # 获取钉钉多维表API配置信息
            self.notable_id = config.get('notable_id')
            self.get_notable_base_url = config.get('get_notable_base')
            self.get_notable_records_url = config.get('get_notable_records')
            self.set_notable_records_url = config.get('set_notable_records')
            self.get_notable_record_byid_url = config.get('get_notable_record_byid')
            # 获取钉钉部门列表
            self.get_department_listsub_url = config.get('get_department_listsub')
            # 获取钉钉用户列表
            self.get_user_list_by_department_url = config.get('get_user_list_by_department')
            
            # 记录配置信息，便于调试
            logger.debug(f"配置信息: app_key={self.app_key}, operatorId={self.operator_id}")
            logger.debug(f"API URLs: get_accessToken_url={self.get_accessToken_url}")
            
            # Access Token相关属性
            self.access_token = None
            self.token_expire_time = None
            # 提前5分钟刷新token，避免临界点问题
            self.token_refresh_buffer = 300  # 5分钟，单位为秒
            
            # 记录配置加载成功
            logger.info("钉钉API配置加载成功")
            
        except json.JSONDecodeError as e:
            logger.error(f"配置文件格式错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"加载配置文件时出错：{str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def get_access_token(self, force_refresh=False):
        """
        获取钉钉API的Access Token
        
        参数:
            force_refresh (bool): 是否强制刷新token，默认为False
            
        返回:
            str: 有效的Access Token
        """
        current_time = datetime.now()
        
        # 检查是否需要刷新Token
        if (not force_refresh and 
            self.access_token and 
            self.token_expire_time and 
            current_time < self.token_expire_time - timedelta(seconds=self.token_refresh_buffer)):
            logger.debug("使用缓存的Access Token")
            return self.access_token
        
        # 需要获取新的Token
        try:
            logger.info("开始获取新的Access Token")
            
            # 验证必要的字段
            if not self.app_key or not self.app_secret:
                logger.error("缺少必要的配置: app_key或app_secret")
                raise ValueError("缺少必要的配置: app_key或app_secret")
            
            if not self.get_accessToken_url:
                logger.error("缺少必要的配置: get_accessToken_url")
                raise ValueError("缺少必要的配置: get_accessToken_url")
                
            headers = {
                'Content-Type': 'application/json'
            }
            payload = {
                'appKey': self.app_key,
                'appSecret': self.app_secret
            }
            
            logger.debug(f"请求URL: {self.get_accessToken_url}")
            logger.debug(f"请求payload: {json.dumps(payload, ensure_ascii=False)}")
            
            # 使用统一的请求方法
            try:
                result = self.call_dingtalk_api(
                    method='POST',
                    url=self.get_accessToken_url,
                    headers=headers,
                    json_data=payload,
                    timeout_type="token",
                    retry_strategy="token"
                )
                
                logger.debug(f"API响应: {json.dumps(result, ensure_ascii=False)}")
                
                if 'accessToken' in result and 'expireIn' in result:
                    self.access_token = result['accessToken']
                    # expireIn单位为秒，计算过期时间
                    expire_seconds = int(result['expireIn'])
                    self.token_expire_time = current_time + timedelta(seconds=expire_seconds) 
                    # 将获取的token和过期时间保存到config.json文件中
                    try:
                        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
                        if os.path.exists(config_path):
                            with open(config_path, 'r', encoding='utf-8') as f:
                                config_data = json.load(f)
                            
                            # 更新token和过期时间
                            if 'dingding' not in config_data:
                                config_data['dingding'] = {}
                            config_data['dingding']['access_token'] = self.access_token
                            config_data['dingding']['access_token_expires'] = int(self.token_expire_time.timestamp())
                            
                            # 写回文件
                            with open(config_path, 'w', encoding='utf-8') as f:
                                json.dump(config_data, f, ensure_ascii=False, indent=4)
                            
                            logger.info(f"已将Access Token和过期时间保存到配置文件: {config_path}")
                        else:
                            logger.warning(f"配置文件不存在，无法保存Access Token: {config_path}")
                    except Exception as e:
                        logger.error(f"保存Access Token到配置文件时出错: {str(e)}")
                        # 继续执行，不因保存配置失败而中断主流程
                    logger.info(f"成功获取Access Token，有效期至：{self.token_expire_time}")
                    return self.access_token
                else:
                    logger.error(f"获取Access Token响应格式错误: {result}")
                    raise Exception("Access Token响应格式错误")
            
            except Exception as e:
                logger.error(f"获取Access Token失败: {str(e)}")
                raise
                
        except requests.exceptions.Timeout:
            logger.error("获取Access Token请求超时")
            logger.error(get_error_message("token"))
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"获取Access Token请求失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"获取Access Token时出现未知错误: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def ensure_access_token(self):
        """
        确保有有效的Access Token，如果无效或即将过期则自动刷新
        
        返回:
            str: 有效的Access Token
        """
        try:
            return self.get_access_token()
        except Exception as e:
            logger.error(f"获取Access Token失败，尝试重试: {str(e)}")
            # 重试一次
            time.sleep(2)  # 等待2秒后重试
            return self.get_access_token(force_refresh=True)
    
    def call_dingtalk_api(self, method, url, headers=None, data=None, json_data=None, timeout_type="default", 
                     retry_strategy="default", max_retries=None, initial_backoff=None, max_backoff=None, backoff_factor=None):
        """
        统一的HTTP请求方法，支持重试和错误处理
        
        参数:
            method (str): 请求方法，如'GET', 'POST', 'PUT'
            url (str): 请求URL
            headers (dict, optional): 请求头
            data (any, optional): 请求数据(用于form表单)
            json_data (dict, optional): JSON格式的请求数据
            timeout_type (str): 超时类型，默认为"default"
            retry_strategy (str): 重试策略类型，默认为"default"
            max_retries (int, optional): 最大重试次数，覆盖retry_strategy
            initial_backoff (int, optional): 初始等待时间（秒），覆盖retry_strategy
            max_backoff (int, optional): 最大等待时间（秒），覆盖retry_strategy
            backoff_factor (int, optional): 退避因子，覆盖retry_strategy
            
        返回:
            dict: 响应的JSON数据
            
        抛出:
            requests.exceptions.RequestException: 请求失败时
        """
        # 获取重试策略参数
        strategy = get_retry_strategy(retry_strategy)
        
        # 覆盖重试策略参数（如果提供）
        if max_retries is not None:
            strategy["max_retries"] = max_retries
        if initial_backoff is not None:
            strategy["initial_backoff"] = initial_backoff
        if max_backoff is not None:
            strategy["max_backoff"] = max_backoff
        if backoff_factor is not None:
            strategy["backoff_factor"] = backoff_factor
        
        # 获取当前超时设置
        timeout_value = get_timeout(timeout_type)
        logger.debug(f"请求超时设置为 {timeout_value} 秒，重试策略: {retry_strategy}，最大重试次数: {strategy['max_retries']}")
        
        # 设置请求头
        if headers is None:
            headers = {
                "Content-Type": "application/json",
                "x-acs-dingtalk-access-token": self.ensure_access_token()
            }

        # 使用带重试的HTTP请求
        @retry_with_backoff(
            max_retries=strategy["max_retries"],
            initial_backoff=strategy["initial_backoff"],
            max_backoff=strategy["max_backoff"],
            backoff_factor=strategy["backoff_factor"]
        )
        def do_request():
            logger.debug(f"发送 {method} 请求: {url}")
            
            # 记录请求详情
            log_detail = {
                "method": method,
                "url": url,
                "timeout": timeout_value,
                "headers": {k: v for k, v in headers.items() if k.lower() != 'x-acs-dingtalk-access-token'} if headers else None
            }
            
            if json_data:
                # 不记录敏感数据
                log_detail["has_json_data"] = True
            if data:
                log_detail["has_form_data"] = True
                
            logger.debug(f"请求详情: {json.dumps(log_detail, ensure_ascii=False)}")
            
            start_time = time.time()
            try:
                response = None
                if method.upper() == 'GET':
                    response = requests.get(url, headers=headers, timeout=timeout_value)
                elif method.upper() == 'POST':
                    response = requests.post(url, headers=headers, data=data, json=json_data, timeout=timeout_value)
                elif method.upper() == 'PUT':
                    response = requests.put(url, headers=headers, data=data, json=json_data, timeout=timeout_value)
                else:
                    raise ValueError(f"不支持的HTTP方法: {method}")
                
                # 记录响应时间
                elapsed_time = time.time() - start_time
                logger.debug(f"请求耗时: {elapsed_time:.2f} 秒")
                
                # 记录响应状态
                logger.debug(f"响应状态码: {response.status_code}")
                
                # 检查响应状态
                response.raise_for_status()
                
                # 尝试解析JSON响应
                try:
                    result = response.json()
                    
                    # 记录响应摘要
                    if isinstance(result, dict):
                        keys = list(result.keys())
                        logger.debug(f"响应包含以下字段: {keys}")
                    elif isinstance(result, list):
                        logger.debug(f"响应是一个列表，包含 {len(result)} 个元素")
                    
                    return result
                except ValueError as e:
                    logger.error(f"解析JSON响应失败: {str(e)}")
                    logger.error(f"响应内容: {response.text[:500]}...")
                    raise
                    
            except requests.exceptions.Timeout:
                elapsed_time = time.time() - start_time
                logger.warning(f"请求超时，已经等待 {elapsed_time:.2f} 秒，超时设置为 {timeout_value} 秒")
                raise
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"连接错误: {str(e)}")
                # 尝试进行简单的网络诊断
                try:
                    import socket
                    hostname = url.split('/')[2].split(':')[0]
                    logger.warning(f"尝试解析主机名 {hostname}...")
                    ip = socket.gethostbyname(hostname)
                    logger.warning(f"主机名 {hostname} 解析为IP: {ip}")
                except Exception as dns_e:
                    logger.warning(f"DNS解析失败: {str(dns_e)}")
                raise
            except requests.exceptions.HTTPError as e:
                logger.warning(f"HTTP错误 ({response.status_code}): {str(e)}")
                
                # 根据状态码提供更详细的错误信息
                if response.status_code == 401:
                    logger.error("身份验证失败，请检查Access Token是否有效")
                elif response.status_code == 403:
                    logger.error("权限不足，当前用户无权限访问该资源")
                elif response.status_code == 404:
                    logger.error("请求的资源不存在")
                elif response.status_code == 429:
                    logger.error("请求过于频繁，已超出API限制")
                elif response.status_code >= 500:
                    logger.error("服务器内部错误，请稍后重试")
                
                # 尝试解析错误响应
                try:
                    error_detail = response.json()
                    logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                except:
                    logger.error(f"响应内容: {response.text[:500]}...")
                
                raise
        
        # 执行请求
        return do_request() 