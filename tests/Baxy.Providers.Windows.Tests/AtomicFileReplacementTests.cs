using System.Text.Json.Nodes;
using Baxy.Kernel;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class AtomicFileReplacementTests
{
    private string _directory = string.Empty;

    [SetUp]
    public void CreateDirectory() => _directory = Directory.CreateTempSubdirectory("baxy-c13-").FullName;

    [TearDown]
    public void DeleteDirectory() => Directory.Delete(_directory, recursive: true);

    private string Written(string name, string text)
    {
        string path = Path.Combine(_directory, name);
        File.WriteAllText(path, text);
        return path;
    }

    // C13 (agent-desktop probes/windows/FINDINGS.md:151; measured on this Windows, 10.0.26300): a temporary file moved
    // over a target that an indexer, an antivirus or a backup holds open answered access denied at every sharing mode.
    [Test]
    public void SettingsAreSavedOverAFileHeldOpenThatSharesDeletion()
    {
        string path = Written(FieldSettingsStore.FileName, "{\"antes\":1}");
        using var holder = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);

        FieldSettingsStore.Write(_directory, new JsonObject { ["despues"] = 2 });

        using var reader = new StreamReader(holder);
        Assert.Multiple(() =>
        {
            Assert.That(reader.ReadToEnd(), Is.EqualTo("{\"antes\":1}"), "the holder goes on reading what it opened");
            Assert.That(File.ReadAllText(path), Does.Contain("despues"));
        });
    }

    // Control: what File.Move did and File.Replace cannot, the first save of a file.
    [Test]
    public void AMissingDestinationIsMade()
    {
        string source = Written("nuevo.tmp", "nuevo");
        string destination = Path.Combine(_directory, "guardado.json");

        AtomicFileReplacement.ReplaceOrCreate(source, destination);

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllText(destination), Is.EqualTo("nuevo"));
            Assert.That(File.Exists(source), Is.False);
        });
    }

    // A reader that does not share deletion (File.ReadAllText of the same process) holds it for an instant.
    [Test]
    public async Task AHolderThatDoesNotShareDeletionIsWaitedOut()
    {
        string destination = Written("guardado.json", "viejo");
        string source = Written("nuevo.tmp", "nuevo");
        var holder = new FileStream(destination, FileMode.Open, FileAccess.Read, FileShare.Read);
        Task closing = Task.Delay(100).ContinueWith(_ => holder.Dispose(), TaskScheduler.Default);

        AtomicFileReplacement.ReplaceOrCreate(source, destination);

        await closing;
        Assert.That(File.ReadAllText(destination), Is.EqualTo("nuevo"));
    }

    // The save fails as it failed, with the file whole, when the holder never lets go.
    [Test]
    public void AHolderThatNeverLetsGoLeavesTheFileWhole()
    {
        string destination = Written("guardado.json", "viejo");
        string source = Written("nuevo.tmp", "nuevo");
        using (new FileStream(destination, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            Assert.That(
                () => AtomicFileReplacement.ReplaceOrCreate(source, destination),
                Throws.InstanceOf<IOException>());
        }

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllText(destination), Is.EqualTo("viejo"));
            Assert.That(File.ReadAllText(source), Is.EqualTo("nuevo"));
        });
    }
}
