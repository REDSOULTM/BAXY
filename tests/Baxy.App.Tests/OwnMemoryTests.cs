using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Owner, 2026-11-08: Settings › Modelo must show all the memory BAXY uses, piece by piece, not only the model's. The
/// processes under BAXY are grouped by what they are, each model server on its own, and the totals are their sums.
/// </summary>
[TestFixture]
public sealed class OwnMemoryTests
{
    private const long Gb = 1L << 30;

    [Test]
    public void EachProcessUnderBaxyIsCountedOnceUnderWhatItIs()
    {
        (int, string)[] processes =
        [
            (10, "Baxy"), (11, "msedgewebview2"), (12, "msedgewebview2"), (13, "baxy-core"), (14, "python"),
            (15, "llama-server"), (16, "llama-server"), (17, "ollama"), (18, "conhost"),
        ];
        var ram = new Dictionary<int, long> { [10] = Gb / 4, [11] = Gb / 4, [12] = Gb / 4, [13] = Gb / 8, [14] = Gb, [15] = Gb / 2, [16] = Gb / 4, [17] = Gb / 8, [18] = 0 };
        var vram = new Dictionary<int, long> { [15] = 4 * Gb, [16] = Gb / 2, [11] = Gb / 8 };

        JsonObject read = OwnMemory.Read(10, processes,
            ids => ids.Sum(id => ram.GetValueOrDefault(id)),
            ids => ids.Sum(id => vram.GetValueOrDefault(id)));

        JsonArray parts = read["parts"]!.AsArray();
        string[] pieces = [.. parts.Select(static p => (string)p!["piece"]!)];
        Assert.Multiple(() =>
        {
            Assert.That(pieces, Is.EqualTo(new[] { "app", "view", "core", "mind", "model", "model_aux", "ollama", "other" }));
            Assert.That((double)parts[1]!["ramGb"]!, Is.EqualTo(0.5).Within(0.001), "the two WebView processes, together");
            Assert.That((double)parts[4]!["vramGb"]!, Is.EqualTo(4).Within(0.001), "the model server holding the most video memory");
            Assert.That((double)parts[5]!["vramGb"]!, Is.EqualTo(0.5).Within(0.001));
            Assert.That((string?)parts[7]!["name"], Is.EqualTo("conhost"));
            Assert.That((double)read["ramGb"]!, Is.EqualTo(2.75).Within(0.001));
            Assert.That((double)read["vramGb"]!, Is.EqualTo(4.625).Within(0.001));
        });
    }

    [Test]
    public void AReadingThatCouldNotBeTakenIsNullNeverZero()
    {
        JsonObject read = OwnMemory.Read(10, [(10, "Baxy")], static _ => null, static _ => null);

        Assert.Multiple(() =>
        {
            Assert.That(read["ramGb"], Is.Null);
            Assert.That(read["vramGb"], Is.Null);
            Assert.That(read["parts"]!.AsArray()[0]!["ramGb"], Is.Null);
        });
    }
}
