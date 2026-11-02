# Builds deliverables/Group19_Capstone_Poster.pptx and .pdf (A1 portrait) with Microsoft PowerPoint.
#   powershell -ExecutionPolicy Bypass -File docs\submission\build_poster.ps1
# PowerPoint opens a window while the chart is drawn; that is expected.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$fig = Join-Path $PSScriptRoot 'poster_figures'
$pptx = Join-Path $root 'deliverables\Group19_Capstone_Poster.pptx'
$pdf = [IO.Path]::ChangeExtension($pptx, '.pdf')
$png = Join-Path $PSScriptRoot 'poster_preview.png'

function U($t) {   # this file stays ASCII so PowerShell 5.1 reads it correctly
  $map = @{ '{rs}' = 0x20B9; '{en}' = 0x2013; '{a}' = 0x3B1; '{sg}' = 0x3C3; '{ap}' = 0x2019; '{x}' = 0xD7; '{ar}' = 0x2192; '{dot}' = 0xB7; '{lam}' = 0x3BB; '{div}' = 0xF7; '{lq}' = 0x201C; '{rq}' = 0x201D; '{u}' = 0xFC }
  foreach ($k in $map.Keys) { $t = $t.Replace($k, [string][char]$map[$k]) }
  return $t
}

# colours (PowerPoint wants BGR integers)
$red = 0x2C30B9; $navy = 0x5F3A1F; $maroon = 0x2B1A8B; $grey = 0xEEEFF0; $ink = 0x333333; $white = 0xFFFFFF; $mute = 0x666666
$ev = @(0xB5A49A, 0xCF8F6B, 0xC46F3A, 0x9E4F1D)   # evidence ramp #9aa4b5 #6b8fcf #3a6fc4 #1d4f9e

$W = 1684.0; $Hgt = 2384.0
$p = New-Object -ComObject PowerPoint.Application
$pres = $p.Presentations.Add($true)
try {
  $pres.PageSetup.SlideWidth = $W; $pres.PageSetup.SlideHeight = $Hgt
  $s = $pres.Slides.Add(1, 12)
  $pres.Windows(1).View.GotoSlide(1)

  function Box($x, $y, $w, $h, $fill, $name, $adj = 0.0, $type = 5) {
    $b = $s.Shapes.AddShape($type, [single]$x, [single]$y, [single]$w, [single]$h); $b.Name = $name
    if ($type -eq 5) { $b.Adjustments.Item(1) = $adj }
    $b.Fill.ForeColor.RGB = $fill; $b.Line.Visible = 0; $b.Shadow.Visible = 0; return $b
  }
  function Txt($x, $y, $w, $h, $t, $size, $color, $bold, $name, $align = 1) {
    $b = $s.Shapes.AddTextbox(1, [single]$x, [single]$y, [single]$w, [single]$h); $b.Name = $name
    $f = $b.TextFrame; $f.WordWrap = -1; $f.AutoSize = 0; $b.Height = [single]$h
    $f.MarginLeft = 0; $f.MarginRight = 0; $f.MarginTop = 0; $f.MarginBottom = 0
    $r = $f.TextRange; $r.Text = (U $t); $r.Font.Name = 'Times New Roman'; $r.Font.Size = [single]$size; $r.Font.Color.RGB = $color
    if ($bold) { $r.Font.Bold = -1 }
    $r.ParagraphFormat.Alignment = $align
    return $b
  }
  function Pic($file, $x, $y, $w, $name) {
    $i = $s.Shapes.AddPicture((Join-Path $fig $file), 0, -1, [single]$x, [single]$y)
    $i.LockAspectRatio = -1; $i.Width = [single]$w; $i.Name = $name; $i.AlternativeText = $name
    $i.Line.Visible = -1; $i.Line.ForeColor.RGB = 0xD0D0D0; $i.Line.Weight = 1
    return $i
  }
  function Section($x, $y, $w, $title) {
    [void](Box $x $y $w 54 $navy "Head $title" 0.18)
    $t = Txt ($x + 18) $y ($w - 36) 54 $title 30 $white $true "Head text $title"; $t.TextFrame.VerticalAnchor = 3
    return ($y + 70)
  }

  # ---------- header
  [void](Box 0 0 $W 236 $red 'Header band' 0 1)
  [void](Box 36 30 290 176 $white 'NMIMS logo box' 0.08)
  $l = $s.Shapes.AddPicture((Join-Path $root 'docs\report\nmims_logo.jpg'), 0, -1, [single]0, [single]0); $l.LockAspectRatio = -1; $l.Height = 150; $l.Left = [single](36 + (290 - $l.Width) / 2); $l.Top = 43; $l.Name = 'NMIMS logo'; $l.AlternativeText = 'SVKM NMIMS logo'
  [void](Box ($W - 326) 30 290 176 $white 'Beretta logo box' 0.08)
  $l = $s.Shapes.AddPicture((Join-Path $PSScriptRoot 'beretta_logo.png'), 0, -1, [single]0, [single]0); $l.LockAspectRatio = -1; $l.Width = 240; $l.Left = [single]($W - 326 + 25); $l.Top = [single](118 - $l.Height / 2); $l.Name = 'Beretta logo'; $l.AlternativeText = 'Beretta logo'
  [void](Txt 350 34 984 120 'An Explainable Automated Cyber-Insurance Underwriting and Continuous Monitoring Platform' 40 $white $true 'Title' 2)
  [void](Txt 350 172 984 34 'Capstone Project {dot} Group 19 {dot} B.Tech CSE (Cybersecurity) {dot} MPSTME, SVKM{ap}s NMIMS, Mumbai {dot} 2026-27' 22 $white $false 'Subtitle' 2)
  [void](Box 0 236 $W 74 $grey 'Member band' 0 1)
  $m = Txt 50 236 ($W - 100) 74 'Krish Mundhra (K041)   {dot}   Harsh Rathod (K080)   {dot}   Yugandhara Goud (K023)          Faculty Mentor: Prof. Rohit Suryawanshi' 26 $ink $true 'Members' 2
  $m.TextFrame.VerticalAnchor = 3

  $cw = 501.0; $gx = 40.0
  $c1 = 50.0; $c2 = $c1 + $cw + $gx; $c3 = $c2 + $cw + $gx
  $top = 340.0

  # ---------- column 1: abstract, problem, market
  $y = Section $c1 $top $cw 'Abstract'
  $t = Txt $c1 $y $cw 470 'Indian SMEs face the same ransomware, email-compromise and payment-fraud attacks as large firms, yet few carry cyber insurance, and the cover they can buy is priced from a self-completed questionnaire that nobody checks again. Beretta is an open prototype that links evidence, pricing, binding and post-bind monitoring in one inspectable pipeline. Evidence for each control is graded from DECLARED to TECHNICALLY_OBSERVED; a frequency{en}severity engine prices five perils from published claims data; and after bind a read-only agent sends signed reports that move warranty states but never the premium. Every parameter carries its source, and all 224 automated tests pass.' 22 $ink $false 'Abstract text' 1
  $y = $y + 396
  $y = Section $c1 $y $cw 'Problem Statement'
  $probs = @(
    @('Priced with traditional thinking', 'Short, heavy-tailed loss history; premiums rest on revenue and industry.'),
    @('The premium is a black box', 'The insured cannot see which answer raised it or what would lower it.'),
    @('One questionnaire, once a year', 'A self-completed form fixes the price until renewal.'),
    @('Controls are never verified', 'A declared {lq}yes{rq} is priced the same as a test result.'),
    @('A static view of a dynamic landscape', 'Nothing is checked after bind; gaps surface only at claim time.')
  )
  $i = 0
  foreach ($q in $probs) {
    $i++
    $o = $s.Shapes.AddShape(9, [single]$c1, [single]($y + 4), 40, 40); $o.Name = "Problem dot $i"; $o.Fill.ForeColor.RGB = $maroon; $o.Line.Visible = 0; $o.Shadow.Visible = 0
    $f = $o.TextFrame; $f.MarginLeft = 0; $f.MarginRight = 0; $f.MarginTop = 0; $f.MarginBottom = 0; $f.VerticalAnchor = 3
    $r = $f.TextRange; $r.Text = "$i"; $r.Font.Name = 'Times New Roman'; $r.Font.Size = 20; $r.Font.Bold = -1; $r.Font.Color.RGB = $white; $r.ParagraphFormat.Alignment = 2
    $b = Txt ($c1 + 56) $y ($cw - 56) 92 ("$($q[0])`r$($q[1])") 21 $ink $false "Problem $i"
    $hp = $b.TextFrame.TextRange.Paragraphs(1); $hp.Font.Bold = -1; $hp.Font.Color.RGB = $maroon; $hp.Font.Size = 23
    $y = $y + 108
  }
  $y = $y + 16
  $y = Section $c1 $y $cw 'Market Context'
  $tiles = @(@('8.84 crore', 'enterprises on India{ap}s Udyam portals (2026)'), @('Under 5%', 'of Indian companies hold cyber cover (estimates)'), @('18.4% a year', 'forecast growth in India, against 14.2% worldwide'), @("{rs}25.5 crore", 'average cost of a breach in India (IBM 2026)'))
  $tw = ($cw - 20) / 2; $i = 0
  foreach ($q in $tiles) {
    $tx = $c1 + ($i % 2) * ($tw + 20); $ty = $y + [math]::Floor($i / 2) * 150; $i++
    [void](Box $tx $ty $tw 136 $grey "Market tile $i" 0.08)
    [void](Txt ($tx + 8) ($ty + 14) ($tw - 16) 50 $q[0] 36 $maroon $true "Market stat $i" 2)
    [void](Txt ($tx + 12) ($ty + 70) ($tw - 24) 60 $q[1] 18 $ink $false "Market label $i" 2)
  }
  $y = $y + 300
  $t = Txt $c1 $y $cw 130 'The gap: premium is concentrated in large firms, underwriting still rests on a self-completed questionnaire, and we did not find an Indian insurer that includes continuous monitoring in its policy. Sources: Ministry of MSME via KNN India; IJIRL (2025); MarketsandMarkets; IBM Cost of a Data Breach 2026.' 19 $mute $false 'Market note' 1
  $y = $y + 150
  $y = Section $c1 $y $cw 'Objectives'
  $ob = Txt $c1 $y $cw 240 ("Verify declared controls with a read-only agent`
Grade evidence by strength`
Develop a pricing mechanism from industry data`
Make premiums transparent and explainable`
Monitor warranties continuously after bind`
Give every user an interactive dashboard") 20 $ink $false 'Objectives list' 1
  $r = $ob.TextFrame.TextRange; $r.ParagraphFormat.Bullet.Visible = -1; $r.ParagraphFormat.Bullet.Character = 8226; $r.ParagraphFormat.SpaceAfter = 4
  $ob.TextFrame.Ruler.Levels(1).FirstMargin = 0; $ob.TextFrame.Ruler.Levels(1).LeftMargin = 18

  # ---------- column 2: methodology
  $y = Section $c2 $top $cw 'Methodology'
  [void](Txt $c2 $y $cw 60 'Two engines share one record of evidence. Signed reports flow from the insured{ap}s machines to the collector, and one signed roll-up per company flows to the platform.' 21 $ink $false 'Method intro' 4)
  $y = $y + 84
  $i1 = Pic 'architecture.png' $c2 $y $cw 'Architecture: agents, collector and platform'
  $y = $y + $i1.Height + 8
  [void](Txt $c2 $y $cw 26 'System architecture' 17 $mute $false 'Arch caption' 2)
  $y = $y + 64
  [void](Txt $c2 $y $cw 32 'Risk engine: grading evidence by strength' 24 $maroon $true 'Ladder title')
  $y = $y + 40
  $labels = @('DECLARED', 'DOCUMENTED', 'TESTED', 'TECHNICALLY OBSERVED'); $notes = @('questionnaire', 'policy, SOC 2, ISO 27001', 'restore test, pen test', 'agent, fleet, scan')
  $bw = ($cw - 30) / 4
  for ($k = 0; $k -lt 4; $k++) {
    $bh = 60 + 40 * $k; $bx = $c2 + $k * ($bw + 10); $by = $y + 180 - $bh
    $b = Box $bx $by $bw $bh $ev[$k] "Ladder bar $($k + 1)" 0.06
    [void](Txt $bx ($y + 186) $bw 46 $labels[$k] 16 $navy $true "Ladder label $($k + 1)" 2)
    [void](Txt $bx ($y + 230) $bw 40 $notes[$k] 15 $mute $false "Ladder note $($k + 1)" 2)
  }
  [void](Txt $c2 ($y + 4) $cw 30 'stronger evidence {ar} more premium credit' 17 $mute $false 'Ladder arrow' 1)
  $y = $y + 310
  [void](Txt $c2 $y $cw 32 'Pricing engine: five perils, priced once' 24 $maroon $true 'Pricing title')
  $y = $y + 40
  $steps = @(
    @('Frequency', '{lam} = {lam}_global {x} turnover {x} sector {x} controls {x} claims'),
    @('Severity', 'lognormal loss, {sg} = 2.193 (NetDiligence SME claims)'),
    @('Payout', 'integrated through the retention and the limit'),
    @('Premium', 'expected loss {div} 0.50 target loss ratio, + 18% GST')
  )
  $k = 0
  foreach ($q in $steps) {
    $k++
    $c = Box $c2 $y 150 52 $navy "Step $k" 0.15
    $tt = $c.TextFrame.TextRange; $tt.Text = (U $q[0]); $tt.Font.Name = 'Times New Roman'; $tt.Font.Size = 20; $tt.Font.Bold = -1; $tt.Font.Color.RGB = $white; $c.TextFrame.VerticalAnchor = 3
    $d2 = Box ($c2 + 160) $y ($cw - 160) 52 $grey "Step detail $k" 0.15
    $tt = $d2.TextFrame.TextRange; $tt.Text = (U $q[1]); $tt.Font.Name = 'Times New Roman'; $tt.Font.Size = 17; $tt.Font.Color.RGB = $ink; $tt.ParagraphFormat.Alignment = 1; $d2.TextFrame.MarginLeft = 10; $d2.TextFrame.VerticalAnchor = 3
    $y = $y + 60
  }
  [void](Txt $c2 ($y + 2) $cw 56 'A stated control earns 60% of a verified control{ap}s credit; claims history uses credibility ({a} = 4.22). Every number carries its source and a tag.' 18 $mute $false 'Pricing note' 4)
  $y = $y + 94
  [void](Txt $c2 $y $cw 32 'After bind: warranties, never the premium' 24 $maroon $true 'Warranty title')
  $y = $y + 40
  $i2 = Pic 'warranty_states.png' $c2 $y $cw 'Warranty state machine'
  $y = $y + $i2.Height + 30
  [void](Txt $c2 $y $cw 32 'Every quote explains itself' 24 $maroon $true 'Quote title')
  $y = $y + 40
  $i4 = Pic 'quote_screen.png' $c2 $y $cw 'Quote screen: premium, eligibility and referral'
  $y = $y + $i4.Height + 8
  [void](Txt $c2 $y $cw 50 'The quote shows the premium, what is needed before cover, and how the figure was reached.' 18 $mute $false 'Quote caption' 1)
  $y = $y + 74
  [void](Txt $c2 $y $cw 32 'Built with' 22 $maroon $true 'Tech title')
  $y = $y + 36
  $chips = @('Python standard library', 'HTML, CSS, JavaScript', 'SQLite', 'HMAC-SHA256', 'TLS')
  $cx = $c2; $cy = $y
  foreach ($q in $chips) {
    $c = Box $cx $cy 100 38 $white "Chip $q" 0.5
    $c.Line.Visible = -1; $c.Line.ForeColor.RGB = 0xBFBFBF; $c.Line.Weight = 1
    $tt = $c.TextFrame.TextRange; $tt.Text = $q; $tt.Font.Name = 'Times New Roman'; $tt.Font.Size = 17; $tt.Font.Color.RGB = $ink; $c.TextFrame.WordWrap = 0; $c.TextFrame.MarginLeft = 0; $c.TextFrame.MarginRight = 0
    $cwid = [double]$tt.BoundWidth + 30
    if ($cx + $cwid -gt $c2 + $cw) { $cx = $c2; $cy = $cy + 46 }
    $c.Width = [single]$cwid; $c.Left = [single]$cx; $c.Top = [single]$cy
    $cx = $cx + $cwid + 8
  }

  # ---------- column 3: results, future work, references
  $y = Section $c3 $top $cw 'Results'
  $sh = $null
  foreach ($z in 1..15) { try { $sh = $s.Shapes.AddChart2(-1, 51, [single]$c3, [single]$y, [single]$cw, [single]390, $true); break } catch { Start-Sleep -Seconds 1 } }
  $sh.Name = 'Premium by evidence chart'; $ch = $sh.Chart
  $ch.ChartData.Activate(); $wb = $null; foreach ($z in 1..20) { try { $wb = $ch.ChartData.Workbook } catch {}; if ($wb) { break }; Start-Sleep -Milliseconds 300 }
  $wb.Application.Visible = $false; $ws = $wb.Worksheets.Item(1); [void]$ws.Range('A1:F12').ClearContents()
  $ws.Range('A1').Value2 = 'Evidence'; $ws.Range('B1').Value2 = 'Technical premium'
  $ws.Range('A2').Value2 = 'No evidence'; $ws.Range('B2').Value2 = 248235
  $ws.Range('A3').Value2 = 'All stated'; $ws.Range('B3').Value2 = 55342
  $ws.Range('A4').Value2 = 'All verified'; $ws.Range('B4').Value2 = 46487
  $ch.SetSourceData("='$($ws.Name)'!`$A`$1:`$B`$4"); $wb.Close(); Start-Sleep -Seconds 2
  $ch.HasTitle = $true; $ch.ChartTitle.Text = (U 'Technical premium for a reference firm ({rs})'); $ch.ChartTitle.Font.Size = 22; $ch.ChartTitle.Font.Bold = $true; $ch.ChartTitle.Font.Name = 'Times New Roman'; $ch.ChartTitle.Font.Color = $navy
  $ch.HasLegend = $false
  $se = $ch.SeriesCollection(1); $se.Format.Fill.ForeColor.RGB = $navy; $se.Points(1).Format.Fill.ForeColor.RGB = $maroon
  $se.HasDataLabels = $true; $dl = $se.DataLabels(); $dl.NumberFormat = (U '"{rs}"#,##,##0'); $dl.Font.Size = 20; $dl.Font.Name = 'Times New Roman'; $dl.Font.Bold = $true
  $ch.ChartGroups(1).GapWidth = 60
  $ax = $ch.Axes(1); $ax.TickLabels.Font.Size = 20; $ax.TickLabels.Font.Name = 'Times New Roman'
  $ch.Axes(2).HasMajorGridlines = $false; $ch.Axes(2).MaximumScale = 290000; $ch.Axes(2).Delete()
  $y = $y + 405
  $stats = @(@('224 / 224', 'automated tests pass (65 platform, 158 agent and collector, 1 end to end)'), @("{rs}32,421", 'saved by verifying privileged access alone (worked example)'), @('1.38% vs 1.48%', 'modelled peril frequency vs published (1.47% with other claims)'), @('Under 16%', 'largest premium change from any one assumption'))
  $tw = ($cw - 20) / 2; $i = 0
  foreach ($q in $stats) {
    $tx = $c3 + ($i % 2) * ($tw + 20); $ty = $y + [math]::Floor($i / 2) * 156; $i++
    [void](Box $tx $ty $tw 142 $grey "Result tile $i" 0.08)
    [void](Txt ($tx + 8) ($ty + 12) ($tw - 16) 44 $q[0] 32 $maroon $true "Result stat $i" 2)
    [void](Txt ($tx + 12) ($ty + 62) ($tw - 24) 76 $q[1] 17 $ink $false "Result label $i" 2)
  }
  $y = $y + 336
  [void](Txt $c3 $y $cw 32 'Live demonstration (SIMULATED endpoints)' 22 $maroon $true 'Demo title')
  $y = $y + 38
  $i3 = Pic 'monitoring_screen.png' $c3 $y $cw 'Collector view of the bound policy with the EDR warranty in grace'
  $y = $y + $i3.Height + 8
  [void](Txt $c3 $y $cw 84 'EDR stopped on 1 of 4 machines: the warranty moved to IN_GRACE within seconds, then BREACHED, then back to MET after the fix. The bound premium stayed at {rs}94,135, and a re-price was refused.' 18 $ink $false 'Demo caption' 4)
  $y = $y + 112
  $y = Section $c3 $y $cw 'Future Work'
  $fw = Txt $c3 $y $cw 250 ("A sturdier, more autonomous agent that tracks current threats such as zero-days, staying read-only`rMore controls monitored, with identity-provider connectors to verify MFA`rBetter loss models from data, including Indian claims`rPolicy conditions and limits on the platform, so coverage and payouts appear on the dashboard`rmacOS and wider OS support") 19 $ink $false 'Future list' 1
  $r = $fw.TextFrame.TextRange; $r.ParagraphFormat.Bullet.Visible = -1; $r.ParagraphFormat.Bullet.Character = 8226; $r.ParagraphFormat.SpaceAfter = 4
  $fw.TextFrame.Ruler.Levels(1).FirstMargin = 0; $fw.TextFrame.Ruler.Levels(1).LeftMargin = 18
  $y = $y + [double]$r.BoundHeight + 30
  $y = Section $c3 $y $cw 'References'
  $rf = Txt $c3 $y $cw 220 ("[1] Coalition, 2025 Cyber Claims Report, 2025.`
[2] NetDiligence, Cyber Claims Study 2025, 2025.`
[3] Marsh McLennan, Using Data to Prioritize Cybersecurity Investments, 2023.`
[4] H. B{u}hlmann, Experience rating and credibility, ASTIN Bulletin, 1967.`
[5] S. Romanosky et al., Content analysis of cyber insurance policies, J. Cybersecurity, 2019.`
[6] D. Woods et al., Mapping the coverage of security controls in proposal forms, JISA, 2017.") 16 $ink $false 'References list' 1
  $rf.TextFrame.TextRange.ParagraphFormat.SpaceAfter = 3

  # ---------- footer
  [void](Box 0 ($Hgt - 70) $W 70 $red 'Footer band' 0 1)
  $ft = Txt 50 ($Hgt - 70) ($W - 100) 70 'Source code: github.com/harxhhr/beretta-cyber-insurance     {dot}     Mukesh Patel School of Technology Management & Engineering, SVKM{ap}s NMIMS, Mumbai' 20 $white $false 'Footer text' 2
  $ft.TextFrame.VerticalAnchor = 3

  # report the lowest content edge so the layout can be checked
  $low = 0; foreach ($x in $s.Shapes) { if ($x.Top -lt ($Hgt - 80)) { $e = $x.Top + $x.Height; if ($e -gt $low) { $low = $e; $who = $x.Name } } }
  "lowest content: $([math]::Round($low)) ($who); footer starts at $($Hgt - 70)"
  $pres.SaveAs($pptx)
  $pres.SaveAs($pdf, 32)
  $s.Export($png, 'PNG', 1684, 2384)
  "wrote $pptx"; "wrote $pdf"
} finally {
  $pres.Saved = -1; $pres.Close()
}
