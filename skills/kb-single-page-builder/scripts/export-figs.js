/* ============================================================
   图示单独导出
   ------------------------------------------------------------
   产出三样：
     1. md/图示/NN_标题.svg   —— 单张矢量图（可直接插入 PPT / Word）
     2. md/图示/图示册.md      —— 图册索引（编号、标题、图注、文件名）
     3. 图示册页.html          —— 独立图册（可投影、可打印为 PDF）；页名默认「图示册」，可被 kb.config.json 的 atlasHtml 覆盖
   用法：node export-figs.js
   ============================================================ */
const fs = require('fs');
const path = require('path');
const dir = __dirname;
/* 图示 kind → 显示标签：中性默认 + kb.config.json 可覆盖 */
const KBC = require('./kb-config.js');
const ATLAS = KBC.atlasName(dir);   /* 图册页名：默认「图示册」，kb.config.json 的 atlasHtml 可覆盖 */

/* ---- 加载数据与图示 ---- */
global.window = {};
fs.readdirSync(dir).filter(f=>/\.js$/i.test(f) && /^(data-|figs)/.test(f)).sort().forEach(f=>{
  try { new Function(fs.readFileSync(path.join(dir,f),'utf8'))(); } catch(e){}
});
function collect(prefix){
  return Object.keys(global.window).filter(k=>k.indexOf(prefix+'_')===0 && /_\d+$/.test(k))
    .sort((a,b)=>parseInt(a.replace(/^.*_/,''),10)-parseInt(b.replace(/^.*_/,''),10))
    .map(k=>global.window[k]);
}
const FE = { figs: {} };
collect('FIG_DATA').forEach(p=>{ if(p&&p.figs) for(const k in p.figs) FE.figs[k]=p.figs[k]; });
const FATLAS = window.FIG_ATLAS || { groups: [] };
const FIG_NO = {}; (function(){
  let n=0;
  (FATLAS.groups||[]).forEach(g=>g.figs.forEach(f=>{ n++; FIG_NO[f]=n; }));
  Object.keys(FE.figs).forEach(f=>{ if(!FIG_NO[f]){ n++; FIG_NO[f]=n; } });
})();

function sanitizeFig(s){ return String(s).replace(/[\\/:*?"<>|（）()：、，。・\s]/g,'_').slice(0,40); }
function figFileName(fid){
  const F = FE.figs[fid]; if(!F) return '';
  let name = String(FIG_NO[fid]||0).padStart(2,'0') + '_' + sanitizeFig(F.t);
  /* 打码标记必须落在文件名上，便于课件侧一眼分辨；不依赖标题里恰好写了「打码」 */
  if (F.sens && name.indexOf('打码') < 0) name += '_已打码';
  return name + '.svg';
}
function esc(s){ return String(s||'').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

const outDir = path.join(dir, 'md', '图示');
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

/* ---- 1. 单张 SVG ---- */
function standaloneSvg(fid){
  const F = FE.figs[fid];
  let svg = F.svg.trim();
  const vb = (svg.match(/viewBox="([\d.\s-]+)"/)||[])[1] || '0 0 680 360';
  const p = vb.trim().split(/\s+/).map(Number);
  const w = p[2]||680, h = p[3]||360;
  /* 补 width/height，使 Excel / Word / Edge 渲染时不至于按默认 300×150 缩放 */
  svg = svg.replace(/<svg\b/, `<svg width="${w}" height="${h}"`);
  /* 独立文件加一层白底，避免透明背景在 Word 里显示为黑底 */
  return svg.replace(/(<svg\b[^>]*>)/, `$1\n<rect x="0" y="0" width="${w}" height="${h}" fill="#ffffff"/>`);
}
let svgCount = 0;
const rows = [];
(FATLAS.groups||[]).forEach((g, gi)=>{
  g.figs.forEach(fid=>{
    const F = FE.figs[fid]; if(!F) return;
    const fn = figFileName(fid);
    fs.writeFileSync(path.join(outDir, fn), standaloneSvg(fid), 'utf8');
    svgCount++;
    rows.push({ gi, gname: g.title, fid, F, fn });
  });
});
console.log('SVG 单图导出: ' + svgCount + ' 张 → md/图示/');

/* ---- 2. 图册索引 Markdown ---- */
let idx = '# ' + ATLAS + '\n\n';
idx += '> ' + (FATLAS.desc||'') + '\n\n';
idx += '> 共 ' + rows.length + ' 张图示，全部为教学用矢量示意图，可直接插入课件或打印。' +
       '含敏感内容的图示（共 ' + rows.filter(r=>r.F.sens).length + ' 张）均已覆盖打码图层，图内不含真实影像。\n\n';
idx += '> SVG 文件位于与本文件同级的目录中，文件名即编号与标题。\n\n---\n\n';
let lastG = -1;
rows.forEach(r=>{
  if(r.gi !== lastG){ idx += '## ' + r.gname + '\n\n'; lastG = r.gi; }
  idx += '### 图 ' + FIG_NO[r.fid] + '　' + r.F.t + (r.F.sens?'　`敏感内容已打码`':'') + '\n\n';
  idx += '- 图注：' + r.F.cap + '\n';
  idx += '- 课堂用法：' + r.F.teach + '\n';
  idx += '- 图示文件：`' + r.fn + '`\n\n';
});
fs.writeFileSync(path.join(outDir, '图示册.md'), idx, 'utf8');
console.log('图册索引: md/图示/图示册.md（' + idx.length + ' 字符）');

/* ---- 3. 独立图册 HTML ---- */
function figCard(r){
  const F = r.F;
  return `<figure class="fig" id="fig-${esc(r.fid)}">
  <div class="hd"><span class="no">图 ${FIG_NO[r.fid]}</span><span class="t">${esc(F.t)}</span>${F.sens?'<span class="sens">敏感内容已打码</span>':''}<span class="meta">${KBC.labelOf(dir, F.kind)}</span></div>
  <div class="cv">${F.svg.trim()}</div>
  <figcaption><p>${esc(F.cap)}</p><p class="teach"><b>课堂用法：</b>${esc(F.teach)}</p></figcaption>
</figure>`;
}
let toc = '', body = '', lastG2 = -1;
rows.forEach(r=>{
  if(r.gi !== lastG2){ toc += `<a href="#g${r.gi}">${esc(r.gname)}</a>`; lastG2 = r.gi; }
});
lastG2 = -1;
rows.forEach(r=>{
  if(r.gi !== lastG2){ body += `<h2 id="g${r.gi}">${esc(r.gname)}</h2>`; lastG2 = r.gi; }
  body += figCard(r);
});
const sensN = rows.filter(r=>r.F.sens).length;
const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${ATLAS}</title>
<style>
:root{--bg:#f4f6f9;--panel:#fff;--text:#1f2329;--text2:#4a5058;--muted:#828a94;
  --line:#e3e7ed;--accent:#1a4d8f;--accent2:#9a2a2a;--warn:#a8620a;--radius:10px;
  --shadow:0 1px 2px rgba(16,24,40,.04),0 4px 16px rgba(16,24,40,.06)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  font-size:15px;line-height:1.75;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding:34px 28px 100px}
h1{font-size:29px;margin:0 0 10px;letter-spacing:-.4px}
.lead{color:var(--text2);font-size:14.5px;margin:0 0 8px;max-width:780px}
.lead.small{color:var(--muted);font-size:13px}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 6px}
.stats .s{flex:1;min-width:140px;background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:12px 15px}
.stats .s .n{font-size:22px;font-weight:700;color:var(--accent);line-height:1.2}
.stats .s .l{font-size:11.5px;color:var(--muted)}
.toc{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0 8px}
.toc a{font-size:12.5px;border:1px solid var(--line);background:#fff;border-radius:20px;
  padding:4px 13px;color:var(--text2);text-decoration:none}
.toc a:hover{border-color:var(--accent);color:var(--accent);background:#eaf1fa}
h2{font-size:17px;margin:38px 0 6px;padding-left:11px;border-left:4px solid var(--accent)}
.fig{background:#fff;border:1px solid var(--line);border-radius:var(--radius);
  margin:20px 0;overflow:hidden;box-shadow:var(--shadow);page-break-inside:avoid;break-inside:avoid}
.fig .hd{display:flex;align-items:center;gap:9px;padding:10px 14px;border-bottom:1px solid #eef1f5;
  background:#fafbfc;flex-wrap:wrap}
.fig .no{font-size:11px;font-weight:700;color:#fff;background:var(--accent);border-radius:4px;padding:2px 7px;white-space:nowrap}
.fig .t{font-size:14px;font-weight:700}
.fig .sens{font-size:11px;color:var(--warn);background:#fffbeb;border:1px solid #f2e3b8;border-radius:4px;padding:1px 6px}
.fig .meta{margin-left:auto;font-size:11px;color:var(--muted)}
.fig .cv{padding:14px 16px 6px}
.fig .cv svg{width:100%;height:auto;display:block}
.fig figcaption{padding:11px 16px 14px;border-top:1px dashed var(--line);background:#fcfdfe}
.fig figcaption p{margin:0;font-size:13px;color:var(--text2)}
.fig figcaption .teach{margin-top:7px;font-size:12.5px;color:var(--muted)}
.fig figcaption .teach b{color:var(--text2)}
.note{margin-top:36px;padding:15px 17px;border-radius:var(--radius);background:#f7f8fa;
  border:1px dashed var(--line);font-size:12.5px;color:var(--muted);line-height:1.85}
@media print{
  body{background:#fff}
  .wrap{max-width:none;padding:0}
  .toc,.stats{display:none}
  h1{font-size:22px}
  h2{page-break-before:always}
  h2:first-of-type{page-break-before:avoid}
  .fig{box-shadow:none}
  .note{page-break-before:always}
}
</style>
</head>
<body>
<div class="wrap">
  <h1>${ATLAS}</h1>
  <p class="lead">${esc(FATLAS.desc||'')}</p>
  <p class="lead small">${(FATLAS.subtitle||'').replace(/<[^>]+>/g,'')}</p>
  <div class="stats">
    <div class="s"><div class="n">${rows.length}</div><div class="l">图示总数</div></div>
    <div class="s"><div class="n">${(FATLAS.groups||[]).length}</div><div class="l">主题板块</div></div>
    <div class="s"><div class="n">${sensN}</div><div class="l">含敏感内容（已打码）</div></div>
    <div class="s"><div class="n">${rows.length-sensN}</div><div class="l">常规教学图示</div></div>
  </div>
  <div class="toc">${toc}</div>
  ${body}
  <div class="note">${esc((FATLAS.footnote||'').replace(/<[^>]+>/g,''))}</div>
</div>
</body>
</html>`;
fs.writeFileSync(path.join(dir, ATLAS + '.html'), html, 'utf8');
console.log('独立图册: ' + ATLAS + '.html（' + html.length + ' 字符）');

/* ---- 4. 可选：PNG 位图（贴 PPT / Word 用） ----
   用法：node export-figs.js --png [浏览器路径]
   需要本机有 Chromium 内核浏览器（Edge / Chrome），逐个 SVG 无头截图，2 倍分辨率。 */
const wantPng = process.argv.indexOf('--png') >= 0;
if (wantPng) {
  const { execFileSync } = require('child_process');
  const { pathToFileURL } = require('url');
  const CANDIDATES = [
    process.argv[process.argv.indexOf('--png') + 1],
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/chromium'
  ].filter(Boolean);
  const browser = CANDIDATES.find(p => { try { return fs.existsSync(p); } catch(e){ return false; } });
  if (!browser) {
    console.log('未找到本机浏览器，跳过 PNG 导出（SVG 已导出，可直接使用）');
  } else {
    const pngDir = path.join(outDir, 'png');
    if (!fs.existsSync(pngDir)) fs.mkdirSync(pngDir, { recursive: true });
    /* 只清「不在本轮清单里」的旧位图（图题改名后的残留）。
       本轮的图一律覆盖写，不做整目录批量删除 —— 批量删除既慢，也容易在中断时留下半截目录。 */
    const expected = new Set(rows.map(r => r.fn.replace(/\.svg$/, '.png')));
    let purged = 0, purgeFail = 0;
    fs.readdirSync(pngDir).filter(f => /\.png$/i.test(f) && !expected.has(f)).forEach(f => {
      try { fs.unlinkSync(path.join(pngDir, f)); purged++; } catch (e) { purgeFail++; }
    });
    if (purged) console.log('清理改名残留位图: ' + purged + ' 个');
    if (purgeFail) console.log('⚠ 有 ' + purgeFail + ' 个旧位图未能删除，位图目录可能残留上一轮文件');
    let n = 0, fail = [];
    rows.forEach(r => {
      const src = path.join(outDir, r.fn);
      const svg = fs.readFileSync(src, 'utf8');
      const w = Number((svg.match(/width="(\d+)"/) || [])[1]) || 680;
      const h = Number((svg.match(/height="(\d+)"/) || [])[1]) || 360;
      const out = path.join(pngDir, r.fn.replace(/\.svg$/, '.png'));
      try {
        execFileSync(browser, [
          '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=2',
          '--window-size=' + w + ',' + h, '--virtual-time-budget=3000',
          '--screenshot=' + out, pathToFileURL(src).href
        ], { stdio: 'ignore', timeout: 60000 });
        if (fs.existsSync(out)) n++; else fail.push(r.fn);
      } catch (e) { fail.push(r.fn); }
    });
    console.log('PNG 位图导出: ' + n + '/' + rows.length + ' 张 → md/图示/png/' + (fail.length ? '（失败：' + fail.join(', ') + '）' : ''));
    /* 位图总数必须等于图示总数，多出来的就是改名残留 */
    const pngHave = fs.readdirSync(pngDir).filter(f => /\.png$/i.test(f)).length;
    if (pngHave !== rows.length) console.log('⚠ 位图目录有 ' + pngHave + ' 个文件，图示共 ' + rows.length + ' 张，请检查是否有改名残留');
  }
}
