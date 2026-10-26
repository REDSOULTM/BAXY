using System.IO;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>The hashes of the mind's runtime files kept between starts (src/Baxy.App/RuntimeFileHashCache.cs).</summary>
[TestFixture]
public sealed class RuntimeFileHashCacheTests
{
    // Revisión de calidad (2026-10-25): the store keeps 64 entries and kept the first 64 paths in order, never the ones
    // this start read: with the store full of older paths (earlier runtimes and models), a file of this runtime that
    // sorts after them was dropped at every save and hashed again, gigabytes, at every start.
    [Test]
    public void AFullStoreKeepsTheFilesThisStartRead()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        try
        {
            string store = Path.Combine(folder, RuntimeFileHashCache.FileName);
            var entries = new JsonArray();
            for (int index = 0; index < 64; index++)
            {
                entries.Add(new JsonObject
                {
                    ["Path"] = $@"A:\old\{index:D2}.gguf",
                    ["Length"] = 1,
                    ["CreationTicks"] = 0,
                    ["LastWriteTicks"] = 0,
                    ["Sha256"] = new string('0', 64),
                });
            }

            File.WriteAllText(store, new JsonObject
            {
                ["Schema"] = RuntimeFileHashCache.Schema,
                ["Entries"] = entries,
            }.ToJsonString());
            string model = Path.Combine(folder, "model.gguf");
            File.WriteAllText(model, "model");
            File.SetLastWriteTimeUtc(model, DateTime.UtcNow.AddHours(-1));
            int hashed = 0;
            string Hasher(string _)
            {
                hashed++;
                return new string('a', 64);
            }

            var first = new RuntimeFileHashCache(store, Hasher);
            _ = first.Sha256(model);
            first.Save();
            var next = new RuntimeFileHashCache(store, Hasher);
            _ = next.Sha256(model);

            Assert.That(hashed, Is.EqualTo(1), "the next start hashed the file again");
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }
}
