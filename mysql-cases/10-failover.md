# 案例 10：故障转移（主从切换）

## 图示：场景 → 问题 → 解决方案

```mermaid
sequenceDiagram
    participant App as 应用服务器
    participant Master as 主库 (Master)
    participant Slave as 从库 (Slave)
    
    Note over Master,Slave: 正常状态：主从同步
    App->>Master: 写入订单数据
    Master->>Slave: binlog 同步
    App->>Slave: 读取订单（只读）
    
    Note over Master: ⚠️ 故障发生
    Note over Master: 主库 MySQL 无响应
    
    App->>Master: ✗ 写入失败！
    App->>Master: ✗ 订单创建失败
    App->>Master: ✗ 支付中断
    
    Note over Master,Slave: 执行故障转移
    Slave->>Slave: 1. STOP SLAVE
    Slave->>Slave: 2. RESET SLAVE ALL
    Slave->>Slave: 3. SET read_only=OFF
    Slave->>Slave: 4. 提升为新主库
    
    App->>Slave: 写入订单数据
    Slave-->>App: ✓ 写入成功
    
    Note over Master,Slave: 故障转移完成
```

```mermaid
flowchart TB
    subgraph 场景["业务场景：电商订单系统高可用"]
        A[主库：订单写入] --> B[从库：数据同步]
        B --> C[读写分离架构]
    end

    subgraph 问题["问题：主库故障"]
        C --> D[主库 MySQL 无响应]
        D --> E[应用写入失败]
        E --> F[订单无法创建]
        F --> G[支付流程中断]
        G --> H[业务中断]
    end

    subgraph 解决["解决方案：主从切换"]
        I[检查从库状态] --> J[确认无延迟]
        J --> K[STOP SLAVE]
        K --> L[RESET SLAVE ALL]
        L --> M[read_only=OFF]
        M --> N[提升为新主库]
        N --> O[切换应用连接]
    end

    问题 --> 解决
```

## 业务需求场景

**电商平台订单系统高可用架构**

某电商平台采用 MySQL 主从架构实现高可用：

- **主库 (Master)**：负责所有写入操作（订单、支付、库存）
- **从库 (Slave)**：负责读取操作（商品查询、订单状态查看）
- **读写分离**：写入走主库，读取优先走从库

**故障发生场景：**

- **时间**：工作日下午 14:30
- **事件**：主库 MySQL 服务无响应
- **原因**：硬件故障/网络中断/数据库崩溃（模拟）
- **影响**：
  - 用户无法下单（写入请求失败）
  - 支付流程中断
  - 订单创建失败
  - 客服投诉激增
  - **业务中断计时开始...**

## 涉及的技术概念

- **主从复制 (Master-Slave Replication)**：MySQL 高可用基础架构
- **读写分离**：写入主库、读取从库，分担负载
- **故障转移 (Failover)**：主库故障时将从库提升为主库的过程
- **read_only**：从库只读模式，防止意外写入
- **super_read_only**：超级用户也无法写入的只读模式
- **STOP SLAVE**：停止从库复制
- **RESET SLAVE ALL**：清除从库复制配置
- **GTID**：全局事务 ID（简化故障转移）
- **MGR (MySQL Group Replication)**：未来自动故障转移方案

## 对业务的影响

- **服务中断**：写入请求失败，业务无法正常进行
- **用户流失**：无法下单导致用户体验极差
- **数据丢失风险**：若从库数据未完全同步，切换将导致数据丢失
- **财务风险**：支付中断可能引发客户投诉和纠纷
- **运维压力**：DBA 需要紧急响应，执行手动故障转移

## 与 mysql-ops-learning 的对应

| 工具操作 | 作用 |
|----------|------|
| `go run ./cmd run 10-failover reproduce` | 模拟业务场景，展示故障发生前后状态 |
| `go run ./cmd run 10-failover prepare` | 准备阶段：检查从库状态，确认数据同步 |
| `go run ./cmd run 10-failover switch` | 执行切换：将从库提升为主库 |
| `go run ./cmd run 10-failover verify` | 验证结果：检查数据一致性和服务状态 |

## 学习要点

1. **故障转移的必要性**：单主库架构下，主库故障将导致业务完全中断
2. **数据一致性是关键**：切换前必须确认从库已同步最新数据（Seconds_Behind_Master = 0）
3. **手动 vs 自动**：手动故障转移依赖 DBA 响应，自动故障转移可使用 MGR 或 Keepalived
4. **read_only 陷阱**：故障转移后必须关闭 read_only，否则仍无法写入
5. **应用切换**：数据库切换后需要更新应用连接配置
6. **善后处理**：原主库修复后需重新建立主从关系
