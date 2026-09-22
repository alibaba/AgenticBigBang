# Stage 4: 审计与自动修复

你的任务：作为本目录中案例的严格审查者。对于评分标准或指令文件中
明显可以修复的问题（无需重新阅读论文），**就地编辑修复**。
然后返回一个结构化的审计报告 JSON。

## 输入

- `material.pdf` — 仅在事实核查特定表述时阅读。使用 `pages`
  参数控制成本。
- `_paper_card.json` — Stage 1 的结构化 Paper Card。
- `_field_manifest.txt` — 自动生成的必覆盖清单。
- `generation_task/instructions.md` — Stage 2 生成。
- `generation_task/judge_prompt.json` — Stage 3 生成。
- `audit_report.schema.json` — 你的输出必须通过其校验。

## 元评分标准（每轴评 1-5 分）

4-5 分为合格；≤3 分为该轴不合格。

1. **style_alignment** — instructions.md 是否遵循六段式
   结构：开头句、`# **幻灯片的严格约束**`、Section 1 含论文特定
   要点、Sections 2-6 来自规范模板（原样）、`# **预期输出**`、
   结束句。
2. **section1_paper_specificity** — Section 1 的*章节标题*是否
   论文特定化（非泛化的"方法"而是"方法：预燃室射流点火技术"），
   要点是否涉及论文特定的主题、机制、数据集或基线（不是模板语言）？
   特定性在主题层面衡量——数值层面的预泄露由
   `instruction_underspecification` 单独评分。
3. **design_constraint_density** — 是否有 ≥3 个 Section 1 条目
   包含引用论文中真实图/表标识符的 `设计约束:` 行？
4. **instruction_underspecification** — Section 1 的要点和设计约束
   行是否描述主题/范围/定性框架，而未预泄露具体数值结果、精度值、
   基线数值排名或 `+/-Δ` 增益？仅读 `instructions.md` 的人不应
   能重构论文的定量发现。评分 1：要点读起来像完整答案提纲（多个
   数值、参数值、Δ 值）；5：每个具体值仅在评分标准中出现。
   需查找的具体缺陷：浮点百分比、"较...提高/降低了X%"、
   P 值/显著性水平、具体参数赋值、key_terms.definition 原文
   引用、traps.correct_form 原文引用。
5. **checklist_anchor_specificity** — 正确性项是否包含具体锚点
  （命名术语、数值+单位+条件、指标区分）？完整性项是否使用论文
   特定术语而非泛化占位符？
6. **completeness_correctness_separation** — 是否没有单个检查项
   同时问"是否包含"和"是否正确"？
7. **trap_coverage** — 正确性检查项是否覆盖了 Paper Card
   `traps` 列表中 ≥3 种不同的 trap 类型？
   同时检查 `_field_manifest.txt`：每个 TRAP 条目应有专门的
   正确性检查项，使用其 correct_form 和 claim_to_avoid。
   若不足 50% 的 traps 被覆盖，评分 1-2。
8. **language_and_meta_hygiene** — 整个案例是否使用中文（英文术语
   保持原文）？`instructions.md` 和 `judge_prompt.json` 中是否
   不含 `PPTSynth`、`自查`、`为满足评分要求` 等管线元语言？
9. **internal_consistency** — 每个完整性检查项的必要元素是否在
   `instructions.md` Section 1 中确有对应要求？每个正确性检查项
   的锚点是否存在于 Paper Card（`key_numbers`、`key_terms`、
   `traps`、`key_figures`）中？
10. **atomicity_check** — 每个检查项是否仅测试一个独立条件？
    查找包含"A、B 和 C"的项，其中每个组件都可以独立判断是/否。
    若有项包含 ≥3 个独立条件，评分 1-2；包含 2 个条件评分 3；
    每项都是原子的评分 4-5。
11. **key_numbers_coverage** — 正确性检查项是否引用了 Paper Card
    中 ≥80% 的 `key_numbers` 条目（对照 `_field_manifest.txt`）？
    引用 <50% 评分 1-2；50-79% 评分 3；≥80% 评分 4-5。

## 允许就地修复的内容

使用 Edit 工具。允许的编辑：

- **松化**过度具体的 Section 1 要点和设计约束行，使其描述范围/
  主题而非预泄露具体值。剥离嵌入的 `key_numbers` 内容（精度 %、
  参数值、`+/-Δ` 增益）、`key_terms[*].definition` 原文引用和
  `traps[*].correct_form` 原文引用，同时保留论文特定的主题/
  机制/数据名称。
- 收紧 Section 1 要点的*主题层面*论文特定性（若读起来像泛化
  模板语言，替换为论文特定描述）。
- 添加缺失的 `设计约束:` 行，引用 `key_figures` 中的真实图/表
  标识符。新行不得含具体值。
- 改写检查项以附加从 Paper Card 提取的具体锚点。
- 拆分一个混合检查项为完整性项和正确性项。
- 拆分一个非原子检查项（测试 A、B 和 C）为单独检查项。
- 为 `_field_manifest.txt` 中未覆盖的 key_numbers 或 traps
  添加缺失的正确性检查项，使用对比格式"X 而非 Y"。
- 移除泄露的元语言，替换为中性措辞。
- 改写引用图/表编号（如"图 3"）的检查项，改为描述内容
  （如"展示 X 与 Y 对比的柱状图"）。

**不允许**做的：

- 向 Section 1 的任何要点或设计约束行添加具体数值、精度 %、
  基线排名或 `+/-Δ` 增益——即使 Paper Card 有。
- 编造 `key_figures` 或论文中不存在的图/表标识符。
- 编造 `key_numbers` 或论文中不存在的数值。
- 改变 Section 1 的章节 *kind* 集合（最多添加一个缺失的规范
  章节）。
- 编辑模板文本（`instructions.md` 的 Sections 2-6）。

如果修复需要重新阅读论文获取新内容，不要编辑；降低相应轴的
评分并在 `findings` 中给出精确的 `fix` 建议。

## 输出纪律

通过 Edit 应用修复后，输出一个通过 `audit_report.schema.json`
校验的 JSON 对象作为最终消息。JSON 须包含：

- `pass`：当且仅当每轴 ≥ 4 时为 true。
- `scores`：每轴的 1-5 整数评分（共 11 轴）。
- `findings`：剩余（未修复的）问题列表，每个标注轴、严重程度
 （`blocker | major | minor`）、文件位置、问题描述和具体修复
  建议。
- `fixes_applied`：实际应用的编辑列表。
- `summary`：2-3 句话的总体评估。使用中文。

最终 JSON 前后无文字说明，无 markdown 围栏。
