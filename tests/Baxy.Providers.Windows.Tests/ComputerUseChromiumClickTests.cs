using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// fable/cu-v3-clic-chromium. Measured live, behind the person's window, on a WebView2 messaging client (its search
/// field an Edit with a writable value and no other pattern, its filter tabs TabItems with SelectionItem) and on a
/// launcher drawn by Slate (no accessible tree):
/// - LegacyIAccessible had no default action on the field; SelectionItem.Select on a tab brought the window to the
///   front; a press posted to the Chrome_RenderWidgetHostHWND in client coordinates focused the field and selected the
///   tab, with neither the front nor the cursor moved.
/// - Once the client's frame was activated by an opening it lay above its content window in the Z order: the view
///   stayed on the frame (eight elements, no field) and every press there needed the pointer.
/// - A press posted to the Slate window changed nothing (the pointer stays its way).
/// The render surface is told by its window class (a surface type), never by an application's name. Review of the
/// branch: a press is posted only where the page's own hit test answers the element (or, at a point, a node naming the
/// label), only before SelectionItem among the patterns, and never to a field that already had the focus. Twins of
/// those views and their counter-cases; no window is read or touched (the page's hit test is described).
/// </summary>
[TestFixture]
public sealed class ComputerUseChromiumClickTests
{
    [Test]
    public void OnARenderSurfaceThePostedPressComesFirstOnlyWhereItWasMeasured()
    {
        string answer = RunPlanner("""
            [
              {"select":true,"kind":"TabItem","render":true},
              {"kind":"Edit","value":true,"render":true},
              {"invoke":true,"kind":"Button","render":true},
              {"toggle":true,"kind":"CheckBox","render":true},
              {"expand":true,"kind":"ComboBox","render":true},
              {"kind":"Group","render":true},
              {"invoke":true,"kind":"Edit","value":true,"render":true},
              {"select":true,"kind":"TabItem"},
              {"kind":"Edit","value":true},
              {"kind":"Button","classic":true}
            ]
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "render select",                  // the measured tab: Select took the front; its pattern only if no press went
            "target render legacy pointer",   // the measured search field: designated in front, else focused by a press
            "invoke",                         // review finding 2: Invoke, Toggle and Expand were never measured taking
            "toggle",                         // the front and reach the exact element: they stay alone, as before
            "expand",
            "legacy render pointer",          // no pattern: the default action (the exact element) before the press
            "invoke",                         // a field with a pattern keeps it: it is never clicked blind
            "select",                         // counter-case: without a render surface nothing changes
            "target legacy pointer",
            "legacy message pointer",
        }));
    }

    [Test]
    public void TheSearchFieldBehindIsFocusedByAPressOnlyWhereThePageAnswersTheField()
    {
        // The measured field: 174,142 317×25 «Buscar»; the page's hit test describes what the page has at its point.
        string answer = RunWorkerScript("""
            function Get-ClickFacts($el){ return @{ invoke=$false; select=$false; toggle=$false; expand=$false; kind='Edit'; value=$true; classic=$false } }
            function New-WebField([uint32]$process,[bool]$takes,[bool]$before){
              $calls=@{ focus=0; takes=$takes; before=$before }
              $current=New-Object psobject -Property @{ NativeWindowHandle=0; ProcessId=$process; Name='Buscar'; Calls=$calls }
              $current | Add-Member -MemberType ScriptProperty -Name HasKeyboardFocus -Value { [bool]$this.Calls.before -or ([bool]$this.Calls.takes -and [BaxyUiaWorkerNative]::Posted.Count -gt 0) }
              $current | Add-Member -MemberType NoteProperty -Name BoundingRectangle -Value (New-Object System.Windows.Rect(174,142,317,25))
              $el=New-Object psobject -Property @{ Current=$current; Calls=$calls }
              $el | Add-Member -MemberType ScriptMethod -Name SetFocus -Value { $this.Calls.focus++ }
              $el | Add-Member -MemberType ScriptMethod -Name GetRuntimeId -Value { return [int[]]@(42,7) }
              $el | Add-Member -MemberType ScriptMethod -Name GetClickablePoint -Value { return (New-Object System.Windows.Point(332,154)) }
              return $el
            }
            $field=@([BaxyUiaWorkerNative]::Node('',180,147,300,15,42),[BaxyUiaWorkerNative]::Node('Buscar',174,142,317,25,42),[BaxyUiaWorkerNative]::Node('',0,0,1256,783,15))
            $list=@([BaxyUiaWorkerNative]::Node('Todos los chats',150,120,400,300,33),[BaxyUiaWorkerNative]::Node('',0,0,1256,783,15))
            $twin=@([BaxyUiaWorkerNative]::Node('Buscar contactos',174,142,317,25,42))
            $script:InFront=$false
            $script:RenderHosts=@([IntPtr]66898)
            $answers=foreach($case in @(
                @{render=$true;process=11216;element=11216;takes=$true;posts=$true;page=$field},
                @{render=$true;process=11216;element=13884;takes=$true;posts=$true;page=$field},
                @{render=$true;process=11216;element=11216;takes=$false;posts=$true;page=$field},
                @{render=$true;process=11216;element=11216;takes=$true;posts=$false;page=$field},
                @{render=$false;process=0;element=11216;takes=$true;posts=$true;page=$field},
                @{render=$true;process=11216;element=11216;takes=$true;posts=$true;page=$list},
                @{render=$true;process=11216;element=11216;takes=$true;posts=$true;page=$twin},
                @{render=$true;process=11216;element=11216;takes=$true;posts=$true;page=@()},
                @{render=$true;process=11216;element=11216;takes=$true;posts=$true;page=$field;dpi=$false},
                @{render=$true;process=11216;element=11216;takes=$true;posts=$true;page=$field;before=$true})){
              [BaxyUiaWorkerNative]::Posted.Clear()
              [BaxyUiaWorkerNative]::Render=$case.render
              [BaxyUiaWorkerNative]::RenderProcess=[uint32]$case.process
              [BaxyUiaWorkerNative]::Posts=$case.posts
              [BaxyUiaWorkerNative]::Dpi=($case.dpi -ne $false)
              [BaxyUiaWorkerNative]::Page=[BaxyUiaWorkerNative+RenderHit[]]@($case.page)
              $el=New-WebField ([uint32]$case.element) $case.takes ([bool]$case.before)
              $done=Invoke-NamedControl $el ([IntPtr]132298)
              ([string]$done.method)+'|'+([string]$done.via)+'|'+([string]$done.renderStep)+'|'+$el.Calls.focus+'|'+(@([BaxyUiaWorkerNative]::Posted) -join ';')
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);

        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            // Behind, never SetFocus (a theft); the page answers the field at its point: the press posted to the surface
            // of its own process, the hosts being the bound window and the family's content window.
            "target|render||0|2@332:154/11216",
            // Counter-case: an element of another process (the frame's own) is never pressed through the content.
            "pointer|||0|",
            // Counter-case: posted but the field did not take the focus: no destination, the next way says why.
            "pointer||unfocused|0|2@332:154/11216",
            // Counter-case: the press could not be sent: the next way.
            "pointer||post-failed|0|2@332:154/11216",
            // Counter-case: no render surface: as before.
            "pointer|||0|",
            // Review finding 1: something else is at the point (a list drawn over the field): nothing is posted.
            "pointer||other|0|",
            // A control of the same box with another name is not the field either.
            "pointer||other|0|",
            // The page answers nothing at the point: nothing is posted blind.
            "pointer||nohit|0|",
            // A surface Windows scales: a posted point would land elsewhere.
            "pointer||dpi|0|",
            // Review finding 5: a field that already had the focus is already the destination; nothing is pressed (its
            // focus would prove nothing, and the press would put the caret in the middle of its text).
            "target|prefocused||0|",
        }));
    }

    [Test]
    public void ATabOnARenderSurfaceIsPressedByThePostOnlyWhenThePageAnswersTheTab()
    {
        string answer = RunWorkerScript("""
            function Get-ClickFacts($el){ return @{ invoke=$false; select=$true; toggle=$false; expand=$false; kind='TabItem'; value=$false; classic=$false } }
            function New-Tab(){
              $current=New-Object psobject -Property @{ NativeWindowHandle=0; ProcessId=[uint32]11216; Name='Todos' }
              $current | Add-Member -MemberType NoteProperty -Name BoundingRectangle -Value (New-Object System.Windows.Rect(205,192,122,40))
              $calls=@{ pattern=0 }
              $el=New-Object psobject -Property @{ Current=$current; Calls=$calls }
              $el | Add-Member -MemberType ScriptMethod -Name GetClickablePoint -Value { return (New-Object System.Windows.Point(266,212)) }
              $el | Add-Member -MemberType ScriptMethod -Name TryGetCurrentPattern -Value { param($id,$out) $this.Calls.pattern++; return $false }
              return $el
            }
            [BaxyUiaWorkerNative]::Render=$true
            [BaxyUiaWorkerNative]::RenderProcess=[uint32]11216
            [BaxyUiaWorkerNative]::Posts=$true
            $answers=foreach($page in @(
                @(@([BaxyUiaWorkerNative]::Node('Todos',230,202,70,20,41),[BaxyUiaWorkerNative]::Node('Todos',205,192,122,40,37))),
                @(@([BaxyUiaWorkerNative]::Node('Sin leer',200,180,300,200,33))))){
              [BaxyUiaWorkerNative]::Posted.Clear()
              [BaxyUiaWorkerNative]::Page=[BaxyUiaWorkerNative+RenderHit[]]@($page)
              $el=New-Tab
              $done=$null
              try { $done=Invoke-NamedControl $el ([IntPtr]66898) } catch { $done=@{ method='select-tried' } }
              ([string]$done.method)+'|'+$el.Calls.pattern+'|'+(@([BaxyUiaWorkerNative]::Posted) -join ';')
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            // Only the bound window is a host here (no family content handed over); its text inside the tab was hit.
            "render|0|1@266:212/11216",
            // Review finding 1: another thing at the point (a pop-up list over the tab, the page under it answering):
            // nothing posted, the tab's own pattern is the way.
            "select-tried|1|",
        }));
    }

    // Review of B3, finding 2: the worker's own double click goes only to an item, a tab or a document; on a button, a
    // link, a menu's item, a split button or a written text it would be two activations, and nothing is posted.
    [Test]
    public void ADoubleClickIsPostedOnlyOnAnItemATabOrADocument()
    {
        string answer = RunWorkerScript("""
            foreach($name in @('Invoke-MannerControl','Get-HolderWindow')){
              $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name },$true))
              . ([scriptblock]::Create($found[0].Extent.Text))
            }
            function New-Control($type){
              $current=New-Object psobject -Property @{ NativeWindowHandle=0; ProcessId=[uint32]11216; Name='Fotos'; ControlType=$type; FrameworkId='Chrome' }
              $current | Add-Member -MemberType NoteProperty -Name BoundingRectangle -Value (New-Object System.Windows.Rect(205,192,122,40))
              $el=New-Object psobject -Property @{ Current=$current }
              $el | Add-Member -MemberType ScriptMethod -Name GetClickablePoint -Value { return (New-Object System.Windows.Point(266,212)) }
              return $el
            }
            [BaxyUiaWorkerNative]::Render=$true
            [BaxyUiaWorkerNative]::RenderProcess=[uint32]11216
            [BaxyUiaWorkerNative]::Posts=$true
            [BaxyUiaWorkerNative]::Page=[BaxyUiaWorkerNative+RenderHit[]]@([BaxyUiaWorkerNative]::Node('Fotos',205,192,122,40,34))
            $CT=[System.Windows.Automation.ControlType]
            $answers=foreach($type in @($CT::ListItem,$CT::TabItem,$CT::Button,$CT::Hyperlink,$CT::MenuItem,$CT::SplitButton,$CT::Text)){
              [BaxyUiaWorkerNative]::Posted.Clear()
              $done=Invoke-MannerControl (New-Control $type) $null ([IntPtr]66898) 'double'
              ([string]$done.method)+'|'+([string]$done.error)+'|'+(@([BaxyUiaWorkerNative]::Posted) -join ';')
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "render||double 1@266:212/11216",            // an item of a list: opened by its double click
            "render||double 1@266:212/11216",            // a tab: chosen twice
            "|visible_control_no_double_click|",         // a button: two presses, nothing posted
            "|visible_control_no_double_click|",         // a link: two activations
            "|visible_control_no_double_click|",         // a menu's item
            "|visible_control_no_double_click|",         // a split button
            "|visible_control_no_double_click|",         // a written text of a page may be a link drawn as text
        }));
    }

    [Test]
    public void APressAtAPointIsPostedOnlyWhenWhatThePageHasThereNamesTheLabel()
    {
        // Review findings 3 and 4: the «at» press has no element; what the page has at the point when it is pressed must
        // name the label read on the screen (the node hit or one of its three ancestors, never the document).
        string answer = RunWorkerScript("""
            [BaxyUiaWorkerNative]::Render=$true
            [BaxyUiaWorkerNative]::RenderProcess=[uint32]0
            [BaxyUiaWorkerNative]::Posts=$true
            $doc=[BaxyUiaWorkerNative]::Node('Juan Pérez - Chats',0,0,1256,783,15)
            $answers=foreach($page in @(
                @(@([BaxyUiaWorkerNative]::Node('',300,200,80,16,41),[BaxyUiaWorkerNative]::Node('Juan Pérez 12:30 Hola',280,190,400,60,34),$doc)),
                @(@([BaxyUiaWorkerNative]::Node('María Soto 12:31 Ya',280,190,400,60,34),$doc)),
                @(@([BaxyUiaWorkerNative]::Node('',300,200,80,16,41),$doc)),
                @(@([BaxyUiaWorkerNative]::Node('',1,1,1,1,41),[BaxyUiaWorkerNative]::Node('',1,1,2,2,20),[BaxyUiaWorkerNative]::Node('',1,1,3,3,20),[BaxyUiaWorkerNative]::Node('',1,1,4,4,20),[BaxyUiaWorkerNative]::Node('Juan Pérez',0,0,800,600,20),$doc)))){
              [BaxyUiaWorkerNative]::Posted.Clear()
              [BaxyUiaWorkerNative]::Page=[BaxyUiaWorkerNative+RenderHit[]]@($page)
              $step=Send-RenderPress (Get-RenderHosts ([IntPtr]132298)) 320 208 ([uint32]0) $null @('Juan Pérez')
              $step+'|'+(@([BaxyUiaWorkerNative]::Posted) -join ';')
            }
            [Console]::Out.Write((@($answers) -join ','))
            """);
        Assert.That(answer.Split(','), Is.EqualTo(new[]
        {
            "posted|1@320:208/0",   // the chat read on the screen is the one at the point when it is pressed
            "other|",               // the list reordered meanwhile: another chat is there, nothing is pressed
            "other|",               // only the document names it: the page's title, not the control
            "other|",               // named only by a node too far up
        }));
    }

    [Test]
    public void APressPostedAtAPointIsAPressWhoseProofIsTheSurface()
    {
        PointPressed render = WindowsVisibleControlAdapter.PointPressFrom(JsonDocument.Parse(
            """{"ok":false,"pending":true,"effectObserved":true,"error":"visible_button_postread_pending","method":"render","cascadeStage":"point"}""").RootElement);
        PointPressed none = WindowsVisibleControlAdapter.PointPressFrom(JsonDocument.Parse(
            """{"ok":false,"effectObserved":false,"error":"visible_point_no_pattern","renderStep":"other"}""").RootElement);
        Assert.Multiple(() =>
        {
            Assert.That(render.Outcome, Is.EqualTo(PointPressOutcome.Pressed));
            Assert.That(render.Method, Is.EqualTo("render"));
            Assert.That(render.Focused, Is.False, "a posted press never makes a field the text's destination by itself");
            Assert.That(none.Outcome, Is.EqualTo(PointPressOutcome.NothingThere), "counter-case: nothing posted, the pointer decides");
        });
    }

    [Test]
    public void TheContentWindowUnderAnActivatedFrameIsAHostButNotTheViewsSurface()
    {
        // The measured client: frame 0,0,1265,792; its WebView2 content window 9,1,1256,783 (tool, no-activate),
        // under the frame once the frame was activated.
        (int, int, int, int) frame = (0, 0, 1265, 792);
        VisibleControlSurface.FamilyWindow under = new(66898, 11216, 9, 1, 1256, 783, AboveFrame: false);
        VisibleControlSurface.FamilyWindow over = under with { AboveFrame = true };
        VisibleControlSurface.FamilyWindow browser = under with { Window = 80, ApplicationWindow = true };
        VisibleControlSurface.FamilyWindow popup = new(81, 11216, 100, 100, 500, 400, AboveFrame: true);
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ContentWindowsOf(frame, [under]), Is.EqualTo(new nint[] { 66898 }));
            Assert.That(VisibleControlSurface.ContentWindowsOf(frame, [over]), Is.EqualTo(new nint[] { 66898 }));
            // The view's surface keeps its rule: under the frame it is not chosen.
            Assert.That(VisibleControlSurface.ChooseFamilySurface(frame, [under]), Is.EqualTo((nint)0));
            // Counter-cases: a window of its own and a window that does not cover the frame are never hosts.
            Assert.That(VisibleControlSurface.ContentWindowsOf(frame, [browser, popup]), Is.Empty);
        });
    }

    [Test]
    public void TheWorkerIsToldTheFamilysContentWindowsOnlyWhenThereAreSome()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            """{"ok":false,"effectObserved":false,"error":"visible_point_no_pattern"}""");
        int enumerated = 0;
        using var withHosts = new WindowsVisibleControlAdapter(
            worker, null, null, elevated: _ => false, renderHosts: window =>
            {
                enumerated++;
                return window == 132298 ? [66898] : [];
            });
        _ = withHosts.PressAtAsync(132298, 332, 154, "Buscar", CancellationToken.None).AsTask().Result;
        _ = withHosts.PressAtAsync(132298, 340, 160, "Buscar", CancellationToken.None).AsTask().Result;
        _ = withHosts.PressAtAsync(500, 332, 154, "Buscar", CancellationToken.None).AsTask().Result;
        using JsonDocument first = JsonDocument.Parse(worker.Commands[0]);
        using JsonDocument again = JsonDocument.Parse(worker.Commands[1]);
        using JsonDocument other = JsonDocument.Parse(worker.Commands[2]);
        Assert.Multiple(() =>
        {
            Assert.That(first.RootElement.GetProperty("hosts").EnumerateArray().Select(host => host.GetInt64()),
                Is.EqualTo(new long[] { 66898 }));
            Assert.That(again.RootElement.GetProperty("hosts").EnumerateArray().Select(host => host.GetInt64()),
                Is.EqualTo(new long[] { 66898 }));
            Assert.That(other.RootElement.TryGetProperty("hosts", out _), Is.False, "counter-case: no family content");
            // Review finding 8: the family is enumerated once per window within a cascade, not on every look.
            Assert.That(enumerated, Is.EqualTo(2));
        });
    }

    [Test]
    public void TheRenderPressNeverUsesThePointerNorTheFrontAndIsCheckedBeforeItIsPosted()
    {
        string worker = WorkerPath();
        string script = File.ReadAllText(worker, Encoding.UTF8);
        int start = script.IndexOf("public static bool PostAt(", StringComparison.Ordinal);
        int end = script.IndexOf("\n  }\n", start, StringComparison.Ordinal);
        Assert.That(start, Is.GreaterThan(0));
        string body = script[start..end];
        // Goal v3 B3 moved the posting itself into PostPress (shared with the double click): PostAt is read with it.
        int press = script.IndexOf("private static bool PostPress(", StringComparison.Ordinal);
        Assert.That(body, Does.Contain("PostPress(target,x,y,false)"));
        Assert.That(press, Is.GreaterThan(0));
        body += script[press..script.IndexOf("\n  }\n", press, StringComparison.Ordinal)];
        int send = script.IndexOf("function Send-RenderPress(", StringComparison.Ordinal);
        Assert.That(send, Is.GreaterThan(0));
        string sender = script[send..script.IndexOf("\n}\n", send, StringComparison.Ordinal)];
        Assert.Multiple(() =>
        {
            Assert.That(body, Does.Contain("PostMessage(target,0x0201"));
            Assert.That(body, Does.Not.Contain("SendInput"));
            Assert.That(body, Does.Not.Contain("SetForegroundWindow"));
            Assert.That(body, Does.Not.Contain("SetCursorPos"));
            // The surface is told by its class, never by an application; the class is data handed over by the host
            // (fable/cu-v3-worker-sin-nombres), so the worker's source spells none.
            Assert.That(script, Does.Contain("public static string[] RenderClasses = new string[0];"));
            Assert.That(script, Does.Not.Contain("Chrome_RenderWidgetHostHWND"));
            // The only call that posts is behind the page's hit test.
            Assert.That(sender.IndexOf("HitChain(", StringComparison.Ordinal),
                Is.LessThan(sender.IndexOf("PostAt(", StringComparison.Ordinal)));
            Assert.That(script.Split("::PostAt(").Length - 1, Is.EqualTo(1), "PostAt is called from Send-RenderPress only");
        });
    }

    // fable/cu-v3-worker-sin-nombres: the render surface's window class is data (render_surface_classes.v1.json,
    // embedded), and the host hands it to the worker in its first «ping». Counter-cases: a blank or repeated entry is
    // dropped, and data without classes names no surface.
    [Test]
    public void TheRenderSurfaceClassComesFromTheDataAndTheHostHandsItOver()
    {
        using var host = new UiaWorkerHost(Path.Combine(Path.GetTempPath(), "baxy-no-worker.ps1"));
        using JsonDocument hello = JsonDocument.Parse(host.HelloJson());
        using var data = new MemoryStream(Encoding.UTF8.GetBytes(
            """{"classes":[" SurfaceA ","","SurfaceA",7,"SurfaceB"]}"""));
        using var empty = new MemoryStream(Encoding.UTF8.GetBytes("""{"version":1}"""));

        Assert.Multiple(() =>
        {
            Assert.That(RenderSurfaceClasses.All, Is.EqualTo(new[] { "Chrome_RenderWidgetHostHWND" }));
            Assert.That(host.RenderClasses, Is.EqualTo(RenderSurfaceClasses.All));
            Assert.That(hello.RootElement.GetProperty("cmd").GetString(), Is.EqualTo("ping"));
            Assert.That(hello.RootElement.GetProperty("renderClasses").EnumerateArray().Select(item => item.GetString()),
                Is.EqualTo(RenderSurfaceClasses.All));
            Assert.That(RenderSurfaceClasses.Parse(data), Is.EqualTo(new[] { "SurfaceA", "SurfaceB" }));
            Assert.That(RenderSurfaceClasses.Parse(empty), Is.Empty);
        });
    }

    // The live worker (no window read or touched) holds the classes its host handed over: RenderAt and HostsRender
    // match through IsRenderClass, a later «ping» without classes keeps them, and a class not handed over matches nothing.
    [Test]
    public async Task TheWorkerTellsARenderSurfaceByTheClassesItsHostHandsOver()
    {
        string worker = WorkerPath();
        using var host = new UiaWorkerHost(worker) { RenderClasses = ["BaxyTestSurface"] };
        const string probe = """
            $known=[BaxyUiaWorkerNative]::IsRenderClass($args[0])
            [pscustomobject]@{ ok=$true; value=[string]$known } | ConvertTo-Json -Compress
            """;

        using JsonDocument? ping = await host.SendAsync("{\"cmd\":\"ping\"}", TimeSpan.FromSeconds(30), CancellationToken.None);
        using JsonDocument? handed = await host.SendAsync(
            "{\"cmd\":\"script\",\"script\":" + JsonSerializer.Serialize(probe) + ",\"args\":[\"BaxyTestSurface\"]}",
            TimeSpan.FromSeconds(30), CancellationToken.None);
        using JsonDocument? other = await host.SendAsync(
            "{\"cmd\":\"script\",\"script\":" + JsonSerializer.Serialize(probe) + ",\"args\":[\"Chrome_RenderWidgetHostHWND\"]}",
            TimeSpan.FromSeconds(30), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(ping?.RootElement.GetProperty("renderClasses").EnumerateArray().Select(item => item.GetString()),
                Is.EqualTo(new[] { "BaxyTestSurface" }), "a ping without classes keeps the host's");
            Assert.That(handed?.RootElement.GetProperty("line").GetString(), Does.Contain("\"value\":\"True\""));
            Assert.That(other?.RootElement.GetProperty("line").GetString(), Does.Contain("\"value\":\"False\""),
                "counter-case: a class the host did not hand over is no render surface");
        });
    }

    private static string WorkerPath()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        return worker;
    }

    private static string RunPlanner(string cases)
    {
        string casesFile = Path.Combine(Path.GetTempPath(), "baxy-render-" + Guid.NewGuid().ToString("N") + ".json");
        File.WriteAllText(casesFile, cases, new UTF8Encoding(false));
        try
        {
            return RunPowerShell("""
                $ErrorActionPreference='Stop'
                $tokens=$null;$errors=$null
                $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_CLICK_WORKER,[ref]$tokens,[ref]$errors)
                if($errors.Count -gt 0){ throw 'worker does not parse' }
                $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Select-ClickMethods' },$true))
                . ([scriptblock]::Create($found[0].Extent.Text))
                $cases=[System.IO.File]::ReadAllText($env:BAXY_CLICK_CASES,[System.Text.Encoding]::UTF8) | ConvertFrom-Json
                $answers=foreach($case in $cases){
                  $facts=@{ invoke=[bool]$case.invoke; select=[bool]$case.select; toggle=[bool]$case.toggle; expand=[bool]$case.expand; kind=[string]$case.kind; value=[bool]$case.value; classic=[bool]$case.classic; render=[bool]$case.render }
                  (@(Select-ClickMethods $facts) -join ' ')
                }
                [Console]::Out.Write((@($answers) -join ','))
                """, ("BAXY_CLICK_WORKER", WorkerPath()), ("BAXY_CLICK_CASES", casesFile));
        }
        finally
        {
            File.Delete(casesFile);
        }
    }

    // The worker's own click functions and its list of pattern ways, taken by their syntax tree, over described controls
    // and stand-ins for the native calls: the page's hit test is described, the render surface recorded, never sent.
    private static string RunWorkerScript(string body) => RunPowerShell("""
        $ErrorActionPreference='Stop'
        Add-Type -AssemblyName UIAutomationClient
        Add-Type -AssemblyName UIAutomationTypes
        Add-Type -AssemblyName WindowsBase
        Add-Type -TypeDefinition @'
        using System;
        public static class BaxyUiaWorkerNative {
          public class RenderHit { public string Name = ""; public int Left; public int Top; public int Width; public int Height; public int Role; }
          public static string LegacyStep = "";
          public static string WindowDefault(IntPtr hwnd) { LegacyStep = "window"; return ""; }
          public static string LegacyDefault(IntPtr top, int[] id) { LegacyStep = "none"; return ""; }
          public static bool PostClick(IntPtr top, int x, int y) { return false; }
          public static bool PostClick(IntPtr top, int x, int y, IntPtr holder) { return false; }
          public static bool Render = false;
          public static bool Posts = true;
          public static bool Dpi = true;
          public static uint RenderProcess = 0;
          public static RenderHit[] Page = new RenderHit[0];
          public static System.Collections.Generic.List<string> Posted = new System.Collections.Generic.List<string>();
          private static string asked = "";
          public static RenderHit Node(string name, int left, int top, int width, int height, int role) {
            var node = new RenderHit(); node.Name = name; node.Left = left; node.Top = top; node.Width = width; node.Height = height; node.Role = role; return node;
          }
          public static bool HostsRender(IntPtr[] hosts, uint process) { return Render && (process == 0 || process == RenderProcess); }
          public static IntPtr RenderAt(IntPtr[] hosts, int x, int y, uint process) {
            if(!HostsRender(hosts, process)) return IntPtr.Zero;
            asked = hosts.Length + "@" + x + ":" + y + "/" + process; return (IntPtr)7;
          }
          public static bool SameDpi(IntPtr surface) { return Dpi; }
          public static RenderHit[] HitChain(IntPtr surface, int x, int y) { return Page; }
          public static bool PostAt(IntPtr surface, int x, int y) { Posted.Add(asked); return Posts; }
          public static bool PostDoubleAt(IntPtr surface, int x, int y) { Posted.Add("double " + asked); return Posts; }
          public static bool PostDoubleClick(IntPtr top, int x, int y, IntPtr holder) { Posted.Add("classic " + holder); return Posts; }
        }
        '@
        $tokens=$null;$errors=$null
        $ast=[System.Management.Automation.Language.Parser]::ParseFile($env:BAXY_CLICK_WORKER,[ref]$tokens,[ref]$errors)
        if($errors.Count -gt 0){ throw 'worker does not parse' }
        foreach($name in @('Select-ClickMethods','Invoke-NamedControl','Select-Element','Test-PlaceMoved','Get-SteadyPlace','Test-PlaceTooDear','Wait-PlaceMoved','Get-PressPoint','Get-CurrentRect','Get-RenderHosts','Send-RenderPress','Test-HitIsElement','Test-HitNamesLabel','Get-Folded','Test-NameHolds')){
          $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name },$true))
          if($found.Count -ne 1){ throw ('function missing: '+$name) }
          . ([scriptblock]::Create($found[0].Extent.Text))
        }
        # Review finding 6: the worker's own list of pattern ways, not a copy of it.
        $ways=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$script:PatternMethods' },$true))
        if($ways.Count -ne 1){ throw 'PatternMethods missing' }
        . ([scriptblock]::Create($ways[0].Extent.Text))
        if(-not ($script:PatternMethods -contains 'render')){ throw 'render is not a pattern way' }
        # Review 1 of r24b (B2): every choice of an item reads the place; here the window holds still.
        function Get-PlaceTrace([IntPtr]$top){ return @{ title=''; items=@{}; volatile=@{} } }
        $script:RenderHosts=@()
        $script:InFront=$false
        function Test-InFront([IntPtr]$top){ return $script:InFront }

        """ + body, ("BAXY_CLICK_WORKER", WorkerPath()));

    private static string RunPowerShell(string script, params (string Name, string Value)[] environment)
    {
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
        foreach ((string name, string value) in environment)
            start.Environment[name] = value;
        start.StandardOutputEncoding = Encoding.UTF8;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return output.Trim();
    }
}
