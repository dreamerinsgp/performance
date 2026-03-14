# 案例 02：连接数耗尽

## 图示：场景 → 问题 → 解决方案

```mermaid
flowchart TB
    subgraph 场景["业务场景：高并发"]
        A[微服务集群 100+ 实例] --> B[每实例连接池 50]
        B --> C[理论 5000+ 连接]
        C --> D[连接泄漏未关闭]
    end

    subgraph 问题["问题：连接耗尽"]
        D --> E[connected_clients 逼近 maxclients]
        E --> F[新连接失败]
        F --> G["max number of clients reached"]
        G --> H[应用报错，服务不可用]
    end

    subgraph 解决["解决方案"]
        I[连接池限流] --> J[合理配置 pool size]
        K[修复泄漏] --> L[确保连接归还]
        M[监控] --> N["connected_clients / maxclients"]
    end

    问题 --> 解决
```

## 业务需求场景

**微服务调用 Redis 连接泄漏**

某公司微服务架构，每个服务实例使用 Redis 连接池。某次发布引入 bug：在异常分支未正确释放连接。

- 集群 **80 个** 实例，每实例池大小 50，理论 4000 连接
- 云 Redis 实例 maxclients = **5000**
- 泄漏导致每实例实际占用 **60+** 连接
- 约 1 小时后，**新请求报错**："max number of clients reached"
- 全部服务无法访问 Redis，业务全面中断

## 涉及的技术概念

- **connected_clients**：当前已连接客户端数
- **maxclients**：Redis 允许的最大连接数（默认 10000，云 Redis 可能更低）
- **blocked_clients**：阻塞在 BLPOP 等命令的客户端数

## 对业务的影响

- **直接影响**：无法连接 Redis，缓存/会话/队列全部不可用
- **间接影响**：级联失败，需紧急回滚或扩容

## 与 redis-ops-learning 的对应

| 工具操作 | 作用 |
|----------|------|
| Run: 查看连接 | 执行 INFO clients，查看 connected_clients、maxclients |

## 学习要点

理解连接池与 maxclients 的关系；监控 connected_clients；排查连接泄漏。
