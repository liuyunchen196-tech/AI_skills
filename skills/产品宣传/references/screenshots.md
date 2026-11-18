# 界面截图操作手册（真实截图，不用示意图）

目标：为 PPT 提供 8~10 张真实界面截图，覆盖首页 / 列表 / 详情 / 导航 / 检索 / 弹窗 / 模板 / 产物。

## 〇、总原则

- 先启动项目的**真实服务**再截；截图分辨率 `--window-size=1600,1000 --force-device-scale-factor=2`；
- **中文路径下必须用 PowerShell 调 Edge**——Bash 传参会把 UTF-8 路径按 GBK 解释，Edge 静默失败（退出码 0 但无输出）；
- 每张截图用独立的 `--user-data-dir`，避免配置锁；
- 每截一张用 ViewImage 检查：状态是否到位、有无截断，不合格重抓。

## 一、静态截图（页面加载即可，如首页）

```powershell
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
& $edge --headless=new --disable-gpu --no-sandbox --hide-scrollbars --no-first-run `
  --user-data-dir="D:\work\p_01" --window-size=1600,1000 --force-device-scale-factor=2 `
  --virtual-time-budget=14000 --screenshot="D:\work\shots\01_home.png" `
  "http://127.0.0.1:5000/" 2>$null | Out-Null
```

## 二、交互状态截图（点按/弹窗后才能看到的画面）

无头 Edge 不便做 CDP 交互（调试端口模式在本环境会秒退），改用**临时注入路由**：
在项目后端加一个只用于截图的路由，把 `index.html` 读出来、在 `</body>` 前注入状态脚本，
按 `?s=状态名` 执行点按/填表，然后用静态截图方式截 `/__shot?s=xxx`。

```python
@app.get("/__shot")
def __shot():
    """临时：给截图脚本注入状态用的调试入口（截完即删）。"""
    import pathlib
    html = (pathlib.Path(app.root_path) / "templates" / "index.html").read_text(encoding="utf-8")
    inject = """
<script>
(function(){
  var s = new URLSearchParams(location.search).get('s');
  if(!s) return;
  function q(x){return document.querySelector(x);}
  function wait(ms){return new Promise(function(r){setTimeout(r,ms)});}
  (async function(){
    await wait(2200);                     // 等首屏数据加载完
    try {
      if (s === 'chapters') { q('#partGrid .card').click(); await wait(1400); }
      if (s === 'detail')   { q('#partGrid .card').click(); await wait(1200);
                              q('#chapterGrid .card').click(); await wait(1200);
                              var li=document.querySelectorAll('#sectionList li'); if(li[0]) li[0].click(); await wait(2000); }
      if (s === 'search')   { q('#searchInput').value='关键词'; q('#searchBtn').click(); await wait(2000); }
      if (s === 'entry')    { q('#btnEntry').click(); await wait(1200);
                              q('#entryChapter').value='示例章'; q('#fProcess').value='工序1 → 工序2'; }
      if (s === 'import')   { q('#btnImport').click(); await wait(1200); }
    } catch(e) { document.title = 'ERR ' + e.message; }
  })();
})();
</script>
"""
    return html.replace("</body>", inject + "</body>")
```

要点与坑：

- **必须走专用路由**：写在普通首页 `/?s=` 上不生效（首页路由不会注入脚本）；
- 注入脚本里选择器按目标项目前端实际 id/class 改；
- `--virtual-time-budget` 给足（≥14000），否则截到的还是首页；
- 批量抓取用 PowerShell 循环，每个状态一个 `--user-data-dir`；
- **截完删除临时路由并重启服务**，保持生产代码干净。

## 三、Excel/表格素材截图（Excel COM）

```powershell
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false; $excel.DisplayAlerts = $false
$wb = $excel.Workbooks.Open("D:\work\模板.xlsx")
$ws = $wb.Worksheets.Item("标准数据"); $ws.Activate()
$range = $ws.Range("A1:H8")
$range.CopyPicture(1, 2)   # xlScreen, xlBitmap
$chartObj = $ws.ChartObjects().Add(0, 0, $range.Width, $range.Height)
$chart = $chartObj.Chart; $chart.Paste()
$chartObj.Chart.Export("D:\work\shots\09_template.png")
$chartObj.Delete(); $wb.Close($false); $excel.Quit()
```

## 四、单文件 HTML / 本地文件截图

文件名含中文时先拷到 ASCII 路径，再 `file:///` 截图：

```bash
curl -s -o /d/_tmp_standalone.html "http://127.0.0.1:5000/api/export"
```
```powershell
& $edge --headless=new ... --virtual-time-budget=25000 `
  --screenshot="...\10_standalone.png" "file:///D:/_tmp_standalone.html" 2>$null | Out-Null
```
截完删除临时文件。内嵌大文件的页面给足 virtual-time-budget（≥25000）。

## 五、PPT 渲染复核截图

见 `scripts/render_pptx.py`（PowerPoint COM 把 pptx 逐页导出 PNG，逐页 ViewImage 检查）。
