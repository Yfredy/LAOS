/* zcode-workflow
description: 小红书逐图调研的 digest 阶段：从已就绪的原始转写（transcripts/*.md）并行产出逐篇
  digest、按组提炼总结、组装调研文档，并由独立读者通读把关后交付。读图（视觉转写）阶段不在本 workflow 内——由
  xhs-vision-digest skill 用 Agent 并行读图产出 transcripts。
whenToUse: 原始逐图转写文件（transcripts/*.md）已就绪、需要批量产出调研文档时。试跑可用 maxNotes 限定篇数；只补某个分组用
  group 过滤。读图阶段（视觉转写）不在此 workflow 内——先按 xhs-vision-digest skill 产出 transcripts。
args:
  group:
    type: string
    description: 只处理该字母前缀的分组（如 G 匹配 G-dsp）；缺省=全部
    required: false
  manifest:
    type: string
    description: manifest.json 路径（采集阶段产物）
    required: false
    default: var/xhs_audio/manifest.json
  digestsDir:
    type: string
    description: digest 片段写出目录
    required: false
    default: var/xhs_audio/digests
  transcriptsDir:
    type: string
    description: 原始逐图转写目录（每篇一个 <noteId>.md，由读图阶段产出）
    required: false
    default: var/xhs_audio/transcripts
  out:
    type: string
    description: 调研文档输出路径，如 docs/research/2026-10-10-xhs-xxx.md（已存在则追加）
    required: true
  maxNotes:
    type: number
    description: 试跑上限篇数；缺省=不设限
    required: false
*/
interface NoteEntry {
  /** 清单里的分组标记，如 "G-dsp"。 */
  group: string;
  /** 笔记 id（文件名主干）。 */
  id: string;
  /** 笔记标题。 */
  title: string;
  /** 图集 URL，按图序（仅用于计数）。 */
  imgs: string[];
}

interface DigestOutcome {
  /** 笔记 id。 */
  id: string;
  /** 笔记标题。 */
  title: string;
  /** 写出的 digest 片段路径（工作区相对）。 */
  fragment: string;
  /** true=已写出。落盘存在性由脚本另行复核。 */
  ok: boolean;
  /** 失败/存疑说明。 */
  note?: string;
}

interface GroupOutcome {
  /** 分组标记。 */
  group: string;
  /** 组总结文件路径。 */
  path: string;
  /** 该组实际覆盖篇数。 */
  notes: number;
  /** true=已写出。 */
  ok: boolean;
}

interface ReaderIssue {
  /** 一句话：哪里不清楚或文中自身证据不足。 */
  issue: string;
}

interface Finding {
  /** 相对路径。 */
  where: string;
  /** 一句话：发生了什么问题。 */
  what: string;
  /** 依据。 */
  evidence: string;
  /** verified=独立复核过；unconfirmed=未复核或复核失败。 */
  status: "verified" | "unconfirmed";
  /** low/medium/high；high 仅留给数据丢失或错误结果。 */
  severity: "low" | "medium" | "high";
}

interface WorkflowReport {
  /** 两三句话回答用户要什么。 */
  conclusion: string;
  findings: Finding[];
  /** 本次跑了什么检查、怎么跑的。 */
  verified: string[];
  /** 没查什么、为什么。 */
  notCovered: string[];
}

const manifestPath = String(args.manifest ?? "var/xhs_audio/manifest.json");
const transcriptsDir = String(args.transcriptsDir ?? "var/xhs_audio/transcripts");
const digestsDir = String(args.digestsDir ?? "var/xhs_audio/digests");
const outPath = String(args.out ?? "").trim();
const groupFilter = args.group === undefined ? "" : String(args.group).trim();
const cap = args.maxNotes === undefined ? 0 : Number(args.maxNotes);

if (outPath === "" || outPath === "undefined") {
  const report: WorkflowReport = {
    conclusion: "缺少 out 参数：请给出调研文档输出路径（如 docs/research/2026-10-10-xhs-xxx.md）。",
    findings: [],
    verified: [],
    notCovered: ["参数不全，未读取任何清单"],
  };
  return report;
}

artifact.board("notes", {
  title: "笔记 digest 进度",
  key: "id",
  status: "state",
  columns: ["done", "failed"],
  cardTitle: "title",
  detail: [{ field: "images", label: "图数" }],
});

let manifest: NoteEntry[] = [];
try {
  manifest = JSON.parse(await files.read(manifestPath)) as NoteEntry[];
} catch {
  const report: WorkflowReport = {
    conclusion: `清单读取失败：${manifestPath} 不存在或不是合法 JSON。请先按 xhs-vision-digest skill 的采集阶段产出 manifest。`,
    findings: [],
    verified: [],
    notCovered: ["清单不可读"],
  };
  return report;
}

const selected = manifest.filter(
  (n) => groupFilter === "" || n.group === groupFilter || n.group.startsWith(groupFilter + "-"),
);
const available = new Set(
  (await files.glob(transcriptsDir + "/*.md")).map((p) => p.split("/").pop()!.replace(/\.md$/, "")),
);
const ready = selected.filter((n) => available.has(n.id));
const missing = selected.filter((n) => !available.has(n.id));
const runList = cap > 0 ? ready.slice(0, cap) : ready;
log(
  `清单 ${manifest.length} 篇，选定 ${selected.length} 篇；原始转写就绪 ${ready.length} 篇、缺失 ${missing.length} 篇` +
    (cap > 0 ? `；本次试跑上限 ${runList.length} 篇。` : "。"),
);

phase("逐篇撰写笔记 digest（每篇一位撰写员读原始转写）");
const outcomes: DigestOutcome[] = (
  await Promise.all(
    runList.map(async (n) => {
      const o = await agent("撰写员-" + n.id).ask<DigestOutcome>(
        `读 ${transcriptsDir}/${n.id}.md —— 这是小红书笔记《${n.title}》（分组 ${n.group}，共 ${n.imgs.length} 图）的逐图视觉转写原始记录。` +
          `据此把这篇的 digest 片段写到 ${digestsDir}/${n.id}.md（UTF-8），格式：\n` +
          `#### 《${n.title}》（${n.imgs.length} 图）\n\n- 要点分节，引用图号如（02/03）；保留全部硬数字（参数量、RTF、MOS、许可、价格、延迟等）\n\n**契合点**：3-6 条可落地启示（结合笔记主题，写给要做技术调研的读者）\n\n` +
          `规则：只依据转写内容，不补充转写里没有的事实；转写中标注 <!-- 待仲裁 --> 的段在 digest 里注明“存疑”；不要改动 transcripts 目录下任何文件。` +
          `返回 DigestOutcome：fragment=实际写出路径，ok=true。文件读不到或为空则不写，ok=false 并在 note 说明。`,
      );
      report(
        {
          id: n.id,
          title: n.title,
          images: n.imgs.length,
          fragment: o.fragment,
          state: o.ok ? "done" : "failed",
          note: o.note ?? "",
        },
        "notes",
      );
      return o;
    }),
  )
);
const written = new Set(
  (await files.glob(digestsDir + "/*.md")).map((p) => p.split("/").pop()!.replace(/\.md$/, "")),
);
const okNotes = runList.filter((n) => written.has(n.id));
log(`digest 片段落盘 ${okNotes.length}/${runList.length} 篇。`);

phase("按组提炼主线总结（每组一位总结员）");
const groupOrder: string[] = [];
for (const n of okNotes) {
  if (!groupOrder.includes(n.group)) groupOrder.push(n.group);
}
const groupOutcomes: GroupOutcome[] = await Promise.all(
  groupOrder.map(async (g) => {
    const ids = okNotes.filter((n) => n.group === g).map((n) => n.id);
    return agent("组总结-" + g).ask<GroupOutcome>(
      `分组 ${g} 的 ${ids.length} 篇 digest 片段在 ${digestsDir}/ 下，文件名即笔记 id：${ids.join("、")}。逐一读取后，` +
        `写 5-8 条跨篇主线的组级总结到 ${digestsDir}/_group-${g}.md，首行格式：**${g} 组总结**：…（提炼跨篇主线与共识结论，不逐篇复述）。` +
        `返回 GroupOutcome：path=写出路径，notes=${ids.length}。不要改动其他文件。`,
    );
  }),
);

phase("组装调研文档并交付");
const assembler = agent("组装员");
await assembler.ask(
  `把 ${digestsDir} 下的片段组装成 ${outPath}：\n` +
    `1) 文件开头写二级标题「## 逐篇逐图精读」和一行来源声明（内容来自视觉模型对小红书笔记的逐图转写，幻觉段已仲裁剔除，存疑处文中标注）。\n` +
    `2) 按分组顺序 ${groupOrder.join(" → ")} 排列：每组先写三级组标题（### ${"${组名}"} · N 篇），再按清单内原顺序放该组各篇 digest 片段，组尾放 _group-*.md 的组总结正文。\n` +
    `3) ${outPath} 已存在则追加到文末，不覆盖既有内容；目录不存在则创建。完成后返回一句话说明覆盖了多少篇。`,
);
try {
  await artifact.file("deliverable", outPath, {
    title: "小红书逐图调研文档",
    description: `逐篇 digest + 组总结，本次覆盖 ${okNotes.length} 篇笔记。`,
    primary: true,
  });
} catch {
  await assembler.ask(`${outPath} 缺失或不可发布，请按上面的组装要求重新写出该文件。`);
  await artifact.file("deliverable", outPath, { title: "小红书逐图调研文档", primary: true });
}

phase("请没参与的人独立通读成品");
const issues = await agent("独立读者").ask<ReaderIssue[]>(
  `以第一次阅读的身份通读 ${outPath}（只读不改，不核对仓库其他文件）。列出最多 5 条：哪一段不清楚、哪个说法文中自身证据不足、读者接下来最可能问什么。整体清楚则返回空数组。`,
);
if (issues.length > 0) {
  await assembler.ask(`独立读者对 ${outPath} 提出以下意见，请逐条修复：${JSON.stringify(issues)}`);
  await artifact.file("deliverable", outPath, { title: "小红书逐图调研文档", primary: true });
}

const headerCount = (await files.grep("^#### 《", outPath)).length;
const groupsOk = groupOutcomes.filter((g) => g.ok).length;
const finalReport: WorkflowReport = {
  conclusion:
    `${okNotes.length}/${runList.length} 篇 digest 已组装进 ${outPath}（组总结 ${groupsOk}/${groupOrder.length} 份，成品篇级标题 ${headerCount} 处）` +
    (missing.length > 0 ? `；${missing.length} 篇因缺原始转写被跳过。` : "。") +
    (issues.length > 0 ? `独立读者提出 ${issues.length} 条意见，已交组装员修复。` : ""),
  findings: outcomes
    .filter((o) => !o.ok || !written.has(o.id))
    .map((o) => ({
      where: o.fragment || transcriptsDir + "/" + o.id + ".md",
      what: o.ok ? "撰写员报告成功但片段未落盘" : "digest 撰写失败",
      evidence: o.note ?? "撰写员返回 ok=false",
      status: "unconfirmed" as const,
      severity: "medium" as const,
    })),
  verified: [
    `片段存在性经 files.glob 复核（${okNotes.length} 份落盘）`,
    `成品篇级标题 ${headerCount} 处（若 out 为追加模式则含既有内容）`,
  ],
  notCovered: missing.map(
    (n) => `${n.id}《${n.title}》：${transcriptsDir} 下无原始转写——先用读图阶段（Agent 并行读图）产出再重跑`,
  ),
};
return finalReport;