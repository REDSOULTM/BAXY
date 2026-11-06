using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso-108, measured on the desktop with a WPF list of its own that never takes the front: a row cut by the bottom of its
/// list and what the real worker's reveal does with it, with the list's own scroll offset as the oracle, not the worker's
/// word. Never runs in a suite: Explicit and BAXY_RECIBOS_LIVE=1. Its window is closed by its exact process.
/// </summary>
[TestFixture]
[Explicit("Opens a window on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class RecibosUso108LiveCheck
{
    // Rows of 20 px in a list of 150: «Fila 08» is half out. The list writes its offset to the file named, on every change.
    private const string FormScript = """
        param([string]$Title,[string]$Offset)
        Add-Type -AssemblyName PresentationFramework
        $w=New-Object System.Windows.Window
        $w.Title=$Title; $w.Width=320; $w.Height=260; $w.WindowStartupLocation='Manual'; $w.Left=60; $w.Top=60; $w.ShowActivated=$false
        $list=New-Object System.Windows.Controls.ListBox
        $list.Height=150; $list.VerticalAlignment='Top'
        [System.Windows.Controls.VirtualizingPanel]::SetIsVirtualizing($list,$false)
        foreach($i in 1..30){
          $item=New-Object System.Windows.Controls.ListBoxItem
          $item.Content=('Fila {0:D2}' -f $i); $item.Height=20; $item.Padding='0'; $item.Margin='0'; $item.BorderThickness='0'
          [void]$list.Items.Add($item)
        }
        $w.Content=$list
        [IO.File]::WriteAllText($Offset,'0')
        $list.AddHandler([System.Windows.Controls.ScrollViewer]::ScrollChangedEvent,[System.Windows.Controls.ScrollChangedEventHandler]{ param($s,$e) [IO.File]::WriteAllText($Offset,[string]$e.VerticalOffset) })
        [void]$w.ShowDialog()
        """;

    [Test]
    public async Task ARowCutByItsListIsScrolledIntoSightByTheRealWorker()
    {
        if (Environment.GetEnvironmentVariable("BAXY_RECIBOS_LIVE") != "1")
            Assert.Ignore("BAXY_RECIBOS_LIVE=1 is needed to touch the desktop.");
        string folder = Path.Combine(Path.GetTempPath(), "baxy-recibos-live-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        string script = Path.Combine(folder, "form.ps1");
        string offset = Path.Combine(folder, "offset.txt");
        await File.WriteAllTextAsync(script, FormScript, new UTF8Encoding(false));
        string title = "BAXY prueba recibos " + Guid.NewGuid().ToString("N")[..6];
        var start = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true };
        foreach (string argument in new[] { "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", script, "-Title", title, "-Offset", offset })
            start.ArgumentList.Add(argument);
        using Process form = Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
        try
        {
            nint window = 0;
            for (int attempt = 0; attempt < 80 && window == 0; attempt++)
            {
                window = FindWindowW(null, title);
                if (window == 0)
                    await Task.Delay(250);
            }

            Assert.That(window, Is.Not.EqualTo((nint)0), "the window did not appear");
            await Task.Delay(800);
            double before = double.Parse(File.ReadAllText(offset), System.Globalization.CultureInfo.InvariantCulture);
            using var host = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using JsonDocument? shown = await host.SendAsync(
                $$"""{"cmd":"reveal","hwnd":{{window}},"aliases":["Fila 03"],"direction":"down","amount":4}""",
                TimeSpan.FromSeconds(20), CancellationToken.None);
            double afterShown = double.Parse(File.ReadAllText(offset), System.Globalization.CultureInfo.InvariantCulture);
            using JsonDocument? cut = await host.SendAsync(
                $$"""{"cmd":"reveal","hwnd":{{window}},"aliases":["Fila 08"],"direction":"down","amount":4}""",
                TimeSpan.FromSeconds(20), CancellationToken.None);
            await Task.Delay(300);
            double afterCut = double.Parse(File.ReadAllText(offset), System.Globalization.CultureInfo.InvariantCulture);
            using JsonDocument? beyond = await host.SendAsync(
                $$"""{"cmd":"reveal","hwnd":{{window}},"aliases":["Fila 25"],"direction":"down","amount":4}""",
                TimeSpan.FromSeconds(20), CancellationToken.None);
            await Task.Delay(300);
            double afterBeyond = double.Parse(File.ReadAllText(offset), System.Globalization.CultureInfo.InvariantCulture);
            TestContext.Out.WriteLine($"offset before {before}");
            TestContext.Out.WriteLine($"shown row: {shown!.RootElement} offset {afterShown}");
            TestContext.Out.WriteLine($"cut row: {cut!.RootElement} offset {afterCut}");
            TestContext.Out.WriteLine($"row beyond: {beyond!.RootElement} offset {afterBeyond}");
            Assert.Multiple(() =>
            {
                Assert.That(shown.RootElement.GetProperty("method").GetString(), Is.EqualTo("already"), "control");
                Assert.That(afterShown, Is.EqualTo(before), "control: a row in sight moves nothing");
                Assert.That(cut.RootElement.GetProperty("method").GetString(), Is.EqualTo("scrollintoview"), "the cut row");
                Assert.That(afterCut, Is.GreaterThan(afterShown), "the list really moved");
                Assert.That(afterBeyond, Is.GreaterThan(afterCut), "control: a row out of sight moves it as before");
            });
        }
        finally
        {
            if (!form.HasExited)
                form.Kill();
            form.WaitForExit(5000);
            Directory.Delete(folder, recursive: true);
        }
    }

    // B2: the witness's real captures of a window of its own, behind whatever is in front, as a named window's key is read:
    // a test process has no right to the front, so what changes the window is the window itself, on a file's word. A little
    // square blinks all the time; the list moves only when told.
    private const string KeyFormScript = """
        param([string]$Title,[string]$Go)
        Add-Type -AssemblyName PresentationFramework
        $w=New-Object System.Windows.Window
        $w.Title=$Title; $w.Width=320; $w.Height=320; $w.WindowStartupLocation='Manual'; $w.Left=60; $w.Top=60; $w.ShowActivated=$false
        $grid=New-Object System.Windows.Controls.DockPanel
        $mark=New-Object System.Windows.Shapes.Rectangle; $mark.Height=20; $mark.Width=40; $mark.Fill='Black'; $mark.HorizontalAlignment='Left'
        [System.Windows.Controls.DockPanel]::SetDock($mark,'Top')
        $list=New-Object System.Windows.Controls.ListBox
        foreach($i in 1..200){ [void]$list.Items.Add(('Fila {0:D3}' -f $i)) }
        [void]$grid.Children.Add($mark); [void]$grid.Children.Add($list); $w.Content=$grid
        $script:on=$true; $script:done=$false
        $timer=New-Object System.Windows.Threading.DispatcherTimer; $timer.Interval=[TimeSpan]::FromMilliseconds(120)
        $timer.Add_Tick({
          $script:on=-not $script:on; $mark.Fill=$(if($script:on){'Black'}else{'Red'})
          if(-not $script:done -and (Test-Path $Go)){ $script:done=$true; $list.ScrollIntoView($list.Items[150]) }
        })
        $timer.Start()
        [void]$w.ShowDialog()
        """;

    [Test]
    public async Task TheWitnessToldAWindowThatChangedFromOneThatOnlyBlinks()
    {
        if (Environment.GetEnvironmentVariable("BAXY_RECIBOS_LIVE") != "1")
            Assert.Ignore("BAXY_RECIBOS_LIVE=1 is needed to touch the desktop.");
        string folder = Path.Combine(Path.GetTempPath(), "baxy-recibos-live-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        string script = Path.Combine(folder, "form.ps1");
        string go = Path.Combine(folder, "go.txt");
        await File.WriteAllTextAsync(script, KeyFormScript, new UTF8Encoding(false));
        string title = "BAXY prueba tecla " + Guid.NewGuid().ToString("N")[..6];
        var start = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true };
        foreach (string argument in new[] { "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", script, "-Title", title, "-Go", go })
            start.ArgumentList.Add(argument);
        using Process form = Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
        try
        {
            nint window = 0;
            for (int attempt = 0; attempt < 80 && window == 0; attempt++)
            {
                window = FindWindowW(null, title);
                if (window == 0)
                    await Task.Delay(250);
            }

            Assert.That(window, Is.Not.EqualTo((nint)0), "the window did not appear");
            await Task.Delay(1000);
            KeySurfaceWitness witness = KeySurfaceWitness.Product;

            // Only the square blinks: the proof must say nothing, however many of its looks differ.
            int claims = 0;
            for (int round = 0; round < 3; round++)
            {
                VisibleControlSurface.CapturedWindow? still = await witness.BeforeAsync(window, CancellationToken.None);
                Assert.That(still, Is.Not.Null, "the window draws itself");
                if (await witness.ChangedAsync(still!.Value, Environment.TickCount64, static () => true, CancellationToken.None) == KeySurfaceVerdict.Changed)
                    claims++;
            }

            // The list moved beside the same square: it keeps moving, so nothing is claimed.
            VisibleControlSurface.CapturedWindow? before = await witness.BeforeAsync(window, CancellationToken.None);
            await File.WriteAllTextAsync(go, "x");
            bool moved = await witness.ChangedAsync(before!.Value, Environment.TickCount64, static () => true, CancellationToken.None) == KeySurfaceVerdict.Changed;
            TestContext.Out.WriteLine($"claims with only the square blinking: {claims} of 3; list moved told: {moved}");
            Assert.Multiple(() =>
            {
                Assert.That(claims, Is.EqualTo(0), "control");
                Assert.That(moved, Is.False);
            });
        }
        finally
        {
            if (!form.HasExited)
                form.Kill();
            form.WaitForExit(5000);
            Directory.Delete(folder, recursive: true);
        }
    }

    // Review of batch 2 (B1), measured: the same window with nothing done to it, drawn while active and while inactive, and
    // drawn again inactive after a front and back. Own windows only.
    private const string ActiveFormScript = """
        param([string]$Title)
        Add-Type -AssemblyName PresentationFramework
        $w=New-Object System.Windows.Window
        $w.Title=$Title; $w.Width=320; $w.Height=200; $w.WindowStartupLocation='Manual'; $w.Left=60; $w.Top=60; $w.ShowActivated=$false
        $s=New-Object System.Windows.Controls.StackPanel
        $a=New-Object System.Windows.Controls.TextBox; $a.Text='uno'; $b=New-Object System.Windows.Controls.TextBox; $b.Margin='0,10,0,0'
        [void]$s.Children.Add($a); [void]$s.Children.Add($b); $w.Content=$s
        [void]$w.ShowDialog()
        """;

    [Test]
    public async Task AWindowsImageWhileActiveAgainstInactiveAndTheFieldThatTakesTheFocus()
    {
        if (Environment.GetEnvironmentVariable("BAXY_RECIBOS_LIVE") != "1")
            Assert.Ignore("BAXY_RECIBOS_LIVE=1 is needed to touch the desktop.");
        string folder = Path.Combine(Path.GetTempPath(), "baxy-recibos-live-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        string script = Path.Combine(folder, "form.ps1");
        await File.WriteAllTextAsync(script, ActiveFormScript, new UTF8Encoding(false));
        Process Open(string title)
        {
            var start = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true };
            foreach (string argument in new[] { "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", script, "-Title", title })
                start.ArgumentList.Add(argument);
            return Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
        }

        string targetTitle = "BAXY prueba activa " + Guid.NewGuid().ToString("N")[..6];
        string otherTitle = "BAXY prueba otra " + Guid.NewGuid().ToString("N")[..6];
        using Process targetForm = Open(targetTitle);
        using Process otherForm = Open(otherTitle);
        try
        {
            async Task<nint> Find(string title)
            {
                for (int attempt = 0; attempt < 80; attempt++)
                {
                    if (FindWindowW(null, title) is var found and not 0)
                        return found;
                    await Task.Delay(250);
                }

                return 0;
            }

            nint target = await Find(targetTitle);
            nint other = await Find(otherTitle);
            Assert.That(target, Is.Not.EqualTo((nint)0));
            Assert.That(other, Is.Not.EqualTo((nint)0));
            await Task.Delay(800);
            async Task<VisibleControlSurface.CapturedWindow> Drawn()
            {
                await Task.Delay(700);
                return (await VisibleControlSurface.CaptureAsync(target, CancellationToken.None, selfDrawn: true))!.Value;
            }

            static int Differ(VisibleControlSurface.CapturedWindow first, VisibleControlSurface.CapturedWindow second) =>
                VisibleControlSurface.DifferingCells(first, second, out _, out _)?.Count(static cell => cell) ?? -1;

            bool heldOther = ForegroundRight.Give(other).Held;
            VisibleControlSurface.CapturedWindow inactive = await Drawn();
            bool heldTarget = ForegroundRight.Give(target).Held;
            VisibleControlSurface.CapturedWindow active = await Drawn();
            _ = ForegroundRight.Give(other);
            VisibleControlSurface.CapturedWindow inactiveAgain = await Drawn();
            TestContext.Out.WriteLine(
                $"front given: other {heldOther}, target {heldTarget}; cells differing active/inactive {Differ(inactive, active)}, inactive/inactive after a front and back {Differ(inactive, inactiveAgain)}");

            // focusMoved through the real worker: the window in front, the keyboard's focus in the first field.
            _ = ForegroundRight.Give(target);
            await Task.Delay(300);
            using var host = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using JsonDocument? view = await host.SendAsync($$"""{"cmd":"view","hwnd":{{target}},"limit":60}""", TimeSpan.FromSeconds(20), CancellationToken.None);
            string[] edits = [.. view!.RootElement.GetProperty("controls").EnumerateArray()
                .Where(static control => control.GetProperty("kind").GetString() == "Edit")
                .Select(static control => control.GetProperty("id").GetString()!)];
            using JsonDocument? focused = await host.SendAsync($$"""{"cmd":"focus","hwnd":{{target}},"controlId":"{{edits[0]}}"}""", TimeSpan.FromSeconds(20), CancellationToken.None);
            using JsonDocument? second = await host.SendAsync($$"""{"cmd":"field","hwnd":{{target}},"controlId":"{{edits[1]}}","text":"dos"}""", TimeSpan.FromSeconds(20), CancellationToken.None);
            using JsonDocument? again = await host.SendAsync($$"""{"cmd":"field","hwnd":{{target}},"controlId":"{{edits[1]}}","text":"tres"}""", TimeSpan.FromSeconds(20), CancellationToken.None);
            TestContext.Out.WriteLine($"focus {focused!.RootElement}");
            TestContext.Out.WriteLine($"field {second!.RootElement}");
            TestContext.Out.WriteLine($"again {again!.RootElement}");
            Assert.Multiple(() =>
            {
                Assert.That(second.RootElement.TryGetProperty("focusMoved", out JsonElement moved) && moved.GetBoolean(), Is.True);
                Assert.That(again.RootElement.TryGetProperty("focusMoved", out _), Is.False, "control: it already held it");
            });
        }
        finally
        {
            foreach (Process form in new[] { targetForm, otherForm })
            {
                if (!form.HasExited)
                    form.Kill();
                form.WaitForExit(5000);
            }

            Directory.Delete(folder, recursive: true);
        }
    }

    // B2 with real keys: the real adapters and SendInput on a slide-like window of its own, drawn and so unseen by the tree;
    // the window's own count of what it took is the oracle. With -Animate a square blinks and a bar ticks every second.
    private const string SlideFormScript = """
        param([string]$Title,[string]$Count,[switch]$Animate)
        Add-Type -AssemblyName PresentationFramework
        $w=New-Object System.Windows.Window
        $w.Title=$Title; $w.Width=420; $w.Height=320; $w.WindowStartupLocation='Manual'; $w.Left=60; $w.Top=60
        $root=New-Object System.Windows.Controls.DockPanel
        $close=New-Object System.Windows.Controls.Button; $close.Content='Salir'; $close.Focusable=$false
        [System.Windows.Controls.DockPanel]::SetDock($close,'Bottom'); [void]$root.Children.Add($close)
        $paper=New-Object System.Windows.Controls.Canvas; [void]$root.Children.Add($paper)
        $slide=New-Object System.Windows.Shapes.Rectangle; $slide.Width=20; $slide.Height=40; $slide.Fill='Navy'
        [System.Windows.Controls.Canvas]::SetLeft($slide,10); [System.Windows.Controls.Canvas]::SetTop($slide,200); [void]$paper.Children.Add($slide)
        $w.Content=$root
        $script:taken=0
        [IO.File]::WriteAllText($Count,'0')
        $w.Add_PreviewKeyDown({ param($s,$e)
          if($e.Key -eq 'Right'){ $script:taken++; $slide.Width=20+30*$script:taken; [IO.File]::WriteAllText($Count,[string]$script:taken); $e.Handled=$true }
        })
        if($Animate){
          $mark=New-Object System.Windows.Shapes.Rectangle; $mark.Width=40; $mark.Height=30; $mark.Fill='Black'
          [System.Windows.Controls.Canvas]::SetLeft($mark,10); [System.Windows.Controls.Canvas]::SetTop($mark,10); [void]$paper.Children.Add($mark)
          $tick=New-Object System.Windows.Shapes.Rectangle; $tick.Height=20; $tick.Fill='Green'
          [System.Windows.Controls.Canvas]::SetLeft($tick,10); [System.Windows.Controls.Canvas]::SetTop($tick,60); [void]$paper.Children.Add($tick)
          $script:on=$true; $script:second=-1
          $timer=New-Object System.Windows.Threading.DispatcherTimer; $timer.Interval=[TimeSpan]::FromMilliseconds(120)
          $timer.Add_Tick({
            $script:on=-not $script:on; $mark.Fill=$(if($script:on){'Black'}else{'Red'})
            $now=[DateTime]::Now.Second; if($now -ne $script:second){ $script:second=$now; $tick.Width=5*($now+1) }
          })
          $timer.Start()
        }
        [void]$w.ShowDialog()
        """;

    [TestCase(false)]
    [TestCase(true)]
    public async Task RealKeysAreToldAsTheWindowTookThem(bool animate)
    {
        if (Environment.GetEnvironmentVariable("BAXY_RECIBOS_LIVE") != "1")
            Assert.Ignore("BAXY_RECIBOS_LIVE=1 is needed to touch the desktop.");
        string folder = Path.Combine(Path.GetTempPath(), "baxy-recibos-live-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        string script = Path.Combine(folder, "form.ps1");
        string count = Path.Combine(folder, "count.txt");
        await File.WriteAllTextAsync(script, SlideFormScript, new UTF8Encoding(false));
        string title = "BAXY prueba tecla real " + Guid.NewGuid().ToString("N")[..6];
        var start = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true };
        foreach (string argument in new[] { "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", script, "-Title", title, "-Count", count })
            start.ArgumentList.Add(argument);
        if (animate)
            start.ArgumentList.Add("-Animate");
        using Process form = Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
        try
        {
            nint window = 0;
            for (int attempt = 0; attempt < 80 && window == 0; attempt++)
            {
                window = FindWindowW(null, title);
                if (window == 0)
                    await Task.Delay(250);
            }

            Assert.That(window, Is.Not.EqualTo((nint)0), "the window did not appear");
            await Task.Delay(1000);
            using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using var visible = new WindowsVisibleControlAdapter(uia);
            var keys = new WindowsDesktopInteractionAdapter(visible) { Scripts = uia };
            _ = WindowsUserInputPause.Shared;
            await Task.Delay(500);
            int Taken() => int.Parse(File.ReadAllText(count), System.Globalization.CultureInfo.InvariantCulture);
            var rows = new List<string>();
            var lies = new List<string>();

            async Task Press(string key, bool named)
            {
                Assert.That(ForegroundRight.Give(window).Held, Is.True, "the window in front");
                await Task.Delay(400);
                if (named)
                {
                    ExternalCapabilityReceipt looked = await visible.InvokeAsync("input.visible.controls",
                        JsonDocument.Parse(JsonSerializer.Serialize(new { window = (long)window, limit = 60 })).RootElement, CancellationToken.None);
                    Assert.That(looked.Verified, Is.True, looked.ErrorCode);
                }

                Assert.That(GetForegroundWindow(), Is.EqualTo(window), "keys go only to this window");
                int before = Taken();
                string arguments = named ? $$"""{"key":"{{key}}","window":{{window}}}""" : $$"""{"key":"{{key}}"}""";
                ExternalCapabilityReceipt receipt = await keys.InvokeAsync(
                    "input.key.press", JsonDocument.Parse(arguments).RootElement.Clone(), CancellationToken.None);
                await Task.Delay(200);
                bool took = Taken() != before;
                JsonElement result = receipt.Result!.Value;
                bool said = result.TryGetProperty("surfaceChanged", out JsonElement changed) && changed.GetBoolean();
                JsonElement view = result.TryGetProperty("after", out JsonElement read) ? read : default;
                string after = view.ValueKind == JsonValueKind.Object ? view.GetRawText() : "-";
                string told = Baxy.Kernel.Operations.OperationVisibleFacts.Verification("input.key.press", result);
                rows.Add($"{(animate ? "anima" : "quieta")} | {(named ? "nombrada" : "sin nombre")} | {key} | tomó {took} | surfaceChanged {said} | after {after} | {told} | {receipt.Verified} {receipt.ErrorCode}");
                // Moving by itself, an unproved key may stay unverified; a claim must be true anywhere.
                if ((said && !took) || (!animate && took && !said)
                    || (took && view.ValueKind == JsonValueKind.Object && view.TryGetProperty("same", out _)))
                    lies.Add(rows[^1]);
            }

            await Press("arrow_right", named: true);
            await Press("arrow_up", named: true);
            await Press("arrow_right", named: false);
            await Press("arrow_up", named: false);
            await Press("arrow_up", named: true);
            await Press("arrow_up", named: false);
            foreach (string row in rows)
                TestContext.Out.WriteLine(row);
            Assert.That(lies, Is.Empty);
        }
        finally
        {
            if (!form.HasExited)
                form.Kill();
            form.WaitForExit(5000);
            Directory.Delete(folder, recursive: true);
        }
    }

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern nint FindWindowW(string? className, string windowName);
}
