# 配置文件迁移说明

## 变更概述

从版本 1.0 开始，我们将配置系统从 `apscheduler_state.json` 迁移到新的 `task_config.json`。这个变更带来了以下改进：

1. 更清晰的配置结构
2. 更完整的功能支持
3. 更好的可维护性
4. 统一的配置管理

## 自动迁移

程序会自动处理配置迁移：

1. 首次运行新版本时，如果检测到旧的 `apscheduler_state.json`：
   - 自动迁移所有配置到新格式
   - 创建旧配置文件的备份（`.bak` 后缀）
   - 生成新的 `task_config.json`

2. 如果没有检测到旧配置：
   - 创建新的 `task_config.json`
   - 使用默认配置值

## 手动迁移

如果需要手动迁移，请按照以下步骤操作：

1. 备份现有配置：
   ```bash
   cp apscheduler_state.json apscheduler_state.json.bak
   ```

2. 创建新的配置文件：
   - 复制 README.md 中的配置示例
   - 根据旧配置更新相应值

3. 配置对照表：

   | 旧配置 | 新配置 |
   |--------|--------|
   | `sync_top_pages` | `task_params.sync_top_pages` |
   | `task_b_start_delay_seconds` | `task_params.task_scheduling.task_b_start_delay_seconds` |
   | `task_b_interval_minutes` | `task_params.task_scheduling.task_b_interval_minutes` |
   | `task_c_start_delay_seconds` | `task_params.task_scheduling.task_c_start_delay_seconds` |
   | `task_c_interval_minutes` | `task_params.task_scheduling.task_c_interval_minutes` |
   | `task_b_running` | `execution_state.task_states.task_b_running` |
   | `task_c_running` | `execution_state.task_states.task_c_running` |
   | `last_run` | `execution_state.last_run` |
   | `completed_runs` | `execution_state.completed_runs` |
   | `error_count` | `execution_state.error_count` |
   | `last_error` | `execution_state.last_error` |
   | `last_status` | `execution_state.last_status` |

## 新增配置项

新的配置文件添加了多个有用的配置项：

1. 任务组配置
   - 支持任务分组
   - 循环执行控制
   - 错误处理策略

2. 性能阈值
   - 任务超时控制
   - 资源使用限制

3. 日志管理
   - 文件大小控制
   - 日志轮转策略

## 验证配置

迁移后，可以通过以下方式验证配置：

1. 检查配置文件格式：
   ```bash
   python -c "import json; json.load(open('task_config.json'))"
   ```

2. 运行配置测试：
   ```bash
   python test_config.py
   ```

## 常见问题

1. Q: 程序无法启动，提示配置错误
   A: 检查 `task_config.json` 格式是否正确，确保所有必需字段都存在

2. Q: 任务调度间隔未生效
   A: 确认配置项位于正确的层级，检查 `task_params.task_scheduling` 下的相应配置

3. Q: 找不到旧的配置数据
   A: 检查是否存在 `.bak` 后缀的备份文件

## 回滚说明

如果需要回滚到旧版本：

1. 恢复旧配置文件：
   ```bash
   mv apscheduler_state.json.bak apscheduler_state.json
   ```

2. 删除新配置文件：
   ```bash
   rm task_config.json
   ```

3. 重启程序

## 技术支持

如果在迁移过程中遇到问题：

1. 查看程序日志文件
2. 检查配置文件格式
3. 联系技术支持团队 