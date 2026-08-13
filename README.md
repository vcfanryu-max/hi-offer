<div align="center">

# Resume Matcher

上传简历和岗位 JD，生成有证据可追溯的匹配分析、HR 开场话术与简历修改建议。

[开始使用](#开始使用) · [本地数据](#本地数据) · [项目结构](#项目结构) · [部署说明](#部署说明)

</div>

找工作时，简历里的同一段经历往往要面对完全不同的岗位要求。Resume Matcher 把一次求职分析保存成一个完整记录。你可以回看当时使用的简历版本、JD、匹配结论、话术和修改建议，不会让后续修改覆盖旧结果。

项目采用 Local-first 方式运行。简历、JD、OCR 文本、SQLite 数据库和生成记录默认保存在你的电脑上。模型请求仍会把本次分析所需文本发送给你选择的模型 Provider，请先阅读[数据边界](#数据边界)。

## 它能做什么

- 保存简历原文件，并为每次上传建立独立版本。
- 接收粘贴文本、PDF、DOCX、TXT、Markdown 和常见图片格式的 JD。
- 使用本地 RapidOCR 识别图片与扫描型 PDF，中英文混排也走同一套解析流程。
- 将长 JD 按语义分段分析，合并时保留职责、硬性要求和到岗条件。
- 分别生成 Match Analysis、HR Message 和 Resume Advice。
- 将 JD、简历版本和三个结果保存为同一个 Generation Snapshot。
- 支持复制文本，并按原始文件、TXT 或 Markdown 下载。
- 在系统凭据库中保存 API Key。凭据库不可用时，只在当前后端进程的内存中保留。

五个业务模块和一个结构修复模块分别使用独立 Prompt。Prompt 文件放在 `backend/ai/prompts/`，修改后不需要复制到其他目录。

```text
Resume → Parser / OCR → resume_structure ─┐
                                         ├→ match_analysis → hr_message
JD     → Parser / OCR → jd_analysis ─────┘                 └→ resume_advice

结构校验失败时
Raw JSON → Normalize → Pydantic Validate → one-shot structured_repair
```

## 开始使用

### 环境

- Python 3.12。项目依赖允许兼容的较新 3.x 版本，但发布验证使用 3.12。
- Node.js 20.9 或更高版本。发布验证使用 Node.js 24。
- npm 10 或更高版本。

### Windows

在项目根目录打开 PowerShell。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd --prefix frontend ci
.\scripts\start-local.ps1
```

浏览器打开 [http://localhost:3000](http://localhost:3000)。页面先要求选择 Provider、Model 并填写自己的 API Key。API Key 不应写入源码、`.env` 或 GitHub 仓库。

需要查看模型结构化输出的调试轨迹时，可以这样启动。

```powershell
.\scripts\start-local.ps1 -DebugMode
```

调试页会显示 Prompt 版本、Request ID、Raw Output、Normalized JSON 和校验错误。API Key 与 Authorization Header 会继续被过滤。

### macOS 与 Linux

准备两个终端。先安装依赖。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
npm --prefix frontend ci
```

终端一启动本地 API。

```bash
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

终端二启动网页。

```bash
npm --prefix frontend run dev
```

Linux 桌面环境如果没有可用的系统 keyring，页面会明确提示 API Key 只在本次后端运行期间有效。

## 本地数据

运行后会在 `data/` 下建立这些内容。

```text
data/
├── app.db
├── resumes/
└── jobs/
```

这些文件已被 `.gitignore` 排除。仓库中的两个 `.gitkeep` 只负责保留空目录，不包含用户数据。上传文件不会覆盖旧版本，数据库迁移也只增加表或字段，不删除既有记录。

如果希望把数据放到另一个目录，可以设置 `RESUME_MATCHER_DATA_DIR`。发布包里的 `.env.example` 只有安全的示例值，不包含密钥。用 `uvicorn --env-file .env` 启动时，后端会读取你复制出来的本地 `.env`。

### 数据边界

- 简历原文件、JD 原文件、OCR 文本、数据库和历史记录默认只写入本机。
- 图片 OCR 在本地由 RapidOCR 与 ONNX Runtime 完成，不调用额外 OCR SaaS。
- 生成分析时，后端会把结构化简历和 JD 发送给你配置的模型 Provider。
- API Key 优先交给操作系统凭据库。项目数据库不保存 API Key。
- `DEBUG=false` 时，前端不会提供内部 Prompt 和模型轨迹接口。
- 把项目部署到远程服务器后，所谓“本地”指服务器磁盘，不再是使用者自己的电脑。

## 项目结构

```text
.
├── backend/
│   ├── ai/                 # Schema、Pipeline、Prompt 与结构修复
│   ├── api/                # FastAPI 路由
│   ├── db/                 # SQLite Model 与安全迁移
│   ├── parsers/            # 文档解析和本地 OCR
│   ├── security/           # OS keyring
│   └── services/           # 简历、JD、Generation 与导出
├── frontend/
│   ├── app/                # Landing、Workspace、Profile
│   ├── components/
│   └── lib/
├── data/                   # 运行时创建，内容不进 Git
├── docs/
├── scripts/
└── tests/
```

API 健康检查位于 [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)。更完整的数据关系和接口说明见 [ARCHITECTURE.md](docs/ARCHITECTURE.md) 与 [INTERFACES_AND_FALLBACKS.md](docs/INTERFACES_AND_FALLBACKS.md)。

## 部署说明

### Netlify 作品集 Demo

仓库根目录的 `netlify.toml` 会让 Netlify 只构建 `frontend/`，并设置
`NEXT_PUBLIC_DEMO_MODE=true`。线上页面使用仓库内的虚构示例数据，不上传文件、
不连接 FastAPI，也不调用付费模型。将 Netlify 连接到 GitHub 的 `main` 分支后，
后续每次合并都会触发一次完整的前端重新构建和原子部署。

### Docker Compose（单用户/私有环境）

复制配置示例，并按实际域名修改前端 API 地址和后端 CORS 白名单。

```bash
cp .env.example .env
docker compose up --build -d
```

默认前端位于 `http://localhost:3000`，后端健康检查位于
`http://localhost:8000/api/health`。运行数据保存在 Docker 命名卷中。
`NEXT_PUBLIC_API_BASE` 会在前端构建时写入浏览器包，修改后需要重新构建前端镜像。

> 当前应用没有登录、多租户和用户数据隔离。该配置只适合个人或受信任的私有环境，不能据此直接开放为多人公共服务。

当前版本无法直接部署到 Streamlit Community Cloud。它包含一个 Next.js 前端和一个 FastAPI 后端，需要 Node.js 与 Python 两个常驻进程；仓库也没有 Streamlit 入口文件。添加一个空的 `streamlit_app.py` 不能让这套网页在 Streamlit 上运行。

这个发布包适合上传到 GitHub，也适合在本机或能同时运行 Node.js 与 Python 的主机上启动。远程部署至少要处理这些事项。

1. 为前端设置 `NEXT_PUBLIC_API_BASE`，指向可访问的后端地址。
2. 为后端设置 `RESUME_MATCHER_CORS_ORIGINS`，只放行实际前端域名。
3. 为 `data/` 准备持久磁盘。临时文件系统会让简历和历史记录在重启后消失。
4. 重新评估 keyring。无桌面的服务器通常不能提供与个人电脑相同的凭据库体验。
5. 若开放给多人使用，需要另外设计身份、数据隔离和密钥管理。当前版本没有登录与多租户。

如果部署目标必须是 Streamlit，需要重新实现一层 Streamlit 页面，并复用现有 Python 服务与 Schema。现有 Next.js 页面无法原样迁入。详细的兼容性判断和迁移范围见 [DEPLOYMENT_COMPATIBILITY.md](docs/DEPLOYMENT_COMPATIBILITY.md)。

## 测试

安装开发依赖后运行。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

测试样本由代码生成，不包含真实简历、JD 或 API Key。OCR 测试会消耗更多 CPU，并可能在首次运行时准备本地模型文件。

## 已知限制

- 图片与文件上传上限为 12 MB。
- OCR 质量取决于清晰度、方向和版面。空结果会中止生成，并要求重新上传。
- 自定义 Provider 必须兼容 OpenAI Chat Completions 接口，并使用 HTTPS。
- Local-first 适合个人本地使用。远程多人服务需要另做安全设计。
- 仓库暂未附带开源许可证。公开可见不等于自动授予复制、修改或再发布权利。
