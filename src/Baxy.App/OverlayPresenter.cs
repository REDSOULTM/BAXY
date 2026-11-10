using System.Runtime.InteropServices;
using System.Text.Json.Nodes;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Threading;

namespace Baxy.App;

/// <summary>
/// When the overlay shows (owner, 2026-11-08): it is on, there is a turn to tell (<see cref="OverlayModel"/>), BAXY's
/// window is not the one in front, and, if the person chose so, no other window fills its screen (a game or a video). It
/// is fed the events the view gets and re-checks twice a second (the clock, the end's time, the window in front).
/// </summary>
internal sealed class OverlayPresenter : IDisposable
{
    private readonly Window _main;
    private readonly FieldSettings _settings;
    private readonly Action _showMain;
    private readonly Func<string, bool, Task<string?>> _answer;
    private readonly OverlayModel _model = new();
    private readonly OverlayWindow _window = new();
    private readonly DispatcherTimer _timer;
    private DateTimeOffset _previewUntil = DateTimeOffset.MinValue;
    private bool _disposed;

    internal OverlayPresenter(Window main, FieldSettings settings, Action showMain, Func<string, bool, Task<string?>> answer)
    {
        _main = main ?? throw new ArgumentNullException(nameof(main));
        _settings = settings ?? throw new ArgumentNullException(nameof(settings));
        _showMain = showMain ?? throw new ArgumentNullException(nameof(showMain));
        _answer = answer ?? throw new ArgumentNullException(nameof(answer));
        _window.Opened += () => { _previewUntil = DateTimeOffset.MinValue; _showMain(); Refresh(); };
        _window.Answered += (card, approve) => _ = Answer(() => _answer(card, approve), () =>
        {
            _model.AnswerNotTaken(card);
            Refresh();
        });
        _timer = new DispatcherTimer(TimeSpan.FromMilliseconds(500), DispatcherPriority.Background, (_, _) => Refresh(), _main.Dispatcher);
        _timer.Start();
    }

    /// <summary>An event the view got (any thread): the overlay reads it on the window's thread.</summary>
    internal void OnEvent(JsonObject eventData)
    {
        if (_disposed || eventData is null)
        {
            return;
        }

        var copy = (JsonObject)eventData.DeepClone();
        _ = _main.Dispatcher.BeginInvoke(() =>
        {
            _model.Apply(copy, DateTimeOffset.UtcNow);
            Refresh();
        });
    }

    /// <summary>Settings › Personalización «Probar»: an example in the chosen corner for a few seconds, BAXY in front or not.</summary>
    internal void Preview() => _main.Dispatcher.BeginInvoke(() =>
    {
        _previewUntil = DateTimeOffset.UtcNow.AddSeconds(5);
        Refresh();
    });

    private void Refresh()
    {
        if (_disposed)
        {
            return;
        }

        DateTimeOffset now = DateTimeOffset.UtcNow;
        OverlaySettings settings = _settings.Overlay;
        bool english = UiLanguage.IsEnglish;
        bool preview = now < _previewUntil;
        OverlaySnapshot? shown = preview ? Example(english) : _model.Snapshot(now, settings.HideSeconds, english);
        bool show = shown is not null && (preview || (settings.On && !MainInFront() && !(settings.NotFullscreen && OtherFillsItsScreen())));
        if (!show)
        {
            if (_window.IsVisible)
            {
                _window.Hide();
            }

            return;
        }

        _window.Render(shown!, settings, english);
        if (!_window.IsVisible)
        {
            _window.Show();
        }

        _window.Place(settings.Corner);
    }

    /// <summary>
    /// APP1 (REV_APP OVL-4): the answer given from the overlay, looked at. The App says why it did not take it (null when
    /// it did: <see cref="FieldProductChannel.AnswerCardAsync"/>); a refusal or a failure is said on the card
    /// (<paramref name="notTaken"/>) instead of the Sí going nowhere, and a failure is kept with its type
    /// (<paramref name="diagnostics"/>: where, for the tests; else the profile's).
    /// </summary>
    internal static async Task Answer(Func<Task<string?>> answer, Action notTaken, string? diagnostics = null)
    {
        ArgumentNullException.ThrowIfNull(answer);
        ArgumentNullException.ThrowIfNull(notTaken);
        string? refused;
        try
        {
            refused = await answer().ConfigureAwait(true);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            UnhandledFailures.Record("overlay.answer", exception, diagnostics);
            refused = "answer_failed";
        }

        if (refused is not null)
        {
            notTaken();
        }
    }

    private bool MainInFront()
    {
        nint main = new WindowInteropHelper(_main).Handle;
        return _main.IsVisible && _main.WindowState != WindowState.Minimized && NativeMethods.GetForegroundWindow() == main;
    }

    // A window in front that covers its whole screen (a full-screen game or video), other than the desktop itself.
    private bool OtherFillsItsScreen()
    {
        nint front = NativeMethods.GetForegroundWindow();
        if (front == 0 || front == new WindowInteropHelper(_main).Handle || front == new WindowInteropHelper(_window).Handle)
        {
            return false;
        }

        char[] name = new char[64];
        int length = NativeMethods.GetClassName(front, name, name.Length);
        if (new string(name, 0, Math.Max(0, length)) is "Progman" or "WorkerW" or "Shell_TrayWnd")
        {
            return false;
        }

        var monitor = new NativeMethods.MonitorInfo { Size = Marshal.SizeOf<NativeMethods.MonitorInfo>() };
        return NativeMethods.GetWindowRect(front, out NativeMethods.Rect window)
            && NativeMethods.GetMonitorInfo(NativeMethods.MonitorFromWindow(front, 2), ref monitor)
            && window.Left <= monitor.Monitor.Left && window.Top <= monitor.Monitor.Top
            && window.Right >= monitor.Monitor.Right && window.Bottom >= monitor.Monitor.Bottom;
    }

    private static OverlaySnapshot Example(bool english) => new(
        "working",
        UiLanguage.Say(english, "Trabajando · paso 2", "Working · step 2"),
        null,
        [
            new OverlayStep(UiLanguage.Say(english, "Abrir una carpeta · Descargas", "Open a folder · Downloads"), "ok", UiLanguage.Say(english, "La ventana quedó al frente", "The window came to the front")),
            new OverlayStep(UiLanguage.Say(english, "Ordenar por fecha", "Sort by date"), "run", null),
        ],
        UiLanguage.Say(english, "ordena Descargas por fecha", "sort Downloads by date"),
        "0:03",
        0.5,
        null);

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _timer.Stop();
        _window.Close();
    }

    private static class NativeMethods
    {
        [StructLayout(LayoutKind.Sequential)]
        internal struct Rect
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;
        }

        [StructLayout(LayoutKind.Sequential)]
        internal struct MonitorInfo
        {
            public int Size;
            public Rect Monitor;
            public Rect Work;
            public uint Flags;
        }

        [DllImport("user32.dll")]
        internal static extern nint GetForegroundWindow();

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        internal static extern int GetClassName(nint window, [Out] char[] name, int capacity);

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool GetWindowRect(nint window, out Rect rect);

        [DllImport("user32.dll")]
        internal static extern nint MonitorFromWindow(nint window, uint flags);

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool GetMonitorInfo(nint monitor, ref MonitorInfo info);
    }
}
