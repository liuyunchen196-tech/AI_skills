# -*- coding: utf-8 -*-
"""
flow_to_visio.py — 将 jituan-PPT 的流程图内容转换为 Visio 矢量图（.vsdx + .emf）

风格基准: C:\\Users\\liuwust\\Desktop\\PPT\\素材\\设计后期管理流程.vsdx
  - 流程步骤节点: 直角矩形, 填充 #eceef6, 边框 #3d64ac 0.75pt
  - 阶段标签节点: 直角矩形, 彩色填充(紫/橙/红/蓝/绿循环), 边框 #fe4040 红色虚线 1pt
  - 文字: 宋体(SimSun) 加粗 12pt, 黑色, 居中
  - 连接线: 黑色 0.75pt, 实心三角箭头(EndArrow=4)
  - 阶段标签沿左列竖排, 竖线串联; 步骤自左向右排布, 超宽自动换行

用法:
    python flow_to_visio.py <flow.json> <out.vsdx> [--emf <out.emf>]

flow.json 结构（与 content.json 的 flow 版式对应）:
    {"title": "...", "stages": [{"label": "施工图交付", "steps": ["...", "..."]}]}
或 简单链: {"title": "...", "steps": ["测量放线", "埋件安装", "..."]}

输出: 生成 .vsdx 与 .emf（矢量, 可直接插入 PPT 无损缩放）,
成功后在 stdout 打印 JSON: {"vsdx":..., "emf":..., "page_w":..., "page_h":...}

依赖: Windows + Microsoft Visio + pywin32 (pip install pywin32)
"""
import sys, os, io, json, math, argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---- 参考样式常量（提取自 设计后期管理流程.vsdx 实测值） ----
STEP_FILL = "#eceef6"      # 流程节点填充（淡蓝灰）
STEP_LINE = "#3d64ac"      # 流程节点边框（深蓝）
STAGE_FILLS = ["#b4a7d6", "#f9cb9c", "#ff9999", "#b5c7e7", "#99dfb9"]  # 阶段填充循环
STAGE_LINE = "#fe4040"     # 阶段节点边框（红色）
CONN_COLOR = "#000000"     # 连接线黑色
FONT_NAME = "Microsoft YaHei"  # 微软雅黑（v1.4.2，与全稿统一；不再用基准文件的宋体）
FONT_SIZE = 12             # pt
BOLD = True

LINE_W_STEP = 0.75         # pt, 流程节点边框
LINE_W_STAGE = 1.0         # pt, 阶段节点边框
LINE_W_CONN = 0.75         # pt, 连接线

# ---- 版面常量 ----
PAGE_W = 12.2              # 画布宽（英寸, 与参考 12.22 接近）
MARGIN = 0.15
STAGE_X = MARGIN           # 阶段标签列左缘
STAGE_W = 1.05             # 阶段标签宽
STEP_X0 = STAGE_X + STAGE_W + 0.55   # 步骤区左缘（阶段→步骤留箭头空间）
STEP_X1 = PAGE_W - MARGIN
GAP_X = 0.45               # 步骤间水平间距（含箭头）
ROW_GAP = 0.32             # 行间距
MIN_PAGE_H = 8.3


def _visio_bold_char(shape):
    """设置宋体加粗 12pt（与参考文件 Char 节一致）"""
    shape.CellsU("Char.Font").FormulaU = 'FONT("%s")' % FONT_NAME
    shape.CellsU("Char.Size").ResultIU = FONT_SIZE / 72.0
    shape.CellsU("Char.Style").ResultIU = 1  # bold


def _style_rect(shape, fill, line_color, line_w_pt, dashed=False, text=""):
    shape.CellsU("FillForegnd").FormulaU = 'RGB(%d,%d,%d)' % _rgb(fill)
    shape.CellsU("LineColor").FormulaU = 'RGB(%d,%d,%d)' % _rgb(line_color)
    shape.CellsU("LineWeight").ResultIU = line_w_pt / 72.0
    shape.CellsU("LinePattern").ResultIU = 2 if dashed else 1
    shape.CellsU("FillPattern").ResultIU = 1
    for c in ("LeftMargin", "RightMargin", "TopMargin", "BottomMargin"):
        shape.CellsU(c).ResultIU = 0.03
    if text:
        shape.Text = text
        # 文字块撑满形状宽度 + 强制水平方向，避免窄框把中文挤成竖排
        try:
            shape.CellsU("TextDirection").ResultIU = 0
            shape.CellsU("TxtWidth").FormulaU = "Width - 0.08 in"
            shape.CellsU("TxtHeight").FormulaU = "Height - 0.06 in"
        except Exception:
            pass
        _visio_bold_char(shape)


def _rgb(hexstr):
    h = hexstr.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _node_size(text):
    """按文字量自适应节点尺寸（文字最长行 ≤ 视觉 2 行封顶, 超出继续加高）"""
    n = len(text)
    w = min(4.6, max(1.8, n * (FONT_SIZE / 72.0) + 0.30))  # 单行容纳
    cpl = max(int((w - 0.20) / (FONT_SIZE / 72.0)), 4)
    lines = max(1, math.ceil(n / cpl))
    h = 0.42 + (lines - 1) * 0.22
    if lines > 1:  # 多行文字适当加宽, 控制行数在 2 行左右
        w = min(4.6, max(w, min(n * 0.62, 3.8) * 0.72))
        cpl = max(int((w - 0.20) / (FONT_SIZE / 72.0)), 4)
        lines = max(1, math.ceil(n / cpl))
        h = 0.42 + (lines - 1) * 0.22
    return round(w, 3), round(h, 3)


def _pack_rows(steps):
    """把步骤贪心装箱为若干行: 返回 [ [ (text,w,h), ... ], ... ]"""
    rows, cur, cur_w = [], [], 0.0
    avail = STEP_X1 - STEP_X0
    for s in steps:
        w, h = _node_size(s)
        need = w if not cur else cur_w + GAP_X + w
        if cur and need > avail:
            rows.append(cur)
            cur, cur_w = [(s, w, h)], w
        else:
            cur.append((s, w, h))
            cur_w = need
    if cur:
        rows.append(cur)
    return rows


def _connect(visio, page, from_shape, to_shape):
    """黑色实心箭头动态连接线（参考: EndArrow=4, 0.75pt, #000000）"""
    conn = page.Drop(visio.ConnectorToolDataObject, 0, 0)
    conn.CellsU("BeginX").GlueTo(from_shape.CellsU("PinX"))
    conn.CellsU("EndX").GlueTo(to_shape.CellsU("PinX"))
    conn.CellsU("LineColor").FormulaU = 'RGB(%d,%d,%d)' % _rgb(CONN_COLOR)
    conn.CellsU("LineWeight").ResultIU = LINE_W_CONN / 72.0
    conn.CellsU("EndArrow").ResultIU = 4
    return conn


def _build(visio, spec):
    doc = visio.Documents.Add("")
    page = visio.ActivePage

    stages = spec.get("stages")
    if not stages:
        steps = [s if isinstance(s, str) else s.get("text", "") for s in spec.get("steps", [])]
        steps = [s for s in steps if s]
        stages = [{"label": "", "steps": steps}] if steps else []

    # 先计算每阶段的行, 得到总行数 → 页高
    packed = []
    for st in stages:
        st_steps = [s if isinstance(s, str) else s.get("text", "") for s in st.get("steps", [])]
        st_steps = [s for s in st_steps if s]
        packed.append({"label": st.get("label", ""), "rows": _pack_rows(st_steps)})

    total_rows = sum(len(p["rows"]) for p in packed)
    # 页高按内容估算（阶段块高度 = max(实际行高, 阶段标签最小高)），避免大片空白把图压小
    est_h = 0.0
    for p in packed:
        rows = p["rows"]
        bh = sum(max(h for _, _, h in row) for row in rows) + ROW_GAP * max(len(rows) - 1, 0)
        est_h += max(bh, 0.62) + 0.16
    page_h = max(2.6, est_h + 0.55 + 0.30)
    page.PageSheet.CellsU("PageWidth").ResultIU = PAGE_W
    page.PageSheet.CellsU("PageHeight").ResultIU = page_h

    y = page_h - 0.55          # 从顶部往下画
    prev_stage = None
    stage_shapes = []
    for si, p in enumerate(packed):
        rows = p["rows"]
        block_h = sum(max(h for _, _, h in row) for row in rows) + ROW_GAP * (len(rows) - 1)
        block_top = y

        # ---- 阶段标签（左列）----
        if p["label"]:
            sh_h = max(0.62, block_h)
            sh = page.DrawRectangle(STAGE_X, block_top - sh_h, STAGE_X + STAGE_W, block_top)
            _style_rect(sh, STAGE_FILLS[si % len(STAGE_FILLS)], STAGE_LINE,
                        LINE_W_STAGE, dashed=True, text=p["label"])
            stage_shapes.append(sh)
            if prev_stage is not None:  # 阶段间竖线（无箭头, 同参考）
                conn = page.Drop(visio.ConnectorToolDataObject, 0, 0)
                conn.CellsU("BeginX").GlueTo(prev_stage.CellsU("PinX"))
                conn.CellsU("EndX").GlueTo(sh.CellsU("PinX"))
                conn.CellsU("LineColor").FormulaU = 'RGB(%d,%d,%d)' % _rgb(CONN_COLOR)
                conn.CellsU("LineWeight").ResultIU = LINE_W_CONN / 72.0
                conn.CellsU("EndArrow").ResultIU = 0
            prev_stage = sh

        # ---- 步骤节点（逐行自左向右）----
        ry = block_top
        prev_in_block = None      # 跨行/跨节点的前一个节点
        block_first_shape = None  # 本阶段首节点（阶段标签 → 它画横向箭头）
        for row in rows:
            row_h = max(h for _, _, h in row)
            total_w = sum(w for _, w, _ in row) + GAP_X * (len(row) - 1)
            x = STEP_X0          # 左对齐：内容有多宽画多宽，页宽随后自适应
            cy = ry - row_h / 2
            row_shapes = []
            for text, w, h in row:
                sh = page.DrawRectangle(x, cy - h / 2, x + w, cy + h / 2)
                _style_rect(sh, STEP_FILL, STEP_LINE, LINE_W_STEP, text=text)
                row_shapes.append(sh)
                x += w + GAP_X
            # 行内箭头
            for a, b in zip(row_shapes, row_shapes[1:]):
                _connect(visio, page, a, b)
            # 行间箭头（上一行末节点 → 本行首节点）
            if prev_in_block is not None and row_shapes:
                _connect(visio, page, prev_in_block, row_shapes[0])
            if block_first_shape is None:
                block_first_shape = row_shapes[0] if row_shapes else None
            prev_in_block = row_shapes[-1] if row_shapes else prev_in_block
            ry -= row_h + ROW_GAP

        # 阶段标签 → 本阶段首节点 横向箭头
        if p["label"] and block_first_shape is not None and stage_shapes:
            _connect(visio, page, stage_shapes[-1], block_first_shape)

        y = block_top - max(block_h, sh_h if p["label"] else block_h) - 0.16

    # ---- 画布宽度自适应内容（否则内容偏窄时整图被缩小一半）----
    max_right = 0.0
    for sh in page.Shapes:
        try:
            if int(sh.Type) != 3:      # visTypeShape；连接线不计
                continue
            r = sh.CellsU("PinX").ResultIU + sh.CellsU("Width").ResultIU / 2.0
            max_right = max(max_right, r)
        except Exception:
            pass
    if max_right:
        page.PageSheet.CellsU("PageWidth").ResultIU = max(6.6, max_right + MARGIN)

    # 保存 vsdx
    return doc, page


def main():
    ap = argparse.ArgumentParser(description="flow JSON -> Visio .vsdx + .emf")
    ap.add_argument("spec", help="flow JSON 文件")
    ap.add_argument("output", help="输出 .vsdx 路径")
    ap.add_argument("--emf", dest="emf", help="输出 .emf 路径（默认与 vsdx 同名）")
    ap.add_argument("--visible", action="store_true")
    args = ap.parse_args()

    with open(args.spec, "r", encoding="utf-8") as f:
        spec = json.load(f)

    vsdx = os.path.abspath(args.output)
    emf = os.path.abspath(args.emf) if args.emf else os.path.splitext(vsdx)[0] + ".emf"
    for p in (vsdx, emf):
        d = os.path.dirname(p)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

    import win32com.client
    visio = None
    doc = None
    try:
        try:
            visio = win32com.client.gencache.EnsureDispatch("Visio.Application")
        except Exception:
            visio = win32com.client.Dispatch("Visio.Application")
        try:
            visio.Visible = -1 if args.visible else 0
        except Exception:
            pass
        doc, page = _build(visio, spec)
        doc.SaveAs(vsdx)
        page.Export(emf)   # EMF 矢量导出
        pw = page.PageSheet.CellsU("PageWidth").ResultIU
        ph = page.PageSheet.CellsU("PageHeight").ResultIU
        print(json.dumps({"vsdx": vsdx, "emf": emf, "page_w": round(pw, 3),
                          "page_h": round(ph, 3)}, ensure_ascii=False))
    finally:
        if doc is not None:
            try:
                doc.Saved = True
                doc.Close()
            except Exception:
                pass
        if visio is not None:
            try:
                visio.Quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
