/* ============================================================
   project-checks.example.js —— 「项目私有校验断言」参考实现
   ------------------------------------------------------------
   用法：复制为同目录的 project-checks.js 再改内容；
        check-data.js 的【5】段会调用它，文件不存在时该段整体跳过。

   什么该放在这里：**换个知识库就不成立**的业务规则。三类典型：
     ① 迁移完整性 / 洁净度 —— 某一批节 id 应当从 A 库迁到 B 库，
        迁完 A 库不得残留、B 库一个都不能少；
     ② 规模口径一致性 —— 库的 subtitle 里写死的「N 组 M 个专题」
        必须与实测一致（书写格式各家不同，所以放这里而不是通用脚本里）；
     ③ 特定题材的取材口径 —— 某类前缀的节必须标注数据来源 /
        不得出现某类未决表述。

   什么不该放在这里：任何通用规则（分组引用、标签配平、口径块、三套轨道…）
   —— 那些已经在 check-data.js 里，跟知识库领域无关。

   ⚠️ 本文件**不要随技能/专家包一起发布**：它是本项目的业务规则，
      对使用者没有意义，还会把项目内部的节 id 带出去。
   ============================================================ */
module.exports = function (ctx) {
  const { win, LIBS, err, warn, log, errors } = ctx;
  log('\n【5】规模统计与库元数据一致性（项目私有断言）');

  /* 用 root 名取库；取不到就跳过（不要报错） */
  const A = win.TOPIC_A_DATA;
  const B = win.TOPIC_B_DATA;

  /* ---------- ① 迁移完整性：一批节从 A 库迁到 B 库 ---------- */
  const MIGRATED = ['topic-a-1', 'topic-a-2', 'topic-a-3'];   /* ← 换成你自己的 id 清单 */
  if (B) {
    const lost = MIGRATED.filter(id => !B.sections[id]);
    if (lost.length) err(`B 库缺少应迁入的章节：${lost.join(', ')}`);
    else log(`  · 迁移完整性：${MIGRATED.length} 个章节已全部就位 ✓`);
  }
  if (A) {
    const residual = MIGRATED.filter(id => A.sections[id]);
    if (residual.length) err(`A 库仍残留已迁出的章节（应已移入 B 库）：${residual.join(', ')}`);
    else log('  · 迁移洁净度：A 库已无迁出章节残留 ✓');
  }

  /* ---------- ② 规模口径一致性：subtitle 写死的数字 vs 实测 ---------- */
  if (A) {
    const secs = Object.keys(A.sections || {});
    const groups = A.groups || [];
    const m = String(A.subtitle || '').match(/共\s*<b>(\d+)\s*个专题（(\d+)\s*组）<\/b>/);
    if (m) {
      if (Number(m[1]) !== secs.length) err(`A 库 subtitle 写「${m[1]} 个专题」，实际 ${secs.length} 个`);
      if (Number(m[2]) !== groups.length) err(`A 库 subtitle 写「${m[2]} 组」，实际 ${groups.length} 组`);
      if (!errors()) log('  · A 库 subtitle 与实测规模一致 ✓');
    } else warn('A 库 subtitle 未按约定格式书写，跳过一致性核对');
  }

  /* ---------- ③ 特定题材的取材口径自查 ---------- */
  if (B) {
    const ids = Object.keys(B.sections || {}).filter(id => /^topic-b-/.test(id));
    let bare = 0;
    ids.forEach(id => {
      const h = (B.sections[id] || {}).html || '';
      if (!/口径|待核|未公布|第三方/.test(h)) bare++;      /* 必须有出处或口径标注 */
    });
    if (bare) warn(`B 库有 ${bare} 个「topic-b-」章节未出现任何口径说明，请核对数据来源标注`);
  }

  /* 想加更多断言就照上面的写法继续；ctx 里还有 LIBS（全部库）可用 */
  void LIBS;
};
