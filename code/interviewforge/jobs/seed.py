"""岗位广场种子数据: 首次启动 (或内存模式每次启动) 灌入的示例岗位。

字段与前端原硬编码列表一一对应, 仅保留入库的基础字段
(category/title/company/salary/salary_min/city/exp/skills/requirements)。
logo / 匹配度等装饰元素由前端按规则现生成, 不在此列。
"""
from __future__ import annotations

SEED_JOBS: list[dict] = [
    # ───────── 后端 ─────────
    {
        "id": "j1", "category": "后端",
        "title": "资深后端工程师", "company": "云启科技 · 基础架构组 · D轮",
        "salary": "30-55K · 16薪", "salary_min": 30, "city": "上海", "exp": "3-5 年",
        "skills": ["Redis", "高并发", "分布式", "MySQL", "Go"],
        "requirements": [
            "5 年以上后端开发，主导过高并发系统设计",
            "精通 Redis 集群、缓存一致性与分布式锁",
            "深入理解 MySQL 索引/事务/分库分表",
            "有秒杀、订单等高 QPS 场景实战经验",
            "熟悉 Go 或 Java，了解微服务治理",
        ],
    },
    {
        "id": "j2", "category": "后端",
        "title": "后端开发工程师", "company": "数珩数据 · B轮",
        "salary": "25-45K", "salary_min": 25, "city": "北京", "exp": "3-5 年",
        "skills": ["Java", "Spring", "Kafka", "微服务"],
        "requirements": [
            "熟练 Java + Spring Boot/Cloud 微服务开发",
            "掌握 Kafka 消息队列与异步解耦",
            "理解服务注册发现、配置中心、链路追踪",
            "有大数据量 ETL 或数据平台经验加分",
        ],
    },
    {
        "id": "j3", "category": "后端",
        "title": "后端工程师 · Go 方向", "company": "极光出行 · 上市公司",
        "salary": "26-46K", "salary_min": 26, "city": "成都", "exp": "2-4 年",
        "skills": ["Go", "gRPC", "PostgreSQL", "K8s"],
        "requirements": [
            "熟练 Go，理解 goroutine/channel 并发模型",
            "有 gRPC 微服务与 Protobuf 经验",
            "掌握 PostgreSQL，了解索引与查询优化",
            "熟悉 Kubernetes 容器编排与 CI/CD",
        ],
    },
    {
        "id": "j7", "category": "后端",
        "title": "Java 高级工程师 · 交易", "company": "蜂享科技 · 已上市",
        "salary": "35-60K", "salary_min": 35, "city": "深圳", "exp": "5 年+",
        "skills": ["Java", "分布式事务", "高可用", "RocketMQ"],
        "requirements": [
            "5 年以上交易/支付系统后端经验",
            "掌握分布式事务（TCC/Saga/本地消息表）",
            "理解幂等、对账、资金安全设计",
            "熟悉 RocketMQ/Kafka 与最终一致性",
        ],
    },
    {
        "id": "j8", "category": "后端",
        "title": "初级后端工程师 · 校招", "company": "鲸跃网络 · A轮",
        "salary": "12-18K", "salary_min": 12, "city": "杭州", "exp": "应届/1 年",
        "skills": ["Java", "MySQL", "Spring", "Linux"],
        "requirements": [
            "计算机相关专业，扎实的数据结构与算法基础",
            "了解 Java 与 Spring 基础，写过完整 CRUD 项目",
            "熟悉 MySQL 基本使用与简单优化",
            "有较强学习能力与工程规范意识",
        ],
    },
    # ───────── 前端 ─────────
    {
        "id": "j5", "category": "前端",
        "title": "高级前端工程师", "company": "织云 · 远程友好",
        "salary": "28-50K", "salary_min": 28, "city": "远程", "exp": "3-5 年",
        "skills": ["React", "TypeScript", "性能优化"],
        "requirements": [
            "精通 React + TypeScript，理解 Hooks 与状态管理",
            "有大型 SPA 性能优化经验（首屏/懒加载/缓存）",
            "熟悉构建工具链 Vite/Webpack",
            "关注工程化、组件库与可维护性",
        ],
    },
    {
        "id": "j9", "category": "前端",
        "title": "Vue 前端工程师", "company": "澜图科技 · B轮",
        "salary": "20-38K", "salary_min": 20, "city": "上海", "exp": "2-4 年",
        "skills": ["Vue 3", "Pinia", "Vite", "可视化"],
        "requirements": [
            "熟练 Vue 3 组合式 API 与 Pinia 状态管理",
            "理解响应式原理与组件通信",
            "有数据可视化（ECharts/D3）经验加分",
            "注重交互细节与还原度",
        ],
    },
    {
        "id": "j10", "category": "前端",
        "title": "资深前端 · 中后台", "company": "匠云 SaaS · C轮",
        "salary": "32-55K", "salary_min": 32, "city": "北京", "exp": "5 年+",
        "skills": ["React", "微前端", "低代码", "Node"],
        "requirements": [
            "主导过中后台/低代码平台前端架构",
            "理解微前端（qiankun/Module Federation）",
            "有 Node.js BFF 层开发经验",
            "能从 0 搭建组件库与脚手架",
        ],
    },
    {
        "id": "j11", "category": "前端",
        "title": "前端工程师 · C 端", "company": "虹宇互娱 · 已上市",
        "salary": "18-32K", "salary_min": 18, "city": "广州", "exp": "2-4 年",
        "skills": ["小程序", "H5", "性能", "动效"],
        "requirements": [
            "熟悉微信小程序与 H5 跨端开发",
            "有 C 端高流量页面性能优化经验",
            "掌握 CSS 动效与交互实现",
            "关注首屏与弱网体验",
        ],
    },
    # ───────── 算法 ─────────
    {
        "id": "j4", "category": "算法",
        "title": "算法工程师 · 推荐", "company": "玄策 AI · C轮",
        "salary": "40-70K", "salary_min": 40, "city": "杭州", "exp": "硕士优先",
        "skills": ["推荐系统", "PyTorch", "召回排序"],
        "requirements": [
            "硕士优先，扎实的机器学习理论基础",
            "有推荐系统召回/排序模型落地经验",
            "熟练 PyTorch/TensorFlow",
            "理解特征工程与 A/B 实验",
        ],
    },
    {
        "id": "j12", "category": "算法",
        "title": "NLP 算法工程师 · 大模型", "company": "深澜智能 · D轮",
        "salary": "45-80K", "salary_min": 45, "city": "北京", "exp": "3-5 年",
        "skills": ["LLM", "Transformer", "RAG", "微调"],
        "requirements": [
            "熟悉 Transformer 与主流大模型架构",
            "有 LLM 微调/对齐或 RAG 落地经验",
            "掌握 PyTorch 与分布式训练",
            "关注推理优化与效果评测",
        ],
    },
    {
        "id": "j13", "category": "算法",
        "title": "计算机视觉工程师", "company": "视界科技 · B轮",
        "salary": "35-60K", "salary_min": 35, "city": "深圳", "exp": "3-5 年",
        "skills": ["CV", "目标检测", "CUDA", "部署"],
        "requirements": [
            "熟悉目标检测/分割主流模型",
            "有模型工程化部署经验（TensorRT/ONNX）",
            "了解 CUDA 与推理加速",
            "有边缘设备落地经验加分",
        ],
    },
    # ───────── 系统设计 ─────────
    {
        "id": "j6", "category": "系统设计",
        "title": "系统架构师", "company": "磐石云 · 上市公司",
        "salary": "50-80K", "salary_min": 50, "city": "深圳", "exp": "7 年+",
        "skills": ["分布式", "高可用", "容量规划"],
        "requirements": [
            "7 年以上，主导过大型分布式系统架构",
            "精通高可用、容灾、容量规划",
            "深入理解 CAP、一致性协议、限流熔断",
            "有跨团队技术决策与落地经验",
        ],
    },
    {
        "id": "j14", "category": "系统设计",
        "title": "中间件研发专家", "company": "枢纽科技 · D轮",
        "salary": "45-75K", "salary_min": 45, "city": "上海", "exp": "5 年+",
        "skills": ["消息队列", "存储引擎", "Java", "源码"],
        "requirements": [
            "有消息队列/存储/RPC 等中间件研发经验",
            "能阅读并改造开源中间件源码",
            "理解高性能网络编程与零拷贝",
            "具备稳定性与性能调优能力",
        ],
    },
    {
        "id": "j15", "category": "系统设计",
        "title": "后端架构师 · 高并发", "company": "穹顶出行 · 已上市",
        "salary": "40-68K", "salary_min": 40, "city": "北京", "exp": "6 年+",
        "skills": ["高并发", "分布式事务", "缓存", "稳定性"],
        "requirements": [
            "主导过千万级 DAU 系统的架构演进",
            "精通缓存体系、分布式事务与幂等设计",
            "有大促/秒杀稳定性保障经验",
            "能制定容量、降级、预案策略",
        ],
    },
]
