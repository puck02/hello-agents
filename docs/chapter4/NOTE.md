# HW
## 1、
ReAct:thoght--action--observation循环直到thought认为结果满意

Plan-and-Solve:先让planner规划好步骤，再让solver逐个执行

reflection：对ReAct和Plan-and-Solve的结果进行review，提供优化建议。

智能家居应该用ReAct版的Reflection

当然可以组合使用，先用Plan-and-Solve规划好步骤，再在每个步骤中使用ReAct进行思考和行动，最后通过Reflection对整个过程进行回顾和优化。这种组合可以充分利用两者的优势，提高智能家居系统的效率和智能水平。

## 2
1. 当前正则解析的潜在脆弱性与失败场景
目前的正则解析（如 re.search(r"Action:\s*(.*?)$", ...)）非常类似于在 C++ 中直接使用 sscanf 或手动 strstr 扫描控制台缓冲区，其风险点在于：

格式随意性（Hallucination of Format）：LLM 可能会产生“幻觉”，将 Thought: 写成 Thinking: 或 Thought（少了冒号）。正则会因此完全失效，导致 thought 变量为 None。
Markdown 的干扰：LLM 极其喜欢用 Markdown。它可能会输出 Action: \``python Search["..."] ````，此时正则匹配到的字符串会包含多余的反引号，导致后续的工具名称提取失败。
输入嵌套问题：目前的 (\w+)\[(.*)\] 是贪婪匹配。如果 tool_input 本身包含方括号（例如查询代码或数学公式 Search[arr[0]]），正则会匹配错误。
多余解释：模型有时会在输出完 Action 后又忍不住加了一句“我这样做是因为...”。正则如果不小心把这句解释也抓进来，就会导致工具执行报错。
2. 更鲁棒的输出解析方案
除了正则表达式，业界主要有以下三种进阶方案：

JSON 格式化 (Structured JSON)：
方法：强制要求模型输出一段合法的 JSON 字符串。
类比：类似于从原始字符串扫描切换到了 nlohmann/json 这种序列化框架。通过定义 Schema（模式），我们可以利用成熟的 JSON 解析器进行健壮的校验。

函数调用 (Function Calling / Tool Calling)：
方法：这是目前 OpenAI/GitHub Models 等厂商提供的原生能力。
类比：类似于 RPC (远程过程调用) 或系统 API 调用。模型不再输出文本，而是输出一个结构化的指令包。

Pydantic 校验 (Model-driven Parsing)：
方法：结合 JSON，使用 Pydantic 库进行类型检查和业务规则验证。



## 3
设计概览

为 tools.py 接入了一个安全的 Calculator 工具，采用 ast 解析并映射有限算子，从而避免 eval 风险，可以处理括号、乘除、幂以及模运算，供 ReAct 智能体直接调用。
ReActAgent 增加了连续工具失败检测：每次检测到格式错误、工具不存在、异常或显式失败提示时递增计数；超过阈值后向 History 注入 System: 提示，要求模型重新核对工具与输入；一旦成功调用则重置计数，避免陷入误用循环。
思考题

当可用工具数量增长到 50+／100+ 时，当前把工具清单直接拼接到 prompt 的方式会导致提示冗长、LLM 难以快速匹配。工程上可以：
给每个工具加上结构化元数据（类别、关键字、能力标签）并维护可搜索的注册表，让工具选择先通过短语检索，再展示给模型。
引入能力检索层（比如 embedding 相似度、向量索引）把用户意图映射到最相关的工具子集，只在 prompt 中列出候选。
在工具执行器中支持分层组织（例如按功能模块或作用域）以及缓存最近使用的工具，优先展示给模型。

## 5

更智能的终止策略可以结合质量与动力学，比如：
改进幅度阈值：对比最近两轮反馈或结果的语义/数值差异，若变动低于阈值（例如 embedding 距离或关键评分提升 < ε）就终止。
自信度信号：让模型在每轮的 Thought/Action 中给出自评（“当前自信度为 0.92”），如果连续几轮都保持高值且没有负面反馈，说明已收敛。

## 7
采用ReAct+Plan-and-Solve+Reflection

