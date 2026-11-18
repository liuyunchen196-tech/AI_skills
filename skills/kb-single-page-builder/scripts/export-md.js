/* 把 data-*.js 中的 HTML 内容转换为 Markdown，输出到 md/ 目录
   使用一个极简但正确的 HTML 解析器（支持嵌套），而非正则切割。 */
const fs = require('fs');
const path = require('path');

global.window = {};
const dir = __dirname;
/* 库清单、输出文件名、图示 kind 全部走共享配置层（脚本不写死库名） */
const KBC = require('./kb-config.js');
/* 自动扫描目录下全部 data-*.js 并加载（新增分片无需改这里） */
fs.readdirSync(dir).filter(f=>/^data-.*\.js$/i.test(f)).sort().forEach(f=>{
  new Function(fs.readFileSync(path.join(dir,f),'utf8'))();
});
/* 合并分片：按 _2 _3 _4 … 的数字顺序，带 isFinalGroups 的分片覆盖分组定义 */
function collect(prefix){
  return Object.keys(global.window).filter(k => k.indexOf(prefix + '_') === 0 && /_\d+$/.test(k))
    .sort((a,b)=>parseInt(a.replace(/^.*_/,''),10)-parseInt(b.replace(/^.*_/,''),10))
    .map(k=>global.window[k]);
}
/* 库清单（顺序 = index.html 的 LIBS.push）；分片合并的结果由 libs() 给出，
   下游直接用 l.sections / l.groups，不必再逐个库写一遍合并逻辑 */
const LIBS = KBC.libs(dir, global.window);
if (!LIBS.length) { console.error('未探测到任何知识库（检查 index.html 的 LIBS.push 与 data-*.js）'); process.exit(1); }

/* ================= 极简 HTML 解析器 ================= */
const VOID = { br:1, hr:1, img:1, input:1, meta:1, link:1 };
function parse(html){
  const root = { tag:'#root', attrs:'', children:[] };
  const stack = [root];
  const re = /<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<\/?([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>|([^<]+)/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    if (m[1] === undefined) { // 文本（含注释分支）
      const t = m[3] !== undefined ? m[3] : '';
      if (t) stack[stack.length-1].children.push({ tag:'#text', text:t });
      continue;
    }
    const tag = m[1].toLowerCase();
    const attrs = m[2] || '';
    const isClose = m[0].charAt(1) === '/';
    if (isClose) {
      for (let i = stack.length-1; i > 0; i--) {
        if (stack[i].tag === tag) { stack.length = i; break; }
      }
      continue;
    }
    const node = { tag, attrs, children:[] };
    stack[stack.length-1].children.push(node);
    if (!VOID[tag] && !/\/\s*$/.test(attrs)) stack.push(node);
  }
  return root;
}
function decode(s){
  return s.replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>')
          .replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&nbsp;/g,' ')
          .replace(/&#(\d+);/g,(m,d)=>String.fromCharCode(+d))
          .replace(/&#x([0-9a-f]+);/gi,(m,h)=>String.fromCharCode(parseInt(h,16)));
}
function escapeMd(s){ return s.replace(/\|/g,'\\|'); }
/* 行内渲染 */
function inline(nodes){
  let out = '';
  (Array.isArray(nodes) ? nodes : [nodes]).forEach(n=>{
    if (n.tag === '#text') { out += decode(n.text); return; }
    if (n.tag === 'br') { out += '\n'; return; }
    const cls = (n.attrs.match(/class="([^"]*)"/) || [,''])[1];
    const inner = inline(n.children);
    switch (n.tag) {
      case 'strong': case 'b': out += '**' + inner.trim() + '**'; break;
      case 'em': case 'i':     out += '*' + inner.trim() + '*'; break;
      case 'code':             out += '`' + inner.trim() + '`'; break;
      case 'a': {
        const href = (n.attrs.match(/href="([^"]*)"/) || [,''])[1];
        out += href ? '[' + inner.trim() + '](' + href + ')' : inner; break;
      }
      case 'span': out += (/\bno\b/.test(cls) ? inner.trim() + '　' : inner); break;
      default: out += inner;
    }
  });
  return out
    /* 防御：相邻加粗（<b>标签</b><b>标题</b>）会产出 ****，多数渲染器解析异常，补一个空格 */
    .replace(/\*\*\s*\*\*/g, '** **')
    .replace(/[ \t]{2,}/g,' ').replace(/[ \t]+\n/g,'\n');
}
/* 补全 case 卡片中「加粗标签＋紧接正文」之间的分隔 */
function fixRowLabel(s){
  return s.replace(/^\*\*([^*\n]{1,24})\*\*(?=[^：，。、；｜·）】\s*])/, function(m, inner){
    if (/\s$/.test(inner)) return m;      /* 标签本身以空格结尾，已有间隔 */
    return '**' + inner + '**：';
  });
}
/* 块级渲染 */
function render(nodes, indent, ordered){
  let md = '';
  nodes.forEach(n=>{
    if (n.tag === '#text') { const t = decode(n.text).trim(); if (t) md += t + '\n\n'; return; }
    switch (n.tag) {
      case 'h1': md += '# ' + inline(n.children).trim() + '\n\n'; break;
      case 'h2': md += '## ' + inline(n.children).trim() + '\n\n'; break;
      case 'h3': md += '### ' + inline(n.children).trim() + '\n\n'; break;
      case 'h4': case 'h5': case 'h6': md += '#### ' + inline(n.children).trim() + '\n\n'; break;
      case 'p':  md += inline(n.children).trim() + '\n\n'; break;
      case 'hr': md += '---\n\n'; break;
      case 'br': md += '\n'; break;
      case 'table': md += tableMd(n); break;
      case 'ul': case 'ol': md += listMd(n, 0); break;
      case 'div': {
        const cls = (n.attrs.match(/class="([^"]*)"/) || [,''])[1];
        if (/\bblk\b/.test(cls)) { md += blkMd(n, cls); break; }
        if (/\bbt\b/.test(cls)) { /* 标题在 blkMd 中处理 */ break; }
        if (!hasBlockChild(n)) {
          /* HTML 中 .case .row b 是 min-width:66px 的定宽列，Markdown 无此机制，
             故对「行首加粗标签 + 紧接正文」补一个全角冒号，避免标签与正文粘连 */
          let s = inline(n.children).trim();
          if (/\brow\b/.test(cls)) s = fixRowLabel(s);
          md += s + '\n\n'; break;
        }
        md += render(n.children, indent); break;
      }
      default: md += inline([n]).trim() + '\n\n';
    }
  });
  return md.replace(/\n{4,}/g, '\n\n\n');
}
/* 是否含块级子元素 */
const BLOCKTAGS = { p:1, ul:1, ol:1, table:1, div:1, h1:1, h2:1, h3:1, h4:1, h5:1, h6:1, hr:1 };
function hasBlockChild(n){
  return n.children.some(c=>c.tag !== '#text' && BLOCKTAGS[c.tag]);
}
function listMd(node, depth){
  const ordered = node.tag === 'ol';
  const items = node.children.filter(c=>c.tag === 'li');
  let md = '';
  items.forEach((li, i)=>{
    const nested = li.children.filter(c=>c.tag === 'ul' || c.tag === 'ol');
    const flat = li.children.filter(c=>c.tag !== 'ul' && c.tag !== 'ol');
    // 块级子元素（如 <p>、<div>）分离处理
    const blockKids = flat.filter(c=>['p','div','table'].includes(c.tag));
    const inlineKids = flat.filter(c=>!['p','div','table'].includes(c.tag));
    const head = inline(inlineKids).replace(/\n+/g,' ').trim();
    const bullet = (ordered ? (i+1) + '. ' : '- ');
    let text = head || (blockKids.length ? inline(blockKids[0].children).trim() : '');
    md += '    '.repeat(depth) + bullet + text + '\n';
    // 剩余块级子元素（如 li 内的 p、div）
    const rest = head ? blockKids : blockKids.slice(1);
    rest.forEach(b=>{
      const sub = render([b], depth + 1).trim();
      if (sub) sub.split('\n').forEach(l=>{ if(l.trim()) md += '    '.repeat(depth+1) + l.replace(/^[\s-]+/,'').trim() + '\n'; });
    });
    nested.forEach(nl=>{ md += listMd(nl, depth + 1); });
  });
  return md + (depth === 0 ? '\n' : '');
}
function tableMd(node){
  const rows = [];
  (function walk(n){
    n.children.forEach(c=>{
      if (c.tag === 'tr') {
        const cells = c.children.filter(x=>x.tag === 'td' || x.tag === 'th')
          .map(x=>escapeMd(inline(x.children).replace(/\n/g,' ').trim()));
        if (cells.length) rows.push(cells);
      } else if (c.tag === 'thead' || c.tag === 'tbody' || c.tag === 'table') walk(c);
    });
  })(node);
  if (!rows.length) return '';
  const w = Math.max.apply(null, rows.map(r=>r.length));
  const pad = r => { const c = r.slice(); while (c.length < w) c.push(''); return c; };
  let md = '| ' + pad(rows[0]).join(' | ') + ' |\n|' + Array(w).fill('---').join('|') + '|\n';
  rows.slice(1).forEach(r=>{ md += '| ' + pad(r).join(' | ') + ' |\n'; });
  return md + '\n';
}
const LABELS = [['law-ref','法条'],['case','案例'],['warn','注意'],['tip','要点'],['note','说明']];
function blkMd(node, cls){
  let label = '说明';
  for (const [k, v] of LABELS) { if (cls.indexOf(k) >= 0) { label = v; break; } }
  const titleEl = node.children.find(c=>c.tag === 'div' && /\bbt\b/.test((c.attrs.match(/class="([^"]*)"/)||[,''])[1]));
  if (titleEl) label = inline(titleEl.children).trim() || label;
  const bodyNodes = node.children.filter(c=>c !== titleEl);
  const body = render(bodyNodes, 1).trim();
  let md = '> **【' + label.replace(/[*【】]/g,'').trim() + '】**\n>\n';
  body.split('\n').forEach(l=>{ md += (l.trim() ? '> ' + l : '>') + '\n'; });
  return md + '\n';
}
function toMd(html){ return render(parse(html).children, 0).replace(/\n{4,}/g,'\n\n\n').trim(); }

/* ================= 图示数据 ================= */
/* 扫描 figs*.js 并加载（含 figs-map.js），合并图示分片 */
fs.readdirSync(dir).filter(f=>/^figs.*\.js$/i.test(f)).sort().forEach(f=>{
  new Function(fs.readFileSync(path.join(dir,f),'utf8'))();
});
const FE = window.FIG_DATA || { figs:{} };
collect('FIG_DATA').forEach(p=>{ if(p&&p.figs) for(const k in p.figs) FE.figs[k]=p.figs[k]; });
const FMAP = window.FIG_MAP || {};
const FATLAS = window.FIG_ATLAS || { groups:[] };

/* 全局图号与文件命名：与 index.html 的编号规则保持一致（按图册顺序） */
const FIG_NO = {}; (function(){
  let n = 0;
  (FATLAS.groups||[]).forEach(g=>g.figs.forEach(f=>{ n++; FIG_NO[f]=n; }));
  Object.keys(FE.figs).forEach(f=>{ if(!FIG_NO[f]){ n++; FIG_NO[f]=n; } });
})();
function sanitizeFig(s){ return String(s).replace(/[\\/:*?"<>|（）()：、，。・\s]/g,'_').slice(0,40); }
function figFileName(fid){
  const F = FE.figs[fid]; if(!F) return '';
  let name = String(FIG_NO[fid]||0).padStart(2,'0') + '_' + sanitizeFig(F.t);
  /* 与 export-figs.js 保持一致：打码标记落在文件名上 */
  if (F.sens && name.indexOf('打码') < 0) name += '_已打码';
  return name + '.svg';
}
/* 章节内的图示引用块（Markdown） */
function figMd(fid){
  const F = FE.figs[fid]; if(!F) return '';
  let s = '> **【图 ' + FIG_NO[fid] + '・' + F.t + '】**'
        + (F.sens ? '　`敏感内容已打码`' : '') + '\n>\n';
  s += '> ' + plain(F.cap||'') + '\n';
  if (F.teach) s += '>\n> **课堂用法：** ' + plain(F.teach) + '\n';
  s += '>\n> 图示文件：`图示/' + figFileName(fid) + '`（矢量图，可直接插入课件）\n\n';
  return s;
}
/* 把图示按锚点插进已渲染的章节 Markdown（锚点对应该小节的 ## 标题） */
function injectFigMd(secId, md){
  const list = FMAP[secId]; if(!list || !list.length) return md;
  const parts = md.split(/\n(?=## )/);
  const top = [];
  list.forEach(it=>{
    const anchor = it.after || '';
    if(!anchor){ top.push(it.f); return; }
    let hit = -1;
    for(let i=0;i<parts.length;i++){
      if(parts[i].indexOf('## ')===0 && parts[i].indexOf(anchor)>=0){ hit=i; break; }
    }
    if(hit<0){ top.push(it.f); return; }
    parts[hit] = parts[hit].replace(/\s*$/,'') + '\n\n' + figMd(it.f);
  });
  return (top.length ? top.map(figMd).join('') : '') + parts.join('\n');
}

/* ================= 输出 ================= */
const outDir = path.join(dir, 'md');
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir);
function sanitize(s){ return s.replace(/[\\/:*?"<>|]/g,'_').replace(/\s+/g,'').slice(0,60); }
function plain(s){ return decode(String(s||'').replace(/<[^>]+>/g,'')); }

function dump(lib, filename, titleText, desc, foot, atlasGroups, kind){
  let md = '# ' + titleText + '\n\n';
  if (desc) md += '> ' + plain(desc) + '\n\n';
  if (foot) md += '> ' + plain(foot) + '\n\n';
  md += '---\n\n## 目录\n\n';
  lib.groups.forEach(g=>{
    md += '**' + g.title + '**\n\n';
    g.sections.forEach(sid=>{ const s = lib.sections[sid]; if (s) md += '- ' + s.title + '\n'; });
    md += '\n';
  });
  /* 图示索引 */
  const hasFigs = Object.keys(FMAP).some(sid=>lib.sections[sid] && FMAP[sid].length);
  if (hasFigs){
    md += '**课程图示索引**\n\n';
    (atlasGroups||[]).forEach(g=>{
      const inLib = g.figs.filter(f=>FE.figs[f] && FE.figs[f].kind===kind);
      if(!inLib.length) return;
      md += '> ' + g.title + '：' + inLib.map(f=>'图 ' + FIG_NO[f] + ' ' + FE.figs[f].t).join('；') + '\n>\n';
    });
    md += '\n';
  }
  md += '\n---\n\n';
  lib.groups.forEach(g=>{
    md += '# ' + g.title + '\n\n';
    g.sections.forEach(sid=>{
      const s = lib.sections[sid]; if (!s) return;
      md += '## ' + s.title + '\n\n';
      if (s.tags && s.tags.length) md += '`' + s.tags.join('` `') + '`\n\n';
      md += injectFigMd(sid, toMd(s.html)) + '\n\n---\n\n';
    });
  });
  fs.writeFileSync(path.join(outDir, filename), md, 'utf8');
  return md.length;
}

/* ================= 导出（库清单自动探测） ================= */
const CFG = KBC.localConfig(dir);
const KINDS = Object.assign({}, CFG.mdKinds || {});    /* root -> 图示 kind，缺省按 root 推导 */
const FILES = Object.assign({}, CFG.mdFiles || {});    /* root -> 输出文件名，缺省用库 title */
const kindOf = l => KINDS[l.root] || l.root.replace(/_DATA$/, '').toLowerCase();
const mdName = l => FILES[l.root] || (l.raw.title || l.name) + '.md';
const atlasGroups = (window.FIG_ATLAS || { groups: [] }).groups;

const stats = [];
LIBS.forEach(l => {
  if (l.atlas) return;                                  /* 图册不导 Markdown（它的产物是 SVG + 图示册.html） */
  const view = { sections: l.sections, groups: l.groups };
  const n = dump(view, mdName(l), l.raw.title || l.name, l.raw.desc, l.raw.footnote, atlasGroups, kindOf(l));

  /* ---- 分节导出 ---- */
  const sub = path.join(outDir, l.name + '分节');
  if (!fs.existsSync(sub)) fs.mkdirSync(sub);
  let i = 0;
  const written = new Set();
  (l.groups || []).forEach(g => {
    (g.sections || []).forEach(sid => {
      const s = l.sections[sid]; if (!s) return;
      i++;
      const fn = String(i).padStart(2, '0') + '_' + sanitize(s.title) + '.md';
      const body = '# ' + s.title + '\n\n' + (s.tags && s.tags.length ? '`' + s.tags.join('` `') + '`\n\n' : '') + injectFigMd(sid, toMd(s.html)) + '\n';
      fs.writeFileSync(path.join(sub, fn), body, 'utf8');
      written.add(fn);
    });
  });
  /* 清理改名/改序残留：只删「数字_标题.md」形态且不在本轮清单里的文件，不碰其它文件 */
  let purged = 0;
  fs.readdirSync(sub).filter(f => /^\d+_.*\.md$/.test(f) && !written.has(f)).forEach(f => {
    try { fs.unlinkSync(path.join(sub, f)); purged++; } catch (e) {}
  });
  console.log(l.name + '分节: ' + i + ' 个文件' + (purged ? '（清理改名残留 ' + purged + ' 个）' : ''));
  stats.push([l.name, n]);
});
stats.forEach(function (r) { console.log(r[0] + ' Markdown: ' + r[1] + ' 字符'); });
