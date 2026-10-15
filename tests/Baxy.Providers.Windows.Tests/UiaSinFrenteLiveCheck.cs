using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Goal v3 point 0, r4a M1 on the real desktop (the analyst's experiment, ported): a WPF window of the test's own sits
/// behind a person's window of the test's own, the simulated person types in theirs (marked keys), and the UIA worker
/// selects a list item and invokes a button of the WPF window by their patterns. Checked: the person's window receives
/// no key but the person's (its thread logs every keyboard message it takes; BAXY's marked bid for the foreground, taken
/// by the system as a hotkey, must never show there), a low-level hook sees no unmarked injection (the client's VK 0xB9
/// is dropped) and reports BAXY's marked injections apart, the person's window never loses the front for longer
/// than a transient (the net gives it back in milliseconds), both effects happen (SelectionChanged, Click), and each
/// press answers well under the client's 2 s wait. Two regimes (review of 1b9b736e7): the person typing (the client's key
/// is dropped) and the person quiet (the client hands the permission over without a key and the net gives the front
/// back). Then a drop-down behind is expanded and an entry chosen: the expand needs its window active (its list closes
/// otherwise), so the net lets that front go, and only the effect is checked there. Never runs in a suite: Explicit
/// and BAXY_CU_UIA_SIN_FRENTE_LIVE=1,
/// only with the desktop turn (no cu-v3/live.lock, an agent lock of its own); its windows close by exact process id.
/// </summary>
[TestFixture]
[Explicit("Opens windows on the person's desktop and types into its own.")]
[Category("LiveDesktop")]
public sealed class UiaSinFrenteLiveCheck
{
    private const uint SimulatedMark = 0x53494D55; // 'SIMU', as the harness's meter
    private const int TransientMs = 150;

    private const string TargetScript = """
        param([string]$Title,[string]$Log,[string]$Keys)
        Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase
        Add-Type -ReferencedAssemblies WindowsBase -TypeDefinition @"
        public static class BaxyTargetKeys {
          static string _path;
          public static void Attach(string path) {
            _path = path;
            System.Windows.Interop.ComponentDispatcher.ThreadFilterMessage += Seen;
          }
          static void Seen(ref System.Windows.Interop.MSG m, ref bool handled) {
            if (m.message >= 0x100 && m.message <= 0x107) System.IO.File.AppendAllText(_path, string.Format("0x{0:X} 0x{1:X}\n", m.message, m.wParam.ToInt64()));
          }
        }
        "@
        [BaxyTargetKeys]::Attach($Keys)
        $w=New-Object System.Windows.Window
        $w.Title=$Title; $w.Width=420; $w.Height=300; $w.Left=520; $w.Top=260; $w.ShowActivated=$false
        $sp=New-Object System.Windows.Controls.StackPanel
        $b=New-Object System.Windows.Controls.Button; $b.Content='Pulsar'; [void]$sp.Children.Add($b)
        $lb=New-Object System.Windows.Controls.ListBox
        foreach($n in 'Uno','Dos','Tres'){ $i=New-Object System.Windows.Controls.ListBoxItem; $i.Content=$n; [void]$lb.Items.Add($i) }
        [void]$sp.Children.Add($lb)
        $cb=New-Object System.Windows.Controls.ComboBox
        [System.Windows.Automation.AutomationProperties]::SetName($cb,'Colores')
        foreach($n in 'Rojo','Verde'){ $i=New-Object System.Windows.Controls.ComboBoxItem; $i.Content=$n; [void]$cb.Items.Add($i) }
        [void]$sp.Children.Add($cb)
        $w.Content=$sp
        $cb.Add_SelectionChanged({ Add-Content -Path $Log -Value ('combo {0}' -f $cb.SelectedIndex) })
        $lb.Add_SelectionChanged({ Add-Content -Path $Log -Value ('seleccion {0}' -f $lb.SelectedIndex) })
        $b.Add_Click({ Add-Content -Path $Log -Value 'click' })
        [void]$w.ShowDialog()
        """;

    // The person's window logs every keyboard message its thread takes from its queue (WM_KEYDOWN to WM_SYSDEADCHAR):
    // what a key that reached it looks like there, whoever injected it.
    private const string PersonScript = """
        param([string]$Title,[string]$Keys)
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -ReferencedAssemblies System.Windows.Forms -TypeDefinition @"
        public class BaxyPersonKeys : System.Windows.Forms.IMessageFilter {
          public string Path;
          public bool PreFilterMessage(ref System.Windows.Forms.Message m) {
            if (m.Msg >= 0x100 && m.Msg <= 0x107) System.IO.File.AppendAllText(Path, string.Format("0x{0:X} 0x{1:X}\n", m.Msg, m.WParam.ToInt64()));
            return false;
          }
        }
        "@
        $k=New-Object BaxyPersonKeys; $k.Path=$Keys; [System.Windows.Forms.Application]::AddMessageFilter($k)
        $f=New-Object System.Windows.Forms.Form; $f.Text=$Title; $f.StartPosition='Manual'; $f.Left=40; $f.Top=560
        $f.Width=420; $f.Height=220
        $t=New-Object System.Windows.Forms.TextBox; $t.Multiline=$true; $t.Dock='Fill'; $f.Controls.Add($t)
        [System.Windows.Forms.Application]::Run($f)
        """;

    [TestCase(true)]
    [TestCase(false)]
    public async Task ThePatternsActBehindThePersonWithoutKeysOrTheft(bool typing)
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_UIA_SIN_FRENTE_LIVE") != "1")
            Assert.Ignore("BAXY_CU_UIA_SIN_FRENTE_LIVE=1 is needed to touch the desktop.");
        string tag = Guid.NewGuid().ToString("N")[..6];
        string folder = Path.Combine(Path.GetTempPath(), "baxy-uia-sin-frente-" + tag);
        Directory.CreateDirectory(folder);
        string effects = Path.Combine(folder, "efectos.log");
        string targetTitle = "BAXY uia sin frente objetivo " + tag;
        string personTitle = "BAXY uia sin frente persona " + tag;
        string targetKeys = Path.Combine(folder, "teclas-objetivo.log");
        using Process target = Start(folder, "objetivo.ps1", TargetScript, "-Title", targetTitle, "-Log", effects, "-Keys", targetKeys);
        await Task.Delay(1500);
        string personKeys = Path.Combine(folder, "teclas-persona.log");
        using Process person = Start(folder, "persona.ps1", PersonScript, "-Title", personTitle, "-Keys", personKeys);
        using var hook = new UnmarkedKeyHook();
        using var stop = new CancellationTokenSource();
        try
        {
            nint targetWindow = await FindAsync(targetTitle);
            nint personWindow = await FindAsync(personTitle);
            Assert.That(new[] { targetWindow, personWindow }, Has.None.Zero, "both windows appeared");
            bool fronted = false;
            for (int attempt = 0; attempt < 20 && !fronted; attempt++)
            {
                fronted = VisibleControlSurface.BringToFront(personWindow);
                if (!fronted)
                    await Task.Delay(100);
            }

            Assert.That(fronted, Is.True, "the person's window in front");
            using var host = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using JsonDocument? ping = await host.SendAsync("""{"cmd":"ping"}""", TimeSpan.FromSeconds(30), CancellationToken.None);
            Assert.That(ping?.RootElement.GetProperty("quietInput").GetString(), Is.EqualTo("on"), "the client's input is taken");

            // The simulated person types in their window every 125 ms (only while it is in front: never elsewhere).
            Task typist = Task.Run(async () =>
            {
                while (!stop.IsCancellationRequested)
                {
                    if (typing && GetForegroundWindow() == personWindow)
                        TypeMarked('a');
                    try { await Task.Delay(125, stop.Token); } catch (OperationCanceledException) { }
                }
            });
            var fronts = new FrontWatch(personWindow);
            Task watch = Task.Run(() => fronts.RunAsync(stop.Token));
            await Task.Delay(1000);

            var latencies = new List<long>();
            var answers = new List<string>();
            foreach (string label in new[] { "Dos", "Pulsar", "Tres" })
            {
                var clock = Stopwatch.StartNew();
                long sent = fronts.Now;
                using JsonDocument? answer = await host.SendAsync(
                    $$"""{"cmd":"click","hwnd":{{targetWindow}},"aliases":["{{label}}"],"controlId":""}""",
                    TimeSpan.FromSeconds(20), CancellationToken.None);
                latencies.Add(clock.ElapsedMilliseconds);
                fronts.Note($"{label} {sent}-{fronts.Now}");
                answers.Add(answer?.RootElement.ToString() ?? "null");
                await Task.Delay(700);
            }

            using JsonDocument? after = await host.SendAsync("""{"cmd":"ping"}""", TimeSpan.FromSeconds(10), CancellationToken.None);
            long longest = fronts.LongestMs;
            string timeline = fronts.Timeline;
            int excursions = fronts.Excursions;
            nint frontAtEnd = GetForegroundWindow();

            // The drop-down: expanded (the net lets that front go), then an entry chosen by its pattern.
            var combo = new List<string>();
            foreach (string label in new[] { "Colores", "Verde" })
            {
                using JsonDocument? answer = await host.SendAsync(
                    $$"""{"cmd":"click","hwnd":{{targetWindow}},"aliases":["{{label}}"],"controlId":""}""",
                    TimeSpan.FromSeconds(20), CancellationToken.None);
                combo.Add(answer?.RootElement.ToString() ?? "null");
                await Task.Delay(700);
            }

            await stop.CancelAsync();
            await Task.WhenAll(typist, watch);
            string[] seen = File.Exists(effects) ? await File.ReadAllLinesAsync(effects) : [];
            string[] received = File.Exists(personKeys) ? await File.ReadAllLinesAsync(personKeys) : [];
            // The target's window never gets a key either: no person types there, so every line would be BAXY's.
            string[] targetReceived = File.Exists(targetKeys) ? await File.ReadAllLinesAsync(targetKeys) : [];
            // The simulated person's own typing arrives as VK_PACKET (0xE7) down and up and its WM_CHAR 'a' (0x61).
            string[] notTheirs = [.. received.Where(line => line is not ("0x100 0xE7" or "0x101 0xE7" or "0x102 0x61"))];
            TestContext.Out.WriteLine($"regimen: {(typing ? "tecleando" : "quieta")} (persona hwnd={personWindow}, objetivo hwnd={targetWindow})");
            TestContext.Out.WriteLine($"desplegable: {string.Join(" | ", combo)}");
            TestContext.Out.WriteLine($"clics: {string.Join(" | ", answers)}");
            TestContext.Out.WriteLine($"latencias ms: {string.Join(", ", latencies)}");
            TestContext.Out.WriteLine($"efectos: {string.Join(", ", seen)}");
            TestContext.Out.WriteLine($"teclas recibidas por la ventana de la persona: {received.Length - notTheirs.Length} suyas, ajenas [{string.Join(", ", notTheirs)}]");
            TestContext.Out.WriteLine($"teclas recibidas por la ventana objetivo: [{string.Join(", ", targetReceived)}]");
            TestContext.Out.WriteLine($"inyecciones: sin marca [{string.Join(", ", hook.Unmarked)}], con la marca de BAXY [{string.Join(", ", hook.Baxy)}]");
            TestContext.Out.WriteLine($"frente ajeno: {excursions} excursiones, la mayor {longest} ms");
            TestContext.Out.WriteLine($"cronologia ms: {timeline}");
            TestContext.Out.WriteLine($"worker: {after?.RootElement}");
            Assert.Multiple(() =>
            {
                Assert.That(notTheirs, Is.Empty, "no key but the person's reached the person's window");
                Assert.That(targetReceived, Is.Empty, "no key reached the target's window");
                Assert.That(hook.Unmarked, Is.Empty, "the client's own key is never injected");
                Assert.That(seen, Does.Contain("seleccion 1").And.Contain("click").And.Contain("seleccion 2"), "the effects happened");
                Assert.That(longest, Is.LessThanOrEqualTo(TransientMs), "no front change beyond a transient");
                Assert.That(frontAtEnd, Is.EqualTo(personWindow), "the person's window is in front at the end");
                Assert.That(seen, Does.Contain("combo 1"), "the drop-down behind took the entry");
                Assert.That(latencies, Has.All.LessThan(1000), "no wait of the client's 2 s");
            });
        }
        finally
        {
            await stop.CancelAsync();
            Kill(person);
            Kill(target);
            try { Directory.Delete(folder, recursive: true); } catch (IOException) { }
        }
    }

    private static Process Start(string folder, string name, string script, params string[] arguments)
    {
        string path = Path.Combine(folder, name);
        File.WriteAllText(path, script, new UTF8Encoding(false));
        var start = new ProcessStartInfo("powershell.exe") { UseShellExecute = false, CreateNoWindow = true };
        foreach (string argument in new[] { "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", path })
            start.ArgumentList.Add(argument);
        foreach (string argument in arguments)
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

    private static void TypeMarked(char character)
    {
        var inputs = new Input[2];
        for (int i = 0; i < 2; i++)
        {
            inputs[i].Type = 1;
            inputs[i].Key.Scan = character;
            inputs[i].Key.Flags = 0x0004 | (i == 1 ? 0x0002u : 0u);
            inputs[i].Key.Extra = (nint)SimulatedMark;
        }

        _ = SendInput(2, inputs, Marshal.SizeOf<Input>());
    }

    /// <summary>
    /// Samples the foreground every 5 ms: how often and how long a window other than the person's held it, and a timeline
    /// (ms since the watch began) of each excursion and of each command sent, for the report.
    /// </summary>
    private sealed class FrontWatch(nint person)
    {
        private readonly Stopwatch _since = Stopwatch.StartNew();
        private readonly List<string> _timeline = [];

        public int Excursions { get; private set; }

        public long LongestMs { get; private set; }

        public long Now => _since.ElapsedMilliseconds;

        public string Timeline
        {
            get
            {
                lock (_timeline)
                    return string.Join("; ", _timeline);
            }
        }

        public void Note(string entry)
        {
            lock (_timeline)
                _timeline.Add(entry);
        }

        public async Task RunAsync(CancellationToken token)
        {
            Stopwatch? away = null;
            long began = 0;
            nint who = 0;
            while (!token.IsCancellationRequested)
            {
                nint front = GetForegroundWindow();
                if (front != person && front != 0)
                {
                    if (away is null)
                    {
                        away = Stopwatch.StartNew();
                        began = Now;
                        who = front;
                        Excursions++;
                        Note($"fuera desde {began} hwnd={who}");
                    }

                    LongestMs = Math.Max(LongestMs, away.ElapsedMilliseconds);
                }
                else if (away is not null)
                {
                    Note($"vuelta tras {away.ElapsedMilliseconds}");
                    away = null;
                }

                try { await Task.Delay(5, token); } catch (OperationCanceledException) { }
            }

            if (away is not null)
                Note($"sin vuelta tras {away.ElapsedMilliseconds}");
        }
    }

    /// <summary>A low-level keyboard hook on a thread of its own: every key without the person's or BAXY's mark.</summary>
    private sealed class UnmarkedKeyHook : IDisposable
    {
        private readonly Thread _thread;
        private readonly HookProc _proc;
        private uint _threadId;
        private readonly List<string> _unmarked = [];
        private readonly List<string> _baxy = [];
        private readonly ManualResetEventSlim _ready = new(false);

        public UnmarkedKeyHook()
        {
            _proc = OnKey;
            _thread = new Thread(() =>
            {
                _threadId = GetCurrentThreadId();
                nint hook = SetWindowsHookExW(13, _proc, GetModuleHandleW(null), 0);
                _ready.Set();
                while (GetMessageW(out Msg _, 0, 0, 0) > 0)
                {
                }

                _ = UnhookWindowsHookEx(hook);
            })
            { IsBackground = true };
            _thread.Start();
            _ready.Wait(TimeSpan.FromSeconds(5));
        }

        public IReadOnlyList<string> Unmarked
        {
            get
            {
                lock (_unmarked)
                    return [.. _unmarked];
            }
        }

        public IReadOnlyList<string> Baxy
        {
            get
            {
                lock (_unmarked)
                    return [.. _baxy];
            }
        }

        public void Dispose()
        {
            _ = PostThreadMessageW(_threadId, 0x0012, 0, 0);
            _thread.Join(TimeSpan.FromSeconds(2));
            _ready.Dispose();
        }

        private nint OnKey(int code, nint wParam, nint lParam)
        {
            if (code == 0)
            {
                var key = Marshal.PtrToStructure<KeyboardHook>(lParam);
                string seen = $"vk=0x{key.Vk:X} wm=0x{wParam:X} flags=0x{key.Flags:X}";
                if (BaxyInputMark.Carries((nuint)key.Extra))
                {
                    lock (_unmarked)
                        _baxy.Add(seen);
                }
                else if ((uint)key.Extra != SimulatedMark)
                {
                    lock (_unmarked)
                        _unmarked.Add(seen);
                }
            }

            return CallNextHookEx(0, code, wParam, lParam);
        }
    }

    private delegate nint HookProc(int code, nint wParam, nint lParam);

    [StructLayout(LayoutKind.Sequential)]
    private struct KeyboardHook
    {
        public uint Vk;
        public uint Scan;
        public uint Flags;
        public uint Time;
        public nint Extra;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KeyInput
    {
        public ushort Vk;
        public ushort Scan;
        public uint Flags;
        public uint Time;
        public nint Extra;
    }

    [StructLayout(LayoutKind.Explicit, Size = 40)]
    private struct Input
    {
        [FieldOffset(0)]
        public uint Type;

        [FieldOffset(8)]
        public KeyInput Key;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Msg
    {
        public nint Hwnd;
        public uint Message;
        public nint WParam;
        public nint LParam;
        public uint Time;
        public int X;
        public int Y;
    }

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern nint FindWindowW(string? className, string windowName);

    [DllImport("user32.dll")]
    private static extern uint SendInput(uint count, Input[] inputs, int size);

    [DllImport("user32.dll")]
    private static extern nint SetWindowsHookExW(int id, HookProc proc, nint module, uint thread);

    [DllImport("user32.dll")]
    private static extern bool UnhookWindowsHookEx(nint hook);

    [DllImport("user32.dll")]
    private static extern nint CallNextHookEx(nint hook, int code, nint wParam, nint lParam);

    [DllImport("user32.dll")]
    private static extern int GetMessageW(out Msg msg, nint hwnd, uint min, uint max);

    [DllImport("user32.dll")]
    private static extern bool PostThreadMessageW(uint thread, uint message, nint wParam, nint lParam);

    [DllImport("kernel32.dll")]
    private static extern uint GetCurrentThreadId();

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    private static extern nint GetModuleHandleW(string? name);
}
