from collections import defaultdict

class Inquiry_Reply_Prompt:
    """
    提示词管理器类，用于生成和管理各种提示词模板
    包含：
    1. 生成回复阶段提示词
    system_preprocessing_prompt: 系统角色设定提示词
    user_preprocessing_prompt: 用户输入问题提示词
    """
    
    # 业务知识模板
    _BUSINESS_KNOWLEDGE = '''
客户国家：United Kingdom
客户邮件:
“We’re considering switching suppliers due to delayed shipments. Can you guarantee 2-week delivery?”
模型输出:
1、"intent": "物流投诉+新供应商评估"
2、"confidence_score": 0.85
3、"recommended_actions": 
"解释当前供应链优化措施"
"提供加急运输方案"
4、"reply_template": 
"We sincerely apologize for the inconvenience...[物流改进详情]...As a goodwill gesture, we offer..."
'''
    # 系统角色设定模板
    _SYSTEM_ROLE_SETUP = '''
你是一位资深外贸经理助理，专门负责分析邮件并识别潜在销售机会。当前任务是通过解读客户邮件内容，判断客户的意图（如询价、投诉、订单跟进等），并生成专业、友好的回复以促进交易。分析邮件内容中的关键信息（如需求描述、时间要求、隐含意图等）。 生成具备以下特性的回复： 准确性：基于邮件原文和客户背景，避免主观臆断。 主动性：挖掘潜在需求（如推荐关联产品、推动样品申请等）。 输出结构化回复建议，包括：客户意图分类、推荐行动、回复模板。 回复内容专业但非机械，体现对客户文化的理解（如欧美客户直接、亚洲客户委婉）。 参考优秀销售人员的沟通风格（如《影响力》中的互惠原则）。
步骤1、识别留言语种： 默认用英语理解，如果不能理解尝试用客户所在国家对应的官方语言理解。 
步骤2、意图识别： 提取邮件内容中的核心问题（如Can you provide a discount for bulk orders?的语句代表：批量采购意向）。 标注情绪倾向（积极/中性/消极）。
步骤3、需求关联： 匹配客户需求与产品卖点（如客户提到fast delivery，则关联物流优势）。 
步骤4、回复策略： 若为询价：提供报价并附加增值信息（如MOQ、质检报告）。 若为投诉：先共情，再解决方案（参考PEARL原则：共情、道歉、解决、补偿、跟进）。
步骤5、生成回复： 按CARE结构生成。Confirm（确认需求） → Answer（解答问题） → Recommend（附加推荐） → Encourage（促进下一步）。
    '''

    # 用户输入问题模板
    _USER_INPUT_QUESTION = '''
基于'{customer_country}'和'{customer_email}'的内容，按格式生成内容。

#参考示例
{business_knowledge}

#输出格式要求# 
1、'confidence_score': 0.9 
2、'intent': '批量采购询价' 
3、 'recommended_actions': 
'发送阶梯报价表' 
'推荐高性价比型号X' 
4、 'reply_template': 
'Dear [名], Thank you for your interest... [产品推荐]... Looking forward to your feedback!'
    '''
    def __init__(self, customer_country: str = "", customer_email: str = ""):
        """
        初始化PromptManager
        
        Args:
            task_type: 任务类型，默认为"低代码开发"
            question: 问题描述，默认为空字符串
        """
        self._customer_country = customer_country
        self._customer_email = customer_email

    @property
    def customer_country(self) -> str:
        """获取客户国家"""
        return self._customer_country
    
    @property
    def customer_email(self) -> str:
        """获取客户邮件"""
        return self._customer_email
    
    @customer_country.setter
    def customer_country(self, value: str):
        """设置客户国家"""
        self._customer_country = value
    
    @customer_email.setter
    def customer_email(self, value: str):
        """设置客户邮件"""
        self._customer_email = value

    def get_system_role_setup_prompt(self) -> str:
        """
        获取系统角色设定提示词
        
        Returns:
            str: 格式化后的系统角色设定提示词
        """
        return self._SYSTEM_ROLE_SETUP

    def get_user_input_question_prompt(self) -> str:
        """
        获取用户输入问题提示词
        
        Returns:
            str: 格式化后的用户输入问题提示词
        """
        # 使用 defaultdict 安全地格式化 prompt，未找到的 key 会被替换为空字符串
        context = {
            "customer_country": self._customer_country,
            "customer_email": self._customer_email,
            "business_knowledge": self._BUSINESS_KNOWLEDGE
        }
        mapping = defaultdict(str, context)
        formatted_prompt = self._USER_INPUT_QUESTION.format_map(mapping)
        
        return formatted_prompt