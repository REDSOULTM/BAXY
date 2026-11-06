using System.Runtime.InteropServices;
using System.Text;

namespace Baxy.Providers.Windows.Clipboard;

public sealed class WindowsClipboardProvider : IClipboardProvider
{
    public const int MaximumCharacters = 65_536;

    // One for the process: a call left waiting is the process's, whichever provider started it.
    private static readonly IClipboardPlatform Win32 = new Win32ClipboardPlatform();
    private static readonly BoundedClipboardCalls Win32Calls = new(Win32, BoundedClipboardCalls.Deadline);

    private readonly IClipboardPlatform _platform;
    private readonly BoundedClipboardCalls _calls;

    public WindowsClipboardProvider()
        : this(Win32, Win32Calls)
    {
    }

    internal WindowsClipboardProvider(IClipboardPlatform platform, TimeSpan? deadline = null)
        : this(platform, new BoundedClipboardCalls(platform, deadline ?? BoundedClipboardCalls.Deadline))
    {
    }

    private WindowsClipboardProvider(IClipboardPlatform platform, BoundedClipboardCalls calls)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _calls = calls;
    }

    public async ValueTask<ClipboardTextSnapshot> ReadTextAsync(
        int maximumCharacters,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (maximumCharacters is < 1 or > MaximumCharacters)
        {
            throw new ClipboardProviderException("invalid_limit");
        }

        ClipboardTextSnapshot first = await ReadAsync(maximumCharacters, cancellationToken).ConfigureAwait(false);
        cancellationToken.ThrowIfCancellationRequested();
        ClipboardTextSnapshot second = await ReadAsync(maximumCharacters, cancellationToken).ConfigureAwait(false);
        if (first != second) throw new ClipboardProviderException("clipboard_changed_during_read");
        return second;
    }

    private ValueTask<ClipboardTextSnapshot> ReadAsync(int maximumCharacters, CancellationToken cancellationToken) =>
        _calls.RunAsync(() => _platform.ReadText(maximumCharacters), mayChangeClipboard: false, cancellationToken);

    public async ValueTask<ClipboardWriteResult> WriteTextAsync(
        string text,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        ValidateText(text);
        uint beforeSequence = _platform.GetSequenceNumber();
        int beforeFormats = _platform.FormatCount();
        string? beforeText = null;
        bool beforeTruncated = false;
        try
        {
            ClipboardTextSnapshot before = await ReadAsync(MaximumCharacters, cancellationToken).ConfigureAwait(false);
            beforeText = before.Text;
            beforeTruncated = before.Truncated;
        }
        catch (ClipboardProviderException exception) when (exception.Code == "clipboard_has_no_text")
        {
        }

        cancellationToken.ThrowIfCancellationRequested();
        _ = await _calls.RunAsync(
            () =>
            {
                _platform.ReplaceText(text);
                return true;
            },
            mayChangeClipboard: true,
            cancellationToken).ConfigureAwait(false);
        cancellationToken.ThrowIfCancellationRequested();
        ClipboardTextSnapshot first;
        ClipboardTextSnapshot second;
        try
        {
            first = await ReadAsync(MaximumCharacters, cancellationToken).ConfigureAwait(false);
            second = await ReadAsync(MaximumCharacters, cancellationToken).ConfigureAwait(false);
        }
        catch (ClipboardProviderException exception) when (!exception.EffectMayHaveOccurred)
        {
            // The text was written; the read-back did not answer.
            throw new ClipboardProviderException(exception.Code) { EffectMayHaveOccurred = true };
        }

        if (first != second || !string.Equals(first.Text, text, StringComparison.Ordinal) || first.Truncated)
        {
            throw new ClipboardProviderException("verification_failed") { EffectMayHaveOccurred = true };
        }

        // FT/proveedores goal (review of receipts): the same plain text written over a richer copy (a Word paragraph's
        // HTML, RTF and picture) or over a longer text read only in part replaced what was there: changed.
        bool changed = beforeSequence != first.SequenceNumber
            && (!string.Equals(beforeText, text, StringComparison.Ordinal) || beforeTruncated
                || beforeFormats > _platform.FormatCount());
        return new ClipboardWriteResult(
            first.SequenceNumber,
            text.Length,
            changed);
    }

    private static void ValidateText(string text)
    {
        if (text is null
            || text.Length > MaximumCharacters
            || text.Contains('\0', StringComparison.Ordinal)
            || !string.Equals(text, text.Normalize(NormalizationForm.FormC), StringComparison.Ordinal))
        {
            throw new ClipboardProviderException("invalid_text");
        }
    }
}

// A8. GetClipboardData on a format the owner renders when asked, and EmptyClipboard for the old owner's
// WM_DESTROYCLIPBOARD, wait on the owner's thread with no limit (agent-desktop probes/windows/FINDINGS.md A22-3; measured
// here, 10.0.26300: still inside after 7.4 s and 4 s, until the owner came back), with the clipboard open for everyone and
// the Core, which awaits each request in turn, stopped. So: an owner that does not answer is refused before the clipboard
// is opened; a call runs on a thread of its own that its deadline can leave behind (an owner that answers and hangs on the
// render passes that probe); and while one is left behind inside the OS call the next is refused, not piled up behind it
// (agent-desktop clipboard_worker_state.rs). Their residual, a clipboard held until the process ends, is closed here: see
// Win32ClipboardPlatform.ReleaseAbandonedOpen.
internal sealed class BoundedClipboardCalls(IClipboardPlatform platform, TimeSpan deadline)
{
    internal const string OwnerNotResponding = "clipboard_owner_not_responding";

    // Long enough for an owner that really renders a large copy, whose time was not measured; inside the App's 30 s.
    internal static readonly TimeSpan Deadline = TimeSpan.FromSeconds(10);

    private const int Running = 0;
    private const int Ended = 1;
    private const int LeftBehind = 2;

    private int _leftBehind;

    /// <param name="mayChangeClipboard">Left behind, the call may still have emptied the clipboard, so it is told as may have changed.</param>
    internal async ValueTask<T> RunAsync<T>(Func<T> call, bool mayChangeClipboard, CancellationToken cancellationToken)
    {
        if (Volatile.Read(ref _leftBehind) > 0 || !platform.OwnerResponds(cancellationToken))
            throw new ClipboardProviderException(OwnerNotResponding);
        // Review of uso-108: the owner's check may have taken seconds; cancelled meanwhile, no thread starts.
        cancellationToken.ThrowIfCancellationRequested();

        int state = Running;
        var answer = new TaskCompletionSource<T>(TaskCreationOptions.RunContinuationsAsynchronously);
        var worker = new Thread(() =>
        {
            try
            {
                answer.TrySetResult(call());
            }
            catch (Exception exception)
            {
                answer.TrySetException(exception);
            }
            finally
            {
                if (Interlocked.Exchange(ref state, Ended) == LeftBehind)
                    Interlocked.Decrement(ref _leftBehind);
            }
        })
        {
            IsBackground = true,
            Name = "BAXY clipboard call",
        };
        worker.Start();
        try
        {
            return await answer.Task.WaitAsync(deadline, cancellationToken).ConfigureAwait(false);
        }
        catch (TimeoutException)
        {
            // It ended just as the time ran out: its answer stands.
            if (Interlocked.CompareExchange(ref state, LeftBehind, Running) != Running)
                return await answer.Task.ConfigureAwait(false);
            LeaveBehind();
            throw new ClipboardProviderException(OwnerNotResponding) { EffectMayHaveOccurred = mayChangeClipboard };
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            if (Interlocked.CompareExchange(ref state, LeftBehind, Running) == Running)
                LeaveBehind();
            throw;
        }
    }

    private void LeaveBehind()
    {
        Interlocked.Increment(ref _leftBehind);
        platform.ReleaseAbandonedOpen();
    }
}

internal sealed partial class Win32ClipboardPlatform : IClipboardPlatform
{
    private const uint UnicodeText = 13;
    private const uint Bitmap = 2;
    private const uint DeviceBitmap = 8;
    private const uint Files = 15;
    private const uint DeviceBitmapV5 = 17;
    private const uint MoveableMemory = 0x0002;
    public uint GetSequenceNumber() => GetClipboardSequenceNumber();

    public int FormatCount() => CountClipboardFormats();

    // The check every act on a window makes (VisibleControlSurface.NotResponding, review of uso-108): an owner busy for a
    // second or three (a document opening) is waited for, and only one Windows calls hung is told so. A window gone or one of
    // a higher integrity (access denied) says nothing of a stall, and the deadline still bounds the call. No owner renders
    // nothing: a clipboard opened with no window, as this class does.
    public bool OwnerResponds(CancellationToken cancellationToken)
    {
        nint owner = GetClipboardOwner();
        return owner == 0 || !External.VisibleControlSurface.NotResponding(owner, cancellationToken);
    }

    // Undocumented, measured here (10.0.26300) against an owner hung on the render and one not pumping: with a thread
    // waiting inside GetClipboardData, an open with no window from another thread succeeds, and its close ends the hold: an
    // open with a window from another process went from access denied to done, the thread still inside. A write left
    // inside EmptyClipboard then finds the clipboard closed, so its SetClipboardData fails and no late text appears.
    public void ReleaseAbandonedOpen()
    {
        if (OpenClipboard(0))
            _ = CloseClipboard();
    }

    // B11 (agent-desktop crates/windows/src/input/clipboard/mod.rs:148): files, then a picture. Unlike theirs, only when
    // there is no text: an app that publishes text and a picture would come back as a picture. Empty stays apart from a
    // read that failed by its error code, as in their empty_clipboard_returns_ok_none_distinct_from_transport_error.
    internal static ClipboardHolds? WhatItHolds(Func<uint, bool> available, uint imageFile, int formats, Func<int?> fileCount)
    {
        if (available(Files))
            return new ClipboardHolds("files", fileCount());
        if (available(DeviceBitmap) || available(Bitmap) || available(DeviceBitmapV5) || available(imageFile))
            return new ClipboardHolds("image");
        return formats > 0 ? new ClipboardHolds("other") : null;
    }

    // Asks the owner for the list, on the call's thread like any other read; a list not answered still says «files».
    private static int? FileCount()
    {
        nint list = GetClipboardData(Files);
        return list == 0 ? null : checked((int)DragQueryFileW(list, uint.MaxValue, 0, 0));
    }

    // Microsoft, «Clipboard Formats», Cloud Clipboard and Clipboard History Formats: data in ExcludeClipboardContentFromMonitorProcessing,
    // or a DWORD of zero in CanIncludeInClipboardHistory, keeps a copy out of the history. CopyQ's security page reads these
    // and the older «Clipboard Viewer Ignore» as what password managers set; each decides for itself (a Bitwarden user reports
    // that it does not), so a key with no mark is left to its form (SecretShape). The clipboard is open.
    private static bool OwnerMarkedPrivate()
    {
        if (IsClipboardFormatAvailable(RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing"))
            || IsClipboardFormatAvailable(RegisterClipboardFormatW("Clipboard Viewer Ignore")))
            return true;
        uint history = RegisterClipboardFormatW("CanIncludeInClipboardHistory");
        if (!IsClipboardFormatAvailable(history))
            return false;
        nint data = GetClipboardData(history);
        if (data == 0 || GlobalSize(data) < sizeof(int))
            return false;
        nint value = GlobalLock(data);
        if (value == 0)
            return false;
        try
        {
            return Marshal.ReadInt32(value) == 0;
        }
        finally
        {
            _ = GlobalUnlock(data);
        }
    }

    public ClipboardTextSnapshot ReadText(int maximumCharacters)
    {
        Open();
        try
        {
            if (!IsClipboardFormatAvailable(UnicodeText))
            {
                throw new ClipboardProviderException("clipboard_has_no_text")
                {
                    Holds = WhatItHolds(IsClipboardFormatAvailable, RegisterClipboardFormatW("PNG"), CountClipboardFormats(), FileCount),
                };
            }

            nint handle = GetClipboardData(UnicodeText);
            if (handle == 0) throw new ClipboardProviderException("clipboard_read_failed");
            nuint bytes = GlobalSize(handle);
            nint pointer = GlobalLock(handle);
            if (pointer == 0) throw new ClipboardProviderException("clipboard_read_failed");
            try
            {
                int availableCharacters = checked((int)Math.Min(bytes / 2, (nuint)(maximumCharacters + 1)));
                string allocated = Marshal.PtrToStringUni(pointer, availableCharacters);
                int terminator = allocated.IndexOf('\0', StringComparison.Ordinal);
                string text = terminator >= 0 ? allocated[..terminator] : allocated;
                bool truncated = terminator < 0 || text.Length > maximumCharacters;
                if (text.Length > maximumCharacters) text = text[..maximumCharacters];
                return new ClipboardTextSnapshot(
                    text,
                    text.Length,
                    truncated,
                    GetClipboardSequenceNumber())
                {
                    MarkedPrivate = OwnerMarkedPrivate(),
                };
            }
            finally
            {
                _ = GlobalUnlock(handle);
            }
        }
        finally
        {
            _ = CloseClipboard();
        }
    }

    public void ReplaceText(string text)
    {
        byte[] encoded = Encoding.Unicode.GetBytes(text + "\0");
        nint memory = GlobalAlloc(MoveableMemory, (nuint)encoded.Length);
        if (memory == 0) throw new ClipboardProviderException("clipboard_allocation_failed");
        bool transferred = false;
        try
        {
            nint pointer = GlobalLock(memory);
            if (pointer == 0) throw new ClipboardProviderException("clipboard_allocation_failed");
            try
            {
                Marshal.Copy(encoded, 0, pointer, encoded.Length);
            }
            finally
            {
                _ = GlobalUnlock(memory);
            }

            Open();
            try
            {
                if (!EmptyClipboard()) throw new ClipboardProviderException("clipboard_write_failed");
                if (SetClipboardData(UnicodeText, memory) == 0)
                {
                    // EmptyClipboard already emptied the person's clipboard.
                    throw new ClipboardProviderException("clipboard_partial_write") { EffectMayHaveOccurred = true };
                }

                transferred = true;
            }
            finally
            {
                _ = CloseClipboard();
            }
        }
        finally
        {
            if (!transferred) _ = GlobalFree(memory);
        }
    }

    // Another process (a clipboard sync such as Synergy, a clipboard history, the app just copied from) holds the
    // clipboard open for an instant after each change; uso real estab t2-c17 and t3-c10 failed a copy on that instant.
    // The open is retried for at most about a second before the clipboard is called busy.
    internal const int OpenAttempts = 20;
    internal static readonly TimeSpan OpenPause = TimeSpan.FromMilliseconds(50);

    private static void Open() => OpenRetrying(static () => OpenClipboard(0), Thread.Sleep);

    internal static void OpenRetrying(Func<bool> tryOpen, Action<TimeSpan> wait)
    {
        for (int attempt = 1; !tryOpen(); attempt++)
        {
            if (attempt >= OpenAttempts) throw new ClipboardProviderException("clipboard_busy");
            wait(OpenPause);
        }
    }

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool OpenClipboard(nint newOwner);

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool CloseClipboard();

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsClipboardFormatAvailable(uint format);

    [LibraryImport("user32.dll", SetLastError = true)]
    private static partial nint GetClipboardData(uint format);

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EmptyClipboard();

    [LibraryImport("user32.dll", SetLastError = true)]
    private static partial nint SetClipboardData(uint format, nint memory);

    [LibraryImport("user32.dll")]
    private static partial nint GetClipboardOwner();

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial uint RegisterClipboardFormatW(string name);

    [LibraryImport("shell32.dll")]
    private static partial uint DragQueryFileW(nint list, uint index, nint buffer, uint characters);

    [LibraryImport("user32.dll")]
    private static partial uint GetClipboardSequenceNumber();

    [LibraryImport("user32.dll")]
    private static partial int CountClipboardFormats();

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial nint GlobalAlloc(uint flags, nuint bytes);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial nint GlobalFree(nint memory);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial nint GlobalLock(nint memory);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GlobalUnlock(nint memory);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial nuint GlobalSize(nint memory);
}
