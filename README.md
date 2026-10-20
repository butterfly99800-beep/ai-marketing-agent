# AI 智能营销 Agent

Python FastAPI + 静态前端 + Node.js/Remotion 渲染。保留文字资料及真实网页两种制作方式、对话规划、资料上传、配音/配乐匹配和 YouTube 发布运营。

- **Ubuntu 24.04 部署**：[DEPLOY_UBUNTU.md](DEPLOY_UBUNTU.md)
- **公开三条制作对话与最新成片**：部署后的 `/showcase.html`，无需账号。
- **Windows**：仍使用 `启动智能营销.cmd`，原本机配置兼容。
- **生产**：默认单 Uvicorn 进程、单渲染并发；2GB 服务器建议云端配音，模型单独下载。
- **敏感数据**：密钥、OAuth JSON、SQLite 和工作目录不进 Git。`.env.example` 仅为模板。

---

最新：新增独立YouTube发布与运营工作台，入口 http://localhost:8020/operations.html 。启动脚本同时维护8000回调。详见21_YouTube发布运营与联网修复.txt。

> 最新升级：音色与配乐库、整片音色锁定、无配音、多平台独立画幅、快剪素材复用和5种构图已经接入。使用输入框的「创作设置」和「音色与配乐库」。详见18_声音与剪辑制作升级.md、19_音色与配乐授权指南.txt。默认先补充最多3项信息，只给一个最终方案，点击开始生成才制作。历史文档记录此前版本行为，以本段及18/19文档为准。

# 幕言 · 智能营销 Agent（第一阶段）

项目位置：D:\项目\货代\ai营销\智能营销agent。它是独立的新项目，旧 agent 项目保持原样。

## 使用

双击根目录 `启动智能营销.cmd`，浏览器打开 http://127.0.0.1:8020。窗口保持运行；关闭该窗口会停止服务。

1. 选择“文字资料”或“网站介绍”，输入资料或一个公开网址，选择抖音、YouTube、YouTube Shorts。
2. 与导演聊受众、目标和风格。可以继续补充资料、调整风格或要求给出方案。
3. 查看分镜、图片数量和视频数量，确认后点击“确认方案，开始制作”。默认只有图片/截图，不调用视频模型。
4. 需要真实物体动作时，先勾选视频预算并在对话中要求短片段。最多2段×5秒，总AI视频画面不超过整片40%。
5. 成片可以播放和下载。开启原创配乐时同时输出无配乐版，保留旁白和音效。刷新后从左栏恢复项目。

“已配置”表示密钥字段存在，实际权限和余额以服务商响应为准。已用当前密钥验证了DeepSeek和万相图片。

## 已实现

- DirectorAgent：DeepSeek多轮对话、风格沟通、结构化分镜、原文证据检查、人工确认。
- ProductionAgent：图片优先、素材状态保存、复用已提交任务、旁白、运镜、字幕、音效、配乐、MP4合成和完整解码验收。
- 文字路线：万相文生图，每次明确n=1，按分镜生成场景，再做推进、平移、轻度侧斜、聚焦和品牌压印。
- 网站路线：读取公开网站及最多两个同源功能/文档链接，保存真实截图和页面内容，再做截图宣传介绍。
- 平台选择：抖音/Shorts输出720×1280竖屏；YouTube输出1280×720横屏，30fps，15–45秒。
- 历史记录：SQLite保存项目/对话/当前计划/任务ID/进度；素材按项目和分镜版本隔离。
- 默认只在本机127.0.0.1:8020运行，前端不接触API密钥；修改请求校验Origin，静态目录不包含配置文件。

## API与模型配置

读取根目录 `api保存位置.env`；已兼容现有“服务名＋下一行密钥”格式，不改写原文件。也支持标准 KEY=VALUE。

可选字段：

```
DEEPSEEK_API_KEY=你的密钥
DASHSCOPE_API_KEY=你的密钥
DEEPSEEK_MODEL=deepseek-flash
WAN_IMAGE_MODEL=wan2.2-t2i-flash
WAN_VIDEO_MODEL=wan2.2-i2v-flash
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com
```

当前DeepSeek账号实际返回 `deepseek-flash` 和 `deepseek-v4-pro`，默认使用前者。万相按原生异步API提交、查询和下载，不依赖聊天里的图片生成工具。改配置后请停止启动窗口再启动，不能仅刷新网页。

## 结构

- app/main.py：本地HTTP接口。
- app/director.py：导演Agent及对话状态。
- app/deepseek.py：独立LLM适配。
- app/wan.py：独立万相图片/图生视频适配。
- app/schemas.py：分镜字段、字数、时长、视频占比限制。
- app/producer.py：独立生产Agent。
- app/media.py / renderer/capture.cjs：网站截图、公开地址检查、下载、旁白。
- prompts/director.txt：独立导演Prompt。
- renderer/src/index.tsx：Remotion镜头、字幕和时间线。
- renderer/ATTRIBUTION.md / SHOTCRAFT_LICENSE：镜头参考与声音归属。
- web：对话工作台。
- tests：自动化测试。
- work/studio.sqlite / work/projects：本地数据与素材。
- .runtime/python_deps / renderer/node_modules：本机依赖，不提交版本库。

## API说明

- GET /api/config：模型名称、配置状态和数量上限，不返回密钥。
- POST /api/projects：mode、source、platform。
- GET /api/projects：项目历史。
- GET /api/projects/{id}：对话、方案和当前状态。
- POST /api/projects/{id}/messages：text、video_budget。
- POST /api/projects/{id}/render：revision、allow_video、bgm。旧版本确认被拒绝；已完成的同版本请求不重复执行。
- GET /api/projects/{id}/video：配乐版/主版本；bgm=false取无配乐版。

## 验证结果

25项自动化测试通过，覆盖JSON结构、图片数量、5秒视频参数、视频占比、字数/品牌停留、预算确认、方案更新、重启记录保留和重复确认。
视频工程TypeScript检查通过。
浏览器验证：真实DeepSeek首轮对话、确认前不自动生成素材、MP4播放、刷新恢复、手机布局、无配乐下载通过。
真实API联调：DeepSeek沟通和两条分镜；万相生成3张图片；文字路线和网站路线各完成18秒MP4，并输出配乐/无配乐两版。
可选视频接口已完成原生请求适配及契约测试，但为了节省费用，本次没有调用付费视频模型，不声称已验证实际视频生成。
独立终检发现并修复视频占比、长品牌入场、浅色标识及长文溢出边界；复核通过。

## 成本与恢复

图片最多6张，默认不用AI视频。开启视频后最多2个5秒片段且≤40%整片；已提交任务ID立即保存。后续查询超时可继续查已有任务。若提交响应不明且没有任务ID，不自动重复提交，防止重复扣费。

服务停止会结束自身的渲染子进程并保留状态。重启后显示“等待恢复”，再确认重试。素材和旁白可复用。要更换方案请继续对话；新分镜版本使用独立素材目录，新的素材调用仍会计费。

## 当前边界

平台策略是常见制作形式，不是实时热门榜或爆款保证。未来可接入可核验的趋势来源和用户参考片。
网站目前为公开页面/文档截图介绍，不登录、不提交表单，不伪造已验证的操作教程；遇到反爬、验证码或登录页面可能失败。
图片运镜不等于人物/船舶真实运动。AI图片和AI视频明确标记示意，不冒充企业实拍。
图片生成内容与字幕仍需用户核对；事实证据检查是逐字引用校验，不能代替完整语义审查。
本阶段是本机单用户版本，未实现公网账号、团队权限或分布式任务队列；网站地址过滤不是经过对抗测试的完整出网隔离。
旁白使用本机Windows Huihui/Zira；目前未接入云端高质量配音，也不做自动发布。

## 官方参考

DeepSeek JSON接口：https://api-docs.deepseek.com/guides/json_mode/
万相文生图：https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference
万相图生视频：https://help.aliyun.com/zh/model-studio/legacy-image-to-video-api-reference/
video-shotcraft镜头配方：https://github.com/Vincentwei1021/video-shotcraft
平台形式参考：https://ads.tiktok.com/business/creativecenter/quicktok/online/5_creative_tips/pc/en 、https://support.google.com/youtube/answer/15424877 。

## 多样化转场升级

转场选择按平台、素材、服务信息和品牌结尾执行，见 [12_平台剪辑与多样转场.md](12_平台剪辑与多样转场.md)。图片接动态镜头采用构图连续切换，场景变更采用侧向推移，图形内容用斜边面板揭示，品牌结尾柔和叠化；短视频过渡速度更快。转场不增加图像/视频模型调用。

验证规则：在renderer目录运行 `node transition_check.cjs`。

## 工作室体验升级

右侧方案和制作记录可折叠，进度只按实际完成步骤更新；预计剩余时间为经验范围，服务商变慢时会提示超时长。15–60秒支持整数选择，方案及合成按所选总时长执行。

分析与制作由服务端后台任务执行，切换项目、标签页或关闭浏览器页面不会取消；启动窗口和电脑需保持运行。服务停止仍会中断本地合成，已提交素材任务和文件保留，可继续制作。

前端按变化局部更新，保留播放器与草稿；后台响应绑定项目ID，避免切换后旧响应覆盖新项目。列表返回轻量摘要，文件复制移到后台线程。Windows本机localhost新连接实测约2秒，127.0.0.1约20毫秒，启动入口改用127.0.0.1。详细记录见13_工作室体验升级.md。

## 内容驱动导演升级
已加入DeepSeek结构化导演、近期作品防重复、六种选曲、九种运动、五种转场、高清正文截图和成片检查关键帧，详见 [14_内容驱动导演升级.md](14_内容驱动导演升级.md)。平台策略仍为常见形式，未接实时热门榜。新项目自动按内容推荐；历史作品保留。

