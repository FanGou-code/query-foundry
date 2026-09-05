# query-foundry

主仓 `aicomp-multimodal-grounding` 的 v5 query 生产线。私有仓，无 remote，永不 push。

## 职责

装整条 v5 生成线（三权分立：教师只看 / 代码只说 / 规划器只分）：

- Phase 0：test 句式挖掘 → `spec/style_spec.json`（语法规范）
- Phase 1：普查协议（教师 GLM-4.6V 只输出结构化观察，不写 query）
- Phase 2：本地组装器（query 文本由代码拼装，不由教师采样）
- Phase 3：规划器（按 style_spec 配额分配句式，分布审计）
- Phase 4/5：全量 run 与重训在主仓执行，本仓只交产物包

## 边界

- 可读主仓 `data/`：`Train` 图序列与 `data/Test/queries/queries.json` 文本（官方下发件）。
- 永不读 `gt-analysis`（其脚本、数据、结论一概不进本仓）。
- 产物包 = query + bbox + 出身字段 + 分布审计报告 + 语法版本 hash，交回主仓薄入库口；
  主仓校验后编 annotation run-id 落 `outputs/annotations/`。
- 语法版本 hash 进主仓 run 指纹（替代原 prompt hash），溯源链不断。
- API_KEY 只走环境变量，永不入库。

## 红线（v5 定案，改动须管理员确认）

- val 719 永远只用真框；伪样本进 val = 教师给自己打分的自证循环。
- 每条样本带出身字段（真标 / 伪 peer），可分开称重、可消融。
- 伪样本 真:伪 ≈ 1:1 起步。
- 同一 peer 只取 2-3 帧（近重复灌水无益）。
- 涨分归因 = 双 run 对照（带伪 / 不带伪，其余全同）。
- 只造事实支撑的句子；凑不够的句式缺口用别的句式补，不硬编（封顶只是保险丝）。
- MT 怪癖只学高频（机械阈值，如 test 中出现 ≥20 次），低频语病不学。

## 结构

```
scripts/  挖掘与生产线脚本
spec/     style_spec.json（test 句式规范）与后续语法版本
docs/     handoff.md（状态与日志）
```
