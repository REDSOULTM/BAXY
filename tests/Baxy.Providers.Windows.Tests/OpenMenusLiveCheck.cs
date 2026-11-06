using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Open menus on the real desktop with windows of the test's own. A WPF menu opens as a top-level tool window of type Window
/// with the Menu inside it (agent-desktop <c>probes/windows/FINDINGS.md</c> A23): <c>Get-OpenMenus</c> counts it, opened here by
/// the window itself, and does not count a tooltip, another tool window. The «menu» manner cannot open that menu: ShowContextMenu
/// answers S_OK with no event and WM_CONTEXTMENU is ignored, so the answer stays without <c>opened</c>. A classic edit control
/// ignores ShowContextMenu too and opens on WM_CONTEXTMENU. Never runs in a suite: Explicit and BAXY_CU_MENUS_LIVE=1; its windows
/// close by exact process id.
/// </summary>
[TestFixture]
[Explicit("Opens windows on the person's desktop and menus in them.")]
[Category("LiveDesktop")]
public sealed class OpenMenusLiveCheck
{
    private const string WpfScript = """
        param([string]$Title)
        Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
        $w=New-Object System.Windows.Window
        $w.Title=$Title; $w.Width=420; $w.Height=300; $w.Left=520; $w.Top=260
        $sp=New-Object System.Windows.Controls.StackPanel
        $with=New-Object System.Windows.Controls.Button; $with.Content='Con menu'
        $menu=New-Object System.Windows.Controls.ContextMenu
        foreach($n in 'Copiar','Pegar'){ $i=New-Object System.Windows.Controls.MenuItem; $i.Header=$n; [void]$menu.Items.Add($i) }
        $menu.PlacementTarget=$with; $menu.Placement='Bottom'; $menu.StaysOpen=$true
        $with.ContextMenu=$menu
        [void]$sp.Children.Add($with)
        $opener=New-Object System.Windows.Controls.Button; $opener.Content='Abrir menu'
        $opener.Add_Click({ $menu.IsOpen=$true })
        [void]$sp.Children.Add($opener)
        $tip=New-Object System.Windows.Controls.ToolTip; $tip.Content='Solo un aviso'; $tip.PlacementTarget=$with; $tip.Placement='Bottom'; $tip.StaysOpen=$true
        $tipper=New-Object System.Windows.Controls.Button; $tipper.Content='Abrir aviso'
        $tipper.Add_Click({ $tip.IsOpen=$true })
        [void]$sp.Children.Add($tipper)
        $without=New-Object System.Windows.Controls.Button; $without.Content='Sin menu'
        [void]$sp.Children.Add($without)
        $w.Content=$sp
        [void]$w.ShowDialog()
        """;

    private const string ClassicScript = """
        param([string]$Title)
        Add-Type -AssemblyName System.Windows.Forms
        $f=New-Object System.Windows.Forms.Form; $f.Text=$Title; $f.StartPosition='Manual'; $f.Left=60; $f.Top=260
        $f.Width=420; $f.Height=220
        $t=New-Object System.Windows.Forms.TextBox; $t.AccessibleName='Campo'; $t.Dock='Top'; $f.Controls.Add($t)
        [System.Windows.Forms.Application]::Run($f)
        """;

    // The worker's own Get-OpenMenus, with its native class, around a press of a button of the window that opens something.
    private const string CountScript = """
        $ErrorActionPreference='Stop'
        Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase
        $text=[IO.File]::ReadAllText($env:BAXY_MENUS_WORKER)
        $tokens=$null;$errors=$null
        $ast=[System.Management.Automation.Language.Parser]::ParseInput($text,[ref]$tokens,[ref]$errors)
        $native=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.StringConstantExpressionAst] -and $node.Value.Contains('public static class BaxyUiaWorkerNative') },$true))[0].Value
        Add-Type -ReferencedAssemblies Accessibility -TypeDefinition $native
        foreach($name in 'Get-ToolMenuRects','Get-OpenMenus'){
          $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name },$true))
          if($found.Count -gt 0){ Invoke-Expression $found[0].Extent.Text }
        }
        $AE=[System.Windows.Automation.AutomationElement]
        $null=$AE::RootElement
        $hwnd=[IntPtr][long]$env:BAXY_MENUS_WINDOW
        $root=$AE::FromHandle($hwnd)
        function Named($name){ return $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition($AE::NameProperty,$name))) }
        $el=Named 'Con menu'
        $process=[int]$el.Current.ProcessId
        $before=Get-OpenMenus $root $process $el
        (Named $env:BAXY_MENUS_OPENER).GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
        Start-Sleep -Milliseconds 700
        $after=Get-OpenMenus $root $process $el
        [Console]::Out.Write("$before,$after")
        """;

    [TestCase("Abrir menu", "0,1")]
    [TestCase("Abrir aviso", "0,0")]
    public async Task AWpfMenuIsCountedOpenAndATooltipIsNot(string opener, string expected)
    {
        Skip();
        string tag = Guid.NewGuid().ToString("N")[..6];
        string title = "BAXY menus wpf " + tag;
        string folder = Folder(tag);
        using Process target = Start(folder, "wpf.ps1", WpfScript, title);
        try
        {
            nint window = await FindAsync(title);
            Assert.That(window, Is.Not.EqualTo((nint)0), "the window appeared");
            string answer = Count(window, opener);
            TestContext.Out.WriteLine($"{opener}: antes,despues {answer}");
            Assert.That(answer, Is.EqualTo(expected));
        }
        finally
        {
            Kill(target);
            TryDelete(folder);
        }
    }

    [TestCase("Con menu")]
    [TestCase("Sin menu")]
    public async Task TheMannerOpensNoWpfMenuAndSaysNothingOpened(string label)
    {
        Skip();
        string tag = Guid.NewGuid().ToString("N")[..6];
        string title = "BAXY menus wpf " + tag;
        string folder = Folder(tag);
        using Process target = Start(folder, "wpf.ps1", WpfScript, title);
        try
        {
            nint window = await FindAsync(title);
            Assert.That(window, Is.Not.EqualTo((nint)0), "the window appeared");
            using var host = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            (JsonElement answer, long milliseconds) = await PressMenuAsync(host, window, label);
            TestContext.Out.WriteLine($"{label}: {milliseconds} ms {answer.GetRawText()}");
            Assert.That(answer.TryGetProperty("opened", out JsonElement read) && read.ValueKind == JsonValueKind.True, Is.False, "opened");
        }
        finally
        {
            Kill(target);
            TryDelete(folder);
        }
    }

    [Test]
    public async Task AClassicContextMenuIsOpenedAndReadOpen()
    {
        Skip();
        string tag = Guid.NewGuid().ToString("N")[..6];
        string title = "BAXY menus clasico " + tag;
        string folder = Folder(tag);
        using Process target = Start(folder, "clasico.ps1", ClassicScript, title);
        try
        {
            nint window = await FindAsync(title);
            Assert.That(window, Is.Not.EqualTo((nint)0), "the window appeared");
            using var host = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            (JsonElement answer, long milliseconds) = await PressMenuAsync(host, window, "Campo");
            TestContext.Out.WriteLine($"Campo: {milliseconds} ms {answer.GetRawText()}");
            Assert.That(answer.TryGetProperty("opened", out JsonElement read) && read.ValueKind == JsonValueKind.True, Is.True, "opened");
        }
        finally
        {
            Kill(target);
            TryDelete(folder);
        }
    }

    private static void Skip()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_MENUS_LIVE") != "1")
            Assert.Ignore("BAXY_CU_MENUS_LIVE=1 is needed to touch the desktop.");
    }

    private static string Count(nint window, string opener)
    {
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
            start.ArgumentList.Add(argument);
        start.ArgumentList.Add(Convert.ToBase64String(Encoding.Unicode.GetBytes(CountScript)));
        start.Environment["BAXY_MENUS_WORKER"] = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        start.Environment["BAXY_MENUS_WINDOW"] = window.ToString(System.Globalization.CultureInfo.InvariantCulture);
        start.Environment["BAXY_MENUS_OPENER"] = opener;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        Task<string> answer = process.StandardOutput.ReadToEndAsync();
        if (!process.WaitForExit(60_000))
        {
            process.Kill();
            Assert.Fail("the count answers within 60 s");
        }

        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        return answer.Result;
    }

    // The control's identity from a look at the window, then the manner by that identity, as the adapter sends it.
    private static async Task<(JsonElement Answer, long Milliseconds)> PressMenuAsync(UiaWorkerHost host, nint window, string label)
    {
        using JsonDocument? view = await host.SendAsync(
            $$"""{"cmd":"view","hwnd":{{window}},"limit":40}""", TimeSpan.FromSeconds(30), CancellationToken.None);
        JsonElement control = view!.RootElement.GetProperty("controls").EnumerateArray()
            .First(item => item.GetProperty("name").GetString() == label);
        var clock = Stopwatch.StartNew();
        using JsonDocument? pressed = await host.SendAsync(
            new System.Text.Json.Nodes.JsonObject
            {
                ["cmd"] = "click",
                ["hwnd"] = window,
                ["aliases"] = new System.Text.Json.Nodes.JsonArray(label),
                ["controlId"] = control.GetProperty("id").GetString(),
                ["manner"] = "menu",
            }.ToJsonString(), TimeSpan.FromSeconds(30), CancellationToken.None);
        return (pressed!.RootElement.Clone(), clock.ElapsedMilliseconds);
    }

    private static string Folder(string tag)
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-menus-" + tag);
        Directory.CreateDirectory(folder);
        return folder;
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
        for (int attempt = 0; attempt < 120; attempt++)
        {
            nint window = FindWindowW(null, title);
            if (window != 0)
                return window;
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

    private static void TryDelete(string folder)
    {
        try
        {
            Directory.Delete(folder, recursive: true);
        }
        catch (IOException)
        {
        }
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern nint FindWindowW(string? className, string windowName);
}
