import logging
import signal
import sys
import time
import json
import os
import argparse
from datetime import datetime
from pathlib import Path
import glob
import traceback

# 导入版本模块
try:
    import version
    logging.info("成功导入 version 模块")
except ImportError as e:
    logging.error(f"导入 version 模块失败: {str(e)}")

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

# 导入Tools模块中的countdown方法
try:
    from hkt_agent_framework.Tools import countdown
    logging.info("成功导入 Tools.countdown")
except ImportError as e:
    logging.error(f"导入 Tools.countdown 失败: {str(e)}")



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
        """获取默认配置并保存到本地json文件"""
        default_config = {
            "task_params": {
                "sync_top_pages": 3,           # 每次同步的页面数量
                "task_interval_seconds": 120,  # 任务间隔时间（秒）
                "refresh_wait_seconds": 5,     # 页面刷新后等待时间（秒）
                "extract_wait_seconds": 15,    # URL提取后等待时间（秒）
                "leads_wait_seconds": 20,      # 处理销售线索后等待时间（秒）
                "max_run_count":3              # 每轮任务最多刷新次数 
            },
            "logging": {
                "level": "ERROR",              # 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
                "log_dir": "logs"              # 日志文件目录
            }
        }
        
        # 如果配置文件不存在，则创建默认配置文件
        if not os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                logging.info(f"已创建默认配置文件: {self.config_file}")
            except Exception as e:
                logging.error(f"创建默认配置文件失败: {str(e)}")
                
        return default_config
    
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
    
    def __init__(self, config_file='task_config.json', init_mode=True):
        self.running = True
        self.config = SimpleConfig(config_file)
        self.hkt_web = None
        self.playwright = None
        self.browser = None
        self.page = None
        self.leads_insight = None
        self.init_mode = init_mode
        self.run_count = 0
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logging.info("SyncHKTLora 初始化完成")
    
    def _signal_handler(self, signum, frame):
        """处理Ctrl+C信号"""
        self._cleanup()
        logging.info("程序已退出")
        sys.exit(0)
    
    def _cleanup(self):
        """清理资源"""
        try:
            logging.info("收到退出信号，正在清理资源...")            
            self.run_count = 0
            self.running = False
            self._destroy_browser()
            self.hkt_web = None
            self.leads_insight = None        
            logging.info("资源清理完成")
        except Exception as e:
            logging.error(f"清理资源时出错: {str(e)}")
    
    def _destroy_browser(self):
        """安全销毁浏览器资源"""
        try:
            logging.info("正在销毁浏览器资源...")
            
            if self.page:
                logging.info("正在关闭页面...")
                self.page.close()
                self.page = None
                
            if self.browser:
                logging.info("正在关闭浏览器...")
                self.browser.close()
                self.browser = None
                
            if self.playwright:
                logging.info("正在停止Playwright...")
                self.playwright.stop()
                self.playwright = None
                
            logging.info("浏览器资源销毁完成")
        except Exception as e:
            logging.error(f"销毁浏览器资源时出错: {str(e)}")
            # 即使出错也尝试将资源设为None
            self.page = None
            self.browser = None
            self.playwright = None
    
    def _initialize_browser(self):
        """初始化浏览器"""
        # 如果程序被打包，则强制指定Playwright浏览器的路径
        if getattr(sys, 'frozen', False):
            # 尝试使用打包的浏览器路径
            bundle_dir = os.path.dirname(sys.executable)
            bundled_browser_path = os.path.join(bundle_dir, 'playwright', 'driver', 'package', '.local-browsers')
            
            # 调试信息
            logging.info(f"程序已打包，尝试查找浏览器...")
            logging.info(f"可执行文件目录: {bundle_dir}")
            logging.info(f"预期浏览器路径: {bundled_browser_path}")
            
            # 检查是否有打包的Chromium浏览器
            chromium_found = False
            if os.path.exists(bundled_browser_path):
                logging.info(f"浏览器目录存在: {bundled_browser_path}")
                # 列出目录内容
                browser_files = os.listdir(bundled_browser_path)
                logging.info(f"浏览器目录内容: {browser_files}")
                
                # 检查是否有Chromium浏览器文件
                chromium_paths = glob.glob(os.path.join(bundled_browser_path, "chromium-*"))
                if chromium_paths:
                    chromium_found = True
                    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = bundled_browser_path
                    logging.info(f"使用打包的Chromium浏览器: {chromium_paths[0]}")
                    # 强制设置环境变量
                    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = bundled_browser_path
                    # 打印环境变量确认
                    logging.info(f"设置环境变量 PLAYWRIGHT_BROWSERS_PATH={os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")
            else:
                logging.warning(f"打包的浏览器目录不存在: {bundled_browser_path}")
            
            # 如果打包中没有找到浏览器，尝试使用本地安装的浏览器
            if not chromium_found:
                logging.info("在打包目录中未找到浏览器，尝试查找本地安装的浏览器")
                browsers_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ms-playwright')
                if os.path.exists(browsers_path):
                    logging.info(f"本地浏览器目录存在: {browsers_path}")
                    # 列出目录内容
                    local_browser_files = os.listdir(browsers_path)
                    logging.info(f"本地浏览器目录内容: {local_browser_files}")
                    
                    # 检查本地是否有Chromium浏览器
                    chromium_paths = glob.glob(os.path.join(browsers_path, "chromium-*"))
                    if chromium_paths:
                        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_path
                        logging.info(f"使用本地安装的Chromium浏览器: {chromium_paths[0]}")
                        chromium_found = True
                        # 强制设置环境变量
                        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_path
                        # 打印环境变量确认
                        logging.info(f"设置环境变量 PLAYWRIGHT_BROWSERS_PATH={os.environ.get('PLAYWRIGHT_BROWSERS_PATH')}")
                else:
                    logging.warning(f"本地浏览器目录不存在: {browsers_path}")
                
                # 如果仍然没有找到浏览器，尝试直接使用当前目录
                if not chromium_found:
                    logging.info("尝试在当前目录查找浏览器")
                    current_dir = os.path.dirname(os.path.abspath(sys.executable))
                    # 递归搜索当前目录下的所有chromium-*目录
                    for root, dirs, files in os.walk(current_dir):
                        for dir_name in dirs:
                            if dir_name.startswith("chromium-"):
                                browser_dir = os.path.dirname(os.path.join(root, dir_name))
                                logging.info(f"在当前目录找到浏览器: {os.path.join(root, dir_name)}")
                                os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browser_dir
                                logging.info(f"设置环境变量 PLAYWRIGHT_BROWSERS_PATH={browser_dir}")
                                chromium_found = True
                                break
                        if chromium_found:
                            break
                
                # 如果仍然没有找到浏览器，提示安装
                if not chromium_found:
                    logging.error("未找到可用的Playwright Chromium浏览器，请运行install_browser.bat安装")
                    print("\n错误: 未找到Playwright Chromium浏览器，请运行install_browser.bat安装\n")
                    return False

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
                "viewport": {"width": 1024, "height": 768},
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
            traceback_info = traceback.format_exc()
            logging.error(f"详细错误信息: {traceback_info}")
            return False
    
    def _initialize_components(self):
        """初始化组件"""
        try:
            logging.info("正在初始化组件...")
            
            # 获取根日志记录器的级别
            root_logger = logging.getLogger()
            log_level = root_logger.level
            
            # 初始化HKTLoraWeb
            self.hkt_web = HKTLoraWeb()
            if not self.hkt_web:
                raise Exception("HKTLoraWeb初始化失败")
            
            # 初始化LeadsInsight
            self.leads_insight = LeadsInsight()
            if not self.leads_insight:
                raise Exception("LeadsInsight初始化失败")
            elif self.init_mode:
                print("正在初始化DingTalk多维表销售线索数据...")
                if not self.leads_insight.process_with_initialization(initialize_first=True):
                    raise Exception("DingTalk多维表初始化失败")
            
            # 确保所有组件的日志记录器使用相同的级别
            logging.getLogger("HKTLoraWeb").setLevel(log_level)
            logging.getLogger("LeadsInsight").setLevel(log_level)
            logging.getLogger("DingTalk").setLevel(log_level)
            logging.getLogger("Notable").setLevel(log_level)
            logging.getLogger("LogCleaner").setLevel(log_level)
            logging.getLogger("ConversationFlow").setLevel(log_level)
            
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

    def run(self):
        is_first_run = True
                      
        while self.running:        
            """主循环"""
            if not is_first_run:
                self.init_mode = False
            
            is_first_run = False            
            self.run_count = 0
            logging.info("开始主循环...")
            
            # 初始化组件
            if not self._initialize_components():
                logging.error("组件初始化失败，退出程序")
                return False
            
            # 初始化浏览器（需要使用组件中的认证信息）
            if not self._initialize_browser():
                logging.error("浏览器初始化失败，退出程序")
                return False
            
            # 登录
            if not self._login():
                logging.error("登录失败，退出程序")
                return False
            
            logging.info("初始化完成，进入任务循环...")                        
            
            while self.run_count < self.config.get('task_params.max_run_count',30):
                try:
                    self.run_count += 1                    
                    # 任务1：刷新页面，获取新线索
                    sync_top_pages = self.config.get('task_params.sync_top_pages', 1)
                    if not self.hkt_web.do_refresh_pages(self.page, sync_top_pages):
                        logging.error("刷新页面时出错，将在60秒后重试...")
                        countdown(60, 60, "刷新页面失败", new_line=True)
                        continue

                    # 检查是否有新线索
                    output_dir = self.hkt_web.CURRENT_OUTPUT_DIR
                    submission_files = glob.glob(os.path.join(output_dir, "submission_*.json"))
                    
                    if not submission_files:
                        # 没有新线索，等待长周期
                        interval = self.config.get('task_params.task_interval_seconds', 180)
                        if interval < 60:
                            interval = 60
                        logging.info(f"没有发现新的销售线索，等待 {interval} 秒...")
                        countdown(interval - 60, interval, f"等待第 {self.run_count+1} 轮刷新销售线索", new_line=True)
                        continue

                    logging.info(f"发现 {len(submission_files)} 条新线索，立即处理...")

                    # 任务2：处理销售线索
                    if not self._process_leads():
                        logging.error("处理销售线索失败，将在60秒后重试...")
                        countdown(60, 60, "处理线索失败", new_line=True)
                        continue

                    # 任务3：提取失败的URL (可以选择性运行)
                    # self._extract_failed_urls()

                    # 短暂等待后开始下一轮
                    leads_wait = self.config.get('task_params.leads_wait_seconds', 20)
                    logging.info(f"销售线索处理完成，等待 {leads_wait} 秒后开始下一轮...")
                    countdown(leads_wait, leads_wait, f"等待第 {self.run_count+1} 开始", new_line=True)

                except Exception as e:
                    logging.error(f"主循环中出现错误: {str(e)}")
                    self._cleanup()
                    logging.info("出现严重错误，正在重启浏览器...")
                    if not self._initialize_browser() or not self._login():
                        logging.error("浏览器重启或重新登录失败，退出程序")
                        break
            
            # 最终清理
            self._cleanup()
            self.run_count = 0
            self.running = True            
            logging.info("本次主循环结束")
        return True


def setup_logging(config):
    """设置日志"""
    log_dir = config.get('logging.log_dir', 'logs')
    log_level = config.get('logging.level', 'INFO')
    
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    
    # 设置日志文件
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f'sync_hktlora_{current_time}.log')
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    
    # 移除所有现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建并配置文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, log_level))
    root_logger.addHandler(file_handler)
    
    # 创建并配置控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level))
    root_logger.addHandler(console_handler)
    
    # 设置根日志记录器的级别
    root_logger.setLevel(getattr(logging, log_level))
    
    logging.info(f"日志系统初始化完成，日志文件: {log_file}")
    logging.info(f"日志级别设置为: {log_level}")
    
    return log_file, log_level


def get_config_help():
    """返回配置文件帮助信息"""
    return """
task_config.json 配置说明：

{
    "task_params": {
        "sync_top_pages": 1,          # 同步的页数，默认为1
        "task_interval_seconds": 180,  # 任务间隔时间（秒），默认180秒
        "refresh_wait_seconds": 5,     # 刷新后等待时间（秒），默认5秒
        "extract_wait_seconds": 15,    # 提取后等待时间（秒），默认15秒
        "leads_wait_seconds": 20,      # 处理销售线索后等待时间（秒），默认20秒
        "max_run_count":15              # 每轮任务最多刷新次数，默认15次
    },
    "logging": {
        "level": "ERROR",             # 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
        "log_dir": "logs"             # 日志文件目录
    }
}

说明：
1. sync_top_pages: 每次同步时处理的页面数量
2. task_interval_seconds: 两次任务执行之间的等待时间
3. refresh_wait_seconds: 页面刷新后的等待时间，确保页面加载完成
4. extract_wait_seconds: URL提取后的等待时间
5. leads_wait_seconds: 销售线索处理后的等待时间
6. level: 日志记录级别，影响日志的详细程度
7. log_dir: 日志文件保存的目录路径
"""

def parse_arguments():
    """解析命令行参数"""
    # 获取版本号
    try:
        import version
        current_version = version.get_version()
    except Exception:
        current_version = 'v0.9.1'  # 默认版本号
        
    parser = argparse.ArgumentParser(description='HKT Sales Leads Sync Tool')
    parser.add_argument('--version', action='version', version=f'hkt-sales_leads {current_version}')
    parser.add_argument('--help-config', action='store_true', help='显示配置文件帮助信息')
    parser.add_argument('--config', '-c', type=str, default='task_config.json', help='配置文件路径')
    parser.add_argument('--dingtalk', action='store_true', help='是否先从钉钉多维表初始化本地数据')
    args = parser.parse_args()
    
    if args.help_config:
        print(get_config_help())
        sys.exit(0)
    
    return args

def main():
    """主函数"""
    args = parse_arguments()
    
    # 设置日志
    config = SimpleConfig(args.config)
    log_file, log_level = setup_logging(config)

    
    # 显示版本号
    try:
        import version
        current_version = version.get_version()
        print(f"HKT Sales Leads 同步工具 {current_version}")
        logging.info(f"程序版本: {current_version}")
    except Exception as e:
        logging.warning(f"无法获取版本信息: {str(e)}")
    
    try:
        print("SyncHKTLora 启动中...")
        print("按 Ctrl+C 可退出程序")
        print(f"日志文件: {log_file},日志级别: {log_level}")        
        
        

        # 初始化并运行，传入init参数
        while True:
            sync = SyncHKTLora(args.config, init_mode=args.dingtalk)
            if not sync.run():                
                sync._cleanup()   
                countdown(10, 10, "程序将在10秒后重新启动", new_line=True)
                continue
            else:
                break
        
        return 0
        
    except KeyboardInterrupt:
        logging.info("用户中断，程序退出")
        return 0
    except Exception as e:
        logging.error(f"程序运行出错: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 