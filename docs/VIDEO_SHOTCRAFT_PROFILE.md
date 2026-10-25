# 默认剪辑策略：video-shotcraft

创意/剪辑来源已切换为video-shotcraft；Remotion仅保留为渲染引擎。没有删除渲染组件或修改账号、发布与素材授权。

执行层：新方案记录editing_profile=video-shotcraft，渲染参数携带该值；未标记的旧方案在重渲时也默认采用此规则。照片镜头按建立、非线性运动、真正静止三个阶段执行，保留用户指定的焦点与动作。停止自动在push/panel间轮换，常规关系采用直切；已有导演明确指定的转场仍优先。真实页面继续使用PageCam与row-embed的已有实现。

选型层：skills/director-editing.json仅将video-shotcraft列为创作来源，声明已实现映射、素材前提和适用范围；提示词只按这些能力选型。不是把124张镜头卡全部自动实现，也不等于照搬Ink Press模板。采用spotlight-hero-card的单主角/动作弧/停留原则，保留用户不需要装饰框和希望轻快节奏的约束。

验证：TypeScript检查、镜头/字幕/转场函数执行测试及本地竖版静帧渲染通过；Python全套回归结果见本次提交说明。未在本轮生成新的付费素材或直接部署云端。已完成MP4不会自动改变；新方案/重渲后使用新规则。
