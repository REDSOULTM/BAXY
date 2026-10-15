using System.IO;
using System.Text;

namespace Baxy.App;

/// <summary>
/// An append-only JSONL record of the profile with a size cap (auditoría de
/// estabilidad r19, hallazgo 4: the presence samples reached 29 MB and the
/// conversation log grew without end). Once the live file would pass its cap it
/// becomes the single archive (<c>&lt;file&gt;.1</c>, replacing the previous
/// one) and a new live file starts, so the record never holds more than two caps.
/// </summary>
internal sealed class BoundedJsonlFile
{
    internal const long DefaultMaximumBytes = 4L * 1024 * 1024;
    internal const string ArchiveSuffix = ".1";

    private readonly long _maximumBytes;

    internal BoundedJsonlFile(string filePath, long maximumBytes = DefaultMaximumBytes)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(filePath);
        ArgumentOutOfRangeException.ThrowIfLessThan(maximumBytes, 1);
        FilePath = filePath;
        _maximumBytes = maximumBytes;
    }

    internal string FilePath { get; }

    internal string ArchivePath => FilePath + ArchiveSuffix;

    internal void AppendLine(string line)
    {
        ArgumentNullException.ThrowIfNull(line);
        string text = line + Environment.NewLine;
        long incoming = Encoding.UTF8.GetByteCount(text);
        var live = new FileInfo(FilePath);
        if (live.Exists && live.Length > 0 && live.Length + incoming > _maximumBytes)
        {
            File.Move(FilePath, ArchivePath, overwrite: true);
        }

        File.AppendAllText(FilePath, text);
    }
}
