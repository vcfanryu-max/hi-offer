# Release Audit

审计日期：2026-08-13。

## 当前状态

- 应用源码已位于仓库根目录，不再嵌套在 `github_release/`。
- 已补充 `.gitignore`、`.env.example`、运行数据占位目录和 `.dockerignore`。
- 已补充前后端 Dockerfile、Docker Compose 和 GitHub Actions CI。
- 未发现真实 API Key、GitHub Token、私钥或超过 10 MB 的受控文件。
- TypeScript 类型检查通过。
- Next.js 16.2.11 production build 通过，静态生成 `/`、`/workspace`、`/profile` 与 `/dev/prompts`。
- Docker Compose 配置解析通过。

## 尚需由 CI 复验

本次 macOS 审计环境未完成完整 Python OCR 依赖下载，因此 Python 测试结果不沿用旧发布记录。首次推送后，GitHub Actions 将在 Python 3.12/Linux 上安装依赖并运行：

```text
python -m pip check
python -m pytest -q
npm ci
npm run typecheck
npm run build
```

## 部署边界

当前 Docker Compose 配置适合个人或受信任的私有环境。应用没有登录、多租户和按用户数据隔离，不能直接作为公开多人服务。生产部署还需要 HTTPS、持久存储、备份、限流和服务端密钥管理。

Streamlit Community Cloud 不能直接运行当前 Next.js + FastAPI 双进程架构。

## 法律状态

仓库尚未附带开源许可证。公开可见不代表自动授予复制、修改或再发布权利；许可证应由仓库所有者选择后添加。
