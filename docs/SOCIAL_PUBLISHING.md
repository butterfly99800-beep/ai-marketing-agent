# 成品发布工作台

2026-11-06。默认首页改为成品上传与发布，旧制作工作室保留在 `/studio`，原 YouTube 数据、评论、账号页保留在 `/operations.html`。

## 已实现

- 直接流式上传 MP4，默认最大 150MB，落盘并解码抽帧验证；不调用图片或视频生成服务。与原作品库共用账号归属和成品预览。
- DeepSeek 根据用户提供的成品介绍、受众、语言，为选择的平台分别输出一份标题、正文、搜索关键词、标签。没有视频理解服务，不声称看懂视频。生成格式及平台长度验证失败会修复一次，网络重试复用现有传输层；结果存入 SQLite，可再次打开和编辑、导出。
- 覆盖 YouTube/Shorts、TikTok、Instagram Reels、Facebook Reels、X、LinkedIn、Pinterest、Threads、Snapchat Spotlight 的文案档案。字段长度是本工作台保守编辑限制，并非各平台所有账号的实时上限。
- YouTube 复用已有 OAuth 和断点上传；到时提交上传，关键词进入 snippet.tags。其他平台仅文案、导出和待授权排程，不提供虚假授权按钮，也不执行发布。取得授权后还需要实现和测试平台适配器，不能只填 Key 就宣称完成。
- 排程带时区，UTC 入库，浏览器显示本地时间；队列每 15 秒检查一次。默认不同作品间隔 6 小时，可选 12/24/48 小时；同作品可跨平台，一次加入所选平台，同平台后续作品顺延。每个账号同一个作品只排一次；上传的相同二进制内容另存文件名也会阻止重复。
- 任务原子认领，状态及 YouTube job id 持久化；服务在提交边界重启时进入待核对，不盲目重传。已提交失败的上传可到旧发布运营页恢复原会话。未提交任务可取消；待授权任务不会自动改成已授权。

## 排程含义和限制

没有“隔几小时就不被限流”的官方通用保证。间隔用于经营节奏，不用于规避规则。禁止把同一视频改一下标题无限循环发。该实现不保证关键词搜索第一，不购买排名，也不操作虚假互动。YouTube 实际上线还取决于上传耗时、处理时间、审核和实际可见性，队列时间是开始提交时间，不是精确上线承诺。

自动关键词来自用户提供的资料，不代表已查询实时热度。流量优化下一步应结合账号真实数据、受众时区及不同作品表现，进行有限对照实验，而不是固定高频重复发布。

## 官方平台资料（查询日 2026-11-06）

| 平台 | 发布接口 / 接入条件 | 官方来源 |
|---|---|---|
| YouTube / Shorts | videos.insert，现有频道授权；Shorts 归类由平台决定 | https://developers.google.com/youtube/v3/docs/videos/insert |
| TikTok | Content Posting API；审核前有私密发布限制，须符合用户控制和披露要求 | https://developers.tiktok.com/docs/en/content-sharing-guidelines |
| Instagram | 专业账号发布 Reels；需相应发布权限 | https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api |
| Facebook | Page Reels 发布；需 Page 权限；Meta 文档抓取时返回 429，具体权限在接入阶段复核 | https://developers.facebook.com/docs/video-api/guides/reels-publishing/ |
| X | 帖子与媒体发布；自动化不得发布重复或高度相似内容 | https://help.x.com/en/rules-and-policies/x-automation |
| LinkedIn | Videos API + Posts API；按成员/组织申请对应权限 | https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api |
| Pinterest | 上传视频后创建 Pin；封面及相应账号授权 | https://developers.pinterest.com/docs/work-with-organic-content-and-users/create-boards-and-pins/ |
| Threads | 创建媒体容器、发布；独立 Threads 授权 | https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api |
| Snapchat | Public Profile / Spotlight 资产 API；先核实账号和应用接入资格 | https://developers.snap.com/marketing-api/Public-Profile-API/ProfileAssetManagement |

搜索相关性参考：https://support.google.com/youtube/answer/16090438 。YouTube 反垃圾内容规则：https://support.google.com/youtube/answer/2801973 。这些规则不能被理解为允许任意高频重复发布。

## Ubuntu 更新

1. `git pull --ff-only origin main`
2. `.env` 可选 `SOCIAL_UPLOAD_MAX_MB=150`。2GB / 8GB 磁盘建议保持此限额；不要长期堆积大文件。
3. 在**服务器实际启用**的 Nginx HTTPS 站点配置设置 `client_max_body_size 160m;`，不要仅修改仓库模板。保持 `proxy_read_timeout 300s;`。运行 `sudo nginx -t` 成功后 `sudo systemctl reload nginx`。
4. `sudo systemctl restart ai-marketing-agent`
5. 使用一个 Uvicorn worker（原部署已如此）。排程依赖服务持续运行；停机错过的任务在启动后补交，不保证精确发布时刻。数据库 `work/studio.sqlite` 及 OAuth 加密密钥仍须持久化，不提交 GitHub。

没有创建真实外部帖子。新增平台 OAuth、实际媒体规格验证、商用应用审核和真实发布回执验证留待各平台授权接入时完成。现有视频作品和生成服务代码均保留。

## 本次验证

- 全量 123 项 Python 测试通过；最后界面调整后重新运行 8 项发布专项测试通过，JavaScript 语法检查通过。
- 使用隔离临时数据库、合成纯色 MP4 和模拟文案，实际浏览器验证了登录、上传、九平台文案展示和桌面/390px 手机布局；没有页面脚本错误或横向溢出。文案支持折叠。
- 自动审批拒绝了向 DeepSeek 发送具体测试产品资料的真实调用；因此本次未验证真实模型输出质量，也未声称外部平台发布成功。浏览器文案由本地拦截的测试数据提供，后端格式和排程由集成测试验证。
- 未登录 Ubuntu 服务器，未宣称已部署。
