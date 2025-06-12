import os
import sys
import logging
import argparse
from datetime import datetime

# 导入LeadsInsight类
from LeadsInsight import LeadsInsight

# 配置日志记录
def setup_logging():
    """设置日志配置"""
    # 确保日志目录存在
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 当前时间作为日志文件名的一部分
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f'test_leads_insight_{current_time}.log')
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    
    # 移除所有现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建并配置文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 创建并配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    return log_file

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='测试LeadsInsight类的功能')
    parser.add_argument('--step', type=int, choices=[1, 2, 3], default=3,
                      help='执行的步骤: 1=整理网页内容, 2=同步到钉钉, 3=完整流程(默认)')
    parser.add_argument('--config', type=str, default=None,
                      help='Notable配置文件路径')
    parser.add_argument('--table', type=str, default="资源池",
                      help='目标表格名称(默认: 资源池)')
    parser.add_argument('--db-dir', type=str, default="elementor_db_sync",
                      help='Elementor数据库同步目录(默认: elementor_db_sync)')
    parser.add_argument('--verbose', action='store_true',
                      help='启用详细日志输出')
    
    return parser.parse_args()

def main():
    """主函数"""
    # 设置日志
    log_file = setup_logging()
    
    # 解析命令行参数
    args = parse_arguments()

    # args.step = 2
    
    # 如果启用详细日志，设置日志级别为DEBUG
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("LeadsInsight").setLevel(logging.DEBUG)
        logging.getLogger("Notable").setLevel(logging.DEBUG)
        logging.getLogger("DingTalk").setLevel(logging.DEBUG)
    
    logging.info(f"日志文件: {log_file}")
    logging.info(f"命令行参数: {args}")
    
    try:
        # 创建LeadsInsight实例
        leads_insight = LeadsInsight(
            elementor_db_dir=args.db_dir,
            notable_config_path=args.config,
            target_table_name=args.table
        )
        
        # 根据步骤执行相应的操作
        if args.step == 1:
            logging.info("执行步骤1: 整理网页内容")
            success = leads_insight.copy_files_to_hktlora_sales_leads()
            if success:
                logging.info("步骤1完成: 成功整理网页内容")
            else:
                logging.error("步骤1失败: 无法整理网页内容")
                return 1
        elif args.step == 2:
            logging.info("执行步骤2: 同步到钉钉多维表")
            success = leads_insight.sync_to_dingtalk()
            if success:
                logging.info("步骤2完成: 成功同步到钉钉多维表")
            else:
                logging.error("步骤2失败: 无法同步到钉钉多维表")
                return 1
        else:  # 完整流程
            logging.info("执行完整流程")
            success = leads_insight.process()
            if success:
                logging.info("完整流程成功完成")
            else:
                logging.error("完整流程执行失败")
                return 1
        
        return 0
    
    except Exception as e:
        logging.error(f"程序执行出错: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 