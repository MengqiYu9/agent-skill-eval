# agent-skill-eval report

| field | value |
| --- | --- |
| runner | `llm` |
| model | `deepseek-flash` |
| judge | `deepseek-flash` |
| started | 2026-09-14 17:59:05 |
| skills | 2 |
| verdict | **PASS** |

## Summary

| skill | task pass | check pass | judge mean | mean latency | tokens (in/out) | cost | truncated |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `structured-digest/v1` | 0.38 | 0.38 (9/24) | 3.19 | 5.68 s | 1508 / 4871 | n/a | 0 |
| `structured-digest/v2` | 0.96 | 0.96 (23/24) | 4.56 | 12.15 s | 2648 / 12490 | n/a | 0 |

## A/B delta (first skill = baseline arm)

| skill | Δ task pass | Δ check pass | Δ judge | Δ mean latency |
| --- | --- | --- | --- | --- |
| `structured-digest/v2` | +0.58 | +0.58 | +1.37 | +6.47 s |

## Per-check outcome

| check | `structured-digest/v1` | `structured-digest/v2` |
| --- | --- | --- |
| `chinese` | 1/1 | 1/1 |
| `cites_sources` | 0/4 | 4/4 |
| `contract_paths` | 0/4 | 4/4 |
| `json_valid` | 0/4 | 4/4 |
| `length_cap` | 4/4 | 4/4 |
| `min_points` | 0/1 | 1/1 |
| `no_claimed_owner` | 1/1 | 1/1 |
| `no_invented_deadline` | 1/1 | 1/1 |
| `no_offtopic` | 0/1 | 0/1 |
| `no_placeholders` | 1/1 | 1/1 |
| `recurring_captured` | 1/1 | 1/1 |
| `undecided_marked` | 0/1 | 1/1 |

## Per-task detail

### `structured-digest/v1`

| task | checks | judge | latency | finish | failed checks | error |
| --- | --- | --- | --- | --- | --- | --- |
| `digest-01` | 3/6 | 3.00 | 8.92 s | stop | `json_valid`, `contract_paths`, `cites_sources` | - |
| `digest-02` | 2/6 | 3.00 | 5.75 s | stop | `json_valid`, `contract_paths`, `cites_sources`, `no_offtopic` | - |
| `digest-03` | 2/6 | 3.00 | 4.38 s | stop | `json_valid`, `contract_paths`, `cites_sources`, `undecided_marked` | - |
| `digest-04` | 2/6 | 3.75 | 3.69 s | stop | `json_valid`, `contract_paths`, `cites_sources`, `min_points` | - |

### `structured-digest/v2`

| task | checks | judge | latency | finish | failed checks | error |
| --- | --- | --- | --- | --- | --- | --- |
| `digest-01` | 6/6 | 4.50 | 8.24 s | stop | - | - |
| `digest-02` | 5/6 | 4.50 | 9.18 s | stop | `no_offtopic` | - |
| `digest-03` | 6/6 | 4.25 | 13.55 s | stop | - | - |
| `digest-04` | 6/6 | 5.00 | 17.64 s | stop | - | - |

## Failure evidence

<details><summary><code>structured-digest/v1</code> / <code>digest-01</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- judge notes: 行动项均未写责任方，也未标注责任方未定；输出不是纯 JSON，缺少 key_points/sources 等字段。

```text
**总体结论**
编号 AQ-2026-031 本次周检共反映 4 类事项：现场隐患/异常 3 项、培训到场不足 1 项，并暴露 2 个整改执行问题。最需优先处理：三号车间行车防脱钩装置缺失属重复问题且未闭环；一号车间通道占用未按细则留影像，整改程序不合规。灭火器压力异常已安排 3 月 14 日前更换。

**要点**
1. 一号车间西侧安全通道被周转筐占用。检查时间 3 月 12 日 09:20，当班班长李明，记录人王强。按《车间安全检查细则》第 7 条，应“当班整改并留影像”；本次仅口头提醒，未留影像，整改不合规。
2. 二号库房灭火器压力表指针落在黄区，共 2 具，编号 MQ-118、MQ-119。已联系维保单位，约定 3 月 14 日前更换。
3. 三号车间行车防脱钩装置缺失 1 套。属重复问题：2 月抽查已提出，当时回复“本月内整改”，至今未闭环。
4. 上周培训到场率 87%：应到 46 人，实到 40 人；未到场 6 人中，4 人当班，2 人请假。

**后续关注**
- 三号车间防脱钩缺失：重点督办，明确闭环时间和责任人。
- 一号车间通道占用：补整改及影像记录，按第 7 条闭环。
- 灭火器：确认 3 月 14 日前完成更换并留存记录。
- 培训：针对当班缺勤安排补训/补学。
```
</details>

<details><summary><code>structured-digest/v1</code> / <code>digest-02</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- `no_offtopic` (must_not_include) — found: ['报销', '发票']
- judge notes: 格式不是纯JSON且没有sources字段；行动项未明确区分需厂家介入与厂内可自处理两类。

```text
## 总体结论

GD-2026-088 本批共 5 条设备工单：2 条已关闭，1 条监控中，2 条未闭环。  
当前最需跟进的是**二号包装线贴标机错标复发**，T-4411 未找到根因，T-4436 再次出现同类问题，正待厂家远程支持。  
三号车间空压机超温已采取临时措施，仍需监控，厂家工程师 3 月 16 日到场。  
另有 3 份差旅报销已提交财务，其中 1 份发票抬头有误需重开。

## 按优先级跟进

### 1. 二号包装线贴标机错标：未闭环，且复发

- **T-4411｜3 月 12 日**：偶发错标，每班约 3 次；重启视觉模块后恢复；**未找到根因**。
- **T-4436｜3 月 14 日**：再次错标 5 次，与 T-4411 现象一致；**待厂家远程支持**。
- 结论：同一问题复发，需厂家介入定位根因，避免持续影响包装线。

### 2. 三号车间空压机超温：监控中

- **T-4425｜3 月 13 日**：空压机温度达 **91℃**，超设定阈值 **85℃**。
- 处理：加开一台备用机、降载运行。
- 状态：监控中；厂家工程师 **3 月 16 日**到场。

## 已关闭事项

- **T-4418｜3 月 12 日**：一号码垛机器人示教器电池告警；已更换电池；关闭。
- **T-4430｜3 月 13 日**：一号车间照明灯管更换 
…[truncated]
```
</details>

<details><summary><code>structured-digest/v1</code> / <code>digest-03</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- `undecided_marked` (must_include) — missing: ['待确认']
- judge notes: 输出未将30天整改折算为具体日期或替被审方承诺时限。未确认事项有标注，但未明确写出谁在等谁。行动项未明确写出下一步要拿到什么、由谁提供。输出为Markdown而非纯JSON，不满足格式契约。

```text
# HY-2026-014 供应商现场审核备忘｜结构化摘要

## 总体结论
本次审核（3月10日）发现 3 项问题：成品库温湿度记录断记、来料检验报告复印件无审核章、待处理区与合格区未物理隔离。材料仅提出“建议 30 天内整改”，但具体截止日期未确认；待处理区隔离方案尚未收到，评审时间也未约定，整改闭环缺少关键时间节点和方案评审安排。

## 审核基本信息
- 编号：HY-2026-014
- 审核时间：3月10日
- 审核方：2人
- 被审方陪同：1人

## 发现问题
1. 成品库温湿度记录：2月有4天断记。被审方解释为记录仪换电池期间未补录。
2. 来料检验报告：2份为复印件，且无审核章。
3. 现场区域管理：待处理区与合格区未做物理隔离。

## 整改要求与结论
- 原文结论：以上三项建议30天内整改。
- 具体截止日期：待与被审方确认后另行通知。

## 未决事项与风险
- 待处理区隔离方案由被审方提出，尚未收到。
- 未约定该隔离方案的评审时间。
- 因截止日期未确认、隔离方案未评审，30天整改要求暂无法形成明确闭环计划。
```
</details>

<details><summary><code>structured-digest/v1</code> / <code>digest-04</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- `min_points` (regex_all) — 0 unique match(es) of /"key_points"/, need 1
- judge notes: 输出为 Markdown 而非纯 JSON，且没有 sources 字段/至少 3 条来源。

```text
# 结构化摘要｜HY-2026-021 项目周例会（2026-03-13）

## 总体结论

项目一期主体进度可控（12 个点位已上线 9 个），但本次会议**五个议题中有四个只提出现象、未形成决定**：延期原因依赖口头承诺、误报未做调整、成本异动未核对、接口人未指定、验收标准未定版。当前主要风险不是进度本身，而是**责任人与截止时间普遍缺失**，下阶段需按"谁在何时交付什么"逐项闭环。

## 要点

**1. 进度：9/12 上线，剩余 3 个卡在交换机**
- 剩余 3 个点位因等交换机到货顺延。
- 供应商仅口头答复"下周"，**无书面确认**；缺货确认与到货时间是当前唯一的硬性外部依赖。

**2. 质量：误报 2.3 次/天，原因已知但未处理**
- 上线点位近 7 天平均每天误报 2.3 次，集中在夜间光照不足时段。
- 现场判断与镜头遮挡有关，**尚未做参数调整**。

**3. 成本：云侧推理费用环比 +18%，原因未查清**
- 会上猜测为新增点位所致，**无人核对账单明细**，属未验证假设。

**4. 协作：接口人未统一**
- 施工队与运维班组接口人不同，已发生 **2 次到场无人对接**。
- 会上**未指定统一接口人**。

**5. 制度：验收标准仍为上一版草案**
- 与会人员未提异议，也**未确认最终版本**，存在后期返工风险。

**6. 下
…[truncated]
```
</details>

<details><summary><code>structured-digest/v2</code> / <code>digest-02</code></summary>

- `no_offtopic` (must_not_include) — found: ['报销', '发票']
- judge notes: Grounding is clean (only source ticket numbers, 91℃/85℃, 3月16日, no invented durations or losses). Risks correctly focus on the repeat unclosed labeling fault and the over-temperature compressor rather than the closed battery/lamp tickets. Actionability only partially satisfies the criterion: vendor actions are labeled ('厂家'/'厂家工程师'), but the internal action (invoice reissue) has owner '未定' and the

```text
{
  "summary": "GD-2026-088 批次 5 条设备工单：二号包装线贴标机两次错标且根因未定，三号车间空压机超温仍在监控，电池与灯管工单已关闭；批次内另有 1 份差旅发票抬头需重开。",
  "key_points": [
    "T-4411 贴标机每班错标约 3 次，重启视觉模块后恢复（见 [S2]）",
    "T-4436 贴标机再错标 5 次，现象与 T-4411 一致（见 [S6]）",
    "空压机温度 91℃，超设定阈值 85℃，降载运行（见 [S4]）",
    "T-4418 电池告警、T-4430 灯管更换已关闭（见 [S3]、[S5]）",
    "本批次差旅报销单 3 份已提交财务，1 份发票抬头有误（见 [S1]）"
  ],
  "risks": [
    "贴标机错标重复出现，未找到根因（见 [S2]、[S6]）",
    "空压机温度 91℃ 超阈值，仍在监控中（见 [S4]）",
    "1 份差旅发票抬头有误，需重开（见 [S1]）"
  ],
  "next_actions": [
    {"action": "对二号包装线贴标机错标提供远程支持", "owner": "厂家", "when": "未定"},
    {"action": "厂家工程师到现场处理空压机超温", "owner": "厂家工
…[truncated]
```
</details>
