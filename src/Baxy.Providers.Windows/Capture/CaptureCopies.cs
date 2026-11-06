using System.Buffers.Binary;
using System.IO.Compression;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.Capture;

/// <summary>A verified copy of a private capture saved where the person asked: the known folder's key, the subfolder of
/// it the copy went into (empty for the folder itself) and the file's name there (never its full path), and the SHA-256
/// of the PNG read back from disk.</summary>
public sealed record SavedCaptureCopy(string Folder, string Subdirectory, string FileName, string Sha256);

/// <summary>
/// Ronda 22 (uso real r18 t2-c16, t3-c11, t4-c09 «…y guárdala en el escritorio»): a private capture copied as a PNG
/// into a known folder. The PNG is written by a minimal encoder over <see cref="ZLibStream"/> (no new dependency); the
/// name is dated and unique and the file is created new, so two captures never overwrite each other or anything the
/// person has; the written file is read back and its hash compared, and a copy that does not match is removed.
/// </summary>
internal static partial class CaptureCopies
{
    private const int MaximumNameAttempts = 100;

    internal static SavedCaptureCopy Save(
        string privateDirectory,
        string captureId,
        string folder,
        Func<string, string?> knownFolder,
        DateTimeOffset now,
        string inside = "")
    {
        if (!CaptureIdPattern().IsMatch(captureId))
            throw new IOException("Capture identity is invalid.");
        // Banco de uso 03-11 (U23): or a folder of the person's inside the known folder (PersonFolders.Place's path).
        string? target = inside.Length == 0 ? TargetDirectory(folder, knownFolder) : InsideDirectory(folder, inside, knownFolder);
        if (target is null)
        {
            throw new ScreenshotUnavailableException("capture_folder_unavailable", "The known folder is not available.")
            {
                Result = inside.Length == 0 ? null : MissingFolder(folder, inside, knownFolder),
            };
        }
        // P2.44 causa 11 (V11D169): where inside the known folder it went (pictures: its Screenshots folder).
        string subdirectory = knownFolder(folder) is { } root ? Path.GetRelativePath(Path.GetFullPath(root), target) : ".";
        if (subdirectory == ".") subdirectory = string.Empty;
        byte[] bmp = File.ReadAllBytes(Path.Combine(privateDirectory, captureId + ".bmp"));
        byte[] png = EncodePng(bmp);
        string hash = Convert.ToHexStringLower(SHA256.HashData(png));
        string stem = "Screenshot " + now.ToLocalTime().ToString("yyyy-MM-dd HHmmss", System.Globalization.CultureInfo.InvariantCulture);
        for (int attempt = 1; attempt <= MaximumNameAttempts; attempt++)
        {
            string name = attempt == 1 ? stem + ".png" : $"{stem} ({attempt}).png";
            string path = Path.Combine(target, name);
            FileStream stream;
            try
            {
                stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough);
            }
            catch (IOException) when (File.Exists(path))
            {
                continue; // a file of that name is there already: it is never replaced
            }

            try
            {
                using (stream)
                {
                    stream.Write(png);
                    stream.Flush(flushToDisk: true);
                }

                if (!string.Equals(Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path))), hash, StringComparison.Ordinal))
                    throw new IOException("Saved capture verification failed.");
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                // Ronda final: the file was created; a failure from here on takes it away, and when it cannot, the copy
                // may stand in the person's folder (never a clean failure).
                try
                {
                    File.Delete(path);
                }
                catch (Exception deleteFailure) when (deleteFailure is IOException or UnauthorizedAccessException)
                {
                    throw new CaptureCopyUnconfirmedException(exception);
                }

                throw;
            }

            return new SavedCaptureCopy(folder, subdirectory, name, hash);
        }

        throw new IOException("No free name for the saved capture.");
    }

    /// <summary>The folder a copy goes to: the known folder itself, or for pictures its screenshots subfolder (the one
    /// Windows keeps its own screenshots in, inside that Pictures folder), created when it is not there yet. Null when the
    /// known folder is not there.</summary>
    internal static string? TargetDirectory(string folder, Func<string, string?> knownFolder)
    {
        string? root = knownFolder(folder);
        if (string.IsNullOrWhiteSpace(root) || !Directory.Exists(root))
            return null;
        if (folder != "pictures")
            return Path.GetFullPath(root);
        string full = Path.GetFullPath(root);
        // The system's screenshots folder when it lies inside the Pictures folder resolved here; else its usual name.
        string screenshots = ScreenshotsFolder() is { } known
            && Path.GetFullPath(known).StartsWith(full.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
            ? Path.GetFullPath(known)
            : Path.Combine(full, "Screenshots");
        Directory.CreateDirectory(screenshots);
        return Path.GetFullPath(screenshots);
    }

    /// <summary>The folder <paramref name="inside"/> of the known folder, when it is there and inside it (never made);
    /// null otherwise.</summary>
    internal static string? InsideDirectory(string folder, string inside, Func<string, string?> knownFolder)
    {
        string? root = knownFolder(folder);
        if (string.IsNullOrWhiteSpace(root) || !Directory.Exists(root))
            return null;
        string full = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar);
        string target = Path.GetFullPath(Path.Combine(full, inside)).TrimEnd(Path.DirectorySeparatorChar);
        return target.StartsWith(full + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
            && Directory.Exists(target)
                ? target
                : null;
    }

    /// <summary>
    /// Encargo 17 (banco uso-cf8d, U23: a folder of the person's and a file name in «path» failed as
    /// capture_folder_unavailable alone): the facts of a folder <paramref name="inside"/> the known folder that is not
    /// there. The part of it that is there and the first part that is not (and whether a file holds that name), that the
    /// path is the folder the copy goes into (its name is dated, never said), and the person's folders of that name under
    /// their known folders (<see cref="Filesystem.PersonFolders.FoldersNamed"/>), each as a path the call takes. Null when
    /// the known folder itself is not there.
    /// </summary>
    internal static System.Text.Json.JsonElement? MissingFolder(string folder, string inside, Func<string, string?> knownFolder)
    {
        string? root = knownFolder(folder);
        if (string.IsNullOrWhiteSpace(root) || !Directory.Exists(root))
            return null;
        string[] parts = inside.Split(['\\', '/'], StringSplitOptions.RemoveEmptyEntries);
        int there = 0;
        string reached = Path.GetFullPath(root);
        while (there < parts.Length && Directory.Exists(Path.Combine(reached, parts[there])))
            reached = Path.Combine(reached, parts[there++]);
        if (there == parts.Length)
            return null;
        string missing = parts[there];
        IReadOnlyList<string> named = Filesystem.PersonFolders.FoldersNamed(missing, knownFolder, out bool complete);
        return External.ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("folder", folder);
            writer.WriteString("existingPath", string.Join('\\', [folder, .. parts[..there]]));
            writer.WriteString("missingPart", missing);
            if (File.Exists(Path.Combine(reached, missing)))
                writer.WriteBoolean("missingPartIsAFile", true);
            writer.WriteBoolean("pathIsAFolder", true);
            writer.WriteStartArray("foldersNamedLikeIt");
            foreach (string path in named)
                writer.WriteStringValue(path);
            writer.WriteEndArray();
            writer.WriteBoolean("searchComplete", complete);
            writer.WriteString("next", "path is the folder the copy goes into, never a file: the copy's name is dated, "
                + "not said; missingPart is not there inside existingPath (nothing was made or saved). foldersNamedLikeIt "
                + "are the person's folders of that name: call again with path set to the one meant, or to existingPath");
            writer.WriteEndObject();
        });
    }

    /// <summary>A 32-bit bottom-up BMP (as <see cref="WindowsScreenshotProvider"/> stores it) as an 8-bit RGB PNG.</summary>
    internal static byte[] EncodePng(byte[] bmp)
    {
        if (bmp.Length < 54 || bmp[0] != (byte)'B' || bmp[1] != (byte)'M')
            throw new IOException("Capture bitmap is invalid.");
        int offset = BinaryPrimitives.ReadInt32LittleEndian(bmp.AsSpan(10));
        int width = BinaryPrimitives.ReadInt32LittleEndian(bmp.AsSpan(18));
        int height = BinaryPrimitives.ReadInt32LittleEndian(bmp.AsSpan(22));
        short bits = BinaryPrimitives.ReadInt16LittleEndian(bmp.AsSpan(28));
        if (bits != 32 || width is < 1 or > 32_768 || height is < 1 or > 32_768
            || offset < 54 || (long)offset + (long)width * height * 4 > bmp.Length)
            throw new IOException("Capture bitmap is invalid.");

        using var output = new MemoryStream();
        output.Write([0x89, (byte)'P', (byte)'N', (byte)'G', 0x0D, 0x0A, 0x1A, 0x0A]);
        byte[] header = new byte[13];
        BinaryPrimitives.WriteInt32BigEndian(header, width);
        BinaryPrimitives.WriteInt32BigEndian(header.AsSpan(4), height);
        header[8] = 8; // bit depth
        header[9] = 2; // truecolour RGB
        WriteChunk(output, "IHDR", header);

        using var compressed = new MemoryStream();
        using (var zlib = new ZLibStream(compressed, CompressionLevel.Fastest, leaveOpen: true))
        {
            byte[] row = new byte[1 + width * 3];
            for (int y = 0; y < height; y++)
            {
                int source = offset + (height - 1 - y) * width * 4; // bottom-up rows
                row[0] = 0; // filter: none
                for (int x = 0; x < width; x++)
                {
                    row[1 + x * 3] = bmp[source + x * 4 + 2];
                    row[2 + x * 3] = bmp[source + x * 4 + 1];
                    row[3 + x * 3] = bmp[source + x * 4];
                }

                zlib.Write(row);
            }
        }

        WriteChunk(output, "IDAT", compressed.ToArray());
        WriteChunk(output, "IEND", []);
        return output.ToArray();
    }

    private static void WriteChunk(Stream output, string type, byte[] data)
    {
        Span<byte> four = stackalloc byte[4];
        BinaryPrimitives.WriteInt32BigEndian(four, data.Length);
        output.Write(four);
        byte[] typed = new byte[4 + data.Length];
        for (int index = 0; index < 4; index++)
            typed[index] = (byte)type[index];
        data.CopyTo(typed, 4);
        output.Write(typed);
        BinaryPrimitives.WriteUInt32BigEndian(four, Crc32(typed));
        output.Write(four);
    }

    private static readonly uint[] CrcTable = BuildCrcTable();

    private static uint[] BuildCrcTable()
    {
        var table = new uint[256];
        for (uint n = 0; n < 256; n++)
        {
            uint c = n;
            for (int k = 0; k < 8; k++)
                c = (c & 1) != 0 ? 0xEDB88320u ^ (c >> 1) : c >> 1;
            table[n] = c;
        }

        return table;
    }

    internal static uint Crc32(ReadOnlySpan<byte> data)
    {
        uint crc = 0xFFFFFFFFu;
        foreach (byte value in data)
            crc = CrcTable[(crc ^ value) & 0xFF] ^ (crc >> 8);
        return crc ^ 0xFFFFFFFFu;
    }

    private static string? ScreenshotsFolder()
    {
        // FOLDERID_Screenshots: where Windows itself saves screenshots (follows a redirected Pictures).
        Guid screenshots = new("b7bede81-df94-4682-a7d8-57a52620b86f");
        try
        {
            if (SHGetKnownFolderPath(in screenshots, 0, 0, out nint path) != 0)
                return null;
            try
            {
                return Marshal.PtrToStringUni(path);
            }
            finally
            {
                Marshal.FreeCoTaskMem(path);
            }
        }
        catch (Exception exception) when (exception is DllNotFoundException or EntryPointNotFoundException)
        {
            return null;
        }
    }

    [GeneratedRegex("^capture_[0-9a-f]{32}$", RegexOptions.CultureInvariant)]
    private static partial Regex CaptureIdPattern();

    [LibraryImport("shell32.dll")]
    private static partial int SHGetKnownFolderPath(in Guid folderId, uint flags, nint token, out nint path);
}

/// <summary>A saved copy that failed after its file was created and could not be taken away: it may stand.</summary>
public sealed class CaptureCopyUnconfirmedException(Exception innerException)
    : IOException("The saved capture failed after its file was created and could not be removed.", innerException);
