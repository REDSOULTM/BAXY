using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Arranque en frío: la App no vuelve a leer gigabytes de modelo y voz en cada
/// arranque cuando nada cambió, y cualquier cambio sigue verificándose contra
/// el hash registrado.
/// </summary>
[TestFixture]
public sealed class RuntimeFileHashCacheTests
{
    private static readonly string[] SttFiles =
    [
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    ];

    [Test]
    public void ASecondStartWithUnchangedFilesReadsNoFile()
    {
        using var fixture = Fixture.Create();
        var first = new CountingHasher();
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, first.Hash), Is.Not.Null);
        Assert.That(first.Calls, Has.Count.EqualTo(8));

        var second = new CountingHasher();
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, second.Hash), Is.Not.Null);
        Assert.That(second.Calls, Is.Empty);
    }

    [Test]
    public void ARewrittenModelIsReadAgainAndRejected()
    {
        using var fixture = Fixture.Create();
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, new CountingHasher().Hash), Is.Not.Null);

        // Same size, other bytes, timestamp moved to another old value.
        File.WriteAllBytes(fixture.Gguf, [2]);
        Fixture.Age(fixture.Gguf, TimeSpan.FromHours(3));

        var again = new CountingHasher();
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, again.Hash), Is.Null);
        Assert.That(again.Calls, Does.Contain(fixture.Gguf));
    }

    [Test]
    public void AGrownSpeechFileIsReadAgainAndRejected()
    {
        using var fixture = Fixture.Create();
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, new CountingHasher().Hash), Is.Not.Null);

        string tokens = Path.Combine(fixture.Stt, "tokens.txt");
        File.AppendAllText(tokens, "changed");

        var again = new CountingHasher();
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, again.Hash), Is.Null);
        Assert.That(again.Calls, Does.Contain(tokens));
    }

    [Test]
    public void AFileWrittenJustBeforeItsHashIsNeverRemembered()
    {
        using var fixture = Fixture.Create(age: false);
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, new CountingHasher().Hash), Is.Not.Null);

        var again = new CountingHasher();
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, again.Hash), Is.Not.Null);
        Assert.That(again.Calls, Has.Count.EqualTo(8));
    }

    [Test]
    public void AForgedStoreCannotMakeAChangedFilePass()
    {
        using var fixture = Fixture.Create();
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, new CountingHasher().Hash), Is.Not.Null);
        string store = Path.Combine(fixture.Root, RuntimeFileHashCache.FileName);
        Assert.That(File.Exists(store), Is.True);

        File.WriteAllText(store, "{ not json");
        var unreadable = new CountingHasher();
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, unreadable.Hash), Is.Not.Null);
        Assert.That(unreadable.Calls, Has.Count.EqualTo(8));

        // The store only remembers what a file hashed to; acceptance still
        // compares it with the registered hash.
        File.WriteAllBytes(fixture.Gguf, [9, 9]);
        Fixture.Age(fixture.Gguf, TimeSpan.FromHours(4));
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, new CountingHasher().Hash), Is.Null);
        Assert.That(MindRuntimeDiscovery.LoadRegistered(fixture.Manifest, new CountingHasher().Hash), Is.Null);
    }

    [Test]
    [Explicit("Microbenchmark del arranque en frío sobre el runtime registrado de este equipo (lee unos 3,4 GB).")]
    [NonParallelizable]
    public void RegisteredRuntimeVerificationBeforeAndAfterTheStore()
    {
        string registered = MindRuntimeDiscovery.DefaultRegistrationPath();
        Assume.That(File.Exists(registered), Is.True);
        string root = Path.Combine(Path.GetTempPath(), "baxy-hash-store-bench-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            string manifest = Path.Combine(root, Path.GetFileName(registered));
            File.Copy(registered, manifest);
            var cold = Stopwatch.StartNew();
            Assert.That(MindRuntimeDiscovery.LoadRegistered(manifest), Is.Not.Null);
            cold.Stop();
            var warm = Stopwatch.StartNew();
            Assert.That(MindRuntimeDiscovery.LoadRegistered(manifest), Is.Not.Null);
            warm.Stop();
            TestContext.Progress.WriteLine(
                $"runtime verification: without store {cold.Elapsed.TotalMilliseconds:F0} ms, with store {warm.Elapsed.TotalMilliseconds:F0} ms");
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private sealed class CountingHasher
    {
        internal List<string> Calls { get; } = [];

        internal string Hash(string path)
        {
            Calls.Add(Path.GetFullPath(path));
            return MindRuntimeDiscovery.FileSha256(path);
        }
    }

    private sealed record Fixture(string Root, string Manifest, string Gguf, string Stt) : IDisposable
    {
        internal static Fixture Create(bool age = true)
        {
            string root = Path.Combine(Path.GetTempPath(), "baxy-hash-store-" + Guid.NewGuid().ToString("N"));
            string python = Touch(Path.Combine(root, "venv", "python.exe"));
            string pythonPath = Path.Combine(root, "source");
            Touch(Path.Combine(pythonPath, "baxy_mind", "__main__.py"));
            string gguf = Touch(Path.Combine(root, "models", "gemma.gguf"));
            string server = Touch(Path.Combine(root, "llama", "llama-server.exe"));
            string stt = Path.Combine(root, "stt");
            foreach (string name in SttFiles)
            {
                Touch(Path.Combine(stt, name));
            }

            string wake = Path.Combine(root, "wake", "baxy-wakeword-v1.json");
            Directory.CreateDirectory(Path.GetDirectoryName(wake)!);
            File.WriteAllText(wake, "{\"schema\":\"baxy-wakeword-v1\"}");
            if (age)
            {
                foreach (string file in Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories))
                {
                    Age(file, TimeSpan.FromHours(1));
                }
            }

            string manifest = Path.Combine(root, "mind-runtime-v1.json");
            File.WriteAllText(
                manifest,
                $$"""
                {
                  "schema": "baxy-mind-runtime-v1",
                  "python": {{Json(python)}},
                  "python_sha256": {{Json(Sha256(python))}},
                  "python_path": {{Json(pythonPath)}},
                  "gguf": {{Json(gguf)}},
                  "gguf_sha256": {{Json(Sha256(gguf))}},
                  "llama_server": {{Json(server)}},
                  "llama_server_sha256": {{Json(Sha256(server))}},
                  "stt_dir": {{Json(stt)}},
                  "stt_sha256": {{Json(SttSha256(stt))}},
                  "wake_manifest": {{Json(Path.GetFullPath(wake))}},
                  "wake_manifest_sha256": {{Json(Sha256(wake))}},
                  "tts_model": null,
                  "tts_sha256": null,
                  "ngl": 99,
                  "wake_on_start": true
                }
                """);
            return new Fixture(root, manifest, gguf, stt);
        }

        internal static void Age(string path, TimeSpan age) =>
            File.SetLastWriteTimeUtc(path, DateTime.UtcNow - age);

        public void Dispose() => Directory.Delete(Root, recursive: true);

        private static string Touch(string path)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllBytes(path, [1]);
            return Path.GetFullPath(path);
        }

        private static string Sha256(string path) =>
            Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)));

        private static string SttSha256(string directory)
        {
            var value = new StringBuilder();
            foreach (string name in SttFiles)
            {
                value.Append(name).Append(':').Append(Sha256(Path.Combine(directory, name))).Append('\n');
            }

            return Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value.ToString())));
        }

        private static string Json(string value) => System.Text.Json.JsonSerializer.Serialize(value);
    }
}
