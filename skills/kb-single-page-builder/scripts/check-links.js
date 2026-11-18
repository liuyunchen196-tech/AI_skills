/* ============================================================
   跨库链接校验 —— 检查正文里所有 href="#N/xxx" 的目标是否存在
   ------------------------------------------------------------
   为什么需要这个脚本：
     项目里两种字符串风格并存（模板串 `'id': {` 与 JSON 风格 `"id": {`），
     简单地 grep 单引号会漏掉一半的节，把有效链接误报成失效。
     本脚本用「实际求值 + 按库收节」的方式，口径与 check-data.js 一致。

   用法：node check-links.js
   ============================================================ */
const fs = require('fs');
const path = require('path');
const dir = __dirname;
/* 库清单走共享配置层自动探测（顺序取 index.html 的 LIBS.push，与页面一致） */
const KBC = require('./kb-config.js');

let errors = 0, warns = 0;
const err  = m => { console.log('  ✗ ' + m); errors++; };

/* ---------- 1. 求值所有 data-*.js，按库收节 ---------- */
global.window = {};
fs.readdirSync(dir).filter(f => /^data-.*\.js$/i.test(f)).sort().forEach(f => {
  try { new Function(fs.readFileSync(path.join(dir, f), 'utf8'))(); }
  catch (e) { err(`${f} 求值失败：${e.message}`); }
});
/* 图册的根对象定义在 figs-map.js（不是 data-*.js），单独求值一次 */
try { new Function(fs.readFileSync(path.join(dir, 'figs-map.js'), 'utf8'))(); }
catch (e) { err(`figs-map.js 求值失败：${e.message}`); }

function collect(prefix) {
  return Object.keys(global.window)
    .filter(k => k.indexOf(prefix + '_') === 0 && /_\d+$/.test(k))
    .sort((a, b) => parseInt(a.replace(/^.*_/, ''), 10) - parseInt(b.replace(/^.*_/, ''), 10))
    .map(k => global.window[k]);
}

/* 库序 = index.html 里 LIBS.push 的顺序（图册在那个位置自然落位） */
const SPEC = KBC.libs(dir, global.window);
if (!SPEC.length) err('未探测到任何知识库（检查 index.html 的 LIBS.push 与 data-*.js）');

const SECS = {};   /* idx -> Set(secId) */
console.log('\n【1】按库收节');
SPEC.forEach(sp => {
  const set = new Set(Object.keys(sp.sections || {}));
  /* 图册是特例：sections 恒为空，真正的「节」是 147 张图的 id，
     它们挂在 groups[].figs[] 里（与 check-figs.js 的归位口径一致）。
     正文跨库链接 #2/fig-xxx 的目标就是这些图 id，必须一并收进来。 */
  if (sp.atlas) {
    (sp.groups || []).forEach(g => (g.figs || []).forEach(f => set.add(f)));
  }
  SECS[sp.idx] = set;
  console.log(`  · #${sp.idx}  ${sp.name.padEnd(7)} ${String(set.size).padStart(3)} 节`);
});

/* ---------- 2. 扫所有 data-*.js 正文里的库内链接 ---------- */
console.log('\n【2】跨库链接目标核对');
const LINK = /href="#(\d+)\/([a-z0-9\-]+)"/g;
let total = 0;
const bad = [];
fs.readdirSync(dir).filter(f => /^data-.*\.js$/i.test(f)).sort().forEach(f => {
  const s = fs.readFileSync(path.join(dir, f), 'utf8');
  let m;
  while ((m = LINK.exec(s)) !== null) {
    total++;
    const li = parseInt(m[1], 10), sid = m[2];
    if (!SECS[li] || !SECS[li].has(sid)) bad.push(`${f}  →  #${li}/${sid}`);
  }
});

if (bad.length) {
  console.log(`  共 ${total} 条链接，失效 ${bad.length} 条：`);
  bad.forEach(b => err(b));
} else {
  console.log(`  · 共 ${total} 条链接，目标全部存在 ✓`);
}

/* ---------- 3. 反向：哪些库还没有跨库入口 ---------- */
console.log('\n【3】跨库入口覆盖度（每库被引用次数）');
const inRef = {};
SPEC.forEach(sp => { if (!sp.atlas) inRef[sp.idx] = 0; });
fs.readdirSync(dir).filter(f => /^data-.*\.js$/i.test(f)).forEach(f => {
  const s = fs.readFileSync(path.join(dir, f), 'utf8');
  let m; const re = /href="#(\d+)\/([a-z0-9\-]+)"/g;
  while ((m = re.exec(s)) !== null) {
    const li = parseInt(m[1], 10);
    if (inRef[li] !== undefined) inRef[li]++;
  }
});
SPEC.forEach(sp => {
  if (sp.atlas) return;
  const n = inRef[sp.idx] || 0;
  const mark = n === 0 ? '  ← 尚无跨库入口' : '';
  console.log(`  · ${sp.name.padEnd(7)} 被引用 ${String(n).padStart(2)} 次${mark}`);
  if (n === 0) warns++;
});

console.log(`\n${errors ? '❌' : '✅'} 跨库链接校验结束：错误 ${errors} 项，提醒 ${warns} 项\n`);
process.exit(errors ? 1 : 0);
