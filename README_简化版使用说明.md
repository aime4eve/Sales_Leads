# SyncHKTLora 简化版使用说明

## 概述

这是一个大幅简化的HKTLora网站同步程序，从原来的2249行复杂APScheduler架构简化为330行的双层循环结构。

## 核心功能

1. **自动登录**: 使用HKTLoraWeb自动登录网站
2. **页面刷新**: 定期刷新指定数量的页面
3. **失败处理**: 提取和处理失败的URL
4. **销售线索**: 自动处理销售线索数据并同步到钉钉
5. **优雅退出**: 支持Ctrl+C优雅退出

## 程序架构

```
主循环 (无限):
├── 初始化浏览器 (Playwright)
├── 初始化组件 (HKTLoraWeb, LeadsInsight)
├── 执行登录 (login_main_site)
└── 任务循环 (无限):
    ├── 刷新页面 (do_refresh_pages) → 等待30秒
    ├── 处理失败URL (extract_failed_urls) → 等待60秒
    └── 处理销售线索 (LeadsInsight.process) → 等待90秒
```

## 配置文件

程序会自动读取 `task_config.json` 配置文件，如果不存在会使用默认配置。

### 配置示例 (task_config_simple.json)

```json
{
  "task_params": {
    "sync_top_pages": 1,
    "refresh_wait_seconds": 30,
    "extract_wait_seconds": 60,
    "leads_wait_seconds": 90
  },
  "logging": {
    "level": "INFO",
    "log_dir": "logs"
  }
}
```

### 配置说明

- `sync_top_pages`: 每次刷新的页面数量 (默认: 1)
- `refresh_wait_seconds`: 页面刷新后等待时间 (默认: 30秒)
- `extract_wait_seconds`: URL提取后等待时间 (默认: 60秒)
- `leads_wait_seconds`: 销售线索处理后等待时间 (默认: 90秒)
- `logging.level`: 日志级别 (INFO/DEBUG/ERROR)
- `logging.log_dir`: 日志目录 (默认: logs)

## 运行方法

### 1. 基本运行

```bash
python sync_hktlora.py
```

### 2. 退出程序

在程序运行时按 `Ctrl+C` 即可优雅退出

### 3. 查看日志

日志文件保存在 `logs/` 目录下，文件名格式：`sync_hktlora_YYYYMMDD_HHMMSS.log`

## 错误处理

- **设计原则**: 任何任务失败都会立即退出程序
- **错误记录**: 所有错误都会详细记录到日志文件
- **资源清理**: 程序退出时自动清理浏览器资源

## 主要组件

### 1. SimpleConfig
- 负载配置文件管理
- 提供默认配置
- 支持嵌套键值获取

### 2. SyncHKTLora
- 主程序类
- 管理整个同步流程
- 处理信号和资源清理

### 3. 依赖模块
- `HKTLoraWeb`: 网站操作功能
- `LeadsInsight`: 销售线索处理
- `playwright`: 浏览器自动化

## 与复杂版本的区别

| 方面 | 复杂版本 | 简化版本 |
|------|----------|----------|
| 代码行数 | 2249行 | ~330行 |
| 调度方式 | APScheduler | 简单循环 |
| 状态管理 | 复杂持久化 | 无状态 |
| 错误恢复 | 自动重试机制 | 立即退出 |
| 性能监控 | 详细监控 | 基本日志 |
| 配置管理 | 复杂多层 | 简单结构 |
| 资源管理 | PlaywrightQueue | 直接调用 |

## 注意事项

1. **网络要求**: 需要稳定的网络连接
2. **浏览器要求**: 需要安装Chromium浏览器
3. **Python版本**: 建议Python 3.8+
4. **依赖模块**: 确保所有依赖模块已正确安装

## 故障排除

### 1. 导入模块失败
```
ModuleNotFoundError: No module named 'HKTLoraWeb'
```
确保 `HKTLoraWeb.py` 和 `LeadsInsight.py` 在同一目录下。

### 2. 浏览器启动失败
检查系统是否安装了Chromium浏览器，或者尝试安装playwright:
```bash
playwright install chromium
```

### 3. 认证错误
```
net::ERR_INVALID_AUTH_CREDENTIALS
```
这个错误已经在简化版本中修复。程序会自动使用HKTLoraWeb中配置的认证信息：
- 用户名: "access"
- 密码: "login"

如果仍然出现此错误，请检查HKTLoraWeb.py中的AUTH_USER和AUTH_PASS配置。

### 4. 登录失败
检查网络连接和网站可访问性。如果是认证问题，参考上面的"认证错误"解决方案。

### 5. 配置文件错误
如果配置文件格式错误，程序会使用默认配置并记录错误到日志。

## 开发说明

如需修改程序逻辑：

1. **修改等待时间**: 编辑 `task_config.json` 中的对应配置
2. **添加新任务**: 在 `_task_loop()` 方法中添加新的任务调用
3. **修改错误处理**: 在各个任务方法中修改错误处理逻辑
4. **调整日志级别**: 修改配置文件中的 `logging.level`

## 版本信息

- **版本**: 简化版 v1.0
- **基于**: 原复杂版本的核心功能提取
- **维护**: 专注于稳定性和简洁性 