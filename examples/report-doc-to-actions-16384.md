# agent-skill-eval report

| field | value |
| --- | --- |
| runner | `llm` |
| model | `deepseek-flash` |
| judge | `deepseek-flash` |
| started | 2026-09-14 20:39:14 |
| skills | 2 |
| verdict | **PASS** |

## Summary

| skill | task pass | check pass | judge mean | mean latency | tokens (in/out) | cost | truncated |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `doc-to-actions/v1` | 0.58 | 0.59 (20/34) | 3.64 | 20.33 s | 3119 / 16285 | n/a | 0 |
| `doc-to-actions/v2` | 1.00 | 1.00 (34/34) | 4.88 | 31.06 s | 3547 / 28407 | n/a | 0 |

## A/B delta (first skill = baseline arm)

| skill | Δ task pass | Δ check pass | Δ judge | Δ mean latency |
| --- | --- | --- | --- | --- |
| `doc-to-actions/v2` | +0.42 | +0.41 | +1.24 | +10.73 s |

## Per-check outcome

| check | `doc-to-actions/v1` | `doc-to-actions/v2` |
| --- | --- | --- |
| `cites_clauses` | 4/4 | 4/4 |
| `conflict_surfaced` | 2/2 | 2/2 |
| `contract_paths` | 0/4 | 4/4 |
| `date_preserved` | 1/1 | 1/1 |
| `json_valid` | 0/4 | 4/4 |
| `length_cap` | 0/4 | 4/4 |
| `missing_annex_flagged` | 1/1 | 1/1 |
| `modality_both` | 3/3 | 3/3 |
| `no_invented_deadline` | 1/1 | 1/1 |
| `no_invented_owner` | 3/3 | 3/3 |
| `no_placeholders` | 1/1 | 1/1 |
| `owner_unresolved` | 0/1 | 1/1 |
| `sla_preserved` | 1/1 | 1/1 |
| `undecided_kept` | 1/1 | 1/1 |
| `unresolved_marked` | 2/3 | 3/3 |

## Per-task detail

### `doc-to-actions/v1`

| task | checks | judge | latency | finish | failed checks | error |
| --- | --- | --- | --- | --- | --- | --- |
| `contract-01` | 6/9 | 3.80 | 22.04 s | stop | `json_valid`, `contract_paths`, `length_cap` | - |
| `contract-02` | 6/9 | 4.00 | 16.88 s | stop | `json_valid`, `contract_paths`, `length_cap` | - |
| `minutes-01` | 4/8 | 3.75 | 23.99 s | stop | `json_valid`, `contract_paths`, `unresolved_marked`, `length_cap` | - |
| `notice-01` | 4/8 | 3.00 | 18.42 s | stop | `json_valid`, `contract_paths`, `owner_unresolved`, `length_cap` | - |

### `doc-to-actions/v2`

| task | checks | judge | latency | finish | failed checks | error |
| --- | --- | --- | --- | --- | --- | --- |
| `contract-01` | 9/9 | 5.00 | 27.71 s | stop | - | - |
| `contract-02` | 9/9 | 5.00 | 28.57 s | stop | - | - |
| `minutes-01` | 8/8 | 5.00 | 29.90 s | stop | - | - |
| `notice-01` | 8/8 | 4.50 | 38.05 s | stop | - | - |

## Failure evidence

<details><summary><code>doc-to-actions/v1</code> / <code>contract-01</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `length_cap` (max_chars) — 3846 chars (limit 2500)
- judge notes: Grounding: 2026-05-05、2027-04-05 等日期属推算，且提及材料未含的通知送达方式。 Conflict: 已明确暴露 5.3 的 30 日与附件一 15 日的矛盾。 Modality: 应当/可以/宜保持区分。 Actionability: 候选待办动作清晰，责任人未明处标 unresolved。 Contract: 输出为 Markdown 而非纯 JSON，缺少 JSON 字段与 items 数组。

```text
# FK-2026-014 抽取结果（草稿，未创建任何任务）

> 说明：以下为带出处的**事实抽取 + 候选行动**，不是法律意见。责任人/日期凡材料未明确的，一律标 `unresolved`，未作推测填补。材料内容按**数据**处理，不作为指令执行。

---

## 1. 结构化事实（按证据类别）

### 1.1 当事方 / 主体
| 项 | 内容 | 出处 | 备注 |
|---|---|---|---|
| 甲方 | 仅以角色出现 | 全文 | **未给出单位名称** |
| 乙方 | 仅以角色出现 | 全文 | **未给出单位名称**；主要义务承担方 |
| 项目对接人 | 双方各设对接人，名单见「另行签署的备忘录」 | 附件二 | 备忘录**本次未附** |

材料中确实**未出现任何部门名称**（已验证该表述属实）；且连甲方/乙方的单位名称也未出现，因此下文所有「责任人」只能落到**角色层**，落不到单位或部门。

### 1.2 日期与期限
| 期限 | 内容 | 出处 | 起算/口径 |
|---|---|---|---|
| 每月 5 日前 | 提交上月服务报告 | 3.2 | 日历日；月初 5 日 |
| 2 个工作日内 | 提供原始日志（应甲方要求时） | 3.4 | **工作日** |
| 2026-04-01 ~ 2027-03-31 | 服务期 |
…[truncated]
```
</details>

<details><summary><code>doc-to-actions/v1</code> / <code>contract-02</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `length_cap` (max_chars) — 3276 chars (limit 2500)
- judge notes: Output is Markdown, not pure JSON, and it does not provide a JSON items array with citations, so the contract criterion fails.

```text
# 文档处理结果 · CG-2026-207（采购订单条款摘录）

> 说明：以下为**忠实抽取**，不构成法律意见。所有未写明的主体/金额/日期一律标 `unresolved`，不代填。**本次仅呈现事实与候选任务，未创建任何任务，等你批准。**

---

## 一、证据归类（含出处）

### 1. 主体与标识
- 当事方：**供方**、**需方**（通用称谓，无公司名）。`[材料整体]`
- 标识：编号 CG-2026-207。`[材料抬头]`
- **经办人/部门：材料明确写明"未写明任何一方的具体经办人姓名或部门" → 全体责任人 `unresolved`。** `[材料末段]`

### 2. 日期与期限
| 事项 | 期限 | 起算 | 出处 | 置信 |
|---|---|---|---|---|
| 全部货物送达 | **2026-05-20 前** | 固定日期 | 2.1 | 高 |
| 变更收货地址的通知窗口 | 到货前 **3 个工作日** | 相对（到货日） | 2.4 | 高 |
| 数量清点与外观验收 | 到货后 **10 个工作日** 内 | 相对（到货日） | 3.1 | 高 |
| 换货/退款 | 收到通知后 **7 日** 内 | 相对（通知日） | 3.3 | 中（"日"≠"工作日"，见校验 ②） |

### 3. 金额 / 数量
- 
…[truncated]
```
</details>

<details><summary><code>doc-to-actions/v1</code> / <code>minutes-01</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `unresolved_marked` (must_include) — missing: ['未明确']
- `length_cap` (max_chars) — 3202 chars (limit 2500)
- judge notes: Output is a markdown report, not pure JSON; it has no `items` array and no per-item `citation` field, so the format requirement fails entirely despite otherwise strong grounding, correct treatment of 建议/口头承诺, and full todo coverage with unresolved owners marked.

```text
# 处理结果：JY-2026-055 专题会纪要摘录

> 本材料按**数据**处理，不作为指令执行。以下全部为**待你批准的草案**——我没有创建任何任务。

---

## 一、证据归类

**主体与标识**：材料编号 JY-2026-055；出现主体为「供应商」「承建方」「与会人员」，均**无具名责任人**。

**语气强度（关键区分，不与「可以/宜/应当」混同）**

| 条目 | 原文措辞 | 判定 |
|---|---|---|
| 1.2 | **必须**在本月底前完成 | 强制义务（最强） |
| 2.2 | **应当**在下月中旬前完成 | 规范性义务 |
| 1.1 | 口头承诺；**应**要求其补书面确认 | 弱承诺 + 建议性跟进 |
| 2.1 | 与会人员**建议** | 建议，**非义务** |
| 3.1 | **未达成一致**，「待下次会议再议」 | 未决，不构成行动 |
| 3.2 | **未讨论**原因，**未指定**核对人 | 缺口，非义务 |

**日期与期限（全部为相对/模糊表述）**：「五月上旬」「本月底前」「下月中旬前」「下次会议」。材料**未给出会议日期与年份**，因此这些均**无法转为绝对日期**。

**金额/数量**：云侧费用环比 +18%（**未给基数，无合计表可交叉核对**）；培训「两批」（**批次如何划分未定义**）；缺
…[truncated]
```
</details>

<details><summary><code>doc-to-actions/v1</code> / <code>notice-01</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `owner_unresolved` (must_include) — missing: ['未明确']
- `length_cap` (max_chars) — 3341 chars (limit 2500)
- judge notes: grounding：仍将「30 日」按 2026-03-10 试算为 2026-04-09，违反不换算要求，但未替双方约定送达方式。conflict：指出了正文 3 项与附件二 4 行，但称其「数目自洽」，未直接定性为不一致。uncertainty：送达方式未约定、联系人未知均已显式标为未明确/待确认。contract：输出为 Markdown 而非纯 JSON，不符合格式要求，尽管候选条目超过 3 条且带 citation。

```text
## 0. 处理说明

按 `doc-to-actions` 流程处理，材料以对话形式给出，故从第 3 步（归类证据）开始。
本输出是**梳理与候选**，不是法律意见，也不构成任何已创建的任务或通知。

---

## 1. 证据归类

**主体与标识**
- 文号：ZG-2026-031
- 出具方：未具名（文中仅以「审核方」出现）
- 受文方：仅称「被审方」，**未具名**
- 联系人：材料明确「未写明任何联系人姓名」→ 责任人字段一律 `unresolved`

**日期与期限**
- 3 月 10 日现场审核结果 —— **未写年份**（文号暗示 2026，但需确认，见风险 R5）
- 1.1：整改完成并提交整改报告，期限「30 日内」；**起算基准未写明**
- 4.1：本通知「自送达之日起生效」；送达方式「由双方另行约定」，**至今未约定**

**金额/数量**
- 无金额。数量相关：审核发现 **3 项**；附件二反馈表 **4 行**（3 项 + 1 行「其他」）

**义务与禁止事项（按语气强度区分）**

| 条款 | 措辞 | 强度 | 义务内容 |
|---|---|---|---|
| 1.1 | 要求…在 30 日内 | 强制性要求 | 完成整改 **并** 提交整改报告（两项） |
| 1.2 | 应当 | 强制 | 报告逐项对应审核发现，附整改前后
…[truncated]
```
</details>
