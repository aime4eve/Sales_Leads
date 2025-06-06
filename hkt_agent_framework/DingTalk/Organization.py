# 作者：伍志勇
# 日期：2025-01-13
# 开发日志：创建Organization对象，实现钉钉部门API调用

# 钉钉组织架构API访问对象

import logging
import json
import os
import requests
import time
from datetime import datetime
import traceback
# 导入进度条库
from tqdm import tqdm
# 导入DingTalk类
from DingTalk import DingTalk

# 配置日志记录
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Organization")


class Organization:
    """
    钉钉组织架构API访问类，负责处理部门相关的API调用
    """
    
    def __init__(self, config_path=None, config_dict=None):
        """
        初始化组织架构API访问对象
        
        参数:
            config_path (str, optional): 配置文件路径
            config_dict (dict, optional): 配置字典
        """
        try:
            # 初始化DingTalk对象，复用其认证和请求功能
            self.dingtalk = DingTalk(config_path=config_path, config_dict=config_dict)
            
            # 设置notable目录路径
            self.notable_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'notable')
            
            # 确保notable目录存在
            if not os.path.exists(self.notable_dir):
                os.makedirs(self.notable_dir)
                logger.info(f"创建notable目录: {self.notable_dir}")
            
            logger.info("Organization对象初始化成功")
            
        except Exception as e:
            logger.error(f"初始化Organization对象时出错：{str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def get_department_list(self, parent_id=1, save_to_file=True, filename="部门列表.json"):
        """
        获取钉钉部门列表
        
        参数:
            parent_id (int): 父部门ID，默认为1（根部门）
            save_to_file (bool): 是否保存到文件，默认为True
            filename (str): 保存的文件名，默认为"部门列表.json"
            
        返回:
            dict: 部门列表数据
        """
        try:
            logger.info(f"开始获取部门列表，父部门ID: {parent_id}")
            
            # 构建API URL（旧版API格式）
            # 注意：用户提供的是旧版API，需要使用access_token作为URL参数
            access_token = self.dingtalk.ensure_access_token()
            # api_url = f"https://oapi.dingtalk.com/topapi/v2/department/listsub?access_token={access_token}"
            api_url = self.dingtalk.get_department_listsub_url.replace("{access_token}", access_token)
            
            # 构建请求数据
            request_data = {
                "dept_id": parent_id
            }
            
            logger.debug(f"请求URL: {api_url}")
            logger.debug(f"请求数据: {json.dumps(request_data, ensure_ascii=False)}")
            
            # 使用特殊的请求头（旧版API不需要x-acs-dingtalk-access-token）
            headers = {
                "Content-Type": "application/json"
            }
            
            result = self.dingtalk.call_dingtalk_api(
                method='POST',
                url=api_url,
                headers=headers,
                json_data=request_data
            )


            
            logger.debug(f"API响应: {json.dumps(result, ensure_ascii=False)}")
            
            # 检查API响应是否成功
            if result.get('errcode') == 0:
                logger.info(f"成功获取部门列表，共 {len(result.get('result', []))} 个部门")
                
                # 保存到文件
                if save_to_file:
                    self.save_to_notable(result, filename)
                
                return result
            else:
                error_msg = f"API调用失败，错误码: {result.get('errcode')}, 错误信息: {result.get('errmsg')}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except requests.exceptions.Timeout:
            logger.error("获取部门列表请求超时")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"获取部门列表请求失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"获取部门列表时出现错误: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def save_to_notable(self, data, filename):
        """
        将数据保存到notable目录的JSON文件中
        
        参数:
            data (dict): 要保存的数据
            filename (str): 文件名
        """
        try:
            file_path = os.path.join(self.notable_dir, filename)
            
            # 添加保存时间戳
            save_data = {
                "save_time": datetime.now().isoformat(),
                "data": data
            }
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"数据已保存到文件: {file_path}")
            
        except Exception as e:
            logger.error(f"保存数据到文件时出错: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def get_department_users(self, dept_id, cursor=0, size=3, save_to_file=False, filename=None):
        """
        获取指定部门的用户列表
        
        参数:
            dept_id (int): 部门ID
            cursor (int): 分页游标，默认为0
            size (int): 每页大小，默认为3（按要求固定值）
            save_to_file (bool): 是否保存到文件，默认为False
            filename (str): 保存的文件名，默认为"部门{dept_id}用户列表.json"
            
        返回:
            dict: 包含用户列表的响应数据
        """
        try:
            logger.info(f"开始获取部门 {dept_id} 的用户列表，cursor={cursor}, size={size}")
            
            # 获取access_token
            access_token = self.dingtalk.ensure_access_token()
            
            # 构建API URL，使用配置中的模板
            api_url = self.dingtalk.get_user_list_by_department_url.format(
                access_token=access_token,
                dept_id=dept_id,
                cursor=cursor,
                size=min(size, 100)
            )
            
            logger.debug(f"请求URL: {api_url}")
            
            # 使用DingTalk对象的call_dingtalk_api方法
            result = self.dingtalk.call_dingtalk_api(
                method='POST',
                url=api_url,
                headers={"Content-Type": "application/json"},
                json_data={}  # 旧版API参数在URL中，POST body为空
            )
            
            logger.info(f"成功获取部门 {dept_id} 的用户列表")
            logger.debug(f"响应数据: {json.dumps(result, ensure_ascii=False)}")
            
            # 保存到文件（如果需要）
            if save_to_file:
                if filename is None:
                    filename = f"部门{dept_id}用户列表.json"
                self.save_to_notable(result, filename)
            
            return result
            
        except Exception as e:
            logger.error(f"获取部门 {dept_id} 用户列表失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def get_all_department_users(self, save_to_file=True, filename="员工列表.json"):
        """
        获取所有部门的所有用户（自动处理分页）
        
        参数:
            save_to_file (bool): 是否保存到文件，默认为True
            filename (str): 保存的文件名，默认为"全公司员工列表.json"
            
        返回:
            dict: 包含所有部门所有用户的完整数据
        """
        try:
            logger.info("开始获取所有部门的所有用户")
            
            # 1. 先调用get_departments_flat_list方法获取所有部门dept_id
            departments_result = self.get_departments_flat_list(save_to_file=True)
            all_departments = departments_result.get('departments', [])
            
            if not all_departments:
                logger.warning("未找到任何部门")
                return {
                    "errcode": 0,
                    "errmsg": "ok",
                    "result": {
                        "total_departments": 0,
                        "total_users": 0,
                        "departments": []
                    }
                }
            
            logger.info(f"找到 {len(all_departments)} 个部门，开始获取每个部门的用户")
            
            # 2. 为每个部门获取用户
            all_departments_users = []
            total_users = 0
            
            # 创建部门级别的进度条
            dept_progress = tqdm(all_departments, desc="获取部门用户", unit="部门")
            
            for dept in dept_progress:
                dept_id = dept.get('dept_id')
                dept_name = dept.get('name', '未知部门')
                
                if dept_id:
                    try:
                        # 更新部门进度条描述
                        dept_progress.set_description(f"获取部门: {dept_name}")
                        logger.info(f"获取部门 {dept_name} (ID: {dept_id}) 的用户")
                        
                        # 获取该部门的所有用户（处理分页）
                        dept_users = []
                        cursor = 0
                        has_more = True
                        page_count = 0
                        
                        # 创建分页进度条（动态更新）
                        page_progress = tqdm(desc=f"  {dept_name[:10]}...", unit="页", leave=False, position=1)
                        
                        while has_more:
                            page_count += 1
                            page_progress.update(1)
                            page_progress.set_description(f"  {dept_name[:10]}...第{page_count}页")
                            logger.debug(f"部门 {dept_name} 第 {page_count} 页，cursor={cursor}")
                            
                            # 获取当前页数据，size固定为3
                            response = self.get_department_users(
                                dept_id=dept_id,
                                cursor=cursor,
                                size=3,
                                save_to_file=False
                            )
                            
                            # 检查响应格式
                            if response.get('errcode') == 0:
                                result = response.get('result', {})
                                users = result.get('list', [])
                                
                                # 添加用户到部门用户列表
                                dept_users.extend(users)
                                
                                # 检查是否还有更多数据
                                has_more = result.get('has_more', False)
                                next_cursor = result.get('next_cursor')
                                
                                if has_more and next_cursor is not None:
                                    cursor = next_cursor
                                else:
                                    has_more = False
                                
                                logger.debug(f"部门 {dept_name} 第 {page_count} 页获取到 {len(users)} 个用户")
                                
                            else:
                                logger.error(f"部门 {dept_name} API返回错误: {response}")
                                break
                        
                        # 关闭分页进度条
                        page_progress.close()
                        
                        # 为每个用户添加部门信息
                        for user in dept_users:
                            user['department_info'] = {
                                'dept_id': dept_id,
                                'dept_name': dept_name
                            }
                        
                        user_count = len(dept_users)
                        total_users += user_count
                        
                        dept_info = {
                            'dept_id': dept_id,
                            'dept_name': dept_name,
                            'user_count': user_count,
                            'page_count': page_count,
                            'users': dept_users
                        }
                        
                        all_departments_users.append(dept_info)
                        logger.info(f"部门 {dept_name} 获取到 {user_count} 个用户")
                        
                    except Exception as e:
                        logger.error(f"获取部门 {dept_name} (ID: {dept_id}) 用户失败: {str(e)}")
                        # 继续处理其他部门
                        continue
            
            # 关闭部门进度条
            dept_progress.close()
            
            # 构建完整结果
            complete_result = {
                "errcode": 0,
                "errmsg": "ok",
                "result": {
                    "total_departments": len(all_departments_users),
                    "total_users": total_users,
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "departments": all_departments_users
                }
            }
            
            logger.info(f"全公司员工列表获取完成，共 {len(all_departments_users)} 个部门，{total_users} 个用户")
            
            # 保存到文件（如果需要）
            if save_to_file:
                self.save_to_notable(complete_result, filename)
            
            return complete_result
            
        except Exception as e:
            logger.error(f"获取全公司员工列表失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise


    
    def get_department_detail(self, dept_id, save_to_file=False):
        """
        获取部门详细信息
        
        参数:
            dept_id (int): 部门ID
            save_to_file (bool): 是否保存到文件，默认为False
            
        返回:
            dict: 部门详细信息
        """
        try:
            logger.info(f"开始获取部门详细信息，部门ID: {dept_id}")
            
            # 构建API URL
            access_token = self.dingtalk.ensure_access_token()
            api_url = f"https://oapi.dingtalk.com/topapi/v2/department/get?access_token={access_token}"
            
            # 构建请求数据
            request_data = {
                "dept_id": dept_id
            }
            
            # 使用特殊的请求头
            headers = {
                "Content-Type": "application/json"
            }
            
            # 调用API
            response = requests.post(
                api_url,
                headers=headers,
                json=request_data,
                timeout=30
            )
            
            # 检查响应状态
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            
            # 检查API响应是否成功
            if result.get('errcode') == 0:
                logger.info(f"成功获取部门详细信息: {result.get('result', {}).get('name', '未知部门')}")
                
                # 保存到文件
                if save_to_file:
                    filename = f"部门详情_{dept_id}.json"
                    self.save_to_notable(result, filename)
                
                return result
            else:
                error_msg = f"API调用失败，错误码: {result.get('errcode')}, 错误信息: {result.get('errmsg')}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"获取部门详细信息时出现错误: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def get_all_departments(self, save_to_file=True, filename="完整部门列表.json"):
        """
        递归获取所有部门信息，构建完整的树形结构
        
        参数:
            save_to_file (bool): 是否保存到文件，默认为True
            filename (str): 保存的文件名，默认为"完整部门列表.json"
            
        返回:
            dict: 完整的部门树结构
        """
        try:
            logger.info("开始获取完整部门列表")
            
            # 获取根部门下的所有子部门
            root_departments_response = self.get_department_list(parent_id=1, save_to_file=False)
            root_departments = root_departments_response.get('result', [])
            
            # 统计信息
            total_departments = 0
            
            # 递归构建树形结构
            def build_department_tree(dept_list):
                nonlocal total_departments
                
                for dept in dept_list:
                    dept_id = dept.get('dept_id')
                    total_departments += 1
                    
                    if dept_id:
                        try:
                            # 获取子部门
                            sub_depts_response = self.get_department_list(parent_id=dept_id, save_to_file=False)
                            sub_depts = sub_depts_response.get('result', [])
                            
                            # 设置子部门字段
                            dept['sub_departments'] = sub_depts
                            dept['has_children'] = len(sub_depts) > 0
                            dept['children_count'] = len(sub_depts)
                            
                            # 如果有子部门，递归处理
                            if sub_depts:
                                logger.debug(f"部门 '{dept.get('name')}' 有 {len(sub_depts)} 个子部门")
                                build_department_tree(sub_depts)
                            else:
                                logger.debug(f"部门 '{dept.get('name')}' 是叶子节点")
                                
                        except Exception as e:
                            logger.warning(f"获取部门 {dept_id} 的子部门失败: {str(e)}")
                            dept['sub_departments'] = []
                            dept['has_children'] = False
                            dept['children_count'] = 0
                            dept['error'] = str(e)
            
            # 开始构建树形结构
            build_department_tree(root_departments)
            
            # 构建返回数据
            result = {
                "summary": {
                    "total_departments": total_departments,
                    "root_departments_count": len(root_departments),
                    "generated_time": datetime.now().isoformat()
                },
                "tree_structure": root_departments
            }
            
            logger.info(f"完成获取完整部门列表，共 {total_departments} 个部门")
            
            # 保存到文件
            if save_to_file:
                self.save_to_notable(result, filename)
            
            return result
            
        except Exception as e:
            logger.error(f"获取完整部门列表时出现错误: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def get_departments_flat_list(self, save_to_file=True, filename="部门列表.json"):
        """
        获取所有部门的扁平列表（非树形结构）
        
        参数:
            save_to_file (bool): 是否保存到文件，默认为True
            filename (str): 保存的文件名，默认为"部门列表.json"
            
        返回:
            dict: 包含所有部门的扁平列表
        """
        try:
            logger.info("开始获取部门扁平列表")
            
            all_departments = []
            processed_dept_ids = set()
            
            # 创建部门收集进度条
            dept_collect_progress = tqdm(desc="收集部门", unit="部门", position=0)
            
            def collect_departments(parent_id):
                try:
                    response = self.get_department_list(parent_id=parent_id, save_to_file=False)
                    departments = response.get('result', [])
                    
                    for dept in departments:
                        dept_id = dept.get('dept_id')
                        dept_name = dept.get('name', '未知部门')
                        if dept_id and dept_id not in processed_dept_ids:
                            processed_dept_ids.add(dept_id)
                            all_departments.append(dept)
                            
                            # 更新进度条
                            dept_collect_progress.update(1)
                            dept_collect_progress.set_description(f"收集部门: {dept_name[:15]}...")
                            
                            # 递归获取子部门
                            collect_departments(dept_id)
                            
                except Exception as e:
                    logger.warning(f"获取父部门 {parent_id} 的子部门失败: {str(e)}")
            
            # 从根部门开始收集
            collect_departments(1)
            
            # 关闭进度条
            dept_collect_progress.close()
            
            result = {
                "summary": {
                    "total_departments": len(all_departments),
                    "generated_time": datetime.now().isoformat()
                },
                "departments": all_departments
            }
            
            logger.info(f"完成获取部门扁平列表，共 {len(all_departments)} 个部门")
            
            # 保存到文件
            if save_to_file:
                self.save_to_notable(result, filename)
            
            return result
            
        except Exception as e:
            logger.error(f"获取部门扁平列表时出现错误: {str(e)}")
            logger.error(traceback.format_exc())
            raise


def _get_color_codes():
    """获取终端颜色代码"""
    return {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "cyan": "\033[96m",
        "reset": "\033[0m"
    }

def main():
     # 获取颜色代码
    colors = _get_color_codes()
    
    try:
        # 创建Organization对象
        org = Organization()     
        
        # 获取所有部门的所有用户
        print(f"{colors['yellow']}正在获取所有部门的所有用户...{colors['reset']}")
        users_result = org.get_all_department_users()
        total_depts = users_result.get('result', {}).get('total_departments', 0)
        total_users = users_result.get('result', {}).get('total_users', 0)
        print(f"{colors['green']}成功获取全公司员工列表，共 {total_depts} 个部门，{total_users} 个用户{colors['reset']}")
        print(f"{colors['cyan']}全公司员工列表已保存到 notable/全公司员工列表.json{colors['reset']}")
        
    except Exception as e:
        print(f"{colors['red']}执行失败: {str(e)}{colors['reset']}") 

# 使用示例
if __name__ == "__main__":
    main()