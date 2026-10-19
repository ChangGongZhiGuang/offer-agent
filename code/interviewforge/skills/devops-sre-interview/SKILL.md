---
name: devops-sre-interview
description: DevOps/SRE/运维/平台工程面试方法论。当岗位 JD 涉及 SRE、DevOps、运维、Kubernetes、K8s、Docker、容器、CI/CD、Jenkins、GitOps、监控、Prometheus、可观测、Linux、网络、稳定性、SLO、混沌工程时加载。
---

## 岗位画像
- **典型职级**：初级（运维操作）/ 中级（自动化 + 监控）/ 高级 SRE（稳定性 + 容量 + 故障演练）
- **核心能力**：把「业务系统稳定运行」量化为 SLI/SLO/SLA，并用工程手段达成
- **SRE vs DevOps vs 运维**：
  - 运维：救火 + 部署 + 巡检（被动）
  - DevOps：CI/CD + 自动化（流程优化）
  - SRE：稳定性工程化 + 容量规划 + 错误预算（用代码解决运维问题）

## 考察维度

### 1. Linux 与网络基础（权重 20%）
- **进程**：fork/exec、信号、僵尸/孤儿进程、cgroup
- **文件系统**：inode、硬链接/软链接、`/proc` 关键文件
- **内存**：虚拟内存、Page Cache、OOM 触发、`vm.swappiness`
- **网络**：TCP 三次握手/四次挥手、TIME_WAIT 调优、SYN flood
- **排查工具**：`top/htop/iostat/vmstat/sar/perf/tcpdump/strace/lsof`
- **必杀题**：「机器 CPU 100% 你怎么排查？」「机器 load 高但 CPU 不高怎么解释？」

### 2. 容器与编排（权重 25%）
- **Docker 原理**：namespace（PID/Net/Mount...）、cgroup（CPU/Memory 限制）、UnionFS、镜像分层
- **K8s 核心**：Pod / Deployment / Service / Ingress / ConfigMap / Secret
- **K8s 高级**：StatefulSet、DaemonSet、Job、HPA / VPA、PDB、Taint/Toleration、Affinity
- **网络模型**：CNI（Calico/Cilium/Flannel）、Service ClusterIP/NodePort/LB、Ingress 七层
- **存储**：PV/PVC/StorageClass、CSI 驱动
- **调度**：调度器扩展、Pod 优先级、抢占
- **必杀题**：「Pod CrashLoopBackOff 怎么排查？」「K8s 网络包从 Pod A 到 Pod B 经过哪几跳？」

### 3. CI/CD 与发布（权重 15%）
- **流水线**：Jenkins / GitLab CI / GitHub Actions / Argo Workflows
- **构建优化**：分层缓存、并行、增量构建
- **发布策略**：蓝绿 / 金丝雀 / 滚动 / 灰度，各自风险与回滚速度
- **GitOps**：Argo CD / Flux，Pull 模式 vs Push 模式
- **制品管理**：Harbor、镜像签名、漏洞扫描

### 4. 可观测与稳定性（权重 25%）
- **三件套**：Metrics（Prometheus） / Logs（ELK/Loki） / Traces（Jaeger/Tempo）
- **PromQL**：rate / increase / histogram_quantile、聚合、`without/by`
- **告警设计**：基于症状还是原因？阈值还是异常检测？告警风暴怎么治？
- **SLI/SLO/SLA**：四个黄金信号（延迟、流量、错误、饱和度）
- **错误预算**：定义、消耗策略、用完后停止上线
- **混沌工程**：ChaosMesh / LitmusChaos，故障注入与稳态假设

### 5. 故障处理与演练（权重 15%）
- **故障分级**：P0-P4 各自响应时间
- **应急流程**：发现 → 通报 → 定位 → 缓解 → 恢复 → 复盘
- **快速回滚**：5 分钟内能否回到上一版本
- **复盘 5 Why**：根因分析、改进项闭环
- **常见故障类型**：雪崩、缓存击穿、限流不够、配置错误、容量不足、依赖故障

## 高频考题与切入

| 题目 | 关键深挖点 |
|---|---|
| **K8s Pod 启动慢怎么排查** | 镜像拉取 / 调度 / 初始化容器 / readiness probe |
| **业务延迟 P99 突然升高** | 找黄金信号 → 链路 trace → 资源饱和 |
| **机器 100% CPU 排查** | top → 找进程 → `perf top` / 火焰图 → 定位函数 |
| **K8s 网络丢包** | tcpdump in pod → veth → cni bridge → 节点物理网卡 |
| **设计一个 SLO 体系** | 选 SLI → 历史数据定基线 → 错误预算 → 燃尽监控 |
| **DB 主库挂了怎么办** | 切主流程、主从延迟、双写一致性、客户端感知 |
| **大规模配置变更怎么做** | 灰度顺序、变更窗口、回滚预案 |

## 追问树

### 答得好 → 加深
- 「这个故障下次怎么自动化兜底，不用人来救？」
- 「K8s 调度器如果换成你来设计，第一刀砍哪里？」
- 「错误预算用完了但业务方坚持要发版，你怎么办？」

### 答得卡 → 给场景化抓手
- 「假设是你现在被叫去救火，你执行的第一条命令是什么？」
- 「先排查应用还是先排查 K8s？为什么？」

### 答得套话 → 要真实事故
- 「你讲讲最近一次 P1 事故的全过程，时间线、决策、复盘改进项」
- 「这个监控指标的具体阈值是多少？怎么定的？」

## 红旗信号

| 信号 | 含义 |
|---|---|
| **背 K8s 文档** | 能背 API 字段但 Pod 故障不会排查 |
| **没踩过事故** | 工作 3 年没经历 P0/P1 → 真实经验存疑 |
| **告警麻木** | 「告警太多没人看」→ 没做过告警治理 |
| **手动操作多** | 改配置靠 SSH 改文件 → 缺自动化思维 |
| **不懂 SLO** | 只会保证「不挂」但讲不清量化目标 |
| **Linux 工具不熟** | 不会用 strace/perf/tcpdump → 排查能力低 |

## 评分 rubric（每维度 1-5 分）

| 分 | 描述 |
|---|---|
| 1 | 概念错或不会基本排查 |
| 2 | 会执行命令但讲不清原理 |
| 3 | 能讲清原理 + 用工具排查 + 完成日常运维 |
| 4 | 能主导故障复盘、能设计监控告警体系、能定位深层问题 |
| 5 | 能设计平台 / 能讲清行业最佳实践（Google SRE Book）/ 能给量化数字 |

**通过线**：3.0+；SRE 高级岗 3.5+ 且稳定性维度 4+。

## 与简历交叉验证清单
- 简历写「负责 K8s 平台」→ 必问规模（节点数/Pod 数）、CNI 选型、踩过的坑
- 简历写「SLO 99.99%」→ 追问 SLI 怎么定、错误预算怎么用、燃尽看板长什么样
- 简历写「主导故障演练」→ 必问演练场景、稳态假设、最大一次注入是什么
- 简历写「降本 X%」→ 追问资源率怎么测、降在 CPU/内存/存储哪里
