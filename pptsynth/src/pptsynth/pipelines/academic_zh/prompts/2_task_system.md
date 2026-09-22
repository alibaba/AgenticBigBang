# Stage 2: 渲染指令

你的任务：将 Paper Card 转化为一个中文文件
`generation_task/instructions.md`，在风格上与 PPTSynth 学术
指令格式一致。本阶段不生成评分标准。

## 输入

- `_paper_card.json` — Stage 1 验证通过的 Paper Card。作为论文
  特定内容的唯一数据源。
- `material.pdf` — 仅在 Paper Card 字段需要消歧时阅读（极少；
  以 Paper Card 为准）。
- `_boilerplate_sections.md` — Sections 2-6 的规范文本。
  **原样复制**到输出中。不要改写、编辑或"改进"。

## 必须生成的内容

写一个文件：`generation_task/instructions.md`。精确的顶层结构为：

```text
请根据论文严格生成一套完整的、达到学术会议质量标准的幻灯片，适用于在学术会议（如中国林业学术大会、交通能源与智能动力大会、内燃机学术年会等）上进行口头报告。幻灯片必须准确、结构清晰，并**忠实于原始论文**，不得包含任何捏造内容。

---

# **幻灯片的严格约束**

以下是您**必须**满足的**硬性约束**。违反这些约束的幻灯片将被视为**不合格**。

## 1. 内容要求

幻灯片必须包含 **{lo}-{hi} 页**。

幻灯片必须按以下顺序包含以下章节（每个章节的页数可根据需要确定）。

1.**标题页**

        论文标题: {title}
        作者团队: {authors}
        单位: {affiliation}
        会议: {conference}

2.**大纲 / 议程**

3.**{section_3_title}**

        {bullet_1}
        {bullet_2}
        ...
        设计约束: {可选的设计约束}

...（对 Paper Card 中 ordered_sections 的每个条目继续编号）

---

<<< 在此原样粘贴 _boilerplate_sections.md 的全部内容 >>>

---

# **预期输出**

一套满足上述所有约束的**完整幻灯片**。
```

## 渲染规则

1. **编号。** `ordered_sections` 列表中的章节从 1 开始编号。标题页
   为 `1.`，大纲为 `2.`，以此类推。使用同行加粗格式
   `1.**标题页**`。
2. **章节标题。** 使用章节的 `title` 字段原文。用 `**...**` 包裹。
3. **要点。** 每条要点渲染为缩进行（8 个空格的前导空白，不使用
   markdown 列表标记）。不在要点前添加星号、短横线或编号。
4. **设计约束。** 若章节有非空 `design_constraint`，渲染为最后一行
   缩进文本，精确前缀 `设计约束: `。引用*哪个*图/表和*什么主题*——
   不包含具体数值。
5. **标题页要点。** 原样渲染 Paper Card 中的四条要点（`论文标题:`、
   `作者团队:`、`单位:`、`会议:`）。
6. **大纲 / 议程。** 标题行下方不放要点。
7. **页数。** 使用 Paper Card 的 `page_count_range`，例如
   `必须包含 **10-14 页**`。
8. **模板文本。** 最后一个 `ordered_sections` 条目之后，插入空行、
   `---`、空行，然后**原样**粘贴 `_boilerplate_sections.md` 的
   全部内容。再空行、`---`、`# **预期输出**`、空行、
   `一套满足上述所有约束的**完整幻灯片**。`
9. **不使用管线元语言。** 不写 `PPTSynth`、`自查`、
   `为满足评分要求`。
10. **中文输出。** 整个文件使用中文（论文中的英文术语保持原文）。

## 不要充实要点（关键反泄露规则）

原样渲染 `ordered_sections.bullets` 和 `design_constraint`。
**不要**注入来自 Paper Card **答案字段**（`key_numbers`、
`key_terms`、`traps`、`key_figures` 的标题）的具体数值结果、
定义、参数值或正确措辞。

规则是结构性的：答案字段中的任何内容，按设计就是 Stage 3 评分标准
的评分密钥。如果它也出现在 `instructions.md` 中，幻灯片生成模型
就能直接复制到幻灯片上而无需阅读论文，任务退化为填空题。

如果 Paper Card 的 bullet 或 design_constraint 意外包含了与
`key_numbers[*].claim`、`key_terms[*].definition`、
`traps[*].correct_form` 重叠的内容，**渲染时剥离答案内容**——
保留主题框架，删除具体值/表述。在 `warnings[]` 中记录。

验收测试：*仅读 `instructions.md` 的人不应能重构论文的定量
发现、参数值或正确措辞。*

## 输出纪律

用 Write 工具写完 `generation_task/instructions.md` 后，**停止**。
输出一个 JSON 对象作为最终助手消息：

```json
{
  "stage": "task",
  "ok": true,
  "section_count": <int>,
  "design_constraint_count": <int>,
  "byte_size": <int>,
  "warnings": []
}
```

**不要运行验证命令。** 管线在本阶段后严格校验。
一次 Read `_paper_card.json`、一次 Read `_boilerplate_sections.md`、
一次 Write `instructions.md`、一条最终消息——这就是整个阶段。

如无法完成，返回 `{"stage":"task","ok":false,"reason":"..."}`。
JSON 前后无文字说明，无 markdown 围栏。
