/* ============================================================
   检索语义近似层 · 通用核心（领域无关）
   ------------------------------------------------------------
   本文件是「引擎 + 语言层」，不含任何领域术语。
   领域术语放在单独的数据文件里（形如 { WORD, PHRASE, INTENT }），
   换一个领域就换一份数据表，本文件不用动。

   为什么需要它：
     离线单页的搜索是「字符串包含」，读者用口语提问时常常
     命中不了——因为他脑子里没有那个规范术语。真正的语义检索
     需要向量模型，离线做不到；用「同义词表 + 口语问法映射」
     做近似，成本极低，召回率提升明显。

   三层展开（顺序即优先级）：
     ① 整句映射   —— 读者打的一整句口语，直接映射到一组术语
     ② 意图识别   —— 「要多久」「多少钱」「去哪办」这类通用疑问，
                     由领域表决定映射成什么术语
     ③ 词级展开   —— 逐词查同义词表，双向生效

   使用方式：
     var sx = window.SYN_CORE.expand(q, window.SYN_DATA);
     // => { ex: ['违约金酌减', ...], label: '公司把我开了', intent: ['COST'] }

   维护纪律（与领域表共同遵守）：
     · 只加**确实等价或高度近义**的词，弱相关词会污染结果
     · 精确性优先：宁可召回少，不可召回错
     · 这是规则驱动的近似，不是真语义理解；表外的新说法仍会退化
       为关键词匹配，所以词表要随读者反馈持续维护

   2026-10-02 从 syn-data.js 抽出通用层。
   ============================================================ */

window.SYN_CORE = (function () {
  'use strict';

  /* ---------- 一、通用噪音词（纯语言层，任何领域都该丢掉） ---------- */
  var STOP = [
    '怎么办', '咋办', '该怎么办', '如何', '怎么', '什么', '哪些', '哪个',
    '我想问', '我想知道', '我想', '我要', '请问', '请教', '求助',
    '一下', '的话', '了吗', '了么', '能不能', '可不可以', '有没有',
    '是不是', '算不算', '是不是算', '应该', '可以', '需要', '要不要',
    '谢谢', '谢了', '在线等', '急急急', '大神', '你好', '您好', '麻烦'
  ];

  /* ---------- 二、通用疑问意图（领域无关，只识别「问的是哪一类」） ----------
     这里只做「识别出意图」，不映射到任何术语——
     映射到什么术语，由领域表的 INTENT 字段决定。
     例如同样是 DURATION，法律领域映射「诉讼时效 / 办案期限」，
     社保领域映射「办理时限 / 到账时间」。                        */
  var INTENT = [
    ['DURATION',  ['要多久', '多久', '多长时间', '几天', '几日', '几个月', '多少天',
                   '什么时候', '啥时候', '多长', '期限', '时限', '等到', '要等']],
    ['COST',      ['多少钱', '多少费用', '要花多少', '花多少', '收费', '费用', '贵不贵',
                   '价格', '缴多少', '交多少', '要交多少', '得多少钱']],
    ['WHERE',     ['去哪', '哪里', '哪儿', '上哪', '找谁', '哪个部门', '什么部门',
                   '在哪办', '去什么地方', '哪个机构', '去哪儿']],
    ['MATERIAL',  ['要什么材料', '需要什么材料', '要哪些材料', '需要哪些材料',
                   '带什么', '准备什么', '啥材料', '什么材料', '要啥手续']],
    ['CONDITION', ['什么条件', '需要什么条件', '要什么条件', '够不够', '够不够格',
                   '有没有资格', '什么资格', '能不能办', '符不符合']],
    ['APPEAL',    ['不服', '不同意', '不认可', '申诉', '投诉', '举报',
                   '复议', '重新审', '不认']],
    ['URGENT',    ['加急', '来不及', '最快', '立刻', '马上', '着急', '特急']]
  ];

  /* ---------- 三、工具：切词（按标点与空白，无分词库） ---------- */
  function cut(s){
    return s.split(/[\s,，。？?！!、；;：:（）()【】\[\]“”"'\/]+/).filter(function(w){
      return !!w;
    });
  }

  /* ---------- 四、引擎 ----------
     q       —— 用户原始查询（建议已转小写）
     domain  —— 领域数据表，形如：
                { WORD: {口语:[术语...]}, PHRASE: [[口语句,[术语...]]],
                  INTENT: { DURATION:[...], COST:[...] }, STOP: [...] }
                兼容旧字段名 SYN_WORD / SYN_PHRASE / STOP。          */
  function expand(q, domain){
    var empty = { ex: [], label: '', intent: [] };
    if(!q) return empty;
    domain = domain || {};

    var W  = domain.WORD    || domain.SYN_WORD    || {};
    var P  = domain.PHRASE  || domain.SYN_PHRASE  || [];
    var IM = domain.INTENT  || {};
    /* 噪音词 = 通用层 + 领域层补充 */
    var ST = STOP.concat(domain.STOP || []);

    /* ex 与 exw 平行：ex[i] 是词，exw[i] 是它的置信权重。
       权重分四档——整句映射最可信，词级精确命中次之，
       通用疑问意图再次，子串兜底最弱（它最容易误伤）。      */
    var W_PHRASE = 1.0, W_WORD = 1.0, W_INTENT = 0.75, W_SUB = 0.35;
    var ex = [], exw = [], exi = [], label = '', intents = [], i;

    /* 通用词集合 = 噪音词 + 全部疑问意图的触发词（要多久/多少钱/去哪办…）。
       这些词字面会出现在绝大多数查询里，但它们表达的是「问法」不是「事由」。
       ③+ 进位时要靠它挡住。领域层若补了 STOP，已在 ST 里带上。 */
    var GEN = ST.slice();
    for(var gi = 0; gi < INTENT.length; gi++){ GEN = GEN.concat(INTENT[gi][1]); }

    /* exi[i] = 1 表示这个词来自「通用疑问意图」，0 表示来自读者说的事由。
       下游据此决定：意图词能不能单独把一节顶上来（见 index.html）。 */
    function add(terms, w, isIntent){
      for(var k = 0; k < terms.length; k++){
        var t = String(terms[k] || '').toLowerCase();
        if(!t || q.indexOf(t) >= 0) continue;      /* 原文已含，不必再算 */
        var pos = ex.indexOf(t);
        if(pos >= 0){
          if(w > exw[pos]){ exw[pos] = w; exi[pos] = isIntent ? 1 : 0; }
          else if(!isIntent && exi[pos]) exi[pos] = 0;  /* 事由词优先，覆盖意图标记 */
          continue;
        }
        ex.push(t); exw.push(w); exi.push(isIntent ? 1 : 0);
      }
    }

    /* ① 整句映射优先：读者打的是一整句口语 */
    for(i = 0; i < P.length; i++){
      if(q.indexOf(P[i][0]) >= 0){
        add(P[i][1], W_PHRASE);
        if(!label) label = P[i][0];
      }
    }

    /* ② 词级展开：去掉噪音词后逐词查表，双向生效 */
    var q2 = q;
    for(i = 0; i < ST.length; i++){ q2 = q2.split(ST[i]).join(' '); }
    var words = cut(q2);
    var keys = Object.keys(W);
    /* 键与查询统一小写口径。
       查询在进引擎前已被 toLowerCase（见 index.html doSearch），
       而 Object.keys(W) 保留词表原样——含拉丁字母的键
       （N加一 / 2N 这类）会完全匹配不上：现象上像是
       「库里没有这个内容」，其实是词表键根本没被匹配到。
       这里建一份「小写键 → 原键」映射，后面查表与子串比较一律走小写。 */
    var KW = {};
    for(i = 0; i < keys.length; i++){ var lk = keys[i].toLowerCase(); if(!(lk in KW)) KW[lk] = keys[i]; }
    var wordHit = false;
    words.forEach(function(w){
      var kw = KW[w] || w;
      if(W[kw]){ add(W[kw], W_WORD); wordHit = true; }
      /* 双向：直接搜某个术语时，也能反查到它的口语说法 */
      for(var k = 0; k < keys.length; k++){
        if(keys[k].toLowerCase() !== w && W[keys[k]].indexOf(w) >= 0){ add([keys[k]], W_WORD * 0.9); wordHit = true; }
      }
    });

    /* ③ 子串兜底：没有分词库，整句里含某个词条也应命中。
          例：「生育津贴要什么材料」去掉噪音后是「生育津贴要材料」，
          切不出「生育津贴」这个词，但它是词表里的键。
          只认 2 字以上的键，避免单字误伤；权重最低，避免误伤顶翻正解。 */
    var q3 = q2.replace(/\s+/g, '');
    for(i = 0; i < keys.length; i++){
      var lk2 = keys[i].toLowerCase();
      if(lk2.length >= 2 && q3.indexOf(lk2) >= 0) add(W[keys[i]], W_SUB);
    }

    /* ③+ 读者字面打出来的词表键，本身要进位。
       上面 add 进去的永远是某个键的**反查值**，键自己永远不进 ex：
       add 里有「原文已含就跳过」，读者亲手敲的词表键会被它挡掉。
       后果是读者亲手敲的那个事由（它正是词表键）没进扩展词，
       只剩反查值以 0.35 兜底权重参与打分；
       而标题里写着泛意图词（如「办案期限」）的无关章节，
       靠 40 × 0.75 × 0.3 反过来把正解顶到了第二位——
       读者说的是那个事由，不是泛意图词。                        */
    /* 通用词表也统一小写口径，避免领域表补进含拉丁字母的噪音词时漏挡 */
    var GENL = [];
    for(i = 0; i < GEN.length; i++){ GENL.push(String(GEN[i]).toLowerCase()); }
    for(i = 0; i < keys.length; i++){
      var kk = keys[i];
      var kkl = kk.toLowerCase();
      if(kkl.length < 2 || q3.indexOf(kkl) < 0) continue;
      /* 两种词不当事由：通用疑问词与噪音词（「多久」「怎么办」这类
         只要字面出现在句子里就会被捞出来，一旦按w=1算，就能绕开
         意图词那条 ×0.3 的保护，直接把不相关的节顶上来）；
         以及词表里压根没有映射的普通词（「打官司」——它是读者随口说的
         一句，不是词条，让它以 w=1 进正文匹配只会放大噪音）。   */
      if(GENL.indexOf(kkl) >= 0 || !W[kk]) continue;
      var p2 = ex.indexOf(kk);
      if(p2 >= 0){
        /* 已经以更低的权重进过 ex（多半是兜底捞出来的反查值/意图值），
           抬到词级权重，并归为「读者说出的事由」。                */
        if(exw[p2] < W_WORD){ exw[p2] = W_WORD; exi[p2] = 0; }
      } else {
        ex.push(kk); exw.push(W_WORD); exi.push(0);
      }
    }

    /* ④ 通用疑问意图：只认出「问的是哪一类」，映射交给领域表。
          权重低于整句与词级命中——「要多久」这类问法很泛，
          不能让读者真正说出的那个事由被泛词盖过去。            */
    for(i = 0; i < INTENT.length; i++){
      var tag = INTENT[i][0], trig = INTENT[i][1], hit = false;
      for(var j = 0; j < trig.length; j++){
        if(q.indexOf(trig[j]) >= 0){ hit = true; break; }
      }
      if(hit){
        intents.push(tag);
        if(IM[tag]) add(IM[tag], W_INTENT, true);
      }
    }

    /* hasCore：读者到底说没说出一件具体的事。
       说出来了（「劳动仲裁要多久」里的劳动仲裁）→ 意图词只作强化；
       没说出来（「不服一审判决」）→ 意图词可以独立生效。        */
    var hasCore = false;
    for(i = 0; i < exi.length; i++){ if(!exi[i]){ hasCore = true; break; } }

    return { ex: ex, exw: exw, exi: exi, hasCore: hasCore, label: label, intent: intents };
  }

  return {
    VERSION: '1.0.0',
    STOP: STOP,
    INTENT: INTENT,
    expand: expand
  };
})();
