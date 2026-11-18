/* ============================================================
   kb-config.js —— 共享配置层（所有脚本从这里取「库清单 / 标签 / 私有断言」）
   ------------------------------------------------------------
   为什么要有这一层：
     校验与导出脚本原先各自写死库清单（TOPIC_A_DATA / TOPIC_B_DATA …）与显示名，
     换一个知识库就得改 5 个脚本；而项目私有的断言（本项目迁了哪些节、
     哪些节 id 参与口径自查）更不该出现在**对外分发**的包里。

   三层取值优先级（与「抽配置层，而不是删参数」的纪律一致）：
     ① 环境变量 / 命令行（调用方显式指定）
     ② 同目录 kb.config.json（**本机私有，不随包发布**）
     ③ 自动探测（默认，任何知识库都能跑）

   自动探测怎么拿到「库序」：
     index.html 里 <script src> 的出现顺序 = 数据加载顺序 = 库序。
     若页面已是 bundle 形态（bundle/xxx.js），先按 bundle 头部的
     「合成自：a.js、b.js」反解回源文件清单，再按出现顺序抓 root 名。
     图册（groups[].figs、sections 为空）计入库序，图示数据分片
     （FIG_DATA_*，求值后并不存在 FIG_DATA 根对象）自动被过滤。
   ============================================================ */
const fs = require('fs');
const path = require('path');

/* ---------- ② 私有配置（可选） ---------- */
function localConfig(dir) {
  const p = path.join(dir || '.', 'kb.config.json');
  if (!fs.existsSync(p)) return {};
  try { return JSON.parse(fs.readFileSync(p, 'utf8')) || {}; }
  catch (e) { console.log(`  ! kb.config.json 解析失败（已忽略）：${e.message}`); return {}; }
}

/* 独立图册页的文件名与标题（不含 .html 后缀）：默认中性的「图示册」，
   可用 kb.config.json 的 atlasHtml 覆盖——项目里若一直叫某个特定名字，写进去即可保持产物不变。 */
function atlasName(dir) {
  const c = localConfig(dir);
  return String(c.atlasHtml || '图示册').replace(/\.html?$/i, '');
}

/* 把 index.html 的 script 标签按加载顺序摊平为源文件清单 */
function scriptSources(dir) {
  const idx = path.join(dir, 'index.html');
  if (!fs.existsSync(idx)) return [];
  const html = fs.readFileSync(idx, 'utf8');
  const out = [];
  for (const m of html.matchAll(/<script\s+src="([^"]+\.js)"/g)) {
    const f = m[1];
    if (f.indexOf('://') >= 0) continue;
    if (f.indexOf('bundle/') === 0) {
      const bp = path.join(dir, f);
      if (!fs.existsSync(bp)) continue;
      const mm = fs.readFileSync(bp, 'utf8').match(/合成自：([^\n]+)\n/);
      if (mm) mm[1].split('、').map(x => x.trim()).filter(Boolean).forEach(x => out.push(x));
    } else out.push(f);
  }
  return out;
}

/* 从一个数据文件里抓「根对象名」：window.TOPIC_A_DATA = { / window.TOPIC_A_DATA_27 = { 都归 TOPIC_A_DATA */
const ROOT_RE = /window\.([A-Z][A-Z0-9_]*?)(?:_\d+)?\s*=\s*\{/g;
function rootsOf(dir, file) {
  const p = path.join(dir, file);
  if (!fs.existsSync(p)) return [];
  const s = fs.readFileSync(p, 'utf8');
  const out = [];
  let m;
  ROOT_RE.lastIndex = 0;
  while ((m = ROOT_RE.exec(s)) !== null) if (out.indexOf(m[1]) < 0) out.push(m[1]);
  return out;
}

/* 按编号顺序收集同根分片（TOPIC_A_DATA_2 / TOPIC_A_DATA_3 …） */
function collect(win, prefix) {
  return Object.keys(win || {})
    .filter(k => k.indexOf(prefix + '_') === 0 && /_\d+$/.test(k))
    .sort((a, b) => parseInt(a.replace(/^.*_/, ''), 10) - parseInt(b.replace(/^.*_/, ''), 10))
    .map(k => win[k]);
}

/* 合并分片后的库视图（不改动原对象）。
   ⚠️ 必须合并后再判定：很多库的**根分片 sections 是空的**，章节与分组都在后续分片里，
   只看根分片会把整个库误判成「不存在」。 */
function resolved(win, root) {
  const base = win && win[root];
  if (!base) return null;
  const out = { sections: Object.assign({}, base.sections || {}), groups: base.groups || [] };
  collect(win, root).forEach(p => {
    if (!p || !p.sections) return;
    for (const k in p.sections) out.sections[k] = p.sections[k];
    if (p.isFinalGroups && p.groups) out.groups = p.groups;
  });
  return out;
}

/* ---------- ③ 自动探测库清单 ---------- */
/* 库序的唯一权威来源：index.html 里 `LIBS.push(window.XXX)` 的书写顺序
   （图册也在其中，位置自然正确；本引擎的所有库都这么拼 LIBS）。
   拿不到就退回「按脚本加载顺序推断」。
   返回 [{ idx, root, prefix, atlas, name, sections, groups }] */
function libOrderFromIndex(dir) {
  const idx = path.join(dir, 'index.html');
  if (!fs.existsSync(idx)) return [];
  const html = fs.readFileSync(idx, 'utf8');
  const out = [];
  for (const m of html.matchAll(/LIBS\.push\(\s*window\.([A-Z][A-Z0-9_]*)\s*\)/g)) {
    if (out.indexOf(m[1]) < 0) out.push(m[1]);
  }
  return out;
}

function libs(dir, win, opts) {
  opts = opts || {};
  const cfg = localConfig(dir);
  let order = libOrderFromIndex(dir);
  let orderSrc = 'index.html 的 LIBS.push 顺序';
  if (!order.length) {
    orderSrc = '脚本加载顺序（index.html 缺少 LIBS.push）';
    for (const f of scriptSources(dir)) {
      if (!/^(data-.*|figs.*)\.js$/i.test(f)) continue;
      rootsOf(dir, f).forEach(r => { if (order.indexOf(r) < 0) order.push(r); });
    }
    if (!order.length) { orderSrc = 'window 键顺序（兜底）'; Object.keys(win || {}).forEach(r => order.push(r)); }
  }

  const out = [];
  order.forEach(root => {
    const o = resolved(win, root);
    if (!o) return;                                   /* 根对象不存在（如 FIG_DATA_* 只有分片名） */
    const hasSecs = Object.keys(o.sections).length > 0;
    const isAtlas = !!(o.groups && o.groups.some(g => g.figs && g.figs.length));
    if (!hasSecs && !isAtlas) return;                 /* FIG_MAP 之类，不是库 */
    out.push({
      idx: out.length,
      root,
      prefix: root,
      atlas: isAtlas && !hasSecs,
      name: String((cfg.libNames || {})[root] || (win[root] || {}).tab || (win[root] || {}).title || root),
      raw: win[root],                 /* 原始根对象（供需要就地合并分片的调用方使用） */
      sections: o.sections,
      groups: o.groups
    });
  });

  /* 允许配置显式指定顺序（当 index.html 不是按库序加载时） */
  if (Array.isArray(cfg.libOrder) && cfg.libOrder.length) {
    out.sort((a, b) => {
      const ia = cfg.libOrder.indexOf(a.root), ib = cfg.libOrder.indexOf(b.root);
      return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib);
    });
    out.forEach((l, i) => { l.idx = i; });
    orderSrc += ' + kb.config.json 的 libOrder 覆盖';
  }
  libs.orderSource = orderSrc;
  return out;
}
libs.collect = collect;
libs.resolved = resolved;


/* 按 root 名从 win 取库；找不到返回 null（调用方自行跳过，不要报错） */
function pick(win, root) {
  const o = win && win[root];
  return (o && o.sections) ? o : null;
}

/* ---------- 图示 kind → 显示标签（中性默认，可被 kb.config.json 覆盖） ---------- */
const DEFAULT_LABELS = { default: '知识库', atlas: '图示册' };
function labels(dir) {
  const cfg = localConfig(dir);
  return Object.assign({}, DEFAULT_LABELS, cfg.figLabels || {});
}
function labelOf(dir, kind) {
  const t = labels(dir);
  return t[kind] || t.default;
}

/* ---------- 项目私有断言（可选文件，不随包发布） ---------- */
function projectChecks(dir) {
  const p = path.join(dir, 'project-checks.js');
  if (!fs.existsSync(p)) return null;
  try { return require(p); }
  catch (e) { console.log(`  ! project-checks.js 加载失败（已跳过）：${e.message}`); return null; }
}

module.exports = { libs, pick, labels, labelOf, localConfig, atlasName, scriptSources, projectChecks, collect: libs.collect, resolved: libs.resolved };
