import os
import logging
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
from log_cleaner import LogCleaner

class LogChecker:
    """日志检查器，用于监控日志系统的健康状态"""
    
    def __init__(self, log_dir: str = 'logs'):
        """
        初始化日志检查器
        
        参数:
            log_dir (str): 日志目录路径
        """
        self.log_dir = log_dir
        self.logger = logging.getLogger("LogChecker")
        self.cleaner = LogCleaner(log_dir)
        
    def check_directory_status(self) -> Dict[str, bool]:
        """
        检查日志目录状态
        
        返回:
            Dict[str, bool]: 目录状态检查结果
        """
        try:
            status = {
                "directory_exists": os.path.exists(self.log_dir),
                "is_directory": os.path.isdir(self.log_dir),
                "is_writable": os.access(self.log_dir, os.W_OK),
                "is_readable": os.access(self.log_dir, os.R_OK),
                "is_executable": os.access(self.log_dir, os.X_OK)
            }
            
            self.logger.info(f"日志目录状态检查结果: {json.dumps(status, ensure_ascii=False)}")
            return status
        except Exception as e:
            self.logger.error(f"检查日志目录状态时出错: {str(e)}")
            return {}
    
    def check_main_log_file(self) -> Dict[str, bool]:
        """
        检查主日志文件状态
        
        返回:
            Dict[str, bool]: 主日志文件状态检查结果
        """
        main_log = os.path.join(self.log_dir, 'leads_insight.log')
        try:
            status = {
                "file_exists": os.path.exists(main_log),
                "is_file": os.path.isfile(main_log),
                "is_writable": os.access(main_log, os.W_OK),
                "is_readable": os.access(main_log, os.R_OK),
                "is_empty": os.path.getsize(main_log) == 0 if os.path.exists(main_log) else True
            }
            
            self.logger.info(f"主日志文件状态检查结果: {json.dumps(status, ensure_ascii=False)}")
            return status
        except Exception as e:
            self.logger.error(f"检查主日志文件状态时出错: {str(e)}")
            return {}
    
    def check_log_rotation(self) -> Dict[str, any]:
        """
        检查日志轮转状态
        
        返回:
            Dict[str, any]: 日志轮转状态检查结果
        """
        try:
            backup_pattern = r'leads_insight\.log\.\d+'
            backup_files = [f for f in os.listdir(self.log_dir) if re.match(backup_pattern, f)]
            
            status = {
                "backup_count": len(backup_files),
                "latest_backup": max([os.path.getmtime(os.path.join(self.log_dir, f)) for f in backup_files]) if backup_files else None,
                "total_size_mb": self.cleaner.get_disk_usage()
            }
            
            self.logger.info(f"日志轮转状态检查结果: {json.dumps(status, ensure_ascii=False)}")
            return status
        except Exception as e:
            self.logger.error(f"检查日志轮转状态时出错: {str(e)}")
            return {}
    
    def check_recent_errors(self, hours: int = 24) -> Tuple[int, List[str]]:
        """
        检查最近的错误日志
        
        参数:
            hours (int): 检查最近多少小时的日志
            
        返回:
            Tuple[int, List[str]]: (错误数量, 错误消息列表)
        """
        try:
            main_log = os.path.join(self.log_dir, 'leads_insight.log')
            if not os.path.exists(main_log):
                return 0, []
            
            error_count = 0
            error_messages = []
            check_time = time.time() - (hours * 3600)
            
            with open(main_log, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        # 解析日志行
                        if ' - ERROR - ' in line:
                            # 解析时间戳
                            timestamp_str = line.split(' - ')[0]
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f').timestamp()
                            
                            if timestamp >= check_time:
                                error_count += 1
                                error_messages.append(line.strip())
                    except Exception:
                        continue
            
            self.logger.info(f"最近{hours}小时内发现{error_count}个错误")
            return error_count, error_messages
        except Exception as e:
            self.logger.error(f"检查最近错误日志时出错: {str(e)}")
            return 0, []
    
    def perform_health_check(self) -> Dict[str, any]:
        """
        执行完整的健康检查
        
        返回:
            Dict[str, any]: 健康检查结果
        """
        try:
            # 检查时间
            check_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 执行所有检查
            dir_status = self.check_directory_status()
            file_status = self.check_main_log_file()
            rotation_status = self.check_log_rotation()
            error_count, recent_errors = self.check_recent_errors(24)
            
            # 汇总结果
            health_status = {
                "check_time": check_time,
                "directory_status": dir_status,
                "main_log_status": file_status,
                "rotation_status": rotation_status,
                "error_status": {
                    "error_count_24h": error_count,
                    "recent_errors": recent_errors[-5:] if recent_errors else []  # 只保留最近5条错误
                }
            }
            
            # 计算总体健康状态
            is_healthy = (
                all(dir_status.values()) and
                all(file_status.values()) and
                rotation_status.get("backup_count", 0) <= 5 and
                error_count < 10  # 如果24小时内错误少于10个，认为是健康的
            )
            
            health_status["is_healthy"] = is_healthy
            
            # 记录健康检查结果
            self.logger.info(f"日志系统健康检查完成，系统状态: {'健康' if is_healthy else '异常'}")
            if not is_healthy:
                self.logger.warning("发现潜在问题，请检查详细报告")
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"执行健康检查时出错: {str(e)}")
            return {
                "check_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "is_healthy": False,
                "error": str(e)
            } 