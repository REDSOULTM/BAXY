using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// Feria (caso 15): the games this Steam client knows, read from a synthetic appinfo.vdf written here as SteamDatabase's
// SteamAppInfo documents it (v40: keys as strings; v41: keys as indexes into the string table at the file's end).
[TestFixture]
public sealed class SteamAppInfoTests
{
    [TestCase(0x07564428u)]
    [TestCase(0x07564429u)]
    public void OnlyTheGamesAreReadWithTheirNames(uint magic)
    {
        byte[] file = AppInfo(magic, [(10, "game", "First Game"), (11, "DLC", "First Game Soundtrack"), (12, "Game", "Ünïcode Game")]);

        IReadOnlyList<SteamStoreTitle> games = SteamAppInfo.Games(file);

        Assert.That(games, Is.EqualTo(new SteamStoreTitle[] { new("10", "First Game"), new("12", "Ünïcode Game") }));
    }

    [Test]
    public void AnotherFormatOrACutFileIsNotRead()
    {
        byte[] file = AppInfo(0x07564429u, [(10, "game", "First Game")]);
        byte[] older = [.. file];
        older[0] = 0x26;

        Assert.Multiple(() =>
        {
            Assert.That(() => SteamAppInfo.Games(older), Throws.InstanceOf<InvalidDataException>());
            Assert.That(() => SteamAppInfo.Games(file.AsSpan(0, file.Length - 30)), Throws.InstanceOf<InvalidDataException>());
            Assert.That(() => SteamAppInfo.Games(file.AsSpan(0, 40)), Throws.InstanceOf<InvalidDataException>());
        });
    }

    [Test]
    public void AFileNotThereIsNotRead() =>
        Assert.That(SteamAppInfo.ReadGames(Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N"), "appinfo.vdf")),
            Is.Null);

    // appid, size, info state, last updated, PICS token, SHA-1, change number, binary SHA-1, then the binary KeyValues
    // «appinfo» { appid (int32), common { name, type }, extended { } }.
    private static byte[] AppInfo(uint magic, (uint AppId, string Type, string Name)[] apps)
    {
        bool table = magic == 0x07564429u;
        var strings = new List<string>();
        using var stream = new MemoryStream();
        using var writer = new BinaryWriter(stream);
        writer.Write(magic);
        writer.Write(1u);
        long tableOffset = stream.Position;
        if (table) writer.Write(0L);
        foreach ((uint appId, string type, string name) in apps)
        {
            using var blob = new MemoryStream();
            using var kv = new BinaryWriter(blob);
            void Key(string key)
            {
                if (!table) { kv.Write(Encoding.UTF8.GetBytes(key)); kv.Write((byte)0); return; }
                if (!strings.Contains(key)) strings.Add(key);
                kv.Write(strings.IndexOf(key));
            }
            void Text(string key, string value)
            {
                kv.Write((byte)1); Key(key); kv.Write(Encoding.UTF8.GetBytes(value)); kv.Write((byte)0);
            }
            kv.Write((byte)0); Key("appinfo");
            kv.Write((byte)2); Key("appid"); kv.Write((int)appId);
            kv.Write((byte)0); Key("common");
            kv.Write((byte)7); Key("gameid"); kv.Write((ulong)appId);
            Text("name", name);
            Text("type", type);
            kv.Write((byte)8);
            kv.Write((byte)0); Key("extended");
            Text("name", "not the common name");
            kv.Write((byte)8);
            kv.Write((byte)8);
            kv.Write((byte)8);
            kv.Flush();
            writer.Write(appId);
            writer.Write((uint)(4 + 4 + 8 + 20 + 4 + 20 + blob.Length));
            writer.Write(2u);
            writer.Write(1_700_000_000u);
            writer.Write(0UL);
            writer.Write(new byte[20]);
            writer.Write(7u);
            writer.Write(new byte[20]);
            writer.Write(blob.ToArray());
        }
        writer.Write(0u);
        if (table)
        {
            long at = stream.Position;
            writer.Write((uint)strings.Count);
            foreach (string value in strings) { writer.Write(Encoding.UTF8.GetBytes(value)); writer.Write((byte)0); }
            stream.Position = tableOffset;
            writer.Write(at);
        }
        writer.Flush();
        return stream.ToArray();
    }
}
