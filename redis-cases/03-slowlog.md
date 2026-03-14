# 案例 03：慢命令

## 图示：场景 → 问题 → 解决方案

```mermaid
flowchart TB
    subgraph 场景["业务场景：缓存查询"]
        A[业务频繁查询用户信息] --> B[KEYS user:* 全匹配]
        B --> C[百万级 key 时 O(N) 扫描]
        C --> D[单次执行数秒]
    end

    subgraph 问题["问题：Redis 单线程阻塞"]
        D --> E[slowlog 记录慢命令]
        E --> F[后续请求排队]
        F --> G[接口 P99 飙升]
        G --> H[用户感知卡顿]
    end

    subgraph 解决["解决方案"]
        I[避免 KEYS *] --> J[用 SCAN 分批]
        K[大 hash] --> L[HSCAN 替代 HGETALL]
        M[监控 slowlog] --> N[定位热点慢命令]
    end

    问题 --> 解决
```

## 业务需求场景

**电商商品缓存 KEYS 扫描**

某电商使用 Redis 缓存商品信息，key 格式为 `product:{id}`。某次活动开发误用 `KEYS product:*` 统计在线商品数。

- 线上 **200 万** 个 product key
- `KEYS product:*` 全表扫描，单次 **3–5 秒**
- Redis 单线程，期间其他命令全部阻塞
- 接口 P99 从 20ms 升到 **5 秒**
- slowlog 刷屏，活动页面大量超时

## 涉及的技术概念

- **slowlog-log-slower-than**：慢于该微秒数的命令记入 slowlog
- **slowlog-max-len**：slowlog 最多保留条数
- **SLOWLOG GET n**：获取最近 n 条慢命令

## 对业务的影响

- **直接影响**：Redis 阻塞，所有依赖 Redis 的接口变慢
- **间接影响**：用户体验极差，活动转化率下降

## 与 redis-ops-learning 的对应

| 工具操作 | 作用 |
|----------|------|
| Run: 查看慢日志配置 | CONFIG GET slowlog* |
| Run: 最近慢命令 | SLOWLOG GET 10 |

## 学习要点

避免 KEYS *、HGETALL 大 hash 等 O(N) 命令；用 SCAN/HSCAN 替代；定期查看 slowlog 定位问题。
