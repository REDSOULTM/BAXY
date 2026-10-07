using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The keyboard of the window in front, inside this process. Computer use measured
/// about 0.65 s per key while every <c>input.key.press</c> and <c>input.text.type</c>
/// started a PowerShell and compiled its SendInput declarations; the same SendInput
/// call made here costs well under a millisecond. The adapter decides what is sent
/// and builds the receipt; this seam only reads the foreground and sends.
/// </summary>
internal interface IDesktopKeyboard
{
    /// <summary>The window in front (0 when nobody holds the foreground), its process and title.</summary>
    DesktopForeground Foreground();

    /// <summary>Presses the keys in order and releases them in reverse; the events Windows accepted.</summary>
    uint PressChord(IReadOnlyList<ushort> virtualKeys);

    /// <summary>
    /// Types each UTF-16 unit as a Unicode key down and up while <paramref name="keepGoing"/> holds before each one
    /// (the request is not cancelled and the window that takes the keys is still in front); the events Windows
    /// accepted, fewer than two per unit when it stopped.
    /// </summary>
    uint TypeText(string text, Func<bool> keepGoing);

    /// <summary>Whether this window (or one of its own process) holds the foreground.</summary>
    bool Holds(nint window);

    /// <summary>Brings this window to the front; whether it holds the foreground afterwards.</summary>
    ValueTask<bool> FrontAsync(nint window, CancellationToken cancellationToken);

    /// <summary>The size of one native INPUT record (40 on x64), checked before anything is sent.</summary>
    int InputSize { get; }

    int LastError();

    /// <summary>Lets the window in front take the keys before its post-read.</summary>
    ValueTask SettleAsync(CancellationToken cancellationToken);
}

internal readonly record struct DesktopForeground(nint Window, int ProcessId, string Title);

internal sealed partial class WindowsDesktopKeyboard : IDesktopKeyboard
{
    private const uint InputKeyboard = 1;
    private const uint KeyUp = 0x0002;
    private const uint Unicode = 0x0004;
    private const int KeyPace = 35;

    // What the PowerShell path waited before reading the foreground again.
    private static readonly TimeSpan Settle = TimeSpan.FromMilliseconds(40);

    public int InputSize => Marshal.SizeOf<Input>();

    public DesktopForeground Foreground()
    {
        nint window = GetForegroundWindow();
        if (window == 0)
            return default;
        _ = GetWindowThreadProcessId(window, out uint processId);
        return new DesktopForeground(window, unchecked((int)processId), VisibleControlSurface.WindowTitle(window));
    }

    public uint PressChord(IReadOnlyList<ushort> virtualKeys)
    {
        var inputs = new Input[virtualKeys.Count * 2];
        for (int index = 0; index < virtualKeys.Count; index++)
        {
            inputs[index] = Key(virtualKeys[index], 0, 0);
            inputs[virtualKeys.Count + index] = Key(virtualKeys[virtualKeys.Count - index - 1], 0, KeyUp);
        }

        return Send(inputs);
    }

    public uint TypeText(string text, Func<bool> keepGoing)
    {
        // One character at a time, at a fast typist's pace. Measured on Windows 11 Notepad (2026-10-07, «Querido Ron:
        // mañana a las 5, llevá pan…»): its editor reads each key when it gets to it, so keys sent faster than it takes
        // them come out as the last one repeated («lista: pan» → «lista:nnnn» at 3 ms, «lista:ppan» at 20 ms), and real
        // virtual keys lose their Shift the same way; 25 ms and slower typed every run whole.
        // Safety review 2026-10-07: 4096 characters at this pace take about 143 s, well past the App's step timeout,
        // and a window that takes the front meanwhile would get the rest. Before each character the request must
        // still stand and the window must still be in front; otherwise typing stops there.
        uint accepted = 0;
        for (int index = 0; index < text.Length; index++)
        {
            if (!keepGoing())
                break;
            accepted += Send([Key(0, text[index], Unicode), Key(0, text[index], Unicode | KeyUp)]);
            Thread.Sleep(KeyPace);
        }

        return accepted;
    }

    public bool Holds(nint window)
    {
        if (window == 0)
            return false;
        if (VisibleControlSurface.ForegroundIs(window))
            return true;
        // A window of the same process in front (its own pop-up or dialog) still takes the keys for it.
        nint foreground = GetForegroundWindow();
        if (foreground == 0)
            return false;
        _ = GetWindowThreadProcessId(foreground, out uint foregroundProcess);
        _ = GetWindowThreadProcessId(window, out uint windowProcess);
        return windowProcess != 0 && foregroundProcess == windowProcess;
    }

    public async ValueTask<bool> FrontAsync(nint window, CancellationToken cancellationToken)
    {
        if (Holds(window))
            return true;
        if (!VisibleControlSurface.IsAlive(window))
            return false;
        _ = VisibleControlSurface.BringToFront(window);
        for (int attempt = 0; attempt < 4 && !Holds(window); attempt++)
            await Task.Delay(50, cancellationToken).ConfigureAwait(false);
        return Holds(window);
    }

    public int LastError() => Marshal.GetLastPInvokeError();

    public ValueTask SettleAsync(CancellationToken cancellationToken) =>
        new(Task.Delay(Settle, cancellationToken));

    private uint Send(Input[] inputs) =>
        inputs.Length == 0 ? 0 : SendInput(unchecked((uint)inputs.Length), inputs, InputSize);

    private static Input Key(ushort virtualKey, ushort scanCode, uint flags) => new()
    {
        Type = InputKeyboard,
        Data = new InputUnion
        {
            Keyboard = new KeyboardInput { VirtualKey = virtualKey, ScanCode = scanCode, Flags = flags },
        },
    };

    [StructLayout(LayoutKind.Sequential)]
    private struct Input
    {
        public uint Type;
        public InputUnion Data;
    }

    // The union carries every member so the record has the native size (40 bytes on x64); a keyboard-only union is
    // shorter and SendInput refuses it.
    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion
    {
        [FieldOffset(0)] public KeyboardInput Keyboard;
        [FieldOffset(0)] public MouseInput Mouse;
        [FieldOffset(0)] public HardwareInput Hardware;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KeyboardInput
    {
        public ushort VirtualKey;
        public ushort ScanCode;
        public uint Flags;
        public uint Time;
        public nuint ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MouseInput
    {
        public int X;
        public int Y;
        public uint MouseData;
        public uint Flags;
        public uint Time;
        public nuint ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct HardwareInput
    {
        public uint Message;
        public ushort ParameterLow;
        public ushort ParameterHigh;
    }

    [LibraryImport("user32.dll", SetLastError = true)]
    private static partial uint SendInput(uint count, [In] Input[] inputs, int size);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);
}
