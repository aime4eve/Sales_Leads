import time
import random
import re
from playwright.sync_api import sync_playwright
import logging
from datetime import datetime
import os
import json
from tqdm import tqdm
from colorama import Fore, Style, init
import glob

# 初始化colorama
init()

class HKTLoraWeb:
    def __init__(self):
        # 登录配置
        self.AUTH_USER = "access"
        self.AUTH_PASS = "login"
        self.WP_USER = "huakuantong"
        self.WP_PASS = "6HJBx%8b^iyo)t1Sry1amxG7"
        self.BASE_URL = "https://www.hktlora.com/wp-admin"
        self.FORM_LIST_URL = f"{self.BASE_URL}/edit.php?post_type=elementor_cf_db"

        # 输出目录配置
        self.OUTPUT_DIR = "elementor_db_sync"
        self.CURRENT_TIME = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.CURRENT_OUTPUT_DIR = os.path.join(self.OUTPUT_DIR, self.CURRENT_TIME)

        # 确保输出目录存在
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.CURRENT_OUTPUT_DIR, exist_ok=True)

        # 配置日志文件
        self.log_file = f'login_{self.CURRENT_TIME}.log'
        self._setup_logging()

    def _setup_logging(self):
        """设置日志处理器"""
        # 移除所有现有的处理器
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
        # 配置新的日志处理器
        logging.basicConfig(
            level=logging.ERROR,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8')
            ]
        )

    def _close_logging(self):
        """关闭所有日志处理器"""
        # 关闭并移除所有处理器
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)

    def tqdm_info(self, msg, color=Fore.WHITE):
        """使用tqdm写入彩色信息，同时记录到日志"""
        tqdm.write(f"{color}[INFO] {msg}{Style.RESET_ALL}")

    def tqdm_warning(self, msg):
        """使用tqdm写入警告信息，同时记录到日志"""
        tqdm.write(f"{Fore.YELLOW}[WARNING] {msg}{Style.RESET_ALL}")

    def tqdm_error(self, msg):
        """使用tqdm写入错误信息，同时记录到日志"""
        tqdm.write(f"{Fore.RED}[ERROR] {msg}{Style.RESET_ALL}")
        logging.error(msg)

    # 线程C：定时处理线程 B 生成的错误日志
    def extract_failed_urls(self):
        """从日志文件中提取失败的URL地址"""
        failed_urls = []
        try:
            # 查找所有日志文件
            log_files = glob.glob("login_*.log")
            start_time = datetime.strptime(self.CURRENT_TIME, '%Y%m%d_%H%M%S')
            
            for log_file in log_files:
                try:
                    # 从文件名中提取时间
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
                    
                    # 如果是当前日志文件，先关闭日志处理器
                    if log_file == self.log_file:
                        self._close_logging()
                    
                    # 重命名日志文件
                    try:
                        bak_file = log_file.replace('.log', '.bak')
                        # 如果已存在同名的.bak文件，先删除它
                        if os.path.exists(bak_file):
                            os.remove(bak_file)
                        os.rename(log_file, bak_file)
                        self.tqdm_info(f"已将日志文件 {log_file} 重命名为 {bak_file}", Fore.GREEN)
                    except Exception as e:
                        self.tqdm_error(f"重命名日志文件 {log_file} 时出错: {str(e)}")
                    
                    # 如果是当前日志文件，重新设置日志处理器
                    if log_file == self.log_file:
                        self._setup_logging()
                            
                except Exception as e:
                    self.tqdm_error(f"处理日志文件 {log_file} 时出错: {str(e)}")
                    continue
                    
        except Exception as e:
            self.tqdm_error(f"查找日志文件时出错: {str(e)}")
            
        return list(set(failed_urls))  # 返回去重后的URL列表

    def retry_failed_submissions(self, page, failed_urls):
        """重新尝试获取失败的提交记录"""
        if not failed_urls:
            self.tqdm_info("没有发现失败的URL", Fore.GREEN)
            return

        self.tqdm_info(f"开始重试 {len(failed_urls)} 个失败的URL", Fore.CYAN)
        
        # 创建重试输出目录
        retry_output_dir = os.path.join(self.OUTPUT_DIR, f"retry_{self.CURRENT_TIME}")
        os.makedirs(retry_output_dir, exist_ok=True)

        # 使用tqdm创建进度条
        with tqdm(total=len(failed_urls), 
                 desc=f"{Fore.MAGENTA}重试失败的URL{Style.RESET_ALL}", 
                 position=1, 
                 leave=False) as retry_pbar:
            
            # 重试每个失败的URL
            for index, url in enumerate(failed_urls, 1):
                try:
                    # 更新进度条描述
                    retry_pbar.set_description(
                        f"{Fore.MAGENTA}重试第 {index}/{len(failed_urls)} 个URL{Style.RESET_ALL}"
                    )
                    
                    self.tqdm_info(f"正在处理: {url}", Fore.YELLOW)
                    if self.save_submission_data(page, url, retry_output_dir):
                        self.tqdm_info(f"成功保存数据: {url}", Fore.GREEN)
                    else:
                        self.tqdm_warning(f"保存数据失败: {url}")
                        
                    # 更新进度条
                    retry_pbar.update(1)
                    
                except Exception as e:
                    self.tqdm_error(f"处理URL时出错 {url}: {str(e)}")
                    retry_pbar.update(1)  # 即使出错也更新进度条

    def extract_submission_data(self, page):
        """提取提交记录详细数据"""
        data = {
            "form_submission": {},
            "extra_information": {}
        }
        
        try:
            # 获取Form Submission表格
            form_table = page.query_selector('#sb_elem_cfd')
            if form_table:
                # 获取所有数据行
                rows = form_table.query_selector_all('tbody tr')
                for row in rows:
                    try:
                        # 获取标签列（第一列）
                        label_cell = row.query_selector('td:first-child strong')
                        if not label_cell:
                            continue
                        label = label_cell.text_content().strip().replace('*', '').strip()
                        
                        # 获取值列（第二列）
                        value_cell = row.query_selector('td:nth-child(2)')
                        if not value_cell:
                            continue
                            
                        # 检查是否有段落标签
                        value_p = value_cell.query_selector('p')
                        value = (value_p.text_content() if value_p else value_cell.text_content()).strip()
                        
                        data["form_submission"][label] = value
                    except Exception as e:
                        self.tqdm_warning(f"提取Form Submission行数据时出错: {str(e)}")
            else:
                self.tqdm_warning("未找到Form Submission表格")

            # 获取Extra Information表格
            extra_section = page.query_selector('#sb_elem_cfd_extra')
            if extra_section:
                extra_table = extra_section.query_selector('table.widefat')
                if extra_table:
                    # 获取所有数据行
                    rows = extra_table.query_selector_all('tbody tr')
                    for row in rows:
                        try:
                            # 获取标签列（第一列）
                            label_cell = row.query_selector('td:first-child strong')
                            if not label_cell:
                                continue
                            label = label_cell.text_content().strip()
                            
                            # 获取值列（第二列）
                            value_cell = row.query_selector('td:nth-child(2)')
                            if not value_cell:
                                continue
                            
                            # 检查是否有链接
                            links = value_cell.query_selector_all('a')
                            if links and len(links) > 0:
                                # 处理包含多个链接的情况
                                link_data = []
                                for link in links:
                                    link_data.append({
                                        "text": link.text_content().strip(),
                                        "href": link.get_attribute('href')
                                    })
                                value = {
                                    "links": link_data,
                                    "full_text": value_cell.text_content().strip()
                                }
                            else:
                                # 检查是否有斜体文本
                                em = value_cell.query_selector('em')
                                if em:
                                    value = em.text_content().strip()
                                else:
                                    value = value_cell.text_content().strip()
                            
                            data["extra_information"][label] = value
                        except Exception as e:
                            self.tqdm_warning(f"提取Extra Information行数据时出错: {str(e)}")
                else:
                    self.tqdm_warning("未找到Extra Information表格")
     
            else:
                self.tqdm_warning("未找到Extra Information部分")

        except Exception as e:
            self.tqdm_error(f"提取表单数据时出错: {str(e)}")

        return data

    def save_submission_data(self, page, link, current_output_dir):
        """保存单个提交记录的数据"""
        try:
            # 访问提交详情页面
            page.goto(link)
            page.wait_for_load_state("networkidle")
            
            # 提取数据
            form_data = self.extract_submission_data(page)
            
            # 保存数据
            post_id = link.split("post=")[-1]
            output_file = os.path.join(current_output_dir, f"submission_{post_id}.json")
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(form_data, f, ensure_ascii=False, indent=2)
                return True
            except IOError as e:
                self.tqdm_error(f"保存数据到文件时出错: {str(e)}")
                return False
                
        except Exception as e:
            self.tqdm_error(f"保存单个提交记录时出错: {str(e)}")
            return False

    def extract_Elementor_DB(self, page, page_num):
        """提取当前页面的Elementor数据库表格数据"""
        try:
            # 使用选择器获取表格
            table = page.query_selector('#posts-filter > table')
            if not table:
                self.tqdm_error("未找到目标表格")
                return []

            # 获取所有行
            rows = table.query_selector_all('tr')
            table_data = []
            headers = []

            for i, row in enumerate(rows):
                if i == 0:  # 表头行
                    # 获取表头
                    header_cells = row.query_selector_all('th')
                    headers = [cell.text_content().strip() for cell in header_cells if cell.text_content().strip()]
                    continue

                # 数据行
                cells = row.query_selector_all('td')
                if not cells:
                    continue

                row_data = {}
                for j, cell in enumerate(cells):
                    if j >= len(headers):
                        continue
                        
                    # 获取View Submission链接
                    if headers[j] == "View":
                        link = cell.query_selector('a')
                        if link:
                            row_data[headers[j]] = {
                                "text": link.text_content().strip(),
                                "href": link.get_attribute("href")
                            }
                    # 获取Form ID
                    elif headers[j] == "Form ID":
                        row_data[headers[j]] = cell.text_content().strip()
                    # 获取Email
                    elif headers[j] == "Email":
                        row_data[headers[j]] = cell.text_content().strip()
                    # 获取Read/Unread状态
                    elif headers[j] == "Read/Unread":
                        row_data[headers[j]] = cell.text_content().strip()
                    # 获取Cloned状态
                    elif headers[j] == "Cloned":
                        row_data[headers[j]] = cell.text_content().strip()
                    # 获取Submitted On
                    elif headers[j] == "Submitted On":
                        row_data[headers[j]] = cell.text_content().strip()
                    # 获取Submission Date
                    elif headers[j] == "Submission Date":
                        row_data[headers[j]] = cell.text_content().strip()
                    else:
                        row_data[headers[j]] = cell.text_content().strip()

                if row_data:
                    table_data.append(row_data)

            submission_links = []
            if table_data:
                # 保存表格数据
                table_output_file = os.path.join(self.CURRENT_OUTPUT_DIR, f"Elementor_DB_{page_num}.json")
                try:
                    with open(table_output_file, 'w', encoding='utf-8') as f:
                        json.dump(table_data, f, ensure_ascii=False, indent=2)
                except IOError as e:
                    self.tqdm_error(f"保存表格数据时出错: {str(e)}")

                # 从表格数据中提取View Submission链接
                for row in table_data:
                    if "View" in row and "href" in row["View"]:
                        submission_links.append(row["View"]["href"])
            
                # 处理View Submission链接
                with tqdm(total=len(submission_links), 
                         desc=f"{Fore.MAGENTA}处理第 {page_num} 页记录{Style.RESET_ALL}", 
                         position=1, 
                         leave=False) as sub_pbar:
                    for index, link in enumerate(submission_links, 1):
                        try:
                            sub_pbar.set_description(
                                f"{Fore.MAGENTA}处理第 {page_num} 页，第 {index}/{len(submission_links)} 个提交记录{Style.RESET_ALL}"
                            )

                            # 保存提交记录数据
                            # 测试
                            # self.save_submission_data(page, link, self.CURRENT_OUTPUT_DIR)
                            sub_pbar.update(1)
                            
                            # 添加随机延迟，避免请求过于频繁
                            delay = random.uniform(1, 3)  # 随机延迟1-3秒
                            time.sleep(delay)
                            
                        except Exception as e:
                            self.tqdm_error(f"保存单个提交记录时出错: {str(e)}")
                            continue

            return table_data
            
        except Exception as e:
            self.tqdm_error(f"提取表格数据时出错: {str(e)}")
            return []

    def extract_pages(self, page):
        """提取当前页面的分页信息"""
        try:
            total_pages = 1
            current_page = 1
            # 获取分页信息
            pagination = page.query_selector('.tablenav-paging-text')
            if pagination:
                # 获取总页数
                total_pages_span = pagination.query_selector('.total-pages')
                if total_pages_span:      
                    total_pages = int(total_pages_span.text_content().strip())
            # 获取当前页码
            current_url = page.url                    
            # 从URL中提取页码
            page_match = re.search(r'paged=(\d+)', current_url)
            if page_match:
                current_page = int(page_match.group(1))
            return total_pages, current_page
        
        except Exception as e:
            self.tqdm_error(f"提取分页信息时出错: {str(e)}")
            return 1, 1

    # 线程A：创建单个浏览器实例并完成 www.hktlora.com 的登录逻辑
    def login_main_site(self, page):
        """登录到www.hktlora.com主站点"""
        try:
            self.tqdm_info("开始登录 www.hktlora.com 主站点", Fore.GREEN)
            
            with tqdm(total=5, desc=f"{Fore.GREEN}登录系统{Style.RESET_ALL}", position=1, leave=False) as login_pbar:
                page.goto(self.BASE_URL)
                login_pbar.update(1)
                
                # 等待登录表单加载
                page.wait_for_selector("#user_login")
                page.wait_for_selector("#user_pass")
                login_pbar.update(1)

                # 填写登录表单
                page.fill("#user_login", self.WP_USER)
                page.fill("#user_pass", self.WP_PASS)
                login_pbar.update(1)
                
                # 点击登录按钮
                page.click("#wp-submit")
                login_pbar.update(1)
                
                # 等待登录完成
                page.wait_for_selector("#wpadminbar")
                self.tqdm_info("登录成功！", Fore.GREEN)
                login_pbar.update(1)
                
                return True
                
        except Exception as e:
            self.tqdm_error(f"登录失败: {str(e)}")
            return False

    def download_url(self, page, url, page_num=None):
        """访问指定URL并提取页面数据"""
        try:
            page.goto(url)
            page.wait_for_load_state('networkidle')
            # 添加随机延迟，避免请求过于频繁
            delay = random.uniform(1, 2)
            time.sleep(delay)
            
            # 获取当前URL
            current_url = page.url
            
            # 提取分页信息
            total_pages, current_page = self.extract_pages(page)
            
            # 提取表格数据
            if page_num is not None:
                self.extract_Elementor_DB(page, page_num)
                
            return True, current_url, total_pages, current_page
            
        except Exception as e:
            self.tqdm_error(f"处理页面失败 {url}: {str(e)}")
            return False, None, None, None

    # 线程B：定时刷新指定网页，抓取内容并保存到本地 JSON 文件，同时记录错误信息到日志文件
    def do_refresh_pages(self, page, sync_top_pages=5):
        with tqdm(total=1, desc=f"{Fore.BLUE}开始下载......{Style.RESET_ALL}", position=1, leave=True) as page_pbar:
            # 先访问第一页获取总页数
            page_pbar.set_description(f"{Fore.BLUE}处理第 首页 {Style.RESET_ALL}")
            success, current_url, total_pages, current_page = self.download_url(
                page, 
                self.FORM_LIST_URL, 
                page_num=1
            )
            if not success:
                self.tqdm_error("无法访问表单列表页面，程序退出")
                return
            
            page_pbar.total = total_pages
            page_pbar.refresh()

            # 处理后续分页数据
            while True:
                try:
                    # 如果已经是最后一页或达到同步页数限制，退出循环
                    if current_page >= (sync_top_pages if sync_top_pages is not None else total_pages):
                        break
                                            
                    # 构造下一页的URL
                    next_page_num = current_page + 1                        
                    base_url = re.sub(r'&paged=\d+', '', current_url)  # 移除现有的paged参数
                    if '?' in base_url:
                        next_page_url = f"{base_url}&paged={next_page_num}"
                    else:
                        next_page_url = f"{base_url}?paged={next_page_num}"

                    # 更新进度条
                    page_pbar.set_description(f"{Fore.BLUE}处理第 {next_page_num}/{total_pages} 页{Style.RESET_ALL}")
                    page_pbar.update(1)                             

                    # 导航到下一页并提取数据
                    success, current_url, total_pages, current_page = self.download_url(
                        page,
                        next_page_url,
                        page_num=next_page_num
                    )                       

                    if not success:
                        self.tqdm_warning(f"跳过第 {next_page_num} 页")
                        continue

                except (ValueError, TypeError) as e:
                    self.tqdm_warning(f"无法解析页码数值: {str(e)}")
                    break
                except Exception as e:
                    self.tqdm_error(f"处理分页时出错: {str(e)}")
                    break
    
    def run(self,sync_top_pages=5):
        """运行主程序"""
        try:
            self.tqdm_info("启动自动化登录脚本", Fore.CYAN)
                            
            with sync_playwright() as p:
                # 启动浏览器
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(
                    http_credentials={"username": self.AUTH_USER, "password": self.AUTH_PASS}
                )
                
                # 创建新页面
                page = context.new_page()
                # self.tqdm_info("成功创建浏览器实例", Fore.GREEN)
                
                # 登录www.hktlora.com
                if not self.login_main_site(page):
                    self.tqdm_error("登录失败，程序退出")
                    return
                            
                # 提取表格数据
                self.tqdm_info("开始提取Elementor_DB数据库表格数据", Fore.BLUE)
                self.do_refresh_pages(page, sync_top_pages=sync_top_pages)
                
                # 创建分页进度条
                # with tqdm(total=1, desc=f"{Fore.BLUE}开始下载......{Style.RESET_ALL}", position=1, leave=True) as page_pbar:
                #     # 先访问第一页获取总页数
                #     page_pbar.set_description(f"{Fore.BLUE}处理第 首页 {Style.RESET_ALL}")
                #     success, current_url, total_pages, current_page = self.download_url(
                #         page, 
                #         self.FORM_LIST_URL, 
                #         page_num=1
                #     )
                #     if not success:
                #         self.tqdm_error("无法访问表单列表页面，程序退出")
                #         return
                    
                #     page_pbar.total = total_pages
                #     page_pbar.refresh()

                #     # 处理后续分页数据
                #     while True:
                #         try:
                #             # 如果已经是最后一页或达到同步页数限制，退出循环
                #             if current_page >= (sync_top_pages if sync_top_pages is not None else total_pages):
                #                 break
                                                       
                #             # 构造下一页的URL
                #             next_page_num = current_page + 1                        
                #             base_url = re.sub(r'&paged=\d+', '', current_url)  # 移除现有的paged参数
                #             if '?' in base_url:
                #                 next_page_url = f"{base_url}&paged={next_page_num}"
                #             else:
                #                 next_page_url = f"{base_url}?paged={next_page_num}"

                #             # 更新进度条
                #             page_pbar.set_description(f"{Fore.BLUE}处理第 {next_page_num}/{total_pages} 页{Style.RESET_ALL}")
                #             page_pbar.update(1)                             

                #             # 导航到下一页并提取数据
                #             success, current_url, total_pages, current_page = self.download_url(
                #                 page,
                #                 next_page_url,
                #                 page_num=next_page_num
                #             )                       

                #             if not success:
                #                 self.tqdm_warning(f"跳过第 {next_page_num} 页")
                #                 continue

                #         except (ValueError, TypeError) as e:
                #             self.tqdm_warning(f"无法解析页码数值: {str(e)}")
                #             break
                #         except Exception as e:
                #             self.tqdm_error(f"处理分页时出错: {str(e)}")
                #             break

                # 完成处理
                self.tqdm_info("所有提交记录处理完成", Fore.CYAN)
                
                # 处理失败的URL
                self.tqdm_info("开始处理失败的URL", Fore.CYAN)
                # 获取脚本运行期间的失败URL
                all_failed_urls = self.extract_failed_urls()
                
                # 重试失败的URL
                if all_failed_urls:
                    self.retry_failed_submissions(page, all_failed_urls)
                else:
                    self.tqdm_info("没有发现需要重试的URL", Fore.GREEN)
                
                # 关闭浏览器
                browser.close()
                self.tqdm_info("脚本执行完成", Fore.CYAN)

        except Exception as e:
            self.tqdm_error(f"发生错误: {str(e)}")
            raise 