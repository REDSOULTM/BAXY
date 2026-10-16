namespace Baxy.Providers.Windows.Clipboard;

public sealed record ClipboardTextSnapshot(
    string Text,
    int CharacterCount,
    bool Truncated,
    uint SequenceNumber);

public sealed record ClipboardWriteResult(
    uint SequenceNumber,
    int CharacterCount,
    bool Changed);

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
}

internal interface IClipboardPlatform
{
    uint GetSequenceNumber();

    ClipboardTextSnapshot ReadText(int maximumCharacters);

    void ReplaceText(string text);
}
