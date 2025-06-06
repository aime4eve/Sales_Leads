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
# 导入Dify类
from Dify import Dify
# 导入DingTalk类
from DingTalk import DingTalk
# 导入tqdm进度条
from tqdm import tqdm
# 导入随机库，用于指数退避策略中的抖动
import random
# 导入超时配置
from timeout_config import get_timeout, get_error_message, get_timeout_tuple, get_retry_strategy

# 配置日志记录
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Notable")

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
        logger.info(len(datetime_str) == 13 and timestamp > 0)
        return len(datetime_str) == 13 and timestamp > 0
    except (ValueError, TypeError):
        return False

class Notable:
    def __init__(self, config_path=None, config_dict=None):
        try:
            # 创建DingTalk实例用于API访问
            self.dingtalk = DingTalk(config_path=config_path, config_dict=config_dict)            

            # 设置notable_dir为当前Python文件所在目录下的notable子目录
            self.notable_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notable")                                      
            # 确保notable目录存在
            if not os.path.exists(self.notable_dir):
                os.makedirs(self.notable_dir)
                logger.info(f"创建notable目录: {self.notable_dir}")
            

        except Exception as e:
            logger.error(f"加载配置文件时出错：{str(e)}")
            logger.error(traceback.format_exc())
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
            logger.debug(f"从表格定义文件中查找视图ID: {definition_file_path}")
            try:
                with open(definition_file_path, 'r', encoding='utf-8') as f:
                    definition_data = json.load(f)
                
                # 查找匹配的sheet_name
                views = []
                if 'items' in definition_data:
                    views = definition_data.get('items', [])
                elif 'value' in definition_data:
                    views = definition_data.get('value', [])
                
                for view in views:
                    if view.get('name') == sheet_name:
                        sheet_id = view.get('id', view.get('sheetId'))
                        logger.debug(f"找到表格视图 '{sheet_name}' 的ID: {sheet_id}")
                        return sheet_id
                
                logger.warning(f"在表格定义中未找到名为 '{sheet_name}' 的视图，将尝试直接使用sheet_name作为ID")
            except Exception as e:
                logger.error(f"读取表格定义文件时出错: {str(e)}")
                logger.warning(f"将尝试直接使用sheet_name作为ID: {sheet_name}")
        else:
            logger.warning(f"表格定义文件不存在: {definition_file_path}")
            logger.warning(f"将尝试直接使用sheet_name作为ID: {sheet_name}")
        
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
                    logger.warning(f"字段 {field_key} 的markdown内容已从 {len(markdown_text)} 字符截断至 {len(truncated_text)} 字符")
            
            # 对于字符串类型的字段
            elif isinstance(field_value, str):
                if len(field_value) > max_length:
                    truncated_text = field_value[:max_length] + "...(已截断)"
                    field_value = truncated_text
                    logger.warning(f"字段 {field_key} 的字符串内容已从 {len(field_value)} 字符截断至 {len(truncated_text)} 字符")
            
            # 对于数字类型的字段，转换为字符串处理
            elif isinstance(field_value, (int, float)):
                field_value_str = str(field_value)
                if len(field_value_str) > max_length:
                    logger.warning(f"数值型字段 {field_key} 的长度异常: {len(field_value_str)} 字符")
                    # 一般情况下，数值不会超过长度限制，这里只记录警告
            
            return field_value
        except Exception as e:
            logger.error(f"截断字段 {field_key} 时发生错误: {str(e)}")
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
                logger.error("记录ID不能为空")
                return None
                
            # 确保有有效的表格ID
            try:
                table_id = self._ensure_table_id(table_id)
            except ValueError as e:
                logger.error(str(e))
                return None
            
            logger.info(f"开始获取记录，表格ID: {table_id}，表格视图: {sheet_name}，记录ID: {record_id}")
            
            # 查找sheet_id
            sheet_id = self._find_sheet_id(sheet_name, definition_file)
            
           
            if not self.dingtalk.get_notable_record_byid_url:
                logger.error("get_notable_record_byid_url 不能为空")
                return None
            
            # 确保有有效的Access Token
            access_token = self.ensure_access_token()
            
            # 替换URL中的参数
            url = self.dingtalk.get_notable_record_byid_url.replace("{table_id}", table_id).replace("{sheetname}", sheet_id).replace("{record_id}", record_id).replace("{unionid}", self.dingtalk.operator_id)
            logger.debug(f"请求URL: {url}")
            
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
                
                logger.debug(f"API响应: {json.dumps(result, ensure_ascii=False)[:500]}...")
                
                # 验证响应中是否包含记录ID
                if "id" in result and result["id"] == record_id:
                    logger.info(f"成功获取记录 ID: {record_id}")
                    return result
                else:
                    logger.warning(f"获取记录 ID: {record_id} 返回的数据不匹配")
                    return None
                    
            except requests.exceptions.HTTPError as e:
                # 捕获HTTP错误
                if hasattr(e, 'response') and e.response is not None:
                    if e.response.status_code == 404:
                        logger.warning(f"记录 {record_id} 不存在")
                        return None
                    else:
                        logger.error(f"获取记录时发生HTTP错误: {e.response.status_code}")
                        try:
                            error_detail = e.response.json()
                            logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                        except:
                            logger.error(f"响应内容: {e.response.text[:500]}...")
                raise
            except requests.exceptions.Timeout:
                logger.error("获取记录请求超时")
                logger.error(get_error_message("get_record"))
                return None
            except Exception as e:
                logger.error(f"获取记录 ID: {record_id} 时发生未知错误: {str(e)}")
                logger.error(traceback.format_exc())
                return None
                
        except Exception as e:
            logger.error(f"获取记录操作过程中出现错误: {str(e)}")
            logger.error(traceback.format_exc())
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
            logger.info(f"验证记录 {record_id} 是否存在")
            
            # 调用get_table_record_byid方法获取记录
            record = self.get_table_record_byid(table_id, sheet_id, record_id)
            
            # 如果成功获取到记录，则返回True
            if record and "id" in record and record["id"] == record_id:
                logger.info(f"记录 {record_id} 存在")
                return True
            else:
                logger.warning(f"记录 {record_id} 不存在")
                return False
                
        except Exception as e:
            logger.error(f"验证记录存在性时发生错误: {str(e)}")
            logger.error(traceback.format_exc())
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
            logger.info(f"开始获取表格视图列表，表格ID: {table_id}")
            
           
            if not self.dingtalk.get_notable_base_url:
                logger.error("get_notable_base_url 不能为空")
                raise ValueError("get_notable_base_url 不能为空")
            
            # 确保有有效的Access Token
            access_token = self.ensure_access_token()
            
            # 替换URL中的参数
            url = self.dingtalk.get_notable_base_url.replace("{table_id}", table_id).replace("{unionid}", self.dingtalk.operator_id)
            logger.debug(f"请求URL: {url}")
            
            # 设置请求头
            headers = {
                "Content-Type": "application/json",
                "x-acs-dingtalk-access-token": access_token
            }
            
            logger.info(f"发送请求获取表格视图列表: {url}")
            
            # 使用统一的请求方法
            try:
                result = self.dingtalk.call_dingtalk_api(
                    method='GET',
                    url=url,
                    headers=headers,
                    timeout_type="get_views"
                )
                
                logger.debug(f"API响应: {json.dumps(result, ensure_ascii=False)[:500]}...")
                
                # 初始化输出文件路径变量
                output_file_path = None
                
                # 如果需要保存到文件
                if save_to_file and result:
                    # 修改输出文件路径到notable目录
                    output_file_path = os.path.join(self.notable_dir, os.path.basename(output_file))
                    
                    # 保存结果到文件
                    with open(output_file_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    logger.info(f"已将表格视图列表保存到文件: {output_file_path}")
                
                # 计算视图数量 - 兼容不同的响应格式
                views = []
                if 'items' in result:
                    views = result.get('items', [])
                elif 'value' in result:
                    views = result.get('value', [])
                else:
                    logger.warning("响应中未找到'items'或'value'字段，无法确定视图列表")
                
                views_count = len(views)
                logger.info(f"成功获取表格视图列表，共 {views_count} 个视图")
                
                # 直接在日志中显示前几个视图的基本信息
                if views:
                    logger.info("表格视图列表摘要:")
                    for idx, view in enumerate(views[:5], 1):  # 只显示前5个
                        view_name = view.get('name', '未命名视图')
                        view_id = view.get('id', view.get('sheetId', '无ID'))
                        logger.info(f"  {idx}. {view_name} (ID: {view_id})")
                    
                    if views_count > 5 and output_file_path:
                        logger.info(f"  ...共 {views_count} 个视图，更多详情请查看 {output_file_path}")
                    elif views_count > 5:
                        logger.info(f"  ...共 {views_count} 个视图")
                
                return result
                
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP错误: {str(e)}")
                
                if hasattr(e, 'response') and e.response:
                    status_code = e.response.status_code
                    if status_code == 401:
                        logger.error("身份验证失败，请检查Access Token是否有效")
                    elif status_code == 403:
                        logger.error("权限不足，当前用户无权限访问该表格")
                    elif status_code == 404:
                        logger.error(f"表格不存在或未找到，请检查表格ID: {table_id}")
                    elif status_code == 500:
                        logger.error("服务器内部错误，可能是表格ID不正确或服务器临时性故障")
                    
                    # 尝试解析错误响应
                    try:
                        error_detail = e.response.json()
                        logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                    except:
                        logger.error(f"原始响应内容: {e.response.text[:500]}...")
                
                raise
            
        except requests.exceptions.Timeout:
            logger.error("获取表格视图列表请求超时")
            logger.error(get_error_message("get_views"))
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"获取表格视图列表请求失败: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"响应状态码: {e.response.status_code}")
                try:
                    error_detail = e.response.json()
                    logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                except:
                    logger.error(f"响应内容: {e.response.text[:500]}...")
            raise
        except Exception as e:
            logger.error(f"获取表格视图列表时出现未知错误: {str(e)}")
            logger.error(traceback.format_exc())
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
            
            logger.info(f"开始获取表格记录，表格ID: {table_id}，表格视图: {sheet_name}")
            
            # 查找sheet_id
            sheet_id = self._find_sheet_id(sheet_name, definition_file)
            
           
            if not self.dingtalk.get_notable_records_url:
                logger.error("get_notable_records_url 不能为空")
                raise ValueError("get_notable_records_url 不能为空")
            
            # 确保有有效的Access Token
            access_token = self.ensure_access_token()
            
            # 替换URL中的参数
            url = self.dingtalk.get_notable_records_url.replace("{table_id}", table_id).replace("{sheetname}", sheet_id).replace("{unionid}", self.dingtalk.operator_id)
            logger.debug(f"请求URL: {url}")
            
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
            with tqdm(desc="获取表格记录", unit="页") as pbar:
                while hasMore:
                    # 构建分页参数
                    pagination_url = url
                    if next_token:
                        if '?' in pagination_url:
                            pagination_url += f"&nextToken={next_token}"
                        else:
                            pagination_url += f"?nextToken={next_token}"
                    
                    logger.info(f"发送请求获取表格记录 (页码: {page_index}): {pagination_url}")
                    
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
                                logger.warning("call_dingtalk_api方法不可用，使用原始请求方式")
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
                                
                                logger.warning(f"获取第 {page_index} 页记录失败 ({page_retry_count}/{max_page_retries})，"
                                              f"等待 {wait_time:.2f} 秒后重试: {str(e)}")
                                
                                # 添加更详细的错误日志和诊断信息
                                if hasattr(e, 'response') and e.response is not None:
                                    try:
                                        error_detail = e.response.json() if e.response.content else "无响应内容"
                                        logger.warning(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)[:500]}")
                                    except:
                                        logger.warning(f"响应内容: {e.response.text[:500] if e.response.text else '无响应内容'}")
                                
                                # 添加网络诊断信息
                                if isinstance(e, requests.exceptions.ConnectionError):
                                    logger.warning("网络连接错误，可能是网络不稳定或服务器暂时不可用")
                                elif isinstance(e, requests.exceptions.Timeout):
                                    logger.warning(f"请求超时，当前超时设置为 {get_timeout('get_records')} 秒")
                                
                                # 如果是最后一次重试前，记录更多诊断信息
                                if page_retry_count == max_page_retries - 1:
                                    logger.warning("这是最后一次重试，记录额外的诊断信息:")
                                    logger.warning(f"请求URL: {pagination_url}")
                                    logger.warning(f"请求头: {headers}")
                                    
                                    # 尝试进行简单的网络诊断
                                    try:
                                        import socket
                                        hostname = pagination_url.split('/')[2].split(':')[0]
                                        logger.warning(f"尝试解析主机名 {hostname}...")
                                        ip = socket.gethostbyname(hostname)
                                        logger.warning(f"主机名 {hostname} 解析为IP: {ip}")
                                    except Exception as dns_e:
                                        logger.warning(f"DNS解析失败: {str(dns_e)}")
                                
                                time.sleep(wait_time)
                            else:
                                # 其他HTTP错误，不重试
                                logger.error(f"获取第 {page_index} 页记录失败，非服务器错误，不再重试: {str(e)}")
                                if hasattr(e, 'response') and e.response is not None:
                                    logger.error(f"状态码: {e.response.status_code}")
                                    try:
                                        error_detail = e.response.json()
                                        logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                                    except:
                                        logger.error(f"响应内容: {e.response.text[:500]}...")
                                raise
                        except Exception as e:
                            # 其他未知错误，记录详情但不重试
                            logger.error(f"获取第 {page_index} 页记录时发生未知错误: {str(e)}")
                            logger.error(traceback.format_exc())
                            raise
                    
                    # 如果尝试了最大次数仍失败，跳出循环
                    if not page_success:
                        logger.error(f"获取第 {page_index} 页记录失败，已达到最大重试次数: {max_page_retries}")
                        
                        # 如果已经获取了一些记录，可以选择继续处理已有记录而不是直接失败
                        if len(all_records) > 0:
                            logger.warning(f"虽然获取第 {page_index} 页失败，但已成功获取了 {len(all_records)} 条记录，将继续处理已有数据")
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
                        logger.warning("响应中未找到'records'字段，无法确定记录列表")
                    
                    # 添加到总记录列表
                    all_records.extend(page_records)
                    
                    # 记录本页获取的记录数
                    page_records_count = len(page_records)
                    logger.info(f"成功获取第 {page_index} 页记录，本页记录数: {page_records_count}，当前总记录数: {len(all_records)}")
                    
                    # 更新进度条
                    pbar.update(1)
                    pbar.set_postfix({"页码": page_index, "本页记录": page_records_count, "总记录": len(all_records)})
                    
                    # 检查是否有下一页
                    next_token = result.get('nextToken')
                    hasMore = result.get("hasMore", False) 
                    # 如果获取到的记录数量为0，但API返回hasMore=True，可能是API异常
                    if page_records_count == 0 and hasMore:
                        logger.warning(f"警告：第 {page_index} 页没有返回任何记录，但API表示还有更多页面")
                        # 记录异常情况，但继续尝试获取下一页
                        if next_token is None:
                            logger.error("API返回hasMore=True但没有提供nextToken，无法继续获取")
                            logger.warning("由于无法继续分页，将停止获取更多记录")
                            hasMore = False
                            break
                    
                    # 添加延迟，避免请求过于频繁触发限流
                    if hasMore:
                        time.sleep(30)  # 每页请求间隔0.5秒
                    if not hasMore:
                        logger.info("没有更多页面，记录获取完毕")
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
                        logger.info(f"读取到本地文件: {output_file_path}")
                    except Exception as e:
                        logger.error(f"读取本地文件时出错，将创建新文件: {str(e)}")
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
                            
                            # 添加或重置AI核定相关字段
                            record.update({
                                "需要AI核定": True,
                                "需要上传推理结论": False
                            })

                            dingding_count += 1
                            
                            if record_id in local_records_dict:
                                logger.debug(f"记录 {record_id} 已更新，重置AI核定字段。API时间: {record.get('lastModifiedTime')}, 本地时间: {local_records_dict[record_id].get('lastModifiedTime')}")
                            else:
                                logger.debug(f"新记录 {record_id}，添加AI核定字段")
                        else:
                            # 如果本地记录已是最新，保留本地的AI核定字段
                            local_record = local_records_dict[record_id]
                            for field in ["需要AI核定"]:
                                if field in local_record:
                                    record[field] = local_record[field]
                                else:
                                    record[field] = None if field != "需要AI核定" else True
                            
                            local_count += 1
                            logger.debug(f"记录 {record_id} 未更新，保留本地AI核定字段")
                        
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
                logger.info(f"已将表格记录保存到文件，处理了 {len(processed_records)} 条记录: {output_file_path},其中从钉钉更新了 {dingding_count} 条记录，本地 {local_count} 条记录不需要更新")
            else:
                complete_result = api_result
            
            logger.info(f"成功获取表格记录，总记录数: {len(all_records)}")
            
            return complete_result
            
        except requests.exceptions.Timeout:
            logger.error("获取表格记录请求超时")
            logger.error(get_error_message("get_records"))
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"获取表格记录请求失败: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"响应状态码: {e.response.status_code}")
                try:
                    error_detail = e.response.json()
                    logger.error(f"错误详情: {json.dumps(error_detail, ensure_ascii=False)}")
                except:
                    logger.error(f"响应内容: {e.response.text[:500]}...")
            raise
        except Exception as e:
            logger.error(f"获取表格记录时出现未知错误: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def set_table_record_byid(self,id,fields, table_id=None,sheet_name="任务管理", definition_file="notable_definition.json"):

        try:
            table_id = self._ensure_table_id(table_id)
        except ValueError as e:
            return {"success": False, "message": str(e), "updated": 0, "total": 0}
                   # 使用配置中的正确URL格式
        sheet_id = self._find_sheet_id(sheet_name, definition_file)        
        update_url = self.dingtalk.set_notable_records_url.format(
            table_id=table_id,
            sheetname=sheet_id,
            unionid=self.dingtalk.operator_id
        )
        
        # 构建请求头
        
        access_token = self.ensure_access_token()
        headers = {
            'Content-Type': 'application/json',
            'x-acs-dingtalk-access-token': access_token
        }

        update_data = {
            "records":[{
                "id": id,
                "fields": fields
            }]
        }

        # 发送请求
        try:
            response = requests.post(update_url, headers=headers, json=update_data)
            
            # 检查是否成功
            if response.status_code in [200, 201]:
                
                logger.info(f"成功更新 {id} 记录")
                return {
                    "success": True,
                    "message": f"成功更新 1 条记录",
                    "updated": 1,
                    "total": 1,
                    "updated_records": update_data
                }
            else:
                error_response = None
                try:
                    error_response = response.json()
                except:
                    error_response = response.text[:500]
                
                error_message = f"API错误: {response.status_code} {error_response}"
                logger.error(error_message)
                return {
                    "success": False,
                    "message": error_message,
                    "updated": 0,
                    "total": 0,
                    "error_code": response.status_code
                }
        except Exception as e:
            logger.error(f"请求时出现异常: {str(e)}")
            # 确保traceback模块已导入，引用导入好的traceback模块
            logger.error(traceback.format_exc())
            return {
                "success": False, 
                "message": f"请求异常: {str(e)}",
                "updated": 0,
                "total": 0
            }                

    def set_table_records(self, table_id=None, sheet_name="任务管理", definition_file="notable_definition.json", 
                         input_file=None, handle_null=False):
        """
        根据本地JSON文件中的数据更新钉钉多维表中的记录
        
        更新逻辑：
        - 如果"需要AI核定"字段为False 且 "需要上传推理结论"字段为True，则更新以下字段：
          - "AI参考意见"
          - "AI核准工时"
          - "AI核准时间"
          - 推理结论相关字段
        - 否则不更新
        
        参数:
            table_id (str, optional): 多维表ID，如果不提供则使用配置中的notable_id
            sheet_name (str): 表格视图名称，默认为"任务管理"
            definition_file (str): 表格定义文件路径，默认为"notable_definition.json"
            input_file (str, optional): 输入文件名，默认为"{sheet_name}.json"
            handle_null (bool): 是否处理空值，默认为False
            
        返回:
            dict: 包含更新结果的字典
        """
        try:
            # 初始化错误统计
            error_stats = {
                "not_found_errors": 0,       # 404错误：记录不存在
                "too_long_errors": 0,        # 400错误：字段值过长
                "server_errors": 0,          # 500错误：服务器内部错误
                "timeout_errors": 0,         # 超时错误
                "other_errors": 0,           # 其他错误
                "retried_success": 0,        # 重试后成功的请求
                "null_values_handled": 0     # 处理的空值数量
            }
            
            # 确保有有效的表格ID
            try:
                table_id = self._ensure_table_id(table_id)
            except ValueError as e:
                return {"success": False, "message": str(e), "updated": 0, "total": 0}
            
            # 如果未提供input_file，则使用默认文件名
            if not input_file:
                input_file = f"{sheet_name}.json"
                
            # 修改输入文件路径到notable目录
            input_file_path = os.path.join(self.notable_dir, os.path.basename(input_file))
                
            # 检查本地文件是否存在
            if not os.path.exists(input_file_path):
                logger.error(f"输入文件不存在: {input_file_path}")
                raise FileNotFoundError(f"输入文件不存在: {input_file_path}")
                
            logger.info(f"开始从文件读取数据: {input_file_path}")
            
            # 读取本地JSON文件
            with open(input_file_path, 'r', encoding='utf-8') as f:
                local_data = json.load(f)
                
            if not local_data or 'records' not in local_data or not local_data['records']:
                logger.warning(f"本地文件中未找到有效记录: {input_file_path}")
                return {"success": False, "message": "未找到有效记录", "updated": 0, "total": 0}
            
            # 处理空值
            if handle_null:
                try:
                    logger.info("启用空值处理功能")
                    # 动态导入null_handler模块，避免循环依赖
                    import null_handler
                    
                    # 处理记录中的空值
                    original_records = local_data['records']
                    local_data['records'] = null_handler.process_records(original_records)
                    
                    # 获取空值统计
                    null_stats = null_handler.get_null_statistics()
                    logger.info(f"空值处理完成，共处理 {null_stats['total_records']} 条记录，处理了 {null_stats['total_null_values']} 个空值")
                    error_stats["null_values_handled"] = null_stats['total_null_values']
                except Exception as e:
                    logger.error(f"空值处理过程中发生错误: {str(e)}")
                    logger.warning("将继续使用原始数据进行更新")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # 筛选需要更新的记录
            records_to_update = []

            # 添加筛选进度条
            with tqdm(total=len(local_data['records']), desc="筛选待更新记录", unit="条") as filter_bar:
                for record in local_data['records']:
                    # 检查更新条件：需要AI核定为False 且 需要上传推理结论为True 
                    if (record.get('需要AI核定', True) == False and record.get('需要上传推理结论', False) == True):
                        # 提取需要更新的字段
                        update_fields = {}
                        record_fields = record.get('fields', {})
                        for field in ["AI参考意见", "AI核准工时", "AI核准时间"]:
                            if field in record_fields:
                                # 对字段值进行截断处理已在set_table_record_byid中处理
                                update_fields[field] = record_fields[field] if record_fields[field] else "暂无"
                        
                        record_fields = record.get('AI推理日志',{})
                        for i, log in enumerate(record_fields):
                            推理结论 = log['推理结果'].get('最终结论', '')
                            # 对推理结论进行截断处理已在set_table_record_byid中处理
                            field_key = f"第{i+1}次推理"
                            update_fields[field_key] = {"markdown": 推理结论}

                        # 如果有需要更新的字段，添加到更新列表
                        logger.debug(f'{update_fields}')
                        if update_fields:
                            records_to_update.append({
                                "id": record.get('id'),
                                "fields": update_fields
                            })
                    filter_bar.update(1)
                    filter_bar.set_postfix({"待更新": len(records_to_update)})
            
            # 检查是否有需要更新的记录
            if not records_to_update:
                logger.info("没有需要更新的记录")
                return {"success": True, "message": "没有需要更新的记录", "updated": 0, "total": 0}
            
            logger.info(f"找到 {len(records_to_update)} 条记录需要更新")
            
            # 查找sheet_id
            sheet_id = self._find_sheet_id(sheet_name, definition_file)
            if not sheet_id:
                error_msg = f"在定义文件中未找到表格视图 '{sheet_name}' 的ID"
                logger.error(error_msg)
                return {"success": False, "message": error_msg, "updated": 0, "total": 0}
            logger.info(f"在定义文件中找到表格视图 '{sheet_name}' 的ID: {sheet_id}")
            
            # 确保有有效的Access Token
            self.ensure_access_token()
            
            # 构建API请求URL
            # 使用配置中的正确URL格式
            update_url = self.dingtalk.set_notable_records_url.format(
                table_id=table_id,
                sheetname=sheet_id,
                unionid=self.dingtalk.operator_id
            )
            
            # 构建请求头
            headers = {
                'Content-Type': 'application/json',
                'x-acs-dingtalk-access-token': self.dingtalk.access_token
            }
            
            # 构建请求体
            # 修改请求体结构，确保符合钉钉API要求
            records_to_update_list = []
            records_to_update_dict = {}
            
            for record in records_to_update:
                record_id = record.get('id')
                if record_id:
                    # 创建要更新的字段字典
                    fields_to_update = {
                        "AI参考意见": record.get("AI参考意见", {"markdown": ""}),
                        "AI核准工时": record.get("AI核准工时", ""),
                        "AI核准时间": record.get("AI核准时间", int(time.time() * 1000)),
                        "第1次推理": record.get("第1次推理", {"markdown": ""}),
                        "第2次推理": record.get("第2次推理", {"markdown": ""}),
                        "第3次推理": record.get("第3次推理", {"markdown": ""})
                    }
                    
                    # 将记录添加到请求体的records列表
                    records_to_update_list.append({
                        "id": record_id,
                        "fields": fields_to_update
                    })
                    
                    # 同时保存对字典的引用，方便后续更新本地记录状态
                    records_to_update_dict[record_id] = fields_to_update
            
            request_body = {
                "records": records_to_update_list
            }
            
            # 发送请求
            try:
                response = requests.post(update_url, headers=headers, json=request_body)
                
                # 检查是否成功
                if response.status_code in [200, 201]:
                    # 标记已更新的记录
                    updated_records = []
                    for record in local_data['records']:
                        if record.get('id') in records_to_update_dict:
                            # 更新记录的状态
                            record['需要上传推理结论'] = False
                            updated_records.append(record.get('id', 'unknown'))
                    
                    # 保存更新后的记录状态
                    with open(input_file_path, 'w', encoding='utf-8') as f:
                        json.dump(local_data, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"成功更新 {len(updated_records)} 条记录")
                    return {
                        "success": True,
                        "message": f"成功更新 {len(updated_records)} 条记录",
                        "updated": len(updated_records),
                        "total": len(records_to_update),
                        "updated_records": updated_records
                    }
                else:
                    error_response = None
                    try:
                        error_response = response.json()
                    except:
                        error_response = response.text[:500]
                    
                    error_message = f"API错误: {response.status_code} {error_response}"
                    logger.error(error_message)
                    return {
                        "success": False,
                        "message": error_message,
                        "updated": 0,
                        "total": len(records_to_update),
                        "error_code": response.status_code
                    }
            except Exception as e:
                logger.error(f"请求时出现异常: {str(e)}")
                # 确保traceback模块已导入，引用导入好的traceback模块
                logger.error(traceback.format_exc())
                return {
                    "success": False, 
                    "message": f"请求异常: {str(e)}",
                    "updated": 0,
                    "total": len(records_to_update_dict) if 'records_to_update_dict' in locals() else 0
                }
            
        except requests.exceptions.Timeout:
            logger.error("更新表格记录请求超时")
            logger.error(get_error_message("update_record"))
            return {"success": False, "message": "请求超时", "updated": 0, "total": 0}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP错误: {str(e)}")
            error_message = str(e)
            if hasattr(e, 'response') and e.response:
                try:
                    error_detail = e.response.json()
                    error_message = json.dumps(error_detail, ensure_ascii=False)
                    logger.error(f"错误详情: {error_message}")
                except:
                    error_message = e.response.text[:500]
                    logger.error(f"响应内容: {error_message}...")
            return {"success": False, "message": f"HTTP错误: {error_message}", "updated": 0, "total": 0}
        except Exception as e:
            logger.error(f"更新表格记录时出现未知错误: {str(e)}")
            logger.error(traceback.format_exc())
            return {"success": False, "message": f"未知错误: {str(e)}", "updated": 0, "total": 0}
                

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
            logger.info(f"使用配置中的默认多维表ID: {table_id}")
        return table_id
                