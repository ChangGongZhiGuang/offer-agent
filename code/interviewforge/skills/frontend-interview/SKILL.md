---
name: frontend-interview
description: 前端工程师面试方法论。当岗位 JD 涉及前端、Web 前端、JavaScript、TypeScript、Vue、React、浏览器、CSS、HTML、HTTP、性能优化、Webpack、Vite、SSR、Node.js、跨端、可访问性时加载。
---

## 岗位画像
- **典型职级**：初级（1-3 年）/ 资深（3-5 年）/ 架构（5+ 年，能主导工程化）
- **核心能力**：把设计稿/产品需求 → 性能优、可维护、跨设备适配的可交互界面
- **常见误区**：候选人会用框架但讲不清浏览器底层 → 资深岗必须深挖
- **细分赛道**：业务前端 / 中后台 / 工程化 / 跨端 / 数据可视化 / Node 全栈，方法论略有侧重

## 考察维度

### 1. JavaScript 语言机制（权重 25%）
- **作用域与闭包**：词法作用域、变量提升、TDZ、闭包内存泄漏
- **this 与执行上下文**：4 种绑定规则、箭头函数差异
- **原型链**：__proto__ / prototype、class 语法糖背后的本质
- **异步模型**：事件循环、宏任务/微任务、浏览器 vs Node 的差异
- **类型系统**：== vs ===、隐式转换坑、Symbol/BigInt 用途
- **Promise 内部**：手写 Promise、then 链、Promise.all/race/allSettled 边界

### 2. 浏览器原理（权重 20%）
- **渲染管线**：DOM/CSSOM/Render Tree/Layout/Paint/Composite
- **重排重绘**：触发条件、合成层提升、will-change 滥用
- **事件机制**：捕获/冒泡、委托、Passive Listener
- **存储**：Cookie / LocalStorage / SessionStorage / IndexedDB 边界
- **跨域**：CORS 预检、JSONP、postMessage、Origin 策略
- **安全**：XSS（存储/反射/DOM 型）、CSRF、CSP、SameSite Cookie

### 3. 框架原理（权重 20%）
- **Vue**：响应式（Vue2 Object.defineProperty vs Vue3 Proxy）、diff 算法、组件通信、Composition API
- **React**：Fiber 调度、Hooks 闭包陷阱、并发模式、Reconciliation、useMemo/useCallback 使用边界
- **状态管理**：Vuex/Pinia / Redux/Zustand 的取舍
- **路由**：history vs hash、SSR 路由匹配

### 4. 工程化与性能（权重 20%）
- **构建工具**：Webpack（loader/plugin/Tree Shaking）、Vite（ESM + esbuild）
- **打包优化**：分包、懒加载、CDN、Gzip/Brotli
- **首屏优化**：FCP/LCP/CLS/INP 各自含义、定位手段
- **运行时优化**：长列表虚拟滚动、防抖节流、Web Worker
- **监控**：错误监控（Sentry）、性能监控（Performance API、RUM）

### 5. 工程素养（权重 15%）
- TypeScript 类型体操（泛型/条件类型/infer）
- 测试：单测（Jest/Vitest）、E2E（Playwright/Cypress）
- 可访问性（a11y）：语义化标签、ARIA、键盘导航
- 国际化、主题切换、设计系统

## 出题节奏（建议 45-60 分钟）
1. **暖场（5 min）**：聊项目，找深挖点
2. **JS 机制（10 min）**：1-2 道闭包/this/异步小题
3. **浏览器（10 min）**：渲染管线 + 一道安全题
4. **框架原理（15 min）**：让讲一个具体框架的内部机制
5. **手写题（10 min）**：手写 Promise.all / debounce / Vue 响应式 / React useState 模拟
6. **设计题（剩余）**：「设计一个图片懒加载库」「设计一个埋点 SDK」

## 追问树

### 答得好 → 加深
- 「Vue3 用 Proxy 解决了 Vue2 的什么问题？还有哪些没解决？」
- 「React 并发模式下，useEffect 还能保证执行顺序吗？」
- 「FCP 怎么降到 1s 以内？硬约束是什么？」

### 答得卡 → 给提示
- 「先讲讲你平时怎么调首屏？」
- 「不考虑框架，原生 DOM 你怎么做这件事？」

### 答得含糊 → 要例子
- 「你说『大概率会卡』，具体哪一帧会掉？」
- 「打开 Performance 面板你看什么？」
- 「这个 Hook 你写过几次？哪次踩过坑？」

## 红旗信号

| 信号 | 含义 |
|---|---|
| **会用不会讲** | 写 React 三年但讲不清 useEffect 依赖数组的本质 → 框架黑盒 |
| **背诵八股** | 一字不差背事件循环但不知道 setTimeout 嵌套 setTimeout 的延迟下限 |
| **不写 CSS** | 自称前端但 flex/grid 都不熟 → 业务能力差 |
| **只会 ant-design** | 离开组件库就不会写 → 缺基础 |
| **TypeScript 当 any 用** | 类型系统形同虚设 |
| **看不懂 Network 面板** | 排查能力存疑 |

## 评分 rubric（每维度 1-5 分）

| 分 | 描述 |
|---|---|
| 1 | 概念错误或答不上来 |
| 2 | 会用 API 但讲不清原理 |
| 3 | 能讲清原理、能写基础手写题 |
| 4 | 能讲清框架内部、能定位性能问题到具体阶段 |
| 5 | 能讲清浏览器/框架源码级实现，能给行业不同方案对比 |

**通过线**：3.0+；资深岗至少一个维度 4+，工程化方向需要 4+ 在「工程化与性能」。

## 与简历交叉验证清单
- 简历写「精通 Vue/React」→ 必问响应式/Fiber 源码级
- 简历写「负责性能优化提升 X%」→ 追问基线、瓶颈定位、对比工具
- 简历写「主导工程化建设」→ 让画 CI/CD + 构建流水线
- 简历写「TypeScript 重构」→ 给一道类型体操题
