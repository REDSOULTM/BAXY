using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// C1 on the real desktop through the real worker: WinForms, WPF and Chromium windows of the test's own behind a person's
/// window of the test's own. A pattern call on them goes through the COM client with AutoSetFocus off (agent-desktop #567),
/// so the target never takes the front (read every 5 ms during the call) and its effect shows in the target's title.
/// Contracase: a classic WinForms button is pressed by the in-process client-side provider, which asks for the front itself
/// (VK 0xB9 from outside UIAutomationCore): AutoSetFocus does not reach it, and BaxyFrontKeeper gives the front back. Never
/// runs in a suite: Explicit and BAXY_CU_SIN_ROBO_LIVE=1; its windows close by exact process id.
/// </summary>
[TestFixture]
[Explicit("Opens windows on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class UiaSinRoboLiveCheck
{
    private const string WinFormsScript = """
        param([string]$Title)
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -ReferencedAssemblies System.Windows.Forms -TypeDefinition @"
        public class SinRoboForm : System.Windows.Forms.Form { protected override bool ShowWithoutActivation { get { return true; } } }
        "@
        $script:n=0; $script:index=-1
        $f=New-Object SinRoboForm; $f.StartPosition='Manual'; $f.Left=300; $f.Top=120; $f.Width=520; $f.Height=420
        function Show-Count { $f.Text=('{0} n={1}' -f $Title,$script:n) }
        Show-Count
        $b=New-Object System.Windows.Forms.Button; $b.Text='Pulsar'; $b.Left=10; $b.Top=10; $b.Width=120
        $t=New-Object System.Windows.Forms.TextBox; $t.AccessibleName='Campo'; $t.Left=10; $t.Top=50; $t.Width=300
        $l=New-Object System.Windows.Forms.ListBox; $l.AccessibleName='Lista'; $l.Left=10; $l.Top=90; $l.Width=200; $l.Height=90
        foreach($i in 'Uno','Dos','Tres'){ [void]$l.Items.Add($i) }
        $f.Controls.AddRange(@($b,$t,$l))
        $b.Add_Click({ $script:n++; Show-Count })
        $t.Add_TextChanged({ $script:n++; Show-Count })
        $timer=New-Object System.Windows.Forms.Timer; $timer.Interval=50
        $timer.Add_Tick({ if($l.SelectedIndex -ne $script:index){ $script:index=$l.SelectedIndex; $script:n++; Show-Count } })
        $timer.Start()
        [System.Windows.Forms.Application]::Run($f)
        """;

    private const string PersonScript = """
        param([string]$Title)
        Add-Type -AssemblyName System.Windows.Forms
        $f=New-Object System.Windows.Forms.Form; $f.Text=$Title; $f.StartPosition='Manual'; $f.Left=60; $f.Top=60; $f.Width=520; $f.Height=420
        [System.Windows.Forms.Application]::Run($f)
        """;

    private const string Page = """
        <!doctype html><html lang="es"><head><meta charset="utf-8"><title>inicio</title></head><body>
        <button id="b">Pulsar</button><br><input id="t" type="text" aria-label="Campo"><br>
        <input id="c" type="checkbox" aria-label="Marca"><br>
        <select id="l" size="3" aria-label="Lista"><option>Uno</option><option>Dos</option><option>Tres</option></select>
        <script>
        const tag=new URLSearchParams(location.search).get('tag'); let n=0;
        function show(){ document.title=tag+' n='+n; } function effect(){ n++; show(); } show();
        document.getElementById('b').addEventListener('click',effect);
        document.getElementById('t').addEventListener('input',effect);
        document.getElementById('c').addEventListener('change',effect);
        document.getElementById('l').addEventListener('change',effect);
        </script></body></html>
        """;

    [Test]
    public async Task ThePatternsActBehindWithoutTheTargetTakingTheFront()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_SIN_ROBO_LIVE") != "1")
            Assert.Ignore("BAXY_CU_SIN_ROBO_LIVE=1 is needed to touch the desktop.");
        string browser = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Microsoft", "Edge", "Application", "msedge.exe");
        Assume.That(File.Exists(browser), "a Chromium browser is installed");
        string tag = Guid.NewGuid().ToString("N")[..6];
        string folder = Path.Combine(Path.GetTempPath(), "baxy-sin-robo-" + tag);
        Directory.CreateDirectory(folder);
        string forms = "BAXY sin robo forms " + tag;
        string web = "BAXYsinroboweb" + tag;
        string person = "BAXY sin robo persona " + tag;
        using Process formsProcess = Start(folder, "forms.ps1", WinFormsScript, forms);
        string page = Path.Combine(folder, "pagina.html");
        await File.WriteAllTextAsync(page, Page, new UTF8Encoding(false));
        string profile = Path.Combine(folder, "perfil");
        var chromium = new ProcessStartInfo(browser) { UseShellExecute = false };
        // Without the occlusion check: a Chromium window wholly covered by another one shows no page to UI Automation.
        foreach (string argument in new[]
                 {
                     "--user-data-dir=" + profile, "--no-first-run", "--no-default-browser-check", "--force-renderer-accessibility",
                     "--disable-features=CalculateNativeWinOcclusion", "--window-position=420,280", "--window-size=520,420",
                     "--app=file:///" + page.Replace('\\', '/') + "?tag=" + web,
                 })
            chromium.ArgumentList.Add(argument);
        using Process webProcess = Process.Start(chromium)!;
        using Process personProcess = Start(folder, "persona.ps1", PersonScript, person);
        try
        {
            nint formsWindow = await FindAsync(forms);
            nint webWindow = await FindAsync(web);
            nint personWindow = await FindAsync(person);
            Assert.That(new[] { formsWindow, webWindow, personWindow }, Has.None.Zero, "the windows appeared");
            using var host = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using JsonDocument? ping = await host.SendAsync("""{"cmd":"ping"}""", TimeSpan.FromSeconds(30), CancellationToken.None);
            Assert.That(ping?.RootElement.GetProperty("ok").GetBoolean(), Is.True);
            Dictionary<string, string> formsIds = await IdsAsync(host, formsWindow, ["Campo", "Dos", "Pulsar"]);
            Dictionary<string, string> webIds = await IdsAsync(host, webWindow, ["Pulsar", "Campo", "Marca", "Dos"]);
            await Task.Delay(1500);
            bool fronted = false;
            for (int attempt = 0; attempt < 20 && !fronted; attempt++)
            {
                fronted = VisibleControlSurface.BringToFront(personWindow);
                if (!fronted)
                    await Task.Delay(100);
            }

            // Another session, or an invisible window of a service (documentacion/computer-use/FRENTE_VENTANA_INVISIBLE.md), holds it.
            if (!fronted)
                Assert.Inconclusive("the person's window could not take the front: nothing was measured");
            await Task.Delay(800);
            var quiet = new List<string>();
            async Task ActAsync(nint window, IReadOnlyDictionary<string, string> ids, string label, bool field, List<string> into)
            {
                int before = Count(window);
                // The front read every 5 ms while the call runs and for the tail after it: a theft given back at once counts.
                using var watching = new CancellationTokenSource();
                bool taken = false;
                Task watch = Task.Run(async () =>
                {
                    while (!watching.IsCancellationRequested)
                    {
                        taken |= GetForegroundWindow() == window;
                        await Task.Delay(5, CancellationToken.None);
                    }
                }, CancellationToken.None);
                using JsonDocument? answer = await host.SendAsync(
                    field ? Field(window, ids[label], "valor") : Click(window, ids[label], label),
                    TimeSpan.FromSeconds(20), CancellationToken.None);
                await Task.Delay(500);
                await watching.CancelAsync();
                await watch;
                string facts = answer?.RootElement.GetRawText() ?? "null";
                TestContext.Out.WriteLine($"{label}: efecto {before}->{Count(window)} frente {(taken ? "tomado" : "quieto")} {facts}");
                into.Add($"{label}|{Count(window) > before}|{taken}");
            }

            await ActAsync(formsWindow, formsIds, "Campo", true, quiet);
            await ActAsync(formsWindow, formsIds, "Dos", false, quiet);
            await ActAsync(webWindow, webIds, "Pulsar", false, quiet);
            await ActAsync(webWindow, webIds, "Campo", true, quiet);
            await ActAsync(webWindow, webIds, "Marca", false, quiet);
            await ActAsync(webWindow, webIds, "Dos", false, quiet);
            var netted = new List<string>();
            await ActAsync(formsWindow, formsIds, "Pulsar", false, netted);
            nint frontAtEnd = GetForegroundWindow();
            Assert.Multiple(() =>
            {
                Assert.That(quiet, Is.EqualTo(new[]
                {
                    "Campo|True|False", "Dos|True|False", "Pulsar|True|False", "Campo|True|False", "Marca|True|False", "Dos|True|False",
                }), "each pattern acted and no target took the front");
                Assert.That(netted[0], Does.StartWith("Pulsar|True"), "the classic button was pressed");
                Assert.That(frontAtEnd, Is.EqualTo(personWindow), "the person's window is in front at the end");
            });
        }
        finally
        {
            Kill(formsProcess);
            Kill(personProcess);
            int[] webFamily = Descendants(webProcess.Id);
            Kill(webProcess);
            foreach (int id in webFamily)
            {
                try
                {
                    using Process rest = Process.GetProcessById(id);
                    Kill(rest);
                }
                catch (ArgumentException)
                {
                }
            }

            await Task.Delay(500);
            try { Directory.Delete(folder, recursive: true); } catch (IOException) { } catch (UnauthorizedAccessException) { }
        }
    }

    private static string Click(nint window, string id, string label) => new JsonObject
    {
        ["cmd"] = "click", ["hwnd"] = window, ["aliases"] = new JsonArray(label), ["controlId"] = id,
    }.ToJsonString();

    private static string Field(nint window, string id, string text) => new JsonObject
    {
        ["cmd"] = "field", ["hwnd"] = window, ["controlId"] = id, ["text"] = text, ["replace"] = true,
    }.ToJsonString();

    private static async Task<Dictionary<string, string>> IdsAsync(UiaWorkerHost host, nint window, string[] labels)
    {
        var ids = new Dictionary<string, string>();
        for (int look = 0; look < 15 && ids.Count < labels.Length; look++)
        {
            using JsonDocument? view = await host.SendAsync(
                $$"""{"cmd":"view","hwnd":{{window}},"limit":60}""", TimeSpan.FromSeconds(30), CancellationToken.None);
            foreach (JsonElement control in view!.RootElement.GetProperty("controls").EnumerateArray())
            {
                string name = control.GetProperty("name").GetString() ?? string.Empty;
                if (labels.Contains(name))
                    ids[name] = control.GetProperty("id").GetString() ?? string.Empty;
            }

            if (ids.Count < labels.Length)
                await Task.Delay(1000);
        }

        Assert.That(ids.Keys, Is.SupersetOf(labels), "the look lists the controls");
        return ids;
    }

    private static string Title(nint window)
    {
        char[] text = new char[256];
        int length = GetWindowTextW(window, text, text.Length);
        return new string(text, 0, Math.Max(0, length));
    }

    private static int Count(nint window)
    {
        Match count = Regex.Match(Title(window), @"n=(\d+)");
        return count.Success ? int.Parse(count.Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture) : -1;
    }

    // The processes the browser this test started has started, by their exact ids, read before that browser closes.
    private static int[] Descendants(int root)
    {
        var start = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true };
        string query = "Get-CimInstance Win32_Process | ForEach-Object { \"$($_.ProcessId) $($_.ParentProcessId)\" }";
        foreach (string argument in new[] { "-NoProfile", "-Command", query })
            start.ArgumentList.Add(argument);
        using Process process = Process.Start(start)!;
        string[] lines = process.StandardOutput.ReadToEnd().Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        process.WaitForExit(10_000);
        int[][] pairs = [.. lines.Select(line => line.Split(' ').Select(part => int.Parse(part, System.Globalization.CultureInfo.InvariantCulture)).ToArray())];
        var found = new List<int> { root };
        for (int index = 0; index < found.Count; index++)
            found.AddRange(pairs.Where(pair => pair[1] == found[index] && !found.Contains(pair[0])).Select(pair => pair[0]));
        return [.. found];
    }

    private static Process Start(string folder, string name, string script, string title)
    {
        string path = Path.Combine(folder, name);
        File.WriteAllText(path, script, new UTF8Encoding(false));
        var start = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true };
        foreach (string argument in new[] { "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", path, "-Title", title })
            start.ArgumentList.Add(argument);
        return Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
    }

    private static async Task<nint> FindAsync(string title)
    {
        for (int attempt = 0; attempt < 200; attempt++)
        {
            nint found = 0;
            _ = EnumWindows((window, _) =>
            {
                if (IsWindowVisible(window) && Title(window).Contains(title, StringComparison.Ordinal))
                {
                    found = window;
                    return false;
                }

                return true;
            }, 0);
            if (found != 0)
                return found;
            await Task.Delay(100);
        }

        return 0;
    }

    private static void Kill(Process process)
    {
        try
        {
            if (!process.HasExited)
                process.Kill();
        }
        catch (InvalidOperationException)
        {
        }
    }

    private delegate bool EnumWindowsProc(nint window, nint value);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc callback, nint value);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(nint window);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowTextW(nint window, [Out] char[] text, int size);

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();
}
