namespace Baxy.Providers.Windows.Clipboard;

public sealed record ClipboardTextSnapshot(
    string Text,
    int CharacterCount,
    bool Truncated,
    uint SequenceNumber)
{
    /// <summary>
    /// The application that copied it asked that clipboard monitors leave it alone. The text is still here: a write's
    /// read-back compares it. Only what the model is given leaves it out.
    /// </summary>
    public bool MarkedPrivate { get; init; }
}

public sealed record ClipboardWriteResult(
    uint SequenceNumber,
    int CharacterCount,
    bool Changed);

/// <summary>
/// What a clipboard without text holds instead: «files» (with how many), «image» or «other». The files' names stay out:
/// the kind and the number answer «¿qué tengo copiado?» and tell it from an empty clipboard, no operation takes the names,
/// and they are private text that would go into the turn's record for that alone.
/// </summary>
public sealed record ClipboardHolds(string Kind, int? Count = null);

public interface IClipboardProvider
{
    ValueTask<ClipboardTextSnapshot> ReadTextAsync(int maximumCharacters, CancellationToken cancellationToken);

    ValueTask<ClipboardWriteResult> WriteTextAsync(string text, CancellationToken cancellationToken);
}

public class ClipboardProviderException(string code) : Exception(code)
{
    public string Code { get; } = code;

    /// <summary>
    /// Round A: the failure came once the person's clipboard was emptied or written (a partial write, a read-back
    /// that did not match or did not answer), so what it holds may already have changed.
    /// </summary>
    public bool EffectMayHaveOccurred { get; init; }

    /// <summary>With clipboard_has_no_text, what it holds instead; null when it holds nothing.</summary>
    public ClipboardHolds? Holds { get; init; }
}

internal interface IClipboardPlatform
{
    uint GetSequenceNumber();

    ClipboardTextSnapshot ReadText(int maximumCharacters);

    void ReplaceText(string text);

    // How many formats the clipboard holds (CountClipboardFormats): a write of text replaces them all.
    int FormatCount() => 0;

    // Whether the window that owns the clipboard answers; an owner that does not would keep a read or a write waiting.
    bool OwnerResponds(CancellationToken cancellationToken) => true;

    // Ends the open of a call left waiting, from another thread.
    void ReleaseAbandonedOpen()
    {
    }
}
