import os
import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple
import traceback

# 导入Notable类
from hkt_agent_framework.DingTalk.Notable import Notable

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/leads_insight.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("LeadsInsight")

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
        self.sales_leads_dir = os.path.join(elementor_db_dir, "sales_leads")
        self.target_table_name = target_table_name
        
        # 确保sales_leads目录存在
        if not os.path.exists(self.sales_leads_dir):
            os.makedirs(self.sales_leads_dir)
            logger.info(f"创建sales_leads目录: {self.sales_leads_dir}")
        
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
                        if pattern == r'^(\d{8}_\d{6})$':
                            dt_str = d
                        elif pattern == r'^retry_(\d{8}_\d{6})$':
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
            
            logger.warning(f"未找到符合模式 {pattern} 的目录")
            return None
        
        except Exception as e:
            logger.error(f"查找最新目录时出错: {str(e)}")
            return None
    
    def copy_files_to_sales_leads(self) -> bool:
        """
        将最新目录中的JSON文件复制到sales_leads目录
        
        返回:
            bool: 操作是否成功
        """
        try:
            # 查找最新的常规目录
            dir_a = self._find_latest_directory(self.elementor_db_dir, r'^(\d{8}_\d{6})$')
            
            # 查找最新的重试目录
            dir_b = self._find_latest_directory(self.elementor_db_dir, r'^retry_(\d{8}_\d{6})$')
            
            # 如果两个目录都未找到，则返回失败
            if not dir_a and not dir_b:
                logger.error("未找到任何有效的数据目录")
                return False
            
            # 跟踪复制文件的数量
            copied_count = 0
            
            # 从目录A复制文件
            if dir_a:
                logger.info(f"从目录A复制文件: {dir_a}")
                for filename in os.listdir(dir_a):
                    if filename.endswith('.json'):
                        src_file = os.path.join(dir_a, filename)
                        dst_file = os.path.join(self.sales_leads_dir, filename)
                        shutil.copy2(src_file, dst_file)
                        copied_count += 1
            
            # 从目录B复制文件
            if dir_b:
                logger.info(f"从目录B复制文件: {dir_b}")
                for filename in os.listdir(dir_b):
                    if filename.endswith('.json'):
                        src_file = os.path.join(dir_b, filename)
                        dst_file = os.path.join(self.sales_leads_dir, filename)
                        shutil.copy2(src_file, dst_file)
                        copied_count += 1
            
            logger.info(f"成功复制 {copied_count} 个文件到sales_leads目录")
            return True
            
        except Exception as e:
            logger.error(f"复制文件到sales_leads目录时出错: {str(e)}")
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
            submission_file = os.path.join(self.sales_leads_dir, f"submission_{post_id}.json")
            
            if not os.path.exists(submission_file):
                logger.warning(f"提交文件不存在: {submission_file}")
                return {}
            
            with open(submission_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            submission = {}
            
            # 提取表单提交信息
            form_submission = data.get("form_submission", {})
            submission["first_name"] = form_submission.get("First Name", "")
            submission["last_name"] = form_submission.get("Last Name", "")
            submission["email"] = form_submission.get("Email Address", "")
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
            json_files = [f for f in os.listdir(self.sales_leads_dir) if f.endswith('.json')]
            if not json_files:
                logger.warning("sales_leads目录中没有找到JSON文件可供同步。")
                return True # 认为这是一个成功的状态，因为没有工作要做

            all_records = []
            for json_file in json_files:
                if json_file.startswith('Elementor_DB_'):
                    elementor_records = self._parse_elementor_db_file(os.path.join(self.sales_leads_dir, json_file))
                    for record in elementor_records:
                        post_id = record.get('post_id')
                        if post_id:
                            submission = self._parse_submission_file(post_id)
                            if submission:
                                record.update(submission)
                                all_records.append(record)
            
            if not all_records:
                logger.warning("解析文件后，没有找到有效的记录可供同步。")
                return True

            # 2. 转换为钉钉格式
            records_to_process = self._convert_to_notable_format(all_records)
            
            # 3. 逐条处理并记录结果
            updated_records = []
            success_count = 0
            failure_count = 0
            logger.info(f"开始逐条同步 {len(records_to_process)} 条记录到钉钉 '{self.target_table_name}'...")

            for record in records_to_process:
                fields_to_submit = record.get("fields", {})
                if not fields_to_submit:
                    logger.warning(f"发现一条空记录，已跳过: {record}")
                    continue

                record_id, error = self.notable.add_record(self.target_table_name, fields_to_submit)

                if error is None and record_id:
                    # 同步成功
                    success_count += 1
                    updated_record = {"id": record_id, "fields": fields_to_submit}
                    logger.info(f"记录(编号: {fields_to_submit.get('编号')})同步成功, ID: {record_id}")
                else:
                    # 同步失败
                    failure_count += 1
                    updated_record = {"error": str(error), "fields": fields_to_submit}
                    logger.error(f"记录(编号: {fields_to_submit.get('编号')})同步失败: {error}")
                
                updated_records.append(updated_record)

            logger.info(f"同步处理完成: {success_count} 条成功, {failure_count} 条失败。")

            # 4. 将最终结果（包含id和error）写入文件
            output_file = f"{self.target_table_name}.json"
            current_dir = os.path.dirname(os.path.abspath(__file__))
            output_path = os.path.join(current_dir, "notable", output_file)
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            final_data = {
                "totalRecords": len(updated_records),
                "records": updated_records
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"成功将 {len(updated_records)} 条处理结果保存到文件: {output_path}")
            
            return True # 流程完成
            
        except Exception as e:
            logger.error(f"同步到钉钉多维表的过程中发生致命错误: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False
    
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
                "编号":record.get("post_id",""),
                "客户": record.get("first_name", "") + " " + record.get("last_name", ""),
                "电子邮件": record.get("email", ""),
                "通讯号码": record.get("phone", ""),
                "国家": record.get("country", ""),
                "邮编": record.get("postcode", ""),
                "留言内容": record.get("message", ""),
                "留言日期": record.get("date_of_submission", ""),
                "是否查阅": record.get("read_unread", ""),
                "留言位置": record.get("href", "")
            }
           
            # 添加到记录列表
            notable_records.append({
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
            if not self.copy_files_to_sales_leads():
                logger.error("步骤1失败: 无法整理网页内容")
                return False
            
            # 步骤2: 将网页内容同步到钉钉多维表
            if not self.sync_to_dingtalk():
                logger.error("步骤2失败: 无法同步到钉钉多维表")
                return False
            
            logger.info("LeadsInsight处理流程成功完成")
            return True
            
        except Exception as e:
            logger.error(f"LeadsInsight处理流程出错: {str(e)}")
            return False

# 测试代码
if __name__ == "__main__":
    try:
        # 确保日志目录存在
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        # 创建LeadsInsight实例
        leads_insight = LeadsInsight()
        
        # 执行处理流程
        success = leads_insight.process()
        
        if success:
            print("LeadsInsight处理流程成功完成")
        else:
            print("LeadsInsight处理流程失败")
            
    except Exception as e:
        print(f"程序执行出错: {str(e)}")