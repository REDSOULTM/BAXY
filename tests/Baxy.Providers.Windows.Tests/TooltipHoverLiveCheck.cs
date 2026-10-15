using System.Diagnostics;
using System.Globalization;
using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The tooltip stage on the real desktop, opt-in only (Explicit and BAXY_TOOLTIP_LIVE_CHECK): for each process named
/// (comma-separated; «self» opens a WinForms window of the test's own with three icon buttons that have only a
/// tooltip), its largest window is bound like a mission's and its candidates are hovered with the real worker, lease
/// and OCR, never clicked. Prints, per window, the candidates and the label each tooltip gave (source: tooltipUia or
/// tooltipOcr), and checks the cursor ends where it was. Only on «self» is a learned icon also pressed (its click
/// changes the window's title). Labels go to a temporary cache, never to the person's data root.
/// </summary>
[TestFixture]
[Explicit("Moves the cursor over the named windows (in pauses of the person) and brings them up for a moment.")]
public sealed class TooltipHoverLiveCheck
{
    [Test]
    public async Task TheTooltipsOfTheNamedWindowsAreReadAndTheCursorGoesBack()
    {
        string? named = Environment.GetEnvironmentVariable("BAXY_TOOLTIP_LIVE_CHECK");
        if (string.IsNullOrWhiteSpace(named))
            Assert.Ignore("Set BAXY_TOOLTIP_LIVE_CHECK=self,<process>,... to run the live check.");
        string cachePath = Path.Combine(Path.GetTempPath(), "baxy-tooltip-live-" + Guid.NewGuid().ToString("N") + ".json");
        var cache = new TooltipLabelCache(cachePath);
        using var worker = new UiaWorkerHost();
        var desktop = new WindowsTooltipDesktop();
        int cap = int.TryParse(Environment.GetEnvironmentVariable("BAXY_TOOLTIP_LIVE_CAP"), NumberStyles.Integer,
            CultureInfo.InvariantCulture, out int configured) ? configured : 12;
        var report = new StringBuilder();
        var locator = new WindowsVisibleTooltipLocator(worker, desktop, cache)
        {
            CandidateCap = cap,
            Budget = 60_000,
            Trace = line => report.AppendLine("      " + line),
        };
        var lease = new WindowsLeaseDesktop();
        Process? own = null;
        try
        {
            foreach (string name in named.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
            {
                nint window;
                if (name == "self")
                {
                    own = OpenForm("BAXY tooltip " + Guid.NewGuid().ToString("N")[..8]);
                    window = await MainWindowAsync(own);
                }
                else
                {
                    window = Process.GetProcessesByName(name)
                        .Select(process => VisibleControlSurface.LargestTopLevelWindow(process.Id))
                        .FirstOrDefault(handle => handle != 0);
                }

                if (window == 0)
                {
                    report.AppendLine(CultureInfo.InvariantCulture, $"{name}: sin ventana");
                    continue;
                }

                (int X, int Y) cursor = lease.Cursor();
                var read = new List<WindowsVisibleTooltipLocator.Learned>();
                var watch = Stopwatch.StartNew();
                using (VisibleControlSurface.RequireWindow(window))
                {
                    VisibleControlSurface.CapturedWindow? capture = await desktop.CaptureAsync(window, null, CancellationToken.None);
                    IReadOnlyList<WindowsVisibleTooltipLocator.Candidate> candidates = capture is { } seen
                        ? await locator.CandidatesAsync(window, seen, CancellationToken.None)
                        : [];
                    _ = await locator.LearnAsync("\u0001", CancellationToken.None, read);
                    report.AppendLine(
                        CultureInfo.InvariantCulture,
                        $"{name} [{VisibleControlSurface.ClassName(window)}]: candidatos {candidates.Count} " +
                        $"({string.Join(',', candidates.GroupBy(candidate => candidate.Kind).Select(group => group.Key + "=" + group.Count()))}), " +
                        $"leídos {read.Count}, {watch.ElapsedMilliseconds} ms, cursor devuelto {lease.Cursor() == cursor}");
                    foreach (WindowsVisibleTooltipLocator.Learned learned in read)
                        report.AppendLine(CultureInfo.InvariantCulture, $"   «{learned.Label}» <- {learned.Source} en {learned.Screen}");
                    if (name == "self" && read.FirstOrDefault(learned => learned.Label.Contains("Configur", StringComparison.Ordinal)) is { Label.Length: > 0 } settings)
                    {
                        string before = VisibleControlSurface.WindowTitle(window);
                        ExternalCapabilityReceipt? pressed = await locator.TryClickAsync(
                            "input.visible.click", "configuración", null, CancellationToken.None);
                        report.AppendLine(
                            CultureInfo.InvariantCulture,
                            $"   clic «configuración»: {pressed?.Verified} {pressed?.Result} título {before} -> {VisibleControlSurface.WindowTitle(window)}");
                    }
                }
            }
        }
        finally
        {
            if (own is { HasExited: false })
                own.Kill();
            own?.Dispose();
            try
            {
                File.Delete(cachePath);
            }
            catch (IOException)
            {
            }
        }

        TestContext.Out.WriteLine(report.ToString());
    }

    // A WinForms window of the test's own: three buttons without text (a drawn glyph) whose only name is a tooltip.
    private static Process OpenForm(string title)
    {
        string script = """
            Add-Type -AssemblyName System.Windows.Forms
            Add-Type -AssemblyName System.Drawing
            $form=New-Object System.Windows.Forms.Form
            $form.Text='__TITLE__'; $form.Width=420; $form.Height=220; $form.StartPosition='Manual'; $form.Left=200; $form.Top=200
            $tips=New-Object System.Windows.Forms.ToolTip
            $tips.InitialDelay=200; $tips.ShowAlways=$true
            $x=20
            foreach($label in @('Notificaciones','Configuración de usuario','Más opciones')){
              $button=New-Object System.Windows.Forms.Button
              $button.Width=36; $button.Height=36; $button.Left=$x; $button.Top=20; $button.Text=''
              $button.Add_Paint({ param($s,$e) $e.Graphics.FillEllipse([System.Drawing.Brushes]::Black,10,10,16,16) })
              $tips.SetToolTip($button,$label)
              $text=$label
              $button.Add_Click({ $form.Text=$form.Text+' pulsado' }.GetNewClosure())
              $form.Controls.Add($button)
              $x+=60
            }
            [void]$form.ShowDialog()
            """.Replace("__TITLE__", title, StringComparison.Ordinal);
        // A shell window is protected from computer use (it is where a developer works): the form runs in a copy of
        // the shell under another name, so the stage treats it as any application's window.
        string host = Path.Combine(Path.GetTempPath(), "baxytooltipform.exe");
        if (!File.Exists(host))
            File.Copy(Path.Combine(Environment.SystemDirectory, "WindowsPowerShell", "v1.0", "powershell.exe"), host);
        var start = new ProcessStartInfo(host)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(script)));
        return Process.Start(start)!;
    }

    private static async Task<nint> MainWindowAsync(Process process)
    {
        for (int attempt = 0; attempt < 100; attempt++)
        {
            process.Refresh();
            if (process.MainWindowHandle != 0)
                return process.MainWindowHandle;
            await Task.Delay(100);
        }

        return 0;
    }
}
