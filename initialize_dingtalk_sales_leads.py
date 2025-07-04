#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初始化dingtalk_sales_leads目录中的数据
从钉钉多维表同步数据到本地
"""

import os
import sys
import logging
import argparse
from LeadsInsight import LeadsInsight

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('initialize_dingtalk_sales_leads')

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='初始化dingtalk_sales_leads目录中的数据')
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
    
    try:
        logger.info("开始初始化dingtalk_sales_leads目录中的数据")
        
        # 创建LeadsInsight实例
        leads_insight = LeadsInsight(
            elementor_db_dir=args.dir,
            notable_config_path=args.config,
            target_table_name=args.table
        )
        
        # 执行初始化
        success = leads_insight.initialize_dingtalk_sales_leads()
        
        if success:
            logger.info("初始化成功")
            # 检查文件数量
            dingtalk_sales_leads_dir = os.path.join(args.dir, "dingtalk_sales_leads")
            file_count = len([f for f in os.listdir(dingtalk_sales_leads_dir) if f.startswith('submission_') and f.endswith('.json')])
            logger.info(f"dingtalk_sales_leads目录中共有 {file_count} 个submission_*.json文件")
            print(f"初始化成功，共同步了 {file_count} 条记录")
            return 0
        else:
            logger.error("初始化失败")
            print("初始化失败，请查看日志了解详细信息")
            return 1
    
    except Exception as e:
        logger.error(f"初始化过程中出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        print(f"初始化过程中出错: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 