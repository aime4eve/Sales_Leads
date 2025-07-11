# 作者：伍志勇
# 日期：2025-05-13
# 开发日志：

# 钉钉多维表对象

import logging
import json
import os
import requests
import time
import re
from datetime import datetime, timedelta
from functools import reduce
import traceback

# 导入DingTalk类
from .DingTalk import DingTalk
# 导入tqdm进度条
from tqdm import tqdm
# 导入随机库，用于指数退避策略中的抖动
import random
import sys
# 导入超时配置
from .timeout_config import get_timeout, get_error_message, get_timeout_tuple, get_retry_strategy
# 导入Tools.py
from ..Tools import countdown

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

# 定义日期时间格式检查函数
def is_valid_datetime_format(datetime_str):
    """
    检查是否是有效的Unix毫秒时间戳
    
    参数:
        datetime_str (str): 需要检查的时间戳字符串
        
    返回:
        bool: 如果是有效的Unix毫秒时间戳，返回True；否则返回False
    """
    if not datetime_str:
        return False
    
    try:
        # 检查是否为纯数字
        timestamp = int(datetime_str)
        # Unix毫秒时间戳通常是13位数字
        # logger.info(len(datetime_str) == 13 and timestamp > 0)
        return len(datetime_str) == 13 and timestamp > 0
    except (ValueError, TypeError):
        return False

class Notable:
    """
    Notable类，用于操作钉钉多维表格
    """
    def __init__(self, config_path=None, config_dict=None):
        try:
            # 设置日志记录器
            self.logger = logging.getLogger(__name__)
            # 使用根日志记录器的级别
            root_logger = logging.getLogger()
            self.logger.setLevel(root_logger.level)
            
            # 创建DingTalk实例用于API访问
            self.dingtalk = DingTalk(config_path=config_path, config_dict=config_dict)            

            # 设置notable_dir为项目根目录下的notable子目录
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.notable_dir = os.path.join(current_dir, "notable")
            
            # 确保notable目录存在
            if not os.path.exists(self.notable_dir):
                os.makedirs(self.notable_dir)
                self.logger.info(f"创建notable目录: {self.notable_dir}")
            

        except Exception as e:
            self.logger.error(f"加载配置文件时出错：{str(e)}")
            self.logger.error(traceback.format_exc())
            raise
  
    
    def _find_sheet_id(self, sheet_name, definition_file="notable_definition.json"):
        """
        从定义文件中查找sheet_id
        
        参数:
            sheet_name (str): 表格视图名称
            definition_file (str): 表格定义文件路径，默认为"notable_definition.json"
            
        返回:
            str: 表格视图ID，如果未找到则返回sheet_name
        """
        # 修改definition_file路径到notable目录
        definition_file_path = os.path.join(self.notable_dir, os.path.basename(definition_file))
        
        # 尝试从definition_file中查找sheet_id
        if os.path.exists(definition_file_path):
            self.logger.debug(f"从表格定义文件中查找视图ID: {definition_file_path}")
            try:
                with open(definition_file_path, 'r', encoding='utf-8') as f:
                    definition_data = json.load(f)
                
                # 查找匹配的sheet_name
                views = []
                if 'items' in definition_data:
                    views = definition_data.get('items', [])
                elif 'value' in definition_data:
                    views = definition_data.get('value', [])
                # print(f"views: {views},sheet_name: {sheet_name}")
                for view in views:
                    if view.get('name') == sheet_name or view.get('id') == sheet_name:
                        sheet_id = view.get('id', view.get('sheetId'))
                        self.logger.debug(f"找到表格视图 '{sheet_name}' 的ID: {sheet_id}")
                        return sheet_id
                
                self.logger.warning(f"在表格定义中未找到名为 '{sheet_name}' 的视图，将尝试直接使用sheet_name作为ID")
            except Exception as e:
                self.logger.error(f"读取表格定义文件时出错: {str(e)}")
                self.logger.warning(f"将尝试直接使用sheet_name作为ID: {sheet_name}")
        else:
            self.logger.warning(f"表格定义文件不存在: {definition_file_path}")
            self.logger.warning(f"将尝试直接使用sheet_name作为ID: {sheet_name}")
        
        return sheet_name
    
    def safe_get(self, dictionary, keys, default=None):
        return reduce(lambda d, key: d.get(key, {}) if isinstance(d, dict) else default, keys.split("."), dictionary)
    
    def truncate_field_value(self, field_key, field_value, max_length=9500):
        """
        检查并截断字段值，确保在API限制范围内
        
        参数:
            field_key (str): 字段名称
            field_value (any): 字段值
            max_length (int): 最大允许长度，默认9500(预留缓冲区)
            
        返回:
            any: 处理后的字段值
        """
        try:
            # 对于markdown类型的字段
            if isinstance(field_value, dict) and 'markdown' in field_value:
                markdown_text = field_value['markdown']
                # 如果markdown文本超长，截断它
                if len(markdown_text) > max_length:
                    truncated_text = markdown_text[:max_length] + "\n\n...(内容已截断，超出字段长度限制)"
                    field_value['markdown'] = truncated_text
                    self.logger.warning(f"字段 {field_key} 的markdown内容已从 {len(markdown_text)} 字符截断至 {len(truncated_text)} 字符")
            
            # 对于字符串类型的字段
            elif isinstance(field_value, str):
                if len(field_value) > max_length:
                    truncated_text = field_value[:max_length] + "...(已截断)"
                    field_value = truncated_text
                    self.logger.warning(f"字段 {field_key} 的字符串内容已从 {len(field_value)} 字符截断至 {len(truncated_text)} 字符")
            
            # 对于数字类型的字段，转换为字符串处理
            elif isinstance(field_value, (int, float)):
                field_value_str = str(field_value)
                if len(field_value_str) > max_length:
                    self.logger.warning(f"数值型字段 {field_key} 的长度异常: {len(field_value_str)} 字符")
                    # 一般情况下，数值不会超过长度限制，这里只记录警告
            
            return field_value
        except Exception as e:
            self.logger.error(f"截断字段 {field_key} 时发生错误: {str(e)}")
            # 出错时返回原值，保证程序继续执行
            return field_value
    
    def get_access_token(self, force_refresh=False):
        """
        获取钉钉API的Access Token（委托给DingTalk实例）
        
        参数:
            force_refresh (bool): 是否强制刷新token，默认为False
            
        返回:
            str: 有效的Access Token
        """
        return self.dingtalk.get_access_token(force_refresh)
    
    def ensure_access_token(self):
        """
        确保有有效的Access Token，如果无效或即将过期则自动刷新（委托给DingTalk实例）
        
        返回:
            str: 有效的Access Token
        """
        return self.dingtalk.ensure_access_token()
    
    def add_record(self, sheet_name: str, fields: dict, fields_id: str = None, table_id: str = None) -> tuple:
        """
        向指定的钉钉多维表添加单条记录。

        此方法实现了V2设计方案，通过调用DingTalk类中统一的API请求方法来确保
        重试、日志和错误处理的一致性。

        参数:
            sheet_name (str): 目标表格的名称。
            fields (dict): 包含记录字段的字典。
            fields_id (str, optional): 记录的ID，用于幂等性检查。如果提供，将检查记录是否存在。
            table_id (str, optional): 多维表的ID。如果为None，则从配置中自动获取。

        返回:
            tuple: 成功时返回 (record_id, None)，失败时返回 (None, error_message)。
        """
        try:
            # 1. 确保获取table_id和sheet_id
            final_table_id = self._ensure_table_id(table_id)
            sheet_id = self._find_sheet_id(sheet_name)

            # 设置默认的API调用方法
            call_api_method = 'POST'
            
            # 初始化默认的json_data结构
            json_data = {
                "records": [
                    {
                        "fields": fields
                    }
                ]
            }

            # 幂等性检查：如果提供了fields_id，则先检查记录是否存在
            if fields_id:
                # 调用check_record_exists进行存在性检查
                record_exists = self.check_record_exists(final_table_id, sheet_name, fields_id)
                if record_exists:
                    # 记录已存在
                    # logger.info(f"记录 '{fields_id}' 已存在，将执行更新操作。")
                    call_api_method = 'PUT'
                    # 更新json_data，添加id字段
                    json_data["records"][0]["id"] = fields_id
                # else:
                #     # 记录不存在
                #     # logger.info(f"记录 '{fields_id}' 不存在，将执行新增操作。")
                #     # 使用默认的json_data结构
                # 可选的短暂延时，以防API频率问题
                time.sleep(0.5)

            # 2. 准备API请求参数
            url_template = self.dingtalk.set_notable_records_url
            if not url_template:
                raise ValueError("钉钉配置中缺少'set_notable_records' URL")

            # 使用与get_table_records一致的占位符
            url = url_template.replace("{table_id}", final_table_id).replace("{sheetname}", sheet_id).replace("{unionid}", self.dingtalk.operator_id)


            
            # 3. 使用DingTalk中统一的方法发送API请求
            result = self.dingtalk.call_dingtalk_api(
                method=call_api_method,
                url=url,
                json_data=json_data
            )
            
            # 4. 解析成功的响应
            record_id = None
            if isinstance(result.get("value"), list) and len(result["value"]) > 0:
                record_id = result["value"][0].get("id")

            if not record_id:
                error_msg = f"刷新记录成功，但响应中未找到ID: {result}"
                self.logger.error(error_msg)
                return None, error_msg

            # logger.info(f"成功刷新记录到'{sheet_name}'多维表，记录ID: {record_id}")
            return record_id, f"刷新记录成功，记录ID: {record_id}"

        except Exception as e:
            # 捕获call_dingtalk_api中抛出的任何异常
            error_message = f"新增记录到'{sheet_name}'时发生错误: {str(e)}"
            self.logger.error(error_message)
            self.logger.error(traceback.format_exc())
            return None, str(e)

    def get_table_record_byid(self, table_id=None, sheet_name="任务管理", record_id=None, definition_file="notable_definition.json"):
        """
        根据ID获取钉钉多维表中的特定记录
        
        参数:
            table_id (str, optional): 多维表ID，如果不提供则使用配置中的notable_id
            sheet_name (str): 表格视图名称，默认为"任务管理"
            record_id (str): 要获取的记录ID
            definition_file (str): 表格定义文件路径，默认为"notable_definition.json"
            
        返回:
            dict: 包含记录数据的字典，如果未找到记录则返回None
        """
        try:
            # 验证必要参数
            if not record_id:
                self.logger.error("记录ID不能为空")
                return None
                
            # 确保有有效的表格ID
            try:
                table_id = self._ensure_table_id(table_id)
            except ValueError as e:
                self.logger.error(str(e))
                return None
            
            # logger.info(f"开始获取记录，表格ID: {table_id}，表格视图: {sheet_name}，记录ID: {record_id}")
            
            # 查找sheet_id
            sheet_id = self._find_sheet_id(sheet_name, definition_file)
            
           
            if not self.dingtalk.get_notable_record_byid_url:
                self.logger.error("get_notable_record_byid_url 不能为空")
                return None
            
            # 确保有有效的Access Token
            access_token = self.ensure_access_token()
            
            # 替换URL中的参数
            url = self.dingtalk.get_notable_record_byid_url.replace("{table_id}", table_id).replace("{sheetname}", sheet_id).replace("{record_id}", record_id).replace("{unionid}", self.dingtalk.operator_id)
            self.logger.debug(f"请求URL: {url}")
            
            # 设置请求头
            headers = {
                "Content-Type": "application/json",
                "x-acs-dingtalk-access-token": access_token
            }
            
            # 使用统一的请求方法
            try:
                result = self.dingtalk.call_dingtalk_api(
                    method='GET',
                    url=url,
                    headers=headers,
                    timeout_type="get_record",
                    retry_strategy="record_operation",
                    max_retries=2
                )
                
                self.logger.debug(f"API响应: {json.dumps(result, ensure_ascii=False)[:500]}...")
                
                # 验证响应中是否包含记录ID
                if "id" in result and result["id"] == record_id:
                    # logger.info(f"成功获取记录 ID: {record_id}")
                    return result
                else:
                    self.logger.warning(f"获取记录 ID: {record_id} 返回的数据不匹配")
                    return None
                    
            except requests.exceptions.HTTPError as e:
                # 捕获HTTP错误
                if hasattr(e, 'response') and e.response is not None:
                    if e.response.status_code == 404:
                        self.logger.warning(f"记录 {record_id} 不存在")
                        return None
                    else:
                        self.logger.error(f"获取记录时发生HTTP错误: {e.response.status_code}")
                        try:
                            error_detail = e.response.json()
                            self.logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                        except:
                            self.logger.error(f"响应内容: {e.response.text[:500]}...")
                raise
            except requests.exceptions.Timeout:
                self.logger.error("获取记录请求超时")
                self.logger.error(get_error_message("get_record"))
                return None
            except Exception as e:
                self.logger.error(f"获取记录 ID: {record_id} 时发生未知错误: {str(e)}")
                self.logger.error(traceback.format_exc())
                return None
                
        except Exception as e:
            self.logger.error(f"获取记录操作过程中出现错误: {str(e)}")
            self.logger.error(traceback.format_exc())
            return None

    def check_record_exists(self, table_id, sheet_id, record_id):
        """
        验证指定记录是否存在
        
        参数:
            table_id (str): 多维表ID
            sheet_id (str): 表格视图ID
            record_id (str): 记录ID
            
        返回:
            bool: 记录是否存在
        """
        try:
            # logger.info(f"验证记录 {record_id} 是否存在")
            
            # 调用get_table_record_byid方法获取记录
            record = self.get_table_record_byid(table_id, sheet_id, record_id)
            
            # 如果成功获取到记录，则返回True
            if record and "id" in record and record["id"] == record_id:
                # logger.info(f"记录 {record_id} 存在")
                return True
            else:
                self.logger.warning(f"记录 {record_id} 不存在")
                return False
                
        except Exception as e:
            self.logger.error(f"验证记录存在性时发生错误: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False
    
    def get_table_views(self, table_id=None, save_to_file=True, output_file="notable_definition.json"):
        """
        获取钉钉多维表中的表格视图列表
        
        参数:
            table_id (str, optional): 多维表ID，如果不提供则使用配置中的notable_id
            save_to_file (bool): 是否保存结果到文件，默认为True
            output_file (str): 输出文件名，默认为notable_definition.json
            
        返回:
            dict: 包含表格视图列表的字典
        """
        try:
            # 确保有有效的表格ID
            table_id = self._ensure_table_id(table_id)
            # logger.info(f"开始获取表格视图列表，表格ID: {table_id}")
            
           
            if not self.dingtalk.get_notable_base_url:
                self.logger.error("get_notable_base_url 不能为空")
                raise ValueError("get_notable_base_url 不能为空")
            
            # 确保有有效的Access Token
            access_token = self.ensure_access_token()
            
            # 替换URL中的参数
            url = self.dingtalk.get_notable_base_url.replace("{table_id}", table_id).replace("{unionid}", self.dingtalk.operator_id)
            self.logger.debug(f"请求URL: {url}")
            
            # 设置请求头
            headers = {
                "Content-Type": "application/json",
                "x-acs-dingtalk-access-token": access_token
            }
            
            # logger.info(f"发送请求获取表格视图列表: {url}")
            
            # 使用统一的请求方法
            try:
                result = self.dingtalk.call_dingtalk_api(
                    method='GET',
                    url=url,
                    headers=headers,
                    timeout_type="get_views"
                )
                
                self.logger.debug(f"API响应: {json.dumps(result, ensure_ascii=False)[:500]}...")
                
                # 初始化输出文件路径变量
                output_file_path = None
                
                # 如果需要保存到文件
                if save_to_file and result:
                    # 修改输出文件路径到notable目录
                    output_file_path = os.path.join(self.notable_dir, os.path.basename(output_file))
                    
                    # 保存结果到文件
                    with open(output_file_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    # logger.info(f"已将表格视图列表保存到文件: {output_file_path}")
                
                # 计算视图数量 - 兼容不同的响应格式
                views = []
                if 'items' in result:
                    views = result.get('items', [])
                elif 'value' in result:
                    views = result.get('value', [])
                else:
                    self.logger.warning("响应中未找到'items'或'value'字段，无法确定视图列表")
                
                views_count = len(views)
                # logger.info(f"成功获取表格视图列表，共 {views_count} 个视图")
                
                # 直接在日志中显示前几个视图的基本信息
                if views:
                    # logger.info("表格视图列表摘要:")
                    for idx, view in enumerate(views[:5], 1):  # 只显示前5个
                        view_name = view.get('name', '未命名视图')
                        view_id = view.get('id', view.get('sheetId', '无ID'))
                        # logger.info(f"  {idx}. {view_name} (ID: {view_id})")
                    
                    if views_count > 5 and output_file_path:
                        self.logger.info(f"  ...共 {views_count} 个视图，更多详情请查看 {output_file_path}")
                    elif views_count > 5:
                        self.logger.info(f"  ...共 {views_count} 个视图")
                
                return result
                
            except requests.exceptions.HTTPError as e:
                self.logger.error(f"HTTP错误: {str(e)}")
                
                if hasattr(e, 'response') and e.response:
                    status_code = e.response.status_code
                    if status_code == 401:
                        self.logger.error("身份验证失败，请检查Access Token是否有效")
                    elif status_code == 403:
                        self.logger.error("权限不足，当前用户无权限访问该表格")
                    elif status_code == 404:
                        self.logger.error(f"表格不存在或未找到，请检查表格ID: {table_id}")
                    elif status_code == 500:
                        self.logger.error("服务器内部错误，可能是表格ID不正确或服务器临时性故障")
                    
                    # 尝试解析错误响应
                    try:
                        error_detail = e.response.json()
                        self.logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                    except:
                        self.logger.error(f"原始响应内容: {e.response.text[:500]}...")
                
                raise
            
        except requests.exceptions.Timeout:
            self.logger.error("获取表格视图列表请求超时")
            self.logger.error(get_error_message("get_views"))
            raise
        except requests.exceptions.RequestException as e:
            self.logger.error(f"获取表格视图列表请求失败: {str(e)}")
            if hasattr(e, 'response') and e.response:
                self.logger.error(f"响应状态码: {e.response.status_code}")
                try:
                    error_detail = e.response.json()
                    self.logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                except:
                    self.logger.error(f"响应内容: {e.response.text[:500]}...")
            raise
        except Exception as e:
            self.logger.error(f"获取表格视图列表时出现未知错误: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise

    def get_table_records(self, table_id=None, sheet_name="任务管理", definition_file="notable_definition.json", 
                         save_to_file=True, output_file=None):
        """
        获取钉钉多维表中指定表格视图的记录数据，支持分页
        
        参数:
            table_id (str, optional): 多维表ID，如果不提供则使用配置中的notable_id
            sheet_name (str): 表格视图名称，默认为"任务管理"
            definition_file (str): 表格定义文件路径，默认为"notable_definition.json"
            save_to_file (bool): 是否保存结果到文件，默认为True
            output_file (str, optional): 输出文件名，默认为"{sheet_name}.json"
            
        返回:
            dict: 包含表格记录数据的字典
        """
        try:
            # 确保有有效的表格ID
            table_id = self._ensure_table_id(table_id)
            
            # 如果未提供output_file，则使用默认文件名
            if not output_file:
                output_file = f"{sheet_name}.json"
            
            # logger.info(f"开始获取表格记录，表格ID: {table_id}，表格视图: {sheet_name}")
            
            # 查找sheet_id
            sheet_id = self._find_sheet_id(sheet_name, definition_file)
            
           
            if not self.dingtalk.get_notable_records_url:
                self.logger.error("get_notable_records_url 不能为空")
                raise ValueError("get_notable_records_url 不能为空")
            
            # 确保有有效的Access Token
            access_token = self.ensure_access_token()
            
            # 替换URL中的参数
            url = self.dingtalk.get_notable_records_url.replace("{table_id}", table_id).replace("{sheetname}", sheet_id).replace("{unionid}", self.dingtalk.operator_id)
            self.logger.debug(f"请求URL: {url}")
            
            # 设置请求头
            headers = {
                "Content-Type": "application/json",
                "x-acs-dingtalk-access-token": access_token
            }
            
            # 分页获取所有记录
            all_records = []
            next_token = None
            hasMore = True
            page_index = 1
            max_page_retries = 5  # 每页最大重试次数
            
            # 初始化进度条，但不确定总页数，所以使用不确定模式
            with tqdm(desc="获取表格记录", unit="页",leave=False) as pbar:
                while hasMore:
                    # 构建分页参数
                    pagination_url = url
                    if next_token:
                        if '?' in pagination_url:
                            pagination_url += f"&nextToken={next_token}"
                        else:
                            pagination_url += f"?nextToken={next_token}"
                    
                    # logger.info(f"发送请求获取表格记录 (页码: {page_index}): {pagination_url}")
                    
                    # 使用带重试的HTTP请求
                    page_retry_count = 0
                    page_success = False
                    
                    while page_retry_count < max_page_retries and not page_success:
                        try:
                            # 使用自定义的重试策略
                            response = None
                            try:
                                # 优先使用call_dingtalk_api方法
                                result = self.dingtalk.call_dingtalk_api(
                                    method='GET',
                                    url=pagination_url,
                                    headers=headers,
                                    timeout_type="get_records",
                                    retry_strategy="record_operation",
                                    max_retries=5  # 每次API调用最多重试5次，从3增加到5
                                )
                                page_success = True
                            except AttributeError:  # 如果call_dingtalk_api方法不存在，使用原始方式
                                self.logger.warning("call_dingtalk_api方法不可用，使用原始请求方式")
                                # 发送GET请求获取表格记录
                                response = requests.get(
                                    pagination_url,
                                    headers=headers,
                                    timeout=get_timeout("get_records")  # 使用配置的获取记录超时时间
                                )
                                # 检查响应状态 
                                response.raise_for_status()
                                result = response.json()
                                page_success = True
                                
                        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError, 
                                requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
                            # 服务器错误(5xx)或连接/超时错误，可以重试
                            is_server_error = (hasattr(e, 'response') and e.response is not None and 
                                               e.response.status_code >= 500)
                                
                            if is_server_error or isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                                page_retry_count += 1
                                
                                # 连续失败时使用更长的等待时间
                                if page_retry_count >= 3:
                                    # 对于连续多次失败，使用更长的等待时间
                                    wait_time = 5 * (3 ** (page_retry_count - 2))  # 5, 15, 45, 135秒...
                                else:
                                    wait_time = 2 * (2 ** page_retry_count)  # 2, 4, 8秒...
                                
                                jitter = random.uniform(0.8, 1.2)  # 增加随机抖动
                                wait_time = min(wait_time * jitter, 180)  # 最多等待180秒
                                
                                self.logger.warning(f"获取第 {page_index} 页记录失败 ({page_retry_count}/{max_page_retries})，"
                                              f"等待 {wait_time:.2f} 秒后重试: {str(e)}")
                                
                                # 添加更详细的错误日志和诊断信息
                                if hasattr(e, 'response') and e.response is not None:
                                    try:
                                        error_detail = e.response.json() if e.response.content else "无响应内容"
                                        self.logger.warning(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)[:500]}")
                                    except:
                                        self.logger.warning(f"响应内容: {e.response.text[:500] if e.response.text else '无响应内容'}")
                                
                                # 添加网络诊断信息
                                if isinstance(e, requests.exceptions.ConnectionError):
                                    self.logger.warning("网络连接错误，可能是网络不稳定或服务器暂时不可用")
                                elif isinstance(e, requests.exceptions.Timeout):
                                    self.logger.warning(f"请求超时，当前超时设置为 {get_timeout('get_records')} 秒")
                                
                                # 如果是最后一次重试前，记录更多诊断信息
                                if page_retry_count == max_page_retries - 1:
                                    self.logger.warning("这是最后一次重试，记录额外的诊断信息:")
                                    self.logger.warning(f"请求URL: {pagination_url}")
                                    self.logger.warning(f"请求头: {headers}")
                                    
                                    # 尝试进行简单的网络诊断
                                    try:
                                        import socket
                                        hostname = pagination_url.split('/')[2].split(':')[0]
                                        self.logger.warning(f"尝试解析主机名 {hostname}...")
                                        ip = socket.gethostbyname(hostname)
                                        self.logger.warning(f"主机名 {hostname} 解析为IP: {ip}")
                                    except Exception as dns_e:
                                        self.logger.warning(f"DNS解析失败: {str(dns_e)}")
                                
                                time.sleep(wait_time)
                            else:
                                # 其他HTTP错误，不重试
                                self.logger.error(f"获取第 {page_index} 页记录失败，非服务器错误，不再重试: {str(e)}")
                                if hasattr(e, 'response') and e.response is not None:
                                    self.logger.error(f"状态码: {e.response.status_code}")
                                    try:
                                        error_detail = e.response.json()
                                        self.logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                                    except:
                                        self.logger.error(f"响应内容: {e.response.text[:500]}...")
                                raise
                        except Exception as e:
                            # 其他未知错误，记录详情但不重试
                            self.logger.error(f"获取第 {page_index} 页记录时发生未知错误: {str(e)}")
                            self.logger.error(traceback.format_exc())
                            raise
                    
                    # 如果尝试了最大次数仍失败，跳出循环
                    if not page_success:
                        self.logger.error(f"获取第 {page_index} 页记录失败，已达到最大重试次数: {max_page_retries}")
                        
                        # 如果已经获取了一些记录，可以选择继续处理已有记录而不是直接失败
                        if len(all_records) > 0:
                            self.logger.warning(f"虽然获取第 {page_index} 页失败，但已成功获取了 {len(all_records)} 条记录，将继续处理已有数据")
                            hasMore = False  # 停止获取更多页
                            break
                        else:
                            raise Exception(f"获取第 {page_index} 页记录失败，已达到最大重试次数")
                    
                    # 提取记录数据
                    page_records = []
                    if 'records' in result:
                        # page_records = result.get('records', [])
                        page_records = self.safe_get(result, 'records', []) 
                                        
                        # 保存原始API响应结果到JSON文件，方便调试
                        # debug_file = f"api_response_{sheet_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        # with open(debug_file, 'w', encoding='utf-8') as f:
                        #     json.dump(result, f, ensure_ascii=False, indent=2)
                        # logger.info(f"已将API原始响应保存到: {debug_file}")
                        
                        
                    else:
                        self.logger.warning("响应中未找到'records'字段，无法确定记录列表")
                    
                    # 添加到总记录列表
                    all_records.extend(page_records)
                    
                    # 记录本页获取的记录数
                    page_records_count = len(page_records)
                    # logger.info(f"成功获取第 {page_index} 页记录，本页记录数: {page_records_count}，当前总记录数: {len(all_records)}")
                    
                    # 更新进度条
                    pbar.update(1)
                    pbar.set_postfix({"页码": page_index, "本页记录": page_records_count, "总记录": len(all_records)})
                    
                    # 检查是否有下一页
                    next_token = result.get('nextToken')
                    hasMore = result.get("hasMore", False) 
                    # 如果获取到的记录数量为0，但API返回hasMore=True，可能是API异常
                    if page_records_count == 0 and hasMore:
                        self.logger.warning(f"警告：第 {page_index} 页没有返回任何记录，但API表示还有更多页面")
                        # 记录异常情况，但继续尝试获取下一页
                        if next_token is None:
                            self.logger.error("API返回hasMore=True但没有提供nextToken，无法继续获取")
                            self.logger.warning("由于无法继续分页，将停止获取更多记录")
                            hasMore = False
                            break
                    
                    # 添加延迟，避免请求过于频繁触发限流
                    if hasMore:                        
                        countdown(5,10,msg='等待下一次同步',new_line=True)
                        # time.sleep(30)  # 每页请求间隔0.5秒
                    if not hasMore:
                        # logger.info("没有更多页面，记录获取完毕")
                        break
                    
                    # 增加页码计数
                    page_index += 1
            
            # 构建完整结果
            api_result = {
                'totalRecords': len(all_records),                
                'records': all_records
            }
            
            # 如果需要保存到文件
            if save_to_file and api_result:
                # 修改输出文件路径到notable目录
                output_file_path = os.path.join(self.notable_dir, os.path.basename(output_file))
                
                # 检查本地文件是否存在
                local_data = None
                if os.path.exists(output_file_path):
                    try:
                        with open(output_file_path, 'r', encoding='utf-8') as f:
                            local_data = json.load(f)
                        # logger.info(f"读取到本地文件: {output_file_path}")
                    except Exception as e:
                        self.logger.error(f"读取本地文件时出错，将创建新文件: {str(e)}")
                        local_data = None
                
                # 构建本地记录的字典，以recordId为键
                local_records_dict = {}
                if local_data and 'records' in local_data and local_data['records']:
                    for record in local_data['records']:
                        if 'id' in record:
                            local_records_dict[record['id']] = record
                
                # 处理每条API记录
                processed_records = []
                dingding_count = 0
                local_count = 0
                
                # 为本地处理添加进度条
                with tqdm(total=len(all_records), desc="处理记录", unit="条") as process_bar:
                    for record in all_records:
                        record_id = record.get('id')
                        
                        # 如果本地没有这条记录，或者API记录的lastModifiedTime更新，则更新AI核定字段
                        if (record_id not in local_records_dict or 
                            ('lastModifiedTime' in record and 
                             'lastModifiedTime' in local_records_dict[record_id] and 
                             record['lastModifiedTime'] > local_records_dict[record_id]['lastModifiedTime'])):
                            
                            # # 添加或重置AI核定相关字段
                            # record.update({
                            #     "需要AI核定": True,
                            #     "需要上传推理结论": False
                            # })

                            dingding_count += 1
                            
                            if record_id in local_records_dict:
                                self.logger.debug(f"记录 {record_id} 已更新，重置AI核定字段。API时间: {record.get('lastModifiedTime')}, 本地时间: {local_records_dict[record_id].get('lastModifiedTime')}")
                            else:
                                self.logger.debug(f"新记录 {record_id}，添加AI核定字段")
                        else:
                            # 如果本地记录已是最新，保留本地的AI核定字段
                            local_record = local_records_dict[record_id]
                            # for field in ["需要AI核定"]:
                            #     if field in local_record:
                            #         record[field] = local_record[field]
                            #     else:
                            #         record[field] = None if field != "需要AI核定" else True
                            
                            local_count += 1
                            self.logger.debug(f"记录 {record_id} 未更新，保留本地AI核定字段")
                        
                        processed_records.append(record)
                        process_bar.update(1)
                        process_bar.set_postfix({"更新": dingding_count, "保留": local_count})
                
                # 保存更新后的结果到文件
                complete_result = {
                    'totalRecords': len(processed_records),
                    'records': processed_records
                }
                
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    json.dump(complete_result, f, ensure_ascii=False, indent=2)
                # logger.info(f"已将表格记录保存到文件，处理了 {len(processed_records)} 条记录: {output_file_path},其中从钉钉更新了 {dingding_count} 条记录，本地 {local_count} 条记录不需要更新")
            else:
                complete_result = api_result
            
            self.logger.info(f"成功获取表格记录，总记录数: {len(all_records)}")
            
            return complete_result
            
        except requests.exceptions.Timeout:
            self.logger.error("获取表格记录请求超时")
            self.logger.error(get_error_message("get_records"))
            raise
        except requests.exceptions.RequestException as e:
            self.logger.error(f"获取表格记录请求失败: {str(e)}")
            if hasattr(e, 'response') and e.response:
                self.logger.error(f"响应状态码: {e.response.status_code}")
                try:
                    error_detail = e.response.json()
                    self.logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                except:
                    self.logger.error(f"响应内容: {e.response.text[:500]}...")
            raise
        except Exception as e:
            self.logger.error(f"获取表格记录时出现未知错误: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise

    def _save_failed_record(self, record, error_info, sheet_name):
        """
        保存同步失败的记录到文件
        
        参数:
            record (dict): 失败的记录数据
            error_info (str): 错误信息
            sheet_name (str): 表格视图名称
            
        返回:
            bool: 保存是否成功
        """
        try:
            # 构建失败记录的数据结构
            failed_record = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sheet_name": sheet_name,
                "record": record,
                "error": error_info
            }
            
            # 构建失败记录文件路径
            failed_records_file = os.path.join(self.notable_dir, "failed_records.json")
            
            # 读取现有的失败记录
            existing_records = []
            if os.path.exists(failed_records_file):
                try:
                    with open(failed_records_file, 'r', encoding='utf-8') as f:
                        existing_records = json.load(f)
                except json.JSONDecodeError:
                    self.logger.warning("失败记录文件格式错误，将创建新文件")
                    existing_records = []
            
            # 添加新的失败记录
            existing_records.append(failed_record)
            
            # 保存更新后的失败记录
            with open(failed_records_file, 'w', encoding='utf-8') as f:
                json.dump(existing_records, f, ensure_ascii=False, indent=2)
            
            # logger.info(f"已将失败的记录保存到文件: {failed_records_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存失败记录时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False

    def set_table_records(self, table_id=None, sheet_name="资源池", definition_file="notable_definition.json", 
                         input_file=None, handle_null=False):
        """
        设置钉钉多维表中的记录
        
        参数:
            table_id (str, optional): 多维表ID，如果不提供则使用配置中的notable_id
            sheet_name (str): 表格视图名称，默认为"任务管理"
            definition_file (str): 表格定义文件路径，默认为"notable_definition.json"
            input_file (str): 输入文件路径，包含要设置的记录
            handle_null (bool): 是否处理空值，默认为False
            
        返回:
            bool: 操作是否成功
        """
        try:
            # 验证必要参数
            if not input_file:
                self.logger.error("未提供输入文件路径")
                return False
            
            # 检查输入文件是否存在
            if not os.path.exists(input_file):
                self.logger.error(f"输入文件不存在: {input_file}")
                return False
            
            # 读取输入文件
            try:
                with open(input_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                self.logger.error(f"读取输入文件时出错: {str(e)}")
                return False
            
            # 验证数据结构
            if not isinstance(data, dict) or 'records' not in data or 'totalRecords' not in data:
                self.logger.error("输入文件格式不正确，缺少records或totalRecords字段")
                return False
            
            records = data.get('records', [])
            total_records = len(records) # 使用实际记录数作为总数
            
            if not records:
                self.logger.warning("没有记录需要设置")
                return True
            
            # 获取sheet_id
            sheet_id = self._find_sheet_id(sheet_name, definition_file)
            
            # 确保有有效的table_id
            table_id = self._ensure_table_id(table_id)
            
            # 使用tqdm创建进度条
            with tqdm(total=total_records, desc=f"同步'{sheet_name}'", unit="条",leave=False) as pbar:
                for record in records:
                    try:
                        # 从文件记录中提取ID和字段
                        record_id = record.get("id")
                        fields_data = record.get("fields", {})

                        if not record_id:
                            warning_msg = f"记录缺少'id'字段，无法进行存在性检查，跳过此记录: {record}"
                            self.logger.warning(warning_msg)
                            self._save_failed_record(record, warning_msg, sheet_name)
                            pbar.update(1)
                            continue

                        # 调用强化后的 add_record 方法进行处理
                        created_id, message = self.add_record(
                            sheet_name=sheet_name,
                            fields=fields_data,
                            fields_id=record_id,
                            table_id=table_id
                        )

                        # 根据返回结果更新进度条和日志
                        if created_id:
                            pbar.set_postfix_str("成功")
                        else:                           
                            self.logger.error(f"处理记录 {record_id} 失败: {message}")
                            self._save_failed_record(record, message, sheet_name)
                            pbar.set_postfix_str("失败")
                        
                    except Exception as e:
                        # 捕获循环内的意外异常，确保主循环不会中断
                        error_msg = f"处理记录 {record.get('id', '未知ID')} 时发生意外错误: {str(e)}"
                        self.logger.error(error_msg)
                        self.logger.error(traceback.format_exc())
                        self._save_failed_record(record, error_msg, sheet_name)
                        pbar.set_postfix_str("异常")
                    
                    finally:
                        # 无论成功、失败还是跳过，都更新进度条
                        pbar.update(1)
                        # 保留适当的延时，避免触发API限流
                        time.sleep(1) # 增加延时到1秒
                                      
            return True
        except Exception as e:
            self.logger.error(f"设置表格 '{sheet_name}' 记录时发生严重错误: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False

    def _ensure_table_id(self, table_id=None):
        """
        确保有有效的表格ID，如果未提供则使用配置中的默认值
        
        参数:
            table_id (str, optional): 多维表ID，如果不提供则使用配置中的notable_id
            
        返回:
            str: 有效的表格ID
            
        抛出:
            ValueError: 如果未提供表格ID且配置中不存在默认notable_id
        """
        if not table_id:
            table_id = self.dingtalk.notable_id
        return table_id
                