# 技能联接维护脚本（2026-11-12）
# 约定：D:\AI技能库\skills 是唯一真实源；各 AI 的技能目录里，每个技能都应是
#       指向该库的一条目录联接（Junction），这样在库里改 = 所有 AI 同时生效。
#
# 安全边界：本脚本只创建联接，不删除、不覆盖任何目录或文件。
#          若目标位置已是真实目录（有文件），一律跳过并提示需要人工处理。
#
# 用法：
#   pwsh D:\AI技能库\relink-skills.ps1               # 真正执行
#   pwsh D:\AI技能库\relink-skills.ps1 -WhatIfOnly   # 只打印将要做什么

param(
    [string]$LibRoot = 'D:\AI技能库\skills',
    [string[]]$Targets = @(
        'C:\Users\liuwust\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills',
        'C:\Users\liuwust\.workbuddy\skills',
        'C:\Users\liuwust\.mobilework\skills'
    ),
    [switch]$WhatIfOnly
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $LibRoot)) { throw "库目录不存在：$LibRoot" }
$skills = @(Get-ChildItem -LiteralPath $LibRoot -Force -Directory | Sort-Object Name)

foreach ($dir in $Targets) {
    $root = $dir.TrimEnd('\')
    Write-Output ""
    Write-Output ("== 目标：" + $root)
    if (-not (Test-Path -LiteralPath $root)) { Write-Output "   目录不存在，跳过"; continue }

    $ok = 0; $created = 0; $real = @(); $foreign = @()
    foreach ($s in $skills) {
        $src = $s.FullName
        $dst = Join-Path $root $s.Name

        if (-not (Test-Path -LiteralPath $dst)) {
            if ($WhatIfOnly) { Write-Output ("   [will create] " + $s.Name); $created++ }
            else {
                New-Item -ItemType Junction -Path $dst -Target $src | Out-Null
                Write-Output ("   [created] " + $s.Name); $created++
            }
            continue
        }

        $item = Get-Item -LiteralPath $dst -Force
        if ($item.LinkType -eq 'Junction') {
            $t = ($item.Target -join ';').TrimEnd('\')
            if ($t -ieq $src.TrimEnd('\')) { $ok++ } else { $foreign += ($s.Name + ' -> ' + $t) }
            continue
        }

        $files = @(Get-ChildItem -LiteralPath $dst -Recurse -File -Force -ErrorAction SilentlyContinue).Count
        $real += ($s.Name + " (真实目录, $files 个文件)")
    }

    Write-Output ("   已正确联接：" + $ok + "  新建：" + $created)
    if ($real.Count -gt 0)     { Write-Output ("   真实目录（需人工确认后再改联接）：" + ($real -join '、')) }
    if ($foreign.Count -gt 0)  { Write-Output ("   指向别处的联接：" + ($foreign -join '、')) }
}

Write-Output ""
Write-Output "提示：豆包新增联接后，重启豆包客户端或新开会话，技能列表才会刷新。"
