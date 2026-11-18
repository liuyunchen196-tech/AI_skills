/* ============================================================
   图示层校验（check-figs.js）
   ------------------------------------------------------------
   用法：node check-figs.js
   检查项：
     1. 每个 figs*.js 能正常求值（语法）
     2. 每张图的必备字段：t / kind / sens / cap / teach / svg
     3. 每张图的 <svg> 与 </svg> 配平且只有一个根节点
     4. FIG_MAP 的章节 id 是否真实存在（三个库都查）
     5. FIG_MAP 引用的图示 id 是否存在
     6. FIG_MAP 的 after 锚点能否命中该章节里的某个 <h2>——
        写错不会报错但会让图掉到节首，故在此硬拦
     7. FIG_ATLAS 的分组是否覆盖了全部图示，且每张图只出现一次
     8. 占位检查：svg 中不得残留 TODO / {{ }} / 未替换的模板痕迹
   退出码：0 = 全部通过；1 = 存在错误
   ============================================================ */
const fs = require('fs');
const path = require('path');
const dir = __dirname;
/* 库清单走共享配置层自动探测，脚本本身不写死任何库名 */
const KBC = require('./kb-config.js');

let errors = 0, warns = 0;
const err = m => { errors++; console.log('  ✗ ' + m); };
const warn = m => { warns++; console.log('  ! ' + m); };

/* ---------- 1. 加载数据层（取章节 id 与 html 供锚点核对） ---------- */
global.window = {};
fs.readdirSync(dir).filter(f => /^data-.*\.js$/i.test(f)).sort().forEach(f => {
  try { new Function(fs.readFileSync(path.join(dir, f), 'utf8'))(); } catch (e) { err(`${f} 求值失败：${e.message}`); }
});
function collect(prefix) {
  return Object.keys(global.window)
    .filter(k => k.indexOf(prefix + '_') === 0 && /_\d+$/.test(k))
    .sort((a, b) => parseInt(a.replace(/^.*_/, ''), 10) - parseInt(b.replace(/^.*_/, ''), 10))
    .map(k => global.window[k]);
}
const SECTIONS = {};
KBC.libs(dir, global.window).forEach(l => {
  for (const k in (l.sections || {})) SECTIONS[k] = l.sections[k];   /* 已含各分片合并结果 */
});

/* ---------- 2. 加载图示层 ---------- */
console.log('\n【1】图示分片加载');
const allFigFiles = fs.readdirSync(dir).filter(f => /^figs.*\.js$/i.test(f)).sort(
  (a, b) => parseInt(a.replace(/\D/g, '') || 0, 10) - parseInt(b.replace(/\D/g, '') || 0, 10)
);
const figFiles = allFigFiles.filter(f => f !== 'figs-map.js');
for (const f of allFigFiles) {
  const src = fs.readFileSync(path.join(dir, f), 'utf8');
  try { new Function(src)(); } catch (e) { err(`${f} 求值失败：${e.message}`); continue; }
  const kb = (Buffer.byteLength(src, 'utf8') / 1024).toFixed(1);
  console.log(`  · ${f.padEnd(12)} ${String(kb).padStart(6)} KB`);
}
const FIGS = {};
collect('FIG_DATA').forEach(p => { if (p && p.figs) for (const k in p.figs) FIGS[k] = p.figs[k]; });

/* ---------- 3. 逐图字段与 svg 检查 ---------- */
console.log('\n【2】图示字段与 svg 结构');
const FIELD = ['t', 'kind', 'sens', 'cap', 'teach', 'svg'];
let teachLong = 0;
for (const id of Object.keys(FIGS)) {
  const F = FIGS[id] || {};
  const bad = FIELD.filter(x => F[x] === undefined || F[x] === '');
  if (bad.length) { err(`${id} 缺少字段：${bad.join(', ')}`); continue; }
  const op = (F.svg.match(/<svg\b/g) || []).length, cl = (F.svg.match(/<\/svg>/g) || []).length;
  if (op !== 1 || cl !== 1) err(`${id} <svg> 标签异常（开 ${op} / 闭 ${cl}）`);
  if (/TODO|\{\{/.test(F.svg)) err(`${id} svg 含占位符（TODO / {{ }}）`);
  if (F.svg.trim().length < 40) err(`${id} svg 内容为空或过短`);
  if (String(F.teach).length > 85) { teachLong++; warn(`${id} teach ${F.teach.length} 字（惯例 ≤85）`); }
}
console.log(`  · 共 ${Object.keys(FIGS).length} 张图，字段与结构检查完成${teachLong ? `，${teachLong} 张 teach 偏长` : ''}`);

/* ---------- 4. FIG_MAP 核对 ---------- */
console.log('\n【3】FIG_MAP 挂载核对');
const FM = global.window.FIG_MAP || {};
let mapEntries = 0, anchorMiss = 0;
for (const secId in FM) {
  if (!SECTIONS[secId]) { err(`FIG_MAP 引用了不存在的章节：${secId}`); continue; }
  const html = SECTIONS[secId].html || '';
  const h2s = [...html.matchAll(/<h2[^>]*>([\s\S]*?)<\/h2>/g)].map(m => m[1]);
  const h2plain = h2s.map(t => t.replace(/<[^>]+>/g, ''));
  for (const it of FM[secId]) {
    mapEntries++;
    if (!FIGS[it.f]) { err(`${secId} 引用了不存在的图示：${it.f}`); continue; }
    if (!it.after) continue;                       /* after 留空 = 插到节首，合法 */
    const hit = h2plain.some(t => t.indexOf(it.after) >= 0) || h2s.some(t => t.indexOf(it.after) >= 0);
    if (!hit) { anchorMiss++; err(`${secId} 的锚点「${it.after}」未命中任何 <h2>`); }
  }
}
console.log(`  · FIG_MAP 共 ${mapEntries} 条挂载，涉及 ${Object.keys(FM).length} 个章节` +
  (anchorMiss ? '' : '，锚点全部命中 ✓'));

/* ---------- 5. FIG_ATLAS 核对 ---------- */
console.log('\n【4】FIG_ATLAS 图册分组');
const AT = global.window.FIG_ATLAS || { groups: [] };
const seen = {}, dup = [];
let atlasN = 0;
(AT.groups || []).forEach(g => {
  (g.figs || []).forEach(f => {
    atlasN++;
    if (!FIGS[f]) err(`图册分组「${g.title}」引用了不存在的图示：${f}`);
    if (seen[f]) dup.push(f);
    seen[f] = 1;
  });
});
if (dup.length) err(`以下图示在图册中重复出现：${[...new Set(dup)].join(', ')}`);
const uncovered = Object.keys(FIGS).filter(f => !seen[f]);
if (uncovered.length) err(`以下图示未归入任何图册分组：${uncovered.join(', ')}`);
console.log(`  · ${(AT.groups || []).length} 个板块，收录 ${atlasN} 张图；图库共 ${Object.keys(FIGS).length} 张`);
if (!uncovered.length && !dup.length) console.log('  · 全部图示恰好归入一个板块 ✓');
if (AT.subtitle) {
  const m = AT.subtitle.match(/共\s*<b>(\d+)\s*张<\/b>/);
  if (m && Number(m[1]) !== Object.keys(FIGS).length)
    err(`图册 subtitle 写「${m[1]} 张」，实际 ${Object.keys(FIGS).length} 张`);
}

/* ---------- 5. 文字溢出估算（画布级） ----------
   为什么要在意：SVG 默认 overflow:hidden，超出 viewBox 的文字会被直接裁掉，
   屏幕上看不出来，但投影或导出成图片时就是「半句话」。
   估算规则：CJK/全角按 font-size 计宽，西文数字按 0.56 倍，空格 0.28 倍；
   font-size 沿 <g> 继承。与浏览器 getBBox 实测的偏差在 3px 以内。 */
console.log('\n【5】文字溢出估算');
function estW(s, fs) {
  let w = 0;
  for (const ch of s) {
    const c = ch.codePointAt(0);
    if (c >= 0x2E80) w += fs; else if (ch === ' ') w += fs * 0.28; else w += fs * 0.56;
  }
  return w;
}
const TOKEN = /<g\b[^>]*>|<\/g>|<text\b[^>]*>[\s\S]*?<\/text>/g;
let ovf = 0;
for (const id of Object.keys(FIGS).sort()) {
  const svg = FIGS[id].svg;
  const W = Number((svg.match(/viewBox="[-\d.]+ [-\d.]+ ([\d.]+)"/) || [])[1] || 680);
  const stack = [null];
  let m, bad = [];
  TOKEN.lastIndex = 0;
  while ((m = TOKEN.exec(svg)) !== null) {
    const seg = m[0];
    if (seg.startsWith('</g>')) { if (stack.length > 1) stack.pop(); continue; }
    if (seg.startsWith('<g')) {
      const f = (seg.match(/font-size="([\d.]+)"/) || [])[1];
      stack.push(f ? Number(f) : stack[stack.length - 1]);
      continue;
    }
    const attrs = seg.slice(5, seg.indexOf('>'));
    const inner = seg.slice(seg.indexOf('>') + 1, seg.lastIndexOf('</text>')).replace(/<[^>]+>/g, '');
    if (!inner.trim()) continue;
    const own = (attrs.match(/font-size="([\d.]+)"/) || [])[1];
    const fs2 = own ? Number(own) : (stack[stack.length - 1] || 12);
    const x = Number((attrs.match(/x="([\d.\-]+)"/) || [0, 0])[1]);
    const anchor = (attrs.match(/text-anchor="(\w+)"/) || [0, 'start'])[1];
    const w = estW(inner, fs2);
    const left = anchor === 'end' ? x - w : (anchor === 'middle' ? x - w / 2 : x);
    const right = anchor === 'end' ? x : (anchor === 'middle' ? x + w / 2 : x + w);
    if (right > W - 2) bad.push(`「${inner.slice(0, 26)}」估到 ${Math.round(right)}，画布宽 ${W}`);
  }
  if (bad.length) { ovf += bad.length; bad.forEach(b => err(`${id} 文字越出画布：${b}`)); }
}
console.log(`  · ${Object.keys(FIGS).length} 张图逐行估算${ovf ? '' : '，未发现越出画布的文字 ✓'}`);

/* ---------- 6. 有内容但整节无图的情况（提醒，不报错） ---------- */
const mapSecIds = Object.keys(FM);
const emptySecs = Object.keys(SECTIONS).filter(id => mapSecIds.indexOf(id) < 0);
if (emptySecs.length) console.log(`  · 另有 ${emptySecs.length} 个章节未配图（属正常，非每节都必须有图）`);

console.log(`\n${errors ? '❌' : '✅'} 图示层校验结束：错误 ${errors} 项，提醒 ${warns} 项\n`);
process.exit(errors ? 1 : 0);
