# HW

## 1
对比AutoGen与langgraph

1、协作模式：AutoGen是多agent协作，Langgraph是单agent

2、控制方式：AutoGen通过角色设定和消息传递来控制agent之间的交互，Langgraph通过配置和状态管理来控制agent的行为。

3、适用场景：AutoGen适用于多agent协同的场景，langgraph适用于？


## 2
动态回退支持：
可以不改变轮询的机制，但是引入“跳过”的逻辑。设置产品经理在确认无误后，返回的消息最后要是[state]:"approve" or "disapprove“,如果后面的agent看到了"disapprove",就会直接跳过，但是工程师agent不会跳过

例如告诉测试工程师：“你只在最近三条消息中任意一条包含 DECISION:TO_QA 时输出有效内容。
如果不满足条件，只回复：SKIP”

类似同步信号量机制


## 3
MsgHub的优势？不是很理解

消息驱动架构（如 MsgHub）相比传统函数调用的优势在于：
解耦：发送方和接收方不直接依赖，便于扩展和维护。
异步：消息可以异步处理，提高系统吞吐量和响应速度。
可扩展性：易于横向扩展，适合分布式和微服务架构。
容错性：消息可持久化，系统部分故障时消息不丢失。

分布式部署，可以使用消息队列Kafka和RabbitMQ
【RabbitMQ是什么？架构是怎么样的？】 https://www.bilibili.com/video/BV1oCwEeVEe4/?share_source=copy_web&vd_source=ab81012dac4e8d6080049f3146a62e9f

## 4
添加一个只负责测试验收的agent，以解决分歧

AutoGen像一个圆桌会议，协作是“聊”出来的（涌现）

而CAMEL像一个成熟的工作室，有拆解任务、分工的agent，有执行任务的agent，整体的可控性更强，效率也许更高。

## 5
添加条件分支边
'''    workflow.add_conditional_edges(
        from_node="reflect",
        condition_fn=should_continue,
        edges={
            "end": END,       # 反思评估 → 结束
            "retry": "understand" # 反思评估 → 重新生成答案
        }
    )
'''

## 6
A：Agentscope

AgentScope 是唯一专注于生产级工程化的框架，完美匹配此场景：

分布式架构原生支持：AgentScope 设计之初就考虑了分布式部署，智能体可以运行在不同服务器上，天然支持水平扩展。

高并发处理能力：通过消息中心（MsgHub）异步消息机制，可以同时处理大量用户请求而不阻塞。

容错与稳定性：内置容错机制，单个智能体失败不会影响整个系统，满足 7×24 运行要求。

性能优化：相比对话式框架（AutoGen/CAMEL）的多轮交互开销，AgentScope 可以针对客服场景做流程优化，确保低延迟。

不选其他框架的原因：

AutoGen/CAMEL：更适合研究和原型阶段，缺少生产级的并发、分布式、监控能力。
LangGraph：虽然流程清晰，但缺少分布式和高并发的架构支持。

B：CAMEL

C：langgraph