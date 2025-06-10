import logging
import signal
import sys
import time
import json
import os
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    logging.info("成功导入 playwright")
except ImportError as e:
    logging.error(f"导入 playwright 失败: {str(e)}")
    raise

try:
    from HKTLoraWeb import HKTLoraWeb
    logging.info("成功导入 HKTLoraWeb")
except ImportError as e:
    logging.error(f"导入 HKTLoraWeb 失败: {str(e)}")
    raise

try:
    from LeadsInsight import LeadsInsight
    logging.info("成功导入 LeadsInsight")
except ImportError as e:
    logging.error(f"导入 LeadsInsight 失败: {str(e)}")
    raise


class SimpleConfig:
    """简化的配置管理器"""
    
    def __init__(self, config_file='task_config.json'):
        self.config_file = config_file
        self.config = self._load_config()
        
    def _load_config(self):
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            return self._get_default_config()
            
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载配置文件失败: {str(e)}")
            return self._get_default_config()
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            "task_params": {
                "sync_top_pages": 1,
                "task_interval_seconds": 180,  
                "refresh_wait_seconds": 5,    
                "extract_wait_seconds": 15,    
                "leads_wait_seconds": 20       
            },
            "logging": {
                "level": "ERROR",
                "log_dir": "logs"
            }
        }
    
    def get(self, key, default=None):
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value


class SyncHKTLora:
    """简化的HKTLora同步程序"""
    
    def __init__(self):
        self.running = True
        self.config = SimpleConfig()
        self.hkt_web = None
        self.playwright = None
        self.browser = None
        self.page = None
        self.leads_insight = None
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logging.info("SyncHKTLora 初始化完成")
    
    def _signal_handler(self, signum, frame):
        """处理Ctrl+C信号"""
        logging.info("收到退出信号，正在清理资源...")
        self.running = False
        self._cleanup()
        logging.info("程序已退出")
        sys.exit(0)
    
    def _cleanup(self):
        """清理资源"""
        try:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logging.info("资源清理完成")
        except Exception as e:
            logging.error(f"清理资源时出错: {str(e)}")
    
    def _initialize_browser(self):
        """初始化浏览器"""
        try:
            logging.info("正在初始化浏览器...")
            
            self.playwright = sync_playwright().start()
            
            browser_options = {
                "headless": False,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--window-size=1920,1080",
                    "--start-maximized"
                ]
            }
            
            self.browser = self.playwright.chromium.launch(**browser_options)
            
            # 创建上下文时包含HTTP认证信息
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "ignore_https_errors": True,
                "bypass_csp": True
            }
            
            # 如果HKTLoraWeb已初始化，添加认证信息
            if hasattr(self, 'hkt_web') and self.hkt_web:
                context_options["http_credentials"] = {
                    "username": self.hkt_web.AUTH_USER,
                    "password": self.hkt_web.AUTH_PASS
                }
            
            context = self.browser.new_context(**context_options)
            self.page = context.new_page()
            
            logging.info("浏览器初始化成功")
            return True
            
        except Exception as e:
            logging.error(f"初始化浏览器失败: {str(e)}")
            return False
    
    def _initialize_components(self):
        """初始化组件"""
        try:
            logging.info("正在初始化组件...")
            
            # 初始化HKTLoraWeb
            self.hkt_web = HKTLoraWeb()
            if not self.hkt_web:
                raise Exception("HKTLoraWeb初始化失败")
            
            # 初始化LeadsInsight
            self.leads_insight = LeadsInsight()
            if not self.leads_insight:
                raise Exception("LeadsInsight初始化失败")
            
            logging.info("组件初始化成功")
            return True
            
        except Exception as e:
            logging.error(f"初始化组件失败: {str(e)}")
            return False
    
    def _login(self):
        """执行登录"""
        try:
            logging.info("开始执行登录...")
            
            # 导航到登录页面
            login_url = self.hkt_web.BASE_URL
            logging.info(f"正在访问登录页面: {login_url}")
            
            response = self.page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
            if not response or response.status >= 400:
                raise Exception(f"无法访问登录页面，状态码: {response.status if response else 'None'}")
            
            # 等待登录表单
            self.page.wait_for_selector("form#loginform", timeout=30000)
            
            # 执行登录
            result = self.hkt_web.login_main_site(self.page)
            if not result:
                raise Exception("登录操作失败")
            
            logging.info("登录成功")
            return True
            
        except Exception as e:
            logging.error(f"登录失败: {str(e)}")
            return False
    
    def _refresh_pages(self):
        """刷新页面"""
        try:
            logging.info("开始刷新页面...")
            
            sync_top_pages = self.config.get('task_params.sync_top_pages', 1)
            result = self.hkt_web.do_refresh_pages(self.page, sync_top_pages)
            
            if not result:
                raise Exception("页面刷新失败")
            
            logging.info("页面刷新完成")
            return True
            
        except Exception as e:
            logging.error(f"页面刷新失败: {str(e)}")
            return False
    
    def _extract_failed_urls(self):
        """提取失败的URL"""
        try:
            logging.info("开始提取失败的URL...")
            
            failed_urls = self.hkt_web.extract_failed_urls()
            if failed_urls:
                logging.info(f"发现 {len(failed_urls)} 个失败的URL")
                # 这里可以添加重试逻辑，但为了简化，我们只记录
            else:
                logging.info("没有发现失败的URL")
            
            logging.info("URL提取完成")
            return True
            
        except Exception as e:
            logging.error(f"提取失败的URL时出错: {str(e)}")
            return False
    
    def _process_leads(self):
        """处理销售线索"""
        try:
            logging.info("开始处理销售线索...")
            
            result = self.leads_insight.process()
            if not result:
                raise Exception("销售线索处理失败")
            
            logging.info("销售线索处理完成")
            return True
            
        except Exception as e:
            logging.error(f"处理销售线索失败: {str(e)}")
            return False
    def countdown(self,seconds):
        """倒计时显示函数"""
        for i in range(seconds, 0, -1):
            sys.stdout.write(f'\r还剩 {i} 秒...   ')
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write('\r' + ' ' * 50 + '\r')  # 清除倒计时显示
        sys.stdout.flush()
        
    def _task_loop(self):
        """内层任务循环"""
        logging.info("开始任务循环...")
        
        while self.running:
            try:
                # 任务1：刷新页面
                if not self._refresh_pages():
                    logging.error("刷新页面失败，退出程序")
                    return False
                
                # 等待
                refresh_wait = self.config.get('task_params.refresh_wait_seconds', 30)
                logging.info(f"刷新完成，等待 {refresh_wait} 秒...")
                self.countdown(refresh_wait)
                # time.sleep(refresh_wait)
                
                if not self.running:
                    break
                
                # 任务2：提取失败的URL
                if not self._extract_failed_urls():
                    logging.error("提取失败URL失败，退出程序")
                    return False
                
                # 等待
                extract_wait = self.config.get('task_params.extract_wait_seconds', 60)
                logging.info(f"URL提取完成，等待 {extract_wait} 秒...")
                self.countdown(extract_wait)
                # time.sleep(extract_wait)
                
                if not self.running:
                    break
                
                # 任务3：处理销售线索
                if not self._process_leads():
                    logging.error("处理销售线索失败，退出程序")
                    return False
                
                # 等待下一轮
                leads_wait = self.config.get('task_params.leads_wait_seconds', 90)
                logging.info(f"销售线索处理完成，等待 {leads_wait} 秒后开始下一轮...")
                self.countdown(leads_wait)
                # time.sleep(leads_wait)
                
            except Exception as e:
                logging.error(f"任务循环中出现错误: {str(e)}")
                return False
        
        return True
    
    def run(self):
        """主循环"""
        logging.info("开始主循环...")
        
        while self.running:
            try:
                # 先初始化组件
                if not self._initialize_components():
                    logging.error("组件初始化失败，退出程序")
                    break
                
                # 再初始化浏览器（需要使用组件中的认证信息）
                if not self._initialize_browser():
                    logging.error("浏览器初始化失败，退出程序")
                    break
                
                # 登录
                if not self._login():
                    logging.error("登录失败，退出程序")
                    break
                
                logging.info("登录成功，进入任务循环...")
                
                # 进入任务循环
                if not self._task_loop():
                    logging.error("任务循环失败，退出程序")
                    break
                
            except Exception as e:
                logging.error(f"主循环中出现错误: {str(e)}")
                break
            finally:
                # 清理当前会话的资源
                try:
                    if self.page:
                        self.page.close()
                        self.page = None
                    if self.browser:
                        self.browser.close()
                        self.browser = None
                    if self.playwright:
                        self.playwright.stop()
                        self.playwright = None
                except:
                    pass
        
        # 最终清理
        self._cleanup()
        logging.info("主循环结束")


def setup_logging(config):
    """设置日志"""
    log_dir = config.get('logging.log_dir', 'logs')
    log_level = config.get('logging.level', 'INFO')
    
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    
    # 设置日志文件
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f'sync_hktlora_{current_time}.log')
    
    # 配置日志
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.info(f"日志系统初始化完成，日志文件: {log_file}")
    return log_file


def main():
    """主函数"""
    try:
        print("SyncHKTLora 启动中...")
        print("按 Ctrl+C 可退出程序")
        
        # 创建配置管理器
        config = SimpleConfig()
        
        # 设置日志
        setup_logging(config)
        
        # 创建并运行同步程序
        sync_app = SyncHKTLora()
        sync_app.run()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n收到退出信号，程序正在退出...")
        return 0
    except Exception as e:
        print(f"程序启动失败: {str(e)}")
        logging.error(f"程序启动失败: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 