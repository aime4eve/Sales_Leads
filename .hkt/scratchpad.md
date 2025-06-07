# 项目协作文档

## 背景和动机
需要根据程序时序图设计文档（程序时序图.markdown）修改sync_hktlora.py，集成APScheduler组件，实现多线程自动化网页抓取。根据时序图，程序应包含以下主要部分：
- APScheduler作为核心调度器，负责任务调度与资源管理
- 线程A：创建浏览器实例并完成登录逻辑（HKTLoraWeb.login_main_site方法）
- 线程B：定时刷新网页并保存内容（HKTLoraWeb.do_refresh_pages方法）
- 线程C：处理错误日志（HKTLoraWeb.extract_failed_urls方法）

新增需求：为任务B和任务C添加可配置的启动延迟（相对于任务A完成的时间）和执行间隔。

新增需求：创建一个LeadsInsight对象，根据@构思.md文档中的设计思路完成销售线索数据的处理和同步。

## 关键挑战和分析
1. 需要使用APScheduler替换现有的手动线程管理方式
2. 需要确保APScheduler能够按照时序图中的逻辑进行任务调度
3. 需要实现错误恢复和异常处理机制
4. 需要确保任务持久化与恢复功能
5. 需要解决Playwright可能存在的线程安全问题

通过分析现有的sync_hktlora.py和hktloraweb.py文件，我们发现：
- 当前实现已经包含线程A、B、C的核心功能
- 当前实现使用了线程事件和共享资源进行线程管理
- 程序已有异常处理机制，但没有使用APScheduler进行任务调度

我们需要重构程序，使用APScheduler替换当前的线程管理方式，同时保留现有的功能。

针对新增的可配置启动时间需求：
- 如何在状态文件 (`apscheduler_state.json`) 中优雅地管理这些新的配置项。
- 定义合理的默认值，例如任务B在任务A完成后立即启动，任务C在任务A完成后延迟几分钟启动。
- 修改任务调度逻辑以使用这些新配置。

针对新增的LeadsInsight需求：
- 需要开发一个新的LeadsInsight类，实现设计文档中的功能
- 需要解析Elementor_DB_*.json和submission_*.json文件中的数据
- 需要使用Notable对象将数据同步到钉钉多维表
- 需要将LeadsInsight集成到sync_hktlora.py中，作为任务D定期执行

## 高层任务拆分
1. 分析现有sync_hktlora.py代码结构和APScheduler集成需求
2. 设计新的程序架构，确定APScheduler的配置和使用方式
3. 重构SharedResources类，适配APScheduler任务管理
4. 实现线程A的APScheduler任务（一次性任务）
5. 实现线程B的APScheduler任务（固定间隔任务）
6. 实现线程C的APScheduler任务（固定间隔任务）
7. 实现异常处理和任务恢复机制
8. 实现运行日志记录和持久化功能
9. 编写主函数，初始化APScheduler并启动任务
10. 测试完整功能，确保符合时序图设计
11. 实现LeadsInsight类，包括文件处理、数据解析和数据同步功能
12. 创建测试脚本，验证LeadsInsight类的功能
13. 将LeadsInsight集成到sync_hktlora.py中，作为任务D定期执行
14. 更新项目文档，包括README.md

## 项目状态看板
- [x] 分析现有代码结构和APScheduler集成需求
- [x] 设计新的程序架构
- [x] 重构SharedResources类
- [x] 实现线程A的APScheduler任务
- [x] 实现线程B的APScheduler任务
- [x] 实现线程C的APScheduler任务
- [x] 实现异常处理和任务恢复机制
- [x] 实现运行日志记录和持久化功能
- [x] 编写主函数，初始化APScheduler并启动任务
- [x] **(新增)** 设计任务B和任务C的启动延迟和执行间隔的配置项。
- [x] **(新增)** 更新 `RunStateManager` 以支持新配置项。
- [x] **(新增)** 更新 `SharedResources` 以支持新配置项。
- [x] **(新增)** 更新 `task_a_login` 以使用新配置项。
- [x] **(新增)** 实现LeadsInsight类，包括文件处理、数据解析和数据同步功能
- [x] **(新增)** 创建测试脚本，验证LeadsInsight类的功能
- [x] **(新增)** 将LeadsInsight集成到sync_hktlora.py中，作为任务D定期执行
- [x] **(新增)** 更新项目文档，包括README.md
- [ ] 测试完整功能，包括新的可配置启动时间。
- [ ] **(新增)** 统一日志文件到 `logs` 目录并修复 `task_c_process_logs` 的日志读取逻辑。

## 当前状态/进度跟踪
已完成所有开发任务，包括代码结构分析、架构设计、SharedResources类重构、三个核心任务实现、异常处理和任务恢复机制，以及运行日志记录和持久化功能。目前已实现的功能包括：

1. **SharedResources类重构**：
   - 添加了context和page属性，方便在任务间共享
   - 添加了error_count和max_error_count，用于错误次数跟踪
   - 添加了init_hkt_web、cleanup、reset_error_count和increment_error_count方法
   - 移除了不再需要的线程事件

2. **核心任务实现**：
   - 任务A：创建一次性任务，负责初始化Playwright、浏览器实例和登录
   - 任务B：创建固定间隔任务（每5分钟执行一次），执行页面刷新和内容保存
   - 任务C：创建固定间隔任务（每10分钟执行一次），提取和处理失败的URL
   - 任务D：创建固定间隔任务（每6小时执行一次），处理销售线索数据并同步到钉钉多维表

3. **异常处理和重启机制**：
   - 实现了restart_process函数，用于重启整个流程
   - 添加了job_listener函数，监听任务执行结果
   - 在任务函数中实现了错误捕获和处理逻辑

4. **运行日志记录和持久化功能**：
   - 创建了RunStateManager类，管理程序运行状态的持久化
   - 实现了状态加载、保存、更新、错误记录和完成记录等功能
   - 在日志设置中添加了创建日志目录和使用完整日志路径的功能
   - 修改了extract_failed_urls方法，使其能够处理不同位置的日志文件

5. **主函数更新**：
   - 设置日志配置并返回完整日志路径
   - 创建状态管理器并加载现有状态
   - 创建共享资源并传入状态管理器
   - 添加作业监听器和初始任务
   - 启动调度器并等待用户中断
   - 确保资源正确清理和状态更新

6. **LeadsInsight类实现**：
   - 创建了LeadsInsight类，实现了设计文档中的功能
   - 实现了文件处理功能，包括查找最新目录和复制文件
   - 实现了数据解析功能，包括解析Elementor_DB和submission文件
   - 实现了数据同步功能，包括准备Notable定义文件和同步到钉钉多维表
   - 创建了测试脚本，验证LeadsInsight类的功能
   - 将LeadsInsight集成到sync_hktlora.py中，作为任务D定期执行
   - 更新了项目文档，包括README.md

**新增功能：任务B和任务C启动时间和间隔可配置**
- **RunStateManager**: 已更新，在初始化时为 `task_b_start_delay_seconds` (默认0), `task_b_interval_minutes` (默认5), `task_c_start_delay_seconds` (默认60), `task_c_interval_minutes` (默认10) 设置了默认值。这些值会在 `apscheduler_state.json` 文件不存在或这些键缺失时使用，并在首次保存时写入文件。
- **SharedResources**: 已更新，在初始化时会从 `RunStateManager` 加载这些配置项，如果加载失败则使用预设的默认值。
- **task_a_login**: 已更新，在调度任务B (task_b_refresh_pages) 和任务C (task_c_process_logs) 时，会使用从 `SharedResources` 中获取的启动延迟 (next_run_time) 和执行间隔 (minutes)。同时更新了日志输出，以显示将使用的延迟和间隔。
- **任务ID统一**: 在 `task_a_login` 中调度任务B和C时，以及在 `restart_process` 中移除这些任务时，统一使用了 `task_b_refresh_pages` 和 `task_c_process_logs` 作为任务ID。

**新增功能：LeadsInsight销售线索处理**
- **LeadsInsight类**: 已实现，包含文件处理、数据解析和数据同步功能。该类按照设计文档中的需求，从elementor_db_sync目录中获取最新的数据文件，解析其中的内容，并通过Notable对象将数据同步到钉钉多维表。
- **测试脚本**: 已创建test_leads_insight.py，用于验证LeadsInsight类的功能。测试脚本支持三种测试模式：仅测试文件处理、仅测试数据同步、测试完整流程。
- **任务D**: 已集成到sync_hktlora.py中，作为定期任务每6小时执行一次。任务D包含完整的错误处理和状态管理逻辑，与其他任务保持一致的风格。
- **文档更新**: 已更新README.md，添加了关于LeadsInsight类的信息，包括功能说明、使用方法和注意事项。

**新增功能：统一日志文件管理**
- **`SharedResources.init_hkt_web`**: 修改后，确保 `HKTLoraWeb` 实例 (`self.hkt_web.log_file`) 使用的日志文件路径指向 `logs` 目录（例如 `logs/login_xxxx.log`）。
- **`patch_extract_failed_urls`**:
    - 修改后，仅在 `logs` 目录中搜索历史日志文件。
    - 修正了跳过当前活动日志文件的逻辑，确保基于完整路径进行比较。
    - 强化了仅处理早于当前程序启动时间的日志文件的逻辑。
这将解决之前在根目录和 `logs` 目录同时存在日志文件的问题。

## 测试计划

为确保程序按照时序图设计正常运行，我们将进行以下测试：

### 1. 基本功能测试

1. **初始化和启动测试**
   - 目标：验证程序能够正确初始化并启动
   - 步骤：运行 `python sync_hktlora.py`
   - 预期结果：程序启动，创建日志目录和状态文件，并开始执行任务A

2. **任务A执行测试**
   - 目标：验证任务A能够正确创建浏览器实例并登录
   - 步骤：观察日志输出
   - 预期结果：任务A成功完成，添加任务B和任务C

3. **任务B执行测试**
   - 目标：验证任务B能够正确刷新页面并保存内容
   - 步骤：观察日志输出和elementor_db_sync目录中的文件
   - 预期结果：任务B成功完成，生成数据文件

4. **任务C执行测试**
   - 目标：验证任务C能够正确处理错误日志
   - 步骤：观察日志输出和.bak文件的生成
   - 预期结果：任务C成功完成，处理失败的URL

5. **任务D执行测试**
   - 目标：验证任务D能够正确处理销售线索数据并同步到钉钉多维表
   - 步骤：观察日志输出和钉钉多维表中的数据
   - 预期结果：任务D成功完成，同步数据到钉钉多维表

### 2. 异常处理测试

1. **任务B失败测试**
   - 目标：验证任务B失败时的错误处理机制
   - 步骤：在任务B执行前，手动关闭浏览器窗口
   - 预期结果：程序检测到错误，增加错误计数

2. **重启流程测试**
   - 目标：验证多次错误后程序能够自动重启流程
   - 步骤：连续触发3次错误（手动关闭浏览器或断开网络）
   - 预期结果：程序重启整个流程，重新执行任务A

3. **网络异常测试**
   - 目标：验证网络异常时的错误处理机制
   - 步骤：在程序运行过程中，断开网络连接
   - 预期结果：程序检测到错误，增加错误计数，可能触发重启流程

### 3. 持久化测试

1. **状态持久化测试**
   - 目标：验证程序状态能够正确持久化
   - 步骤：运行程序一段时间后，检查apscheduler_state.json文件
   - 预期结果：文件包含正确的运行状态信息

2. **程序重启测试**
   - 目标：验证程序重启后能够正确加载之前的状态
   - 步骤：运行程序一段时间后，手动终止并重新启动
   - 预期结果：程序加载之前的状态并继续运行

### 4. 时序图验证测试

1. **任务顺序验证**
   - 目标：验证任务执行顺序符合时序图设计
   - 步骤：观察日志输出中任务A、B、C的执行顺序
   - 预期结果：任务A先执行，然后任务B和任务C按照（可配置的）延迟和固定间隔交替执行

2. **任务依赖验证**
   - 目标：验证任务依赖关系符合时序图设计
   - 步骤：观察任务A完成后是否添加任务B和任务C
   - 预期结果：任务A成功完成后，添加任务B和任务C

3. **异常流程验证**
   - 目标：验证异常流程符合时序图设计
   - 步骤：触发异常，观察重启流程
   - 预期结果：异常后重启整个流程，从任务A开始

### 5. (新增) 可配置性测试

1. **默认配置测试**
   - 目标：验证程序使用默认配置启动任务B和任务C。
   - 步骤：首次运行程序，不修改任何配置文件。
   - 预期结果：任务B和任务C按照预设的默认延迟和间隔启动和执行。

2. **自定义配置测试 - 任务B**
   - 目标：验证修改任务B的启动延迟和执行间隔配置后，程序按新配置运行。
   - 步骤：
     1. 运行一次程序以生成 `apscheduler_state.json`。
     2. 修改 `apscheduler_state.json` 中任务B的启动延迟（例如，`task_b_start_delay_seconds`）和执行间隔（例如，`task_b_interval_minutes`）。
     3. 重启程序。
   - 预期结果：任务B根据修改后的配置启动和执行，日志中反映新的调度时间。

3. **自定义配置测试 - 任务C**
   - 目标：验证修改任务C的启动延迟和执行间隔配置后，程序按新配置运行。
   - 步骤：
     1. 运行一次程序以生成 `apscheduler_state.json`。
     2. 修改 `apscheduler_state.json` 中任务C的启动延迟（例如，`task_c_start_delay_seconds`）和执行间隔（例如，`task_c_interval_minutes`）。
     3. 重启程序。
   - 预期结果：任务C根据修改后的配置启动和执行，日志中反映新的调度时间。

4. **无效配置测试**
   - 目标：验证程序如何处理无效或缺失的配置项。
   - 步骤：
     1. 手动删除或修改 `apscheduler_state.json` 中的相关配置项为无效值（例如，非数字）。
     2. 重启程序。
   - 预期结果：程序应能优雅处理，例如使用默认值并记录警告，而不是崩溃。

### 6. (新增) LeadsInsight测试

1. **文件处理测试**
   - 目标：验证LeadsInsight类能够正确处理文件
   - 步骤：运行 `python test_leads_insight.py --step 1`
   - 预期结果：成功查找最新目录并复制文件到sales_leads目录

2. **数据同步测试**
   - 目标：验证LeadsInsight类能够正确同步数据到钉钉多维表
   - 步骤：运行 `python test_leads_insight.py --step 2`
   - 预期结果：成功解析数据并同步到钉钉多维表

3. **完整流程测试**
   - 目标：验证LeadsInsight类能够正确执行完整流程
   - 步骤：运行 `python test_leads_insight.py --step 3`
   - 预期结果：成功执行文件处理和数据同步

4. **任务D集成测试**
   - 目标：验证任务D能够正确执行LeadsInsight处理流程
   - 步骤：运行 `python sync_hktlora.py`，等待任务D执行
   - 预期结果：任务D成功执行，LeadsInsight处理流程完成

### 测试计划执行步骤

1. 确保已安装APScheduler包：`pip install apscheduler`
2. 运行程序：`python sync_hktlora.py`
3. 按照测试计划依次进行各项测试
4. 记录测试结果和发现的问题
5. 根据测试结果进行必要的修复和调整

**新增：日志统一和 task_c 修正**
- 日志文件现在应统一在 `logs` 目录下创建和管理。
- `task_c_process_logs` 中的日志文件读取逻辑已修正，应能正确处理 `logs` 目录下的历史日志。

建议在测试时，特别注意：
1. 新的日志文件是否只在 `logs` 目录下生成。
2. 删除根目录下的旧日志文件（如果存在），然后运行程序，确认 `task_c_process_logs` 是否能正确找到并处理 `logs` 目录中的旧日志（如果创建一些用于测试的旧日志）。
3. `task_c_process_logs` 是否不再因为找不到日志或错误处理当前日志而失败。

**新增：LeadsInsight测试注意事项**
1. 确保elementor_db_sync目录中有数据文件，如果没有，可以先运行程序让任务B生成数据。
2. 确保Notable配置正确，能够正常连接钉钉API。
3. 检查钉钉多维表是否存在"资源池"视图，如果不存在，可以先创建。
4. 测试LeadsInsight类之前，先运行一次get_table_views方法生成notable_definition.json文件。

## 执行者反馈或请求帮助
已完成所有开发任务，现在需要进行测试。在开发过程中发现并解决了几个关键问题：

1. **任务调度顺序**：使用APScheduler的next_run_time参数控制任务的首次执行时间，确保任务按照正确的顺序执行。

2. **资源共享**：使用SharedResources类在不同任务间共享资源，并处理了Playwright线程安全问题。

3. **状态持久化**：通过RunStateManager类实现了程序运行状态的持久化，记录错误、完成次数和同步配置等信息。

4. **日志管理**：改进了日志文件管理，创建专门的logs目录，并确保extract_failed_urls方法能够处理不同位置的日志文件。

**针对新增可配置启动时间功能的开发已完成。**
- `RunStateManager` 已扩展以包含新的配置项及其默认值。
- `SharedResources` 已更新以读取这些配置。
- `task_a_login` 已修改为使用这些配置来调度任务B和C。
- 任务ID已统一为 `task_b_refresh_pages` 和 `task_c_process_logs`。

**针对新增LeadsInsight功能的开发已完成。**
- 创建了完整的LeadsInsight类，实现了文件处理、数据解析和数据同步功能。
- 创建了测试脚本test_leads_insight.py，用于验证LeadsInsight类的功能。
- 将LeadsInsight集成到sync_hktlora.py中，作为任务D定期执行。
- 更新了README.md，添加了关于LeadsInsight类的信息。

现在已经准备好进行测试计划中的各项测试，以确保程序按照时序图设计正常运行。请批准测试计划并指导如何进行测试。

**新增：日志统一和 task_c 修正**
- 日志文件现在应统一在 `logs` 目录下创建和管理。
- `task_c_process_logs` 中的日志文件读取逻辑已修正，应能正确处理 `logs` 目录下的历史日志。

建议在测试时，特别注意：
1. 新的日志文件是否只在 `logs` 目录下生成。
2. 删除根目录下的旧日志文件（如果存在），然后运行程序，确认 `task_c_process_logs` 是否能正确找到并处理 `logs` 目录中的旧日志（如果创建一些用于测试的旧日志）。
3. `task_c_process_logs` 是否不再因为找不到日志或错误处理当前日志而失败。

**新增：LeadsInsight测试注意事项**
1. 确保elementor_db_sync目录中有数据文件，如果没有，可以先运行程序让任务B生成数据。
2. 确保Notable配置正确，能够正常连接钉钉API。
3. 检查钉钉多维表是否存在"资源池"视图，如果不存在，可以先创建。
4. 测试LeadsInsight类之前，先运行一次get_table_views方法生成notable_definition.json文件。

## 经验教训
- 程序输出应包含调试信息，便于跟踪执行流程。
- Playwright不支持在多线程之间共享Page对象，会出现"Cannot switch to a different thread"错误。
- 在使用第三方库时，需要了解其线程安全性和限制。
- 有时候需要根据实际情况灵活调整实现方式，在保留核心功能的同时解决技术限制。
- 使用Event对象可以很好地标记各个步骤的完成状态，即使在单线程环境中也很有用。
- 处理日志文件时需要注意文件锁定问题，不要尝试操作当前正在使用的日志文件。
- 即使在单线程环境中，也可以通过合理的设计来模拟多线程执行的逻辑流程。
- APScheduler的BackgroundScheduler使用后台线程执行任务，适合在常规Python程序中使用。
- APScheduler的job_id必须唯一，使用replace_existing=True可以替换同名任务。
- APScheduler的任务可以通过add_listener监听执行结果和异常。
- APScheduler的next_run_time参数可以控制任务的首次执行时间，非常适合控制任务执行顺序。
- 共享资源的清理非常重要，特别是在异常情况下，确保所有资源都被正确释放。
- 程序状态的持久化对于长时间运行的任务非常重要，可以帮助恢复和调试。
- 使用专门的日志目录和文件命名规则可以更好地管理日志文件。 