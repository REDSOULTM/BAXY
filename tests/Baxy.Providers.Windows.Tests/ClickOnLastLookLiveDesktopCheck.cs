using System.Diagnostics;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real 05-11 (C2040), measured on the desktop with programs of the test's own: two windows show a button of the same
/// name, the second in front. A look names the first; the adapter alone presses the label in the window in front, and the
/// provider, as the product runs it, in the window looked at. And a program whose first window goes and whose main window
/// comes seconds later: a look by its name answers «none» at once with no opening noted, and waits for it with one.
/// Never runs in a suite: Explicit and BAXY_C2040_LIVE_CHECK=1. It closes every process of its own by id.
/// </summary>
[TestFixture]
[Explicit("Opens windows on the person's desktop and clicks in them.")]
[Category("LiveDesktop")]
public sealed class ClickOnLastLookLiveDesktopCheck
{
    private const string Label = "Curso de prueba";

    private const string ButtonProgram = """
        using System.Windows.Forms;
        static class P {
          [System.STAThread] static void Main(string[] a) {
            var f = new Form { Text = a[0], StartPosition = FormStartPosition.Manual, Left = int.Parse(a[1]), Top = 40, Width = 500, Height = 300 };
            var b = new Button { Text = "Curso de prueba", Width = 200, Height = 60, Left = 40, Top = 40 };
            b.Click += (s, e) => {
              if (a.Length < 3) { f.Text = a[0] + " pulsada"; return; }
              var d = new Form { Text = "Dialogo", Width = 300, Height = 200 };
              var o = new Button { Text = "Curso de prueba", Width = 200, Height = 60 };
              o.Click += (s2, e2) => { f.Text = a[0] + " dialogo"; d.Close(); };
              d.Controls.Add(o);
              d.ShowDialog(f);
            };
            f.Controls.Add(b);
            Application.Run(f);
          }
        }
        """;

    private static string ProgramThatOpensLate(string name, int gapSeconds) => $$"""
        using System.Threading; using System.Windows.Forms;
        static class P {
          [System.STAThread] static void Main() {
            var aviso = new Form { Text = "Aviso {{name}}" }; aviso.Show(); Application.DoEvents();
            Thread.Sleep(2000); aviso.Close(); aviso.Dispose(); Application.DoEvents();
            Thread.Sleep({{gapSeconds}} * 1000);
            var main = new Form { Text = "{{name}}" }; main.Show(); Application.DoEvents();
            var until = System.DateTime.UtcNow.AddSeconds(40);
            while (System.DateTime.UtcNow < until) { Application.DoEvents(); Thread.Sleep(100); }
          }
        }
        """;

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private static void RequireLiveCheck()
    {
        if (Environment.GetEnvironmentVariable("BAXY_C2040_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_C2040_LIVE_CHECK=1 is needed to touch the desktop.");
    }

    // A program of the test's own, no console nor developer's tool.
    private static async Task<string> CompileAsync(string folder, string name, string source)
    {
        string program = Path.Combine(folder, name + ".exe");
        string script = Path.Combine(folder, name + ".ps1");
        await File.WriteAllTextAsync(script,
            "Add-Type -ReferencedAssemblies System.Windows.Forms -OutputType WindowsApplication -OutputAssembly '"
            + program + "' -TypeDefinition @'\n" + source + "\n'@\n");
        using var compile = Process.Start(new ProcessStartInfo("powershell.exe")
        {
            ArgumentList = { "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script },
            UseShellExecute = false,
            CreateNoWindow = true,
        })!;
        await compile.WaitForExitAsync();
        Assert.That(File.Exists(program), "the test's own program compiled");
        return program;
    }

    private static async Task<nint> WindowTitledAsync(string title)
    {
        for (int attempt = 0; attempt < 40; attempt++)
        {
            nint window = await VisibleControlSurface.ResolveTitledWindowAsync(title, CancellationToken.None);
            if (window != 0)
                return window;
            await Task.Delay(250);
        }

        return 0;
    }

    private static async Task CleanAsync(string folder, params Process?[] own)
    {
        foreach (Process? process in own)
        {
            if (process is null)
                continue;
            if (!process.HasExited)
                process.Kill();
            await process.WaitForExitAsync();
            process.Dispose();
        }

        await Task.Delay(500);
        try
        {
            Directory.Delete(folder, recursive: true);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            TestContext.Out.WriteLine("carpeta temporal sin borrar: " + folder);
        }
    }

    [Test]
    public async Task TheClickGoesToTheWindowLookedAtNotToTheOneInFront()
    {
        RequireLiveCheck();
        const string looked = "Bandeja C2040";
        const string front = "Portal C2040";
        string folder = Path.Combine(Path.GetTempPath(), "baxy-c2040-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(folder);
        Process? first = null;
        Process? second = null;
        try
        {
            string program = await CompileAsync(folder, "BotonC2040", ButtonProgram);
            first = Process.Start(new ProcessStartInfo(program) { ArgumentList = { looked, "0" }, UseShellExecute = false });
            nint lookedWindow = await WindowTitledAsync(looked);
            second = Process.Start(new ProcessStartInfo(program) { ArgumentList = { front, "520" }, UseShellExecute = false });
            nint frontWindow = await WindowTitledAsync(front);
            Assert.That(lookedWindow, Is.Not.EqualTo((nint)0));
            Assert.That(frontWindow, Is.Not.EqualTo((nint)0));
            await Task.Delay(800);

            using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using var visible = new WindowsVisibleControlAdapter(uia)
            {
                PersonTouchOf = (_, _) => PersonTouch.None,
                WindowInFront = _ => ValueTask.FromResult(frontWindow),
            };
            using var provider = new WindowsExternalCapabilityProvider([visible], null, (_, _) => false);
            string look = $$"""{"application":"{{looked}}"}""";
            string click = $$"""{"label":"{{Label}}"}""";

            ExternalCapabilityReceipt view = await provider.InvokeAsync("input.visible.controls", Json(look), CancellationToken.None);
            Assert.That(visible.NamesSeen(lookedWindow), Does.Contain(Label), "the look shows the button: " + view.ErrorCode);
            ExternalCapabilityReceipt alone = await visible.InvokeAsync("input.visible.click", Json(click), CancellationToken.None);
            await Task.Delay(500);
            string frontAfterAlone = VisibleControlSurface.WindowTitle(frontWindow);
            string lookedAfterAlone = VisibleControlSurface.WindowTitle(lookedWindow);
            TestContext.Out.WriteLine($"el adaptador solo (la base): error={alone.ErrorCode} delante=«{frontAfterAlone}» mirada=«{lookedAfterAlone}»");

            await provider.InvokeAsync("input.visible.controls", Json(look), CancellationToken.None);
            ExternalCapabilityReceipt bound = await provider.InvokeAsync("input.visible.click", Json(click), CancellationToken.None);
            await Task.Delay(500);
            string lookedAfterBound = VisibleControlSurface.WindowTitle(lookedWindow);
            TestContext.Out.WriteLine($"el proveedor: error={bound.ErrorCode} mirada=«{lookedAfterBound}»");

            Assert.Multiple(() =>
            {
                Assert.That(frontAfterAlone, Does.Contain("pulsada"), "without the binding the window in front is pressed");
                Assert.That(lookedAfterAlone, Does.Not.Contain("pulsada"));
                Assert.That(lookedAfterBound, Does.Contain("pulsada"), "with it, the window looked at");
            });
        }
        finally
        {
            await CleanAsync(folder, first, second);
        }
    }

    // Revisión R2 (H2): another window comes in front after the look, with a button of the same name: the click goes there,
    // never to the window looked at; a click in the window in front ends the look (H1), so the next stays there.
    [Test]
    public async Task AWindowBroughtAfterTheLookTakesTheClick()
    {
        RequireLiveCheck();
        const string looked = "Bandeja R2";
        const string front = "Portal R2";
        const string brought = "Aviso R2";
        string folder = Path.Combine(Path.GetTempPath(), "baxy-c2040-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(folder);
        Process? first = null;
        Process? second = null;
        Process? third = null;
        try
        {
            string program = await CompileAsync(folder, "BotonC2040", ButtonProgram);
            first = Process.Start(new ProcessStartInfo(program) { ArgumentList = { looked, "0" }, UseShellExecute = false });
            nint lookedWindow = await WindowTitledAsync(looked);
            second = Process.Start(new ProcessStartInfo(program) { ArgumentList = { front, "520" }, UseShellExecute = false });
            nint frontWindow = await WindowTitledAsync(front);
            third = Process.Start(new ProcessStartInfo(program) { ArgumentList = { brought, "1040" }, UseShellExecute = false });
            nint broughtWindow = await WindowTitledAsync(brought);
            Assert.That(new[] { lookedWindow, frontWindow, broughtWindow }, Has.None.EqualTo((nint)0));
            await Task.Delay(800);

            nint inFront = frontWindow;
            using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using var visible = new WindowsVisibleControlAdapter(uia)
            {
                PersonTouchOf = (_, _) => PersonTouch.None,
                WindowInFront = _ => ValueTask.FromResult(inFront),
            };
            using var provider = new WindowsExternalCapabilityProvider([visible], null, (_, _) => false);

            await provider.InvokeAsync("input.visible.controls", Json($$"""{"application":"{{looked}}"}"""), CancellationToken.None);
            Assert.That(visible.NamesSeen(lookedWindow), Does.Contain(Label));
            inFront = broughtWindow;
            ExternalCapabilityReceipt pressed = await provider.InvokeAsync(
                "input.visible.click", Json($$"""{"label":"{{Label}}"}"""), CancellationToken.None);
            await Task.Delay(500);
            string lookedAfter = VisibleControlSurface.WindowTitle(lookedWindow);
            string frontAfter = VisibleControlSurface.WindowTitle(frontWindow);
            string broughtAfter = VisibleControlSurface.WindowTitle(broughtWindow);
            TestContext.Out.WriteLine($"traída: error={pressed.ErrorCode} mirada=«{lookedAfter}» delante antes=«{frontAfter}» traída=«{broughtAfter}»");

            Assert.Multiple(() =>
            {
                Assert.That(broughtAfter, Does.Contain("pulsada"));
                Assert.That(lookedAfter, Does.Not.Contain("pulsada"));
                Assert.That(frontAfter, Does.Not.Contain("pulsada"));
            });
        }
        finally
        {
            await CleanAsync(folder, first, second, third);
        }
    }

    // The button opened a modal dialog with one of the same name. Revisión R2 (H5): the click by that label was decided on
    // the window, and the dialog asks something of its own: nothing is pressed until a look reads it; then it goes there.
    [Test]
    public async Task AModalDialogIsPressedOnlyOnceALookReadIt()
    {
        RequireLiveCheck();
        const string title = "Modal C2040";
        string folder = Path.Combine(Path.GetTempPath(), "baxy-c2040-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(folder);
        Process? started = null;
        try
        {
            string program = await CompileAsync(folder, "BotonC2040", ButtonProgram);
            started = Process.Start(new ProcessStartInfo(program) { ArgumentList = { title, "0", "modal" }, UseShellExecute = false });
            nint window = await WindowTitledAsync(title);
            Assert.That(window, Is.Not.EqualTo((nint)0));
            await Task.Delay(800);
            using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using var visible = new WindowsVisibleControlAdapter(uia) { PersonTouchOf = (_, _) => PersonTouch.None };
            using var provider = new WindowsExternalCapabilityProvider([visible], null, (_, _) => false);
            string click = $$"""{"label":"{{Label}}"}""";

            await provider.InvokeAsync("input.visible.controls", Json($$"""{"application":"{{title}}"}"""), CancellationToken.None);
            ExternalCapabilityReceipt opened = await provider.InvokeAsync("input.visible.click", Json(click), CancellationToken.None);
            await Task.Delay(800);
            ExternalCapabilityReceipt unread = await provider.InvokeAsync("input.visible.click", Json(click), CancellationToken.None);
            await Task.Delay(500);
            string before = VisibleControlSurface.WindowTitle(window);
            await provider.InvokeAsync("input.visible.controls", Json($$"""{"application":"{{title}}"}"""), CancellationToken.None);
            nint bound = await visible.WindowOfLastLookAsync("input.visible.click", Json(click), CancellationToken.None);
            ExternalCapabilityReceipt pressed = await provider.InvokeAsync("input.visible.click", Json(click), CancellationToken.None);
            await Task.Delay(500);
            string after = VisibleControlSurface.WindowTitle(window);
            TestContext.Out.WriteLine($"abrir: error={opened.ErrorCode}; sin leer: error={unread.ErrorCode}, título=«{before}»; atado={bound} principal={window}; pulsar: error={pressed.ErrorCode}; título=«{after}»");

            Assert.Multiple(() =>
            {
                Assert.That(unread.ErrorCode, Is.EqualTo(WindowsVisibleControlAdapter.DialogNotRead));
                Assert.That(before, Does.Not.Contain("dialogo"));
                Assert.That(bound, Is.Not.EqualTo(window), "bound to the dialog, not to the window it disabled");
                Assert.That(after, Does.Contain("dialogo"));
            });
        }
        finally
        {
            await CleanAsync(folder, started);
        }
    }

    [Test]
    public async Task ALookWaitsForTheMainWindowOfWhatWasJustOpened()
    {
        RequireLiveCheck();
        const string name = "ProgramaC2040";
        string folder = Path.Combine(Path.GetTempPath(), "baxy-c2040-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(folder);
        Process? started = null;
        try
        {
            string program = await CompileAsync(folder, name, ProgramThatOpensLate(name, gapSeconds: 8));
            started = Process.Start(new ProcessStartInfo(program) { UseShellExecute = false })!;
            using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            Assert.That(await WindowTitledAsync("Aviso " + name), Is.Not.EqualTo((nint)0));
            await Task.Delay(TimeSpan.FromSeconds(2.5));

            using var noOpening = new WindowsVisibleControlAdapter(uia) { OpeningRuns = _ => null };
            var clock = Stopwatch.StartNew();
            ExternalCapabilityReceipt before = await noOpening.InvokeAsync(
                "input.visible.controls", Json($$"""{"application":"{{name}}"}"""), CancellationToken.None);
            TestContext.Out.WriteLine($"sin apertura anotada (la base): error={before.ErrorCode} {clock.ElapsedMilliseconds} ms");

            Process running = started;
            using var opening = new WindowsVisibleControlAdapter(uia) { OpeningRuns = _ => !running.HasExited };
            clock.Restart();
            ExternalCapabilityReceipt after = await opening.InvokeAsync(
                "input.visible.controls", Json($$"""{"application":"{{name}}"}"""), CancellationToken.None);
            TestContext.Out.WriteLine($"con la apertura anotada: error={after.ErrorCode} {clock.ElapsedMilliseconds} ms");
            clock.Restart();
            await opening.InvokeAsync("input.visible.controls", Json($$"""{"application":"{{name}}"}"""), CancellationToken.None);
            TestContext.Out.WriteLine($"otra mirada, la ventana ya arriba: {clock.ElapsedMilliseconds} ms");

            Assert.Multiple(() =>
            {
                Assert.That(before.ErrorCode, Is.EqualTo("application_window_not_found"));
                Assert.That(after.ErrorCode, Is.Null);
                Assert.That(after.Result?.GetProperty("window").GetProperty("title").GetString(), Does.Contain(name));
            });
        }
        finally
        {
            await CleanAsync(folder, started);
        }
    }
}
