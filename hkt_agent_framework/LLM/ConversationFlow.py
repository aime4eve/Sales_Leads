import json
from typing import Any, Dict, Optional
from collections import defaultdict
import logging
import os
import sys

try:
    # This works when the script is imported as a module in a package.
    from .SiliconCloud import SiliconCloud
except ImportError:
    # This is a fallback for when the script is run directly, fixing the path.
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)
    from hkt_agent_framework.LLM.SiliconCloud import SiliconCloud
# 获取SiliconCloud的日志记录器并设置级别
logger = logging.getLogger(__name__)
# 使用根日志记录器的级别
root_logger = logging.getLogger()
logger.setLevel(root_logger.level)

class ConversationFlow:
    """
    一个引擎，用于驱动基于预定义规则的、有状态的多轮对话。
    """
    def __init__(self, llm_client: Any, flow_definition: Optional[Dict[str, Any]] = None):
        """
        初始化对话流引擎。

        Args:
            llm_client (Any): 一个遵循特定接口的LLM客户端对象。
            flow_definition (Dict, optional): 包含"nodes"和"edges"的对话流程定义。
                                              如果为None，则从默认文件加载。
        """
        if flow_definition:
            self.flow_definition = flow_definition
        else:
            # 从默认文件加载流程定义
            current_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(current_dir, 'inquiry_replay_flow.json')
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    self.flow_definition = json.load(f)
            except FileNotFoundError:
                if getattr(sys, 'frozen', False):
                    base_path = sys._MEIPASS
                    json_path = os.path.join(base_path, 'hkt_agent_framework', 'LLM', 'inquiry_replay_flow.json')
                    with open(json_path, 'r', encoding='utf-8') as f:
                        self.flow_definition = json.load(f)
                else:
                    raise

        self.llm_client = llm_client
        self.conversation_history = []

        # 验证流程定义的基本结构
        if 'nodes' not in self.flow_definition or 'edges' not in self.flow_definition:
            raise ValueError("流程定义必须包含 'nodes' 和 'edges'。")
        
        self.nodes = {node['id']: node for node in self.flow_definition['nodes']}
        self.start_node_id = self.flow_definition.get('start_node')
        if not self.start_node_id or self.start_node_id not in self.nodes:
            raise ValueError("流程定义必须有一个有效的 'start_node'。")

    @classmethod
    def from_json_file(cls, filepath: str, llm_client: Any):
        """
        从JSON文件加载流程定义并创建ConversationFlow实例。
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            flow_definition = json.load(f)
        return cls(llm_client=llm_client, flow_definition=flow_definition)

    def _execute_node(self, node_id: str, context: Dict[str, Any]) -> str:
        """
        执行单个节点：格式化prompt，构建消息，调用LLM，并返回AI响应。
        """
        node = self.nodes[node_id]
        
        # 使用 defaultdict 来安全地格式化字符串
        mapping = defaultdict(str, context)

        system_prompt = node.get("system_prompt", "").format_map(mapping)
        user_prompt = node.get("user_prompt", "").format_map(mapping)
        
        messages_to_send = []
        if system_prompt:
            messages_to_send.append({"role": "system", "content": system_prompt})
        if user_prompt:
            messages_to_send.append({"role": "user", "content": user_prompt})

        if not messages_to_send:
            print(f"警告: 节点 {node_id} 没有有效的prompt，跳过执行。")
            return ""

        print(f"\n--- [调用LLM - 节点: {node_id}] ---")
        ai_response = self.llm_client.chat(messages_to_send)
        print(f"--- [AI响应] ---\n{ai_response}\n--------------------")

        # 记录完整的对话交互
        self.conversation_history.append({
            "node_id": node_id,
            "request": messages_to_send,
            "response": ai_response
        })
        
        return ai_response

    def _find_next_node_id(self, current_node_id: str, last_response: str) -> Optional[str]:
        """根据上一步的响应和边定义查找下一个节点。"""
        possible_edges = [edge for edge in self.flow_definition['edges'] if edge['from'] == current_node_id]
        
        default_edge = None
        for edge in possible_edges:
            condition = edge.get('condition')
            if not condition:
                # 这是一个无条件的边，通常不应该和其他条件边一起使用
                return edge['to']
            
            if condition.get('default', False):
                default_edge = edge
                continue
            
            # 核心条件逻辑：检查响应是否包含指定的子字符串
            if 'contains' in condition and condition['contains'] in last_response:
                print(f"--- [条件满足] 响应中包含 '{condition['contains']}'，转换到节点 {edge['to']} ---")
                return edge['to']
        
        if default_edge:
            print(f"--- [默认转换] 未满足任何特定条件，转换到默认节点 {default_edge['to']} ---")
            return default_edge['to']
        
        return None

    def run(self, initial_context: Optional[Dict[str, Any]] = None):
        """
        启动并循环执行对话流，直到没有下一个节点。
        """
        print("--- 对话流开始 ---")
        context = initial_context or {}
        current_node_id = self.start_node_id
        last_ai_response = ""

        while current_node_id:
            # 执行当前节点
            ai_response = self._execute_node(current_node_id, context)
            
            # 更新上下文，以便下一个节点可以使用上一步的结果
            context['last_user_answer'] = ai_response
            last_ai_response = ai_response
            
            # 查找下一个节点
            next_node_id = self._find_next_node_id(current_node_id, last_ai_response)
            
            current_node_id = next_node_id

        print("\n--- 对话流结束 ---")
        logger.info("\n--- 完整对话历史记录 ---")
        logger.info(json.dumps(self.conversation_history, indent=2, ensure_ascii=False))
        return self.conversation_history

# --- 模拟和测试代码 ---
class MockLLMClient:
    """一个模拟的LLM客户端，用于测试目的。"""
    _step = 0
    def chat(self, messages):
        """模拟多轮对话行为。"""
        MockLLMClient._step += 1
        
        print("\n--- [DEBUG] MockLLMClient.chat() received: ---")
        print(f"    messages: {messages}")
        print("-------------------------------------------\n")

        # 第一次调用（setp_1）时，返回一个包含特殊标记的响应
        if MockLLMClient._step == 1:
            # return "这是第一步的分析结果。##%%继续%%## 请根据此结果提炼产品需求。"
            return "本次结束"
        
        # 第二次调用（setp_2）时，返回最终结果
        if MockLLMClient._step == 2:
             return "已收到第一步的结果，分析出的产品需求是：需要一个低功耗、远距离的传感器解决方案。"

        # 其他意外调用
        return "这是一个通用的结束语。"

if __name__ == '__main__':
    print("正在初始化对话流引擎...")
    

    
    # --- 测试 inquiry_replay_flow.json ---
    print("\n--- 开始测试: inquiry_replay_flow.json (带条件分支的自动流程) ---")
    try:
        flow = ConversationFlow()
        print("对话流引擎初始化成功！")
        
        initial_context = {
            'customer_name': "Tlhalefang Sepato",
            'customer_country': "Botswana",
            'customer_email': "Please, i am so interested on you technology. want to trade with it. can you please share more details. Thanks"
        }
        # 切换为 MockLLMClient 进行可预测的测试
        flow.llm_client = MockLLMClient()
        # 运行流程
        flow.run(initial_context=initial_context)
        
    except FileNotFoundError:
        print("错误：找不到 'inquiry_replay_flow.json'。请确保它位于正确的目录中。")
    except Exception as e:
        print(f"初始化或运行过程中发生错误: {e}")
        import traceback
        traceback.print_exc() 