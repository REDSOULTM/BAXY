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
}

internal interface IClipboardPlatform
{
    uint GetSequenceNumber();

    ClipboardTextSnapshot ReadText(int maximumCharacters);

    void ReplaceText(string text);
}
