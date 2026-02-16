"""
异步 vs 同步调用对比示例
演示为什么 AutoGen 需要使用异步
"""

import time
import asyncio

# ==================== 同步版本 ====================

def sync_task_1():
    """同步任务1：模拟 ProductManager 分析需求（耗时3秒）"""
    print("🎯 [同步] ProductManager 开始分析需求...")
    time.sleep(3)  # 模拟耗时操作（调用 LLM API）
    print("✅ [同步] ProductManager 分析完成")
    return "需求分析结果"

def sync_task_2():
    """同步任务2：模拟 Engineer 编写代码（耗时4秒）"""
    print("💻 [同步] Engineer 开始编写代码...")
    time.sleep(4)  # 模拟耗时操作
    print("✅ [同步] Engineer 代码完成")
    return "代码实现"

def sync_task_3():
    """同步任务3：模拟 CodeReviewer 审查（耗时2秒）"""
    print("🔍 [同步] CodeReviewer 开始审查...")
    time.sleep(2)  # 模拟耗时操作
    print("✅ [同步] CodeReviewer 审查完成")
    return "审查报告"

def run_sync_workflow():
    """同步执行工作流"""
    print("\n" + "="*60)
    print("📌 同步执行模式：一个接一个执行")
    print("="*60)
    
    start_time = time.time()
    
    # 按顺序执行，每个任务必须等待前一个完成
    result1 = sync_task_1()  # 等待 3 秒
    result2 = sync_task_2()  # 等待 4 秒
    result3 = sync_task_3()  # 等待 2 秒
    
    total_time = time.time() - start_time
    print(f"\n⏱️  总耗时：{total_time:.1f} 秒")
    print(f"特点：主线程被阻塞，什么都不能做\n")

# ==================== 异步版本 ====================

async def async_task_1():
    """异步任务1：模拟 ProductManager 分析需求（耗时3秒）"""
    print("🎯 [异步] ProductManager 开始分析需求...")
    await asyncio.sleep(3)  # 模拟耗时操作（非阻塞）
    print("✅ [异步] ProductManager 分析完成")
    return "需求分析结果"

async def async_task_2():
    """异步任务2：模拟 Engineer 编写代码（耗时4秒）"""
    print("💻 [异步] Engineer 开始编写代码...")
    await asyncio.sleep(4)  # 模拟耗时操作（非阻塞）
    print("✅ [异步] Engineer 代码完成")
    return "代码实现"

async def async_task_3():
    """异步任务3：模拟 CodeReviewer 审查（耗时2秒）"""
    print("🔍 [异步] CodeReviewer 开始审查...")
    await asyncio.sleep(2)  # 模拟耗时操作（非阻塞）
    print("✅ [异步] CodeReviewer 审查完成")
    return "审查报告"

async def run_async_workflow():
    """异步执行工作流"""
    print("\n" + "="*60)
    print("📌 异步执行模式：可以并发执行（如果允许）")
    print("="*60)
    
    start_time = time.time()
    
    # 方式1：顺序执行（和同步一样的效果）
    # result1 = await async_task_1()
    # result2 = await async_task_2()
    # result3 = await async_task_3()
    
    # 方式2：并发执行（如果任务之间没有依赖）
    # 注意：AutoGen 的实际场景是顺序的，这里只是展示异步的能力
    results = await asyncio.gather(
        async_task_1(),
        async_task_2(),
        async_task_3()
    )
    
    total_time = time.time() - start_time
    print(f"\n⏱️  总耗时：{total_time:.1f} 秒")
    print(f"特点：非阻塞，可以做其他事情（如显示进度）\n")

# ==================== AutoGen 实际场景 ====================

async def autogen_style_workflow():
    """
    AutoGen 实际使用场景：顺序执行但非阻塞
    虽然任务是顺序的，但使用异步有这些好处：
    """
    print("\n" + "="*60)
    print("📌 AutoGen 实际场景：顺序但非阻塞")
    print("="*60)
    
    start_time = time.time()
    
    # ProductManager 分析（必须先完成）
    print("🎯 ProductManager 开始分析需求...")
    await asyncio.sleep(3)  # 在等待 API 响应时，程序不会卡死
    print("✅ ProductManager 分析完成")
    
    # Engineer 实现（依赖 ProductManager 的结果）
    print("💻 Engineer 开始编写代码...")
    await asyncio.sleep(4)  # 可以实时显示进度
    print("✅ Engineer 代码完成")
    
    # CodeReviewer 审查（依赖 Engineer 的代码）
    print("🔍 CodeReviewer 开始审查...")
    await asyncio.sleep(2)  # UI 可以响应用户操作
    print("✅ CodeReviewer 审查完成")
    
    total_time = time.time() - start_time
    print(f"\n⏱️  总耗时：{total_time:.1f} 秒")
    print(f"优势：")
    print(f"  ✓ 可以实时显示对话过程（Console 流式输出）")
    print(f"  ✓ 程序不会假死，用户体验更好")
    print(f"  ✓ 可以随时取消操作")
    print(f"  ✓ 支持多个团队同时工作\n")

# ==================== 关键区别演示 ====================

def blocking_example():
    """同步阻塞示例"""
    print("\n" + "="*60)
    print("❌ 同步模式的问题演示")
    print("="*60)
    print("开始执行耗时操作...")
    time.sleep(3)  # 在这3秒内，整个程序完全卡住
    print("操作完成")
    print("问题：在等待期间，无法做任何事情！\n")

async def non_blocking_example():
    """异步非阻塞示例"""
    print("\n" + "="*60)
    print("✅ 异步模式的优势演示")
    print("="*60)
    print("开始执行耗时操作...")
    
    # 创建一个后台任务
    task = asyncio.create_task(asyncio.sleep(3))
    
    # 在等待期间可以做其他事情
    for i in range(3):
        await asyncio.sleep(1)
        print(f"  进度更新 {i+1}/3 - 可以显示进度条！")
    
    await task
    print("操作完成")
    print("优势：可以实时显示进度，响应用户操作！\n")

# ==================== 主程序 ====================

def main():
    """运行所有对比示例"""
    print("\n" + "🔬 异步 vs 同步对比演示" + "\n")
    
    # 1. 同步阻塞问题
    blocking_example()
    
    # 2. 异步非阻塞优势
    asyncio.run(non_blocking_example())
    
    # 3. 同步工作流
    run_sync_workflow()
    
    # 4. 异步工作流（并发）
    asyncio.run(run_async_workflow())
    
    # 5. AutoGen 实际场景
    asyncio.run(autogen_style_workflow())
    
    print("\n" + "="*60)
    print("📝 总结")
    print("="*60)
    print("""
在 AutoGen 中使用异步的原因：

1. **流式输出** 🌊
   - await Console(team_chat.run_stream(task=task))
   - 可以实时看到每个智能体的对话
   - 同步模式只能等全部完成才显示

2. **非阻塞** ⚡
   - 等待 LLM API 响应时（可能很慢）
   - 程序不会卡死，可以响应用户操作
   - 可以显示"正在思考..."的提示

3. **可扩展** 🚀
   - 未来可以支持多个团队同时工作
   - 可以并行处理独立的任务
   - 更容易集成到 Web 应用中

4. **API 设计** 🎨
   - AutoGen 的 run_stream() 本身就是异步的
   - 必须用 await 调用
   - 这是现代 Python 异步编程的标准做法
    """)

if __name__ == "__main__":
    main()
