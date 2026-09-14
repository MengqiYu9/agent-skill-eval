# 为什么我的评测说"技能变差了"——推理模型把 max_tokens 吃光了

> 一次真实的评测误诊：报告的结论是"改进后的技能更差"，而真相是生成被 token 上限截断。
> 数字全部来自 [agent-skill-eval](https://github.com/MengqiYu9/agent-skill-eval) 仓库里的真实运行。

## 症状

给一个技能做了"更严格"的 v2（加了输出契约：必须是 JSON、必须带条款出处、必须标注未知项），
跑 A/B 对比，报告第一版长这样：

| arm | 检查通过率 | judge 均分 |
|---|---|---|
| v1（松散提示词） | 0.38 | **3.31** |
| v2（严格契约） | 0.50 | **1.62** |

结论会写成"v2 通过率涨了一点，但主观质量掉了一半，得不偿失"。

这个结论是错的。翻原始输出才发现：v2 在 4 个任务里有 **2 个任务的输出是空字符串**，
`completion_tokens` 恰好等于 `max_tokens`（2048）。也就是说模型把 2048 个 token 全部
花在了**推理过程**上，一个字的答案都没写出来就撞到了上限。

空输出在评测里是"最差答案"：所有确定性检查失败（没有 JSON、没有出处），
评分员看到空字符串就给 0 分。于是**一个测量装置的故障，被记成了被测对象的质量问题**。

## 为什么这类误诊特别常见

1. **`reasoning` 和 `answer` 共享同一个预算。** OpenAI 兼容的 chat completions 里，
   `max_tokens` 限制的是 `completion_tokens` 总量，推理模型的思维链也算在里面。
   你以为给了 2048 个 token 写答案，实际是"推理 + 答案"一共 2048。
2. **大多数 harness 只读 `choices[0].message.content`。** 空字符串是一个合法返回值，
   不会报错、不会抛异常、不会进日志。上游静默，下游照常打分。
3. **它偏向"结构化输出更多"的那一版。** 输出越长、字段越多、引用越全的版本越容易撞上限——
   而这类版本恰好就是你想改进的方向。所以这个 bug 有**系统性偏见**：它专门惩罚改进。
4. **评分员不会说"没收到东西"。** 我把评分员的 prompt 也检查了一遍：它老老实实地给每条标准打 0，
   还附上一句"未提供候选输出"。信息其实在报告里，只是没人会去看一个 0 分的原因字段。

## 修法（三处，都很小）

**一、把 `finish_reason` 当一等公民。** 它只有三个常见值（`stop` / `length` / `content_filter`），
但能立刻区分"模型说完了"和"模型被切断了"。我的 `Completion` 现在带 `finish_reason` 和
`truncated` 属性，报告每个任务多一列 `finish`。

**二、空输出必须是"具名错误"，不能是"低分答案"。** 现在：

```python
if not text.strip():
    completion.error = empty_content_error(finish, reasoning_chars, max_tokens)
    # → "empty content: the model spent all 4096 tokens before writing an answer
    #    (finish_reason=length, 10743 reasoning chars) — raise --max-tokens"
```

同一次运行里，有一个任务在 `max_tokens=4096` 下烧掉了 **10 743 个推理字符**才被截断——
这个数字以前是看不见的，现在它直接告诉你"该把上限调多大"。

**三、在报告顶部加截断告警，并把上限写进报告元数据。**

> **Truncation warning** — 1 task(s) stopped at the token cap, so their output is incomplete.
> Raise `--max-tokens` before reading these numbers as a skill result.

同一份报告，"cap 太小"和"技能太差"是两种完全不同的结论，而它们的表格长得一模一样。
把上限记进报告，也意味着这个数字可复现——别人能重跑出同样的结果。

## 修好之后的数字

同一套 4 个任务、同一个模型、同一份评分员，只把 `--max-tokens` 从 2048 提到 8192：

| arm | 检查通过率 | judge 均分 | tokens (入/出) | 平均延迟 |
|---|---|---|---|---|
| v1 | 0.38 (9/24) | 3.19 | 1 508 / 4 871 | 5.68 s |
| v2 | **0.96 (23/24)** | **4.56** | 2 648 / 12 490 | 12.15 s |

结论完全反过来了：v2 不是"质量掉了"，而是**在 2048 的上限下根本没写完**。
代价也才第一次看得清：**2.4 倍 token、2.1 倍延迟，换 +58% 通过率**。

## 五点自查清单

在同一条 pipeline 上花五分钟就能查完：

1. 你的 runner 读 `finish_reason` 吗？为 `length` 单独计数了吗？
2. 空输出和"错误答案"在报告里能区分吗？（能不能一眼看出 `completion_tokens == max_tokens`）
3. 报告的元数据里写了 `max_tokens` / 模型名 / 端点吗？换个上限跑出来的数字还能比吗？
4. 评分员拿到空输入时，是报错还是打 0 分？**打 0 分就是在替测量故障背锅。**
5. 你的基线是在哪个上限下录的？改了上限的 run 不能直接和旧基线比通过率。

最后一条最容易被忽略：如果基线是在"会截断"的配置下录的，那么后来把上限调大，
你会看到一次"假提升"；反过来，把上限调小，你会看到一次"假回退"。
**评测的上限、模型、端点属于结果的一部分，不是运行环境的一部分。**

---

*复现：`python -m skilleval run --suite suites/doc-to-actions --skill skills/doc-to-actions/v1 --skill skills/doc-to-actions/v2 --max-tokens 8192 --baseline baseline.json`；
截断样本见 `examples/report-live-2048-truncated.md`，干净样本见 `examples/report-live-8192.md`。*
