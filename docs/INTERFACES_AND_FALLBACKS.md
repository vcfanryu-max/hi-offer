# 接口、降级与前端信息边界

## 1. 本地 API

| 领域 | 接口 | 用途 |
|---|---|---|
| Resume | `GET /api/resumes` | 版本列表 |
| Resume | `GET /api/resumes/current` | 当前版本 |
| Resume | `POST /api/resumes/upload` | 新建版本 |
| Resume | `PATCH /api/resumes/versions/{id}/current` | 切换当前版本 |
| Resume | `GET /api/resumes/versions/{id}/download` | 下载原文件 |
| Job | `POST /api/jobs/text` | 保存粘贴 JD |
| Job | `POST /api/jobs/upload` | 保存并解析 JD 文件 |
| Job | `GET /api/jobs/{id}/download` | 下载原文件或 TXT |
| Settings | `GET/PUT/DELETE /api/settings/provider` | 读取状态、保存或移除配置 |
| Settings | `POST /api/settings/provider/test` | 测试模型连接 |
| Generation | `POST /api/generations` | 建立快照并运行五个业务模块 |
| Generation | `GET /api/generations[/{id}]` | 历史摘要/完整详情 |
| Generation | `POST /api/generations/{id}/retry/{module}` | 单模块重试 |
| Generation | `GET /api/generations/{id}/export/{kind}` | 服务端文本导出 |
| Prompt Lab | `GET /api/dev/prompts` | 任务与版本目录 |
| Prompt Lab | `POST /api/dev/prompts/run` | 运行单个 Prompt |

## 2. 降级与兜底

| 故障 | 系统行为 | 用户可继续做什么 |
|---|---|---|
| 文件格式不支持、过大或 OCR 无有效文字 | 拒绝该文件，不创建空版本，也不进入 LLM | 上传更清晰的图片、可复制 PDF/DOCX 或粘贴 JD |
| JD 超过模型安全上下文 | 语义分段提取并合并，不静默截断 | 正常等待生成；Development Trace 可查看分块数量 |
| 操作系统凭据库不可用 | API Key 仅保存在当前后端内存，界面明确标记 | 本次运行仍可生成；重启后重新输入 |
| 本地后端未启动 | 前端给出“本地后端未连接”，不假装云端可用 | 启动 Backend 后重试；磁盘数据不丢失 |
| 网络、鉴权、额度或 Provider 错误 | 显示面向用户的分类错误，不输出 Key 或完整响应 | 修改配置、稍后重试或更换 Provider |
| Match Analysis 失败 | HR 与 Advice 标记 blocked | 单独重试 Match；不写伪造结果 |
| HR Message 失败 | 保留 Match，并继续生成 Advice | 单独重试 HR Message |
| Resume Advice 失败 | 保留 Match 和 HR Message | 单独重试 Resume Advice |
| 模型返回非 JSON 或结构不合规 | Normalize 后最多自动 Repair 一次，仍失败才显示简短提示 | 重试或更换模型；原始异常只在 DEBUG 折叠区可见 |

“降级”是功能缩小但仍可用，例如 keyring 不可用时改为进程内密钥；“兜底”是失败后的最后安全输出，例如明确错误和可执行下一步。两者都不能用模板假装 AI 已完成分析。

## 3. 前端可以展示

- 原始文件名、版本号、日期和下载入口。
- Provider、Model、是否已配置、密钥是否持久化。
- Generation ID、Resume Version、JD 标题/公司、Match/HR/Advice 三个用户结果状态。
- 结构化匹配结论、HR Message、Resume Advice 和可行动的错误提示。
- Prompt 版本和历史快照说明。

## 4. 普通前端不得展示

- API Key、Authorization Header、凭据库条目或任何密钥片段。
- 本地绝对路径、SQLite 位置、堆栈、内部异常类和网络响应全文。
- System/Role Prompt、完整 Prompt 模板、Raw LLM Output；Prompt Lab 与 Raw/Parsed/Normalized Trace 只允许在 `DEBUG=true` 的开发界面出现。
- 用户未上传或模型未证实的信息、内部风险评分公式、算法中间推理。
- 其他 Generation 的 Advice；详情必须由当前 `generation_id` 获取。

所有第三方响应的错误正文在后端先截断并替换 API Key，再映射为简洁信息。普通页面只消费白名单字段。
