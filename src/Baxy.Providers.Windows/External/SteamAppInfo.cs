using System.Buffers.Binary;
using System.Text;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Feria (caso 15): the games this Steam client knows (owned, seen in its library or its store), by the local cache
/// <c>&lt;steam&gt;/appcache/appinfo.vdf</c>, so a title not installed still resolves to its AppID on the PC alone. It is
/// not the whole store, and knowing a game is not owning it.
/// </summary>
/// <remarks>
/// The format, as SteamDatabase's SteamAppInfo documents it (README and SteamAppInfoParser/AppInfo.cs): a magic
/// (0x07564427 v39, 0x07564428 v40, 0x07564429 v41), the universe, and from v41 an int64 offset of a string table (a
/// uint32 count, then that many NUL-terminated UTF-8 strings); then per app its AppID (0 ends the list), a uint32 size of
/// the rest of its entry, info state, last updated, PICS token (uint64), a 20-byte SHA-1, change number, from v40 a
/// 20-byte SHA-1 of the binary data, and the binary KeyValues. Those (ValvePython/vdf binary_loads; ValveKeyValue's
/// KV1BinaryReader for v41): a type byte (0 a nested object, 1 a NUL-terminated UTF-8 string, 2 int32, 3 float32,
/// 4 pointer, 5 a UTF-16 string ended by two NULs, 6 color, 7 uint64, 10 int64; 8 or 11 ends an object), then the key:
/// a NUL-terminated string, or from v41 an int32 index into the string table. The game's name and kind are
/// appinfo/common/name and appinfo/common/type.
/// </remarks>
internal static class SteamAppInfo
{
    private const uint Version39 = 0x07564427;
    private const uint Version40 = 0x07564428;
    private const uint Version41 = 0x07564429;

    // The last file read (its path, size and time written) and its games: a file of several MB is read again only when
    // Steam rewrote it.
    private static (string Path, long Length, DateTime Written, IReadOnlyList<SteamStoreTitle> Games)? _last;
    private static readonly Lock LastLock = new();

    /// <summary>The games in the cache at <paramref name="path"/>; null when it is not there or cannot be read.</summary>
    internal static IReadOnlyList<SteamStoreTitle>? ReadGames(string path)
    {
        try
        {
            // Steam keeps the file open and rewrites it while it runs: read it without denying it that.
            using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            long length = stream.Length;
            DateTime written = File.GetLastWriteTimeUtc(path);
            lock (LastLock)
            {
                if (_last is { } last && last.Path == path && last.Length == length && last.Written == written)
                    return last.Games;
            }
            if (length > Array.MaxLength)
                throw new InvalidDataException("appinfo.vdf larger than an array");
            byte[] bytes = new byte[length];
            stream.ReadExactly(bytes);
            IReadOnlyList<SteamStoreTitle> games = Games(bytes);
            lock (LastLock)
                _last = (path, length, written, games);
            return games;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or InvalidDataException)
        {
            return null;
        }
    }

    /// <summary>The apps whose common type is «game», with their common name. A format not read here, or a file cut
    /// short, throws <see cref="InvalidDataException"/>.</summary>
    internal static IReadOnlyList<SteamStoreTitle> Games(ReadOnlySpan<byte> file)
    {
        uint magic = UInt32(file, 0);
        if (magic is not (Version39 or Version40 or Version41))
            throw new InvalidDataException("appinfo.vdf format not read");
        int at = 8;
        string[]? table = null;
        if (magic == Version41)
        {
            table = StringTable(file, Int64(file, at));
            at += 8;
        }
        var games = new List<SteamStoreTitle>();
        while (true)
        {
            uint appId = UInt32(file, at);
            if (appId == 0)
                return games;
            uint size = UInt32(file, at + 4);
            if (size > file.Length - at - 8)
                throw new InvalidDataException("appinfo.vdf entry cut short");
            int end = at + 8 + (int)size;
            int data = at + 8 + 4 + 4 + 8 + 20 + 4 + (magic >= Version40 ? 20 : 0);
            (string? name, string? type) = Common(file[..end], data, table);
            if (name is { Length: > 0 } && string.Equals(type, "game", StringComparison.OrdinalIgnoreCase))
                games.Add(new(appId.ToString(System.Globalization.CultureInfo.InvariantCulture), name));
            at = end;
        }
    }

    // appinfo/common/name and appinfo/common/type of one app's binary KeyValues.
    private static (string? Name, string? Type) Common(ReadOnlySpan<byte> entry, int at, string[]? table)
    {
        var path = new List<string>();
        string? name = null, type = null;
        while (true)
        {
            byte kind = Byte(entry, at++);
            if (kind is 8 or 11)
            {
                if (path.Count == 0)
                    return (name, type);
                path.RemoveAt(path.Count - 1);
                continue;
            }
            string key;
            if (table is null)
            {
                key = Text(entry, ref at);
            }
            else
            {
                int index = (int)UInt32(entry, at);
                at += 4;
                key = index >= 0 && index < table.Length ? table[index]
                    : throw new InvalidDataException("appinfo.vdf key not in the string table");
            }
            switch (kind)
            {
                case 0:
                    path.Add(key);
                    break;
                case 1:
                    string value = Text(entry, ref at);
                    if (path is ["appinfo", "common"])
                    {
                        if (key == "name") name = value;
                        else if (key == "type") type = value;
                    }
                    break;
                case 2 or 3 or 4 or 6:
                    at += 4;
                    break;
                case 7 or 10:
                    at += 8;
                    break;
                case 5:
                    while (Byte(entry, at) != 0 || Byte(entry, at + 1) != 0) at += 2;
                    at += 2;
                    break;
                default:
                    throw new InvalidDataException("appinfo.vdf value of an unknown type");
            }
        }
    }

    private static string[] StringTable(ReadOnlySpan<byte> file, long offset)
    {
        if (offset < 8 || offset > file.Length)
            throw new InvalidDataException("appinfo.vdf string table outside the file");
        int at = (int)offset;
        uint count = UInt32(file, at);
        at += 4;
        if (count > file.Length - at)
            throw new InvalidDataException("appinfo.vdf string table cut short");
        string[] table = new string[count];
        for (int index = 0; index < table.Length; index++)
            table[index] = Text(file, ref at);
        return table;
    }

    private static string Text(ReadOnlySpan<byte> bytes, ref int at)
    {
        int length = at < bytes.Length ? bytes[at..].IndexOf((byte)0) : -1;
        if (length < 0)
            throw new InvalidDataException("appinfo.vdf string cut short");
        string value = Encoding.UTF8.GetString(bytes.Slice(at, length));
        at += length + 1;
        return value;
    }

    private static byte Byte(ReadOnlySpan<byte> bytes, int at) =>
        at >= 0 && at < bytes.Length ? bytes[at] : throw new InvalidDataException("appinfo.vdf cut short");

    private static uint UInt32(ReadOnlySpan<byte> bytes, int at) =>
        at >= 0 && at <= bytes.Length - 4
            ? BinaryPrimitives.ReadUInt32LittleEndian(bytes[at..])
            : throw new InvalidDataException("appinfo.vdf cut short");

    private static long Int64(ReadOnlySpan<byte> bytes, int at) =>
        at >= 0 && at <= bytes.Length - 8
            ? BinaryPrimitives.ReadInt64LittleEndian(bytes[at..])
            : throw new InvalidDataException("appinfo.vdf cut short");
}
