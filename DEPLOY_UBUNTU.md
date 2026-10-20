# Ubuntu 24.04 生产部署

目标：Python 3.12 / Node.js 22 / npm 10，`/home/ubuntu/ai-marketing-agent`，`https://wyf.suiyizou.xyz`。
这份配置不修改 Windows 启动方式，不迁移本机账号或 Google Token。

## 1. 安装与目录

使用 ubuntu 用户，确认 Node.js 22、npm 10 已安装。系统依赖：

```bash
sudo apt-get update
sudo apt-get install -y python3.12-venv python3-pip ffmpeg nginx fonts-noto-cjk fontconfig certbot python3-certbot-nginx
git clone https://github.com/butterfly99800-beep/ai-marketing-agent.git /home/ubuntu/ai-marketing-agent
cd /home/ubuntu/ai-marketing-agent
bash scripts/install_ubuntu.sh
cd renderer
sudo env PATH="$PATH" ./node_modules/.bin/playwright install-deps chromium
cd ..
cp .env.example .env
chmod 600 .env
```

已有 checkout 时，在该目录执行 `git pull --ff-only origin main`，不要重新 clone 覆盖目录。不要把本机 `.runtime`、`node_modules`、SQLite、账号授权文件搬到 GitHub。
`.env` 由 systemd 和 `scripts/run_server.py` 读取；Windows 仍支持原来的 `api保存位置.env`。填写真实 DeepSeek/百炼密钥。运行缓存、上传资料、数据库与生成视频留在 `work/`，必须由 ubuntu 用户持有。

## 2. 先创建操作账号

首次对外开放前运行：

```bash
.venv/bin/python scripts/create_operator.py
```

密码交互输入，不写进命令历史。生产默认 `ALLOW_REGISTRATION=0`，避免公开注册消耗付费接口。管理员可重复运行该脚本创建受信用户；需要开放 SaaS 注册时自行设为 1，并配置相应配额/准入策略。公开样片无需登录，创作、上传及绑定 YouTube 需要工作台账号。

## 3. 启动后台及 HTTPS

```bash
sudo cp deploy/ai-marketing-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-marketing-agent
sudo cp deploy/nginx.conf /etc/nginx/sites-available/ai-marketing-agent
sudo ln -s /etc/nginx/sites-available/ai-marketing-agent /etc/nginx/sites-enabled/ai-marketing-agent
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d wyf.suiyizou.xyz
```

以上链接仅首次创建；已有同名配置先检查再调整。域名 A/AAAA 需正确解析到服务器，云防火墙放行 80/443。FastAPI 仅绑定 `127.0.0.1:8020`；不开放 8020 或 8000。
Nginx 文件是申请证书前的 HTTP 引导配置，certbot 会添加 HTTPS。完成前不要通过 HTTP 登录（生产 Cookie 使用 Secure）。

```bash
curl --fail https://wyf.suiyizou.xyz/api/config
sudo systemctl status ai-marketing-agent
sudo journalctl -u ai-marketing-agent -n 60 --no-pager
```

直接前台运行：`bash scripts/start.sh`。不要同时运行多个实例，禁止 `--workers 2` 或 `--reload`：现有任务锁在进程内。更新代码应先等待任务结束，再重启；中断后原任务编号和素材保留，可在界面继续，不要手工删除任务记录。

## 4. YouTube 生产授权

将唯一 Web OAuth 客户端 JSON **单独上传到服务器** `.env` 指定的 `work/secrets/youtube/`，不要提交 Git。
在 Google Cloud 同一客户端配置授权回调：

`https://wyf.suiyizou.xyz/api/auth/youtube/callback`

`.env` 中 `YOUTUBE_REDIRECT_URI` 必须完全一致。生产回调由 8020 主应用处理，不再运行 8000 本机桥接。启用 YouTube Data API v3 和 YouTube Analytics API，并按 Google 要求配置测试用户或完成应用验证。Windows 原 localhost:8000 回调仍支持。
Google 配置、账号绑定和 HTTPS 证书需要在服务器/Google 控制台完成，本次代码提交不会代替这些步骤。

## 5. 配音模型与 2GB 资源限制

默认先用云端音色 Ethan/Cherry/Serena；只安装核心依赖，不加载本地模型。
如需本地 Kokoro：

```bash
.venv/bin/pip install --no-cache-dir -r requirements-voice.txt
.venv/bin/python scripts/setup_voice_models.py
```

模型约 380MB，下载到 `models/kokoro/`，保留来源、许可与 SHA256 清单。可将已有模型盘挂载到该目录；不要覆盖或删除代码。原 ONNX 中文 G2P 路径保留，已兼容标准 Linux venv，无需 Windows `.runtime/voice_deps`。本地音色是可选依赖，未安装时前端会标为不可用；Windows 系统音色不在 Linux 提供。

2GB 是紧凑配置：Uvicorn 单进程、渲染并发 1、Node 堆 512MB、单次渲染超时 3600 秒。systemd 内存软限 1400MB/硬限 1800MB。建议只进行一个制作任务；多用户、复杂 1080p 合成或本地中文 TTS 可能仍然 OOM，应扩容或将渲染移至专用机器，不能承诺 2GB 可承载任意项目。
先用 `free -h` / `swapon --show` / `df -h` 检查资源。需要 swap 时由管理员在确认磁盘余量后配置；安装脚本不擅自分配大文件。8GB 剩余空间还要留给 venv、npm/Chromium、模型、OS 更新及生成素材，使用 `du -sh work renderer/node_modules .venv models` 定期检查。不要为清空间直接删除 `work/`（包含账号和任务恢复记录）。

## 6. 必须上传与必须保密的内容

- `app/ web/ renderer/src/`、浏览器脚本、锁文件、`prompts/ skills/ scripts/ deploy/`：源代码及运行说明。
- `assets/music-library.json` 和许可证明：配乐筛选与署名所需。
- `renderer/public/audio/`：仅提交启用且已有来源许可的 26 个实际运行文件（约134MB），包含真实音乐与音效；未启用或来源不明的旧音频不上传。
- `models/kokoro/README.md`：模型安装说明；大权重通过下载/挂载提供。
- `.runtime/`：本机安装的第三方运行库，Ubuntu 从 requirements 与 npm lock 安装替代，不能直接复用。
- `work/`：不整体提交！包括 SQLite、加密凭证、Token、用户上传、缓存、临时素材。没有任何本机账号或 OAuth 授权被复制进公开样片。
- `examples/` 旧生成视频退出 Git 跟踪，但本地文件保留；本次不改写已有 Git 历史。

## 7. 公开的三条对话与视频

打开 `https://wyf.suiyizou.xyz/showcase.html`（工作台左侧也有入口），无需登录。
公开样本为最近三个已有成片的对话：复旦 rev1、DREWES rev5、江苏科技大学 rev3。
成片、首镜预览及纯文本制作对话位于 `web/showcase/`，仅包含白名单字段；不上传原始项目数据库、账号 ID、发布草稿凭证、工具日志或授权信息。配乐署名与影片一同展示。

## 8. 验证、备份与更新

```bash
.venv/bin/python -m unittest discover -s tests -q
(cd renderer && npm run typecheck)
.venv/bin/python scripts/check_deployment.py
.venv/bin/python scripts/render_smoke.py
```

这些检查不调用付费生成接口。GitHub Actions 在 Ubuntu 24.04/Python 3.12/Node 22 执行相同核心检查与浏览器安装预检，不使用私钥。
部署后还需使用真实账号做一次制作和 OAuth 绑定验证。公开样片页面可先验证静态资源及视频播放。
备份整个 `work/`（特别是 studio.sqlite 和加密密钥）、私有 `.env` 和 OAuth JSON，并存入私密备份位置；不要上传公共仓库。备份数据库前停止服务或使用 SQLite backup API，不能在写入时只复制单个数据库文件。

参考：[Uvicorn 部署](https://www.uvicorn.org/deployment/)；[Remotion 并发选项](https://www.remotion.dev/docs/options)。
