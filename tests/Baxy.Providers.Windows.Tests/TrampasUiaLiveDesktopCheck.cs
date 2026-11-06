using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso-108: one window of the test's own, read and pressed by the real worker, with no model and no real application
/// (agent-desktop tests/fixture-app-windows: each card stages one UIA trap). It shows without taking the front and closes
/// by its process id. Never runs in a suite: Explicit and BAXY_TRAMPAS_LIVE_CHECK=1.
/// </summary>
[TestFixture]
[Explicit("Opens a window on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class TrampasUiaLiveDesktopCheck
{
    private const string Form = """
        Add-Type -AssemblyName System.Windows.Forms,System.Drawing
        Add-Type -ReferencedAssemblies System.Windows.Forms,System.Drawing -TypeDefinition @'
        public class QuietForm : System.Windows.Forms.Form {
          protected override bool ShowWithoutActivation { get { return true; } }
        }
        '@
        $form=New-Object QuietForm
        $form.Text='Trampas UIA de BAXY'; $form.Width=560; $form.Height=320; $form.StartPosition='Manual'; $form.Left=80; $form.Top=80
        $form.Name='trampas'
        $apagado=New-Object System.Windows.Forms.Button; $apagado.Text='Apagado'; $apagado.Enabled=$false; $apagado.Left=10; $apagado.Top=10; $form.Controls.Add($apagado)
        $encendido=New-Object System.Windows.Forms.Button; $encendido.Text='Encendido'; $encendido.Left=110; $encendido.Top=10; $form.Controls.Add($encendido)
        $largo=New-Object System.Windows.Forms.TextBox; $largo.Name='Largo'; $largo.AccessibleName='Largo'; $largo.Left=10; $largo.Top=50; $largo.Width=500; $largo.Text=('abcde ' * 80).Trim(); $form.Controls.Add($largo)
        $corto=New-Object System.Windows.Forms.TextBox; $corto.Name='Corto'; $corto.AccessibleName='Corto'; $corto.Left=10; $corto.Top=80; $corto.Width=500; $corto.Text='corto'; $form.Controls.Add($corto)
        $efimero=New-Object System.Windows.Forms.Button; $efimero.Text='Efimero'; $efimero.Left=210; $efimero.Top=10; $form.Controls.Add($efimero)
        $tiempo=New-Object System.Windows.Forms.Timer; $tiempo.Interval=9000; $tiempo.Add_Tick({ $tiempo.Stop(); $form.Controls.Remove($efimero); $efimero.Dispose() }); $tiempo.Start()
        $form.Add_Shown({ [Console]::Out.WriteLine($form.Handle.ToInt64()) })
        [System.Windows.Forms.Application]::Run($form)
        """;

    [Test]
    public async Task ADisabledControlAndALongValueAreToldAsThey()
    {
        if (Environment.GetEnvironmentVariable("BAXY_TRAMPAS_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_TRAMPAS_LIVE_CHECK=1 is needed to touch the desktop.");
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-STA", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(Form)));
        using Process form = Process.Start(start)!;
        try
        {
            string? line = await form.StandardOutput.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(30));
            Assert.That(long.TryParse(line, out long window), line);
            await Task.Delay(500);

            // The worker itself on this window: the adapter refuses a window of a console host (protected_window), and this
            // one's process is PowerShell. No adapter stage can touch another window this way.
            using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            async Task<string> Ask(object command)
            {
                using JsonDocument? answer = await uia.SendAsync(
                    JsonSerializer.Serialize(command), TimeSpan.FromSeconds(20), CancellationToken.None);
                return answer?.RootElement.GetRawText() ?? "(sin respuesta)";
            }

            var watch = Stopwatch.StartNew();
            string read = await Ask(new { cmd = "view", hwnd = window, limit = 60 });
            TestContext.Out.WriteLine($"mirada {watch.ElapsedMilliseconds} ms: {read}");
            watch.Restart();
            string dimmed = await Ask(new { cmd = "click", hwnd = window, aliases = new[] { "Apagado" }, controlId = "" });
            TestContext.Out.WriteLine($"apagado {watch.ElapsedMilliseconds} ms: {dimmed}");
            watch.Restart();
            string missing = await Ask(new { cmd = "click", hwnd = window, aliases = new[] { "No existe" }, controlId = "" });
            TestContext.Out.WriteLine($"no existe {watch.ElapsedMilliseconds} ms: {missing}");

            // Revisión de la tanda 1: a control gone since the look is stale, never disabled. Its element's properties raise,
            // and PowerShell turns that raise into $null: «not enabled» read true on a dead element.
            string gone = await Ask(new { cmd = "view", hwnd = window, limit = 60 });
            using JsonDocument seen = JsonDocument.Parse(gone);
            string fleeting = seen.RootElement.GetProperty("controls").EnumerateArray()
                .First(static control => control.GetProperty("name").GetString() == "Efimero")
                .GetProperty("id").GetString()!;
            await Task.Delay(TimeSpan.FromSeconds(10) - watch.Elapsed > TimeSpan.Zero ? TimeSpan.FromSeconds(10) : TimeSpan.Zero);
            string pressedGone = await Ask(new { cmd = "click", hwnd = window, aliases = new[] { "Efimero" }, controlId = fleeting });
            TestContext.Out.WriteLine($"efimero: {pressedGone}");

            Assert.Multiple(() =>
            {
                Assert.That(pressedGone, Does.Contain("visible_control_identity_stale"));
                Assert.That(pressedGone, Does.Not.Contain("visible_control_disabled"));
                Assert.That(read, Does.Contain("\"valueCut\":359"), "the long value says what it lost");
                Assert.That(read, Does.Contain("\"valueCut\":0"), "the short one does not");
                Assert.That(dimmed, Does.Contain("visible_control_disabled"));
                Assert.That(dimmed, Does.Contain("\"effectObserved\":false"));
                Assert.That(missing, Does.Contain("visible_button_not_found"), "control: what does not exist still says so");
            });
        }
        finally
        {
            if (!form.HasExited)
                form.Kill();
        }
    }
}
