# 部署兼容性报告

## 结论

这份发布包可以作为公开 GitHub 仓库的源码，也可以在干净的本地环境中独立安装和运行。

Streamlit Community Cloud 不能直接运行当前版本。项目的网页入口是 Next.js，API 入口是 FastAPI。两者需要独立常驻进程，Streamlit 的单一 Python 应用入口无法启动并托管现有 Next.js 页面。

## 实际入口

| 部分 | 技术 | 入口 | 默认地址 |
| --- | --- | --- | --- |
| Web | Next.js 16 + React 19 | `frontend/app` | `http://localhost:3000` |
| API | FastAPI + Uvicorn | `backend.main:app` | `http://127.0.0.1:8000` |
| 数据 | SQLite + 本地文件 | `data/app.db`、`data/resumes/`、`data/jobs/` | 项目本地目录 |
| 密钥 | Python keyring | 操作系统凭据库 | 当前操作系统账户 |

Windows 可用 `scripts/start-local.ps1` 同时管理两个进程。其他系统可分别运行 Uvicorn 和 npm 命令。

## Streamlit Gate

| 检查 | 结果 | 说明 |
| --- | --- | --- |
| 是否存在 Streamlit 页面入口 | 不存在 | 项目有意移除了旧 Streamlit 入口 |
| Python 依赖是否包含 Streamlit | 不包含 | 当前 UI 由 Next.js 提供 |
| 单个 Python 进程能否展示完整页面 | 不能 | Next.js 需要 Node.js 进程 |
| Streamlit Cloud 能否按当前结构启动 | 不能 | 平台入口模型与当前双进程结构不匹配 |
| 添加占位入口能否解决 | 不能 | 占位页无法承载现有路由、组件与浏览器交互 |

因此，发布包没有 `streamlit_app.py`、`packages.txt` 或伪造的 Streamlit 配置。

## 最小可行部署路径

### 保留现有页面

在能运行 Node.js 和 Python 的主机上部署两个进程。前端通过 `NEXT_PUBLIC_API_BASE` 找到后端，后端通过 `RESUME_MATCHER_CORS_ORIGINS` 放行前端域名。服务器还需要持久磁盘保存 `data/`。

这条路径保留当前黑白 UI、页面路由、复制下载和 Profile 历史视图。远程开放前仍要补充访问控制、HTTPS、服务端密钥管理和按用户隔离数据。

### 必须使用 Streamlit

需要新增真正的 Streamlit 展示层。可复用 Pydantic Schema、文档解析、OCR、AI Pipeline、SQLite Model 和导出服务；Next.js 组件、CSS、浏览器状态与路由需要重写。页面外观和交互会发生变化。

## 云端与 Local-first 的差异

- 服务器磁盘属于部署者，无法继续称为使用者设备上的本地存储。
- 免费或无持久卷的运行环境可能在休眠、重启或重新构建后清空 SQLite 与上传文件。
- 无桌面服务器上的 keyring 可能不可用。当前安全降级只把 Key 留在后端进程内，进程重启后需重新填写。
- 当前应用没有登录、注册、多租户和权限边界，不适合直接开放给互不信任的多人使用。
- OCR 会占用 CPU 和内存。并发处理扫描 PDF 时，需要为资源设上限。

## 系统依赖判断

当前解析与 OCR 使用 PyMuPDF、RapidOCR 和 ONNX Runtime 的 Python wheel，不调用 Tesseract、LibreOffice 或 Poppler 命令行程序。发布包因此不提供 `packages.txt`。部署到目标 Linux 镜像时仍应实际执行安装和 OCR 冒烟测试，确认该镜像、CPU 架构与 wheel 兼容。

## 发布验证

最终验证结果会在打包完成后写入 `RELEASE_AUDIT.md`。该记录只包含环境版本、命令结果、文件数量和安全扫描结论，不包含 API Key、请求头、Cookie、简历或 JD 内容。

