import logging
import threading
import time
import queue
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from hktloraweb import HKTLoraWeb

# 配置日志文件
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = f'login_{current_time}.log'
logging.basicConfig(
    level=logging.INFO,  # 从ERROR改为INFO，输出更多调试信息
    format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s',  # 添加线程名称
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)

# 全局共享变量和锁
class SharedResources:
    def __init__(self):
        self.stop_flag = threading.Event()
        self.thread_a_completed = threading.Event()
        self.thread_b_completed = threading.Event()
        self.thread_c_completed = threading.Event()
        self.error_queue = queue.Queue()  # 存储错误信息
        self.sync_top_pages = 2  # 默认同步的页面数
        self.playwright = None
        self.browser = None
        self.current_time = current_time  # 使用与日志文件相同的时间戳

# 修改HKTLoraWeb类的extract_failed_urls方法，避免尝试重命名当前正在使用的日志文件
def patch_extract_failed_urls(hkt_web):
    original_extract_failed_urls = hkt_web.extract_failed_urls
    
    def patched_extract_failed_urls():
        failed_urls = []
        try:
            # 查找所有日志文件
            log_files = [f for f in os.listdir() if f.startswith('login_') and f.endswith('.log')]
            start_time = datetime.strptime(hkt_web.CURRENT_TIME, '%Y%m%d_%H%M%S')
            
            for log_file in log_files:
                try:
                    # 跳过当前正在使用的日志文件
                    if log_file == hkt_web.log_file:
                        logging.info(f"跳过当前正在使用的日志文件: {log_file}")
                        continue
                        
                    # 从文件名中提取时间
                    import re
                    file_time_str = re.search(r'login_(\d{8}_\d{6})\.log', log_file)
                    if not file_time_str:
                        continue
                        
                    file_time = datetime.strptime(file_time_str.group(1), '%Y%m%d_%H%M%S')
                    
                    # 跳过早于该当前时间的文件
                    if start_time and file_time > start_time:
                        continue
                    
                    # 读取并解析日志文件
                    with open(log_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 使用正则表达式匹配URL
                        matches = re.finditer(r'navigating to "(https://[^"]+)"', content)
                        for match in matches:
                            failed_urls.append(match.group(1))
                    
                    # 重命名日志文件
                    try:
                        bak_file = log_file.replace('.log', '.bak')
                        # 如果已存在同名的.bak文件，先删除它
                        if os.path.exists(bak_file):
                            os.remove(bak_file)
                        os.rename(log_file, bak_file)
                        logging.info(f"已将日志文件 {log_file} 重命名为 {bak_file}")
                    except Exception as e:
                        logging.error(f"重命名日志文件 {log_file} 时出错: {str(e)}")
                            
                except Exception as e:
                    logging.error(f"处理日志文件 {log_file} 时出错: {str(e)}")
                    continue
                    
        except Exception as e:
            logging.error(f"查找日志文件时出错: {str(e)}")
            
        return list(set(failed_urls))  # 返回去重后的URL列表
    
    # 替换原方法
    hkt_web.extract_failed_urls = patched_extract_failed_urls
    return hkt_web

# 主线程：协调三个步骤的执行
def main():
    try:
        # 创建HKTLoraWeb实例
        hkt_web = HKTLoraWeb()
        # 修补extract_failed_urls方法
        hkt_web = patch_extract_failed_urls(hkt_web)
        
        # 创建共享资源
        shared_resources = SharedResources()
        shared_resources.sync_top_pages = 2  # 设置同步页数
        
        logging.info("开始网页抓取")
        
        # 外层循环：如果发生异常，重新从步骤A开始
        while True:
            # 重置所有事件标志
            shared_resources.stop_flag.clear()
            shared_resources.thread_a_completed.clear()
            shared_resources.thread_b_completed.clear()
            shared_resources.thread_c_completed.clear()
            
            # 初始化Playwright
            shared_resources.playwright = sync_playwright().start()
            
            try:
                # 步骤A：创建浏览器实例并登录
                logging.info("步骤A开始：创建浏览器实例并登录")
                
                # 创建浏览器实例
                shared_resources.browser = shared_resources.playwright.chromium.launch(headless=False)
                context = shared_resources.browser.new_context(
                    http_credentials={"username": hkt_web.AUTH_USER, "password": hkt_web.AUTH_PASS}
                )
                page = context.new_page()
                logging.info("浏览器实例创建成功")
                
                # 执行登录
                login_success = hkt_web.login_main_site(page)
                
                if not login_success:
                    logging.error("登录失败，重新启动流程")
                    if shared_resources.browser:
                        shared_resources.browser.close()
                    if shared_resources.playwright:
                        shared_resources.playwright.stop()
                    time.sleep(5)  # 等待5秒后重试
                    continue
                
                shared_resources.thread_a_completed.set()
                logging.info("步骤A完成")
                
                # 内部循环：执行步骤B和步骤C的交替执行
                while not shared_resources.stop_flag.is_set():
                    # 步骤B：定时刷新页面并保存内容
                    logging.info("步骤B开始：定时刷新页面并保存内容")
                    try:
                        hkt_web.do_refresh_pages(page, shared_resources.sync_top_pages)
                        logging.info("页面刷新和内容保存完成")
                    except Exception as e:
                        logging.error(f"页面刷新过程中发生异常: {str(e)}")
                        shared_resources.error_queue.put(str(e))
                        shared_resources.stop_flag.set()
                        break
                    
                    shared_resources.thread_b_completed.set()
                    
                    # 步骤C：处理错误日志
                    logging.info("步骤C开始：处理错误日志")
                    try:
                        # 提取失败的URL
                        failed_urls = hkt_web.extract_failed_urls()
                        
                        if failed_urls:
                            logging.info(f"找到 {len(failed_urls)} 个失败的URL，开始重试")
                            hkt_web.retry_failed_submissions(page, failed_urls)
                        else:
                            logging.info("没有发现失败的URL")
                    except Exception as e:
                        logging.error(f"处理错误日志过程中发生异常: {str(e)}")
                        shared_resources.error_queue.put(str(e))
                        shared_resources.stop_flag.set()
                        break
                    
                    shared_resources.thread_c_completed.set()
                    
                    # 检查是否完成所有任务
                    if shared_resources.thread_a_completed.is_set() and \
                       shared_resources.thread_b_completed.is_set() and \
                       shared_resources.thread_c_completed.is_set():
                        logging.info("所有步骤都已完成，任务结束")
                        shared_resources.stop_flag.set()
                
                # 如果没有设置stop_flag，说明任务正常完成
                if not shared_resources.stop_flag.is_set():
                    logging.info("任务正常完成，退出主循环")
                    break
                
                logging.warning("检测到停止标志，重新启动流程")
                
            except Exception as e:
                logging.error(f"执行过程中发生异常: {str(e)}")
                shared_resources.stop_flag.set()
            
            finally:
                # 清理资源
                if shared_resources.browser:
                    try:
                        shared_resources.browser.close()
                        shared_resources.browser = None
                    except Exception as e:
                        logging.error(f"关闭浏览器时发生异常: {str(e)}")
                
                if shared_resources.playwright:
                    try:
                        shared_resources.playwright.stop()
                        shared_resources.playwright = None
                    except Exception as e:
                        logging.error(f"停止Playwright时发生异常: {str(e)}")
                
                time.sleep(5)  # 等待5秒后重试
    
    except KeyboardInterrupt:
        logging.info("用户中断程序")
        if hasattr(shared_resources, 'stop_flag'):
            shared_resources.stop_flag.set()
    
    except Exception as e:
        logging.error(f"主程序发生异常: {str(e)}")
    
    finally:
        # 确保所有资源都被释放
        if hasattr(shared_resources, 'browser') and shared_resources.browser:
            try:
                shared_resources.browser.close()
            except:
                pass
        
        if hasattr(shared_resources, 'playwright') and shared_resources.playwright:
            try:
                shared_resources.playwright.stop()
            except:
                pass
        
        logging.info("程序执行完毕")

if __name__ == "__main__":
    main() 