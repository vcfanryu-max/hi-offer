# Resume Matcher V2.5 架构

## 1. 技术选型

- 前端：Next.js + React + TypeScript，负责路由、交互与浏览器下载。
- 后端：FastAPI + Pydantic，负责解析、Schema 校验、AI 编排与下载响应。
- 数据：SQLite + SQLAlchemy；原始文件保存在本地目录。
- 密钥：Python keyring 接入操作系统凭据库；不可用时只保留在当前后端进程内。
- 模型：OpenAI Chat Completions 兼容接口，支持 DeepSeek、OpenAI 与自定义 HTTPS Provider。

这是一个本地模块化单体。前后端边界清楚，但不引入微服务、队列、向量库、登录系统或云端数据库。

## 2. 页面与数据流

```text
Landing /
   ├─ 开始 ───────────────> Workspace /workspace
   │                          ├─ Resume Version
   │                          ├─ JD
   │                          ├─ Provider Config
   │                          └─ Generation
   │                               ├─ Match Analysis
   │                               ├─ HR Message
   │                               └─ Resume Advice
   └─ 用户档案 ───────────> Profile /profile
                              ├─ Resume Versions
                              ├─ API 保存状态
                              └─ Generation Master–Detail
                                   └─ JD ↔ Resume Version ↔ Match ↔ HR ↔ Advice
```

浏览器只访问 `127.0.0.1:8000` 的本地 API。模型调用由后端发起，前端从不读取已保存的 API Key。

## 3. 数据模型

- `Resume`：本地简历档案，指向当前版本。
- `ResumeVersion`：不可覆盖的版本号、解析文本、原文件路径、OCR 元数据、结构化缓存和创建时间。
- `Job`：完整 JD 文本、来源类型、可选原文件、OCR 元数据和结构化缓存。
- `Generation`：一次不可变业务快照；同时引用一个 `Job` 和一个 `ResumeVersion`，并保存 Structured Resume/JD、Match、HR、Advice、状态、错误、六个 Prompt 版本、Provider 和 Model。
- `ApiConfig`：只保存非敏感配置及 `key_persisted` 状态，不含密钥字段。

数据库通过外键强制 Generation 的 `job_id` 和 `resume_version_id` 有效。历史页不按“当前 JD”或数组下标拼接数据，而是先选择 Generation ID，再读取其关联对象。

## 4. AI 边界

`backend/ai/prompts/` 是唯一 Prompt Source of Truth：

```text
prompts/
├─ role.md
├─ resume_structure/v1.md
├─ jd_analysis/v1.md
├─ match_analysis/v2.md
├─ hr_message/v2.md
├─ resume_advice/v2.md
└─ structured_repair/v1.md
```

五个业务任务分别使用严格 Pydantic Schema。处理链为 Resume/JD 原文 → 独立结构化 → Match；Match 失败会阻断两个依赖它的模块；Match 成功后，HR Message 与 Resume Advice 并行独立运行。所有结构化模块共用 Raw → Parse → Normalize → Validate → 最多一次 Repair → Final Validate。

JD 先估算 Token；超出模型安全预算时按标题、段落和句子语义分块，各块独立生成 Structured JD，再按 ID/内容去重合并。任何步骤都不使用字符切片截断。

图片与扫描 PDF 通过统一 Document Ingestion Pipeline 变成 `CanonicalDocumentText`。后续 AI 模块不关心文本来自 DOCX、嵌入式 PDF 还是本地 OCR。

`/dev/prompts` 每次运行都从磁盘加载所选版本，展示 Prompt Content、Raw/Parsed Output、校验错误、耗时、模型和版本，便于独立迭代。

## 5. 目录职责

```text
backend/
├─ api/          # HTTP 路由与下载响应
├─ ai/           # LLM Client、Pipeline、Schemas、Prompts
├─ db/           # SQLAlchemy 模型与 Session
├─ parsers/      # 文件类型校验与文本提取
├─ security/     # API Key Store
└─ services/     # Resume、Job、Generation、Export 用例
frontend/
├─ app/          # 四个路由
├─ components/   # 复用 UI 与复制/下载操作
├─ lib/          # API Client、类型和文本导出格式
└─ tokens.css    # 唯一 Design Token 来源
data/            # 被 Git 忽略的本地数据库和文件
tests/           # 后端契约、持久化、关联与安全测试
```

## 6. 明确不包含

- 登录、注册、用户表、Session、JWT、OAuth。
- 多租户、云端数据库、对象存储和同步。
- 自动投递、联系 HR、爬取招聘网站和反馈学习闭环。
- V4 的职业定位大表单、Application Tracking 和多阶段 Agent 链。
