using System.Runtime.InteropServices;
using System.Text;

namespace Baxy.Providers.Windows.Clipboard;

public sealed class WindowsClipboardProvider : IClipboardProvider
{
    public const int MaximumCharacters = 65_536;
    private readonly IClipboardPlatform _platform;

    public WindowsClipboardProvider()
        : this(new Win32ClipboardPlatform())
    {
    }

    internal WindowsClipboardProvider(IClipboardPlatform platform)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
    }

    public ValueTask<ClipboardTextSnapshot> ReadTextAsync(
        int maximumCharacters,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (maximumCharacters is < 1 or > MaximumCharacters)
        {
            throw new ClipboardProviderException("invalid_limit");
        }

        ClipboardTextSnapshot first = _platform.ReadText(maximumCharacters);
        cancellationToken.ThrowIfCancellationRequested();
        ClipboardTextSnapshot second = _platform.ReadText(maximumCharacters);
        if (first != second) throw new ClipboardProviderException("clipboard_changed_during_read");
        return ValueTask.FromResult(second);
    }

    public ValueTask<ClipboardWriteResult> WriteTextAsync(
        string text,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        ValidateText(text);
        uint beforeSequence = _platform.GetSequenceNumber();
        string? beforeText = null;
        try
        {
            beforeText = _platform.ReadText(MaximumCharacters).Text;
        }
        catch (ClipboardProviderException exception) when (exception.Code == "clipboard_has_no_text")
        {
        }

        cancellationToken.ThrowIfCancellationRequested();
        _platform.ReplaceText(text);
        cancellationToken.ThrowIfCancellationRequested();
        ClipboardTextSnapshot first = _platform.ReadText(MaximumCharacters);
        ClipboardTextSnapshot second = _platform.ReadText(MaximumCharacters);
        if (first != second || !string.Equals(first.Text, text, StringComparison.Ordinal) || first.Truncated)
        {
            throw new ClipboardProviderException("verification_failed");
        }

        bool changed = beforeSequence != first.SequenceNumber
            && !string.Equals(beforeText, text, StringComparison.Ordinal);
        return ValueTask.FromResult(new ClipboardWriteResult(
            first.SequenceNumber,
            text.Length,
            changed));
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

internal sealed partial class Win32ClipboardPlatform : IClipboardPlatform
{
    private const uint UnicodeText = 13;
    private const uint MoveableMemory = 0x0002;

    public uint GetSequenceNumber() => GetClipboardSequenceNumber();

    public ClipboardTextSnapshot ReadText(int maximumCharacters)
    {
        Open();
        try
        {
            if (!IsClipboardFormatAvailable(UnicodeText))
            {
                throw new ClipboardProviderException("clipboard_has_no_text");
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
                    GetClipboardSequenceNumber());
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
                    throw new ClipboardProviderException("clipboard_partial_write");
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

    private static void Open()
    {
        if (!OpenClipboard(0)) throw new ClipboardProviderException("clipboard_busy");
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
    private static partial uint GetClipboardSequenceNumber();

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
