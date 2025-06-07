import sys
import os
import json
import logging
from datetime import datetime

# 添加hkt_agent_framework目录到Python路径
sys.path.append(os.path.abspath("hkt_agent_framework"))

# 创建logs目录（如果不存在）
if not os.path.exists('logs'):
    os.makedirs('logs')

# 配置根日志记录器
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# 创建控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)

# 创建文件处理器
log_filename = f'logs/test_dingtalk_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
root_logger.addHandler(file_handler)

# 获取测试日志记录器
logger = logging.getLogger("TestDingTalkConfig")
logger.setLevel(logging.DEBUG)

# 导入DingTalk和Notable类
from hkt_agent_framework.DingTalk.DingTalk import DingTalk
from hkt_agent_framework.DingTalk.Notable import Notable

def test_dingtalk_config():
    """测试DingTalk类是否能够正确读取配置"""
    logger.info("开始测试DingTalk配置...")
    
    try:
        # 创建DingTalk实例
        dingtalk = DingTalk()
        
        # 检查关键配置是否正确读取
        logger.info(f"DingTalk配置信息:")
        logger.info(f"  app_key = {dingtalk.app_key}")
        logger.info(f"  operator_id = {dingtalk.operator_id}")
        logger.info(f"  notable_id = {dingtalk.notable_id}")
        logger.info(f"  get_notable_base_url = {dingtalk.get_notable_base_url}")
        logger.info(f"  get_notable_records_url = {dingtalk.get_notable_records_url}")
        logger.info(f"  set_notable_records_url = {dingtalk.set_notable_records_url}")
        logger.info(f"  get_notable_record_byid_url = {dingtalk.get_notable_record_byid_url}")
        logger.info(f"  get_department_listsub_url = {dingtalk.get_department_listsub_url}")
        logger.info(f"  get_user_list_by_department_url = {dingtalk.get_user_list_by_department_url}")
        
        # 检查配置是否有效
        if not dingtalk.notable_id:
            logger.warning("notable_id未配置")
        if not dingtalk.get_notable_base_url:
            logger.warning("get_notable_base_url未配置")
        if not dingtalk.get_notable_records_url:
            logger.warning("get_notable_records_url未配置")
        if not dingtalk.set_notable_records_url:
            logger.warning("set_notable_records_url未配置")
        if not dingtalk.get_notable_record_byid_url:
            logger.warning("get_notable_record_byid_url未配置")
        
        logger.info("DingTalk配置测试完成")
        return True
    except Exception as e:
        logger.error(f"DingTalk配置测试失败: {str(e)}")
        return False

def test_notable_config():
    """测试Notable类是否能够正确读取配置"""
    logger.info("开始测试Notable配置...")
    
    try:
        # 创建Notable实例
        notable = Notable()
        
        # 检查DingTalk实例是否创建成功
        if not hasattr(notable, 'dingtalk'):
            logger.error("Notable实例中没有dingtalk属性")
            return False
        
        # 检查关键配置是否正确读取
        logger.info(f"Notable配置信息:")
        logger.info(f"  dingtalk.notable_id = {notable.dingtalk.notable_id}")
        
        # 检查配置是否有效
        if not notable.dingtalk.notable_id:
            logger.warning("notable_id未配置")
        
        # 测试获取表格视图
        try:
            logger.info("尝试获取表格视图...")
            result = notable.get_table_views(save_to_file=True)
            if result:
                views = []
                if 'items' in result:
                    views = result.get('items', [])
                elif 'value' in result:
                    views = result.get('value', [])
                
                logger.info(f"成功获取表格视图，共 {len(views)} 个视图")
                for idx, view in enumerate(views[:3], 1):  # 只显示前3个
                    view_name = view.get('name', '未命名视图')
                    view_id = view.get('id', view.get('sheetId', '无ID'))
                    logger.info(f"  {idx}. {view_name} (ID: {view_id})")
            else:
                logger.warning("获取表格视图失败")
        except Exception as e:
            logger.error(f"获取表格视图时出错: {str(e)}")
        
        logger.info("Notable配置测试完成")
        return True
    except Exception as e:
        logger.error(f"Notable配置测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("=== 开始测试DingTalk和Notable配置 ===")
    
    # 测试DingTalk配置
    dingtalk_success = test_dingtalk_config()
    
    # 测试Notable配置
    notable_success = test_notable_config()
    
    # 输出测试结果
    logger.info("=== 测试结果 ===")
    logger.info(f"DingTalk配置测试: {'成功' if dingtalk_success else '失败'}")
    logger.info(f"Notable配置测试: {'成功' if notable_success else '失败'}")
    
    if dingtalk_success and notable_success:
        logger.info("配置测试全部通过，系统可以正常运行")
    else:
        logger.warning("配置测试未全部通过，系统可能无法正常运行") 