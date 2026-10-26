using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using Baxy.Providers.Windows.Filesystem;
using Baxy.Providers.Windows.Infrastructure;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Holdout v6 V6E041 («agrégale al file jugadores.txt … la línea: Matías, arquero», 8 of 8 runs file.write without
/// append; in 6 the file was read and replaced by that line alone under its observed hash, and the reply said
/// «agregué»): a file.write that would replace a file of the person's that has text with a text keeping little of it is
/// refused once before any effect, with how much the file has and the exact call that appends; the same replacement
/// again goes on, asking the person first in normal mode (aid overwrite_guard).
/// </summary>
[TestFixture]
public sealed class OverwriteGuardTests
{
    private const string Players = "Benja, delantero\r\nTomi, defensa\r\nFeña, volante\r\n";
    private const string Path = "Liga de Futbolito/jugadores.txt";

    // The bench's sequence on the real provider and kernel: written without append, refused; read; written under the
    // hash the read gave. That replacement asks the person (no effect without the yes), and the append the refusal named
    // keeps every line. With BAXY_AYUDAS=none it goes as before: the file is replaced unasked.
    [TestCase("all")]
    [TestCase("none")]
    public async Task TheBenchSequenceAsksBeforeTheReplacementAndTheNamedAppendKeepsTheLines(string aids)
    {
        using IDisposable setting = ModelAids.Use(aids);
        bool guarded = aids == "all";
        using var place = new Place();
        FilesystemMutationResult original = place.Seed(Players);
        await using FileInvocationJournal journal = await place.Journal();
        using var engine = new MissionEngine(new OperationRegistry(FilesystemHandlers.Create(place.Provider)), journal);

        OperationResponse refused = await engine.ExecuteAsync(
            Request("""{"relativePath":"Liga de Futbolito/jugadores.txt","text":"Matías, arquero","folder":"documents"}"""),
            CancellationToken.None);
        OperationResponse read = await engine.ExecuteAsync(
            Request($$"""{"resourceId":"{{original.ResourceId}}"}""", "filesystem.read.text"), CancellationToken.None);
        OperationResponse replaced = await engine.ExecuteAsync(
            Request($$"""{"relativePath":"Liga de Futbolito/jugadores.txt","text":"Matías, arquero","folder":"documents","expectedSha256":"{{original.Sha256}}"}"""),
            CancellationToken.None);
        string afterReplace = place.Text();

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("version_conflict"));
            Assert.That(read.Status, Is.EqualTo(OperationStatuses.Completed));
            if (guarded)
            {
                JsonElement facts = refused.Result!.Value;
                Assert.That(facts.GetProperty("lines").GetInt32(), Is.EqualTo(3));
                Assert.That(facts.GetProperty("characters").GetInt32(), Is.EqualTo(48));
                Assert.That(facts.GetProperty("linesKept").GetInt32(), Is.Zero);
                Assert.That(facts.GetProperty("next").GetString(), Is.EqualTo(
                    "nothing was written: jugadores.txt is already there with 3 lines (48 characters), and this call "
                    + "would replace all of it with the text, which keeps none of its lines. If the person asked to add "
                    + "the text: file_write {\"relativePath\":\"Liga de Futbolito/jugadores.txt\",\"folder\":\"documents\","
                    + "\"text\":\"Matías, arquero\",\"append\":true}, a new line at its end that keeps what it has. If the "
                    + "person asked to replace all it has: the same call with expectedSha256 (currentSha256). Their words "
                    + "pick the call, so ask them nothing: in normal mode BAXY itself asks their yes before a replacement"));
                Assert.That(replaced.ErrorCode, Is.EqualTo(ConfirmationChallengeContract.RequiredErrorCode));
                Assert.That(afterReplace, Is.EqualTo(Players));
                Assert.That(place.Bin.Recycled, Is.Empty);
            }
            else
            {
                Assert.That(refused.Result!.Value.TryGetProperty("lines", out _), Is.False);
                Assert.That(replaced.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(afterReplace, Is.EqualTo("Matías, arquero"));
            }
        });

        if (!guarded)
        {
            return;
        }

        OperationResponse appended = await engine.ExecuteAsync(
            Request("""{"relativePath":"Liga de Futbolito/jugadores.txt","folder":"documents","text":"Matías, arquero","append":true}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(appended.Status, Is.EqualTo(OperationStatuses.Completed));
            // The bench's oracle: four lines, the new one last (an append adds it as a line of its own).
            Assert.That(place.Text(), Is.EqualTo(Players + "Matías, arquero"));
        });
    }

    // A replacement under the hash a read gave, with no refusal before it: refused once, before any effect, with the
    // facts and the append call; the same call again asks the person, and with their yes it replaces the file, its
    // previous version to the Recycle Bin.
    [Test]
    public async Task AReplacementThatLosesTheTextIsRefusedOnceThenAsksAndRunsOnTheYes()
    {
        using IDisposable setting = ModelAids.Use("all");
        using var place = new Place();
        FilesystemMutationResult original = place.Seed(Players);
        await using FileInvocationJournal journal = await place.Journal();
        using var engine = new MissionEngine(new OperationRegistry(FilesystemHandlers.Create(place.Provider)), journal);
        string replace = $$"""{"relativePath":"Liga de Futbolito/jugadores.txt","text":"Matías, arquero","folder":"documents","expectedSha256":"{{original.Sha256}}"}""";

        OperationResponse refused = await engine.ExecuteAsync(Request(replace), CancellationToken.None);
        OperationRequest again = Request(replace);
        OperationResponse asked = await engine.ExecuteAsync(again, CancellationToken.None);
        string beforeTheYes = place.Text();
        OperationResponse confirmed = await engine.ExecuteAsync(
            again with
            {
                RequestId = Guid.NewGuid().ToString("D"),
                ConfirmationToken = asked.Result!.Value.GetProperty("token").GetString(),
            },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("replacement_loses_text"));
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            JsonElement facts = refused.Result!.Value;
            Assert.That(facts.GetProperty("currentSha256").GetString(), Is.EqualTo(original.Sha256));
            Assert.That(facts.GetProperty("lines").GetInt32(), Is.EqualTo(3));
            Assert.That(facts.GetProperty("next").GetString(), Is.EqualTo(
                "nothing was written: jugadores.txt has 3 lines (48 characters), and this call would replace all of it "
                + "with the text, which keeps none of its lines. If the person asked to add the text: file_write "
                + "{\"relativePath\":\"Liga de Futbolito/jugadores.txt\",\"folder\":\"documents\",\"text\":\"Matías, "
                + "arquero\",\"append\":true}, a new line at its end that keeps what it has. If the person asked to "
                + "replace all it has: the same call again. Their words pick the call, so ask them nothing: in normal "
                + "mode BAXY itself asks their yes before a replacement"));
            Assert.That(asked.ErrorCode, Is.EqualTo(ConfirmationChallengeContract.RequiredErrorCode));
            Assert.That(beforeTheYes, Is.EqualTo(Players));
            Assert.That(confirmed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(place.Text(), Is.EqualTo("Matías, arquero"));
            Assert.That(place.Bin.Recycled.Select(File.ReadAllText), Is.EqualTo(new[] { Players }));
        });
    }

    // «sobrescribe repertorio.txt … con la palabra pendiente» (V6E048): without the hash, refused with the facts; under
    // the hash that refusal told, it asks once (never a second refusal after the yes) and replaces on the yes.
    [Test]
    public async Task AReplacementTheRefusalAlreadyToldAsksOnceAndRunsOnTheYes()
    {
        using IDisposable setting = ModelAids.Use("all");
        using var place = new Place();
        place.Seed("Aleluya de Cohen\r\nGracias a la vida\r\nCanción de cuna\r\n");
        await using FileInvocationJournal journal = await place.Journal();
        using var engine = new MissionEngine(new OperationRegistry(FilesystemHandlers.Create(place.Provider)), journal);

        OperationResponse refused = await engine.ExecuteAsync(
            Request("""{"relativePath":"Liga de Futbolito/jugadores.txt","text":"pendiente","folder":"documents"}"""),
            CancellationToken.None);
        string told = refused.Result!.Value.GetProperty("currentSha256").GetString()!;
        OperationRequest replace = Request(
            $$"""{"relativePath":"Liga de Futbolito/jugadores.txt","text":"pendiente","folder":"documents","expectedSha256":"{{told}}"}""");
        OperationResponse asked = await engine.ExecuteAsync(replace, CancellationToken.None);
        OperationResponse confirmed = await engine.ExecuteAsync(
            replace with
            {
                RequestId = Guid.NewGuid().ToString("D"),
                ConfirmationToken = asked.Result!.Value.GetProperty("token").GetString(),
            },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("version_conflict"));
            Assert.That(asked.ErrorCode, Is.EqualTo(ConfirmationChallengeContract.RequiredErrorCode));
            Assert.That(confirmed.Status, Is.EqualTo(OperationStatuses.Completed), confirmed.ErrorCode);
            Assert.That(place.Text(), Is.EqualTo("pendiente"));
        });
    }

    // Bypass asks nothing: the refusal still comes once, and the same call again replaces.
    [Test]
    public async Task InBypassTheRefusalComesOnceAndTheSameCallAgainReplaces()
    {
        using IDisposable setting = ModelAids.Use("all");
        using var place = new Place();
        FilesystemMutationResult original = place.Seed(Players);
        await using FileInvocationJournal journal = await place.Journal();
        using var engine = new MissionEngine(
            new OperationRegistry(FilesystemHandlers.Create(place.Provider)),
            journal,
            new MissionEngineOptions { ConfirmationMode = () => ConfirmationMode.Bypass });
        string replace = $$"""{"relativePath":"Liga de Futbolito/jugadores.txt","text":"Matías, arquero","folder":"documents","expectedSha256":"{{original.Sha256}}"}""";

        OperationResponse refused = await engine.ExecuteAsync(Request(replace), CancellationToken.None);
        OperationResponse replaced = await engine.ExecuteAsync(Request(replace), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("replacement_loses_text"));
            Assert.That(replaced.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(place.Text(), Is.EqualTo("Matías, arquero"));
        });
    }

    // What loses nothing, or is an edit, goes straight under its hash: an empty file (or only blanks), a text that holds
    // all the file had (a line added at the start or the end by rewriting it), and one that keeps more than half of its
    // words (a line corrected, one of three taken out). One that keeps half or less is refused.
    [TestCase("", "Matías, arquero", false)]
    [TestCase(" \r\n\r\n", "Matías, arquero", false)]
    [TestCase(Players, "Matías, arquero\r\n" + Players, false)]
    [TestCase(Players, "Benja, delantero\nTomi, defensa\nFeña, volante\nMatías, arquero\n", false)]
    [TestCase(Players, "Benja, delantero\r\nTomi, defensa\r\nFernanda, volante\r\n", false)]
    [TestCase(Players, "Benja, delantero\r\nFeña, volante\r\n", false)]
    [TestCase(Players, "Benja, delantero\r\nMatías, arquero\r\n", true)]
    [TestCase("Benja, delantero\r\nTomi, defensa\r\n", "Benja, delantero\r\nMatías, arquero\r\n", true)]
    [TestCase(Players, "", true)]
    public async Task WhatLosesNothingOrIsAnEditGoesStraight(string before, string text, bool refused)
    {
        using IDisposable setting = ModelAids.Use("all");
        using var place = new Place();
        FilesystemMutationResult original = place.Seed(before);

        OperationOutcome outcome = await Handle(place.Provider, JsonSerializer.Serialize(new
        {
            relativePath = Path,
            text,
            folder = "documents",
            expectedSha256 = original.Sha256,
        }));

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(refused ? "replacement_loses_text" : null));
            Assert.That(place.Text(), Is.EqualTo(refused ? before : text));
        });
    }

    // A write without the hash whose text keeps all the file has loses nothing: its refusal says only what append and
    // the hash do (replace_or_append), with no count of lines.
    [Test]
    public async Task AVersionConflictThatLosesNothingKeepsTheSentenceOfBothWays()
    {
        using IDisposable setting = ModelAids.Use("all");
        using var place = new Place();
        place.Seed(Players);

        OperationOutcome refused = await Handle(place.Provider, JsonSerializer.Serialize(new
        {
            relativePath = Path,
            text = Players + "Matías, arquero\r\n",
            folder = "documents",
        }));

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("version_conflict"));
            Assert.That(refused.Result!.Value.TryGetProperty("lines", out _), Is.False);
            Assert.That(refused.Result!.Value.GetProperty("next").GetString(), Does.StartWith(
                "nothing was written: jugadores.txt is already there; file_write with append true adds"));
            Assert.That(place.Text(), Is.EqualTo(Players));
        });
    }

    // A file that is not text (bytes that are no UTF-8) keeps nothing of itself in a text: it is refused once too.
    [Test]
    public async Task AFileThatIsNotTextIsRefusedOnce()
    {
        using IDisposable setting = ModelAids.Use("all");
        using var place = new Place();
        string full = place.Full();
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(full)!);
        File.WriteAllBytes(full, [0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10]);
        string hash = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(full)))
            .ToLowerInvariant();

        OperationOutcome outcome = await Handle(place.Provider, JsonSerializer.Serialize(new
        {
            relativePath = Path,
            text = "hola",
            folder = "documents",
            expectedSha256 = hash,
        }));

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("replacement_loses_text"));
            Assert.That(outcome.Result!.Value.TryGetProperty("lines", out _), Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("size").GetInt64(), Is.EqualTo(6));
            Assert.That(File.ReadAllBytes(full), Has.Length.EqualTo(6));
        });
    }

    // A long text is not repeated in the refusal: the append call names it as the same text.
    [Test]
    public async Task ALongTextIsNotRepeatedInTheAppendCall()
    {
        using IDisposable setting = ModelAids.Use("all");
        using var place = new Place();
        FilesystemMutationResult original = place.Seed(Players);
        string text = string.Concat(Enumerable.Repeat("palabra ", 100));

        OperationOutcome outcome = await Handle(place.Provider, JsonSerializer.Serialize(new
        {
            relativePath = Path,
            text,
            folder = "documents",
            expectedSha256 = original.Sha256,
        }));

        string next = outcome.Result!.Value.GetProperty("next").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("replacement_loses_text"));
            Assert.That(next, Does.Contain("file_write with the same relativePath, folder and text, and append true"));
            Assert.That(next, Does.Not.Contain("palabra palabra"));
        });
    }

    private static OperationRequest Request(string arguments, string operation = "file.write")
    {
        using JsonDocument document = JsonDocument.Parse(arguments);
        return new OperationRequest(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            operation,
            document.RootElement.Clone());
    }

    private static ValueTask<OperationOutcome> Handle(IFilesystemProvider provider, string arguments)
    {
        using JsonDocument document = JsonDocument.Parse(arguments);
        return new FilesystemHandler("file.write", provider).ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", document.RootElement.Clone()),
            CancellationToken.None);
    }

    // A temporary «documents» with its Recycle Bin, and the file of the bench under it.
    private sealed class Place : IDisposable
    {
        private readonly string _root = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "baxy-overwrite-guard-" + Guid.NewGuid().ToString("N"));

        internal Place()
        {
            string documents = System.IO.Path.Combine(_root, "documents");
            Directory.CreateDirectory(documents);
            Bin = new KnownFileToolsTests.FolderRecycleBin(System.IO.Path.Combine(_root, "bin"));
            Provider = new LocalFilesystemProvider(System.IO.Path.Combine(_root, "sandbox"), Bin)
            {
                KnownFolderPath = folder => folder == "documents" ? documents : System.IO.Path.Combine(_root, "absent"),
            };
        }

        internal KnownFileToolsTests.FolderRecycleBin Bin { get; }

        internal LocalFilesystemProvider Provider { get; }

        internal string Full() => System.IO.Path.Combine(_root, "documents", "Liga de Futbolito", "jugadores.txt");

        // The person's file, as the bench's setup writes it (UTF-8 without a byte order mark).
        internal FilesystemMutationResult Seed(string text)
        {
            Directory.CreateDirectory(System.IO.Path.GetDirectoryName(Full())!);
            File.WriteAllText(Full(), text, new System.Text.UTF8Encoding(false));
            // A no-op write of the same text gives its handle and hash without changing it (reachedState).
            return Provider.WriteText(Path, text, null, "documents");
        }

        internal string Text() => File.ReadAllText(Full());

        internal Task<FileInvocationJournal> Journal() => FileInvocationJournal.OpenAsync(
            System.IO.Path.Combine(_root, "journal.jsonl"), new JournalHmacAuthenticator(new byte[32])).AsTask();

        public void Dispose()
        {
            try
            {
                Directory.Delete(_root, recursive: true);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }
}
