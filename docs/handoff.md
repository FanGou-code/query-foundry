# 交接文档（query-foundry）

> 本仓 = 主仓 v5 query 生产线。边界与红线见根 README。
> 上游定案见主仓 `docs/handoff.md` 与 `/tmp/handoff-2026-09-05-query-foundry.md`（2026-09-05 会话交接）。

## 当前状态（2026-09-05）

- 仓已建：私有、无 remote，规格对齐 gt-analysis（永不 push）。
- Phase 0 完成：`spec/style_spec.json` 草案（status=draft-awaiting-admin-review）+
  `spec/vocab_freq.json` 全词表，由 `scripts/phase0_mine_test_style.py` 从
  `data/Test/queries/queries.json` 文本层挖出（只读 `query` 字段，sha256 入 spec 溯源）。
  **待管理员过目冻结。**
- Phase 1（普查 JSON schema + 20 序列试点方案）未开始。

## 交接日志

### 2026-09-05 Phase 0：test 句式挖掘（草案待审）

- 动因：v5 定案的 Phase 0——语法克隆的事实基础；只读 queries.json 文本，不触 GT。
- 改动：`scripts/phase0_mine_test_style.py`（纯 stdlib，可复现）、
  `spec/style_spec.json`、`spec/vocab_freq.json`。
- 验证：总数 9555 与既有读数一致；重复率 0.076、词数均值 10.33、序数桶 335.6‰
  均与既往 handoff 基线互洽（7.6% / 10.3 / 33.5%）。
- 关键读数（供管理员审阅 spec 时对照）：
  - 框架集中：`from left to right` 496 / `from right to left` 449 近对称成对；
    `on the left/right side of the` 家族 ~600；`closest to the camera` 354 对
    `farthest from the camera` 39（5.5:1 不对称）；`the far right/left` 288/255
    是 extreme 位置的独立主力框架；`of the image` 303 作画幅锚点；camera 锚定 691。
  - 深度行句式在 test 几乎不存在：`front row`/`back row` 各 1 次，`row` 43 次全是
    物理行（a row of X）。现行 prompt 的 `depth row` cue 不属官方方言。
  - 桶级（草案文本分类器）：序数 335.6‰、空间 329.0‰、属性动作 232.8‰、距离 102.6‰。
  - 骨架多样性：unique 5353，top60 覆盖仅 27%——长尾在 <X> 槽位填充，框架本身集中。
  - MT 错误低频：非 ASCII 中文夹杂 32 次（唯一过 ≥20 阈值的错误怪癖）、邻接重复词
    14、撇号脱落（mans）8、冠词误用 4、双空格 3；高频层的 MT 特征在框架结构本身，
    不在语法错误。
- 下一步：管理员审阅冻结 style_spec.json → Phase 1 普查协议 + 20 序列试点方案。

### 2026-09-05 建仓

- 动因：v5 生成策略定案（三权分立），训练全流程只吃标注产物，生产线拆出主仓。
- 改动：README（边界与红线）、docs/handoff.md、scripts/、spec/ 骨架；git init（main，无 remote）。
- 验证：git init 成功；尚无代码，无测试。
- 下一步：Phase 0 挖掘 → style_spec.json 草案 → 管理员审阅冻结 → Phase 1 普查协议草案。
