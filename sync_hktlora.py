import logging
import threading
import time
import queue
import os
import re
import json
import signal
import sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from hktloraweb import HKTLoraWeb
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from apscheduler.jobstores.memory import MemoryJobStore

# 配置日志文件
current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
log_dir = 'logs'  # 定义日志目录
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, f'login_{current_time}.log')  # 包含完整路径的日志文件名

# 运行状态记录文件
run_state_file = 'apscheduler_state.json'

# Playwright操作队列类
class PlaywrightQueue:
    def __init__(self):
        self.queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.thread = None
        self.running = False
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.hkt_web = None
        
    def start(self, hkt_web):
        """启动Playwright操作线程"""
        self.running = True
        self.hkt_web = hkt_web
        self.thread = threading.Thread(target=self._process_queue)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self):
        """停止Playwright操作线程"""
        self.running = False
        
        # 清空队列
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except:
                pass
                
        # 发送停止信号
        try:
            self.queue.put(None)
        except:
            pass
            
        # 等待线程结束，但最多等待5秒
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
            
        # 如果线程还在运行，尝试强制终止（仅在Windows上有效）
        if self.thread and self.thread.is_alive():
            try:
                import ctypes
                thread_id = self.thread.ident
                if thread_id:
                    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                        ctypes.c_long(thread_id), 
                        ctypes.py_object(SystemExit)
                    )
                    if res > 1:
                        ctypes.pythonapi.PyThreadState_SetAsyncExc(
                            ctypes.c_long(thread_id), 
                            None
                        )
            except:
                pass
                
        self._cleanup()
            
        # 清空引用
        self.thread = None
        self.hkt_web = None
            
    def _cleanup(self):
        """清理Playwright资源"""
        if self.page:
            try:
                self.page.close()
            except:
                pass
        if self.context:
            try:
                self.context.close()
            except:
                pass
        if self.browser:
            try:
                self.browser.close()
            except:
                pass
        if self.playwright:
            try:
                self.playwright.stop()
            except:
                pass
                
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        
    def _process_queue(self):
        """处理Playwright操作队列的主循环"""
        while self.running:
            try:
                # 获取下一个操作
                operation = self.queue.get()
                if operation is None:  # 停止信号
                    break
                    
                func, args = operation
                
                # 如果是初始化操作且还没有创建浏览器实例
                if func == 'init' and not self.browser:
                    try:
                        self.playwright = sync_playwright().start()
                        self.browser = self.playwright.chromium.launch(headless=False)
                        self.context = self.browser.new_context(
                            http_credentials={"username": self.hkt_web.AUTH_USER, "password": self.hkt_web.AUTH_PASS}
                        )
                        self.page = self.context.new_page()
                        self.result_queue.put((True, None))
                    except Exception as e:
                        self.result_queue.put((False, str(e)))
                        self._cleanup()
                    continue
                
                # 执行操作
                try:
                    if func == 'login':
                        result = self.hkt_web.login_main_site(self.page)
                        self.result_queue.put((True, result))
                    elif func == 'refresh':
                        sync_top_pages = args[0] if args else 2
                        self.hkt_web.do_refresh_pages(self.page, sync_top_pages)
                        self.result_queue.put((True, None))
                    elif func == 'process_failed':
                        failed_urls = args[0] if args else []
                        retry_dir = args[1] if len(args) > 1 else None
                        if failed_urls and retry_dir:
                            for url in failed_urls:
                                self.hkt_web.save_submission_data(self.page, url, retry_dir)
                        self.result_queue.put((True, None))
                except Exception as e:
                    self.result_queue.put((False, str(e)))
                    
            except Exception as e:
                logging.error(f"Playwright队列处理出错: {str(e)}")
                if not self.result_queue.empty():
                    try:
                        self.result_queue.get_nowait()  # 清空结果队列
                    except:
                        pass
                self.result_queue.put((False, str(e)))
                
    def execute(self, func, *args):
        """执行Playwright操作并等待结果"""
        self.queue.put((func, args))
        success, result = self.result_queue.get()
        if not success:
            raise Exception(f"Playwright操作失败: {result}")
        return result

# 设置日志格式
def setup_logging():
    """设置日志配置"""
    # 日志目录已在全局创建
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,  # 确保日志级别为 INFO
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # 同时输出到控制台
        ]
    )
    
    # 设置APScheduler日志级别为 INFO
    logging.getLogger('apscheduler').setLevel(logging.INFO)
    
    # 确保其他模块的日志级别也是 INFO
    logging.getLogger().setLevel(logging.INFO)
    
    return log_file

# 运行状态记录
class RunStateManager:
    """管理程序运行状态的持久化"""
    
    def __init__(self, state_file=run_state_file):
        """初始化状态管理器"""
        self.state_file = state_file
        self.state = self._load_state() or {
            'last_run': None,
            'completed_runs': 0,
            'error_count': 0,
            'last_error': None,
            'last_status': 'init',  # init, running, error, completed
            'sync_top_pages': 2,
            'task_b_start_delay_seconds': 0,  # 默认任务B延迟0秒启动
            'task_b_interval_minutes': 5,    # 默认任务B间隔5分钟
            'task_c_start_delay_seconds': 60, # 默认任务C延迟60秒启动
            'task_c_interval_minutes': 10,    # 默认任务C间隔10分钟
            'task_b_running': False,         # 任务B的执行状态
            'task_c_running': False,         # 任务C的执行状态
            'task_b_last_start': None,       # 任务B最后一次开始执行的时间
            'task_c_last_start': None,       # 任务C最后一次开始执行的时间
            'task_b_last_end': None,         # 任务B最后一次结束执行的时间
            'task_c_last_end': None          # 任务C最后一次结束执行的时间
        }
    
    def _load_state(self):
        """从文件加载状态"""
        if not os.path.exists(self.state_file):
            return None
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载状态文件时出错: {str(e)}")
            return None
    
    def save_state(self):
        """保存状态到文件"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            logging.info("已保存运行状态")
        except Exception as e:
            logging.error(f"保存状态文件时出错: {str(e)}")
    
    def update_state(self, **kwargs):
        """更新状态"""
        for key, value in kwargs.items():
            if key in self.state:
                self.state[key] = value
        
        # 更新最后运行时间
        self.state['last_run'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 保存更新后的状态
        self.save_state()
    
    def get_state(self, key=None):
        """获取状态"""
        if key:
            return self.state.get(key)
        return self.state
    
    def record_error(self, error_msg):
        """记录错误"""
        self.state['error_count'] += 1
        self.state['last_error'] = {
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'message': str(error_msg)
        }
        self.state['last_status'] = 'error'
        self.save_state()
    
    def record_completion(self):
        """记录成功完成"""
        self.state['completed_runs'] += 1
        self.state['last_status'] = 'completed'
        self.save_state()

    def set_task_running(self, task_name, is_running):
        """设置任务运行状态"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if task_name == 'task_b':
            self.state['task_b_running'] = is_running
            if is_running:
                self.state['task_b_last_start'] = current_time
            else:
                self.state['task_b_last_end'] = current_time
        elif task_name == 'task_c':
            self.state['task_c_running'] = is_running
            if is_running:
                self.state['task_c_last_start'] = current_time
            else:
                self.state['task_c_last_end'] = current_time
        self.save_state()

    def is_task_running(self, task_name):
        """检查任务是否正在运行"""
        if task_name == 'task_b':
            return self.state.get('task_b_running', False)
        elif task_name == 'task_c':
            return self.state.get('task_c_running', False)
        return False

    def get_task_last_end_time(self, task_name):
        """获取任务最后一次结束时间"""
        if task_name == 'task_b':
            return self.state.get('task_b_last_end')
        elif task_name == 'task_c':
            return self.state.get('task_c_last_end')
        return None

# 共享资源类
class SharedResources:
    def __init__(self, state_manager=None):
        """初始化共享资源"""
        self.playwright_queue = PlaywrightQueue()
        self.error_count = 0
        self.max_error_count = 3  # 最大错误次数，超过将重启流程
        self.current_time = current_time  # 使用与日志文件相同的时间戳
        self.state_manager = state_manager
        
        # 如果有状态管理器，从中加载配置
        if self.state_manager:
            self.sync_top_pages = self.state_manager.get_state('sync_top_pages') or 2
            self.task_b_start_delay_seconds = self.state_manager.get_state('task_b_start_delay_seconds') or 0
            self.task_b_interval_minutes = self.state_manager.get_state('task_b_interval_minutes') or 5
            self.task_c_start_delay_seconds = self.state_manager.get_state('task_c_start_delay_seconds') or 60
            self.task_c_interval_minutes = self.state_manager.get_state('task_c_interval_minutes') or 10
        else:
            self.sync_top_pages = 2  # 默认同步的页面数
            self.task_b_start_delay_seconds = 0
            self.task_b_interval_minutes = 5
            self.task_c_start_delay_seconds = 60
            self.task_c_interval_minutes = 10
        
    def init_hkt_web(self):
        """初始化HKTLoraWeb实例"""
        self.hkt_web = HKTLoraWeb()
        # 确保 HKTLoraWeb 实例也使用 logs 目录下的日志文件
        if self.hkt_web.log_file and not self.hkt_web.log_file.startswith('logs' + os.path.sep):
            self.hkt_web.log_file = os.path.join('logs', self.hkt_web.log_file)
            logging.info(f"HKTLoraWeb 实例的 log_file 更新为: {self.hkt_web.log_file}")
            
        # 修补extract_failed_urls方法
        patch_extract_failed_urls(self.hkt_web)
        
        # 启动Playwright队列
        self.playwright_queue.start(self.hkt_web)
        
        return self.hkt_web
        
    def cleanup(self):
        """清理资源"""
        logging.info("开始清理资源")
        self.playwright_queue.stop()
        logging.info("资源清理完成")
        
    def reset_error_count(self):
        """重置错误计数"""
        self.error_count = 0
        
    def increment_error_count(self):
        """增加错误计数并返回是否达到阈值"""
        self.error_count += 1
        
        # 如果有状态管理器，记录错误
        if self.state_manager:
            self.state_manager.update_state(error_count=self.state_manager.get_state('error_count') + 1)
            
        return self.error_count >= self.max_error_count
    
    def set_sync_top_pages(self, pages):
        """设置同步的页面数"""
        self.sync_top_pages = pages
        
        # 如果有状态管理器，更新状态
        if self.state_manager:
            self.state_manager.update_state(sync_top_pages=pages)

# 修改HKTLoraWeb类的extract_failed_urls方法，避免尝试重命名当前正在使用的日志文件
def patch_extract_failed_urls(hkt_web):
    original_extract_failed_urls = hkt_web.extract_failed_urls
    
    def patched_extract_failed_urls():
        failed_urls = []
        log_dir = 'logs' # 定义日志目录
        try:
            # 确保logs目录存在
            if not os.path.exists(log_dir):
                logging.warning(f"日志目录 {log_dir} 不存在，无法提取失败的URL。")
                return []

            # 只查找logs目录中的日志文件
            log_files_in_logs_dir = [os.path.join(log_dir, f) for f in os.listdir(log_dir) if f.startswith('login_') and f.endswith('.log')]
            
            # hkt_web.CURRENT_TIME 应该是来自 sync_hktlora.py 的全局 current_time
            # 它是一个格式如 YYYYMMDD_HHMMSS 的字符串
            # hkt_web.log_file 此刻应该是 'logs/login_YYYYMMDD_HHMMSS.log'
            current_log_file_full_path = hkt_web.log_file 

            start_time_str = getattr(hkt_web, 'CURRENT_TIME', None)
            if not start_time_str:
                logging.error("HKTLoraWeb 实例缺少 CURRENT_TIME 属性，无法确定日志时间范围。")
                return []
            start_time = datetime.strptime(start_time_str, '%Y%m%d_%H%M%S')
            
            for log_file_path in log_files_in_logs_dir:
                try:
                    # 跳过当前正在使用的日志文件 (比较完整路径)
                    if log_file_path == current_log_file_full_path:
                        logging.info(f"跳过当前正在使用的日志文件: {log_file_path}")
                        continue
                        
                    # 从文件名中提取时间
                    # 文件名格式: login_YYYYMMDD_HHMMSS.log
                    file_name = os.path.basename(log_file_path)
                    file_time_str_match = re.search(r'login_(\d{8}_\d{6})\.log', file_name)
                    if not file_time_str_match:
                        logging.warning(f"无法从文件名 {file_name} 中提取时间，跳过此文件。")
                        continue
                        
                    file_time = datetime.strptime(file_time_str_match.group(1), '%Y%m%d_%H%M%S')
                    
                    # 跳过晚于程序启动时间的文件 (hkt_web.CURRENT_TIME)
                    # 这是为了确保只处理本次运行之前的旧日志
                    if file_time >= start_time:
                        logging.info(f"跳过较新的或同期的日志文件: {log_file_path} (文件时间: {file_time}, 程序启动时间: {start_time})")
                        continue
                    
                    # 读取并解析日志文件
                    with open(log_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 使用正则表达式匹配URL
                        matches = re.finditer(r'navigating to "(https://[^"]+)"', content)
                        for match in matches:
                            failed_urls.append(match.group(1))
                    
                    # 重命名日志文件
                    try:
                        bak_file = log_file_path.replace('.log', '.bak')
                        # 如果已存在同名的.bak文件，先删除它
                        if os.path.exists(bak_file):
                            os.remove(bak_file)
                        os.rename(log_file_path, bak_file)
                        logging.info(f"已将日志文件 {log_file_path} 重命名为 {bak_file}")
                    except Exception as e:
                        logging.error(f"重命名日志文件 {log_file_path} 时出错: {str(e)}")
                            
                except Exception as e:
                    logging.error(f"处理日志文件 {log_file_path} 时出错: {str(e)}")
                    continue
                    
        except Exception as e:
            logging.error(f"查找日志文件时出错: {str(e)}")
            
        return list(set(failed_urls))  # 返回去重后的URL列表
    
    # 替换原方法
    hkt_web.extract_failed_urls = patched_extract_failed_urls
    return hkt_web

# 配置APScheduler
def create_scheduler():
    """创建并配置APScheduler调度器"""
    # 配置作业存储
    jobstores = {
        'default': MemoryJobStore()
    }
    
    # 配置执行器 - 使用线程池执行器，允许多个任务并行执行
    executors = {
        'default': ThreadPoolExecutor(2)  # 增加到2个线程，允许任务B和C并行执行
    }
    
    # 配置作业默认值
    job_defaults = {
        'coalesce': True,                 # 合并执行错过的作业
        'max_instances': 1,               # 作业最大实例数
        'misfire_grace_time': 180,        # 增加错过作业的宽限时间到3分钟
        'replace_existing': True          # 总是替换现有的作业
    }
    
    # 创建调度器
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone='Asia/Shanghai',  # 设置时区为上海
        logger=logging.getLogger('apscheduler')
    )
    
    return scheduler

# 全局调度器实例
scheduler = create_scheduler()

# 任务A: 创建浏览器实例并登录
def task_a_login(resources, scheduler):
    """线程A：创建浏览器实例并登录"""
    logging.info("任务A开始：创建浏览器实例并登录")
    
    try:
        # 更新状态
        if resources.state_manager:
            resources.state_manager.update_state(last_status='running')
        
        # 初始化Playwright
        resources.playwright_queue.execute('init')
        logging.info("浏览器实例创建成功")
        
        # 执行登录
        login_success = resources.playwright_queue.execute('login')
        
        if not login_success:
            logging.error("登录失败，需要重新启动流程")
            resources.cleanup()
            
            # 记录错误
            if resources.state_manager:
                resources.state_manager.record_error("登录失败")
            
            # 返回失败状态，调度器会处理异常
            return False
        
        # 登录成功，添加线程B和线程C的定时任务
        logging.info("登录成功，将添加线程B和线程C的定时任务")
        
        # 获取当前时间
        now = datetime.now()
        
        # 添加线程B任务
        scheduler.add_job(
            func=task_b_refresh_pages, 
            trigger='interval', 
            minutes=resources.task_b_interval_minutes, 
            id='task_b_refresh_pages', 
            name='定时刷新页面和保存内容', 
            args=[resources, scheduler],
            next_run_time=now + timedelta(seconds=resources.task_b_start_delay_seconds),
            misfire_grace_time=60,  # 1分钟的宽限时间
            coalesce=True,
            max_instances=1,
            replace_existing=True
        )
        logging.info(f"任务B将在 {resources.task_b_start_delay_seconds} 秒后开始，并每 {resources.task_b_interval_minutes} 分钟运行一次")

        # 添加线程C任务
        scheduler.add_job(
            func=task_c_process_logs, 
            trigger='interval', 
            minutes=resources.task_c_interval_minutes, 
            id='task_c_process_logs', 
            name='定时处理错误日志', 
            args=[resources, scheduler],
            next_run_time=now + timedelta(seconds=resources.task_c_start_delay_seconds),
            misfire_grace_time=180,  # 3分钟的宽限时间
            coalesce=True,
            max_instances=1,
            replace_existing=True
        )
        logging.info(f"任务C将在 {resources.task_c_start_delay_seconds} 秒后开始，并每 {resources.task_c_interval_minutes} 分钟运行一次")
        
        resources.reset_error_count()
        return True
    
    except Exception as e:
        logging.error(f"任务A执行出错: {str(e)}")
        resources.cleanup()
        
        # 记录错误
        if resources.state_manager:
            resources.state_manager.record_error(str(e))
            
        return False

# 任务B: 定时刷新页面并保存内容
def task_b_refresh_pages(resources, scheduler):
    """线程B：定时刷新页面并保存内容"""
    # 检查任务B是否正在运行
    if resources.state_manager.is_task_running('task_b'):
        logging.warning("任务B仍在运行中，跳过本次执行")
        return False

    start_time = datetime.now()
    logging.info("任务B开始：定时刷新页面并保存内容")
    
    try:
        # 设置任务B为运行状态
        resources.state_manager.set_task_running('task_b', True)
        
        # 执行页面刷新和内容保存
        resources.playwright_queue.execute('refresh', resources.sync_top_pages)
        
        # 记录执行时间
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        logging.info(f"页面刷新和内容保存完成，执行时间：{execution_time:.2f}秒")
        
        # 重置错误计数
        resources.reset_error_count()
        
        # 重新获取配置参数
        if resources.state_manager:
            new_sync_top_pages = resources.state_manager.get_state('sync_top_pages')
            new_interval_minutes = resources.state_manager.get_state('task_b_interval_minutes')
            
            # 如果配置有变化，更新资源对象中的值并重新调度任务
            config_changed = False
            
            if new_sync_top_pages is not None and new_sync_top_pages != resources.sync_top_pages:
                logging.info(f"sync_top_pages配置已更新: {resources.sync_top_pages} -> {new_sync_top_pages}")
                resources.sync_top_pages = new_sync_top_pages
                config_changed = True
                
            if new_interval_minutes is not None and new_interval_minutes != resources.task_b_interval_minutes:
                logging.info(f"task_b_interval_minutes配置已更新: {resources.task_b_interval_minutes} -> {new_interval_minutes}")
                resources.task_b_interval_minutes = new_interval_minutes
                config_changed = True
            
            # 如果配置发生变化，重新调度任务
            if config_changed:
                logging.info("重新调度任务B以应用新的配置")
                try:
                    # 获取当前时间
                    now = datetime.now()
                    # 移除现有的任务B
                    scheduler.remove_job('task_b_refresh_pages')
                    # 添加新的任务B
                    scheduler.add_job(
                        func=task_b_refresh_pages,
                        trigger='interval',
                        minutes=resources.task_b_interval_minutes,
                        id='task_b_refresh_pages',
                        name='定时刷新页面和保存内容',
                        args=[resources, scheduler],
                        next_run_time=now + timedelta(minutes=resources.task_b_interval_minutes),
                        misfire_grace_time=60,
                        coalesce=True,
                        max_instances=1,
                        replace_existing=True
                    )
                    logging.info(f"任务B已重新调度，将在 {resources.task_b_interval_minutes} 分钟后执行")
                except Exception as e:
                    logging.error(f"重新调度任务B时出错: {str(e)}")
        
        # 设置任务B为非运行状态
        resources.state_manager.set_task_running('task_b', False)
        return True
    
    except Exception as e:
        logging.error(f"任务B执行出错: {str(e)}")
        # 设置任务B为非运行状态
        resources.state_manager.set_task_running('task_b', False)
        if resources.increment_error_count():
            restart_process(resources, scheduler)
        return False

# 任务C: 处理错误日志
def task_c_process_logs(resources, scheduler):
    """线程C：处理错误日志"""
    # 检查任务C是否正在运行
    if resources.state_manager.is_task_running('task_c'):
        logging.warning("任务C仍在运行中，跳过本次执行")
        return False

    start_time = datetime.now()
    logging.info("任务C开始：处理错误日志")
    
    try:
        # 设置任务C为运行状态
        resources.state_manager.set_task_running('task_c', True)
        
        # 提取失败的URL
        logging.info("开始提取失败的URL...")
        failed_urls = resources.hkt_web.extract_failed_urls()
        logging.info(f"提取完成，找到 {len(failed_urls) if failed_urls else 0} 个失败的URL")
        
        if failed_urls:
            # 创建重试输出目录
            retry_dir = os.path.join(resources.hkt_web.OUTPUT_DIR, f"retry_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(retry_dir, exist_ok=True)
            logging.info(f"创建重试输出目录: {retry_dir}")
            
            # 记录失败的URL到文件
            failed_urls_file = os.path.join(retry_dir, "failed_urls.txt")
            with open(failed_urls_file, "w", encoding="utf-8") as f:
                for url in failed_urls:
                    f.write(f"{url}\n")
            logging.info(f"已将失败的URL记录到文件: {failed_urls_file}")
            
            logging.info(f"找到 {len(failed_urls)} 个失败的URL，开始重试")
            # 重试失败的URL
            resources.playwright_queue.execute('process_failed', failed_urls, retry_dir)
        else:
            logging.info("没有发现失败的URL")
        
        # 记录执行时间
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        logging.info(f"错误日志处理完成，执行时间：{execution_time:.2f}秒")
        
        # 重置错误计数
        resources.reset_error_count()
        
        # 更新完成记录
        if resources.state_manager:
            resources.state_manager.record_completion()
            
        # 设置任务C为非运行状态
        resources.state_manager.set_task_running('task_c', False)
        return True
    
    except Exception as e:
        logging.error(f"任务C执行出错: {str(e)}")
        # 设置任务C为非运行状态
        resources.state_manager.set_task_running('task_c', False)
        if resources.increment_error_count():
            restart_process(resources, scheduler)
        return False

# 异常处理：重启流程
def restart_process(resources, scheduler):
    """重启整个流程"""
    logging.warning("错误次数过多，重启整个流程")
    
    # 记录错误状态
    if resources.state_manager:
        resources.state_manager.update_state(last_status='restarting')
    
    # 移除现有的任务B和任务C
    try:
        scheduler.remove_job('task_b_refresh_pages')
        logging.info("已移除任务B")
    except Exception as e:
        logging.warning(f"移除任务B时出错: {str(e)}")
    
    try:
        scheduler.remove_job('task_c_process_logs')
        logging.info("已移除任务C")
    except Exception as e:
        logging.warning(f"移除任务C时出错: {str(e)}")
    
    # 清理资源
    resources.cleanup()
    resources.reset_error_count()
    
    # 重新添加任务A（一次性任务，立即执行）
    scheduler.add_job(
        task_a_login, 
        'date',
        args=[resources, scheduler],
        id='task_a',
        replace_existing=True
    )
    
    logging.info("已重新安排任务A执行")

# 作业监听器
def job_listener(event):
    """作业执行监听器"""
    if event.exception:
        job_id = event.job_id
        logging.error(f"作业 {job_id} 执行失败: {str(event.exception)}")
    else:
        job_id = event.job_id
        logging.info(f"作业 {job_id} 执行成功")

def cleanup_and_exit(scheduler, resources, state_manager, signum=None, frame=None):
    """清理资源并退出程序"""
    try:
        logging.info("开始清理资源并退出程序...")
        
        # 先移除所有任务
        if scheduler and scheduler.running:
            try:
                scheduler.remove_all_jobs()
                logging.info("已移除所有调度任务")
            except:
                pass
            
            # 关闭调度器
            logging.info("关闭APScheduler调度器")
            scheduler.shutdown(wait=False)  # 不等待任务完成
        
        # 清理资源
        if resources:
            logging.info("清理共享资源")
            # 确保 playwright_queue 停止
            if resources.playwright_queue:
                resources.playwright_queue.running = False
                if resources.playwright_queue.queue:
                    while not resources.playwright_queue.queue.empty():
                        try:
                            resources.playwright_queue.queue.get_nowait()
                        except:
                            pass
            resources.cleanup()
        
        # 更新最终状态
        if state_manager:
            logging.info("更新最终状态")
            state_manager.update_state(last_status='shutdown')
        
        # 关闭所有日志处理器
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)
            
        logging.info("程序正常退出")
        
        # 强制退出程序
        os._exit(0)
        
    except Exception as e:
        logging.error(f"清理资源时出错: {str(e)}")
        os._exit(1)

# 主函数
def main():
    # 设置日志
    full_log_path = setup_logging()
    
    logging.info("开始网页抓取程序")
    logging.info(f"日志文件: {full_log_path}")
    
    # 创建状态管理器
    state_manager = RunStateManager()
    logging.info(f"加载运行状态: {state_manager.get_state()}")
    
    # 创建共享资源
    resources = SharedResources(state_manager)
    resources.init_hkt_web()
    
    # 创建调度器
    scheduler = create_scheduler()
    
    try:
        # 注册信号处理函数
        signal.signal(signal.SIGINT, lambda signum, frame: cleanup_and_exit(scheduler, resources, state_manager, signum, frame))
        signal.signal(signal.SIGTERM, lambda signum, frame: cleanup_and_exit(scheduler, resources, state_manager, signum, frame))
        
        # 添加作业监听器
        scheduler.add_listener(
            job_listener, 
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
        )
        
        # 添加任务A（一次性任务，立即执行）
        scheduler.add_job(
            task_a_login, 
            'date',
            args=[resources, scheduler],
            id='task_a'
        )
        
        # 启动调度器
        logging.info("启动APScheduler调度器")
        scheduler.start()
        
        # 等待用户中断
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                logging.info("收到用户中断信号")
                cleanup_and_exit(scheduler, resources, state_manager)
                break  # 虽然 cleanup_and_exit 会调用 sys.exit()，但以防万一还是加上 break
    
    except Exception as e:
        logging.error(f"主程序异常: {str(e)}")
        # 记录错误
        state_manager.record_error(str(e))
        # 清理资源并退出
        cleanup_and_exit(scheduler, resources, state_manager)

if __name__ == "__main__":
    main() 