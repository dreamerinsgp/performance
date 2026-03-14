# 案例 09：CPU/IO 飙高

## 业务需求场景

某电商平台的报表系统每日凌晨 2 点定时执行聚合查询，统计昨日订单销售数据。开发人员编写了如下 SQL：

```sql
SELECT status, DATE(create_time) as day, COUNT(*), SUM(amount) 
FROM orders 
WHERE create_time >= '2024-01-01'
GROUP BY status, DATE(create_time)
ORDER BY day DESC
```

上线初期数据量较小，查询执行正常。但随着订单表数据量增长到 50 万条后，报表执行时间从原来的 1 秒飙升到 30+ 秒，同时 DBA 发现 MySQL 服务器 CPU 使用率飙升至 80%+，I/O 等待时间显著增加。

## 涉及的技术概念

- **全表扫描 (Full Table Scan)**: MySQL 必须遍历整个表的所有行来获取数据
- **索引 (Index)**: 加速数据检索的数据结构
- **复合索引 (Composite Index)**: 包含多个列的索引
- **Filesort**: 无法使用索引排序时的外部排序操作
- **EXPLAIN**: MySQL 查询优化器的执行计划分析工具
- **Buffer Pool**: InnoDB 缓存数据页和索引页的内存区域
- **覆盖索引 (Covering Index)**: 索引包含查询所需的全部列

## 对业务的影响

- **用户体验**: 报表生成超时，运营人员无法按时获取数据
- **系统性能**: MySQL 服务器负载过高，影响其他业务查询
- **资源成本**: CPU 和磁盘 I/O 资源被长时间占用

## 问题根因分析

1. **缺少合适的索引**: `create_time` 字段虽然有索引，但 `WHERE create_time >= '2024-01-01'` 使用了范围查询，且后续 `GROUP BY status, DATE(create_time)` 需要对结果排序

2. **索引列上使用函数**: `DATE(create_time)` 对索引列使用了函数，导致索引失效

3. **Filesort 排序**: 没有合适的索引支持排序操作，MySQL 只能使用 Filesort 进行外部排序，消耗大量 CPU 和内存

4. **全表扫描**: 50 万行数据全部读取到内存中进行聚合计算

## 解决方案

### 方案一：添加复合索引

```sql
ALTER TABLE orders ADD INDEX idx_status_time (status, create_time);
```

### 方案二：使用覆盖索引（推荐）

```sql
ALTER TABLE orders ADD INDEX idx_cover (status, create_time, amount);
```

### 方案三：优化 SQL 写法

避免在索引列上使用函数：

```sql
-- 不推荐（索引失效）
SELECT ... WHERE DATE(create_time) = '2024-01-01'

-- 推荐（可使用索引）
SELECT ... WHERE create_time >= '2024-01-01' AND create_time < '2024-01-02'
```

## 与 mysql-ops-learning 的对应

| Action | 说明 |
|--------|------|
| reproduce | 创建 50 万条测试数据，执行全表扫描聚合查询，触发 CPU/IO 飙高 |
| explain | 查看查询执行计划，分析全表扫描和 Filesort 问题 |
| optimize | 添加复合索引后重新执行，对比优化效果 |

## 学习要点

1. **索引设计原则**: 遵循最左前缀原则，合理设计复合索引
2. **避免索引失效**: 不要在索引列上使用函数
3. **EXPLAIN 重要性**: 任何慢查询都应先通过 EXPLAIN 分析执行计划
4. **Filesort 优化**: 尽量使用索引排序，避免 Filesort
5. **覆盖索引**: 优先使用覆盖索引，减少回表查询
