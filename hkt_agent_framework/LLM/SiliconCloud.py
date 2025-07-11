import requests
import json
import logging
from .Prompt import Inquiry_Reply_Prompt

# 获取SiliconCloud的日志记录器并设置级别
logger = logging.getLogger(__name__)
# 使用根日志记录器的级别
root_logger = logging.getLogger()
logger.setLevel(root_logger.level)

class Message:
    def __init__(self, role="user", content=""):
        self._role = role
        self._content = content
    
    def __str__(self):
        return f"{self._role}: {self._content}"
    
    def __repr__(self):
        return self.__str__()
    
    def to_json(self):
        return json.dumps(self.to_dict())
    
    def to_dict(self):
        return {
            "role": self._role,
            "content": self._content
        }
    
    def from_json(self, json_str):
        data = json.loads(json_str)
        self._role = data["role"]
        self._content = data["content"]
        return self
    
    def from_dict(self, data):
        self._role = data["role"]
        self._content = data["content"]
        return self
    
    def from_json_file(self, json_file):
        with open(json_file, "r") as f:
            self.from_json(f.read())
        return self
    
    @property
    def role(self):
        return self._role
    
    @role.setter
    def role(self, role):
        self._role = role
        return self
    
    @property
    def content(self):
        return self._content
    
    @content.setter
    def content(self, content):
        self._content = content
        return self
    
    def set_role(self, role):
        self._role = role
        return self
    
    def set_content(self, content):
        self._content = content
        return self
    
    @property
    def get_role(self):
        return self._role
    
    @property
    def get_content(self):
        return self._content
    
class SiliconCloud:
    def __init__(self, model="deepseek-ai/DeepSeek-R1"):
        self.model = model
        self.url = "https://api.siliconflow.cn/v1/chat/completions"
        self.headers = {
            "Authorization": "Bearer sk-oggtqfkngvjnveqljbymxtjqzsndlxhwugtcvqzmpsurszny",
            "Content-Type": "application/json"
        }
        
    def chat(self, messages):
        # Handle both single Message object and list of messages
        if isinstance(messages, Message):
            formatted_messages = [messages.to_dict()]
        else:
            # Convert messages to dictionaries if they are Message objects or JSON strings
            formatted_messages = []
            for msg in messages:
                if isinstance(msg, Message):
                    formatted_messages.append(msg.to_dict())
                elif isinstance(msg, str):
                    try:
                        formatted_messages.append(json.loads(msg))
                    except json.JSONDecodeError:
                        # If not valid JSON, treat as plain text user message
                        formatted_messages.append({"role": "user", "content": msg})
                elif isinstance(msg, dict):
                    formatted_messages.append(msg)
                else:
                    raise TypeError(f"Unsupported message type: {type(msg)}")
        # 检查formatted_messages中是否有空的键值
        can_send_messages = False
        for msg in formatted_messages:
            role = msg.get("role", "").lower()
            content = msg.get("content", "")
            if role == 'user' and content is not None:
                can_send_messages = True
                break
            
        if not can_send_messages:
            logger.debug("缺少需要询问大模型的内容！")
            return ""
            
            
        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": False
        }
        
        try:
            response = requests.post(self.url, json=payload, headers=self.headers)
            response.raise_for_status()  # Raise exception for HTTP errors
            response_json = response.json()
            
            # Extract content from the response
            if (response_json and 
                "choices" in response_json and 
                len(response_json["choices"]) > 0 and 
                "message" in response_json["choices"][0] and 
                "content" in response_json["choices"][0]["message"]):
                return response_json["choices"][0]["message"]["content"]
            else:
                # Return full response if content not found
                return response_json
        except requests.exceptions.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response content: {response.text}")
            return {"error": "Failed to decode JSON response", "raw_response": response.text}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return {"error": f"Request failed: {str(e)}"}
    
    

if __name__ == "__main__":
    sc = SiliconCloud()
    customer_country="Nigeria"
    customer_email="""
Hi, We are interested in LORA enebaled or compatible sensors for downhole installation of oil and gas wells. We are also interested in gateways and remote transmission units (RTU's) that are compatible with the LORA technology. Thanks Chinedu Onyeizu    
    """
    prompt = Inquiry_Reply_Prompt(customer_country=customer_country, customer_email=customer_email)
    system_msg = Message(role="system",content=prompt.get_system_role_setup_prompt())
    user_msg = Message(role="user",content=prompt.get_user_input_question_prompt())
    response = sc.chat([system_msg,user_msg])
    print(response)    

    
    
    