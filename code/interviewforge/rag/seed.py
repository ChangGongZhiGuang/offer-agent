"""灌库: 把种子题写入题库(原文) + 向量库(题干 embedding)。"""
from __future__ import annotations

from typing import Callable

from interviewforge.rag.chunking import embeddable_text
from interviewforge.rag.index_builder import metadata_for
from interviewforge.rag.question_bank import QuestionBank
from interviewforge.rag.types import Question
from interviewforge.rag.vector_store import VectorStore

SEED_QUESTIONS: list[Question] = [
    # ── 后端 / Redis ──
    Question(id="be-1", role="后端", topic="redis",
             stem="如何用 Redis 实现一个可靠的分布式锁?",
             answer="SETNX + 过期时间 + 唯一 value, 释放时校验 value, 可用 Redlock。", difficulty="hard"),
    Question(id="be-1b", role="后端", topic="redis",
             stem="Redis 的过期策略有哪些? 内存淘汰策略如何选择?",
             answer="定期删除 + 惰性删除; 淘汰策略有 allkeys-lru / volatile-lru / allkeys-random 等, 缓存场景常用 allkeys-lru。", difficulty="medium"),
    Question(id="be-1c", role="后端", topic="redis",
             stem="Redis 持久化方式 RDB 与 AOF 的区别及如何选型?",
             answer="RDB 快照, 恢复快但可能丢数据; AOF 追加日志, 数据安全但文件大; 生产常两者结合。", difficulty="medium"),
    # ── 后端 / MySQL ──
    Question(id="be-2", role="后端", topic="mysql",
             stem="MySQL 的聚簇索引和非聚簇索引有什么区别?",
             answer="聚簇索引叶子存整行数据, 非聚簇索引叶子存主键需回表。", difficulty="medium"),
    Question(id="be-2b", role="后端", topic="mysql",
             stem="MySQL 在高并发下如何避免死锁? 出现死锁后怎么排查?",
             answer="保持固定加锁顺序, 缩短事务, 用 SHOW ENGINE INNODB STATUS 查死锁日志, 必要时开 innodb_deadlock_detect。", difficulty="hard"),
    Question(id="be-2c", role="后端", topic="mysql",
             stem="EXPLAIN 输出的 type 列各值代表什么? 哪些值说明需要优化?",
             answer="从好到差: system>const>eq_ref>ref>range>index>ALL; range 以下通常需要优化索引。", difficulty="medium"),
    # ── 后端 / 并发 & 高并发 ──
    Question(id="be-3", role="后端", topic="并发",
             stem="什么是缓存击穿? 怎么缓解?",
             answer="热点 key 失效瞬间大量请求打到 DB; 用互斥锁/逻辑过期/永不过期缓解。", difficulty="medium"),
    Question(id="be-3b", role="后端", topic="高并发",
             stem="设计一个支持每秒 10 万 QPS 的秒杀系统, 请描述核心架构思路。",
             answer="前端限流→消息队列削峰→Redis 预扣库存→异步落库; 避免超卖用 Lua 原子扣减。", difficulty="hard"),
    Question(id="be-3c", role="后端", topic="并发",
             stem="Java 中 synchronized 与 ReentrantLock 有何区别? 各自适用场景?",
             answer="synchronized 自动释放, 适合简单场景; ReentrantLock 支持公平锁/超时/可中断, 适合复杂并发控制。", difficulty="medium"),
    # ── 后端 / 分布式 ──
    Question(id="be-4", role="后端", topic="分布式",
             stem="CAP 理论中 P (分区容忍) 为何通常是必选项? CP 与 AP 如何取舍?",
             answer="分布式系统网络分区不可避免; CP 保一致牺牲可用 (如 Zookeeper), AP 保可用牺牲强一致 (如 Eureka/Cassandra)。", difficulty="hard"),
    Question(id="be-4b", role="后端", topic="分布式",
             stem="如何保证分布式系统中接口的幂等性?",
             answer="唯一请求 ID + 数据库唯一索引/Redis setnx 去重; 状态机设计只允许单向流转。", difficulty="medium"),
    # ── 算法 ──
    Question(id="algo-1", role="算法", topic="动态规划",
             stem="如何用动态规划求最长递增子序列?",
             answer="dp[i]=以 i 结尾的 LIS 长度; O(n^2) 或贪心+二分 O(n log n)。", difficulty="medium"),
    Question(id="algo-2", role="算法", topic="动态规划",
             stem="背包问题 0/1 背包与完全背包的 DP 转移方程分别是什么?",
             answer="0/1: dp[j]=max(dp[j], dp[j-w]+v), 逆序遍历; 完全: 正序遍历。", difficulty="medium"),
    Question(id="algo-3", role="算法", topic="图算法",
             stem="Dijkstra 算法的时间复杂度是多少? 为什么不能处理负权边?",
             answer="优先队列版 O((V+E)logV); 负权边会使已确定最短路的节点被更新, 破坏贪心假设。", difficulty="hard"),
    # ── 前端 ──
    Question(id="fe-1", role="前端", topic="vue",
             stem="Vue 3 中 ref 与 reactive 的区别是什么? 分别在什么场景下使用?",
             answer="ref 包装单值(原始类型/对象均可), 通过 .value 访问; reactive 只包装对象, 直接访问属性; 原始类型用 ref, 复杂对象两者皆可。", difficulty="medium"),
    Question(id="fe-2", role="前端", topic="性能优化",
             stem="前端白屏时间过长如何排查和优化?",
             answer="Chrome Performance/LCP 定位; 手段: 路由懒加载, 代码分割, CDN, 首屏 SSR/SSG, 资源预加载 prefetch/preload。", difficulty="hard"),
    Question(id="fe-3", role="前端", topic="javascript",
             stem="解释 JavaScript 事件循环 (Event Loop) 中宏任务与微任务的执行顺序。",
             answer="每轮 Tick: 执行一个宏任务 → 清空微任务队列 (Promise.then/queueMicrotask) → 渲染 → 下一个宏任务。", difficulty="medium"),
]


def seed_questions(question_bank: QuestionBank, vector_store: VectorStore,
                   embedder: Callable[[list[str]], list[list[float]]],
                   questions: list[Question] | None = None) -> int:
    questions = questions if questions is not None else SEED_QUESTIONS
    texts = [embeddable_text(q) for q in questions]   # 只题干
    embeddings = embedder(texts)
    for q in questions:
        question_bank.add(q)
    vector_store.add(
        ids=[q.id for q in questions],
        embeddings=embeddings,
        metadatas=[metadata_for(q) for q in questions],   # 单源构造, 与增量比对一致
    )
    return len(questions)
