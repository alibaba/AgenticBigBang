# Stage 4: 审计与自动修复

你的任务：作为本目录中案例的严格审查员，对于可明确就地修复的
问题直接修改文件。然后返回一个审计报告 JSON。

## 输入

- `material.pdf` — 仅在核实具体声明时读取。使用 `pages` 参数控制成本。
- `_doc_card.json`（或 `_paper_card.json`）— Stage 1 的结构化 DocCard。
- `_field_manifest.txt` — 自动生成的强制覆盖清单。
- `generation_task/instructions.md` — Stage 2 的产物。
- `generation_task/judge_prompt.json` — Stage 3 的产物。
- `_audit_report.schema.json` — 你的输出必须通过的 schema。

## 元评分标准（每轴评分 1-5）

得分 4 或 5 合格；≤3 为该轴不合格。

1. **style_alignment** — `instructions.md` 是否遵循六段式
   结构：开头句、`# **幻灯片的严格约束**`、Section 1（文档特定的
   幻灯片大纲，带 bullets 和设计约束行）、Sections 2-6（规范模板，
   逐字复制）、`# **预期输出**`、结束句。

2. **section1_paper_specificity** — Section 1 的章节**标题**是否
   文档特定化（非"方法"而是"方法：腹腔镜手术操作流程"），bullets
   是否命名了文档特定的话题、机制、产品名、数据集或基线
   （读者不能将其不加修改地套用到另一份文档）。仅在主题/机制
   层面评估特定性——数值级的预泄露由 `instruction_underspecification`
   单独评分。

3. **design_constraint_density** — Section 1 中至少有 2 个章节
   包含 `设计约束:` 行，且引用了文档中真实的图/表标识符。
   方法/流程、结果/成效和视觉分析章节应包含。

4. **instruction_underspecification** — Section 1 的 bullets 和
   设计约束行描述的是话题/范围/定性视角，而非预泄露具体数值结果、
   具体指标数值、排名或 `+/-Δ` 增量。仅读 `instructions.md` 的人
   不应能重建文档的定量结论。评 1 分如果 bullets 读起来像完整答案
   大纲（多个数值/比例嵌入结果 bullets，baseline 数字在设置 bullet
   中，`+X.X%` 增量在设计约束中）；评 5 分如果每个具体数值仅存在
   于评分标准，instructions 只描述每页幻灯片应涵盖的话题。
   具体缺陷：`\\d+\\.\\d+%`、"优于"/"高于"加数字、"+/-\\d+\\.\\d+ 个
   百分点"、`key_terms.definition` 逐字引用、`traps.correct_form`
   逐字引用。

5. **checklist_anchor_specificity** — 每个正确性项是否携带具体锚点
   （命名术语、数值+单位+条件、指标区分）。每个完整性项是否命名
   了文档特定术语而非泛化占位符。

6. **completeness_correctness_separation** — 没有检查项同时询问
   "X 是否存在"和"X 是否正确"。覆盖性和准确性清晰分离。

7. **trap_coverage** — 正确性项是否涵盖了 DocCard `traps` 列表中
   至少 3 种不同类型的 trap。对照 `_field_manifest.txt`：每个 TRAP
   条目都应有一个专用的正确性项，使用其 `correct_form` 和
   `claim_to_avoid`。如果覆盖率 <50% 则评 1-2 分。

8. **language_and_meta_hygiene** — 案例是否全部使用中文（英文专有
   名词保留）。`instructions.md` 和 `judge_prompt.json` 中是否无
   `PPTSynth`、"自查"、"为满足评分要求"、"根据评分细则"等
   自指元语言。"基准"、"评分标准"、"检查列表"等词仅在文档本身
   使用这些概念时方可出现；仅在自指合成任务时标记。

9. **internal_consistency** — 每个完整性项要求的元素是否在
   `instructions.md` Section 1 中确实要求。每个正确性项的锚点是否
   存在于 DocCard（`key_numbers`、`key_terms`、`traps`、`key_figures`）。

10. **atomicity_check** — 没有检查项测试多于一个独立条件。检查包含
    "A、B 和 C"的项（其中每个都可以独立判定是/否）。如果任何项捆绑
    了 ≥3 个独立条件则评 1-2 分；捆绑 2 个则评 3 分；每项都是原子的
    则评 4-5 分。

11. **key_numbers_coverage** — 正确性项是否引用了 DocCard 中 ≥80%
    的 `key_numbers` 条目（对照 `_field_manifest.txt` 检查）。
    <50% 覆盖则评 1-2 分；50-79% 则评 3 分；≥80% 则评 4-5 分。

## 允许就地修复的内容

使用 Edit 工具。允许的修改：

- **放宽**过度指定的 Section 1 bullets 和设计约束行，使其描述
  话题/范围而非预泄露具体数值。剥离嵌入的 `key_numbers` 内容
  （具体百分比、排名、`+/-Δ` 增量）、逐字引用的 `key_terms[*].definition`
  和 `traps[*].correct_form`，同时保留文档特定的话题/机制/产品名
  等表述。Bullets 必须保持话题层面的文档特定性，但不含数值。
  示例转换：
  - 之前：`销售额同比增长 23.5%，超过目标 8.5 个百分点。`
  - 之后：`销售额：分析同比增长情况及与目标的差距。`
- 收紧主题层面的章节标题特定性（"讨论方法" → "方法：腹腔镜三孔技术的关键操作步骤"）。
- 在方法/流程/结果/视觉分析章节添加缺失的 `设计约束:` 行，
  引用 `key_figures` 中的真实图/表标识符，不含具体数值。
- 改写检查项，附加从 DocCard 中提取的具体锚点。
- 将混合项拆分为完整性项和正确性项。
- 将非原子项拆分为独立项。
- 为 `_field_manifest.txt` 中未覆盖的 `key_numbers` 或 traps 添加
  缺失的正确性项，使用对比格式"X 而非 Y"。
- 删除泄露的元语言，用中性表述替代。
- 将引用图/表编号的项改为描述内容。

**不允许**：
- 向 Section 1 的任何 bullet 或设计约束行添加具体数值、百分比或
  排名——即使 DocCard 中有这些数值。那些数值属于评分标准。
- 虚构未出现在 `key_figures` 或文档中的图/表标识符。
- 虚构 `key_numbers` 中没有的数字。
- 修改 Section 1 的章节种类集合（至多可添加一个缺失的规范章节）。
- 编辑 Sections 2-6 的模板文本——那是逐字复制的设计。

如果一个修复需要重新阅读文档才能获得新内容，则不要编辑；
改为降低相关轴的评分，并在 `findings` 中给出精确的 `fix` 建议。

## 输出纪律

通过 Edit 工具应用修复后，输出一个通过 `_audit_report.schema.json`
校验的 JSON 对象作为最终消息。JSON 必须包含：

- `pass`：当且仅当每轴 ≥ 4 时为 true。
- `scores`：每轴的 1-5 整数评分。
- `findings`：剩余（未修复）问题列表，每条标注 axis、severity
  （`blocker | major | minor`）、文件位置、问题内容和具体修复建议。
- `fixes_applied`：实际应用的编辑列表。
- `summary`：2-3 句总体评价。

最终消息前后无文字说明，无 markdown 代码块围栏。
