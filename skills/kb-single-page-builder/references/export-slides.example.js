/* ============================================================
   投屏课件导出 · 参考实现（export-slides.js）
   ------------------------------------------------------------
   把知识库里「指定的若干节」拼成一份**单文件、离线、可投屏**的 HTML 课件。

   产出：一个 .html 文件 + 一份控制台统计。
   用法：node export-slides.js

   这不是开箱即用的脚本，而是一份**跑通过的实现**，
   展示第三轨（投屏课件）的关键做法。换到自己的库上要改的只有最上面
   那段 CONFIG —— 下面的分页、出页、组装逻辑与内容无关，可原样复用。

   它演示的六件事：
     ① 加载并合并分片，口径与 index.html 的 merge() 完全一致（同一份数据源，
        课件与知识库永不脱节）；
     ② 把每节 HTML 切成「顶层块」，表格与卡片块作为整体参与分页，绝不被切开；
     ③ 软换页：小节没铺满阈值就让下一节接着排，避免满屏半空页；
     ④ 跨页续排标「（续）」，用 base 字段拼接，避免「（续）（续）」累积；
     ⑤ 每节先出导览页（大序号 + 标题 + 领读 + 本节路线 chips），配图各占一页；
     ⑥ 版式直接复用 index.html 的样式表，顶部进度条随库换色。

   屏幕操作：← → 翻页 · 空格下一页 · F 全屏 · P 打印成 PDF · Home/End 首末页。
   ============================================================ */
const fs = require('fs');
const path = require('path');
const dir = __dirname;

/* ============================================================
   CONFIG —— 换项目只改这一段
   ============================================================ */

/* 输出文件名 */
const OUT_FILE = 'course-deck.html';

/* 封面与页脚文案 */
const DECK = {
  eyebrow: '专题课件 · 可投屏',
  title: '专题课件标题',
  subtitle: '一句话副标题，说清这套内容回答什么问题',
  note: '本课件为学习整理稿。<b>涉及具体事务请咨询相应专业人士。</b>'
};

/* 参与课件的数据源。
   rootKey / prefix 必须与你的分片写法一致：
   分片里写 window.<PREFIX>_<数字> = { sections: {...} }，
   rootKey 则是那个基础对象名（分片会往它的 sections 里合并）。 */
const LIBS = {
  a: { rootKey: 'LIB_A_DATA', prefix: 'LIB_A_DATA', label: '主库 A', color: '#1a4d8f', accentVar: '--lib-a' },
  b: { rootKey: 'LIB_B_DATA', prefix: 'LIB_B_DATA', label: '主库 B', color: '#9a2a2a', accentVar: '--lib-b' }
};

/* 课件范围：按顺序列出（库 key、讲次序号、小节 id）。
   小节 id 就是 sections 上的键；顺序即讲课顺序。 */
const SCOPE = [
  { lib: 'a', slot: '一', sec: 'topic-a-1' },
  { lib: 'a', slot: '二', sec: 'topic-a-2' },
  { lib: 'a', slot: '三', sec: 'topic-a-3' },
  { lib: 'b', slot: '四', sec: 'topic-b-1' },
  { lib: 'b', slot: '五', sec: 'topic-b-2' }
];

/* 目录页：每条线一个小标题（第二行是这一组的完整组名） */
const TOC = {
  head: '两条线：一条讲规范，一条讲执行',
  cols: {
    a: { head: '主库 A · 第 X 组', sub: '这一组的完整组名' },
    b: { head: '主库 B · 第 Y 组', sub: '这一组的完整组名' }
  },
  note: { title: '两组的关系', body: '用两三句话说明两条线为什么放在一起讲、在哪一点上交汇。' }
};

/* 收尾页：讲这套内容时要守的纪律。三到四条，每条一句话说清底线。 */
const END = {
  eyebrow: '收尾',
  title: '讲这套内容时的几条纪律',
  items: [
    { kind: 'warn', t: '一、示例纪律甲', p: '一句话说清这条底线，并给出违反它会出什么问题的具体例子。' },
    { kind: 'note', t: '二、示例纪律乙', p: '同上。纪律要能指导动作，不要写成口号。' },
    { kind: 'tip', t: '三、示例纪律丙', p: '同上。涉及敏感领域时，这里写清本课件与知识库共同的内容边界。' }
  ]
};

/* 分页阈值（按正文字数计）。
   BUDGET = 单页上限；SOFT = 软换页阈值，见下方 paginate() 注释。 */
const BUDGET = 820;
const SOFT = 340;

/* ============================================================
   以下与具体内容无关，可原样复用
   ============================================================ */

/* ---------- 1. 加载内容层并合并分片（与 index.html 的 merge() 同口径） ---------- */
global.window = {};
fs.readdirSync(dir).filter(f => /^data-.*\.js$/i.test(f)).sort().forEach(f => {
  try { new Function(fs.readFileSync(path.join(dir, f), 'utf8'))(); } catch (e) { console.error('加载失败 ' + f + '：' + e.message); }
});
function collect(prefix) {
  return Object.keys(global.window)
    .filter(k => k.indexOf(prefix + '_') === 0 && /_\d+$/.test(k))
    .sort((a, b) => parseInt(a.replace(/^.*_/, ''), 10) - parseInt(b.replace(/^.*_/, ''), 10))
    .map(k => global.window[k]);
}
function build(rootKey, prefix) {
  const root = global.window[rootKey];
  if (!root) { console.error('缺少根对象：' + rootKey); return { sections: {}, groups: [] }; }
  collect(prefix).forEach(p => {
    if (!p || !p.sections) return;                       /* 无 sections 的分片整体跳过 */
    for (const k in p.sections) root.sections[k] = p.sections[k];
    if (p.isFinalGroups && p.groups) root.groups = p.groups;
  });
  return root;
}
const ROOTS = {};
Object.keys(LIBS).forEach(k => { ROOTS[k] = build(LIBS[k].rootKey, LIBS[k].prefix); });

/* ---------- 2. 加载图示层 ---------- */
fs.readdirSync(dir).filter(f => /^figs.*\.js$/i.test(f)).sort().forEach(f => {
  try { new Function(fs.readFileSync(path.join(dir, f), 'utf8'))(); } catch (e) {}
});
const FIGS = {};
collect('FIG_DATA').forEach(p => { if (p && p.figs) for (const k in p.figs) FIGS[k] = p.figs[k]; });
const FMAP = window.FIG_MAP || {};
const FATLAS = window.FIG_ATLAS || { groups: [] };
/* 图号由图示册的分组顺序自动生成；未收入的图追加在后面 */
const FIG_NO = {}; (function () {
  let n = 0;
  (FATLAS.groups || []).forEach(g => (g.figs || []).forEach(f => { n++; FIG_NO[f] = n; }));
  Object.keys(FIGS).forEach(f => { if (!FIG_NO[f]) { n++; FIG_NO[f] = n; } });
})();

/* ---------- 3. 工具 ---------- */
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function plain(s) {
  return String(s || '')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&#(\d+);/g, (m, d) => String.fromCharCode(+d))
    .replace(/&#x([0-9a-f]+);/gi, (m, h) => String.fromCharCode(parseInt(h, 16)))
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'").replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ').trim();
}
const weightOf = s => plain(s).replace(/\s/g, '').length;

/* ---------- 4. 把章节 HTML 切成顶层块 ----------
   只按顶层标签切，靠 findEnd() 的深度计数找到配对的闭合标签，
   所以 <table>、<div class="blk"> 这类嵌套结构会被完整保留为一个块，
   分页时不会从中间断开。 */
function cutBlocks(html) {
  const blocks = [];
  const openRe = /<(p|h2|h3|h4|table|div|ul|ol|blockquote)\b[^>]*>/gi;
  let pos = 0;
  while (pos < html.length) {
    openRe.lastIndex = pos;
    const m = openRe.exec(html);
    if (!m) break;
    const tag = m[1].toLowerCase();
    const end = findEnd(html, tag, openRe.lastIndex);
    blocks.push({ tag, html: html.slice(m.index, end) });
    pos = end;
  }
  return blocks;
}
function findEnd(html, tag, from) {
  const re = new RegExp('<' + tag + '\\b[^>]*>|</' + tag + '>', 'gi');
  re.lastIndex = from;
  let depth = 1, m;
  while ((m = re.exec(html)) !== null) {
    if (m[0].charAt(1) === '/') { depth--; if (depth === 0) return re.lastIndex; }
    else if (!/\/\s*>$/.test(m[0])) depth++;                 /* 自闭合标签不计深度 */
  }
  return html.length;
}

/* ---------- 5. 分页 ----------
   硬换页（一节一刀）会让短节产出大量半空屏，本次实测 152 页 → 软换页后 101 页。
   规则：h2 开新页，但上一页还没铺满 SOFT 就继续排在同页，
   同页的后续小节降级为 h3.sh2 小标题。
   两个容易踩的点：
     · 「（续）」必须用 base 字段拼接，直接改 title 会累积成「（续）（续）」；
     · flush() 会把 cur 置空，所以销毁前要把 base / rooted 先存进局部变量。 */
function weightOfBlock(b) {
  if (b.tag === 'table') return (b.html.match(/<tr\b/g) || []).length * 34 + 40;
  if (b.tag === 'div' && /\bblk\b/.test(b.html.slice(0, 90))) return weightOf(b.html) + 30;
  if (b.tag === 'ul' || b.tag === 'ol') return (b.html.match(/<li\b/g) || []).length * 26 + 20;
  return weightOf(b.html) + 12;
}
function paginate(blocks) {
  const pages = [];
  let cur = null;
  const flush = () => { if (cur && cur.blocks.length) pages.push(cur); cur = null; };
  blocks.forEach(b => {
    if (b.tag === 'h2') {
      const t = plain(b.html);
      if (cur && cur.weight >= SOFT) flush();
      if (!cur) cur = { base: t, title: t, blocks: [], weight: 0, rooted: true };
      else cur.blocks.push(`<h3 class="sh2">${esc(t)}</h3>`);   /* 同页的后续小节降为小标题 */
      return;
    }
    if (!cur) cur = { base: '', title: '', blocks: [], weight: 0, rooted: false };
    const w = weightOfBlock(b);
    if (cur.blocks.length && cur.weight + w > BUDGET) {
      const base = cur.base, r = cur.rooted;
      flush();
      cur = { base: base, title: (r && base ? base + '（续）' : base), blocks: [], weight: 0, rooted: r };
    }
    cur.blocks.push(b.html);
    cur.weight += w;
  });
  flush();
  return pages;
}

/* ---------- 6. 出页 ---------- */
const slides = [];
const foot = label => `<div class="sfoot"><span>${esc(label)}</span><span class="pg"></span></div>`;

SCOPE.forEach(item => {
  const lib = ROOTS[item.lib];
  const sec = lib.sections[item.sec];
  if (!sec) { console.error('缺少章节：' + item.sec); return; }
  const M = LIBS[item.lib];
  const group = (TOC.cols[item.lib] || {}).head || '';
  const eyebrow = M.label + ' · ' + group + ' · 第 ' + item.slot + ' 讲';
  const label = M.label + ' · ' + sec.title;

  const blocks = cutBlocks(sec.html || '');
  const h2s = blocks.filter(b => b.tag === 'h2').map(b => plain(b.html));
  const lead = plain((blocks.find(b => b.tag !== 'h2') || {}).html || '').slice(0, 140);

  /* 6.1 节导览页：大序号 + 标题 + 领读 + 本节路线 chips */
  slides.push(`<section class="slide divider" data-accent="${item.lib}">
  <div class="sbody">
    <div class="dnum">${esc(item.slot)}</div>
    <h1 class="dtitle">${esc(sec.title)}</h1>
    ${lead ? `<p class="dlead">${esc(lead)}</p>` : ''}
    <div class="droute">
      <div class="dlab">本节路线</div>
      <div class="dchips">${h2s.map(t => `<span class="dchip">${esc(t.replace(/^[一二三四五六七八九十]+、/, ''))}</span>`).join('')}</div>
    </div>
  </div>
  ${foot(M.label + ' · ' + group)}
</section>`);

  /* 6.2 内容页 */
  paginate(blocks).forEach(pg => {
    slides.push(`<section class="slide" data-accent="${item.lib}">
  <div class="sbody article">
    <div class="eyebrow">${esc(eyebrow)}</div>
    ${pg.title ? `<h2 class="sh">${esc(pg.title)}</h2>` : ''}
    ${pg.blocks.join('')}
  </div>
  ${foot(label)}
</section>`);
  });

  /* 6.3 配图页：一图一页，图注与课堂用法一并带上 */
  (FMAP[item.sec] || []).forEach(it => {
    const F = FIGS[it.f];
    if (!F) return;
    slides.push(`<section class="slide figslide" data-accent="${item.lib}">
  <div class="sbody article">
    <div class="eyebrow">${esc(eyebrow)}　·　配图</div>
    <h2 class="sh"><span class="fno" style="background:${M.color}">图 ${FIG_NO[it.f]}</span>${esc(F.t)}</h2>
    <div class="scv">${String(F.svg || '').trim()}</div>
    <div class="scap"><p>${esc(F.cap)}</p><p class="teach"><b>课堂用法：</b>${esc(F.teach)}</p></div>
  </div>
  ${foot(label)}
</section>`);
  });
});

/* ---------- 7. 封面、目录与收尾 ---------- */
const nWord = SCOPE.reduce((n, x) => n + weightOf((ROOTS[x.lib].sections[x.sec] || {}).html || ''), 0);
const nFig = SCOPE.reduce((n, x) => n + (FMAP[x.sec] || []).length, 0);
const libCount = {}; SCOPE.forEach(x => { libCount[x.lib] = (libCount[x.lib] || 0) + 1; });
const libOrder = Object.keys(LIBS).filter(k => libCount[k]);

const cover = `<section class="slide cover">
  <div class="sbody">
    <div class="clab">${esc(DECK.eyebrow)}</div>
    <h1>${esc(DECK.title)}</h1>
    <p class="csub">${esc(DECK.subtitle)}</p>
    <div class="cgrid">
      ${libOrder.map(k => `<div class="ccell"><div class="cn">${libCount[k]}</div><div class="cl">${esc(LIBS[k].label)}专题（节）</div></div>`).join('')}
      <div class="ccell"><div class="cn">${nFig}</div><div class="cl">配套图示</div></div>
      <div class="ccell"><div class="cn">${(nWord / 10000).toFixed(1)} 万</div><div class="cl">正文规模（字）</div></div>
    </div>
    <div class="ckeys"><span><b>← →</b> 翻页</span><span><b>空格</b> 下一页</span><span><b>F</b> 全屏</span><span><b>P</b> 打印 / 导出 PDF</span><span><b>Home / End</b> 首末页</span></div>
    <p class="cnote">${DECK.note}</p>
  </div>
</section>`;

const toc = `<section class="slide">
  <div class="sbody article">
    <div class="eyebrow">目录</div>
    <h2 class="sh">${esc(TOC.head)}</h2>
    <div class="tocgrid" style="grid-template-columns:repeat(${libOrder.length},1fr)">
      ${libOrder.map(k => `<div class="toccol" data-accent="${k}">
        <div class="tochd">${esc((TOC.cols[k] || {}).head || LIBS[k].label)}<br><span>${esc((TOC.cols[k] || {}).sub || '')}</span></div>
        ${SCOPE.filter(x => x.lib === k).map(x => `<div class="tocit"><b>${x.slot}</b>${esc((ROOTS[k].sections[x.sec] || {}).title || x.sec)}</div>`).join('')}
      </div>`).join('')}
    </div>
    ${TOC.note ? `<div class="blk note"><div class="bt">${esc(TOC.note.title)}</div>
      <p>${TOC.note.body}</p></div>` : ''}
  </div>
  ${foot('目录')}
</section>`;

const endSlide = `<section class="slide">
  <div class="sbody article">
    <div class="eyebrow">${esc(END.eyebrow)}</div>
    <h2 class="sh">${esc(END.title)}</h2>
    ${END.items.map(it => `<div class="blk ${esc(it.kind)}"><div class="bt">${esc(it.t)}</div>
      <p>${it.p}</p></div>`).join('')}
  </div>
  ${foot(END.eyebrow)}
</section>`;

/* ---------- 8. 样式 ----------
   版式直接复用 index.html 的 <style>，保证课件与知识库同一套视觉。
   下面只加课件特有的部分（整屏翻页、封面、导览页、配图页、目录、控制条、打印）。 */
const baseCss = (fs.readFileSync(path.join(dir, 'index.html'), 'utf8').match(/<style>([\s\S]*?)<\/style>/) || [, ''])[1];

const accentRules = libOrder.map(k =>
  `.slide[data-accent="${k}"],.toccol[data-accent="${k}"]{--accent:var(${LIBS[k].accentVar});--accent-soft:var(${LIBS[k].accentVar}-soft)}`
).join('\n');

const deckCss = `

/* ================= 课件专用样式 ================= */
html,body{height:100%;overflow:hidden;background:#e9edf2;font-size:15px}
#deck{position:absolute;inset:0}
.slide{position:absolute;left:0;right:0;top:0;bottom:0;display:none;background:var(--bg);overflow:auto}
.slide.on{display:block}
.sbody{max-width:1180px;margin:0 auto;padding:38px 56px 80px}
.sfoot{position:fixed;left:0;right:0;bottom:0;height:34px;background:rgba(255,255,255,.95);
  border-top:1px solid var(--line);display:flex;align-items:center;gap:14px;
  padding:0 24px;font-size:11.5px;color:var(--muted);z-index:20}
.sfoot .pg{margin-left:auto;font-variant-numeric:tabular-nums}
${accentRules}
.eyebrow{font-size:12.5px;font-weight:700;letter-spacing:.6px;color:var(--muted);margin-bottom:7px}
.article h2.sh{font-size:24px;margin:0 0 14px;padding-left:13px;border-left:5px solid var(--accent);
  line-height:1.4;letter-spacing:-.2px;display:flex;align-items:center;gap:10px}
.slide .article{font-size:15.5px}
.slide .article p{margin:11px 0;line-height:1.85}
.slide .article table{font-size:14px}
.slide .article table thead th,.slide .article table td{padding:8px 11px}
.slide .article .blk{font-size:14.5px}
.slide .article h3.sh2{font-size:16.5px;font-weight:700;margin:20px 0 8px;padding-left:9px;
  border-left:3px solid var(--line);color:var(--text)}

/* 封面 */
.cover{background:linear-gradient(140deg,#12325c 0%,#1a4d8f 42%,#7d2a2a 100%);color:#fff}
.cover .sbody{padding:76px 56px}
.cover .clab{font-size:13px;letter-spacing:3px;color:#cbd9ef;font-weight:700}
.cover h1{font-size:50px;margin:12px 0 10px;letter-spacing:-1px;line-height:1.15}
.cover .csub{font-size:17.5px;color:#dbe5f5;margin:0 0 34px}
.cgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;max-width:920px}
.ccell{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:12px;padding:16px 18px}
.ccell .cn{font-size:30px;font-weight:700;line-height:1.2}
.ccell .cl{font-size:12.5px;color:#d5e0f2}
.ckeys{display:flex;gap:20px;flex-wrap:wrap;margin:34px 0 0;font-size:13px;color:#e3ebf8}
.ckeys b{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.3);border-radius:5px;padding:2px 8px;font-size:12px}
.cover .cnote{margin-top:28px;font-size:12.5px;color:#c9d6ea;line-height:1.9;max-width:920px;
  border-top:1px solid rgba(255,255,255,.2);padding-top:15px}
.cover .cnote b{color:#fff}

/* 节导览页 */
.divider .sbody{padding:64px 56px}
.dnum{font-size:84px;font-weight:800;line-height:.95;color:var(--accent);opacity:.22;letter-spacing:-3px}
.dtitle{font-size:36px;margin:6px 0 16px;letter-spacing:-.5px;line-height:1.3;max-width:980px}
.dlead{font-size:16.5px;color:var(--text-2);max-width:920px;line-height:1.9;margin:0 0 30px}
.droute{border-top:1px solid var(--line);padding-top:20px;max-width:1060px}
.dlab{font-size:12.5px;font-weight:700;color:var(--muted);letter-spacing:.6px;margin-bottom:10px}
.dchips{display:flex;flex-wrap:wrap;gap:8px}
.dchip{font-size:13.5px;background:#fff;border:1px solid var(--line);border-radius:20px;padding:5px 15px;color:var(--text-2)}
.dchip:first-child{background:var(--accent-soft);border-color:var(--accent);color:var(--accent);font-weight:600}

/* 配图页 */
.figslide .scv{margin:4px 0 12px}
.figslide .scv svg{width:100%;height:auto;display:block;max-height:50vh}
.figslide .scap{border-top:1px dashed var(--line);padding-top:12px;font-size:13.5px;color:var(--text-2);line-height:1.8}
.figslide .scap .teach{color:var(--muted);font-size:12.8px;margin-top:7px}
.figslide .scap .teach b{color:var(--text-2)}
.fno{font-size:12px;font-weight:700;color:#fff;border-radius:5px;padding:3px 9px;white-space:nowrap;flex:none}

/* 目录页 */
.tocgrid{display:grid;gap:26px;margin:6px 0 20px}
.toccol{border:1px solid var(--line);border-radius:12px;background:#fff;padding:16px 18px}
.toccol .tochd{font-weight:700;font-size:14px;padding-bottom:10px;margin-bottom:8px;border-bottom:1px solid var(--line-2);line-height:1.6;color:var(--accent)}
.toccol .tochd span{font-weight:400;font-size:12.5px;color:var(--muted)}
.tocit{font-size:13.8px;color:var(--text-2);padding:5px 0;line-height:1.5}
.tocit b{display:inline-block;min-width:22px;color:var(--muted);font-weight:700}

/* 控制条 */
#hud{position:fixed;right:18px;bottom:46px;z-index:30;display:flex;align-items:center;gap:4px;
  background:rgba(255,255,255,.96);border:1px solid var(--line);border-radius:999px;padding:5px 8px;
  box-shadow:0 4px 16px rgba(16,24,40,.1);font-size:12.5px;color:var(--text-2)}
#hud button{border:0;background:transparent;cursor:pointer;font-size:15px;line-height:1;color:var(--text-2);
  padding:5px 9px;border-radius:999px;font-family:inherit}
#hud button:hover{background:var(--accent-soft);color:var(--accent)}
#hud .n{font-variant-numeric:tabular-nums;padding:0 4px;white-space:nowrap}
#hud .n b{color:var(--text)}
#bar{position:fixed;left:0;top:0;height:3px;background:#1a4d8f;z-index:40;width:0}
#tip{position:fixed;left:18px;bottom:46px;z-index:30;font-size:12px;color:var(--muted);
  background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:999px;padding:5px 14px;
  transition:opacity .8s}
/* 打印：全部页面顺序铺开，A4 横向，一页一张 */
@media print{
  html,body{overflow:visible;background:#fff}
  #hud,#tip,#bar{display:none}
  .sfoot{display:none}
  .slide{position:static;display:block !important;page-break-after:always;break-after:page;overflow:visible;height:auto}
  .slide:last-child{page-break-after:auto;break-after:auto}
  .sbody{padding:0 0 8mm;max-width:none}
  .slide .article{font-size:12.5px}
  .slide .article table{font-size:11.5px}
  .article h2.sh{font-size:19px}
  .cover h1{font-size:34px}
  .dtitle{font-size:26px}
  .figslide .scv svg{max-height:none}
  @page{size:A4 landscape;margin:12mm}
}
`;

/* ---------- 9. 组装 ---------- */
const accentMap = JSON.stringify(libOrder.reduce((o, k) => (o[k] = LIBS[k].color, o), {}));

const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${esc(DECK.title)}</title>
<style>${baseCss}${deckCss}</style>
</head>
<body>
<div id="bar"></div>
<div id="deck">
${[cover, toc].concat(slides, [endSlide]).join('\n')}
</div>
<div id="hud">
  <button id="bPrev" title="上一页（←）">‹</button>
  <span class="n"><b id="cur">1</b> / <span id="tot">1</span></span>
  <button id="bNext" title="下一页（→ / 空格）">›</button>
  <button id="bFull" title="全屏（F）">⛶</button>
  <button id="bPrint" title="打印 / 导出 PDF（P）">⎙</button>
</div>
<div id="tip">← → 翻页 · 空格下一页 · F 全屏 · P 打印</div>
<script>
(function(){
  var ACCENT = ${accentMap};
  var slides = [].slice.call(document.querySelectorAll('#deck > .slide'));
  var i = 0;
  var cur = document.getElementById('cur');
  var bar = document.getElementById('bar');
  document.getElementById('tot').textContent = slides.length;
  function pad(n){ return (n < 10 ? '0' : '') + n; }
  function show(n, silent){
    if (n < 0) n = 0;
    if (n > slides.length - 1) n = slides.length - 1;
    slides[i].classList.remove('on');
    i = n;
    var s = slides[i];
    s.classList.add('on');
    s.scrollTop = 0;
    var p = s.querySelector('.pg');
    if (p) p.textContent = pad(i + 1) + ' / ' + pad(slides.length);
    cur.textContent = i + 1;
    bar.style.width = ((i + 1) / slides.length * 100) + '%';
    bar.style.background = ACCENT[s.getAttribute('data-accent')] || '#1a4d8f';
    if (!silent) { try { history.replaceState(null, '', '#s=' + (i + 1)); } catch (e) { location.hash = 's=' + (i + 1); } }
  }
  function next(){ show(i + 1); }
  function prev(){ show(i - 1); }
  function full(){
    if (document.fullscreenElement) document.exitFullscreen();
    else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
  }
  document.getElementById('bNext').onclick = next;
  document.getElementById('bPrev').onclick = prev;
  document.getElementById('bFull').onclick = full;
  document.getElementById('bPrint').onclick = function(){ window.print(); };
  window.addEventListener('keydown', function(e){
    if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    var k = e.key;
    if (k === 'ArrowRight' || k === 'ArrowDown' || k === ' ' || k === 'PageDown' || k === 'Enter') { e.preventDefault(); next(); }
    else if (k === 'ArrowLeft' || k === 'ArrowUp' || k === 'PageUp') { e.preventDefault(); prev(); }
    else if (k === 'Home') { e.preventDefault(); show(0); }
    else if (k === 'End') { e.preventDefault(); show(slides.length - 1); }
    else if (k === 'f' || k === 'F') { e.preventDefault(); full(); }
    else if (k === 'p' || k === 'P') { e.preventDefault(); window.print(); }
  });
  var start = 1;
  var m = (location.hash || '').match(/s=(\\d+)/);
  if (m) start = parseInt(m[1], 10) || 1;
  show(start - 1, true);
  setTimeout(function(){ var t = document.getElementById('tip'); if (t) t.style.opacity = '0'; }, 4500);
})();
</script>
</body>
</html>`;

fs.writeFileSync(path.join(dir, OUT_FILE), html, 'utf8');
const totalPages = slides.length + 3;
console.log('课件已生成：' + OUT_FILE);
console.log('  共 ' + totalPages + ' 页 = 封面 1 + 目录 1 + 正文 ' + slides.length + ' + 收尾 1');
console.log('  覆盖 ' + SCOPE.length + ' 节 / ' + nFig + ' 张配图 / 正文约 ' + (nWord / 10000).toFixed(1) + ' 万字');
console.log('  单文件 ' + (Buffer.byteLength(html, 'utf8') / 1024).toFixed(0) + ' KB，离线可用');
