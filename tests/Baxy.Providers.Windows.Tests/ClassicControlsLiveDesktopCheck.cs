using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Goal v3, analysis r3a M1 and M5, measured on the desktop: classic Win32 windows of the system opened minimized and
/// without activation (never in front) are read with their common controls as themselves, through the worker's
/// client-side providers: the character table's combo boxes, buttons and list items, the system information's tree
/// items; and a file manager whose title is the folder it shows is found by its executable's description. Never runs
/// in a suite: Explicit and BAXY_CU_ARBOL_LIVE_CHECK=1. Run it only with the desktop turn (scripts/cu_live/turno.sh
/// tomar: its agent lock first, then no live.lock); it closes what it opened by its exact process id.
/// </summary>
[TestFixture]
[Explicit("Opens windows on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class ClassicControlsLiveDesktopCheck
{
    [Test]
    public async Task ClassicControlsAreReadAsThemselvesWithoutTheFront()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_ARBOL_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_CU_ARBOL_LIVE_CHECK=1 is needed to touch the desktop.");
        string system = Environment.GetFolderPath(Environment.SpecialFolder.System);
        nint front = GetForegroundWindow();
        var opened = new List<int>();
        try
        {
            using var host = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            (nint table, int tableProcess) = await OpenQuietlyAsync(Path.Combine(system, "charmap.exe"), opened);
            (nint information, _) = await OpenQuietlyAsync(Path.Combine(system, "msinfo32.exe"), opened);
            await Task.Delay(TimeSpan.FromSeconds(3));
            JsonElement[] tableControls = await ViewAsync(host, table);
            JsonElement[] informationControls = await ViewAsync(host, information);
            TestContext.Out.WriteLine("tabla: " + Kinds(tableControls));
            TestContext.Out.WriteLine("informacion: " + Kinds(informationControls));

            string manager = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "7-Zip", "7zFM.exe");
            nint byDescription = 0;
            nint managerWindow = 0;
            if (File.Exists(manager))
            {
                (managerWindow, _) = await OpenQuietlyAsync(manager, opened);
                byDescription = await VisibleControlSurface.ResolveTitledWindowAsync("7-Zip File Manager", CancellationToken.None);
                TestContext.Out.WriteLine($"gestor: titulo «{VisibleControlSurface.WindowTitle(managerWindow)}»");
            }

            Assert.Multiple(() =>
            {
                Assert.That(tableProcess, Is.GreaterThan(0));
                Assert.That(tableControls.Count(control => Kind(control) == "ComboBox"), Is.GreaterThanOrEqualTo(1), "the font combo box");
                Assert.That(tableControls.Count(control => Kind(control) == "Button"), Is.GreaterThanOrEqualTo(1));
                Assert.That(tableControls.Count(control => Kind(control) == "Pane"), Is.LessThan(tableControls.Length / 2),
                    "classic controls are no longer opaque panes");
                Assert.That(informationControls.Count(control => Kind(control) == "TreeItem"), Is.GreaterThanOrEqualTo(1), "the categories tree");
                // Another window of the same manager may be on top of the one opened here: any of its windows will do.
                if (managerWindow != 0)
                {
                    Assert.That(byDescription, Is.Not.EqualTo((nint)0), "found by its executable's description");
                    Assert.That(VisibleControlSurface.ProcessDescription(WindowProcessId(byDescription)), Is.EqualTo("7-Zip File Manager"));
                }
                Assert.That(GetForegroundWindow(), Is.EqualTo(front), "the person's front never moved");
            });
        }
        finally
        {
            foreach (int id in opened)
            {
                try
                {
                    using Process process = Process.GetProcessById(id);
                    process.Kill();
                }
                catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
                    or System.ComponentModel.Win32Exception)
                {
                }
            }
        }
    }

    /// <summary>
    /// Pasada r15b (v3-27, v3-28, v3-29) on the character table opened behind the person's window: its buttons that wait
    /// for text («Copy», disabled while the field is empty) are listed apart as disabled, and its closed font list is set
    /// to a value by its field (the entry chosen by pattern) without the front, the character shown changing with it.
    /// </summary>
    [Test]
    public async Task DisabledButtonsAreListedAndAClosedListIsSetBehind()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_ARBOL_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_CU_ARBOL_LIVE_CHECK=1 is needed to touch the desktop.");
        string system = Environment.GetFolderPath(Environment.SpecialFolder.System);
        nint front = GetForegroundWindow();
        var opened = new List<int>();
        try
        {
            using var host = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            (nint table, _) = await OpenQuietlyAsync(Path.Combine(system, "charmap.exe"), opened);
            await Task.Delay(TimeSpan.FromSeconds(2));
            VisibleControlSurface.ShowBehind(table);
            using JsonDocument? view = await host.SendAsync(
                $$"""{"cmd":"view","hwnd":{{table}},"limit":60}""", TimeSpan.FromSeconds(30), CancellationToken.None);
            JsonElement root = view!.RootElement;
            JsonElement[] disabled = root.TryGetProperty("disabled", out JsonElement listed)
                ? [.. listed.EnumerateArray().Select(item => item.Clone())]
                : [];
            TestContext.Out.WriteLine("disabled: " + string.Join(" | ", disabled.Select(item => item.GetRawText())));
            JsonElement font = root.GetProperty("controls").EnumerateArray()
                .First(control => Kind(control) == "ComboBox" && control.GetProperty("name").GetString() == "Fuente:");
            string Shown(JsonElement look) => string.Join(" | ", look.GetProperty("controls").EnumerateArray()
                .Select(control => control.GetProperty("name").GetString() ?? string.Empty)
                .Where(name => name.StartsWith("U+", StringComparison.Ordinal)));
            string before = Shown(root);
            using JsonDocument? set = await host.SendAsync(
                new System.Text.Json.Nodes.JsonObject
                {
                    ["cmd"] = "field",
                    ["hwnd"] = table,
                    ["controlId"] = font.GetProperty("id").GetString(),
                    ["text"] = "Wingdings",
                    ["replace"] = true,
                }.ToJsonString(), TimeSpan.FromSeconds(30), CancellationToken.None);
            TestContext.Out.WriteLine("field: " + set?.RootElement.GetRawText());
            await Task.Delay(400);
            using JsonDocument? again = await host.SendAsync(
                $$"""{"cmd":"view","hwnd":{{table}},"limit":60}""", TimeSpan.FromSeconds(30), CancellationToken.None);
            string after = Shown(again!.RootElement);
            TestContext.Out.WriteLine($"shown before «{before}» after «{after}»");
            Assert.Multiple(() =>
            {
                Assert.That(disabled.Any(item => Kind(item) == "Button" && item.GetProperty("state").GetString() == "disabled"),
                    Is.True, "a button that waits for text is listed as disabled");
                Assert.That(set?.RootElement.GetProperty("method").GetString(), Is.EqualTo("select"));
                Assert.That(set?.RootElement.GetProperty("delivered").GetBoolean(), Is.True);
                Assert.That(GetForegroundWindow(), Is.EqualTo(front), "the person's front never moved");
            });
        }
        finally
        {
            foreach (int id in opened)
            {
                try
                {
                    using Process process = Process.GetProcessById(id);
                    process.Kill();
                }
                catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
                    or System.ComponentModel.Win32Exception)
                {
                }
            }
        }
    }

    /// <summary>
    /// Live 2026-10-08 (regresión r4, todos los casos de un lanzador de juegos CEF): with the whole client-side provider
    /// assembly registered, its catch-all native MSAA bridge walked the CEF content node by node across processes and
    /// the view ran out of its 20 s. An application already open whose window has no UI Automation tree of its own
    /// (BAXY_CU_VIEW_APP, its title) is viewed behind the person's window in under 3 s, with the text it draws.
    /// </summary>
    [Test]
    public async Task AWindowWithoutItsOwnTreeIsViewedQuicklyFromWhatItDraws()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_ARBOL_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_CU_ARBOL_LIVE_CHECK=1 is needed to touch the desktop.");
        string? application = Environment.GetEnvironmentVariable("BAXY_CU_VIEW_APP");
        if (string.IsNullOrWhiteSpace(application))
            Assert.Ignore("BAXY_CU_VIEW_APP names an open application whose window has no tree of its own.");
        nint front = GetForegroundWindow();
        using var adapter = new WindowsVisibleControlAdapter();
        await adapter.PrewarmAsync();
        var watch = Stopwatch.StartNew();
        ExternalCapabilityReceipt view = await adapter.InvokeAsync(
            "input.visible.controls",
            JsonDocument.Parse(JsonSerializer.Serialize(new { application })).RootElement,
            CancellationToken.None);
        long elapsed = watch.ElapsedMilliseconds;
        string text = view.Result is { ValueKind: JsonValueKind.Object } result
            && result.TryGetProperty("text", out JsonElement written)
                ? written.GetRawText()
                : string.Empty;
        TestContext.Out.WriteLine($"view_ms={elapsed} ok={view.Verified} error={view.ErrorCode} text={text}");
        TestContext.Out.WriteLine("view=" + view.Result?.GetRawText());
        Assert.Multiple(() =>
        {
            Assert.That(view.ErrorCode, Is.Null);
            Assert.That(elapsed, Is.LessThan(3000));
            Assert.That(text, Does.Match("\\p{L}{3,}"), "the text the window draws");
            Assert.That(GetForegroundWindow(), Is.EqualTo(front), "the person's front never moved");
        });
    }

    private static string Kinds(JsonElement[] controls) =>
        string.Join(", ", controls.GroupBy(Kind).Select(group => group.Key + "=" + group.Count()))
        + " | " + string.Join(" | ", controls.Take(25).Select(control => Kind(control) + ":" + control.GetProperty("name").GetString()));

    private static string Kind(JsonElement control) => control.GetProperty("kind").GetString() ?? string.Empty;

    private static async Task<JsonElement[]> ViewAsync(UiaWorkerHost host, nint window)
    {
        VisibleControlSurface.ShowBehind(window);
        using JsonDocument? view = await host.SendAsync(
            $$"""{"cmd":"view","hwnd":{{window}},"limit":60}""", TimeSpan.FromSeconds(30), CancellationToken.None);
        Assert.That(view?.RootElement.GetProperty("ok").GetBoolean(), Is.True);
        Assert.That(view!.RootElement.GetProperty("clientProviders").GetBoolean(), Is.True);
        return [.. view.RootElement.GetProperty("controls").EnumerateArray().Select(control => control.Clone())];
    }

    // Started minimized and not activated (STARTF_USESHOWWINDOW with SW_SHOWMINNOACTIVE): never in front.
    private static async Task<(nint Window, int ProcessId)> OpenQuietlyAsync(string executable, List<int> opened)
    {
        var startup = new StartupInfo { Size = Marshal.SizeOf<StartupInfo>(), Flags = 1, ShowWindow = 7 };
        Assert.That(CreateProcessW(null, "\"" + executable + "\"", 0, 0, false, 0, 0, null, ref startup, out ProcessInformation information),
            Is.True, executable);
        _ = CloseHandle(information.Process);
        _ = CloseHandle(information.Thread);
        opened.Add(information.ProcessId);
        for (int attempt = 0; attempt < 80; attempt++)
        {
            nint window = VisibleControlSurface.LargestTopLevelWindow(information.ProcessId);
            if (window != 0)
                return (window, information.ProcessId);
            await Task.Delay(250);
        }

        Assert.Fail("no window for " + executable);
        return (0, 0);
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct StartupInfo
    {
        public int Size;
        public string? Reserved;
        public string? Desktop;
        public string? Title;
        public int X, Y, XSize, YSize, XCountChars, YCountChars, FillAttribute, Flags;
        public short ShowWindow, Reserved2;
        public nint Reserved3, StdInput, StdOutput, StdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ProcessInformation
    {
        public nint Process, Thread;
        public int ProcessId, ThreadId;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CreateProcessW(string? application, string commandLine, nint processAttributes,
        nint threadAttributes, bool inherit, int flags, nint environment, string? directory, ref StartupInfo startup,
        out ProcessInformation information);

    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(nint handle);

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint processId);

    private static uint WindowProcessId(nint window)
    {
        _ = GetWindowThreadProcessId(window, out uint processId);
        return processId;
    }
}
