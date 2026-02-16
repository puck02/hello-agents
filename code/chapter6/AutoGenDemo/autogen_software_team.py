"""
AutoGen 软件开发团队协作案例
"""

import os
import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 先测试一个版本，使用 OpenAI 客户端
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.ui import Console

def create_openai_model_client():
    """创建 OpenAI 模型客户端用于测试"""
    return OpenAIChatCompletionClient(
        model=os.getenv("LLM_MODEL_ID", "gpt-4o"),
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    )

def create_product_manager(model_client):
    """创建产品经理智能体"""
    system_message = """你是一位经验丰富的产品经理，专门负责软件产品的需求分析和项目规划。

【协作协议】
你只在以下两种情况输出有效内容：
1) 首轮（还没有任何 NEXT:/DECISION:/QA: 控制标记）
2) 最近三条消息中任意一条包含 DECISION:BACK_TO_PM

如果不满足以上条件，只回复：SKIP

你的输出必须在最后一行追加：NEXT:TO_ENGINEER

你的核心职责包括：
1. **需求分析**：深入理解用户需求，识别核心功能和边界条件
2. **技术规划**：基于需求制定清晰的技术实现路径
3. **风险评估**：识别潜在的技术风险和用户体验问题
4. **协调沟通**：与工程师和其他团队成员进行有效沟通

当接到开发任务时，请按以下结构进行分析：
1. 需求理解与分析
2. 功能模块划分
3. 技术选型建议
4. 实现优先级排序
5. 验收标准定义

请简洁明了地回应。"""

    return AssistantAgent(
        name="ProductManager",
        model_client=model_client,
        system_message=system_message,
    )

def create_engineer(model_client):
    """创建软件工程师智能体"""
    system_message = """你是一位资深的软件工程师，擅长 Python 开发和 Web 应用构建。

【协作协议】
你只在最近三条消息中任意一条包含以下任一标记时输出有效内容：
- NEXT:TO_ENGINEER
- DECISION:BACK_TO_ENGINEER
- QA:FAILED

如果不满足条件，只回复：SKIP

完成代码后，最后一行必须追加：NEXT:TO_REVIEW

你的技术专长包括：
1. **Python 编程**：熟练掌握 Python 语法和最佳实践
2. **Web 开发**：精通 Streamlit、Flask、Django 等框架
3. **API 集成**：有丰富的第三方 API 集成经验
4. **错误处理**：注重代码的健壮性和异常处理

当收到开发任务时，请：
1. 仔细分析技术需求
2. 选择合适的技术方案
3. 编写完整的代码实现
4. 提供关键实现说明（简洁）
5. 考虑边界情况和异常处理

请提供完整的可运行代码。"""

    return AssistantAgent(
        name="Engineer",
        model_client=model_client,
        system_message=system_message,
    )

def create_code_reviewer(model_client):
    """创建代码审查员智能体"""
    system_message = """你是一位经验丰富的代码审查专家，专注于代码质量和最佳实践。

【协作协议】
你只在最近三条消息中任意一条包含 NEXT:TO_REVIEW 时输出有效内容。
如果不满足条件，只回复：SKIP

你必须在审查结尾给出一个且仅一个决策标记：
- DECISION:BACK_TO_PM      （需求理解有偏差，需要回退到产品经理）
- DECISION:BACK_TO_ENGINEER（需求没问题，但代码需修复）
- DECISION:TO_QA           （代码可进入测试）

你的审查重点包括：
1. **代码质量**：检查代码的可读性、可维护性和性能
2. **安全性**：识别潜在的安全漏洞和风险点
3. **最佳实践**：确保代码遵循行业标准和最佳实践
4. **错误处理**：验证异常处理的完整性和合理性

审查流程：
1. 仔细阅读和理解代码逻辑
2. 检查代码规范和最佳实践
3. 识别潜在问题和改进点
4. 提供具体的修改建议
5. 评估代码的整体质量

请提供具体、可执行的审查意见。"""

    return AssistantAgent(
        name="CodeReviewer",
        model_client=model_client,
        system_message=system_message,
    )

def create_quality_assurance(model_client):
    """创建测试工程师（QA）智能体"""
    system_message = """你是一位测试工程师（Quality Assurance），负责在代码审查通过后执行测试验证。

【协作协议】
你只在最近三条消息中任意一条包含 DECISION:TO_QA 时输出有效内容。
如果不满足条件，只回复：SKIP

测试步骤（轻量化）：
1. 生成功能测试清单（核心功能、异常处理、边界情况）
2. 说明可执行的测试方法（手动/自动）
3. 给出测试结论

结论标记（二选一，且必须在最后一行输出）：
- QA:FAILED  （测试未通过，回退工程师修复）
- QA:PASSED TERMINATE （测试通过，终止流程）
"""

    return AssistantAgent(
        name="QualityAssurance",
        model_client=model_client,
        system_message=system_message,
    )

async def run_software_development_team():
    """运行软件开发团队协作"""
    
    print("🔧 正在初始化模型客户端...")
    
    # 先使用标准的 OpenAI 客户端测试
    model_client = create_openai_model_client()
    
    print("👥 正在创建智能体团队...")
    
    # 创建智能体团队
    product_manager = create_product_manager(model_client)
    engineer = create_engineer(model_client)
    code_reviewer = create_code_reviewer(model_client)
    quality_assurance = create_quality_assurance(model_client)
    
    # 添加终止条件
    termination = TextMentionTermination("TERMINATE")
    
    # 创建团队聊天
    team_chat = RoundRobinGroupChat(
        participants=[
            product_manager,
            engineer,
            code_reviewer,
            quality_assurance,
        ],
        termination_condition=termination,
        max_turns=24,
    )
    
    # 定义开发任务
    task = """我们需要开发一个比特币价格显示应用，具体要求如下：

核心功能：
- 实时显示比特币当前价格（USD）
- 显示24小时价格变化趋势（涨跌幅和涨跌额）
- 提供价格刷新功能

技术要求：
- 使用 Streamlit 框架创建 Web 应用
- 界面简洁美观，用户友好
- 添加适当的错误处理和加载状态

请团队协作完成这个任务，从需求分析到最终实现。

协作要求（必须遵守）：
- 按照控制标记推进：NEXT:/DECISION:/QA:
- 如需回退，严格使用 DECISION:BACK_TO_PM 或 DECISION:BACK_TO_ENGINEER
- 只在满足本角色触发条件时输出实质内容，否则回复 SKIP"""
    
    # 执行团队协作
    print("🚀 启动 AutoGen 软件开发团队协作...")
    print("=" * 60)
    
    # 使用 Console 来显示对话过程
    result = await Console(team_chat.run_stream(task=task))
    
    print("\n" + "=" * 60)
    print("✅ 团队协作完成！")
    
    return result

# 主程序入口
if __name__ == "__main__":
    try:
        # 运行异步协作流程
        result = asyncio.run(run_software_development_team())
        
        print(f"\n📋 协作结果摘要：")
        print(f"- 参与智能体数量：4个（含QA）")
        print(f"- 任务完成状态：{'成功' if result else '需要进一步处理'}")
        
    except ValueError as e:
        print(f"❌ 配置错误：{e}")
        print("请检查 .env 文件中的配置是否正确")
    except Exception as e:
        print(f"❌ 运行错误：{e}")
        import traceback
        traceback.print_exc()



