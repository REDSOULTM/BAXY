using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Clipboard;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// On the PC's real clipboard, so never in the ordinary suite: the text it held is put back, and the owners are threads of
/// this test. An isolated window station was refused on the PC (CreateWindowStation, error 5). A clipboard listener of the
/// machine (a clipboard sync, the history) may open it at any moment, so a failure here is read before it is believed.
/// </summary>
[TestFixture]
[Explicit("Uses the real clipboard")]
[NonParallelizable]
public sealed class ClipboardLiveTests
{
    private const uint UnicodeText = 13;
    private const uint Files = 15;
    private const uint DeviceBitmap = 8;
    private const uint RenderFormat = 0x305;
    private const uint DestroyClipboard = 0x307;
    private string? _heldText;

    [SetUp]
    public void SaveText()
    {
        _heldText = null;
        try
        {
            _heldText = new Win32ClipboardPlatform().ReadText(WindowsClipboardProvider.MaximumCharacters).Text;
        }
        catch (ClipboardProviderException)
        {
        }
    }

    [TearDown]
    public void RestoreText()
    {
        try
        {
            if (_heldText is not null)
                new Win32ClipboardPlatform().ReplaceText(_heldText);
        }
        catch (ClipboardProviderException)
        {
        }
    }

    // A8: GetClipboardData on a delay-rendered format waits for an owner that does not pump (agent-desktop
    // probes/windows/FINDINGS.md A22-3; here still inside it after 7.4 s). The answer comes from the probe before it.
    [Test]
    public async Task AReadOfAStalledOwnerEndsWithItsCode()
    {
        using var owner = new ClipboardOwner(pumps: false, stallsOn: 0);
        var watch = Stopwatch.StartNew();
        Task<ClipboardTextSnapshot> read = Task.Run(async () =>
            await new WindowsClipboardProvider().ReadTextAsync(100, CancellationToken.None));

        Task finished = await Task.WhenAny(read, Task.Delay(TimeSpan.FromSeconds(3)));

        Assert.That(finished, Is.SameAs(read), "the read did not answer");
        var refused = Assert.CatchAsync<ClipboardProviderException>(async () => await read);
        Assert.Multiple(() =>
        {
            Assert.That(refused!.Code, Is.EqualTo("clipboard_owner_not_responding"));
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            Assert.That(watch.Elapsed, Is.LessThan(TimeSpan.FromSeconds(2)));
        });
    }

    // A8: an owner that answers WM_NULL and hangs on the render passes the probe (measured 5.7 ms). The deadline ends the
    // read, the clipboard is let go with the thread still inside, and the next call is refused until the thread comes back.
    [Test]
    public async Task AReadOfAnOwnerHungOnTheRenderIsLetGoAtItsDeadline()
    {
        var provider = new WindowsClipboardProvider(new Win32ClipboardPlatform(), TimeSpan.FromSeconds(1));
        using var opener = new WindowedOpener();
        ClipboardProviderException? refusedNext;
        using (var owner = new ClipboardOwner(pumps: true, stallsOn: RenderFormat))
        {
            var refused = Assert.CatchAsync<ClipboardProviderException>(
                async () => await provider.ReadTextAsync(100, CancellationToken.None));
            Assert.That(refused!.Code, Is.EqualTo("clipboard_owner_not_responding"));
            Assert.That(opener.Opens(), Is.True, () => "the clipboard stayed held for the others, by " + Holder());
            var watch = Stopwatch.StartNew();
            refusedNext = Assert.CatchAsync<ClipboardProviderException>(
                async () => await provider.ReadTextAsync(100, CancellationToken.None));
            Assert.Multiple(() =>
            {
                Assert.That(refusedNext!.Code, Is.EqualTo("clipboard_owner_not_responding"));
                Assert.That(watch.Elapsed, Is.LessThan(TimeSpan.FromMilliseconds(500)));
            });
        }

        // The owner went: whatever it left, the provider no longer refuses for it.
        await Task.Delay(200);
        ClipboardProviderException? after = null;
        try
        {
            await provider.ReadTextAsync(100, CancellationToken.None);
        }
        catch (ClipboardProviderException exception)
        {
            after = exception;
        }

        Assert.That(after?.Code, Is.Not.EqualTo("clipboard_owner_not_responding"));
    }

    // A8, the write: EmptyClipboard waits on the old owner's WM_DESTROYCLIPBOARD. The deadline ends it as «may have
    // changed», and when the owner comes back the thread left behind writes nothing.
    [Test]
    public async Task AWriteOverAnOwnerHungOnItsDestructionLeavesNoLateText()
    {
        var provider = new WindowsClipboardProvider(new StallsOnlyOnReplace(), TimeSpan.FromSeconds(1));
        using (new ClipboardOwner(pumps: true, stallsOn: DestroyClipboard))
        {
            var refused = Assert.CatchAsync<ClipboardProviderException>(
                async () => await provider.WriteTextAsync("texto tardío de la prueba", CancellationToken.None));
            Assert.Multiple(() =>
            {
                Assert.That(refused!.Code, Is.EqualTo("clipboard_owner_not_responding"));
                Assert.That(refused.EffectMayHaveOccurred, Is.True);
            });
        }

        await Task.Delay(300);
        string? held = null;
        try
        {
            held = new Win32ClipboardPlatform().ReadText(100).Text;
        }
        catch (ClipboardProviderException)
        {
        }

        Assert.That(held, Is.Not.EqualTo("texto tardío de la prueba"));
    }

    // C18: the docs say SetClipboardData fails after OpenClipboard(NULL) and EmptyClipboard; here it does not.
    [Test]
    public async Task AWriteWithNoOwnerWindowIsReadBack()
    {
        var provider = new WindowsClipboardProvider();
        for (int attempt = 0; attempt < 5; attempt++)
        {
            string text = "prueba sin dueño " + attempt;
            await provider.WriteTextAsync(text, CancellationToken.None);
            ClipboardTextSnapshot read = await provider.ReadTextAsync(100, CancellationToken.None);
            Assert.That(read.Text, Is.EqualTo(text));
        }
    }

    private static string Holder()
    {
        nint window = GetOpenClipboardWindow();
        if (window == 0)
            return "no window";
        _ = GetWindowThreadProcessId(window, out uint process);
        return process == Environment.ProcessId ? "this test" : Process.GetProcessById((int)process).ProcessName;
    }

    // The real platform, except that it reads nothing: only ReplaceText can meet the owner's destruction.
    private sealed class StallsOnlyOnReplace : IClipboardPlatform
    {
        private readonly Win32ClipboardPlatform _real = new();

        public uint GetSequenceNumber() => _real.GetSequenceNumber();

        public ClipboardTextSnapshot ReadText(int maximumCharacters) => new("antes", 5, false, 1);

        public void ReplaceText(string text) => _real.ReplaceText(text);

        public void ReleaseAbandonedOpen() => _real.ReleaseAbandonedOpen();
    }

    // Tries the clipboard as an app does, with a window: refused while another holds it (error 5).
    private sealed class WindowedOpener : IDisposable
    {
        private readonly nint _window;

        public WindowedOpener()
        {
            _windowProcedure = static (window, message, first, second) => DefWindowProcW(window, message, first, second);
            var windowClass = new WindowClass
            {
                Procedure = Marshal.GetFunctionPointerForDelegate(_windowProcedure),
                ClassName = "BaxyClipboardOpenerTest",
            };
            _ = RegisterClassW(ref windowClass);
            _window = CreateWindowExW(0, windowClass.ClassName, string.Empty, 0, 0, 0, 10, 10, 0, 0, 0, 0);
        }

        private readonly WindowProcedure _windowProcedure;

        public bool Opens()
        {
            if (!OpenClipboard(_window))
                return false;
            CloseClipboard();
            return true;
        }

        public void Dispose() => DestroyWindow(_window);
    }

    // B11: what a copy of files or of a picture holds is said, on this failure only.
    [Test]
    public async Task ACopyOfFilesIsToldAsFilesWithoutTheirNames()
    {
        PutFiles(@"C:\privado\a.pdf", @"C:\privado\b.pdf", @"C:\privado\c.pdf");

        OperationOutcome outcome = await Read();

        string message = OperationVisibleFacts.FromOutcome("clipboard.read.text", outcome);
        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("clipboard_has_no_text"));
            Assert.That(message, Does.Contain("\"observed\":{\"holds\":\"files\",\"count\":3}"));
            Assert.That(message, Does.Not.Contain("a.pdf"));
        });
    }

    [Test]
    public async Task ACopyOfAPictureIsToldAsAnImage()
    {
        PutBitmap();

        OperationOutcome outcome = await Read();

        Assert.That(
            OperationVisibleFacts.FromOutcome("clipboard.read.text", outcome),
            Does.Contain("\"observed\":{\"holds\":\"image\"}"));
    }

    [Test]
    public async Task AnEmptyClipboardSaysWhatItAlwaysSaid()
    {
        Assert.That(OpenClipboard(0), Is.True);
        EmptyClipboard();
        CloseClipboard();

        OperationOutcome outcome = await Read();

        Assert.That(
            OperationVisibleFacts.FromOutcome("clipboard.read.text", outcome),
            Is.EqualTo("{\"status\":\"failed\",\"error\":\"clipboard_has_no_text\"}"));
    }

    private static async Task<OperationOutcome> Read()
    {
        using JsonDocument arguments = JsonDocument.Parse("{}");
        return await new ClipboardReadTextHandler(new WindowsClipboardProvider()).ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", arguments.RootElement.Clone()),
            CancellationToken.None);
    }

    private static void PutFiles(params string[] paths)
    {
        byte[] names = Encoding.Unicode.GetBytes(string.Concat(paths.Select(static path => path + '\0')) + '\0');
        const int header = 20; // DROPFILES
        nint memory = GlobalAlloc(2, (nuint)(header + names.Length));
        nint pointer = GlobalLock(memory);
        Marshal.WriteInt32(pointer, 0, header);
        Marshal.WriteInt32(pointer, 16, 1); // fWide
        Marshal.Copy(names, 0, pointer + header, names.Length);
        GlobalUnlock(memory);
        Put(Files, memory);
    }

    private static void PutBitmap()
    {
        const int header = 40; // BITMAPINFOHEADER, one 32-bit pixel
        nint memory = GlobalAlloc(2, header + 4);
        nint pointer = GlobalLock(memory);
        Marshal.WriteInt32(pointer, 0, header);
        Marshal.WriteInt32(pointer, 4, 1);
        Marshal.WriteInt32(pointer, 8, 1);
        Marshal.WriteInt16(pointer, 12, 1);
        Marshal.WriteInt16(pointer, 14, 32);
        GlobalUnlock(memory);
        Put(DeviceBitmap, memory);
    }

    private static void Put(uint format, nint memory)
    {
        Assert.That(OpenClipboard(0), Is.True, "another process holds the clipboard");
        try
        {
            EmptyClipboard();
            Assert.That(SetClipboardData(format, memory), Is.Not.EqualTo((nint)0));
        }
        finally
        {
            CloseClipboard();
        }
    }

    // Takes the clipboard with a window of its own, on a thread of its own, advertising text it renders only when asked.
    // Without a pump it answers nothing; with one it answers WM_NULL and hangs on the message named by stallsOn.
    private sealed class ClipboardOwner : IDisposable
    {
        private readonly ManualResetEventSlim _end = new();
        private readonly ManualResetEventSlim _ready = new();
        private readonly Thread _thread;
        private readonly WindowProcedure _procedure;
        private readonly uint _stallsOn;
        private readonly bool _pumps;
        private nint _window;

        public ClipboardOwner(bool pumps, uint stallsOn)
        {
            _pumps = pumps;
            _stallsOn = stallsOn;
            _procedure = Procedure;
            _thread = new Thread(Run) { IsBackground = true, Name = "clipboard owner of a test" };
            _thread.Start();
            if (!_ready.Wait(TimeSpan.FromSeconds(5)))
                throw new TimeoutException("The owner did not take the clipboard.");
        }

        private nint Procedure(nint window, uint message, nint first, nint second)
        {
            if (message == _stallsOn)
                _end.Wait();
            return DefWindowProcW(window, message, first, second);
        }

        private void Run()
        {
            var windowClass = new WindowClass
            {
                Procedure = Marshal.GetFunctionPointerForDelegate(_procedure),
                ClassName = "BaxyClipboardOwnerTest" + Environment.CurrentManagedThreadId,
            };
            _ = RegisterClassW(ref windowClass);
            _window = CreateWindowExW(0, windowClass.ClassName, string.Empty, 0, 0, 0, 10, 10, 0, 0, 0, 0);
            OpenClipboard(_window);
            EmptyClipboard();
            SetClipboardData(UnicodeText, 0);
            CloseClipboard();
            _ready.Set();
            if (!_pumps)
            {
                _end.Wait();
                return;
            }

            while (!_end.IsSet && GetMessageW(out Message message, 0, 0, 0) > 0)
                DispatchMessageW(ref message);
        }

        // Its window goes with the thread, and whatever waited on it comes back.
        public void Dispose()
        {
            _end.Set();
            _ = PostMessageW(_window, 0, 0, 0); // wakes the pump, which then sees the end
            _ = _thread.Join(TimeSpan.FromSeconds(5));
        }
    }

    private delegate nint WindowProcedure(nint window, uint message, nint first, nint second);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WindowClass
    {
        public uint Style;
        public nint Procedure;
        public int ClassExtra;
        public int WindowExtra;
        public nint Instance;
        public nint Icon;
        public nint Cursor;
        public nint Background;
        public string? MenuName;
        public string ClassName;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Message
    {
        public nint Window;
        public uint Value;
        public nint First;
        public nint Second;
        public uint Time;
        public int X;
        public int Y;
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern ushort RegisterClassW(ref WindowClass windowClass);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern nint CreateWindowExW(
        uint extended, string className, string title, uint style, int x, int y, int width, int height,
        nint parent, nint menu, nint instance, nint parameter);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern nint DefWindowProcW(nint window, uint message, nint first, nint second);

    [DllImport("user32.dll")]
    private static extern int GetMessageW(out Message message, nint window, uint first, uint last);

    [DllImport("user32.dll")]
    private static extern nint DispatchMessageW(ref Message message);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool PostMessageW(nint window, uint message, nint first, nint second);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool DestroyWindow(nint window);

    [DllImport("user32.dll")]
    private static extern nint GetOpenClipboardWindow();

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint process);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool OpenClipboard(nint window);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool CloseClipboard();

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool EmptyClipboard();

    [DllImport("user32.dll", SetLastError = true)]
    private static extern nint SetClipboardData(uint format, nint memory);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern nint GlobalAlloc(uint flags, nuint bytes);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern nint GlobalLock(nint memory);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GlobalUnlock(nint memory);
}
