# GitHub Release 最终验收

验收日期为 2026-08-13。本记录针对当前 `github_release/`，不包含原开发目录、个人数据库或本次验证使用的临时环境。

## 发布内容

发布包采用白名单复制方式生成，只保留运行和理解项目所需的内容。

- FastAPI 后端、Next.js 前端和启动脚本。
- 六个正式业务与结构修复 Prompt，以及独立 `role.md`。
- Pydantic Schema、Structured Output、Normalizer 和 one-shot repair。
- SQLite Model、安全追加 Migration、本地文件与 keyring 服务。
- Long JD、本地 RapidOCR、复制下载和 Generation Snapshot。
- 合成测试、架构文档、依赖清单和安全示例配置。

最终文件数量为 81。总大小约为 347 KB，不含临时 Git 元数据。

## 已过滤内容

- 原项目的 `data/app.db`、数据库备份、Resume、JD、OCR 结果和 Generation History。
- `.env`、`secrets.toml`、API Key、Authorization Header、Cookie 和系统凭据。
- `.venv`、`node_modules`、`.next`、`__pycache__`、`.pytest_cache`、npm cache 和运行时 PID。
- 日志、临时文件、调试抓取、模型权重、压缩包和大文件。
- 旧 Streamlit 入口、旧 Prompt 镜像、个人文档和截图。

`data/resumes/` 与 `data/jobs/` 只保留空的 `.gitkeep`。运行时数据库和上传文件由程序重新建立，并受到 `.gitignore` 保护。

## 安装与依赖

验证环境使用 Python 3.12、Node.js 24.14.1 和 npm 11.11.0。

| 检查 | 结果 |
| --- | --- |
| 干净虚拟环境执行 `pip install -r requirements.txt` | 通过 |
| `pip check` | 通过，无依赖冲突 |
| `npm ci` | 通过，安装 30 个包 |
| npm audit | 通过，0 个已知漏洞 |
| TypeScript `tsc --noEmit` | 通过 |
| Next.js production build | 通过 |
| Python 自动测试 | 53 passed |

Python 依赖按实际 import 整理。Pillow 是源码直接依赖，已经显式加入 `requirements.txt`。前端锁文件与 `package.json` 一致，`npm ci` 可以重建依赖目录。

当前代码不调用 Tesseract、Poppler、LibreOffice 或其他系统命令，因此没有添加 `packages.txt`。Windows x64 的干净安装已经验证；目标 Linux 镜像仍需确认 RapidOCR、ONNX Runtime 与 CPU 架构的 wheel 兼容性。

## HTTP Smoke Test

最终版本从 `github_release/` 自身启动，使用 8100 与 3100 临时端口，未借用原开发目录的服务。

| 请求 | 状态 |
| --- | --- |
| `GET http://127.0.0.1:8100/api/health` | 200，`storage=local`，`debug=false` |
| `GET http://127.0.0.1:3100/` | 200 |
| `GET http://127.0.0.1:3100/workspace` | 200，页面含 Resume Matcher 标题 |
| `GET http://127.0.0.1:3100/profile` | 200 |
| 从 `http://localhost:3100` 访问 API 的 CORS | 正确返回该 Origin |

Smoke Test 结束后，前后端测试进程、临时数据库、虚拟环境、npm cache 和日志均已关闭并清除。该测试没有调用真实 LLM Provider，因而没有读取或复制个人 API Key、简历或 JD。

## Secret 与隐私检查

- 文件名扫描未发现 SQLite、Resume、JD、PDF、Office、图片、日志、模型权重、压缩包、`.env` 或 `secrets.toml`。
- 文本扫描未发现个人 Windows 用户路径、用户名、OpenAI/DeepSeek Key、GitHub Token、AWS Key、Google Key 或私钥头。
- 唯一 Bearer 形态命中为单元测试中的固定字符串 `Bearer should-not-appear`。它用于确认 Debug Trace 能脱敏，不是真实 Credential。
- 全部文件均小于 10 MB。
- 临时 `git add --all` 检查没有暂存被禁止的文件。`data/` 中只有两个 `.gitkeep`。

## Streamlit Compatibility

当前版本不兼容 Streamlit Community Cloud。

网页入口由 Next.js 提供，API 由 FastAPI 提供，两者需要 Node.js 和 Python 两个常驻进程。仓库没有 Streamlit 入口，运行依赖中也没有 Streamlit。添加占位 `streamlit_app.py` 无法承载现有页面、路由与交互。

保留现有 UI 的部署方式需要能同时运行 Node.js 与 Python，并为 `data/` 提供持久磁盘。如果目标必须是 Streamlit，需要重写一层 Streamlit 页面，再复用现有 Python Schema、解析、OCR、Pipeline 和导出服务。

## Release Checklist

- [x] 发布包与原项目分离，未修改或删除原项目用户数据。
- [x] README、架构、部署兼容性和本地启动说明齐全。
- [x] Python 与 Node 依赖可从锁文件和依赖清单重建。
- [x] TypeScript、Next production build 和 53 个 Python 测试通过。
- [x] Landing、Workspace、Profile 与 API HTTP Smoke Test 通过。
- [x] 六个正式 Prompt 只有一个 Source of Truth。
- [x] SQLite Migration、Local OCR、Long JD 和 Generation Snapshot 代码齐全。
- [x] Debug 默认关闭，API Key 与请求头脱敏规则保留。
- [x] 文件、Secret、个人路径、大文件和 Git ignore 检查通过。
- [x] 运行与验证产物已从发布包移除。
- [x] Streamlit 不兼容结论如实记录，没有伪造入口。

## 已知问题

- Streamlit Community Cloud 无法直接部署当前架构。
- 当前产品面向个人本地使用，没有登录、多租户和远程数据隔离。
- 远程服务器通常没有桌面 keyring，API Key 可能只能在进程内临时保存。
- 没有持久卷的云主机会在重启或重建后丢失 SQLite 和上传文件。
- FastAPI 测试客户端提示未来将从当前 `httpx` 迁移到 `httpx2`。当前测试和运行均正常，后续升级 FastAPI/Starlette 时应重新验证。
- 发布验证在 Windows x64 完成，尚未在 Linux 容器上实际执行 OCR 冒烟测试。
- 仓库没有附带开源许可证。公开上传不会自动授予他人修改或再发布的权利。
