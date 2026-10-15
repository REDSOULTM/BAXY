using System.Text;

namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// How a text file of the person's is read and written back without changing what was not asked: the byte order mark
/// it carries (UTF-8, UTF-16 LE or BE) is kept, and a file without one is UTF-8. A head with control bytes is no text.
/// </summary>
internal static class TextFileEncoding
{
    internal const int ProbeBytes = 4_096;

    private static readonly UTF8Encoding LenientUtf8 = new(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: false);
    private static readonly UTF8Encoding StrictUtf8 = new(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true);
    private static readonly UnicodeEncoding Utf16Le = new(bigEndian: false, byteOrderMark: false);
    private static readonly UnicodeEncoding Utf16Be = new(bigEndian: true, byteOrderMark: false);

    /// <summary>The encoding the file's byte order mark names (UTF-8 without one) and that mark's length.</summary>
    internal static (Encoding Encoding, int PreambleLength) Detect(ReadOnlySpan<byte> bytes) =>
        bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF ? (LenientUtf8, 3)
        : bytes.Length >= 2 && bytes[0] == 0xFF && bytes[1] == 0xFE ? (Utf16Le, 2)
        : bytes.Length >= 2 && bytes[0] == 0xFE && bytes[1] == 0xFF ? (Utf16Be, 2)
        : (LenientUtf8, 0);

    /// <summary>More than one byte in a hundred of the head is a NUL or a control byte that text does not carry.</summary>
    internal static bool LooksBinary(ReadOnlySpan<byte> head)
    {
        int probe = Math.Min(head.Length, ProbeBytes);
        if (probe == 0) return false;
        if (head.Length >= 2 && (head[0] == 0xFF && head[1] == 0xFE || head[0] == 0xFE && head[1] == 0xFF))
            return false;
        int control = 0;
        for (int index = 0; index < probe; index++)
        {
            byte value = head[index];
            if (value == 0 || (value < 0x20 && value is not (0x09 or 0x0A or 0x0D or 0x0C)))
                control++;
        }
        return control * 100 > probe;
    }

    /// <summary>The text of the file as read (invalid UTF-8 shown as replacement characters).</summary>
    internal static string Decode(ReadOnlySpan<byte> bytes)
    {
        (Encoding encoding, int preamble) = Detect(bytes);
        return encoding.GetString(bytes[preamble..]);
    }

    /// <summary>
    /// The text of a file that will be written back: null when it carries no byte order mark and is not valid UTF-8
    /// (an ANSI file), which re-encoding would change in the parts nobody touched.
    /// </summary>
    internal static string? DecodeExactly(ReadOnlySpan<byte> bytes)
    {
        (Encoding encoding, int preamble) = Detect(bytes);
        if (preamble > 0) return encoding.GetString(bytes[preamble..]);
        try
        {
            return StrictUtf8.GetString(bytes);
        }
        catch (DecoderFallbackException)
        {
            return null;
        }
    }

    /// <summary>The file's own byte order mark and encoding applied to new text.</summary>
    internal static byte[] EncodeLike(ReadOnlySpan<byte> original, string text)
    {
        (Encoding encoding, int preamble) = Detect(original);
        return [.. original[..preamble], .. encoding.GetBytes(text)];
    }

    /// <summary>Text to be appended to the file, in the file's encoding (no mark: it is already at the start).</summary>
    internal static byte[] EncodeAppended(ReadOnlySpan<byte> original, string text) =>
        Detect(original).Encoding.GetBytes(text);
}
