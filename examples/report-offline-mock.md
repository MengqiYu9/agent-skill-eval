# agent-skill-eval report

| field | value |
| --- | --- |
| runner | `mock` |
| model | `deepseek-flash` |
| judge | off |
| started | 2026-09-14 17:54:25 |
| skills | 2 |
| verdict | **PASS** |

## Summary

| skill | task pass | check pass | judge mean | mean latency | tokens (in/out) | cost |
| --- | --- | --- | --- | --- | --- | --- |
| `structured-digest/v1` | 0.38 | 0.38 (9/24) | n/a | n/a s | 200 / 209 | n/a |
| `structured-digest/v2` | 1.00 | 1.00 (24/24) | n/a | n/a s | 720 / 641 | n/a |

## A/B delta (first skill = baseline arm)

| skill | Δ task pass | Δ check pass | Δ judge | Δ mean latency |
| --- | --- | --- | --- | --- |
| `structured-digest/v2` | +0.62 | +0.62 | n/a | n/a |

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
| `no_offtopic` | 1/1 | 1/1 |
| `no_placeholders` | 1/1 | 1/1 |
| `recurring_captured` | 0/1 | 1/1 |
| `undecided_marked` | 0/1 | 1/1 |

## Per-task detail

### `structured-digest/v1`

| task | checks | judge | latency | failed checks | error |
| --- | --- | --- | --- | --- | --- |
| `digest-01` | 3/6 | - | 0.00 s | `json_valid`, `contract_paths`, `cites_sources` | - |
| `digest-02` | 2/6 | - | 0.00 s | `json_valid`, `contract_paths`, `cites_sources`, `recurring_captured` | - |
| `digest-03` | 2/6 | - | 0.00 s | `json_valid`, `contract_paths`, `cites_sources`, `undecided_marked` | - |
| `digest-04` | 2/6 | - | 0.00 s | `json_valid`, `contract_paths`, `cites_sources`, `min_points` | - |

### `structured-digest/v2`

| task | checks | judge | latency | failed checks | error |
| --- | --- | --- | --- | --- | --- |
| `digest-01` | 6/6 | - | 0.00 s | - | - |
| `digest-02` | 6/6 | - | 0.00 s | - | - |
| `digest-03` | 6/6 | - | 0.00 s | - | - |
| `digest-04` | 6/6 | - | 0.00 s | - | - |

## Failure evidence

<details><summary><code>structured-digest/v1</code> / <code>digest-01</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3

```text
本次安全检查整体可控，但存在几处需要跟进的问题。一号车间西侧安全通道被周转筐占用，属当班需整改项，本次只做了口头提醒，没有留影像。二号库房有 2 具灭火器压力表落在黄区，已经联系维保单位，约定 3 月 14 日前更换。比较值得关注的是三号车间行车防脱钩装置缺失，这个问题 2 月抽查时就提过，当时说本月内整改，到现在还没闭环。上周培训到场率 87%，46 人应到实到 40 人，未到的 6 人里 4 人当班、2 人请假。总体看，重复问题没闭环是主要短板，建议把通道占用和防脱钩缺失去向全部补上影像留存。
```
</details>

<details><summary><code>structured-digest/v1</code> / <code>digest-02</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- `recurring_captured` (must_include) — missing: ['T-4411', 'T-4436']

```text
工单汇总显示设备问题以包装线为主。二号包装线贴标机在 3 月 12 日偶发错标，每班约 3 次，重启视觉模块后恢复，但没有找到根因；3 月 14 日又出现 5 次同类错标，正在等厂家远程支持。一号码垛机器人换了示教器电池后关闭。三号车间空压机温度到 91 度，超过 85 度阈值，已经加开备用机并降载运行，厂家工程师 3 月 16 日到场。另外一号车间更换了 6 支灯管。整体上包装线错标是当前最需要盯住的问题。
```
</details>

<details><summary><code>structured-digest/v1</code> / <code>digest-03</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- `undecided_marked` (must_include) — missing: ['待确认']

```text
这次供应商现场审核共发现三项现象。一是成品库温湿度记录 2 月有 4 天断记，被审方解释为换电池期间没有补录。二是来料检验报告中有 2 份是复印件且没有审核章。三是待处理区与合格区没有做物理隔离。审核结论建议以上三项在 30 天内完成整改。综合看，记录完整性和标识管理是薄弱环节，建议把整改责任落到被审方质量负责人，并在下一次审核前完成闭环。
```
</details>

<details><summary><code>structured-digest/v1</code> / <code>digest-04</code></summary>

- `json_valid` (json_valid) — no parseable JSON object found
- `contract_paths` (json_path) — no parseable JSON
- `cites_sources` (regex_all) — 0 unique match(es) of /\[S\d+\]/, need 3
- `min_points` (regex_all) — 0 unique match(es) of /"key_points"/, need 1

```text
本周例会覆盖五个议题。一期 12 个点位已上线 9 个，剩余 3 个等交换机到货，供应商口头说下周，没有书面确认。上线点位近 7 天平均每天 2.3 次误报，集中在夜间光照不足时段，判断与镜头遮挡有关，还没调参数。云侧推理费用环比增加 18%，原因没查清，会上猜是新增点位导致，但没人核对账单。现场施工队和运维班组接口人不一致，出现过两次到场无人对接。验收标准还是上一版草案，没有确认最终版本。下次例会暂定 3 月 20 日，会议室待定。
```
</details>
