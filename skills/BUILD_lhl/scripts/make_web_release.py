# -*- coding: utf-8 -*-
"""
make_web_release.py — 生成纯静态「措施库」网站发布包（可直接上传花生壳/任意静态托管）

产出目录：<out>/网站发布/
  index.html        单页应用（内联 CSS/JS，无外部依赖）
  data.js           全量措施数据（window.LEAN_DATA，双击 index.html 也能看，不受 file:// 限制）
  img/              仅被引用的图片
  发布说明.txt

约束校验：文件数 ≤ 2000、单包 ≤ 100MB，超限自动压缩图片（最长边 1280，质量逐级 80→50）。

用法：
    python make_web_release.py --data <工具端>/data --out <板块根>/成果发布 --name 精益建造措施库
"""
import argparse
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = ''
SRC_JSON = ''
SRC_IMG = ''
OUT_ROOT = ''
OUT = ''
SITE_NAME = '精益建造措施库'

MAX_FILES = 1900          # 留出余量（花生壳上限 2000）
MAX_BYTES = 96 * 1024 * 1024   # 留出余量（上限 100MB）


def load():
    with open(SRC_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def shrink(src, dst, max_w=1280, quality=80):
    """按最长边缩放到 max_w 并重编码，体积过大时逐级降质"""
    im = Image.open(src)
    if im.mode not in ('RGB', 'L'):
        im = im.convert('RGB')
    w, h = im.size
    if w > max_w:
        im = im.resize((max_w, int(h * max_w / w)), Image.LANCZOS)
    for q in (quality, 70, 60, 50):
        im.save(dst, 'JPEG', quality=q, optimize=True, progressive=True)
        if os.path.getsize(dst) <= 120 * 1024:
            break


def build(site_name=None):
    site_name = site_name or SITE_NAME
    measures = load()
    # 章节顺序
    order = ['设计优化', '工艺优化', '措施优化', '先进技术应用',
             '安全文明施工管理', '绿色施工管理', '智慧工地管理', '智能工具设备']
    measures.sort(key=lambda r: (order.index(r['章节']) if r['章节'] in order else 99, r['id']))

    if os.path.isdir(OUT):
        # 只允许清空 <out>/网站发布，防误删
        if os.path.basename(OUT.rstrip('\\/')) != '网站发布':
            sys.exit(f'拒绝删除非网站目录：{OUT}')
        shutil.rmtree(OUT)
    img_out = os.path.join(OUT, 'img')
    os.makedirs(img_out)

    # ---- 图片：只复制被引用的，必要时压缩 ----
    used, missing = set(), []
    for m in measures:
        for n in m.get('图片') or []:
            if os.path.isfile(os.path.join(SRC_IMG, n)):
                used.add(n)
            else:
                missing.append((m['id'], n))
    total = sum(os.path.getsize(os.path.join(SRC_IMG, n)) for n in used)
    need_compress = (len(used) + 6 > MAX_FILES) or (total > MAX_BYTES * 0.8)
    copied = 0
    for n in sorted(used):
        src = os.path.join(SRC_IMG, n)
        dst = os.path.join(img_out, n)
        if need_compress:
            shrink(src, dst)
        else:
            shutil.copy2(src, dst)
        copied += 1

    # ---- 数据 ----
    items = []
    for m in measures:
        items.append({
            'i': m['id'],
            'n': m['优化措施名称'],
            'c': m['章节'],
            't': m['优化类型'],
            'd': m['分部工程'],
            's': m['子分部工程'],
            'p': m['分项工程'],
            'a': m.get('适用部位') or '',
            'x': m.get('优化内容') or '',
            'y': m.get('优化效果') or '',
            'k': [k for k in (m.get('信息词条') or '').split(';') if k],
            'g': m.get('图片') or [],
            'src': (m.get('来源表') or '') + ('·P' + str(m.get('来源页')) if m.get('来源页') else ''),
        })

    chapters = []
    for ch in order:
        c = sum(1 for x in items if x['c'] == ch)
        if c:
            chapters.append({'name': ch, 'count': c})
    stats = {
        'total': len(items),
        'chapters': len(chapters),
        'images': sum(len(x['g']) for x in items),
        'divisions': len({x['d'] for x in items}),
        'build': datetime.now().strftime('%Y-%m-%d'),
    }
    payload = {'meta': {'name': site_name, 'stats': stats, 'chapters': chapters}, 'items': items}
    with open(os.path.join(OUT, 'data.js'), 'w', encoding='utf-8') as f:
        f.write('window.LEAN_DATA=')
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
        f.write(';\n')

    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(HTML.replace('__SITE_NAME__', site_name))

    # ---- 发布说明 ----
    with open(os.path.join(OUT, '发布说明.txt'), 'w', encoding='utf-8') as f:
        f.write(SITE_README.format(total=stats['total'], images=stats['images'],
                                   divisions=stats['divisions'], build=stats['build']))
    return stats, missing, need_compress


def package():
    zip_path = os.path.join(OUT_ROOT, f'{SITE_NAME}_网站发布.zip')
    if os.path.exists(zip_path):
        os.remove(zip_path)
    n = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(OUT):
            for fn in files:
                p = os.path.join(root, fn)
                z.write(p, os.path.relpath(p, OUT))
                n += 1
    return zip_path, n


def report():
    files = 0
    size = 0
    for root, dirs, fs in os.walk(OUT):
        for fn in fs:
            p = os.path.join(root, fn)
            files += 1
            size += os.path.getsize(p)
    return files, size


HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__SITE_NAME__</title>
<style>
*{box-sizing:border-box}
:root{--blue:#2F5597;--blue-d:#24406f;--blue-l:#eaf0fa;--ink:#1c2430;--gray:#6b7787;--line:#e3e8f0;--bg:#f4f6fb}
html,body{margin:0;padding:0}
body{font-family:"Microsoft YaHei","微软雅黑",-apple-system,"Helvetica Neue",Arial,sans-serif;background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
header{background:linear-gradient(120deg,#2F5597 0%,#3a6bbd 55%,#4a7fd0 100%);color:#fff;padding:26px 24px 22px}
.hd{max-width:1320px;margin:0 auto;display:flex;flex-wrap:wrap;align-items:flex-end;gap:18px}
h1{margin:0;font-size:23px;letter-spacing:.5px;font-weight:700}
h1 span{display:block;font-size:12.5px;font-weight:400;opacity:.85;margin-top:6px;letter-spacing:1px}
.kpis{margin-left:auto;display:flex;gap:26px;flex-wrap:wrap}
.kpi b{display:block;font-size:24px;line-height:1.1;font-weight:700}
.kpi i{font-style:normal;font-size:11.5px;opacity:.8;letter-spacing:.5px}
.bar{background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:30;box-shadow:0 2px 10px rgba(28,36,48,.06)}
.bar-in{max-width:1320px;margin:0 auto;padding:12px 24px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.search{flex:1;min-width:220px;position:relative}
.search input{width:100%;padding:10px 14px 10px 36px;border:1px solid var(--line);border-radius:8px;font-size:13.5px;background:#fbfcfe;outline:none;font-family:inherit}
.search input:focus{border-color:var(--blue);background:#fff;box-shadow:0 0 0 3px rgba(47,85,151,.1)}
.search svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);opacity:.45}
select{padding:9px 30px 9px 12px;border:1px solid var(--line);border-radius:8px;background:#fbfcfe;font-size:13px;font-family:inherit;color:var(--ink);outline:none;cursor:pointer;max-width:200px}
select:focus{border-color:var(--blue)}
.chips{max-width:1320px;margin:0 auto;padding:0 24px 12px;display:flex;gap:8px;flex-wrap:wrap}
.chip{padding:6px 13px;border:1px solid var(--line);border-radius:99px;background:#fff;font-size:12.5px;cursor:pointer;color:#4a5568;transition:.15s;white-space:nowrap}
.chip:hover{border-color:#b9c8de;color:var(--blue)}
.chip.on{background:var(--blue);border-color:var(--blue);color:#fff;box-shadow:0 2px 8px rgba(47,85,151,.25)}
.chip b{font-weight:500;opacity:.75;margin-left:3px;font-size:11.5px}
main{max-width:1320px;margin:0 auto;padding:18px 24px 60px}
.meta{display:flex;align-items:center;gap:14px;margin-bottom:14px;font-size:12.5px;color:var(--gray);flex-wrap:wrap}
.meta b{color:var(--blue);font-size:14px}
.btn{padding:6px 13px;border:1px solid var(--line);background:#fff;border-radius:6px;font-size:12.5px;cursor:pointer;color:#44506b;font-family:inherit}
.btn:hover{border-color:var(--blue);color:var(--blue)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(316px,1fr));gap:16px}
.card{background:#fff;border-radius:10px;overflow:hidden;border:1px solid #eaeef5;box-shadow:0 1px 3px rgba(28,36,48,.05);cursor:pointer;transition:.18s;display:flex;flex-direction:column}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(47,85,151,.14);border-color:#c8d7ee}
.thumb{position:relative;background:#eef2f8;aspect-ratio:16/9;overflow:hidden}
.thumb img{width:100%;height:100%;object-fit:cover;display:block;transition:.4s}
.card:hover .thumb img{transform:scale(1.04)}
.thumb .no{position:absolute;left:8px;top:8px;background:rgba(28,36,48,.62);color:#fff;font-size:11px;padding:2px 7px;border-radius:4px;letter-spacing:.5px}
.thumb .cnt{position:absolute;right:8px;bottom:8px;background:rgba(47,85,151,.86);color:#fff;font-size:11px;padding:2px 7px;border-radius:4px}
.body{padding:13px 15px 15px;display:flex;flex-direction:column;flex:1}
.tagrow{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}
.tag{font-size:11px;padding:2px 7px;border-radius:4px;background:var(--blue-l);color:var(--blue);white-space:nowrap}
.tag.gray{background:#f2f4f8;color:#6b7787}
.card h3{margin:0 0 8px;font-size:14.5px;line-height:1.45;font-weight:700;color:#16202e;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.lbl{font-size:10.5px;color:#9aa5b5;letter-spacing:1px;margin-bottom:2px}
.txt{font-size:12.5px;line-height:1.72;color:#4d5866;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:8px}
.eff{font-size:12.5px;line-height:1.7;color:#2c4a78;background:#f6f9fe;border-left:3px solid #9db8e0;padding:6px 9px;border-radius:0 4px 4px 0;margin-top:auto;overflow:hidden}
.effin{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;word-break:break-word}
.more{text-align:center;margin:26px 0 0}
.more button{padding:11px 40px;border:1px solid var(--line);background:#fff;border-radius:8px;cursor:pointer;font-size:13.5px;color:var(--blue);font-family:inherit;box-shadow:0 1px 3px rgba(28,36,48,.06)}
.more button:hover{background:var(--blue);color:#fff;border-color:var(--blue)}
.empty{text-align:center;padding:70px 20px;color:#98a3b3;font-size:14px}
/* 弹窗 */
.mask{position:fixed;inset:0;background:rgba(16,22,32,.55);backdrop-filter:blur(2px);display:none;z-index:100;padding:28px;overflow:auto}
.mask.on{display:block}
.dlg{max-width:1080px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.3)}
.dlg-hd{display:flex;align-items:flex-start;gap:12px;padding:18px 22px;border-bottom:1px solid var(--line);background:#fbfcff}
.dlg-hd h2{margin:0;font-size:17px;line-height:1.5;flex:1}
.close{width:30px;height:30px;border:none;background:#eef2f8;border-radius:6px;cursor:pointer;font-size:17px;color:#6b7787;line-height:1;flex:none}
.close:hover{background:#dfe6f2;color:#2F5597}
.dlg-bd{display:grid;grid-template-columns:1.05fr 1fr;gap:0}
.dlg-img{background:#f2f5fa;padding:16px;display:flex;flex-direction:column;gap:10px;align-items:center;justify-content:center}
.dlg-img img{width:100%;border-radius:6px;display:block;box-shadow:0 2px 10px rgba(0,0,0,.09)}
.dlg-img .thumbs{display:flex;gap:8px;flex-wrap:wrap}
.dlg-img .thumbs img{width:64px;height:48px;object-fit:cover;cursor:pointer;border:2px solid transparent;border-radius:4px;box-shadow:none;opacity:.8}
.dlg-img .thumbs img.on{border-color:var(--blue);opacity:1}
.dlg-tx{padding:18px 22px 24px;max-height:70vh;overflow:auto}
.sec{margin-bottom:16px}
.sec .lbl{margin-bottom:5px;color:#8b96a8;font-size:11px;letter-spacing:1.2px}
.sec p{margin:0;font-size:13.5px;line-height:1.95;color:#333d4c;text-align:justify}
.sec p.eff{background:#f6f9fe;border-left:3px solid var(--blue);padding:9px 12px;border-radius:0 5px 5px 0;color:#22406b;display:block;-webkit-line-clamp:unset;overflow:visible}
.wc{display:flex;flex-wrap:wrap;gap:6px}
.wc span{font-size:11.5px;background:#f2f5fa;border:1px solid #e6ecf5;color:#5a6a80;padding:3px 9px;border-radius:99px}
.foot{max-width:1320px;margin:0 auto;padding:20px 24px 34px;text-align:center;color:#9aa5b5;font-size:11.5px;line-height:1.9}
@media(max-width:760px){
  header{padding:20px 16px 18px}h1{font-size:19px}
  .kpis{margin-left:0;gap:20px}.kpi b{font-size:19px}
  .bar-in{flex-direction:column;align-items:stretch;gap:9px}
  .bar-in,.chips,main,.foot{padding-left:14px;padding-right:14px}
  .search{min-width:0}.search input{font-size:14px}
  select{width:100%;max-width:100%;flex:none}
  .grid{grid-template-columns:1fr;gap:13px}
  .dlg-bd{grid-template-columns:1fr}
  .mask{padding:0}.dlg{border-radius:0;min-height:100%}
  .dlg-tx{max-height:none}
  .meta{gap:9px}
}
</style>
</head>
<body>
<header>
  <div class="hd">
    <h1>__SITE_NAME__<span>精益建造 · 设计优化 / 工艺优化 / 措施优化 措施集成</span></h1>
    <div class="kpis" id="kpis"></div>
  </div>
</header>

<div class="bar">
  <div class="bar-in">
    <div class="search">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#2F5597" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <input id="q" type="search" placeholder="搜索措施名称 / 优化内容 / 信息词条…">
    </div>
    <select id="fdiv"><option value="">全部分部工程</option></select>
    <select id="ftype"><option value="">全部优化类型</option></select>
  </div>
  <div class="chips" id="chips"></div>
</div>

<main>
  <div class="meta">
    <span>共 <b id="cnt">0</b> 条措施</span>
    <span id="filt"></span>
    <button class="btn" id="reset" style="margin-left:auto">清空筛选</button>
    <button class="btn" id="csv">导出当前结果 CSV</button>
  </div>
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty" style="display:none">没有匹配的措施，换个关键词试试</div>
  <div class="more" id="more" style="display:none"><button id="morebtn">加载更多</button></div>
</main>

<div class="foot">
  <div id="footline"></div>
  数据来源：精益建造措施库（内部资料，仅供项目参考）
</div>

<div class="mask" id="mask">
  <div class="dlg">
    <div class="dlg-hd"><h2 id="dtitle"></h2><button class="close" id="dclose">×</button></div>
    <div class="dlg-bd">
      <div class="dlg-img"><img id="dimg" alt=""><div class="thumbs" id="dthumbs"></div></div>
      <div class="dlg-tx" id="dtx"></div>
    </div>
  </div>
</div>

<script src="data.js"></script>
<script>
(function(){
  var D = window.LEAN_DATA, ITEMS = D.items, META = D.meta;
  var PAGE = 36, shown = 0, list = [];

  // KPI
  document.getElementById('kpis').innerHTML =
    '<div class="kpi"><b>'+META.stats.total+'</b><i>优化措施</i></div>'+
    '<div class="kpi"><b>'+META.stats.images+'</b><i>实体案例图片</i></div>'+
    '<div class="kpi"><b>'+META.stats.divisions+'</b><i>分部工程</i></div>'+
    '<div class="kpi"><b>'+META.stats.chapters+'</b><i>板块分类</i></div>';
  document.getElementById('footline').textContent = '更新时间：'+META.stats.build+'　·　共 '+META.stats.total+' 项措施 / '+META.stats.images+' 张图片';

  // 章节 chips
  var chips = document.getElementById('chips');
  var cAll = document.createElement('div');
  cAll.className = 'chip on'; cAll.dataset.ch = '';
  cAll.innerHTML = '全部<b>'+META.stats.total+'</b>';
  chips.appendChild(cAll);
  META.chapters.forEach(function(c){
    var d = document.createElement('div');
    d.className = 'chip'; d.dataset.ch = c.name;
    d.innerHTML = c.name + '<b>'+c.count+'</b>';
    chips.appendChild(d);
  });
  chips.addEventListener('click', function(e){
    var t = e.target.closest('.chip'); if(!t) return;
    chips.querySelectorAll('.chip').forEach(function(x){x.classList.remove('on')});
    t.classList.add('on'); render();
  });

  // 下拉
  var divs = {}, types = {};
  ITEMS.forEach(function(i){ divs[i.d]=(divs[i.d]||0)+1; types[i.t]=(types[i.t]||0)+1; });
  var sd = document.getElementById('fdiv');
  Object.keys(divs).sort(function(a,b){return divs[b]-divs[a]}).forEach(function(k){
    var o=document.createElement('option'); o.value=k; o.textContent=k+'（'+divs[k]+'）'; sd.appendChild(o);
  });
  var st = document.getElementById('ftype');
  Object.keys(types).sort(function(a,b){return types[b]-types[a]}).forEach(function(k){
    var o=document.createElement('option'); o.value=k; o.textContent=k+'（'+types[k]+'）'; st.appendChild(o);
  });
  sd.onchange = st.onchange = function(){ render(); };

  var q = document.getElementById('q'), timer=null;
  q.addEventListener('input', function(){ clearTimeout(timer); timer=setTimeout(render,160); });
  document.getElementById('reset').onclick = function(){
    q.value=''; sd.value=''; st.value='';
    chips.querySelectorAll('.chip').forEach(function(x){x.classList.remove('on')});
    cAll.classList.add('on'); render();
  };

  function curChapter(){ var on = chips.querySelector('.chip.on'); return on ? on.dataset.ch : ''; }

  function match(i, ch, kw){
    if(ch && i.c !== ch) return false;
    if(sd.value && i.d !== sd.value) return false;
    if(st.value && i.t !== st.value) return false;
    if(!kw) return true;
    var hay = i.n+' '+i.x+' '+i.y+' '+i.k.join(' ')+' '+i.d+' '+i.p+' '+i.a+' '+i.t;
    return kw.split(/\s+/).every(function(w){ return hay.indexOf(w) >= 0; });
  }

  function render(){
    var ch = curChapter(), kw = q.value.trim().toLowerCase();
    list = ITEMS.filter(function(i){ return match(i, ch, kw); });
    document.getElementById('cnt').textContent = list.length;
    var fs = [];
    if(ch) fs.push('板块：'+ch);
    if(sd.value) fs.push('分部：'+sd.value);
    if(st.value) fs.push('类型：'+st.value);
    if(kw) fs.push('关键词："'+q.value.trim()+'"');
    document.getElementById('filt').textContent = fs.length ? '｜ 筛选：'+fs.join('　') : '';
    document.getElementById('grid').innerHTML = '';
    document.getElementById('empty').style.display = list.length ? 'none' : 'block';
    shown = 0; addMore(true);
  }

  function card(i){
    var el = document.createElement('div');
    el.className = 'card';
    var img = i.g.length ? 'img/'+encodeURIComponent(i.g[0]) : '';
    el.innerHTML =
      '<div class="thumb">'+(img?'<img loading="lazy" src="'+img+'" alt="">':'')+
        '<span class="no">'+i.i+'</span>'+
        (i.g.length>1?'<span class="cnt">'+i.g.length+' 图</span>':'')+'</div>'+
      '<div class="body">'+
        '<div class="tagrow"><span class="tag">'+i.c+'</span><span class="tag gray">'+i.d+'</span></div>'+
        '<h3>'+esc(i.n)+'</h3>'+
        '<div class="lbl">优化内容</div><div class="txt">'+esc(i.x)+'</div>'+
        '<div class="lbl">优化效果</div><div class="eff"><div class="effin">'+esc(i.y)+'</div></div>'+
      '</div>';
    el.onclick = function(){ open(i); };
    return el;
  }

  function addMore(first){
    var g = document.getElementById('grid');
    var end = Math.min(shown + PAGE, list.length);
    for(var k=shown;k<end;k++) g.appendChild(card(list[k]));
    shown = end;
    document.getElementById('more').style.display = shown < list.length ? 'block' : 'none';
    document.getElementById('morebtn').textContent = '加载更多（还有 '+(list.length-shown)+' 条）';
  }
  document.getElementById('morebtn').onclick = function(){ addMore(false); };

  function esc(s){ return String(s||'').replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

  // 弹窗
  var mask = document.getElementById('mask');
  function open(i){
    document.getElementById('dtitle').textContent = i.n;
    document.getElementById('dimg').src = i.g.length ? 'img/'+encodeURIComponent(i.g[0]) : '';
    var th = document.getElementById('dthumbs'); th.innerHTML='';
    if(i.g.length > 1){
      i.g.forEach(function(n, idx){
        var im = document.createElement('img');
        im.src = 'img/'+encodeURIComponent(n);
        if(idx===0) im.className='on';
        im.onclick = function(){
          document.getElementById('dimg').src = im.src;
          th.querySelectorAll('img').forEach(function(x){x.classList.remove('on')});
          im.classList.add('on');
        };
        th.appendChild(im);
      });
    }
    document.getElementById('dtx').innerHTML =
      '<div class="sec"><div class="tagrow"><span class="tag">'+i.c+'</span>'+
        '<span class="tag gray">'+i.t+'</span><span class="tag gray">'+i.d+' / '+i.s+' / '+i.p+'</span></div></div>'+
      (i.a?'<div class="sec"><div class="lbl">适用部位</div><p>'+esc(i.a)+'</p></div>':'')+
      '<div class="sec"><div class="lbl">优化内容</div><p>'+esc(i.x)+'</p></div>'+
      '<div class="sec"><div class="lbl">优化效果</div><p class="eff">'+esc(i.y)+'</p></div>'+
      (i.k.length?'<div class="sec"><div class="lbl">信息词条</div><div class="wc">'+i.k.map(function(k){return '<span>'+esc(k)+'</span>'}).join('')+'</div></div>':'')+
      (i.src?'<div class="sec"><div class="lbl">来源</div><p style="font-size:12px;color:#8b96a8">'+esc(i.src)+'</p></div>':'');
    mask.classList.add('on');
    document.body.style.overflow='hidden';
  }
  function close(){ mask.classList.remove('on'); document.body.style.overflow=''; }
  document.getElementById('dclose').onclick = close;
  mask.onclick = function(e){ if(e.target===mask) close(); };
  document.addEventListener('keydown', function(e){ if(e.key==='Escape') close(); });

  // 导出 CSV
  document.getElementById('csv').onclick = function(){
    var head = ['编号','优化措施名称','章节','优化类型','分部工程','子分部工程','分项工程','适用部位','优化内容','优化效果','信息词条','实体案例'];
    var rows = [head].concat(list.map(function(i){
      return [i.i,i.n,i.c,i.t,i.d,i.s,i.p,i.a,i.x,i.y,i.k.join(';'),i.g.join(';')];
    }));
    var csv = rows.map(function(r){
      return r.map(function(c){ return '"'+String(c==null?'':c).replace(/"/g,'""')+'"'; }).join(',');
    }).join('\r\n');
    var blob = new Blob(['\ufeff'+csv], {type:'text/csv;charset=utf-8'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '__SITE_NAME___'+new Date().toISOString().slice(0,10)+'.csv';
    a.click();
  };

  render();
})();
</script>
</body>
</html>
'''

SITE_README = '''精益建造措施库 · 网站发布包
=================================
生成时间：{build}
内容：{total} 项优化措施、{images} 张实体案例图片，覆盖 {divisions} 个分部工程。

目录结构
  index.html      入口页面（双击即可本地浏览，无需服务器）
  data.js         全量措施数据
  img/            实体案例图片
  发布说明.txt    本文件

一、在花生壳发布为网址
  1）花生壳「网站建设 / 虚拟主机」上传：把本目录内全部文件（或整包 zip）上传到站点根目录，
     入口文件设为 index.html 即可。包内文件数与体积已控制在 2000 个 / 100MB 以内。
  2）花生壳「内网穿透」映射本地服务：本目录为纯静态网站，可用任意静态服务器托管，
     例如在目录内执行  python -m http.server 8080  ，然后把 8080 端口映射出去。

二、功能
  · 按板块（设计优化/工艺优化/措施优化…）筛选、按分部工程与优化类型过滤
  · 关键词搜索：措施名称、优化内容、优化效果、信息词条
  · 卡片点击查看图文详情（多图可切换）
  · 一键导出当前筛选结果为 CSV（Excel 可直接打开）

三、说明
  · 本页面为只读浏览版，PDF / PPT 成果生成请使用「精益建造一体化工具.exe」。
  · 修改措施库后，重新运行 make_web_release.py 即可更新本发布包。
'''


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help='工具端 data 目录（含 lean_measures.json 与 图片库）')
    ap.add_argument('--out', required=True, help='成果输出目录，网站落在 <out>/网站发布')
    ap.add_argument('--name', default='精益建造措施库', help='站点名（标题与压缩包名）')
    a = ap.parse_args()

    DATA = os.path.abspath(a.data)
    SRC_JSON = os.path.join(DATA, 'lean_measures.json')
    SRC_IMG = os.path.join(DATA, '图片库')
    OUT_ROOT = os.path.abspath(a.out)
    OUT = os.path.join(OUT_ROOT, '网站发布')
    SITE_NAME = a.name
    if not os.path.isfile(SRC_JSON):
        sys.exit(f'找不到 {SRC_JSON}')

    st, missing, comp = build()
    files, size = report()
    print(f'措施 {st["total"]} 条 / 图片 {st["images"]} 张 / 分部 {st["divisions"]}')
    print(f'文件数 {files}（上限 {MAX_FILES}）  体积 {size/1024/1024:.1f} MB（上限 100MB）')
    print('图片压缩：' + ('已压缩' if comp else '无需压缩'))
    if missing:
        print('缺失图片：', missing[:5])
    z, n = package()
    print(f'压缩包：{z}  {os.path.getsize(z)/1024/1024:.1f} MB / {n} 个文件')
