/* ============================================================
   build-bundle.js —— 把 index.html 里的散装 <script src> 合成 bundle/
   ------------------------------------------------------------
   用途：知识库项目动辄上百个 <script src>（每库的内容分片 + 词表 + 图示分片）。
   散装标签会让 index.html 难以阅读、也让「改完忘重跑」无从察觉。
   本脚本按 index.html 里脚本标签的**原始顺序**分组拼接：不改任何一个字符，
   因此全局变量的定义顺序与逐标签加载时完全一致，渲染结果逐字节等价。

   纪律：data-*.js / figs*.js / syn-*.js 是**唯一数据源**，bundle/ 是**生成物**。
         任何时候改动了源文件，都要再跑一次本脚本，否则页面会停在旧 bundle 上。

   用法（在项目根目录执行即可，脚本自行定位 index.html）：
       node build-bundle.js          # 生成/重建 bundle 并回填 index.html
       node build-bundle.js --self-test   # 只跑自测：在临时目录造迷你项目验证分组/幂等/等价性/报错能力

   分组规则（由架构决定，见 SKILL.md「架构：内容与引擎分离」）：
       syn-core.js                    → bundle/engine.js        （引擎，领域无关）
       syn-data.js                    → bundle/word-main.js     （主词表）
       syn-data-<域>.js               → bundle/word-<域>.js     （第二域词表，如 syn-data-shebao.js）
       figs*.js                       → bundle/figs.js          （所有图示分片合成一张）
       data-<域>.js / data-<域>N.js   → bundle/data-<域>.js     （去掉末位数字，同库合成一个）
   归不了类的脚本（如 index.html 自己的引擎脚本）直接报错退出，不做猜测。

   幂等：脚本从 index.html 现存标签（可能是上一轮的 bundle 标签）反解回源文件清单再重建，
        所以重复跑不会把 bundle 标签当成源文件、也不会越滚越多。

   ★ 命名漂移自愈：一旦改了 bucketOf 的命名规则，index.html 里那些旧名字就成了死链——
     页面照常打开，但引擎 / 词表 404 加载不到，全站检索静默失效，而三个校验脚本一个都
     不会报（它们读源文件，不看 index.html 指向哪）。所以回填阶段会从旧 bundle 头部的
     「合成自」清单反推出它的正确名，不一致就自动改正；标签指向本轮没生成的 bundle 时
     直接报错退出，绝不静默留死链（自测 ⑦ 守这条）。

   收尾自带**等价性自检**：逐个源文件求值 vs 逐个 bundle 求值，比对全部全局对象的值
   （函数比 arity）。注意它只覆盖 window.X = ... 这类全局赋值——引擎自身（IIFE 内部逻辑）
   的变化是靠「打包前后 DOM 抠掉 script 标签 + 去空行后逐字符比对」兜底的，两者缺一不可。
   ============================================================ */
'use strict';
const fs = require('fs');
const path = require('path');
const os = require('os');

/* ------------------ 分组规则：按架构推断，不写死库名 ------------------ */
function bucketOf(f) {
  const n = String(f).replace(/\.js$/, '');
  if (/^figs/.test(n)) return 'figs.js';                     // figs / figs24 / figs25 / figs-map（图示分片 + 映射表进同一组）
  const m0 = n.match(/^syn-core$/);
  if (m0) return 'engine.js';
  if (/^syn-data$/.test(n)) return 'word-main.js';
  const m1 = n.match(/^syn-data-(.+)$/);
  if (m1) return 'word-' + m1[1] + '.js';
  const m2 = n.match(/^data-(.+?)(\d*)$/);
  if (m2 && m2[1]) return 'data-' + m2[1] + '.js';
  return null;
}

/* ------------------ 主流程 ------------------ */
function run(dir) {
  dir = dir || process.cwd();
  const BUNDLE = path.join(dir, 'bundle');
  const TAG_RE = /<script\s+src="([^"]+)"\s*><\/script>/g;

  const html = fs.readFileSync(path.join(dir, 'index.html'), 'utf8');
  const tags = [];
  let m;
  TAG_RE.lastIndex = 0;
  while ((m = TAG_RE.exec(html))) tags.push(m[1]);
  if (!tags.length) { console.error('✗ index.html 里没读到任何 <script src>，中止'); return 1; }
  console.log('index.html 共 ' + tags.length + ' 个脚本标签');

  /* 1. 展开：bundle/ 标签反解回源文件清单
        同时顺手算出「这个旧标签现在的正确名字」，记进 tagFix —— 命名漂移自愈。
        必须在第 3 步删旧产物之前做，否则旧 bundle 文件已不在，反解无从下手。 */
  const tagFix = {};
  function expand(f) {
    if (f.indexOf('bundle/') !== 0) return [f];
    const p = path.join(dir, f);
    if (!fs.existsSync(p)) {
      console.error('✗ 找不到 ' + f + '（index.html 引用了不存在的 bundle）');
      console.error('  两种可能：① 还没跑过本脚本生成 bundle；② build-bundle.js 改过命名规则，' +
        'index.html 还停在旧名上，而旧产物已被删。后者请把该标签直接改成本轮产物名。');
      return null;
    }
    const s = fs.readFileSync(p, 'utf8');
    const mm = s.match(/合成自：([^\n]+)\n/);
    if (!mm) { console.error('✗ ' + f + ' 头部缺少「合成自」清单，无法反解'); return null; }
    const list = mm[1].split('、').map(x => x.trim()).filter(Boolean);
    const names = list.map(x => bucketOf(x));
    if (!names[0] || names.some(x => x !== names[0])) {
      console.error('✗ ' + f + ' 的源文件不属于同一组（' + list.join('、') + '），无法判定其正确名'); return null;
    }
    const correct = 'bundle/' + names[0];
    if (correct !== f) { tagFix[f] = correct; console.log('  · 发现 bundle 命名漂移：' + f + ' → ' + correct + '（将自动改正 index.html）'); }
    return list;
  }
  const srcs = [];
  for (const f of tags) {
    const r = expand(f);
    if (r === null) return 1;
    r.forEach(x => srcs.push(x));
  }
  const dup = srcs.filter((x, i) => srcs.indexOf(x) !== i);
  if (dup.length) { console.error('✗ 脚本清单出现重复：' + dup.join(', ')); return 1; }
  console.log('反解出 ' + srcs.length + ' 个源文件');

  /* 2. 分组 */
  const groups = {};
  const unknown = [];
  srcs.forEach(f => {
    const b = bucketOf(f);
    if (!b) { unknown.push(f); return; }
    (groups[b] = groups[b] || []).push(f);
  });
  if (unknown.length) { console.error('✗ 未归类的脚本（请在 build-bundle.js 的 bucketOf 里补规则）：' + unknown.join(', ')); return 1; }

  /* 3. 写 bundle */
  fs.rmSync(BUNDLE, { recursive: true, force: true });
  fs.mkdirSync(BUNDLE, { recursive: true });
  const manifest = [];
  Object.keys(groups).forEach(b => {
    const files = groups[b];
    const parts = files.map(f => fs.readFileSync(path.join(dir, f), 'utf8').replace(/\s+$/, '') + '\n');
    const head =
      '/* ============================================================\n' +
      '   本文件由 build-bundle.js 生成，请勿手改\n' +
      '   合成自：' + files.join('、') + '\n' +
      '   源文件（data-*.js / figs*.js / syn-*.js）是唯一数据源，改完请重跑 node build-bundle.js\n' +
      '   ============================================================ */\n';
    fs.writeFileSync(path.join(BUNDLE, b), head + parts.join('\n'), 'utf8');
    manifest.push({ bundle: b, files: files.length, kb: +(fs.statSync(path.join(BUNDLE, b)).size / 1024).toFixed(1) });
  });
  manifest.forEach(x => console.log('  · bundle/' + x.bundle.padEnd(20) + x.files + ' 个源文件 → ' + x.kb + ' KB'));

  /* 4. 回填 index.html（幂等：连续的同名 bundle 标签折叠成一个）
        三种输入都要认：① 散装源名（首轮）→ 折叠成 bundle 名；
        ② 已是 bundle 名（常态）→ 原样保留；③ 漂移的旧 bundle 名 → 按 tagFix 改正。
        只要标签指向本轮没有生成的 bundle 名，就直接报错——不许静默留一个死链。 */
  const out = [];
  const okNames = manifest.map(x => x.bundle);
  let cur = null, badName = null;
  for (const line of html.split('\n')) {
    const mm = line.match(/^(\s*)<script\s+src="([^"]+)"\s*><\/script>\s*$/);
    if (mm) {
      const raw = mm[2];
      let b;
      if (raw.indexOf('bundle/') === 0) b = (tagFix[raw] || raw).slice(7);  // 已是 / 改正后的 bundle 名
      else b = bucketOf(raw);                                              // 散装源名 → 折叠
      if (!b) { out.push(line); continue; }                                // index.html 自己的引擎脚本
      if (okNames.indexOf(b) < 0) { badName = b; break; }
      if (cur !== b) { cur = b; out.push(mm[1] + '<script src="bundle/' + b + '"></script>'); }
      continue;
    }
    cur = null;
    out.push(line);
  }
  if (badName) {
    console.error('✗ index.html 引用了本轮未生成的 bundle：bundle/' + badName);
    console.error('  本轮产物：' + okNames.join('、'));
    console.error('  多半是 build-bundle.js 改过命名规则、而 index.html 没跟着改。把 index.html 里那个标签改成本轮产物名即可。');
    return 1;
  }
  const html2 = out.join('\n');
  const after = (html2.match(/<script\s+src="([^"]+)"\s*><\/script>/g) || []).length;
  if (after !== manifest.length) {
    console.error('✗ 回填后 index.html 剩 ' + after + ' 个脚本标签，期望 ' + manifest.length +
      '（index.html 的脚本格式可能不是独占一行的 <script src="x"></script>，请先看 --self-test 通过后再改）');
    return 1;
  }
  if (html2 !== html) { fs.writeFileSync(path.join(dir, 'index.html'), html2, 'utf8'); console.log('index.html 已回填 bundle 标签'); }
  else console.log('index.html 已是 bundle 形态，跳过回填');

  /* 5. 等价性自检：源文件逐个求值 vs bundle 逐个求值 */
  function snapOf(list) {
    const sandbox = {};
    list.forEach(f => {
      const src = fs.readFileSync(path.join(dir, f), 'utf8');
      try { new Function('window', src)(sandbox); }
      catch (e) { throw new Error(f + ' 求值失败：' + e.message); }
    });
    const g = {};
    Object.keys(sandbox).forEach(k => {
      const v = sandbox[k];
      g[k] = typeof v === 'function' ? 'fn(' + v.length + ')' : JSON.stringify(v);
    });
    return g;
  }
  const allSources = Object.keys(groups).map(b => groups[b]).reduce((a, x) => a.concat(x), []);
  let a, b, ka, kb2, diff = 0, labels;
  try {
    a = snapOf(allSources);
    b = snapOf(manifest.map(x => 'bundle/' + x.bundle));
  } catch (e) { console.error('✗ 等价性自检中断：' + e.message); return 1; }
  ka = Object.keys(a).sort(); kb2 = Object.keys(b).sort();
  labels = ka.map(k => k);
  ka.forEach(k => { if (!(k in b)) { console.log('✗ bundle 缺少全局 ' + k); diff++; return; } if (a[k] !== b[k]) { console.log('✗ 全局 ' + k + ' 内容不一致'); diff++; } });
  kb2.forEach(k => { if (!(k in a)) { console.log('✗ bundle 多出全局 ' + k); diff++; } });
  console.log(diff ? '❌ 等价性自检失败：' + diff + ' 处不一致' : '✅ 等价性自检通过：' + labels.length + ' 个全局对象，值与顺序一致');
  return diff ? 1 : 0;
}

/* ------------------ 自测：先证明它能报得出来，再信它的绿灯 ------------------ */
function selfTest() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'bb-selftest-'));
  const W = (p, s) => fs.writeFileSync(path.join(tmp, p), s, 'utf8');
  console.log('自测目录：' + tmp);

  // 造一个迷你知识库：引擎 + 主词表 + 第二域词表 + 2 个图示分片 + 2 库的若干分片
  W('index.html', [
    '<!doctype html><html><head><meta charset="utf-8"></head><body><div id=a></div>',
    '<script src="syn-core.js"></script>',
    '<script src="syn-data.js"></script>',
    '<script src="syn-data-shebao.js"></script>',
    '<script src="figs1.js"></script>',
    '<script src="figs2.js"></script>',
    '<script src="data-topicA7.js"></script>',
    '<script src="data-topicA9.js"></script>',
    '<script src="data-topicB3.js"></script>',
    '<script>/* 引擎脚本，不打包 */</script>',
    '</body></html>'
  ].join('\n'));

  W('syn-core.js', '(function(){window.SYN_ENGINE={v:1,expand:function(){return 1;}};})();\n');
  W('syn-data.js', 'window.SYN_DATA={phrases:["仲裁"],entries:1};\n');
  W('syn-data-shebao.js', 'window.SYN_DATA_SHEBAO={phrases:["社保"],entries:2};\n');
  W('figs1.js', 'window.FIG_DATA_1={figs:{\'f1\':{t:\'一图\'}}};\n');
  W('figs2.js', 'window.FIG_DATA_2={figs:{\'f2\':{t:\'二图\'}}};\n');
  W('data-topicA7.js', 'window.TOPIC_A_DATA_7={sections:{\'a\':{title:\'甲\'}}};\n');
  W('data-topicA9.js', 'window.TOPIC_A_DATA_9={sections:{\'b\':{title:\'乙\'}}};\n');
  W('data-topicB3.js', 'window.TOPIC_B_DATA_3={sections:{\'c\':{title:\'丙\'}}};\n');
  console.log('① 迷你项目已就位（8 个脚本标签，其中 1 个是引擎脚本）');

  // 跑第一轮
  const code1 = run(tmp);
  const got = fs.readdirSync(path.join(tmp, 'bundle')).sort();
  const want = ['data-topicA.js', 'data-topicB.js', 'engine.js', 'figs.js', 'word-main.js', 'word-shebao.js'];
  const okGroup = want.every(x => got.indexOf(x) >= 0) && got.length === want.length;
  console.log(okGroup ? '✅ ② 分组正确：' + got.join(' ') : '❌ ② 分组错误：' + got.join(' '));

  const afterTags = (fs.readFileSync(path.join(tmp, 'index.html'), 'utf8')
    .match(/<script\s+src="[^"]+"\s*><\/script>/g) || []).length;
  console.log(afterTags === 6 ? '✅ ③ 回填后 index.html 收敛到 6 个 bundle 标签（引擎脚本原样保留）'
    : '❌ ③ 回填后标签数 = ' + afterTags + '，应为 6');

  // 幂等：再跑一次，bundle 文件与 index.html 都不该变
  const before = fs.readdirSync(path.join(tmp, 'bundle')).sort().join(',') +
    fs.statSync(path.join(tmp, 'bundle', 'data-topicA.js')).size;
  const idxBefore = fs.readFileSync(path.join(tmp, 'index.html'), 'utf8');
  const code2 = run(tmp);
  const after = fs.readdirSync(path.join(tmp, 'bundle')).sort().join(',') +
    fs.statSync(path.join(tmp, 'bundle', 'data-topicA.js')).size;
  const okIdem = before === after && idxBefore === fs.readFileSync(path.join(tmp, 'index.html'), 'utf8');
  console.log(okIdem ? '✅ ④ 幂等：重跑一次后 bundle 与 index.html 完全不变' : '❌ ④ 不幂等');

  // 等价性要抓得出来：往源词表塞一个语法错误 → 必须报错退出
  W('syn-data.js', 'window.SYN_DATA={phrases:["仲裁"};oops(\n');
  let threw = false;
  if (run(tmp)) threw = true;
  console.log(threw ? '✅ ⑤ 源词表写坏时脚本报错中断（绿灯不是白给）' : '❌ ⑤ 坏源文件没被拦住');
  const okRun = code1 === 0 && code2 === 0;
  console.log(okRun ? '✅ ⑥ 两轮正常构建均返回 0' : '❌ ⑥ 正常构建返回码异常 ' + code1 + '/' + code2);

  // ⑦ 命名漂移自愈：build-bundle.js 改了命名规则后，index.html 会停在旧名上，
  //    从此页面加载不到引擎（全站检索静默失效）。脚本必须认出来并自动改正。
  W('syn-data.js', 'window.SYN_DATA={phrases:["仲裁"],entries:1};\n');   // 先修回 ⑤ 弄坏的词表
  run(tmp);
  const idxP = path.join(tmp, 'index.html');
  fs.copyFileSync(path.join(tmp, 'bundle', 'engine.js'), path.join(tmp, 'bundle', 'engine-core.js'));
  fs.writeFileSync(idxP, fs.readFileSync(idxP, 'utf8').replace('bundle/engine.js', 'bundle/engine-core.js'), 'utf8');
  const code3 = run(tmp);
  const idxNow = fs.readFileSync(idxP, 'utf8');
  const okDrift = code3 === 0 && idxNow.indexOf('bundle/engine.js') >= 0 && idxNow.indexOf('engine-core.js') < 0;
  console.log(okDrift ? '✅ ⑦ 命名漂移自愈：index.html 里的旧 bundle 名被自动改正为新名'
    : '❌ ⑦ 命名漂移没被改正（返回码 ' + code3 + '，或 index.html 仍含 engine-core）');

  fs.rmSync(tmp, { recursive: true, force: true });
  const allOk = okGroup && afterTags === 6 && okIdem && okRun && threw && okDrift;
  console.log(allOk ? '\n✅ 自测全部通过' : '\n❌ 自测未全过');
  process.exit(allOk ? 0 : 1);
}

if (process.argv.indexOf('--self-test') >= 0) {
  selfTest();
} else {
  process.exit(run());
}
