using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Goal v3 point 2, measured on the desktop: the worker's mouse-free primitives on a WinForms form of its own that
/// never takes the front: an unnamed field labelled by the text at its left (the view names it «Ancho»), its value
/// replaced (1366 → 800, not 1366800), a list-only combo box's entry chosen by pattern, and an item of a 300-row list
/// brought into view («reveal»). Never runs in a suite: Explicit and BAXY_CU_TIPOS_LIVE_CHECK=1. Run it only with the
/// desktop turn (scripts/cu_live/turno.sh tomar: its agent lock first, then no live.lock); it closes its form by its
/// exact process.
/// </summary>
[TestFixture]
[Explicit("Opens a window on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class TiposUiaLiveDesktopCheck
{
    private const string FormScript = """
        param([string]$Title)
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -ReferencedAssemblies System.Windows.Forms -TypeDefinition @'
        public class BaxyQuietTiposForm : System.Windows.Forms.Form {
          protected override bool ShowWithoutActivation { get { return true; } }
        }
        '@
        $f=New-Object BaxyQuietTiposForm
        $f.Text=$Title; $f.Width=460; $f.Height=360; $f.StartPosition='Manual'; $f.Left=80; $f.Top=80
        $label=New-Object System.Windows.Forms.Label; $label.Text='Ancho:'; $label.Left=10; $label.Top=14; $label.Width=60
        $box=New-Object System.Windows.Forms.TextBox; $box.Left=74; $box.Top=10; $box.Width=120; $box.Text='1366'
        $combo=New-Object System.Windows.Forms.ComboBox; $combo.Left=210; $combo.Top=10; $combo.Width=160
        $combo.DropDownStyle='DropDownList'; $combo.AccessibleName='Fuente'; [void]$combo.Items.AddRange(@('Arial','Calibri','Consolas')); $combo.SelectedIndex=1
        $list=New-Object System.Windows.Forms.ListBox; $list.Left=10; $list.Top=50; $list.Width=420; $list.Height=240
        for($i=1;$i -le 300;$i++){ [void]$list.Items.Add(('Elemento {0:D3}' -f $i)) }
        $f.Controls.AddRange(@($label,$box,$combo,$list))
        [System.Windows.Forms.Application]::Run($f)
        """;

    [Test]
    public async Task TheFormIsFilledAndTheListRevealedWithoutTheFront()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_TIPOS_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_CU_TIPOS_LIVE_CHECK=1 is needed to touch the desktop.");
        string script = Path.Combine(Path.GetTempPath(), "baxy-tipos-live-" + Guid.NewGuid().ToString("N") + ".ps1");
        await File.WriteAllTextAsync(script, FormScript, new UTF8Encoding(false));
        string title = "BAXY prueba tipos " + Guid.NewGuid().ToString("N")[..6];
        var start = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true };
        foreach (string argument in new[] { "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", script, "-Title", title })
            start.ArgumentList.Add(argument);
        using Process form = Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
        nint front = GetForegroundWindow();
        try
        {
            nint window = 0;
            for (int attempt = 0; attempt < 60 && window == 0; attempt++)
            {
                window = FindWindowW(null, title);
                if (window == 0)
                    await Task.Delay(250);
            }

            Assert.That(window, Is.Not.EqualTo((nint)0), "the form did not appear");
            using var host = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using JsonDocument? view = await host.SendAsync(
                $$"""{"cmd":"view","hwnd":{{window}},"limit":60}""", TimeSpan.FromSeconds(20), CancellationToken.None);
            JsonElement[] controls = view!.RootElement.GetProperty("controls").EnumerateArray().ToArray();
            JsonElement width = controls.Single(control => control.GetProperty("name").GetString() == "Ancho");
            JsonElement font = controls.Single(control => control.GetProperty("kind").GetString() == "ComboBox");
            string widthId = width.GetProperty("id").GetString()!;
            using JsonDocument? replaced = await host.SendAsync(
                $$"""{"cmd":"field","hwnd":{{window}},"controlId":"{{widthId}}","text":"800","replace":true}""",
                TimeSpan.FromSeconds(20), CancellationToken.None);
            using JsonDocument? chosen = await host.SendAsync(
                $$"""{"cmd":"field","hwnd":{{window}},"controlId":"{{font.GetProperty("id").GetString()}}","text":"Consolas","replace":true}""",
                TimeSpan.FromSeconds(20), CancellationToken.None);
            using JsonDocument? revealed = await host.SendAsync(
                $$"""{"cmd":"reveal","hwnd":{{window}},"aliases":["Elemento 250"],"direction":"down","amount":40}""",
                TimeSpan.FromSeconds(30), CancellationToken.None);
            TestContext.Out.WriteLine($"campo: {replaced!.RootElement}");
            TestContext.Out.WriteLine($"combo: {chosen!.RootElement}");
            TestContext.Out.WriteLine($"revelar: {revealed!.RootElement}");
            Assert.Multiple(() =>
            {
                Assert.That(width.GetProperty("nameSource").GetString(), Is.EqualTo("nearText"));
                Assert.That(replaced.RootElement.GetProperty("delivered").GetBoolean(), Is.True, "1366 → 800 by SetValue");
                Assert.That(chosen.RootElement.GetProperty("delivered").GetBoolean(), Is.True, "the combo's entry by pattern");
                Assert.That(revealed.RootElement.GetProperty("visible").GetBoolean(), Is.True, "the 250th row in view");
                Assert.That(GetForegroundWindow(), Is.EqualTo(front), "the person's front never moved");
            });
        }
        finally
        {
            try
            {
                if (!form.HasExited)
                    form.Kill();
            }
            catch (InvalidOperationException)
            {
            }

            File.Delete(script);
        }
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern nint FindWindowW(string? className, string windowName);

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();
}
