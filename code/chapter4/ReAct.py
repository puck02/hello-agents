import re
from llm_client import HelloAgentsLLM
from tools import ToolExecutor, search, calculator

# (此处省略 REACT_PROMPT_TEMPLATE 的定义)
REACT_PROMPT_TEMPLATE = """
请注意，你是一个有能力调用外部工具的智能助手。

可用工具如下：
{tools}

请严格按照以下格式进行回应：

Thought: 你的思考过程，用于分析问题、拆解任务和规划下一步行动。
Action: 你决定采取的行动，必须是以下格式之一：
- `{{tool_name}}[{{tool_input}}]`：调用一个可用工具。
- `Finish[最终答案]`：当你认为已经获得最终答案时。
- 当你收集到足够的信息，能够回答用户的最终问题时，你必须在`Action:`字段后使用 `Finish[最终答案]` 来输出最终答案。


如果你在 History 中看到以 System: 开头的提示，说明系统检测到前几次调用工具失败，请结合已有观察重新确认工具选择及参数。

现在，请开始解决以下问题：
Question: {question}
History: {history}
"""

class ReActAgent:
    def __init__(self, llm_client: HelloAgentsLLM, tool_executor: ToolExecutor, max_steps: int = 5, max_tool_failures: int = 2):
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.max_steps = max_steps
        self.max_tool_failures = max_tool_failures
        self.tool_error_streak = 0
        self.history = []

    def run(self, question: str):
        self.history = []
        self._reset_failure_tracker()
        current_step = 0

        while current_step < self.max_steps:
            current_step += 1
            print(f"\n--- 第 {current_step} 步 ---")

            tools_desc = self.tool_executor.getAvailableTools()
            history_str = "\n".join(self.history)
            prompt = REACT_PROMPT_TEMPLATE.format(tools=tools_desc, question=question, history=history_str)

            messages = [{"role": "user", "content": prompt}]
            response_text = self.llm_client.think(messages=messages)
            if not response_text:
                print("错误：LLM未能返回有效响应。"); break

            thought, action = self._parse_output(response_text)
            if thought: print(f"🤔 思考: {thought}")
            if not action: print("警告：未能解析出有效的Action，流程终止。"); break
            
            if action.startswith("Finish"):
                # 如果是Finish指令，提取最终答案并结束
                final_answer = self._parse_action_input(action)
                print(f"🎉 最终答案: {final_answer}")
                return final_answer
            
            tool_name, tool_input = self._parse_action(action)
            if not tool_name or not tool_input:
                self.history.append("Observation: 无效的Action格式，请检查。")
                self._increment_failure_counter("无效的Action格式，请核对你的工具调用语法。")
                continue

            print(f"🎬 行动: {tool_name}[{tool_input}]")
            observation, tool_failed = self._execute_tool(tool_name, tool_input)
            print(f"👀 观察: {observation}")
            self.history.append(f"Action: {action}")
            self.history.append(f"Observation: {observation}")

            if tool_failed:
                self._increment_failure_counter(f"工具 '{tool_name}' 的调用返回失败结果。")
                continue

            self._reset_failure_tracker()

        print("已达到最大步数，流程终止。")
        return None

    def _parse_output(self, text: str):
        # Thought: 匹配到 Action: 或文本末尾
        thought_match = re.search(r"Thought:\s*(.*?)(?=\nAction:|$)", text, re.DOTALL)
        # Action: 匹配到文本末尾
        action_match = re.search(r"Action:\s*(.*?)$", text, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else None
        action = action_match.group(1).strip() if action_match else None
        return thought, action

    def _parse_action(self, action_text: str):
        match = re.match(r"(\w+)\[(.*)\]", action_text, re.DOTALL)
        return (match.group(1), match.group(2)) if match else (None, None)

    def _parse_action_input(self, action_text: str):
        match = re.match(r"\w+\[(.*)\]", action_text, re.DOTALL)
        return match.group(1) if match else ""

    def _execute_tool(self, tool_name: str, tool_input: str):
        tool_function = self.tool_executor.getTool(tool_name)
        if not tool_function:
            return f"错误：未找到名为 '{tool_name}' 的工具。", True
        try:
            raw_result = tool_function(tool_input)
        except Exception as exc:
            return f"工具执行异常: {exc}", True

        observation = raw_result if isinstance(raw_result, str) else str(raw_result)
        return observation, self._is_error_observation(observation)

    def _is_error_observation(self, observation: str) -> bool:
        normalized = observation.lower()
        error_markers = ("错误", "异常", "失败", "对不起", "未找到")
        return any(marker in normalized for marker in error_markers)

    def _increment_failure_counter(self, context: str):
        self.tool_error_streak += 1
        print(f"⚠️ {context}")
        if self.tool_error_streak >= self.max_tool_failures:
            guidance = (
                "System: 系统检测到你连续多次调用工具失败。"
                " 请根据已有观察，重新确认工具名称与输入参数，再选择下一步行动。"
            )
            print(guidance)
            self.history.append(guidance)
            self.tool_error_streak = 0

    def _reset_failure_tracker(self):
        self.tool_error_streak = 0

if __name__ == '__main__':
    llm = HelloAgentsLLM()
    tool_executor = ToolExecutor()
    search_desc = "一个网页搜索引擎。当你需要回答关于时事、事实以及在你的知识库中找不到的信息时，应使用此工具。"
    tool_executor.registerTool("Search", search_desc, search)
    calculator_desc = "一个安全的计算器工具，适用于带括号、多级运算和除法的数学问题。"
    tool_executor.registerTool("Calculator", calculator_desc, calculator)
    agent = ReActAgent(llm_client=llm, tool_executor=tool_executor)
    question = "华为最新的手机是哪一款？它的主要卖点是什么？"
    agent.run(question)
