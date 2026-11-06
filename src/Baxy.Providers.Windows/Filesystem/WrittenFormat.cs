using System.Collections.Frozen;

namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// Encargo 115 (H4): file.write wrote UTF-8 under any name, so «aviso.docx» was told written and Word could not open it.
/// A name asks for a format: a Word document is made of the text (<see cref="External.OfficePackage"/>, read back); a format
/// that holds no plain text is refused, and the receipt says so. Windows' perceived types do not tell them apart (measured on
/// the notebook: .html is «document», .svg «image», .pdf unspecified), so these are the formats whose first bytes are a
/// binary signature, by the name each is known by.
/// </summary>
internal static class WrittenFormat
{
    internal enum Kind
    {
        Text,
        Word,
        NotText,
    }

    internal const string NotTextError = "file_format_not_text";

    private static readonly FrozenSet<string> Binary = FrozenSet.ToFrozenSet(
        [
            ".doc", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".odt", ".ods", ".odp",
            ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico",
            ".mp3", ".wav", ".flac", ".m4a", ".ogg", ".mp4", ".m4v", ".mkv", ".mov", ".avi", ".webm",
            ".zip", ".7z", ".rar", ".gz", ".exe", ".dll", ".msi",
        ],
        StringComparer.OrdinalIgnoreCase);

    internal static Kind Of(string path)
    {
        string extension = Path.GetExtension(path);
        return extension.Equals(".docx", StringComparison.OrdinalIgnoreCase) ? Kind.Word
            : Binary.Contains(extension) ? Kind.NotText
            : Kind.Text;
    }

    // One paragraph per line, blank lines left out, as office.document.create takes a body.
    internal static string[] Lines(string text) =>
        [.. text.ReplaceLineEndings("\n").Split('\n').Select(static line => line.Trim()).Where(static line => line.Length > 0)];

    internal static FilesystemProviderException Refused(string path, bool append) => new(NotTextError)
    {
        Result = External.ExternalJson.Create(writer =>
        {
            string extension = Path.GetExtension(path);
            writer.WriteStartObject();
            writer.WriteBoolean("written", false);
            writer.WriteString("extension", extension);
            writer.WriteString("next", append
                ? $"nothing was written: a {extension} file is not plain text, so a line cannot be added at its end"
                : $"nothing was written: file_write writes plain text, and a {extension} file is another format, which a text "
                    + "under that name would not be");
            writer.WriteEndObject();
        }),
    };
}
