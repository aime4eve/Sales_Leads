# HKT Lora 网页数据同步工具

这是一个用于自动同步和处理HKT Lora网站数据的Python工具。该工具使用Playwright进行网页自动化操作，并通过APScheduler实现定时任务调度。

## 环境要求

- Python 3.6+
- PowerShell 7+ (Windows环境)
- Chrome浏览器

## 安装依赖

1. 安装Python包依赖：
```bash
pip install -r requirements.txt
```

2. 安装Playwright浏览器：
```bash
playwright install chromium
```

主要依赖包说明：
- playwright: 网页自动化操作
- apscheduler: 任务调度管理
- tqdm: 进度条显示
- colorama: 控制台彩色输出

## 项目结构

```
Sales_Leads/
├── design/                # 设计文档目录
├── docs/                 # 文档目录
│   └── MIGRATION.md     # 配置迁移说明
├── hkt_agent_framework/  # 框架代码
│   └── DingTalk/        # 钉钉相关模块
├── notable/             # Notable相关代码
├── tests/               # 测试目录
│   ├── integration/     # 集成测试
│   └── system/         # 系统测试
├── task_config.json    # 配置文件
├── hktloraweb.py       # 网页操作模块
├── LeadsInsight.py     # 销售线索处理
├── sync_hktlora.py     # 主程序
├── requirements.txt    # 依赖管理
└── README.md          # 说明文档
```

## 快速开始

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 配置程序：
   - 复制配置示例：`cp task_config.example.json task_config.json`
   - 根据需要修改配置

3. 运行程序：
   ```bash
   python sync_hktlora.py
   ```

## 故障排查

如果程序运行出现问题：

1. 检查日志文件
2. 检查 `task_config.json` 中的配置
3. 确认网络连接正常
4. 查看错误信息

## 配置文件

程序使用 `task_config.json` 进行配置管理，主要配置项包括：

```json
{
  "task_params": {
    "sync_top_pages": 2,                    # 同步的页面数量
    "task_scheduling": {
      "task_b_start_delay_seconds": 0,      # 任务B启动延迟（秒）
      "task_b_interval_minutes": 5,         # 任务B执行间隔（分钟）
      "task_c_start_delay_seconds": 60,     # 任务C启动延迟（秒）
      "task_c_interval_minutes": 10         # 任务C执行间隔（分钟）
    }
  }
}
```

## 启动程序

```bash
python sync_hktlora.py
```

程序启动后会自动：
1. 创建必要的目录（如logs）
2. 初始化配置文件（如果不存在）
3. 启动浏览器并执行登录
4. 开始定时任务调度

## 功能特性

### 1. 多任务协同工作

程序包含四个主要任务：

- **任务A**（一次性任务）
  - 创建浏览器实例
  - 执行网站登录
  - 初始化任务B和任务C

- **任务B**（定时任务）
  - 定时刷新指定页面
  - 抓取页面内容并保存
  - 支持动态配置执行间隔和页面数量
  - 自动检测配置变更并重新调度

- **任务C**（定时任务）
  - 定期处理错误日志
  - 重试失败的URL
  - 自动归档处理过的日志

- **任务D**（定时任务）
  - 整理网页内容数据
  - 解析JSON文件内容
  - 通过Notable对象将数据同步到钉钉多维表
  - 每6小时执行一次

### 2. 智能任务调度

- 防止任务重复执行
- 自动跳过仍在运行的任务
- 支持动态调整任务间隔
- 任务执行状态持久化

### 3. 错误处理机制

- 自动重试失败的操作
- 错误次数统计和限制
- 超出错误阈值时自动重启
- 详细的错误日志记录

### 4. 状态管理

- 运行状态持久化存储
- 任务执行状态跟踪
- 配置参数动态更新
- 完整的执行历史记录

### 5. 日志管理

- 统一的日志目录管理
- 自动日志归档
- 详细的操作记录
- 错误追踪和分析

### 6. 销售线索处理

- 自动收集客户留言和联系信息
- 整理网页表单数据
- 同步到钉钉多维表格
- 数据清洗和转换

## 配置说明

### 配置文件结构

项目使用 `task_config.json` 作为统一的配置文件，包含以下主要部分：

1. **基本信息**
   - `version`: 配置文件版本
   - `last_update`: 最后更新时间

2. **任务组配置** (`task_group`)
   - `loop_count`: 循环执行次数
   - `pause_minutes`: 循环间暂停时间
   - `error_wait_minutes`: 错误后等待时间
   - `current_group_id`: 当前任务组ID
   - `completed_groups`: 已完成的任务组数

3. **任务参数** (`task_params`)
   - `sync_top_pages`: 要同步的页面数量
   - `retry_count`: 重试次数
   - `retry_wait_seconds`: 重试等待时间
   - **任务调度** (`task_scheduling`)
     - `task_b_start_delay_seconds`: 任务B首次启动延迟
     - `task_b_interval_minutes`: 任务B执行间隔
     - `task_c_start_delay_seconds`: 任务C首次启动延迟
     - `task_c_interval_minutes`: 任务C执行间隔
   - **性能阈值** (`performance_threshold`)
     - `task_a_timeout`: 任务A超时时间
     - `task_b_timeout`: 任务B超时时间
     - `task_c_timeout`: 任务C超时时间
     - `task_d_timeout`: 任务D超时时间

4. **执行状态** (`execution_state`)
   - `last_run`: 最后运行时间
   - `completed_runs`: 完成的运行次数
   - `error_count`: 错误计数
   - `current_loop`: 当前循环次数
   - `last_error`: 最后一次错误信息
   - `last_status`: 最后状态
   - **任务状态** (`task_states`)
     - 各任务的运行状态（running）
     - 各任务的开始和结束时间

5. **资源阈值** (`resource_thresholds`)
   - `cpu_percent`: CPU使用率阈值
   - `memory_percent`: 内存使用率阈值
   - `disk_percent`: 磁盘使用率阈值
   - `process_memory_mb`: 进程内存限制

6. **日志配置** (`logging`)
   - `level`: 日志级别
   - `max_file_size_mb`: 单个日志文件大小限制
   - `max_files`: 保留的日志文件数量
   - `log_dir`: 日志目录

### 配置示例

```json
{
    "version": "1.0",
    "last_update": "2025-06-05 21:12:50",
    "task_params": {
        "sync_top_pages": 2,
        "task_scheduling": {
            "task_b_start_delay_seconds": 10,
            "task_b_interval_minutes": 90,
            "task_c_start_delay_seconds": 120,
            "task_c_interval_minutes": 30
        }
    }
}
```

### 配置更新

配置文件支持动态更新，修改后将在下次任务执行时生效：

1. **任务调度更新**
   - 修改 `task_scheduling` 中的参数
   - 新的调度间隔将在当前任务完成后生效
   - 首次启动延迟仅在程序启动时生效

2. **性能参数更新**
   - 修改 `performance_threshold` 中的超时设置
   - 新的超时设置将在下次任务执行时生效

3. **资源限制更新**
   - 修改 `resource_thresholds` 中的阈值
   - 新的阈值将立即生效

4. **日志配置更新**
   - 修改 `logging` 中的设置
   - 需要重启程序才能生效

### 注意事项

1. 配置文件使用 UTF-8 编码
2. 时间相关的配置单位说明：
   - `*_seconds`: 秒
   - `*_minutes`: 分钟
   - 超时配置单位均为秒
3. 状态值说明：
   - `init`: 初始状态
   - `running`: 运行中
   - `error`: 错误状态
   - `completed`: 完成状态
   - `shutdown`: 已关闭
4. 建议在修改配置前备份当前配置文件

## 销售线索处理

LeadsInsight类实现了以下功能：

1. **整理网页内容**
   - 从elementor_db_sync目录查找最新的数据文件
   - 从YYYYMMDD_HHMMSS格式的目录中找到最新目录
   - 从retry_YYYYMMDD_HHMMSS格式的目录中找到最新目录
   - 将两个目录中的JSON文件复制到sales_leads目录

2. **解析JSON文件内容**
   - 从Elementor_DB_*.json文件中提取View信息和Read/Unread状态
   - 根据提取的post ID读取submission_*.json文件获取客户留言详情
   - 合并两个数据源的信息形成完整客户记录

3. **同步到钉钉多维表**
   - 使用Notable对象连接钉钉API
   - 将客户数据转换为钉钉多维表格式
   - 同步数据到"资源池"多维表中
   - 记录同步状态和错误信息

### 如何单独测试LeadsInsight

可以使用提供的测试脚本：

```bash
python test_leads_insight.py --step 3
```

参数说明：
- `--step 1`: 仅执行整理网页内容
- `--step 2`: 仅执行同步到钉钉
- `--step 3`: 执行完整流程（默认）
- `--config`: 指定Notable配置文件路径
- `--table`: 指定目标表格名称
- `--db-dir`: 指定Elementor数据库目录

## 注意事项

1. 确保程序运行时网络连接稳定
2. 不要手动删除或修改正在使用的日志文件
3. 修改配置文件后，新的配置将在下一次任务执行时生效
4. 程序异常退出时会自动清理资源并保存状态
5. 钉钉多维表同步需要有效的Notable配置

## 错误处理

1. 如果遇到网络错误，程序会自动重试
2. 连续失败3次后，程序会自动重启流程
3. 所有错误都会记录在日志文件中
4. 可以通过查看日志文件了解详细的错误信息

## 调试建议

1. 查看 `logs` 目录下的日志文件
2. 检查 `task_config.json` 中的状态信息
3. 观察浏览器窗口的操作情况
4. 需要时可以调整日志级别获取更详细的信息

## Sales_Leads 项目

## 项目说明
Sales_Leads 是一个自动化网页抓取和数据同步工具，用于从网页获取销售线索数据并同步到钉钉多维表。

## 主要功能
1. 自动登录和页面抓取
2. 定时刷新和数据保存
3. 错误日志处理和重试
4. 销售线索数据同步
5. 性能监控和资源管理

## 系统要求
- Python 3.7+
- Chrome浏览器
- 钉钉开放平台账号
- psutil（可选，用于系统资源监控）

## 安装
1. 克隆仓库
```bash
git clone [repository_url]
cd Sales_Leads
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

## 配置
1. 创建配置文件
```bash
cp task_config.json.example task_config.json
```

2. 修改配置文件
编辑 `task_config.json`，根据需要调整以下配置：
- task_group：任务组执行配置
- task_params：任务参数配置
- resource_thresholds：资源阈值配置
- logging：日志配置

## 使用方法
1. 启动程序
```bash
python sync_hktlora.py
```

2. 监控运行状态
- 查看日志文件：`logs/login_*.log`
- 查看状态文件：`task_config.json`

3. 停止程序
按 Ctrl+C 或发送 SIGTERM 信号

## 配置文件说明

### task_group 配置
```json
{
    "loop_count": 30,        // 任务组内循环次数
    "pause_minutes": 3,      // 任务组间暂停时间
    "error_wait_minutes": 1  // 错误后等待时间
}
```

### task_params 配置
```json
{
    "sync_top_pages": 2,     // 同步的页面数量
    "retry_count": 3,        // 任务失败重试次数
    "retry_wait_seconds": 60 // 重试等待时间
}
```

### resource_thresholds 配置
```json
{
    "cpu_percent": 80,       // CPU使用率阈值
    "memory_percent": 80,    // 内存使用率阈值
    "disk_percent": 90,      // 磁盘使用率阈值
    "process_memory_mb": 1024 // 进程内存使用阈值
}
```

## 任务执行流程
1. Task A：创建浏览器实例并登录
2. Task B：定时刷新页面并保存内容
3. Task C：处理错误日志和重试失败URL
4. Task D：同步销售线索数据到钉钉多维表

## 错误处理
- 任务失败自动重试
- 指数退避重试策略
- 状态一致性检查
- 资源使用监控

## 性能监控
- CPU使用率监控
- 内存使用情况监控
- 磁盘使用情况监控
- 任务执行时间监控

## 注意事项
1. 确保配置文件格式正确
2. 不要手动修改状态文件
3. 定期检查日志文件大小
4. 监控系统资源使用情况

## 常见问题
1. Q: 程序启动失败
   A: 检查配置文件格式和必要参数

2. Q: 任务执行超时
   A: 调整性能阈值配置

3. Q: 内存使用过高
   A: 检查资源阈值配置

## 贡献指南
1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 发起 Pull Request

## 许可证
MIT License

## 作者
[Your Name]

## 更新日志
### v1.0.0 (2025-06-05)
- 实现基本功能
- 添加任务调度系统
- 添加性能监控
- 添加错误处理