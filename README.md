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

## 目录结构

```
.
├── sync_hktlora.py      # 主程序
├── hktloraweb.py        # HKT Lora网页操作类
├── logs/                # 日志目录
└── apscheduler_state.json  # 调度器状态文件
```

## 配置文件

程序使用 `apscheduler_state.json` 进行配置管理，主要配置项包括：

```json
{
  "sync_top_pages": 2,                    # 同步的页面数量
  "task_b_start_delay_seconds": 0,        # 任务B启动延迟（秒）
  "task_b_interval_minutes": 5,           # 任务B执行间隔（分钟）
  "task_c_start_delay_seconds": 60,       # 任务C启动延迟（秒）
  "task_c_interval_minutes": 10           # 任务C执行间隔（分钟）
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

程序包含三个主要任务：

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

## 配置说明

### 动态配置

你可以通过修改 `apscheduler_state.json` 文件来动态调整程序行为：

1. **页面同步配置**
   - `sync_top_pages`: 设置要同步的页面数量
   - 修改后将在任务B下次执行时生效

2. **任务B配置**
   - `task_b_start_delay_seconds`: 首次启动延迟
   - `task_b_interval_minutes`: 执行间隔
   - 修改后将在任务B下次执行完成时生效

3. **任务C配置**
   - `task_c_start_delay_seconds`: 首次启动延迟
   - `task_c_interval_minutes`: 执行间隔

### 日志配置

- 所有日志文件统一存储在 `logs` 目录
- 日志文件命名格式：`login_YYYYMMDD_HHMMSS.log`
- 处理过的日志文件会自动重命名为 `.bak` 后缀

## 注意事项

1. 确保程序运行时网络连接稳定
2. 不要手动删除或修改正在使用的日志文件
3. 修改配置文件后，新的配置将在下一次任务执行时生效
4. 程序异常退出时会自动清理资源并保存状态

## 错误处理

1. 如果遇到网络错误，程序会自动重试
2. 连续失败3次后，程序会自动重启流程
3. 所有错误都会记录在日志文件中
4. 可以通过查看日志文件了解详细的错误信息

## 调试建议

1. 查看 `logs` 目录下的日志文件
2. 检查 `apscheduler_state.json` 中的状态信息
3. 观察浏览器窗口的操作情况
4. 需要时可以调整日志级别获取更详细的信息