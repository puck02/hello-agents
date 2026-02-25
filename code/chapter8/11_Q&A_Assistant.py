#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能文档问答助手 - 基于HelloAgents的智能文档问答系统

这是一个完整的PDF学习助手应用，支持：
- 加载PDF文档并构建知识库
- 智能问答（基于RAG）
- 学习历程记录（基于Memory）
- 学习回顾和报告生成
"""

from dotenv import load_dotenv
load_dotenv()
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import gradio as gr
import uuid
import re
import math
from hello_agents import HelloAgentsLLM

# ── MemoryTool 实现（hello-agents 0.1.1 尚未内置，此处自行实现）──
class MemoryTool:
    """四种记忆类型的统一管理工具，模拟人类认知记忆系统（纯 Python 实现）。"""
    WORKING_CAPACITY = 50

    def __init__(self, user_id: str, memory_types: list = None):
        self.user_id      = user_id
        self.memory_types = memory_types or ["working", "episodic", "semantic", "perceptual"]
        self._stores: dict = {t: [] for t in self.memory_types}

    def run(self, params: dict) -> str:
        action = params.get("action", "")
        return {
            "add":         self._add,
            "search":      self._search,
            "summary":     self._summary,
            "stats":       self._stats,
            "update":      self._update,
            "remove":      self._remove,
            "forget":      self._forget,
            "consolidate": self._consolidate,
            "clear_all":   self._clear_all,
        }.get(action, lambda p: f"❌ 未知操作: {action}")(params)

    def _add(self, p):
        mtype = p.get("memory_type", "working")
        if mtype not in self._stores:
            return f"❌ 记忆类型 '{mtype}' 未初始化"
        record = {
            "id": str(uuid.uuid4())[:8],
            "content": p.get("content", ""),
            "memory_type": mtype,
            "importance": float(p.get("importance", 0.5)),
            "created_at": time.time(),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        for k, v in p.items():
            if k not in ("action", "content", "memory_type", "importance"):
                record[k] = v
        store = self._stores[mtype]
        if mtype == "working" and len(store) >= self.WORKING_CAPACITY:
            store.sort(key=lambda x: x["importance"])
            store.pop(0)
        store.append(record)
        return f"✅ 已存入{mtype}记忆 [id={record['id']}，重要性={record['importance']}]"

    def _tfidf_score(self, query, text):
        q_words = set(re.findall(r'\w+', query.lower()))
        t_words = re.findall(r'\w+', text.lower())
        if not t_words:
            return 0.0
        return sum(1 for w in t_words if w in q_words) / len(t_words)

    def _search(self, p):
        query, mtype, limit = p.get("query", ""), p.get("memory_type"), int(p.get("limit", 5))
        stores = [self._stores[mtype]] if mtype and mtype in self._stores else list(self._stores.values())
        candidates = []
        for store in stores:
            for rec in store:
                score = self._tfidf_score(query, rec["content"]) + rec["importance"] * 0.2
                candidates.append((score, rec))
        top = sorted(candidates, key=lambda x: -x[0])[:limit]
        if not top:
            return "未找到相关记忆"
        return "\n".join(
            f"[{r['memory_type']}] {r['content'][:80]}（重要性={r['importance']}, 相关度={s:.3f}）"
            for s, r in top)

    def _summary(self, p):
        limit = int(p.get("limit", 10))
        lines = [f"📋 用户 {self.user_id} 的记忆摘要："]
        for mtype, store in self._stores.items():
            recent = sorted(store, key=lambda x: -x["created_at"])[:limit]
            lines.append(f"\n  [{mtype}] 共 {len(store)} 条，最近 {len(recent)} 条：")
            for r in recent:
                lines.append(f"    · {r['content'][:60]}")
        return "\n".join(lines)

    def _stats(self, p):
        total = sum(len(s) for s in self._stores.values())
        lines = [f"📊 记忆统计 (user={self.user_id})  总计: {total} 条"]
        for mtype, store in self._stores.items():
            avg = (sum(r["importance"] for r in store) / len(store)) if store else 0
            lines.append(f"  {mtype:12s}: {len(store):3d} 条  平均重要性={avg:.2f}")
        return "\n".join(lines)

    def _update(self, p):
        rid = p.get("id")
        for store in self._stores.values():
            for rec in store:
                if rec["id"] == rid:
                    rec.update({k: v for k, v in p.items() if k not in ("action", "id")})
                    return f"✅ 记忆 [id={rid}] 已更新"
        return f"❌ 未找到 id={rid}"

    def _remove(self, p):
        rid = p.get("id")
        for key, store in self._stores.items():
            for rec in store:
                if rec["id"] == rid:
                    store.remove(rec)
                    return f"✅ 已从 {key} 删除 [id={rid}]"
        return f"❌ 未找到 id={rid}"

    def _forget(self, p):
        thr = float(p.get("importance_threshold", 0.4))
        removed = 0
        for key, store in self._stores.items():
            before = len(store)
            self._stores[key] = [r for r in store if r["importance"] >= thr]
            removed += before - len(self._stores[key])
        return f"✅ 已遗忘 {removed} 条重要性 < {thr} 的记忆"

    def _consolidate(self, p):
        src, tgt = p.get("source_type", "working"), p.get("target_type", "episodic")
        thr = float(p.get("importance_threshold", 0.7))
        if src not in self._stores or tgt not in self._stores:
            return "❌ 记忆类型不存在"
        count = 0
        for rec in self._stores[src]:
            if rec["importance"] >= thr:
                new = {**rec, "id": str(uuid.uuid4())[:8], "memory_type": tgt,
                       "importance": min(1.0, rec["importance"] * 1.1), "consolidated_from": src}
                self._stores[tgt].append(new)
                count += 1
        return f"✅ 已将 {count} 条 {src} 记忆（重要性>={thr}）整合到 {tgt}"

    def _clear_all(self, p):
        for key in self._stores:
            self._stores[key] = []
        return "✅ 所有记忆已清空"


# ── RAGTool 实现（hello-agents 0.1.1 尚未内置，此处自行实现）──
class RAGTool:
    """检索增强生成工具：文档管道 → TF-IDF 检索 → LLM 问答。"""

    def __init__(self, knowledge_base_path: str = "./rag_kb", rag_namespace: str = "default"):
        from pathlib import Path
        self.kb_path   = Path(knowledge_base_path)
        self.namespace = rag_namespace
        self.kb_path.mkdir(parents=True, exist_ok=True)
        self._chunks: list = []
        self._vocab:  dict = {}
        self._idf:    dict = {}
        self._tfidf_matrix: list = []
        self._load_index()

    def run(self, params: dict) -> str:
        action = params.get("action", "")
        dispatch = {
            "add_document": self._add_document,
            "search":       self._search,
            "query":        self._query,
            "ask":          self._query,   # 兼容 action="ask" 的调用方式
            "status":       self._status,
            "stats":        self._status,  # 兼容 action="stats"
        }
        fn = dispatch.get(action)
        if not fn:
            return f"❌ 未知操作: {action}"
        return fn(params)

    def _add_document(self, p: dict) -> str:
        from pathlib import Path
        file_path = p.get("file_path", "")
        metadata  = p.get("metadata", {})
        if not file_path or not Path(file_path).exists():
            return f"❌ 文件不存在: {file_path}"
        text = self._read_file(file_path)
        chunks = self._chunk_text(text)
        source = Path(file_path).name
        for chunk in chunks:
            self._chunks.append({"id": str(uuid.uuid4())[:8], "text": chunk,
                                  "metadata": metadata, "source": source})
        self._build_index()
        self._save_index()
        return f"✅ 已添加 {len(chunks)} 个分块 (来源: {source}，总块数: {len(self._chunks)})"

    def _search(self, p: dict) -> str:
        query = p.get("query", "") or p.get("question", "")
        top_k = int(p.get("top_k", p.get("limit", 3)))
        if not self._chunks:
            return "知识库为空，请先添加文档"
        scores = self._cosine_scores(query)
        top = sorted(scores, key=lambda x: -x[1])[:top_k]
        if not top:
            return "未找到相关内容"
        lines = []
        for rank, (idx, score) in enumerate(top, 1):
            chunk = self._chunks[idx]
            lines.append(f"[{rank}] 来源: {chunk['source']}  相关度: {score:.3f}\n    {chunk['text'][:200]}")
        return "\n\n".join(lines)

    def _query(self, p: dict) -> str:
        query = p.get("query", "") or p.get("question", "")
        context_str = self._search(p)
        try:
            llm = HelloAgentsLLM()
            prompt = (f"请根据以下参考资料回答问题，如资料中没有相关信息请如实说明。\n\n"
                      f"参考资料：\n{context_str}\n\n问题：{query}")
            return llm.invoke([{"role": "user", "content": prompt}])
        except Exception as e:
            return f"[LLM 不可用，以下为检索结果]\n{context_str}\n\n(LLM 错误: {e})"

    def _status(self, p: dict) -> str:
        from collections import defaultdict
        sources = defaultdict(int)
        for c in self._chunks:
            sources[c["source"]] += 1
        lines = [f"📊 RAGTool 状态 (namespace={self.namespace})",
                 f"  总块数: {len(self._chunks)}", f"  词汇量: {len(self._vocab)}", "  已索引文件："]
        for src, cnt in sources.items():
            lines.append(f"    · {src}  ({cnt} 块)")
        return "\n".join(lines)

    def _read_file(self, path: str) -> str:
        import pathlib
        suffix = pathlib.Path(path).suffix.lower()
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(path)
                pages = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return "\n\n".join(pages)
            except ImportError:
                pass  # fall back to binary read
            except Exception as e:
                return f"[PDF读取错误: {e}]"
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _chunk_text(self, text: str, max_len: int = 300) -> list:
        paragraphs = re.split(r'\n{2,}', text.strip())
        chunks = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            while len(para) > max_len:
                chunks.append(para[:max_len])
                para = para[max_len:]
            if para:
                chunks.append(para)
        return chunks or [text[:max_len]]

    def _tokenize(self, text: str) -> list:
        return re.findall(r'\w+', text.lower())

    def _build_index(self):
        from collections import defaultdict
        N = len(self._chunks)
        if N == 0:
            return
        df: dict = defaultdict(int)
        chunk_tokens = []
        for chunk in self._chunks:
            toks = self._tokenize(chunk["text"])
            chunk_tokens.append(toks)
            for t in set(toks):
                df[t] += 1
        self._vocab = {t: i for i, t in enumerate(df.keys())}
        self._idf = {t: math.log((N + 1) / (cnt + 1)) + 1 for t, cnt in df.items()}
        self._tfidf_matrix = []
        for toks in chunk_tokens:
            from collections import defaultdict as dd
            tf: dict = dd(float)
            for t in toks:
                tf[t] += 1
            total = len(toks) or 1
            self._tfidf_matrix.append({t: (cnt / total) * self._idf.get(t, 1) for t, cnt in tf.items()})

    def _cosine_scores(self, query: str) -> list:
        from collections import defaultdict
        q_toks = self._tokenize(query)
        q_tf: dict = defaultdict(float)
        for t in q_toks:
            q_tf[t] += 1
        total = len(q_toks) or 1
        q_vec = {t: (cnt / total) * self._idf.get(t, 1) for t, cnt in q_tf.items()}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1
        results = []
        for idx, doc_vec in enumerate(self._tfidf_matrix):
            dot = sum(q_vec.get(t, 0) * v for t, v in doc_vec.items())
            d_norm = math.sqrt(sum(v * v for v in doc_vec.values())) or 1
            results.append((idx, dot / (q_norm * d_norm)))
        return results

    def _index_file(self):
        return self.kb_path / f"{self.namespace}_index.json"

    def _save_index(self):
        with open(self._index_file(), "w", encoding="utf-8") as f:
            json.dump(self._chunks, f, ensure_ascii=False)

    def _load_index(self):
        fp = self._index_file()
        if fp.exists():
            with open(fp, encoding="utf-8") as f:
                self._chunks = json.load(f)
            if self._chunks:
                self._build_index()

class PDFLearningAssistant:
    """智能文档问答助手"""

    def __init__(self, user_id: str = "default_user"):
        """初始化学习助手

        Args:
            user_id: 用户ID，用于隔离不同用户的数据
        """
        self.user_id = user_id
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 初始化工具
        self.memory_tool = MemoryTool(user_id=user_id)
        self.rag_tool = RAGTool(rag_namespace=f"pdf_{user_id}")

        # 学习统计
        self.stats = {
            "session_start": datetime.now(),
            "documents_loaded": 0,
            "questions_asked": 0,
            "concepts_learned": 0
        }

        # 当前加载的文档
        self.current_document = None

    def load_document(self, pdf_path: str) -> Dict[str, Any]:
        """加载PDF文档到知识库

        Args:
            pdf_path: PDF文件路径

        Returns:
            Dict: 包含success和message的结果
        """
        if not os.path.exists(pdf_path):
            return {"success": False, "message": f"文件不存在: {pdf_path}"}

        start_time = time.time()

        try:
            # 使用RAG工具处理PDF
            result = self.rag_tool.run({
                "action":"add_document",
                "file_path":pdf_path,
                "chunk_size":1000,
                "chunk_overlap":200
            })

            process_time = time.time() - start_time

            # RAG工具返回的是字符串消息
            self.current_document = os.path.basename(pdf_path)
            self.stats["documents_loaded"] += 1

            # 记录到学习记忆
            self.memory_tool.run({
                "action":"add",
                "content":f"加载了文档《{self.current_document}》",
                "memory_type":"episodic",
                "importance":0.9,
                "event_type":"document_loaded",
                "session_id":self.session_id
            })

            return {
                "success": True,
                "message": f"加载成功！(耗时: {process_time:.1f}秒)",
                "document": self.current_document
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"加载失败: {str(e)}"
            }

    def ask(self, question: str, use_advanced_search: bool = True) -> str:
        """向文档提问

        Args:
            question: 用户问题
            use_advanced_search: 是否使用高级检索（MQE + HyDE）

        Returns:
            str: 答案
        """
        if not self.current_document:
            return "⚠️ 请先加载文档！使用 load_document() 方法加载PDF文档。"

        # 记录问题到工作记忆
        self.memory_tool.run({
            "action":"add",
            "content":f"提问: {question}",
            "memory_type":"working",
            "importance":0.6,
            "session_id":self.session_id
        })

        # 使用RAG检索答案
        answer = self.rag_tool.run({
            "action":"ask",
            "question":question,
            "limit":5,
            "enable_advanced_search":use_advanced_search,
            "enable_mqe":use_advanced_search,
            "enable_hyde":use_advanced_search
        })

        # 记录到情景记忆
        self.memory_tool.run({
            "action":"add",
            "content":f"关于'{question}'的学习",
            "memory_type":"episodic",
            "importance":0.7,
            "event_type":"qa_interaction",
            "session_id":self.session_id
        })

        self.stats["questions_asked"] += 1

        return answer

    def add_note(self, content: str, concept: Optional[str] = None):
        """添加学习笔记

        Args:
            content: 笔记内容
            concept: 相关概念（可选）
        """
        self.memory_tool.run({
            "action":"add",
            "content":content,
            "memory_type":"semantic",
            "importance":0.8,
            "concept":concept or "general",
            "session_id":self.session_id
        })

        self.stats["concepts_learned"] += 1

    def recall(self, query: str, limit: int = 5) -> str:
        """回顾学习历程

        Args:
            query: 查询关键词
            limit: 返回结果数量

        Returns:
            str: 相关记忆
        """
        result = self.memory_tool.run({
            "action":"search",
            "query":query,
            "limit":limit
        })
        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取学习统计

        Returns:
            Dict: 统计信息
        """
        duration = (datetime.now() - self.stats["session_start"]).total_seconds()

        return {
            "会话时长": f"{duration:.0f}秒",
            "加载文档": self.stats["documents_loaded"],
            "提问次数": self.stats["questions_asked"],
            "学习笔记": self.stats["concepts_learned"],
            "当前文档": self.current_document or "未加载"
        }

    def generate_report(self, save_to_file: bool = True) -> Dict[str, Any]:
        """生成学习报告

        Args:
            save_to_file: 是否保存到文件

        Returns:
            Dict: 学习报告
        """
        # 获取记忆摘要
        memory_summary = self.memory_tool.run({"action":"summary", "limit":10})

        # 获取RAG统计
        rag_stats = self.rag_tool.run({"action":"stats"})

        # 生成报告
        duration = (datetime.now() - self.stats["session_start"]).total_seconds()
        report = {
            "session_info": {
                "session_id": self.session_id,
                "user_id": self.user_id,
                "start_time": self.stats["session_start"].isoformat(),
                "duration_seconds": duration
            },
            "learning_metrics": {
                "documents_loaded": self.stats["documents_loaded"],
                "questions_asked": self.stats["questions_asked"],
                "concepts_learned": self.stats["concepts_learned"]
            },
            "memory_summary": memory_summary,
            "rag_status": rag_stats
        }

        # 保存到文件
        if save_to_file:
            report_file = f"learning_report_{self.session_id}.json"
            try:
                with open(report_file, 'w', encoding='utf-8') as f:
                    json.dump(report, f, ensure_ascii=False, indent=2, default=str)
                report["report_file"] = report_file
            except Exception as e:
                report["save_error"] = str(e)

        return report





def create_gradio_ui():
    """创建Gradio Web UI"""
    # 全局助手实例
    assistant_state = {"assistant": None}

    def init_assistant(user_id: str) -> str:
        """初始化助手"""
        if not user_id:
            user_id = "web_user"
        assistant_state["assistant"] = PDFLearningAssistant(user_id=user_id)
        return f"✅ 助手已初始化 (用户: {user_id})"

    def load_pdf(pdf_file) -> str:
        """加载PDF文件"""
        if assistant_state["assistant"] is None:
            return "❌ 请先初始化助手"

        if pdf_file is None:
            return "❌ 请上传PDF文件"

        # Gradio 5+/6+ type="filepath" 直接返回路径字符串
        pdf_path = pdf_file if isinstance(pdf_file, str) else pdf_file.name
        result = assistant_state["assistant"].load_document(pdf_path)

        if result["success"]:
            return f"✅ {result['message']}\n📄 文档: {result['document']}"
        else:
            return f"❌ {result['message']}"

    def chat(message: str, history: List) -> Tuple[str, List]:
        """聊天功能"""
        if assistant_state["assistant"] is None:
            history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": "❌ 请先初始化助手并加载文档"}
            ]
            return "", history

        if not message.strip():
            return "", history

        # 判断是技术问题还是回顾问题
        if any(keyword in message for keyword in ["之前", "学过", "回顾", "历史", "记得"]):
            # 回顾学习历程
            response = assistant_state["assistant"].recall(message)
            response = f"🧠 **学习回顾**\n\n{response}"
        else:
            # 技术问答
            response = assistant_state["assistant"].ask(message)
            response = f"💡 **回答**\n\n{response}"

        history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response}
        ]
        return "", history

    def add_note_ui(note_content: str, concept: str) -> str:
        """添加笔记"""
        if assistant_state["assistant"] is None:
            return "❌ 请先初始化助手"

        if not note_content.strip():
            return "❌ 笔记内容不能为空"

        assistant_state["assistant"].add_note(note_content, concept or None)
        return f"✅ 笔记已保存: {note_content[:50]}..."

    def get_stats_ui() -> str:
        """获取统计信息"""
        if assistant_state["assistant"] is None:
            return "❌ 请先初始化助手"

        stats = assistant_state["assistant"].get_stats()
        result = "📊 **学习统计**\n\n"
        for key, value in stats.items():
            result += f"- **{key}**: {value}\n"
        return result

    def generate_report_ui() -> str:
        """生成报告"""
        if assistant_state["assistant"] is None:
            return "❌ 请先初始化助手"

        report = assistant_state["assistant"].generate_report(save_to_file=True)

        result = f"✅ 学习报告已生成\n\n"
        result += f"**会话信息**\n"
        result += f"- 会话时长: {report['session_info']['duration_seconds']:.0f}秒\n"
        result += f"- 加载文档: {report['learning_metrics']['documents_loaded']}\n"
        result += f"- 提问次数: {report['learning_metrics']['questions_asked']}\n"
        result += f"- 学习笔记: {report['learning_metrics']['concepts_learned']}\n"

        if "report_file" in report:
            result += f"\n💾 报告已保存至: {report['report_file']}"

        return result

    # 创建Gradio界面
    with gr.Blocks(title="智能文档问答助手") as demo:
        gr.Markdown("""
        # 📚 智能文档问答助手

        基于HelloAgents的智能文档问答系统，支持：
        - 📄 加载PDF文档并构建知识库
        - 💬 智能问答（基于RAG）
        - 📝 学习笔记记录
        - 🧠 学习历程回顾
        - 📊 学习报告生成
        """)

        with gr.Tab("🏠 开始使用"):
            with gr.Row():
                user_id_input = gr.Textbox(
                    label="用户ID",
                    placeholder="输入你的用户ID（可选，默认为web_user）",
                    value="web_user"
                )
                init_btn = gr.Button("初始化助手", variant="primary")

            init_output = gr.Textbox(label="初始化状态", interactive=False)
            init_btn.click(init_assistant, inputs=[user_id_input], outputs=[init_output])

            gr.Markdown("### 📄 加载PDF文档")
            pdf_upload = gr.File(
                label="上传PDF文件",
                file_types=[".pdf"],
                type="filepath"
            )
            load_btn = gr.Button("加载文档", variant="primary")
            load_output = gr.Textbox(label="加载状态", interactive=False)
            load_btn.click(load_pdf, inputs=[pdf_upload], outputs=[load_output])

        # 页面加载时自动初始化默认用户
        demo.load(init_assistant, inputs=[user_id_input], outputs=[init_output])

        with gr.Tab("💬 智能问答"):
            gr.Markdown("### 向文档提问或回顾学习历程")
            chatbot = gr.Chatbot(
                label="对话历史",
                height=400,
                type="messages"
            )
            with gr.Row():
                msg_input = gr.Textbox(
                    label="输入问题",
                    placeholder="例如：什么是Transformer？ 或 我之前学过什么？",
                    scale=4
                )
                send_btn = gr.Button("发送", variant="primary", scale=1)

            gr.Examples(
                examples=[
                    "什么是大语言模型？",
                    "Transformer架构有哪些核心组件？",
                    "如何训练大语言模型？",
                    "我之前学过什么内容？",
                    "回顾一下关于注意力机制的学习"
                ],
                inputs=msg_input
            )

            msg_input.submit(chat, inputs=[msg_input, chatbot], outputs=[msg_input, chatbot])
            send_btn.click(chat, inputs=[msg_input, chatbot], outputs=[msg_input, chatbot])

        with gr.Tab("📝 学习笔记"):
            gr.Markdown("### 记录学习心得和重要概念")
            note_content = gr.Textbox(
                label="笔记内容",
                placeholder="输入你的学习笔记...",
                lines=3
            )
            concept_input = gr.Textbox(
                label="相关概念（可选）",
                placeholder="例如：transformer, attention"
            )
            note_btn = gr.Button("保存笔记", variant="primary")
            note_output = gr.Textbox(label="保存状态", interactive=False)
            note_btn.click(add_note_ui, inputs=[note_content, concept_input], outputs=[note_output])

        with gr.Tab("📊 学习统计"):
            gr.Markdown("### 查看学习进度和统计信息")
            stats_btn = gr.Button("刷新统计", variant="primary")
            stats_output = gr.Markdown()
            stats_btn.click(get_stats_ui, outputs=[stats_output])

            gr.Markdown("### 生成学习报告")
            report_btn = gr.Button("生成报告", variant="primary")
            report_output = gr.Textbox(label="报告状态", interactive=False)
            report_btn.click(generate_report_ui, outputs=[report_output])

    return demo


def main():
    """主函数 - 启动Gradio Web UI"""
    print("\n" + "="*60)
    print("智能文档问答助手")
    print("="*60)
    print("正在启动Web界面...\n")

    demo = create_gradio_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        theme=gr.themes.Soft()
    )


if __name__ == "__main__":
    main()

