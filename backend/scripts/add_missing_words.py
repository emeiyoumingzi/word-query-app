# -*- coding: utf-8 -*-
"""将 单词.txt 中不在词库的单词（人工翻译）按 16 列格式加入 CSV，备注列填"非大纲单词"。
同时重新生成收藏种子（此时 312 词全部在词库中）。"""
import csv
import json
import re
from pathlib import Path

BASE = Path(r"C:\Users\hp\Desktop\单词速查")
CSV = BASE / "考研英语大纲词汇5500.csv"

# (word, [(pos, meaning), ...], {present, past, past_participle})
ENTRIES = [
    ("mundane", [("adj.", "平凡的，世俗的，单调乏味的")], {}),
    ("founder", [("n.", "创始人，奠基者，创立者")], {}),
    ("regularity", [("n.", "规律性，规则性，经常性")], {}),
    ("reconstruction", [("n.", "重建，再建，重构")], {}),
    ("monoglot", [("adj.", "只懂一种语言的"), ("n.", "只使用一种语言的人")], {}),
    ("algorithm", [("n.", "算法，运算法则")], {}),
    ("emission", [("n.", "排放，散发；发出物")], {}),
    ("predatory", [("adj.", "掠夺的，捕食性的；掠夺成性的")], {}),
    ("acuity", [("n.", "敏锐，敏锐度，分辨力")], {}),
    ("bewildering", [("adj.", "令人困惑的，使人迷乱的")], {}),
    ("conscience", [("n.", "良心，良知，道德心")], {}),
    ("exploitation", [("n.", "开发，开采；剥削，利用")], {}),
    ("misplaced", [("adj.", "放错位置的；错置的，不恰当的")], {}),
    ("transportation", [("n.", "运输，运送；交通，运输工具")], {}),
    ("perpetually", [("adv.", "永久地，不断地")], {}),
    ("originally", [("adv.", "最初，原先；独创地")], {}),
    ("decoration", [("n.", "装饰，装潢；装饰品；勋章")], {}),
    ("temporarily", [("adv.", "暂时地，临时地")], {}),
    ("volatile", [("adj.", "易变的，不稳定的；挥发性的")], {}),
    ("dispatch", [("v.", "派遣，发送，调遣"), ("n.", "急件，快信；派遣")],
     {"present": "dispatching", "past": "dispatched", "past_participle": "dispatched"}),
    ("sensual", [("adj.", "感官的，感觉的；肉欲的，性感的")], {}),
    ("contrary", [("adj.", "相反的，对立的"), ("n.", "相反，反面")], {}),
    ("nonfiction", [("n.", "非虚构类作品，非小说类文学")], {}),
    ("predominance", [("n.", "优势，主导地位，支配地位")], {}),
    ("inflationary", [("adj.", "通货膨胀的")], {}),
    ("projection", [("n.", "投射，投影；预测，推断；突出物")], {}),
    ("farcical", [("adj.", "闹剧的，滑稽的，荒诞可笑的")], {}),
    ("citation", [("n.", "引用，引文；嘉奖；（法律）传票")], {}),
    ("conservatism", [("n.", "保守主义，守旧")], {}),
    ("buzz", [("n.", "嗡嗡声；传闻，热议"), ("v.", "发出嗡嗡声；热议")],
     {"present": "buzzing", "past": "buzzed", "past_participle": "buzzed"}),
    ("biotic", [("adj.", "生物的，生命活动的")], {}),
    ("reawaken", [("v.", "重新唤醒，再次唤起")],
     {"present": "reawakening", "past": "reawakened", "past_participle": "reawakened"}),
    ("construct", [("v.", "建造，构筑，构造"), ("n.", "构想，概念")],
     {"present": "constructing", "past": "constructed", "past_participle": "constructed"}),
    ("poetic", [("adj.", "诗的，诗歌的；富有诗意的")], {}),
    ("critical", [("adj.", "批评的，批判的；关键的，危急的；挑剔的")], {}),
    ("evolutionary", [("adj.", "进化的，演化的")], {}),
    ("convinced", [("adj.", "确信的，深信的")], {}),
    ("pernicious", [("adj.", "有害的，恶性的，致命的")], {}),
    ("courtship", [("n.", "求爱，求婚；求偶")], {}),
    ("construction", [("n.", "建造，建设；建筑，建筑物；结构")], {}),
    ("continuity", [("n.", "连续性，连贯性")], {}),
    ("creative", [("adj.", "有创造力的，创造性的")], {}),
    ("precisely", [("adv.", "精确地，准确地；恰好，正是")], {}),
    ("enrollment", [("n.", "注册，登记；入学；注册人数")], {}),
    ("rejection", [("n.", "拒绝，驳回；排斥")], {}),
    ("publishing", [("n.", "出版，出版业")], {}),
    ("irrepressible", [("adj.", "抑制不住的，无法控制的")], {}),
    ("intriguing", [("adj.", "引人入胜的，有趣的，神秘的")], {}),
    ("intrusive", [("adj.", "侵入的，打扰的，闯入的")], {}),
    ("copious", [("adj.", "丰富的，大量的，多产的")], {}),
    ("marshal", [("v.", "整理，集结，排列"), ("n.", "元帅；司仪")],
     {"present": "marshalling", "past": "marshalled", "past_participle": "marshalled"}),
    ("imprisonment", [("n.", "监禁，关押")], {}),
    ("oriented", [("adj.", "以…为方向的，定向的，导向的")], {}),
    ("predominantly", [("adv.", "主要地，占主导地位地")], {}),
    ("constituent", [("n.", "成分，要素；选民"), ("adj.", "组成的，构成的")], {}),
    ("biographer", [("n.", "传记作者，传记作家")], {}),
    ("motivation", [("n.", "动机，动力，积极性")], {}),
    ("unconditional", [("adj.", "无条件的，绝对的")], {}),
    ("slippage", [("n.", "滑动，滑移；下降，贬值；延误")], {}),
    ("fertility", [("n.", "肥沃；生育力，繁殖力")], {}),
    ("apprenticeship", [("n.", "学徒期，学徒身份")], {}),
    ("innate", [("adj.", "天生的，固有的，先天的")], {}),
    ("sobering", [("adj.", "使人清醒的，令人警醒的")], {}),
    ("foreseeable", [("adj.", "可预见的，可预知的")], {}),
    ("oppression", [("n.", "压迫，压制，压抑")], {}),
    ("heresy", [("n.", "异端，邪说")], {}),
    ("migration", [("n.", "迁移，移居；迁徙")], {}),
    ("coincident", [("adj.", "同时发生的，巧合的；一致的")], {}),
    ("elevation", [("n.", "提升，升高；海拔，高度；立面图")], {}),
    ("decay", [("v.", "腐烂，腐朽；衰退，衰败"), ("n.", "腐烂；衰退")],
     {"present": "decaying", "past": "decayed", "past_participle": "decayed"}),
    ("titanic", [("adj.", "巨大的，庞大的")], {}),
    ("optimism", [("n.", "乐观，乐观主义")], {}),
    ("convince", [("v.", "使确信，使信服；说服")],
     {"present": "convincing", "past": "convinced", "past_participle": "convinced"}),
    ("rationalist", [("n.", "理性主义者，唯理论者")], {}),
    ("ambiguity", [("n.", "歧义，模棱两可，含糊不清")], {}),
    ("purport", [("v.", "声称，自称"), ("n.", "意图，主旨")],
     {"present": "purporting", "past": "purported", "past_participle": "purported"}),
    ("flora", [("n.", "植物群，植物区系")], {}),
    ("empowerment", [("n.", "授权，赋权")], {}),
    ("restrained", [("adj.", "克制的，节制的；受限的")], {}),
    ("tempting", [("adj.", "诱人的，吸引人的")], {}),
    ("dependency", [("n.", "依赖，依靠；从属")], {}),
    ("turbulence", [("n.", "动荡，骚乱；湍流")], {}),
    ("yearn", [("v.", "渴望，向往，怀念")],
     {"present": "yearning", "past": "yearned", "past_participle": "yearned"}),
    ("sustainability", [("n.", "可持续性")], {}),
    ("sewing", [("n.", "缝纫，缝纫活")], {}),
    ("promotion", [("n.", "晋升，提升；促销，推广")], {}),
    ("allot", [("v.", "分配，分派，拨给")],
     {"present": "allotting", "past": "allotted", "past_participle": "allotted"}),
    ("relevance", [("n.", "相关性，关联；中肯")], {}),
    ("continent", [("n.", "大陆，洲"), ("adj.", "自制的，节制的")], {}),
    ("accessible", [("adj.", "可到达的；易接近的；可使用的")], {}),
    ("constrained", [("adj.", "受约束的，受限的；勉强的")], {}),
    ("unevenly", [("adv.", "不均匀地，不均衡地")], {}),
    ("exacerbate", [("v.", "使恶化，使加剧")],
     {"present": "exacerbating", "past": "exacerbated", "past_participle": "exacerbated"}),
    ("capability", [("n.", "能力，才能；性能")], {}),
    ("curb", [("v.", "抑制，控制，约束"), ("n.", "路缘；抑制")],
     {"present": "curbing", "past": "curbed", "past_participle": "curbed"}),
    ("incredibly", [("adv.", "难以置信地，非常地")], {}),
    ("enlightenment", [("n.", "启发，启蒙；[E-]启蒙运动")], {}),
    ("rationally", [("adv.", "理性地，合理地")], {}),
    ("lineage", [("n.", "血统，世系，家系")], {}),
    ("prevailing", [("adj.", "流行的，盛行的；占优势的")], {}),
    ("endlessly", [("adv.", "无止境地，不断地")], {}),
    ("anticipation", [("n.", "预期，期望，预料")], {}),
    ("polished", [("adj.", "擦亮的，光洁的；优雅的，精练的")], {}),
    ("anaemia", [("n.", "贫血，贫血症")], {}),
    ("readable", [("adj.", "易读的，可读的")], {}),
    ("coexistence", [("n.", "共存，共处")], {}),
    ("uncanny", [("adj.", "离奇的，神秘的，不可思议的")], {}),
    ("passionately", [("adv.", "热情地，激昂地；深情地")], {}),
    ("afterwards", [("adv.", "后来，以后")], {}),
    ("famed", [("adj.", "著名的，出名的")], {}),
    ("exploration", [("n.", "探索，勘探，探测")], {}),
    ("merciless", [("adj.", "无情的，残忍的")], {}),
    ("journalism", [("n.", "新闻业，新闻工作")], {}),
    ("emigration", [("n.", "移居国外，移民出境")], {}),
    ("reproducible", [("adj.", "可复制的，可重现的，可再生的")], {}),
    ("contain", [("v.", "包含，容纳；控制，抑制")],
     {"present": "containing", "past": "contained", "past_participle": "contained"}),
    ("instantly", [("adv.", "立即，马上")], {}),
    ("generative", [("adj.", "能生成的，生成式的；有生产力的")], {}),
    ("cheerfulness", [("n.", "愉快，高兴，乐观")], {}),
    ("strategic", [("adj.", "战略的，战略上的；关键的")], {}),
    ("entirely", [("adv.", "完全地，彻底地")], {}),
    ("inferiority", [("n.", "自卑，劣势；下级")], {}),
    ("spatial", [("adj.", "空间的，空间上的")], {}),
    ("connection", [("n.", "连接，联系；关系")], {}),
    ("crucial", [("adj.", "至关重要的，决定性的")], {}),
    ("interaction", [("n.", "相互作用，相互影响；交流，互动")], {}),
]

NOTE = "非大纲单词"
assert len(ENTRIES) == 126, len(ENTRIES)

# ---- 读取现有 CSV ----
with open(CSV, "r", encoding="utf-8-sig", newline="") as f:
    rows = [r for r in csv.reader(f)]
header = rows[0]
existing = [r[0].strip().lower() for r in rows[1:] if r and r[0].strip()]

added = 0
skipped = []
for word, groups, inf in ENTRIES:
    if word.lower() in existing:
        skipped.append(word)
        continue
    row = [word]
    for i in range(5):
        g = groups[i] if i < len(groups) else ("", "")
        row.append(g[0])
        row.append(g[1])
    row.append(inf.get("present", ""))
    row.append(inf.get("past", ""))
    row.append(inf.get("past_participle", ""))
    row.append("")          # 词组
    row.append(NOTE)        # 备注
    rows.append(row)
    existing.append(word.lower())
    added += 1

rows = [rows[0]] + sorted(rows[1:], key=lambda r: r[0].strip().lower())
with open(CSV, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerows(rows)

print(f"added: {added} | skipped(already in csv): {len(skipped)}")
if skipped:
    print("skipped:", skipped)
print("total rows now:", len(rows) - 1)

# ---- 重新生成收藏种子（312 词现在全部在词库中） ----
words_from_txt = []
with open(BASE / "单词.txt", encoding="utf-8") as f:
    for line in f:
        s = line.strip()
        m = re.match(r"^\d+[\.、)\s]*\s*(.*)$", s)
        if m:
            s = m.group(1).strip()
        if s:
            words_from_txt.append(s.lower())

csv_map = {}
with open(CSV, encoding="utf-8-sig", newline="") as f:
    r = csv.reader(f)
    next(r)
    for row in r:
        if row and row[0].strip():
            csv_map.setdefault(row[0].strip().lower(), row)

seed = []
for w in words_from_txt:
    if w in csv_map:
        row = csv_map[w]
        pos = row[1].strip() if len(row) > 1 else ""
        meaning = (row[2].strip() if len(row) > 2 else "").split("；")[0].split(";")[0][:30]
        seed.append({"word": row[0].strip(), "pos": pos, "meaning": meaning})

seed_path = BASE / "word-query-app" / "frontend" / "src" / "favorites-seed.js"
seed_path.write_text(
    "// 由脚本生成：单词.txt 中存在于词库的单词（翻译高频词汇收藏夹种子）\n"
    "export const FAVORITES_SEED_FOLDER = '\u7ffb\u8bd1\u9ad8\u9891\u8bcd\u6c47'\n"
    "export const FAVORITES_SEED = " + json.dumps(seed, ensure_ascii=False, indent=1) + "\n",
    encoding="utf-8",
)
print("seed regenerated:", len(seed))
