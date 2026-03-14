# MySQL 运维案例库

本目录存放 MySQL 常见运维问题的**真实业务场景**设计，帮助学生理解技术概念对业务的实际影响。

每个案例文件对应 mysql-ops-learning 中的一个问题，包含：业务需求场景、涉及概念、对业务的影响、与工具的对应关系。

## 案例索引

| 案例文件 | 问题 | 核心概念 |
|----------|------|----------|
| [01-max-connections.md](01-max-connections.md) | 最大连接数耗尽 | max_connections、连接池 |
| [02-slow-log.md](02-slow-log.md) | 慢查询监控 | slow_query_log、long_query_time |
| [03-large-transaction.md](03-large-transaction.md) | 大事务 | 事务持有锁时间、INNODB_TRX |
| [04-large-table.md](04-large-table.md) | 大表问题 | 分区、在线 DDL、pt-osc |
| [05-deadlock.md](05-deadlock.md) | 死锁 | 加锁顺序、死锁检测 |
| [06-lock-wait-timeout.md](06-lock-wait-timeout.md) | 锁等待超时 | innodb_lock_wait_timeout |
| [07-index-misuse.md](07-index-misuse.md) | 索引使用不当 | EXPLAIN、全表扫描 |
