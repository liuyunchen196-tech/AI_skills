/* ============================================================
   内容层校验（check-data.js）
   ------------------------------------------------------------
   用法：node check-data.js
   检查项：
     1. 每个 data-*.js 能正常求值（语法）
     2. 单文件体积硬线：不超过 64 KB（超出会报「建议再分片」）
     3. 分片合并后：分组定义里出现的章节 id 是否都已定义（缺挂载）
     4. 是否有多余章节（定义了但没有归入任何分组）
     5. 每个章节的 <div> / </div>、<table> / </table> 是否配平
     6. 元数据转义字段（title/homeTitle/desc/tags、章节 title/desc/tags）
        中不得出现 HTML 标签——这些字段走 esc(...) 渲染，写标签会被当文字显示
     7. 恰好一个分片带 isFinalGroups（分组定义只能在末片）
     8. 三套功能轨道完整性（正文 / 总导读 / 速查自测）——每个库三条都要有
     9. 时效标注完整性——每个章节都要带统一的「本节口径」声明（P0 硬拦截）
   退出码：0 = 全部通过；1 = 存在错误
   ============================================================ */
const fs = require('fs');
const path = require('path');
const dir = __dirname;
const SIZE_HARD = 64 * 1024;
/* 库清单 / 标签 / 私有断言全部走共享配置层，脚本本身不写死任何库名 */
const KBC = require('./kb-config.js');

let errors = 0, warns = 0;
const err = m => { errors++; console.log('  ✗ ' + m); };
const warn = m => { warns++; console.log('  ! ' + m); };

/* ---------- 1. 加载全部分片 ---------- */
console.log('\n【1】分片加载与体积');
const files = fs.readdirSync(dir).filter(f => /^data-.*\.js$/i.test(f)).sort();
global.window = {};
for (const f of files) {
  const p = path.join(dir, f);
  const src = fs.readFileSync(p, 'utf8');
  const kb = (Buffer.byteLength(src, 'utf8') / 1024).toFixed(1);
  try {
    new Function(src)();
  } catch (e) {
    err(`${f} 求值失败：${e.message}`);
    continue;
  }
  const over = Buffer.byteLength(src, 'utf8') > SIZE_HARD;
  console.log(`  · ${f.padEnd(18)} ${String(kb).padStart(6)} KB${over ? '  ← 超 64 KB' : ''}`);
  if (over) err(`${f} 超过 64 KB 硬线（${kb} KB），建议再分片`);
}

/* ---------- 2. 合并分组与章节 ---------- */
function collect(prefix) {
  return Object.keys(global.window)
    .filter(k => k.indexOf(prefix + '_') === 0 && /_\d+$/.test(k))
    .sort((a, b) => parseInt(a.replace(/^.*_/, ''), 10) - parseInt(b.replace(/^.*_/, ''), 10))
    .map(k => global.window[k]);
}
const LIBS = KBC.libs(dir, global.window);
console.log(`  · 库序来源：${KBC.libs.orderSource || '自动探测'}（共 ${LIBS.length} 个库）`);
if (!LIBS.length) err('未探测到任何知识库（检查 index.html 的 LIBS.push 与 data-*.js）');

for (const lib of LIBS) {
  const ROOT = lib.raw;
  if (!ROOT) { err(`缺少 ${lib.prefix}（根对象不存在）`); continue; }
  const parts = collect(lib.prefix);
  let finalCount = 0, finalName = '';
  parts.forEach(p => {
    if (!p || !p.sections) return;          /* 无 sections 的分片会被 index.html 的 merge() 整体跳过 */
    for (const k in p.sections) ROOT.sections[k] = p.sections[k];
    if (p.isFinalGroups) { ROOT.groups = p.groups; finalCount++; finalName = lib.prefix; }
  });

  console.log(`\n【2】${lib.name}：分片 ${parts.length} 个，章节 ${Object.keys(ROOT.sections).length} 个，分组 ${(ROOT.groups || []).length} 组`);
  if (finalCount !== 1) err(`${lib.name} 带 isFinalGroups 的分片数量 = ${finalCount}（应恰好 1 个）`);
  else console.log(`  · 分组定义来源：${finalName} ✓`);

  /* 分组 ↔ 章节 双向核对 */
  const inGroups = [];
  (ROOT.groups || []).forEach(g => (g.secs || g.sections || g.items || []).forEach(s => inGroups.push(s)));
  const defined = Object.keys(ROOT.sections);
  const missing = inGroups.filter(s => !ROOT.sections[s]);
  const orphan = defined.filter(s => inGroups.indexOf(s) < 0);
  if (missing.length) err(`${lib.name} 分组引用了未定义的章节：${missing.join(', ')}`);
  if (orphan.length) err(`${lib.name} 有章节未归入任何分组：${orphan.join(', ')}`);
  if (!missing.length && !orphan.length)
    console.log(`  · 分组引用 ${inGroups.length} 个章节，全部已定义，无多余章节 ✓`);

  /* ---------- 3. 逐章节结构检查 ---------- */
  console.log(`\n【3】${lib.name} 章节结构与元数据`);
  for (const id of defined) {
    const s = ROOT.sections[id] || {};
    const html = s.html || '';
    const cd = (html.match(/<div\b/g) || []).length, cd2 = (html.match(/<\/div>/g) || []).length;
    const ct = (html.match(/<table\b/g) || []).length, ct2 = (html.match(/<\/table>/g) || []).length;
    const bad = [];
    if (cd !== cd2) bad.push(`div ${cd}/${cd2}`);
    if (ct !== ct2) bad.push(`table ${ct}/${ct2}`);
    if (/<[a-z\/][^>]*>/i.test(String(s.desc || ''))) bad.push('desc 含 HTML 标签');
    if (/<[a-z\/][^>]*>/i.test(String(s.title || ''))) bad.push('title 含 HTML 标签');
    if (bad.length) err(`[${lib.name}] ${id}：${bad.join(' | ')}`);
  }
  /* 根分片元数据 */
  ['title', 'homeTitle', 'desc'].forEach(f => {
    if (/<[a-z\/][^>]*>/i.test(String(ROOT[f] || '')))
      err(`${lib.name} 根元数据 ${f} 含 HTML 标签（走 esc 渲染，须为纯文本）`);
  });
}

/* ---------- 4. index.html 挂载一致性 ---------- */
console.log('\n【4】index.html 脚本挂载');
const idxPath = path.join(dir, 'index.html');
if (!fs.existsSync(idxPath)) err('index.html 不存在');
else {
  const idx = fs.readFileSync(idxPath, 'utf8');
  /* index.html 里现在是 bundle/ 形态，要把 bundle 标签反解回它合成的源文件清单，
     否则每个分片都会被判成「存在但未挂载」 */
  function expand(f) {
    if (f.indexOf('bundle/') !== 0) return [f];
    const bp = path.join(dir, f);
    if (!fs.existsSync(bp)) return [];
    const m = fs.readFileSync(bp, 'utf8').match(/合成自：([^\n]+)\n/);
    return m ? m[1].split('、').map(x => x.trim()) : [];
  }
  const tags = [...idx.matchAll(/<script\s+src="([^"]+\.js)"/g)].map(m => m[1]);
  const mounted = [];
  tags.forEach(f => expand(f).forEach(x => mounted.push(x)));
  const need = files.filter(f => mounted.indexOf(f) < 0);
  const dead = tags.filter(m => m.indexOf('://') < 0 && !fs.existsSync(path.join(dir, m)));
  if (need.length) err(`以下分片存在但未在 index.html 中挂载：${need.join(', ')}`);
  if (dead.length) err(`index.html 引用了不存在的文件：${dead.join(', ')}`);
  if (!need.length && !dead.length) console.log(`  · 共挂载 ${tags.length} 个脚本标签（反解 ${mounted.length} 个源文件），全部存在且齐备 ✓`);
}

/* ---------- 5. 规模统计与库元数据一致性（项目私有断言，可选） ----------
   这一段（各库 subtitle 口径、判例库分组起点、迁移完整性…）是**本项目的业务规则**，
   不是通用规则，因此整体抽到 project-checks.js：该文件存在就跑，不存在就跳过。
   对外分发的包里不带它——别人换上自己的断言即可。 */
const PC = KBC.projectChecks(dir);
if (PC) PC({ win: global.window, LIBS, err, warn, errors: () => errors, log: console.log });
else console.log('\n【5】规模统计与库元数据一致性：未提供 project-checks.js，跳过（项目私有断言）');

/* ===== 三套功能轨道完整性（库成熟度检查项，2026-10-01 采纳）=====
   每个知识库都应具备三条功能轨道：
     ① 正文轨道   —— 库的主体内容
     ② 总导读轨道 —— 「本库怎么读、先读什么」，level 含「导读」
     ③ 速查自测轨道 —— 「问—答—依据」形式的自测题，level 含「自测」/「速查」
   缺哪条报哪条。新建库时必须在同一批次内把 ② ③ 一并补齐，
   否则新库天生「两条轨道空着」，日后审计必然被列为缺口。 */
{
  const TRACK_LIBS = LIBS.map(l => ({ name: l.name, root: l.raw }));
  const isOver = s => /导读/.test(String((s || {}).level || '') + String((s || {}).title || ''));
  const isSelf = s => /自测|速查/.test(String((s || {}).level || '') + String((s || {}).title || ''));
  console.log('\n【6】三套功能轨道完整性（正文 / 总导读 / 速查自测）');
  TRACK_LIBS.forEach(lib => {
    if (!lib.root) return;
    const secs = lib.root.sections || {};
    const cur = Object.keys(secs);
    const guide = cur.filter(id => isOver(secs[id]));
    const self  = cur.filter(id => isSelf(secs[id]));
    const okBody = cur.length > 0;
    const mark = (ok, ids) => (ok ? `✓${ids.length ? ' ' + ids.join(', ') : ''}` : '✗ 缺失');
    console.log(`  · ${lib.name}：正文 ${mark(okBody, [])} ｜ 总导读 ${mark(guide.length > 0, guide)} ｜ 速查自测 ${mark(self.length > 0, self)}`);
    if (!okBody) err(`${lib.name}正文轨道为空`);
    if (!guide.length) err(`${lib.name}缺「总导读」轨道——新建库须在同一批次内补齐，不要留到下一轮`);
    if (!self.length)  err(`${lib.name}缺「速查自测」轨道——新建库须在同一批次内补齐，不要留到下一轮`);
  });
}

/* ===== 时效标注完整性（P0 硬拦截，2026-10-01 采纳）=====
   法律类内容的最大风险不是「写错」，而是「写对了但已经过期」。
   因此每个章节正文都必须带一段统一的「本节口径」声明——说明依据什么整理、
   以什么为准、引用前去哪里核验、旧法条文不得直接引用。

   判定标准（与 7 个库的插入模板一致）：
     · 章节 html 中必须出现 `blk scope` 容器（index.html 已有 .scope 样式）
     · 不允许出现 2 个及以上（重复插入）
   注意：仅凭正文里出现「截至 20xx 年」不算——那可能是案例叙事里的案发时间，
   属于误报。必须存在 scope 容器本身。

   新建 / 扩写章节时，把该节的口径块一并写入，否则本项直接报错退出。 */
{
  console.log('\n【7】时效标注完整性（每节「本节口径」声明）');
  const SCOPE_PAT = /blk scope/g;
  let gTotal = 0, gOk = 0, gDup = 0;
  LIBS.forEach(lib => {
    if (!lib.raw || !lib.raw.sections) return;
    const secs = lib.raw.sections;
    let total = 0, ok = 0, dup = 0;
    const bare = [];
    for (const id in secs) {
      const s = secs[id];
      if (!s || typeof s.html !== 'string' || !s.html) continue;
      total++;
      const n = (s.html.match(SCOPE_PAT) || []).length;
      if (n >= 1) ok++;
      if (n > 1) { dup++; gDup++; }
      if (n === 0) bare.push(id);
    }
    gTotal += total; gOk += ok;
    const pct = total ? Math.round(100 * ok / total) : 100;
    console.log(`  · ${lib.name}：${ok}/${total} 节（${pct}%）` + (dup ? `，重复 ${dup} 节` : ''));
    if (bare.length) {
      err(`${lib.name}有 ${bare.length} 个章节缺「本节口径」标注：${bare.slice(0, 6).join(', ')}${bare.length > 6 ? ' …' : ''}`);
    }
    if (dup) err(`${lib.name}有 ${dup} 个章节重复插入「本节口径」标注`);
  });
  console.log(`  · 合计：${gOk}/${gTotal} 节带口径声明（${gTotal ? Math.round(100 * gOk / gTotal) : 100}%）`);
}

console.log(`\n${errors ? '❌' : '✅'} 内容层校验结束：错误 ${errors} 项，提醒 ${warns} 项\n`);process.exit(errors ? 1 : 0);
