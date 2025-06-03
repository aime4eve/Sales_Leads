import logging
from datetime import datetime
from hktloraweb import HKTLoraWeb

# 配置日志文件
log_file = f'login_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8')  # 添加UTF-8编码设置
    ]
)

def main():
    try:
        # 创建HKTLoraWeb实例并运行
        web = HKTLoraWeb()
        web.run(sync_top_pages=2)
    except Exception as e:
        print(f"发生错误: {str(e)}")
        raise

if __name__ == "__main__":
    main() 