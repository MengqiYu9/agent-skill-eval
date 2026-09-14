# agent-skill-eval report

| field | value |
| --- | --- |
| runner | `llm` |
| model | `deepseek-flash` |
| judge | `deepseek-flash` |
| started | 2026-09-14 17:54:30 |
| skills | 2 |
| verdict | **PASS** |

## Summary

| skill | task pass | check pass | judge mean | mean latency | tokens (in/out) | cost |
| --- | --- | --- | --- | --- | --- | --- |
| `structured-digest/v1` | 0.38 | 0.38 (9/24) | 3.31 | 6.69 s | 1508 / 5535 | n/a |
| `structured-digest/v2` | 0.50 | 0.50 (12/24) | 1.62 | 8.92 s | 2648 / 8192 | n/a |

## A/B delta (first skill = baseline arm)

| skill | Δ task pass | Δ check pass | Δ judge | Δ mean latency |
| --- | --- | --- | --- | --- |
| `structured-digest/v2` | +0.12 | +0.12 | -1.69 | +2.23 s |

## Per-check outcome

| check | `structured-digest/v1` | `structured-digest/v2` |
| --- | --- | --- |
| `chinese` | 1/1 | 0/1 |
| `cites_sources` | 0/4 | 2/4 |
| `contract_paths` | 0/4 | 0/4 |
| `json_valid` | 0/4 | 0/4 |
| `length_cap` | 4/4 | 4/4 |
| `min_points` | 0/1 | 1/1 |
| `no_claimed_owner` | 1/1 | 1/1 |
| `no_invented_deadline` | 1/1 | 1/1 |
| `no_offtopic` | 0/1 | 1/1 |
| `no_placeholders` | 1/1 | 1/1 |
| `recurring_captured` | 1/1 | 0/1 |
| `undecided_marked` | 0/1 | 1/1 |

## Per-task detail

### `structured-digest/v1`

| task | checks | judge | latency | failed checks | error |
| --- | --- | --- | --- | --- | --- |
| `digest-01` | 3/6 | 3.00 | 5.18 s | `json_valid`, `contract_paths`, `cites_sources` | - |
| `digest-02` | 2/6 | 3.25 | 9.24 s | `json_valid`, `contract_paths`, `cites_sources`, `no_offtopic` | - |
| `digest-03` | 2/6 | 3.25 | 6.04 s | `json_valid`, `contract_paths`, `cites_sources`, `undecided_marked` | - |
| `digest-04` | 2/6 | 3.75 | 6.31 s | `json_valid`, `contract_paths`, `cites_sources`, `min_points` | - |

### `structured-digest/v2`

| task | checks | judge | latency | failed checks | error |
| --- | --- | --- | --- | --- | --- |
| `digest-01` | 2/6 | 0.00 | 10.39 s | `json_valid`, `contract_paths`, `cites_sources`, `chinese` | - |
| `digest-02` | 2/6 | 0.00 | 8.47 s | `json_valid`, `contract_paths`, `cites_sources`, `recurring_captured` | - |
| `digest-03` | 4/6 | 2.75 | 8.33 s | `json_valid`, `contract_paths` | - |
| `digest-04` | 4/6 | 3.75 | 8.51 s | `json_valid`, `contract_paths` | - |

## Failure evidence

<details><summary><code>structured-digest/v1</code> / <code>digest-01</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- judge notes: 输出不是纯 JSON，缺少 key_points 与 sources 字段；待跟踪事项多数未写明责任方，也未标注责任方未定。

```text
## 总体结论
本次检查记录编号 AQ-2026-031，共发现 5 项情况。主要风险集中在现场通道占用、消防器材失效和行车防护缺失；其中“行车防脱钩装置缺失”属重复问题且未闭环，“通道占用”整改未按细则留影像，需优先跟踪。

## 关键问题
- **一号车间西侧安全通道被周转筐占用**：检查时间 3 月 12 日 09:20，当班班长李明，记录人王强。
- **整改不合规**：依据《车间安全检查细则》第 7 条，通道占用需当班整改并留影像；本次仅口头提醒，未留影像。
- **二号库房灭火器异常**：2 具灭火器 MQ-118、MQ-119 压力表指针落黄区，已联系维保，约定 3 月 14 日前更换。
- **三号车间行车防脱钩装置缺失 1 套**：2 月抽查已提出，当时回复“本月内整改”，至今未闭环，属重复问题。
- **培训到场率不足**：上周应到 46 人，实到 40 人，到场率 87%；未到场 6 人，其中当班 4 人、请假 2 人。

## 待跟踪事项
1. 三号车间行车防脱钩装置缺失问题：必须闭环，并说明重复未整改原因。
2. 一号车间通道占用：补做当班整改及影像留存，按细则第 7 条处理。
3. 二号库房灭火器 MQ-118、MQ-119：跟踪 3 月 14 日前完成更换。
4. 培训未到场人员：重点处理当班未到 4 人，请假 2 人另计。
```
</details>

<details><summary><code>structured-digest/v1</code> / <code>digest-02</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- `no_offtopic` (must_not_include) — found: ['报销', '发票']
- judge notes: 输出不是纯 JSON，缺少字段和 sources 字段；内容在 T-442 处截断；行动项仅部分区分厂家介入与厂内自处理。

```text
# GD-2026-088 设备工单结构化结论

## 总体结论
本批共 5 条设备工单：已关闭 2 条，未闭环/需跟踪 3 条。核心风险有两项：  
1. 二号包装线贴标机错标重复发生，T-4411 未找到根因，T-4436 再次出现且待厂家远程支持。  
2. 三号车间空压机温度达 91℃，超 85℃阈值，已应急降载并监控，厂家工程师 3 月 16 日到场。  
另：差旅报销单 3 份已提交财务，其中 1 份发票抬头有误，需重开。

## 重点风险
- **T-4411 / T-4436：二号包装线贴标机错标**  
  - 3 月 12 日：偶发错标，每班约 3 次；重启视觉模块后恢复；未找到根因。  
  - 3 月 14 日：再次错标 5 次，现象与 T-4411 一致；待厂家远程支持。  
  - 结论：同一故障复发，不能仅靠重启恢复，需厂家排查根因。

- **T-442
```
</details>

<details><summary><code>structured-digest/v1</code> / <code>digest-03</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- `undecided_marked` (must_include) — missing: ['待确认']
- judge notes: 未将30天整改折算为具体日期，也未替被审方承诺时限；未确认事项和等待关系标出，但未形成明确下一步行动项；输出是Markdown而非纯JSON，违反格式要求。

```text
# HY-2026-014 供应商现场审核摘要

## 总体结论
3 月 10 日现场审核记录三项问题，均建议 30 天内整改；但具体截止日期未确认，待处理区隔离方案尚未收到、未约定评审时间，整改闭环时间不明确。

## 审核信息
- 编号：HY-2026-014
- 审核时间：3 月 10 日
- 人员：审核方 2 人，被审方陪同 1 人

## 发现的问题
1. **成品库温湿度记录断记**：2 月有 4 天断记；被审方解释为记录仪换电池期间未补录。
2. **来料检验报告不合规**：2 份为复印件，且无审核章。
3. **现场区域未物理隔离**：待处理区与合格区未做物理隔离。

## 整改要求
- 对以上三项建议 **30 天内整改**。
- 具体截止日期待与被审方确认后另行通知。

## 未闭环事项
- 整改截止日期未确认。
- 待处理区隔离方案由被审方提出，尚未收到。
- 隔离方案评审时间未约定。

## 风险点
- 整改期限未明确，30 天整改要求难以考核闭环。
- 待处理区与合格区未隔离，且方案未收、未评审，现场管理风险未消除。
```
</details>

<details><summary><code>structured-digest/v1</code> / <code>digest-04</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- `min_points` (regex_all) — 0 unique match(es) of /"key_points"/, need 1
- judge notes: 输出不是纯 JSON，且没有 sources 字段或至少 3 条来源。

```text
# HY-2026-021 周例会摘要（2026-03-13）

## 总体结论
一期 12 个点位已上线 9 个（75%），剩余 3 个卡在交换机到货。当前主要问题不在进度本身，而在多项事项未闭环：到货无书面确认、误报未调参、云费用未核账、协作无统一接口人、验收标准未定版。下次 3 月 20 日例会前应优先推进这些事项。

## 要点
- **进度**：12 个点位已上线 9 个；剩余 3 个因等交换机到货顺延。供应商口头答复“下周”到货，未给书面确认。
- **质量**：上线点位近 7 天平均每天误报 2.3 次，集中在夜间光照不足时段；现场确认与镜头遮挡有关，未做参数调整。
- **成本**：本月云侧推理费用较上月增加 18%；原因未查清，会上推测可能与新增点位有关，但无人核对账单明细。
- **协作**：现场施工队与运维班组接口人不同，已出现 2 次到场无人对接；会上未指定统一接口人。
- **制度**：验收标准仍沿用上一版草案；与会人员未提出异议，也未确认最终版本。
- **会议安排**：下次例会暂定 3 月 20 日，会议室待定。

## 待闭环事项
1. 取得交换机到货的书面确认。
2. 处理夜间误报：参数调整、光照与镜头遮挡整改。
3. 核对云费用账单，查清 18% 增长原因。
4. 指定施工队与运维班组的统一接口人。
5. 确认最终验收标准版本。
6. 确定下次例
…[truncated]
```
</details>

<details><summary><code>structured-digest/v2</code> / <code>digest-01</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- `chinese` (language) — cjk=0 latin=0
- judge notes: grounding: no structured conclusion was provided. actionability: no actions or responsible parties were stated. readability: no summary was given. format_contract: output was not JSON with required fields and minimum counts.

```text

```
</details>

<details><summary><code>structured-digest/v2</code> / <code>digest-02</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- `recurring_captured` (must_include) — missing: ['T-4411', 'T-4436']
- judge notes: No candidate output was provided, so it fails every criterion.

```text

```
</details>

<details><summary><code>structured-digest/v2</code> / <code>digest-03</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- judge notes: Output is truncated and not valid JSON; next action items are vague and incomplete, not specifying deliverables or responsible parties.

```text
{
  "summary": "HY-2026-014供应商现场审核发现：成品库温湿度记录2月断记4天、2份来料检验报告复印件无审核章、待处理区与合格区未物理隔离。结论建议30天内整改，截止日期待确认；隔离方案未收到。",
  "key_points": [
    "成品库温湿度记录2月有4天断记（见 [S2]）",
    "来料检验报告2份复印件无审核章（见 [S3]）",
    "待处理区与合格区未物理隔离（见 [S4]）",
    "结论建议30天内整改，截止日期待确认（见 [S5]）",
    "待处理区隔离方案由被审方提出，尚未收到（见 [S6]）"
  ],
  "risks": [
    "温湿度记录断记4天，可能影响成品库环境追溯（见 [S2]）",
    "来料检验报告复印件无审核章，可能影响文件有效性（见 [S3]）",
    "待处理区与合格区未物理隔离，存在混料风险（见 [S4]）",
    "整改截止日期未确认，30天期限可能无法落实（见 [S5]）",
    "隔离方案未收到、未约定评审时间（见 [S6]）"
  ],
  "next_actions": [
    {
      "action": "对三项现象进行整改",
      "owner": "未定",
      "when": "30天内（具体截止日期待确认）"
 
…[truncated]
```
</details>

<details><summary><code>structured-digest/v2</code> / <code>digest-04</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- judge notes: Grounding: causes are restated as unverified per the meeting, no invented conclusions (mild '影响上线点位质量' is a defensible inference). Compression: retains 9/12, 2.3次, 18% and all five topics. Actionability: 未指定接口人、版本未确认、账单未核对 all appear as explicit待办. Format contract: output is a truncated, invalid JSON object and contains no 'sources' field despite [S1]-[S6] citations, so the format/sources requirem

```text
{"summary":"HY-2026-021项目周例会：一期12个点位上线9个，3个等交换机到货；近7天日均误报2.3次，集中夜间；云推理费增18%未查清；接口人与验收标准未定；下次例会暂定3月20日，会议室待定。","key_points":["一期12个点位已上线9个，剩余3个因等交换机顺延（见 [S1]）","上线点位近7天日均误报2.3次，集中在夜间光照不足时段（见 [S2]）","本月云侧推理费用较上月增加18%，原因未查清（见 [S3]）","施工队与运维接口人不同，两次到场无人对接（见 [S4]）","验收标准沿用上一版草案，未确认最终版本（见 [S5]）","下次例会暂定3月20日，会议室待定（见 [S6]）"],"risks":["交换机到货仅供应商口头答复“下周”，无书面确认，剩余3个点位顺延（见 [S1]）","夜间误报集中且未做参数调整，影响上线点位质量（见 [S2]）","云侧推理费用增加18%原因未查清，未核对账单明细（见 [S3]）","现场施工队与运维班组接口人不统一，已出现两次无人对接（见 [S4]）","验收标准未确认最终版本，仍沿用上一版草案（见 [S5]）"],"next_actions":[{"action":"获取交换机到货书面确认（见 [S1]）","owner":"未定","when":"未定"},{"action":"排查夜间误报
…[truncated]
```
</details>
