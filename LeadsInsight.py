import os
import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple
import traceback
import sys
import time
import stat
from logging.handlers import RotatingFileHandler
from log_cleaner import LogCleaner
from log_checker import LogChecker

def setup_logging():
    """
    设置和初始化日志系统
    包含权限检查、文件系统检查、日志轮转配置和清理机制
    """
    log_dir = 'logs'
    log_file = os.path.join(log_dir, 'leads_insight.log')
    
    # 确保日志目录存在并有正确的权限
    try:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            # 设置目录权限为755 (rwxr-xr-x)
            os.chmod(log_dir, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    except Exception as e:
        print(f"创建日志目录失败: {str(e)}")
        sys.exit(1)

    # 检查日志文件权限
    try:
        # 如果日志文件不存在，创建它
        if not os.path.exists(log_file):
            with open(log_file, 'a') as f:
                pass
            # 设置文件权限为644 (rw-r--r--)
            os.chmod(log_file, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        
        # 测试文件是否可写
        try:
            with open(log_file, 'a') as f:
                f.write("")
        except IOError as e:
            print(f"日志文件不可写: {str(e)}")
            sys.exit(1)
    except Exception as e:
        print(f"设置日志文件失败: {str(e)}")
        sys.exit(1)

    # 配置日志记录
    try:
        # 创建日志格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # 创建RotatingFileHandler
        # 设置单个日志文件最大为10MB
        # 保留最近的5个日志文件
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)

        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # 获取根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # 移除所有现有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # 添加新的处理器
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # 获取LeadsInsight日志记录器
        logger = logging.getLogger("LeadsInsight")
        logger.info("日志系统初始化成功")
        logger.info(f"日志文件路径: {log_file}")
        logger.info("日志轮转配置: 单个文件最大10MB，保留最近5个文件")
        
        # 初始化并运行日志清理器
        try:
            cleaner = LogCleaner(log_dir=log_dir, retention_days=30)
            disk_usage = cleaner.get_disk_usage()
            if disk_usage is not None:
                logger.info(f"当前日志目录使用空间: {disk_usage:.2f}MB")
            
            if cleaner.clean_old_logs():
                logger.info("日志清理完成")
            else:
                logger.warning("日志清理过程中出现错误")
        except Exception as e:
            logger.error(f"运行日志清理器时出错: {str(e)}")

        # 执行日志系统健康检查
        try:
            checker = LogChecker(log_dir=log_dir)
            health_status = checker.perform_health_check()
            
            if health_status["is_healthy"]:
                logger.info("日志系统健康检查通过")
            else:
                logger.warning("日志系统健康检查发现问题")
                logger.warning(f"健康检查详细报告: {json.dumps(health_status, ensure_ascii=False, indent=2)}")
        except Exception as e:
            logger.error(f"执行日志系统健康检查时出错: {str(e)}")
        
        return logger
    except Exception as e:
        print(f"配置日志系统失败: {str(e)}")
        sys.exit(1)

# 初始化日志系统
logger = setup_logging()

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
    
    def countdown(self, seconds):
        """倒计时显示函数"""
        for i in range(seconds, 0, -1):
            sys.stdout.write(f'\r等待下一次评估，还剩 {i} 秒...   ')
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write('\r' + ' ' * 50 + '\r')  # 清除倒计时显示
        sys.stdout.flush()

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
            
            logger.warning(f"未找到符合模式 {pattern} 的目录")
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
            logger.error(f"删除{self.elementor_db_dir}目录中的 submission_*.json文件\Elementor_DB_*.json文件\retry_*目录下所有文件时出错: {str(e)}")
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
                
                self.countdown(10)

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
            '''
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
            '''
            fields = {
                "编号":record.get("post_id",""),
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
            
            dingtalk_submission_file = os.path.join(self.dingtalk_sales_leads_dir, f"submission_{record.get('post_id', '')}.json")
            with open(dingtalk_submission_file, 'r', encoding='utf-8') as f:
                dingtalk_submission_data = json.load(f)
            dingtalk_id = dingtalk_submission_data.get('dingding', {}).get('id', "")
            # dingtalk_id = record.get("dingtalk_id", "")
           
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
            # copy_result = self.copy_files_to_hktlora_sales_leads()
            # if not copy_result:
            #     logger.error("步骤1失败: 无法整理网页内容")
            #     return False
                
            # 检查是否有文件被复制
            # if hasattr(copy_result, 'copied_count') and copy_result.copied_count == 0:
            #     logger.info("【执行状态】本次运行没有新的销售线索需要同步")
            #     return True
            
            # 步骤2: 将网页内容同步到钉钉多维表
            if not self.sync_to_dingtalk():
                logger.error("步骤2失败: 无法同步到钉钉多维表")
                return False
            
            # 步骤3: 删除hktlora_sales_leads目录中的submission_*.json文件和Elementor_DB_*.json文件
            # if not self.delete_files_in_hktlora_sales_leads():
            #     logger.error("步骤3失败: 无法删除hktlora_sales_leads目录中的文件")
            #     return False
                
            # logger.info("【执行状态】销售线索同步流程执行完成")
            return True
            
        except Exception as e:
            logger.error(f"LeadsInsight处理流程出错: {str(e)}")
            logger.error(f"详细错误: {traceback.format_exc()}")
            return False


# 测试代码
if __name__ == "__main__":
    try:
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