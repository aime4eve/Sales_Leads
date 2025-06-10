import os
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional
import re

class LogCleaner:
    """日志清理器，用于管理日志文件的生命周期"""
    
    def __init__(self, log_dir: str = 'logs', retention_days: int = 30):
        """
        初始化日志清理器
        
        参数:
            log_dir (str): 日志目录路径
            retention_days (int): 日志文件保留天数
        """
        self.log_dir = log_dir
        self.retention_days = retention_days
        self.logger = logging.getLogger("LogCleaner")
    
    def get_log_files(self) -> List[str]:
        """获取所有日志文件路径"""
        log_files = []
        try:
            for file in os.listdir(self.log_dir):
                if file.endswith('.log'):
                    log_files.append(os.path.join(self.log_dir, file))
            return log_files
        except Exception as e:
            self.logger.error(f"获取日志文件列表失败: {str(e)}")
            return []
    
    def get_file_age_days(self, file_path: str) -> Optional[float]:
        """
        获取文件的年龄（天数）
        
        参数:
            file_path (str): 文件路径
            
        返回:
            float: 文件年龄（天数），如果出错则返回None
        """
        try:
            # 获取文件的最后修改时间
            mtime = os.path.getmtime(file_path)
            # 计算文件年龄
            age_days = (time.time() - mtime) / (24 * 3600)
            return age_days
        except Exception as e:
            self.logger.error(f"获取文件 {file_path} 年龄失败: {str(e)}")
            return None
    
    def is_backup_file(self, file_path: str) -> bool:
        """
        判断是否为备份日志文件
        
        参数:
            file_path (str): 文件路径
            
        返回:
            bool: 是否为备份文件
        """
        return bool(re.search(r'\.log\.\d+$', file_path))
    
    def clean_old_logs(self) -> bool:
        """
        清理过期的日志文件
        
        返回:
            bool: 清理操作是否成功
        """
        try:
            self.logger.info(f"开始清理日志文件，保留天数: {self.retention_days}")
            cleaned_count = 0
            failed_count = 0
            
            # 获取所有日志文件
            log_files = self.get_log_files()
            
            for file_path in log_files:
                try:
                    # 获取文件年龄
                    age_days = self.get_file_age_days(file_path)
                    if age_days is None:
                        continue
                    
                    # 如果是主日志文件（非备份），跳过
                    if not self.is_backup_file(file_path) and os.path.basename(file_path) == 'leads_insight.log':
                        continue
                    
                    # 如果文件超过保留期限，删除它
                    if age_days > self.retention_days:
                        os.remove(file_path)
                        cleaned_count += 1
                        self.logger.info(f"已删除过期日志文件: {file_path} (年龄: {age_days:.1f}天)")
                except Exception as e:
                    self.logger.error(f"清理文件 {file_path} 失败: {str(e)}")
                    failed_count += 1
            
            self.logger.info(f"日志清理完成。已清理: {cleaned_count} 个文件，失败: {failed_count} 个文件")
            return failed_count == 0
            
        except Exception as e:
            self.logger.error(f"日志清理过程出错: {str(e)}")
            return False
    
    def get_disk_usage(self) -> Optional[float]:
        """
        获取日志目录的磁盘使用量（MB）
        
        返回:
            float: 磁盘使用量（MB），如果出错则返回None
        """
        try:
            total_size = 0
            for file_path in self.get_log_files():
                total_size += os.path.getsize(file_path)
            return total_size / (1024 * 1024)  # 转换为MB
        except Exception as e:
            self.logger.error(f"获取磁盘使用量失败: {str(e)}")
            return None 