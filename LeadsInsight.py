import os
import json
import logging
import re
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, Tuple
import traceback
import time

from hkt_agent_framework.LLM.ConversationFlow import ConversationFlow, MockLLMClient
from hkt_agent_framework.LLM.SiliconCloud import SiliconCloud

from hkt_agent_framework.Tools import countdown 


logger = logging.getLogger(__name__)
root_logger = logging.getLogger()
logger.setLevel(root_logger.level)

# 导入Notable类
from hkt_agent_framework.DingTalk.Notable import Notable

class LeadsInsight:
    """
    LeadsInsight类，用于解析网页内容并同步到钉钉多维表格。
    
    根据设计文档，该类完成以下功能：
    1. 整理网页内容：从目录中获取最新的JSON文件
    2. 解析JSON文件内容：从Elementor_DB_*.json和submission_*.json文件中提取信息
    3. 通过Notable对象将数据同步到钉钉多维表
    """
    
    def __init__(self, elementor_db_dir: str = "elementor_db_sync", 
                 notable_config_path: Optional[str] = None,
                 target_table_name: str = "资源池"):
        """
        初始化LeadsInsight对象
        
        参数:
            elementor_db_dir (str): Elementor数据库同步目录
            notable_config_path (str, optional): Notable配置文件路径
            target_table_name (str): 目标表格名称，默认为"资源池"
        """
        self.elementor_db_dir = elementor_db_dir
        self.hktlora_sales_leads_dir = os.path.join(elementor_db_dir, "hktlora_sales_leads")
        self.dingtalk_sales_leads_dir = os.path.join(elementor_db_dir, "dingtalk_sales_leads")
        self.target_table_name = target_table_name
        self.llm_client = SiliconCloud()
        # self.llm_client = MockLLMClient() 
        self.llm_chat_flow = ConversationFlow(self.llm_client)
        
        
        # 确保hktlora_sales_leads目录存在
        if not os.path.exists(self.hktlora_sales_leads_dir):
            os.makedirs(self.hktlora_sales_leads_dir)
            logger.info(f"创建hktlora_sales_leads目录: {self.hktlora_sales_leads_dir}")
        
        # 确保dingtalk_sales_leads目录存在
        if not os.path.exists(self.dingtalk_sales_leads_dir):
            os.makedirs(self.dingtalk_sales_leads_dir)
            logger.info(f"创建dingtalk_sales_leads目录: {self.dingtalk_sales_leads_dir}")

        # 初始化Notable对象，用于同步数据到钉钉
        try:
            # 如果没有指定配置文件路径，使用默认路径
            if not notable_config_path:
                # 获取当前工作目录
                current_dir = os.path.abspath(os.path.dirname(__file__))
                # 构建配置文件路径
                notable_config_path = os.path.join(
                    current_dir,
                    "hkt_agent_framework",
                    "DingTalk",
                    "dingtalk_config.json"
                )
                logger.info(f"使用默认配置文件路径: {notable_config_path}")
            
            # 检查配置文件是否存在
            if not os.path.exists(notable_config_path):
                logger.error(f"配置文件不存在: {notable_config_path}")
                raise FileNotFoundError(f"配置文件不存在: {notable_config_path}")
            
            self.notable = Notable(config_path=notable_config_path)
            logger.info("Notable对象初始化成功")
            
            # 检查Notable对象是否正确读取配置
            if hasattr(self.notable, 'dingtalk') and hasattr(self.notable.dingtalk, 'notable_id'):
                logger.info(f"Notable配置信息: notable_id={self.notable.dingtalk.notable_id}")
                if not self.notable.dingtalk.notable_id:
                    logger.warning("Notable ID未配置，可能导致同步失败")
            else:
                logger.warning("无法读取Notable配置信息，可能导致同步失败")
        except Exception as e:
            logger.error(f"初始化Notable对象失败: {str(e)}")
            raise
    
    def _find_latest_directory(self, base_dir: str, pattern: str) -> Optional[str]:
        """
        按照指定模式查找最新的目录
        
        参数:
            base_dir (str): 基础目录
            pattern (str): 正则表达式模式
            
        返回:
            str: 最新目录的路径，如果未找到则返回None
        """
        try:
            # 列出所有目录
            dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
            
            # 按照模式筛选目录
            matched_dirs = []
            for d in dirs:
                if re.match(pattern, d):
                    try:
                        # 从目录名中提取日期时间部分
                        if pattern == r"\d{8}_\d{6}":
                            dt_str = d
                        elif pattern == r"retry_\d{8}_\d{6}":
                            dt_str = d[6:]  # 移除"retry_"前缀
                        else:
                            continue
                        
                        # 解析日期时间
                        dt = datetime.strptime(dt_str, "%Y%m%d_%H%M%S")
                        matched_dirs.append((d, dt))
                    except ValueError:
                        logger.warning(f"目录名 {d} 不符合日期时间格式 (%Y%m%d_%H%M%S)")
                        continue
            
            # 按日期时间排序
            if matched_dirs:
                matched_dirs.sort(key=lambda x: x[1], reverse=True)
                latest_dir = matched_dirs[0][0]
                logger.info(f"找到最新的目录: {latest_dir}")
                return os.path.join(base_dir, latest_dir)
            
            # logger.warning(f"未找到符合模式 {pattern} 的目录")
            return None
        
        except Exception as e:
            logger.error(f"查找最新目录时出错: {str(e)}")
            return None
    
    def delete_files_in_hktlora_sales_leads(self) -> bool:
        """
        删除hktlora_sales_leads目录中的submission_*.json文件和Elementor_DB_*.json文件
        """
        try:
            
            for file in os.listdir(self.hktlora_sales_leads_dir):
                # 删除hktlora_sales_leads目录中的submission_*.json文件
                if file.startswith('submission_'):
                    os.remove(os.path.join(self.hktlora_sales_leads_dir, file))
                # 删除hktlora_sales_leads目录中的Elementor_DB_*.json文件
                if file.startswith('Elementor_DB_'):
                    os.remove(os.path.join(self.hktlora_sales_leads_dir, file))

            # 删除elementor_db_sync目录中的retry_*目录下所有文件
            for item in os.listdir(self.elementor_db_dir):
                item_path = os.path.join(self.elementor_db_dir, item)
                if item.startswith('retry_') and os.path.isdir(item_path):
                    for file in os.listdir(item_path):
                        file_path = os.path.join(item_path, file)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    logger.debug(f"已清空目录: {item_path}")

            return True
        except Exception as e:
            logger.error(f"删除{self.elementor_db_dir}目录中的 submission_*.json文件\\Elementor_DB_*.json文件\\retry_*目录下所有文件时出错: {str(e)}")
            return False
    
    def initialize_dingtalk_sales_leads(self) -> bool:
        """
        初始化dingtalk_sales_leads目录中的数据，从钉钉多维表同步到本地
        
        返回:
            bool: 操作是否成功
        """
        try:
            logger.info("开始初始化dingtalk_sales_leads目录中的数据")
            
            # 1. 确保输出目录存在
            os.makedirs(self.dingtalk_sales_leads_dir, exist_ok=True)
            logger.info(f"确保输出目录存在: {self.dingtalk_sales_leads_dir}")
            
            # 删除dingtalk_sales_leads目录中的所有文件
            for file in os.listdir(self.dingtalk_sales_leads_dir):
                os.remove(os.path.join(self.dingtalk_sales_leads_dir, file))
            
            # 2. 获取多维表数据
            logger.info(f"开始从钉钉多维表获取数据: {self.target_table_name}")
            table_data = self.notable.get_table_records(
                sheet_name=self.target_table_name,
                save_to_file=False  # 不自动保存为单个文件
            )
            
            # 3. 初始化统计信息
            stats = {
                "total": 0,
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "errors": 0
            }
            
            # 获取记录总数
            records = table_data.get("records", [])
            total_records = len(records)
            logger.info(f"从钉钉多维表获取到 {total_records} 条记录")
            
            # 4. 遍历记录并保存
            from tqdm import tqdm
            with tqdm(total=total_records, desc="同步进度", unit="条",leave=False) as pbar:
                for record in records:
                    try:
                        # 提取记录ID和字段
                        record_id = record.get("id")
                        fields = record.get("fields", {})
                        
                        # 提取编号
                        post_id = fields.get("编号")
                        if not post_id:
                            logger.warning(f"记录 {record_id} 缺少编号字段，跳过")
                            stats["skipped"] += 1
                            pbar.update(1)
                            continue
                        
                        # 构造输出文件路径
                        output_file = os.path.join(self.dingtalk_sales_leads_dir, f"submission_{post_id}.json")
                        
                        # 构造输出数据
                        output_data = {
                            "form_submission": {
                                "Name": fields.get("客户", ""),
                                "Email": fields.get("电子邮件", ""),
                                "Country": fields.get("国家", ""),
                                "WhatsApp": fields.get("通讯号码", ""),
                                "Message": fields.get("留言内容", ""),
                                "Date of Submission": fields.get("留言日期", "")
                            },
                            "extra_information": {
                                "Submitted On": {
                                    "links": [
                                        {
                                            "text": "View Page",
                                            "href": fields.get("留言位置", "")
                                        },
                                        {
                                            "text": "Edit Page",
                                            "href": f"https://www.hktlora.com/wp-admin/post.php?action=edit&post={post_id}"
                                        }
                                    ],
                                    "full_text": "Quote (View Page | Edit Page)"
                                },
                                "Submitted By": "Not a registered user"
                            },
                            "dingding": {
                                "id": record_id,
                                "编号": post_id
                            }
                        }
                        
                        # 检查文件是否已存在
                        if os.path.exists(output_file):
                            stats["updated"] += 1
                        else:
                            stats["created"] += 1
                        
                        # 保存到文件
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(output_data, f, ensure_ascii=False, indent=4)
                        
                        stats["total"] += 1
                        
                    except Exception as e:
                        logger.error(f"处理记录 {record.get('id', '未知ID')} 时出错: {str(e)}")
                        logger.debug(traceback.format_exc())
                        stats["errors"] += 1
                    
                    # 更新进度条
                    pbar.update(1)
                    pbar.set_postfix({
                        "新建": stats["created"],
                        "更新": stats["updated"],
                        "跳过": stats["skipped"],
                        "错误": stats["errors"]
                    })
            
            # 打印统计信息
            logger.info(f"同步完成: 总记录数 {stats['total']}, 新创建 {stats['created']}, 更新 {stats['updated']}, 跳过 {stats['skipped']}, 错误 {stats['errors']}")
            
            # 检查是否有错误
            if stats["errors"] > 0:
                logger.warning(f"同步过程中有 {stats['errors']} 条记录出错")
            
            # 检查是否有记录
            if stats["total"] == 0:
                logger.warning("没有从钉钉多维表获取到任何记录")
                if stats["errors"] > 0:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"初始化dingtalk_sales_leads目录中的数据时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def copy_files_to_hktlora_sales_leads(self) -> bool:
        """
        将最新的文件复制到hktlora_sales_leads目录
        
        返回:
            bool: 操作是否成功
        """
        try:
            # 找到最新的目录
            latest_dir = self._find_latest_directory(self.elementor_db_dir, r"\d{8}_\d{6}")
            retry_dir = self._find_latest_directory(self.elementor_db_dir, r"retry_\d{8}_\d{6}")
            
            if latest_dir:
                logger.info(f"找到最新的目录: {latest_dir}")
            if retry_dir:
                logger.info(f"找到最新的目录: {retry_dir}")
            
            if not latest_dir and not retry_dir:
                logger.warning("没有找到可用的源目录")
                return True  # 返回True因为这是正常的状态
            
            # 统计复制的文件数量
            copied_count = 0
            skipped_count = 0
            
            # 从目录A复制文件
            if latest_dir:
                logger.info(f"从目录A复制文件: {latest_dir}")
                for file in os.listdir(latest_dir):
                    if file.startswith(('Elementor_DB_', 'submission_')) and file.endswith('.json'):
                        src_file = os.path.join(latest_dir, file)
                        dst_file = os.path.join(self.hktlora_sales_leads_dir, file)
                        if os.path.exists(dst_file) and os.path.getmtime(src_file) <= os.path.getmtime(dst_file):
                            skipped_count += 1
                            continue
                        shutil.copy2(src_file, dst_file)
                        copied_count += 1
            
            # 从目录B复制文件
            if retry_dir:
                logger.info(f"从目录B复制文件: {retry_dir}")
                for file in os.listdir(retry_dir):
                    if file.startswith(('Elementor_DB_', 'submission_')) and file.endswith('.json'):
                        src_file = os.path.join(retry_dir, file)
                        dst_file = os.path.join(self.hktlora_sales_leads_dir, file)
                        if os.path.exists(dst_file) and os.path.getmtime(src_file) <= os.path.getmtime(dst_file):
                            skipped_count += 1
                            continue
                        shutil.copy2(src_file, dst_file)
                        copied_count += 1
            
            logger.info(f"文件处理完成: {copied_count} 个文件已复制, {skipped_count} 个文件已跳过")
            
            # 创建一个包含统计信息的对象
            class CopyResult:
                def __init__(self, success: bool, copied: int, skipped: int):
                    self.success = success
                    self.copied_count = copied
                    self.skipped_count = skipped
                
                def __bool__(self):
                    return self.success
            
            return CopyResult(True, copied_count, skipped_count)
            
        except Exception as e:
            logger.error(f"复制文件时出错: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def _parse_elementor_db_file(self, elementor_file_path: str) -> List[Dict[str, Any]]:
        """
        解析Elementor_DB_*.json文件
        
        参数:
            elementor_file_path (str): Elementor DB文件路径
            
        返回:
            List[Dict]: 解析后的记录列表
        """
        try:
            with open(elementor_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            records = []
            for item in data:
                # 提取View信息
                view_info = item.get("View", {})
                href = view_info.get("href", "")
                
                # 解析post_id
                post_id = None
                if href:
                    post_id_match = re.search(r'post=(\d+)', href)
                    if post_id_match:
                        post_id = post_id_match.group(1)
                
                # 提取Read/Unread和Submitted On信息
                read_unread = item.get("Read/Unread", "")
                submitted_on = item.get("Submitted On", "")
                
                if post_id:
                    records.append({
                        "post_id": post_id,
                        "read_unread": read_unread,
                        "submitted_on": submitted_on,
                        "href": href
                    })
            
            logger.info(f"从文件 {os.path.basename(elementor_file_path)} 中解析出 {len(records)} 条记录")
            return records
            
        except Exception as e:
            logger.error(f"解析Elementor DB文件时出错: {str(e)}")
            return []
    
    def _parse_submission_file(self, post_id: str) -> Dict[str, Any]:
        """
        解析submission_*.json文件
        
        参数:
            post_id (str): 帖子ID
            
        返回:
            Dict: 解析后的记录，如果文件不存在或解析失败则返回空字典
        """
        try:
            submission_file = os.path.join(self.hktlora_sales_leads_dir, f"submission_{post_id}.json")
            
            if not os.path.exists(submission_file):
                logger.warning(f"提交文件不存在: {submission_file}")
                return {}
            
            with open(submission_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            submission = {}
            
            # 提取表单提交信息
            form_submission = data.get("form_submission", {})
            
            if form_submission.get("Name"):
                submission["customer_name"] = form_submission.get("Name", "")
            else:
                submission["customer_name"] = form_submission.get("First Name", "") + " " + form_submission.get("Last Name", "")

            if form_submission.get("Email Address"):
                submission["email"] = form_submission.get("Email Address", "")
            else:
                submission["email"] = form_submission.get("Email", "")

            if form_submission.get("WhatsApp"):
                submission["phone"] = form_submission.get("WhatsApp", "")
            else:
                submission["phone"] = form_submission.get("WhatsApp/Phone NO.", "")
            
            submission["country"] = form_submission.get("Country", "")
            submission["postcode"] = form_submission.get("Postcode", "")
            submission["message"] = form_submission.get("Message", "")
            submission["date_of_submission"] = form_submission.get("Date of Submission", "")
            
            # 提取额外信息
            extra_information = data.get("extra_information", {})
            submitted_on = extra_information.get("Submitted On", {})
            links = submitted_on.get("links", [])
            
            if links and isinstance(links, list) and len(links) > 0:
                submission["view_page_href"] = links[0].get("href", "")
            
            # 检查是否已同步过：如果存在dingding字段，需要进一步核实
            dingding_info = data.get('dingding', {})
            if dingding_info and dingding_info.get('id'):
                submission['dingtalk_id'] = dingding_info.get('id')
                # logger.info(f"检测到记录(编号: {post_id})存在钉钉ID: {dingtalk_id}，正在核实钉钉多维表中是否真实存在...")
                
                # 调用notable.check_record_exists来核实记录是否真的存在
                # try:
                #     # 获取表格ID和视图ID
                #     table_id = self.notable._ensure_table_id()
                #     sheet_id = self.notable._find_sheet_id(self.target_table_name)
                    
                #     # 检查记录是否存在
                #     record_exists = self.notable.check_record_exists(table_id, sheet_id, dingtalk_id)
                    
                #     if record_exists:
                #         submission['dingtalk_id'] = dingtalk_id
                #         logger.info(f"记录(编号: {post_id})在钉钉多维表中确实存在，将跳过同步")
                #     else:
                #         logger.warning(f"记录(编号: {post_id})的钉钉ID {dingtalk_id} 在多维表中不存在，将重新同步")
                # except Exception as e:
                #     logger.error(f"核实记录存在性时出错 (post_id={post_id}): {str(e)}")
                #     logger.warning(f"由于无法核实，记录(编号: {post_id})将被重新同步")

            logger.debug(f"成功解析提交文件: submission_{post_id}.json")
            return submission
            
        except Exception as e:
            logger.error(f"解析提交文件时出错 (post_id={post_id}): {str(e)}")
            return {}
    
    def prepare_notable_definition(self) -> bool:
        """
        准备Notable定义文件，如果不存在则获取表格视图
        
        返回:
            bool: 操作是否成功
        """
        try:
            notable_dir = os.path.join(os.path.dirname(os.path.abspath(
                os.path.dirname(self.notable.__class__.__module__))), 
                "DingTalk", "notable")
            
            definition_file = os.path.join(notable_dir, "notable_definition.json")
            
            # 检查定义文件是否存在
            if not os.path.exists(definition_file):
                logger.info("Notable定义文件不存在，正在获取表格视图...")
                result = self.notable.get_table_views(save_to_file=True)
                
                if not result:
                    logger.error("获取表格视图失败")
                    return False
                
                logger.info("成功获取表格视图并保存到定义文件")
            else:
                logger.info(f"Notable定义文件已存在: {definition_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"准备Notable定义文件时出错: {str(e)}")
            return False
    
    def sync_to_dingtalk(self) -> bool:
        """
        将数据逐条同步到钉钉多维表，并记录每一条的成功与失败。
        本方法实现了V2设计方案，采用逐条处理以增强容错性。
        
        返回:
            bool: 整个流程执行完毕则返回True，即使部分记录失败。发生致命错误则返回False。
        """
        try:
            # 1. 获取并解析源数据文件
            json_files = [f for f in os.listdir(self.hktlora_sales_leads_dir) if f.endswith('.json')]
            if not json_files:
                logger.info("【同步状态】hktlora_sales_leads目录中没有找到JSON文件，本次无需同步。")
                return True # 认为这是一个成功的状态，因为没有工作要做

            elementor_files = [f for f in json_files if f.startswith('Elementor_DB_')]
            if not elementor_files:
                logger.info("【同步状态】没有找到Elementor_DB_*.json文件，本次无需同步。")
                return True

            # 确保dingtalk_success.json和dingtalk_failure.json文件存在
            success_file = os.path.join(self.hktlora_sales_leads_dir, "dingtalk_success.json")
            failure_file = os.path.join(self.hktlora_sales_leads_dir, "dingtalk_failure.json")
            
            # 如果文件不存在，创建空的JSON数组文件
            if not os.path.exists(success_file):
                with open(success_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=4)
            if not os.path.exists(failure_file):
                with open(failure_file, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False, indent=4)

            # 读取现有的成功和失败记录
            try:
                with open(success_file, 'r', encoding='utf-8') as f:
                    success_records = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"dingtalk_success.json 格式错误，将重置为空数组")
                success_records = []
            
            try:
                with open(failure_file, 'r', encoding='utf-8') as f:
                    failure_records = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"dingtalk_failure.json 格式错误，将重置为空数组")
                failure_records = []

            # 创建一个编号到ID的映射字典，用于快速查找
            post_id_to_dingtalk_id = {}
            for record in success_records:
                if "fields" in record and "编号" in record["fields"]:
                    post_id = record["fields"]["编号"]
                    post_id_to_dingtalk_id[post_id] = record["id"]

            all_records = []
            for json_file in elementor_files:
                elementor_records = self._parse_elementor_db_file(os.path.join(self.hktlora_sales_leads_dir, json_file))
                for record in elementor_records:
                    post_id = record.get('post_id')
                    if post_id:
                        submission = self._parse_submission_file(post_id)
                        # 如果 submission 文件有效
                        if submission:
                            # 如果记录已同步过，则记录日志并跳过
                            # if submission.get('dingtalk_id'):
                            #     logger.info(f"记录(编号: {post_id})已同步过 (DingTalk ID: {submission.get('dingtalk_id')})，本次将跳过。")
                            #     continue
                            
                            # 合并记录并添加到待处理列表
                            record.update(submission)
                            all_records.append(record)
            
            if not all_records:
                logger.info("【同步状态】解析文件后发现所有记录都已同步，本次无需同步。")
                return True

            # 2. 转换为钉钉格式
            records_to_process = self._convert_to_notable_format(all_records)
            
            # 3. 逐条处理并记录结果
            success_count = 0
            failure_count = 0
            logger.info(f"【同步状态】开始同步 {len(records_to_process)} 条新记录到钉钉 '{self.target_table_name}' 多维表...")

            for record in records_to_process:
                fields_id_to_submit = record.get("id", "")
                fields_to_submit = record.get("fields", {})
                if not fields_to_submit:
                    logger.warning(f"发现一条空记录，已跳过: {record}")
                    continue

                # 从映射字典中查找对应的钉钉记录ID
                if fields_id_to_submit:
                    logger.info(f"在dingtalk_success.json中找到对应的钉钉记录ID: {fields_id_to_submit}")
                else:
                    post_id = fields_to_submit.get("编号")  
                    fields_id_to_submit = post_id_to_dingtalk_id.get(post_id, "")
                    logger.info(f"在dingtalk_success.json中没有找到对应的钉钉记录ID: {fields_id_to_submit}")

                record_id, error = self.notable.add_record(self.target_table_name, fields=fields_to_submit, fields_id=fields_id_to_submit)

                if record_id:
                    # 同步成功
                    success_count += 1
                    updated_record = {"id": record_id, "fields": fields_to_submit}
                    logger.info(f"记录(编号: {fields_to_submit.get('编号')})同步成功, ID: {record_id}")
                    
                    # 检查dingtalk_success.json文件大小
                    if os.path.getsize(success_file) > 5 * 1024 * 1024:
                        # 如果文件大于5MB，重命名并创建新文件
                        new_name = os.path.join(
                            self.hktlora_sales_leads_dir, 
                            f"dingtalk_success_{time.strftime('%Y%m%d_%H%M%S')}.json"
                        )
                        os.rename(success_file, new_name)
                        success_records = []

                    # 添加新记录到数组
                    success_records.append(updated_record)
                    
                    # 将更新后的数组写入文件
                    with open(success_file, "w", encoding="utf-8") as f:
                        json.dump(success_records, f, ensure_ascii=False, indent=4)

                    # 回写ID到submission文件
                    post_id = fields_to_submit.get('编号')
                    if post_id:
                        self._update_submission_file_with_dingtalk_id(post_id, record_id)
                        # 将同步成功的submission文件移动到dingtalk_sales_leads目录中
                        try:
                            shutil.move(
                                    os.path.join(self.hktlora_sales_leads_dir, f"submission_{post_id}.json"), 
                                    os.path.join(self.dingtalk_sales_leads_dir, f"submission_{post_id}.json")
                                )
                        except Exception as e:
                            logger.error(f"移动submission文件时出错: {str(e)}")
                else:
                    # 同步失败
                    failure_count += 1
                    updated_record = {"error": str(error), "fields": fields_to_submit}
                    logger.error(f"记录(编号: {fields_to_submit.get('编号')})同步失败: {error}")
                    
                    # 检查dingtalk_failure.json文件大小
                    if os.path.getsize(failure_file) > 5 * 1024 * 1024:
                        # 如果文件大于5MB，重命名并创建新文件
                        new_name = os.path.join(
                            self.hktlora_sales_leads_dir, 
                            f"dingtalk_failure_{time.strftime('%Y%m%d_%H%M%S')}.json"
                        )
                        os.rename(failure_file, new_name)
                        failure_records = []

                    # 添加新记录到数组
                    failure_records.append(updated_record)
                    
                    # 将更新后的数组写入文件
                    with open(failure_file, "w", encoding="utf-8") as f:
                        json.dump(failure_records, f, ensure_ascii=False, indent=4)
                
                countdown(10, 10, "等待下一次同步",new_line=False)

            logger.info(f"同步处理完成: {success_count} 条成功, {failure_count} 条失败。")
            
            return True
            
        except Exception as e:
            logger.error(f"同步到钉钉多维表的过程中发生致命错误: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
    def _update_submission_file_with_dingtalk_id(self, post_id: str, dingtalk_id: str):
        """
        将钉钉记录ID更新到对应的submission JSON文件中。

        参数:
            post_id (str): 帖子ID (即 "编号")。
            dingtalk_id (str): 钉钉多维表返回的记录ID。
        """
        submission_file_path = os.path.join(self.hktlora_sales_leads_dir, f"submission_{post_id}.json")
        
        try:
            if not os.path.exists(submission_file_path):
                logger.warning(f"尝试更新ID时未找到submission文件: {submission_file_path}")
                return

            # 读取现有文件内容
            with open(submission_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 更新或添加dingding字段
            data['dingding'] = {
                "id": dingtalk_id,
                "编号": post_id
            }

            # 写回更新后的内容
            with open(submission_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"成功将钉钉ID {dingtalk_id} 更新到文件: {os.path.basename(submission_file_path)}")

        except Exception as e:
            logger.error(f"更新submission文件 {os.path.basename(submission_file_path)} 失败: {e}")

    def _convert_to_notable_format(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将记录转换为Notable格式
        
        参数:
            records (List[Dict]): 原始记录列表
            
        返回:
            List[Dict]: Notable格式的记录列表
        """
        notable_records = []
        for record in records:
            # 构建fields对象
            fields = {
                "编号": record.get("post_id", ""),
                "客户": record.get("customer_name", ""),
                "留言日期": record.get("date_of_submission", ""),
                "电子邮件": record.get("email", ""),
                "通讯号码": record.get("phone", ""),
                "国家": record.get("country", ""),
                "邮编": record.get("postcode", ""),
                "留言内容": record.get("message", "")[:9999],# 留言内容截取前9999个字符, 因为钉钉多维表的Text字段长度限制为10000个字符                "留言日期": record.get("date_of_submission", ""),
                "是否查阅": record.get("read_unread", ""),
                "留言位置": record.get("view_page_href", "")
            }

            # 尝试从dingtalk_sales_leads目录获取dingtalk_id
            dingtalk_id = ""
            post_id = record.get("post_id", "")
            if post_id:
                dingtalk_submission_file = os.path.join(self.dingtalk_sales_leads_dir, f"submission_{post_id}.json")
                try:
                    if os.path.exists(dingtalk_submission_file):
                        with open(dingtalk_submission_file, 'r', encoding='utf-8') as f:
                            dingtalk_submission_data = json.load(f)
                            dingtalk_id = dingtalk_submission_data.get('dingding', {}).get('id', "")
                    
                except Exception as e:
                    logger.warning(f"读取submission文件失败 (post_id: {post_id}): {str(e)}")
                    # 继续处理，使用空的dingtalk_id
            
            # 调用ConversationFlow生成回复
            logger.info(f"开始调用ConversationFlow生成回复: {fields}")
            
            context = {
                "客户": record.get("customer_name", ""),
                "电子邮件": record.get("email", ""),
                "国家": record.get("country", ""),
                "留言内容": record.get("message", "")[:9999]# 留言内容截取前9999个字符, 因为钉钉多维表的Text字段长度限制为10000个字符                "留言日期": record.get("date_of_submission", ""),
            }
            
            response = self.llm_chat_flow.run(initial_context=context)           
            if response:
                fields['AI赋能'] = {"markdown": response[-1]['response']}        
            logger.info(f"ConversationFlow生成回复: {fields['AI赋能']}")
            
            # 添加到记录列表
            notable_records.append({
                "id": dingtalk_id,
                "fields": fields
            })
        
        return notable_records
    
    def process(self) -> bool:
        """
        执行完整的处理流程
        
        返回:
            bool: 操作是否成功
        """
        try:
            logger.info("开始执行LeadsInsight处理流程")
            
            # 步骤1: 整理网页内容
            copy_result = self.copy_files_to_hktlora_sales_leads()
            if not copy_result:
                logger.error("步骤1失败: 无法整理网页内容")
                return False
                
            # 检查是否有文件被复制
            if hasattr(copy_result, 'copied_count') and copy_result.copied_count == 0:
                logger.info("【执行状态】本次运行没有新的销售线索需要同步")
                return True
            
            # 步骤2: 将网页内容同步到钉钉多维表
            if not self.sync_to_dingtalk():
                logger.error("步骤2失败: 无法同步到钉钉多维表")
                return False
            
            # 步骤3: 删除hktlora_sales_leads目录中的submission_*.json文件和Elementor_DB_*.json文件
            if not self.delete_files_in_hktlora_sales_leads():
                logger.error("步骤3失败: 无法删除hktlora_sales_leads目录中的文件")
                return False
                
            logger.info("【执行状态】销售线索同步流程执行完成")
            return True
            
        except Exception as e:
            logger.error(f"LeadsInsight处理流程出错: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
            
    def process_with_initialization(self, initialize_first=False) -> bool:
        """
        执行完整的处理流程，包括可选的初始化步骤
        
        参数:
            initialize_first (bool): 是否先初始化dingtalk_sales_leads目录中的数据
            
        返回:
            bool: 操作是否成功
        """
        try:
            logger.info("开始执行LeadsInsight处理流程(包含初始化)")
            
            # 可选步骤: 初始化dingtalk_sales_leads目录中的数据
            if initialize_first:
                logger.info("执行初始化步骤: 从钉钉多维表同步数据到本地")
                if not self.initialize_dingtalk_sales_leads():
                    logger.error("初始化步骤失败: 无法从钉钉多维表同步数据到本地")
                    # 这里不直接返回False，因为初始化步骤是可选的
                    logger.warning("尽管初始化失败，但将继续执行后续步骤")
            
            # 执行标准处理流程
            return self.process()
            
        except Exception as e:
            logger.error(f"LeadsInsight处理流程(包含初始化)出错: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False



# 测试代码
if __name__ == "__main__":
    try:
        import argparse
        
        # 创建命令行参数解析器
        parser = argparse.ArgumentParser(description='执行LeadsInsight处理流程')
        parser.add_argument(
            '--init',
            action='store_true',
            help='是否先从钉钉多维表初始化本地数据'
        )
        parser.add_argument(
            '--config', 
            type=str, 
            default=None,
            help='Notable配置文件路径，默认使用LeadsInsight的默认配置'
        )
        parser.add_argument(
            '--table', 
            type=str, 
            default="资源池",
            help='钉钉多维表中的表格名称'
        )
        parser.add_argument(
            '--dir', 
            type=str, 
            default="elementor_db_sync",
            help='elementor_db_sync目录路径'
        )
        
        # 解析命令行参数
        args = parser.parse_args()
        
        # 创建LeadsInsight实例
        leads_insight = LeadsInsight(
            elementor_db_dir=args.dir,
            notable_config_path=args.config,
            target_table_name=args.table
        )
        
        # 执行处理流程
        success = leads_insight.process_with_initialization(initialize_first=args.init)
        
        if success:
            print("LeadsInsight处理流程成功完成")
        else:
            print("LeadsInsight处理流程失败")
            
    except Exception as e:
        print(f"程序执行出错: {str(e)}")
        logger.error(f"程序执行出错: {str(e)}")
        logger.error(traceback.format_exc())