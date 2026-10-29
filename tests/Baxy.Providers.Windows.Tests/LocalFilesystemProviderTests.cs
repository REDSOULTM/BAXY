using System.Globalization;
using System.Text;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Filesystem;
using Baxy.Providers.Windows.Infrastructure;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class LocalFilesystemProviderTests
{
    [Test]
    public void SearchDistinguishesUnsupportedAbsolutePathsFromEmptyNameSearches()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox);
        provider.WriteText("same.txt", "inside", null);
        string outside = Path.Combine(temporary.Path, "same.txt");
        File.WriteAllText(outside, "outside");
        string[] absolutePaths =
        [
            outside,
            outside.Replace('\\', '/'),
            Path.Combine(sandbox, "same.txt"),
            Path.Combine(temporary.Path, "absent.txt"),
            @"\\server\share\same.txt",
        ];

        Assert.Multiple(() =>
        {
            foreach (string path in absolutePaths)
            {
                Assert.That(() => provider.Search(path, 10),
                    Throws.TypeOf<FilesystemProviderException>()
                        .With.Property(nameof(FilesystemProviderException.Code))
                        .EqualTo("absolute_path_search_unsupported"), path);
            }

            FilesystemEntry match = provider.Search("SAME.txt", 10).Entries.Single();
            Assert.That(provider.ReadText(match.ResourceId, 100).Text, Is.EqualTo("inside"));
            Assert.That(provider.Search("absent.txt", 10).Count, Is.Zero);
            Assert.That(File.ReadAllText(outside), Is.EqualTo("outside"));
        });
    }

    // Holdout v6 (V6F010): «lista invitados» said, lista_invitados.txt there, and the search found nothing. A part of a
    // name is its words whatever separates them (space, -, _, .); an append to the name said finds that file as it finds
    // one of that name below (append_target_missing), and makes no second file beside it.
    [Test]
    public void ASearchAndAnAppendFindANameWhoseWordsAreOtherwiseSeparated()
    {
        using TemporaryDirectory temporary = new();
        var provider = InOwnFolder(Path.Combine(temporary.Path, "sandbox"));
        provider.WriteText("lista_invitados.txt", "Ana", null);
        provider.WriteText("notas/Lista-Invitados.2025.md", "Luis", null);
        provider.WriteText("compras.txt", "pan", null);

        Assert.Multiple(() =>
        {
            Assert.That(provider.Search("lista invitados", 10).Entries.Select(entry => entry.Name)
                .Order(StringComparer.Ordinal), Is.EqualTo(new[] { "Lista-Invitados.2025.md", "lista_invitados.txt" }));
            Assert.That(provider.Search("invitados 2025", 10).Count, Is.EqualTo(1));
            Assert.That(provider.Search("compras", 10).Count, Is.EqualTo(1));
            Assert.That(provider.Search("lista compras", 10).Count, Is.Zero);
            FilesystemProviderException refused = Assert.Throws<FilesystemProviderException>(
                () => provider.WriteText("lista invitados.txt", "Pedro", null, append: true))!;
            Assert.That(refused.Code, Is.EqualTo("append_target_missing"));
            Assert.That(refused.Result!.Value.GetProperty("sameNameIn").EnumerateArray().Select(item => item.GetString()),
                Is.EqualTo(new[] { "lista_invitados.txt" }));
            Assert.That(provider.Search("lista invitados.txt", 10).Count, Is.EqualTo(1), "no second file was made");
        });
    }

    [Test]
    public void ARenameThatOnlyChangesCaseIsMade()
    {
        // FT/proveedores goal (review of receipts): «notas.txt» to «Notas.txt» is the same file renamed, not a
        // destination that exists.
        using TemporaryDirectory temporary = new();
        var provider = InOwnFolder(temporary.Path);
        provider.WriteText("notas.txt", "hola", null);
        FilesystemEntry entry = provider.List(string.Empty, 10).Entries.Single();
        FilesystemTextResult read = provider.ReadText(entry.ResourceId, 100);

        FilesystemMutationResult renamed = provider.Transfer(entry.ResourceId, "Notas.txt", read.Sha256, move: true);

        Assert.Multiple(() =>
        {
            Assert.That(renamed.Name, Is.EqualTo("Notas.txt"));
            Assert.That(Directory.GetFiles(temporary.Path).Select(Path.GetFileName), Is.EqualTo(new[] { "Notas.txt" }));
        });
    }

    [Test]
    public void ListReadWriteAndTransferUseOpaqueRevalidatedResources()
    {
        using TemporaryDirectory temporary = new();
        var provider = InOwnFolder(temporary.Path);
        FilesystemMutationResult written = provider.WriteText("entrada.txt", "hola", null);
        FilesystemListResult listed = provider.List(string.Empty, 10);
        string resourceId = listed.Entries.Single().ResourceId;
        FilesystemTextResult read = provider.ReadText(resourceId, 100);
        FilesystemMutationResult copied = provider.Transfer(
            resourceId, "copias/salida.txt", read.Sha256, move: false);

        Assert.Multiple(() =>
        {
            Assert.That(written.ResourceId, Does.Match("^fs_[0-9a-f]{32}$"));
            Assert.That(read.Text, Is.EqualTo("hola"));
            Assert.That(copied.Sha256, Is.EqualTo(read.Sha256));
            Assert.That(File.ReadAllText(
                Path.Combine(temporary.Path, "copias", "salida.txt"), Encoding.UTF8), Is.EqualTo("hola"));
        });
    }

    // file.write (BAXY Renew agent tools): replacing takes the exact current hash and sends the previous version to
    // the Recycle Bin first (a stand-in bin here; WindowsRecycleBinLiveCheck uses the real one).
    [Test]
    public void ExistingWriteRequiresExactHashRecyclesThePreviousVersionAndReachedStateIsSafe()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var provider = InOwnFolder(Path.Combine(temporary.Path, "sandbox"), bin);
        FilesystemMutationResult first = provider.WriteText("dato.txt", "uno", null);
        FilesystemMutationResult replay = provider.WriteText("dato.txt", "uno", null);

        Assert.Multiple(() =>
        {
            Assert.That(first.PreviousVersionRecycled, Is.False);
            Assert.That(replay.ReachedState, Is.True);
            Assert.That(replay.PreviousVersionRecycled, Is.False);
            Assert.That(provider.Hash(replay.ResourceId).Sha256, Is.EqualTo(first.Sha256));
            Assert.That(
                () => provider.WriteText("dato.txt", "dos", new string('0', 64)),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("version_conflict"));
            Assert.That(
                () => provider.WriteText("dato.txt", "dos", null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("version_conflict"));
            Assert.That(bin.Recycled, Is.Empty);
            FilesystemMutationResult replaced = provider.WriteText("dato.txt", "dos", first.Sha256);
            Assert.That(replaced.Sha256, Is.Not.EqualTo(first.Sha256));
            Assert.That(replaced.PreviousVersionRecycled, Is.True);
            Assert.That(bin.Recycled.Select(File.ReadAllText), Is.EqualTo(new[] { "uno" }));
            Assert.That(File.ReadAllText(Path.Combine(temporary.Path, "sandbox", "dato.txt")), Is.EqualTo("dos"));
        });
    }

    // Hallazgo de seguridad E030 (w9-sha), the bench's sequence on the real provider and journal: «sobrescribe notas.txt
    // con el texto 'vacío'» went without the hash, the refusal told the file's current one (currentSha256), and the retry
    // with it replaced the file unasked. The retry asks, bound to it, and with no yes the file stays as it was; a real read
    // of the file (this provider's filesystem.read.text here, file.read in the product) is a sighting it goes on. Without
    // the aid overwrite_guard: with it, a replacement that loses the file's text asks after the read too (OverwriteGuardTests).
    [Test]
    public async Task AReplacementUnderTheHashItsRefusalToldAsksAndTheFileStaysWithoutTheYes()
    {
        using IDisposable aids = ModelAids.Use("none");
        const string before = "uno\r\ndos\r\ntres\r\n";
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var provider = InOwnFolder(sandbox, bin);
        FilesystemMutationResult original = provider.WriteText("BAXY-bench/notas.txt", before, null);
        await using FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
            Path.Combine(temporary.Path, "journal.jsonl"), new JournalHmacAuthenticator(new byte[32]));
        using var engine = new MissionEngine(new OperationRegistry(FilesystemHandlers.Create(provider)), journal);

        OperationResponse refused = await engine.ExecuteAsync(
            Request("file.write", """{"path":"BAXY-bench/notas.txt","text":"vacío"}"""), CancellationToken.None);
        string told = refused.Result!.Value.GetProperty("currentSha256").GetString()!;
        string replace = $$"""{"path":"BAXY-bench/notas.txt","text":"vacío","expectedSha256":"{{told}}"}""";
        OperationResponse asked = await engine.ExecuteAsync(Request("file.write", replace), CancellationToken.None);
        string untouched = File.ReadAllText(Path.Combine(sandbox, "BAXY-bench", "notas.txt"));
        int recycledWithoutTheYes = bin.Recycled.Count;
        OperationResponse read = await engine.ExecuteAsync(
            Request("filesystem.read.text", $$"""{"resourceId":"{{original.ResourceId}}"}"""), CancellationToken.None);
        OperationResponse replaced = await engine.ExecuteAsync(Request("file.write", replace), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("version_conflict"));
            Assert.That(told, Is.EqualTo(original.Sha256));
            Assert.That(asked.ErrorCode, Is.EqualTo(ConfirmationChallengeContract.RequiredErrorCode));
            Assert.That(untouched, Is.EqualTo(before));
            Assert.That(recycledWithoutTheYes, Is.Zero);
            Assert.That(read.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(replaced.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "BAXY-bench", "notas.txt")), Is.EqualTo("vacío"));
        });
    }

    private static OperationRequest Request(string operation, string arguments)
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

    // Renew al máximo (w8): a subfolder named wrong was made silently and the file told as written; the folder the write
    // made is said, and a write into folders already there says none.
    [Test]
    public async Task AWriteSaysTheFolderItMade()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox, new KnownFileToolsTests.FolderRecycleBin(
            Path.Combine(temporary.Path, "bin")));
        Directory.CreateDirectory(Path.Combine(sandbox, "Proyectos"));

        async Task<OperationOutcome> Write(string relativePath)
        {
            using JsonDocument arguments = JsonDocument.Parse(
                JsonSerializer.Serialize(new { path = relativePath, text = "hola" }));
            return await new FilesystemHandler("file.write", provider).ExecuteAsync(
                new OperationInvocation("r", "m", "i", arguments.RootElement.Clone()), CancellationToken.None);
        }

        OperationOutcome made = await Write("Proyetos/2026/notas.txt");
        OperationOutcome there = await Write("Proyectos/notas.txt");

        Assert.Multiple(() =>
        {
            Assert.That(made.Succeeded, Is.True, made.ErrorCode);
            Assert.That(made.Result!.Value.GetProperty("folderCreated").GetString(), Is.EqualTo("Proyetos"));
            Assert.That(there.Succeeded, Is.True, there.ErrorCode);
            Assert.That(there.Result!.Value.TryGetProperty("folderCreated", out _), Is.False);
        });
    }

    // Renew al máximo (w8): a replace whose new version could not take the name once the previous one was in the bin
    // deleted the new text; it is kept beside the name and the failure says where both are.
    [Test]
    public void AReplaceThatCannotTakeTheNameAfterTheBinKeepsTheNewText()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var bin = new RetakenNameBin(Path.Combine(temporary.Path, "bin"));
        var provider = InOwnFolder(sandbox, bin);
        FilesystemMutationResult first = provider.WriteText("dato.txt", "uno", null);

        FilesystemProviderException? failure = Assert.Throws<FilesystemProviderException>(
            () => provider.WriteText("dato.txt", "uno y dos", first.Sha256));

        string kept = Path.Combine(sandbox, failure!.Result!.Value.GetProperty("newTextFile").GetString()!);
        Assert.Multiple(() =>
        {
            Assert.That(failure.Code, Is.EqualTo("write_not_completed_previous_recycled"));
            Assert.That(failure.EffectMayHaveOccurred, Is.True);
            Assert.That(File.ReadAllText(kept), Is.EqualTo("uno y dos"));
            Assert.That(File.ReadAllText(bin.Recycled.Single()), Is.EqualTo("uno"));
        });
    }

    // A bin that takes the file, after which something else takes its name (a folder here, a sync client in use).
    private sealed class RetakenNameBin(string folder) : IRecycleBin
    {
        internal List<string> Recycled { get; } = [];

        public bool Recycle(string path)
        {
            Directory.CreateDirectory(folder);
            string destination = Path.Combine(folder, Guid.NewGuid().ToString("N"));
            File.Move(path, destination);
            Recycled.Add(destination);
            Directory.CreateDirectory(path);
            return true;
        }
    }

    [Test]
    public void AReplaceTheBinCannotTakeChangesNothing()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"), accepts: false);
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox, bin);
        FilesystemMutationResult first = provider.WriteText("dato.txt", "uno", null);

        Assert.Multiple(() =>
        {
            Assert.That(
                () => provider.WriteText("dato.txt", "uno y dos", first.Sha256),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("previous_version_not_recycled"));
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "dato.txt")), Is.EqualTo("uno"));
            Assert.That(Directory.GetFiles(sandbox), Is.EqualTo(new[] { Path.Combine(sandbox, "dato.txt") }));
        });
    }

    // FT/proveedores goal (review of receipts): a file another program holds open with no sharing (Excel) threw past the
    // handler and ended the core; it is file.write's failure, file_in_use, and the file is untouched.
    [Test]
    public async Task AFileHeldOpenByAnotherProgramIsInUseNotACrash()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox, bin);
        string path = Path.Combine(sandbox, "ventas.csv");
        File.WriteAllText(path, "a;b");
        using JsonDocument arguments = JsonDocument.Parse("""{"path":"ventas.csv","text":"c;d","append":true}""");

        OperationOutcome outcome;
        using (new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
        {
            outcome = await new FilesystemHandler("file.write", provider).ExecuteAsync(
                new OperationInvocation("r", "m", "i", arguments.RootElement.Clone()), CancellationToken.None);
        }

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("file_in_use"));
            Assert.That(File.ReadAllText(path), Is.EqualTo("a;b"));
        });
    }

    // FT/proveedores goal (review of receipts): an ANSI file (no mark, not UTF-8) is not appended to in UTF-8; it is
    // refused before anything is written, as file.edit refuses it.
    [Test]
    public void AnAppendToAnAnsiFileIsRefusedBeforeWriting()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox, bin);
        string path = Path.Combine(sandbox, "notas.txt");
        byte[] ansi = [0x63, 0x61, 0x66, 0xE9];
        File.WriteAllBytes(path, ansi);

        Assert.Multiple(() =>
        {
            Assert.That(() => provider.WriteText("notas.txt", "pan", null, append: true),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("known_text_encoding_unsupported"));
            Assert.That(File.ReadAllBytes(path), Is.EqualTo(ansi));
        });
    }

    // file.write append (it absorbed filesystem.sandbox.append.named): what is there stays, the text goes at the end
    // in the file's own encoding, no hash is needed (a given one must match), and a missing file is created.
    [Test]
    public void AppendKeepsWhatIsThereInTheFilesEncodingAndCreatesAMissingFile()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox, bin);
        File.WriteAllText(Path.Combine(sandbox, "lista.txt"), "pan\n", new UnicodeEncoding(false, true));

        FilesystemMutationResult appended = provider.WriteText("lista.txt", "leche\n", null, append: true);
        FilesystemMutationResult created = provider.WriteText("logs/nuevo.txt", "uno\n", null, append: true);
        FilesystemMutationResult again = provider.WriteText("logs/nuevo.txt", "dos\n", created.Sha256, append: true);

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "lista.txt"), Encoding.Unicode), Is.EqualTo("pan\nleche\n"));
            Assert.That(File.ReadAllBytes(Path.Combine(sandbox, "lista.txt"))[..2], Is.EqualTo(new byte[] { 0xFF, 0xFE }));
            Assert.That(appended.PreviousVersionRecycled, Is.False);
            // FT/proveedores goal (review of receipts): the append to a missing file made it, and says so.
            Assert.That(appended.Created, Is.False);
            Assert.That(created.Created, Is.True);
            Assert.That(again.Created, Is.False);
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "logs", "nuevo.txt")), Is.EqualTo("uno\ndos\n"));
            Assert.That(again.ReachedState, Is.False);
            Assert.That(
                () => provider.WriteText("logs/nuevo.txt", "tres\n", created.Sha256, append: true),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("version_conflict"));
            Assert.That(provider.WriteText("logs/nuevo.txt", "", null, append: true).ReachedState, Is.True);
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // Renew al máximo (w5, E024): «añade a notas.txt, en la carpeta BAXY-bench» came as relativePath
    // «notas.txt» in home, the subfolder left out, and the append made a new home\notas.txt (int5 X s0/s1, int M s0).
    // An append presupposes the file: missing there and found below the same folder, nothing is written and the
    // places are told; with BAXY_AYUDAS=none, the facts without the sentence. Contracase: found nowhere, it is made.
    // Holdout v6 V6E044 (cien s1 and s2): told «a file of that name is in BAXY-bench/gastos.txt, and file_write with that
    // relativePath and the same folder appends to it», the model answered «gastos.txt está en mi carpeta de trabajo» and
    // wrote nothing. With aid «append_elsewhere_call» the file is said by its full path, as the person's, and the append
    // as a call with its arguments; with «append_elsewhere» alone, the sentence of before.
    [TestCase("all", "call")]
    [TestCase("append_elsewhere", "where")]
    [TestCase("none", null)]
    public async Task AnAppendToAMissingFileFoundInASubfolderWritesNothingAndSaysWhere(string aids, string? hint)
    {
        using IDisposable setting = ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "BAXY-bench"));
        Directory.CreateDirectory(Path.Combine(home, ".oculta"));
        File.SetAttributes(Path.Combine(home, ".oculta"), FileAttributes.Directory | FileAttributes.Hidden);
        File.WriteAllText(Path.Combine(home, "BAXY-bench", "notas.txt"), "uno\r\ndos\r\ntres\r\n");
        File.WriteAllText(Path.Combine(home, ".oculta", "lista.txt"), "x");
        var provider = new LocalFilesystemProvider(Path.Combine(temporary.Path, "sandbox"))
        {
            KnownFolderPath = folder => folder == "home" ? home : Path.Combine(temporary.Path, "absent", folder),
        };

        OperationOutcome outcome = await Handle(provider, "file.write",
            """{"path":"notas.txt","text":"revisar el router","append":true}""");
        OperationOutcome made = await Handle(provider, "file.write",
            """{"path":"lista.txt","text":"pan","append":true}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("append_target_missing"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(File.Exists(Path.Combine(home, "notas.txt")), Is.False);
            Assert.That(File.ReadAllText(Path.Combine(home, "BAXY-bench", "notas.txt")), Is.EqualTo("uno\r\ndos\r\ntres\r\n"));
            JsonElement result = outcome.Result!.Value;
            Assert.That(result.GetProperty("exists").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("fullPath").GetString(), Is.EqualTo(Path.Combine(home, "notas.txt")));
            Assert.That(result.GetProperty("sameNameIn").EnumerateArray().Select(item => item.GetString()),
                Is.EqualTo(new[] { "BAXY-bench/notas.txt" }));
            Assert.That(result.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint is not null));
            if (hint == "where")
            {
                Assert.That(next.GetString(), Is.EqualTo(
                    $"nothing was written: notas.txt is not in {home}; a file of that name is in BAXY-bench/notas.txt, "
                    + "and file_write with path \"home/BAXY-bench/notas.txt\" appends to it; without append, a new "
                    + "notas.txt is made here"));
            }
            if (hint == "call")
            {
                Assert.That(next.GetString(), Is.EqualTo(
                    $"nothing was written: notas.txt is not in {home}; the file of that name is "
                    + $"{Path.Combine(home, "BAXY-bench", "notas.txt")}, a file of the person's: to add the text at its "
                    + "end, call file_write again with path \"home/BAXY-bench/notas.txt\" and append true; without "
                    + "append, a new notas.txt is made here"));
            }
            // A name found nowhere (a hidden folder is not looked in) is made, as before.
            Assert.That(made.Succeeded, Is.True, made.ErrorCode);
            Assert.That(File.ReadAllText(Path.Combine(home, "lista.txt")), Is.EqualTo("pan"));
        });
    }

    // Renew al máximo (w5, E020): «¿cuál es el archivo más grande dentro de BAXY-bench, en mi carpeta de usuario?» ran
    // filesystem.list (int5 X s0: Qwen chose filesystem_search, System One corrected it to filesystem_list), whose
    // result was an empty list and a path, and the answer was «no hay nada en mi carpeta de trabajo». A listing or a
    // search of the working folder says it is BAXY's (folder baxy_work), and one that found nothing that the person's
    // folders were not looked at; with BAXY_AYUDAS=none, neither.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AnEmptyLookAtTheWorkingFolderSaysThePersonsFoldersWereNotLookedAt(string aids, bool hint)
    {
        using IDisposable setting = ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox);

        JsonElement empty = await Observed(provider, "filesystem.list", "{}");
        JsonElement missing = await Observed(provider, "filesystem.search", """{"query":"informe"}""");
        provider.WriteText("informe.txt", "uno", null);
        JsonElement listed = await Observed(provider, "filesystem.list", "{}");
        JsonElement found = await Observed(provider, "filesystem.search", """{"query":"informe"}""");

        Assert.Multiple(() =>
        {
            foreach (JsonElement look in new[] { empty, missing, listed, found })
            {
                Assert.That(look.TryGetProperty("folder", out JsonElement folder), Is.EqualTo(hint));
                if (hint) Assert.That(folder.GetString(), Is.EqualTo("baxy_work"));
            }
            Assert.That(empty.TryGetProperty("next", out JsonElement none), Is.EqualTo(hint));
            Assert.That(missing.TryGetProperty("next", out JsonElement nothing), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(none.GetString(), Is.EqualTo("BAXY's own working folder holds nothing here; the person's "
                    + "folders (their home and everything under it) were not looked at: file_find looks there"));
                Assert.That(nothing.GetString(), Is.EqualTo("nothing named informe in BAXY's own working folder; the "
                    + "person's folders (their home and everything under it) were not looked at: file_find looks there"));
            }
            Assert.That(listed.TryGetProperty("next", out _), Is.False);
            Assert.That(found.TryGetProperty("next", out _), Is.False);
        });
    }

    private static async Task<JsonElement> Observed(IFilesystemProvider provider, string operation, string arguments)
    {
        OperationOutcome outcome = await Handle(provider, operation, arguments);
        Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
        using JsonDocument message = JsonDocument.Parse(OperationVisibleFacts.FromOutcome(operation, outcome));
        return message.RootElement.GetProperty("observed").Clone();
    }

    // BAXY Renew (notebook): a hash expected of a file that is not there is said as that, not as another version;
    // the refusal says what it saw, and nothing is written.
    [TestCase("")]
    [TestCase("0000000000000000000000000000000000000000000000000000000000000000")]
    public async Task AWriteExpectingAHashOfAMissingFileSaysTheFileIsNotThere(string expected)
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox);

        OperationOutcome outcome = await Handle(
            provider, "file.write",
            $$"""{"path":"nuevo.txt","text":"hola","expectedSha256":"{{expected}}"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("expected_hash_for_missing_file"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("exists").GetBoolean(), Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("fullPath").GetString(),
                Is.EqualTo(Path.Combine(sandbox, "nuevo.txt")));
            Assert.That(outcome.Result!.Value.GetProperty("append").GetBoolean(), Is.False);
            Assert.That(File.Exists(Path.Combine(sandbox, "nuevo.txt")), Is.False);
        });
    }

    // A refused write leaves nothing behind, not even the folder a new file would have gone in (the receipt says no
    // effect happened).
    [Test]
    public async Task ARefusedWriteOfANewFileInANewFolderLeavesNoFolder()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox);

        OperationOutcome outcome = await Handle(
            provider, "file.write", """{"path":"viaje/plan.txt","text":"hola","expectedSha256":""}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("expected_hash_for_missing_file"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(Directory.Exists(Path.Combine(sandbox, "viaje")), Is.False);
        });
    }

    [Test]
    public async Task AVersionConflictSaysTheFileIsThereAndWhere()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox);
        provider.WriteText("dato.txt", "uno", null);

        OperationOutcome outcome = await Handle(
            provider, "file.write", """{"path":"dato.txt","text":"dos"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("version_conflict"));
            Assert.That(outcome.Result!.Value.GetProperty("exists").GetBoolean(), Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("fullPath").GetString(),
                Is.EqualTo(Path.Combine(sandbox, "dato.txt")));
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "dato.txt")), Is.EqualTo("uno"));
        });
    }

    // Holdout v6 V6E041 («agrégale al file jugadores.txt … la línea: Matías, arquero»): written without append, refused,
    // then read and replaced by that line alone. The refusal of a write with neither append nor the hash says what each
    // does; with BAXY_AYUDAS=none, the facts without the sentence; a replace whose hash is not the file's says nothing.
    // With overwrite_guard on too, a text that keeps little of the file says how much it has instead (OverwriteGuardTests).
    [TestCase("replace_or_append", true)]
    [TestCase("none", false)]
    public async Task AWriteWithoutAppendOrHashToAFileThereSaysWhatAppendAndTheHashDo(string aids, bool hint)
    {
        using IDisposable setting = ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox);
        provider.WriteText("jugadores.txt", "Benja, delantero\r\n", null);

        OperationOutcome refused = await Handle(
            provider, "file.write", """{"path":"jugadores.txt","text":"Matías, arquero"}""");
        OperationOutcome stale = await Handle(provider, "file.write",
            $$"""{"path":"jugadores.txt","text":"x","expectedSha256":"{{new string('0', 64)}}"}""");

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("version_conflict"));
            Assert.That(refused.Result!.Value.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo(
                    "nothing was written: jugadores.txt is already there; file_write with append true adds the text as a "
                    + "new line at its end and keeps what it has, and with expectedSha256 (currentSha256) it replaces all "
                    + "the file has with the text, its previous version to the Recycle Bin"));
            }
            Assert.That(stale.ErrorCode, Is.EqualTo("version_conflict"));
            Assert.That(stale.Result!.Value.TryGetProperty("next", out _), Is.False);
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "jugadores.txt")), Is.EqualTo("Benja, delantero\r\n"));
        });
    }

    // Al máximo, flujos: the refusal of a replace without the hash took a file.read and another file.write; it carries
    // the version it saw (its hash and size), so the second call goes straight, its previous version to the bin.
    [Test]
    public async Task AVersionConflictCarriesTheVersionItSawSoTheSecondWriteGoesStraight()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var provider = InOwnFolder(sandbox, bin);
        provider.WriteText("dato.txt", "uno", null);

        OperationOutcome refused = await Handle(
            provider, "file.write", """{"path":"dato.txt","text":"dos"}""");
        string seen = refused.Result!.Value.GetProperty("currentSha256").GetString()!;
        OperationOutcome written = await Handle(
            provider, "file.write", $$"""{"path":"dato.txt","text":"dos","expectedSha256":"{{seen}}"}""");

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("version_conflict"));
            Assert.That(refused.Result!.Value.GetProperty("size").GetInt64(), Is.EqualTo(3));
            Assert.That(written.Succeeded && written.Verified, Is.True, written.ErrorCode);
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "dato.txt")), Is.EqualTo("dos"));
            Assert.That(bin.Recycled, Has.Count.EqualTo(1));
        });
    }

    // The list says which folder it read and whether its limit left entries out.
    [Test]
    public async Task AListSaysItsFolderAndWhetherTheLimitLeftEntriesOut()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        var provider = InOwnFolder(sandbox);
        foreach (string name in new[] { "a.txt", "b.txt", "c.txt" }) provider.WriteText("notas/" + name, name, null);

        OperationOutcome cut = await Handle(
            provider, "filesystem.list", """{"relativeDirectory":"notas","limit":2}""");
        OperationOutcome whole = await Handle(provider, "filesystem.list", """{"relativeDirectory":"notas"}""");

        Assert.Multiple(() =>
        {
            Assert.That(cut.Succeeded, Is.True, cut.ErrorCode);
            Assert.That(cut.Result!.Value.GetProperty("fullPath").GetString(), Is.EqualTo(Path.Combine(sandbox, "notas")));
            Assert.That(cut.Result!.Value.GetProperty("count").GetInt32(), Is.EqualTo(2));
            Assert.That(cut.Result!.Value.GetProperty("totalCount").GetInt32(), Is.EqualTo(3));
            Assert.That(cut.Result!.Value.GetProperty("hasMore").GetBoolean(), Is.True);
            Assert.That(whole.Result!.Value.GetProperty("count").GetInt32(), Is.EqualTo(3));
            Assert.That(whole.Result!.Value.GetProperty("hasMore").GetBoolean(), Is.False);
        });
    }

    // Round A: a read-back that did not match once the file was written, or a provider failure after its move, came
    // back as a clean failure, as if nothing had changed. It says the change may be on disk; a write whose content was
    // already there changed nothing and says so.
    [TestCase("nuevo.txt", true)]
    [TestCase("dato.txt", false)]
    public async Task AWriteWhoseReadBackDoesNotMatchSaysWhetherTheChangeMayBeOnDisk(string name, bool effectMayHaveOccurred)
    {
        using TemporaryDirectory temporary = new();
        var provider = new MisreadingProvider(InOwnFolder(Path.Combine(temporary.Path, "sandbox")));
        provider.WriteText("dato.txt", "igual", null);

        OperationOutcome outcome = await Handle(
            provider, "file.write", $$"""{"path":"{{name}}","text":"igual"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.EqualTo(effectMayHaveOccurred));
        });
    }

    [Test]
    public async Task AProviderFailureAfterTheMoveReachesTheOutcomeAsAPossibleEffect()
    {
        using TemporaryDirectory temporary = new();
        var provider = new MisreadingProvider(InOwnFolder(temporary.Path)) { TransferFailsAfterEffect = true };
        FilesystemMutationResult source = provider.WriteText("origen.txt", "dato", null);

        OperationOutcome outcome = await Handle(
            provider, "filesystem.move",
            $$"""{"resourceId":"{{source.ResourceId}}","destinationRelativePath":"destino.txt","expectedSha256":"{{source.Sha256}}"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
        });
    }

    // Ronda B: a full table of handles refuses a write, a new folder, a copy and a move before anything is touched,
    // instead of after the change (it came out as a clean handle_capacity_reached with the change on disk).
    [Test]
    public void AFullTableOfHandlesRefusesBeforeTheChange()
    {
        using TemporaryDirectory temporary = new();
        var provider = InOwnFolder(temporary.Path);
        FilesystemMutationResult source = provider.WriteText("origen.txt", "dato", null);
        for (int issued = 1; issued < 512; issued++)
            _ = provider.WriteText("origen.txt", "dato", null);

        Assert.Multiple(() =>
        {
            foreach (TestDelegate change in new TestDelegate[]
            {
                () => provider.WriteText("nuevo/escrito.txt", "dato", null),
                () => provider.CreateDirectory("carpeta"),
                () => provider.Transfer(source.ResourceId, "copia/copia.txt", source.Sha256!, move: false),
                () => provider.Transfer(source.ResourceId, "movido/movido.txt", source.Sha256!, move: true),
            })
            {
                Assert.That(change, Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("handle_capacity_reached")
                    .And.Property(nameof(FilesystemProviderException.EffectMayHaveOccurred)).False);
            }
            Assert.That(Directory.GetFileSystemEntries(temporary.Path).Select(Path.GetFileName),
                Is.EquivalentTo(new[] { "origen.txt", ".backups" }));
            Assert.That(File.ReadAllText(Path.Combine(temporary.Path, "origen.txt")), Is.EqualTo("dato"));
        });
    }

    // Ronda B: the handle of what was just written no longer resolving (the file changed or went meanwhile) says the
    // change may be on disk; a write whose content was already there changed nothing.
    [TestCase("nuevo.txt", true)]
    [TestCase("dato.txt", false)]
    public async Task AHandleThatNoLongerResolvesAfterAWriteSaysWhetherTheChangeMayBeOnDisk(string name, bool effectMayHaveOccurred)
    {
        using TemporaryDirectory temporary = new();
        var provider = new MisreadingProvider(InOwnFolder(Path.Combine(temporary.Path, "sandbox")))
        {
            HashFailure = "resource_changed",
        };
        provider.WriteText("dato.txt", "igual", null);

        OperationOutcome outcome = await Handle(
            provider, "file.write", $$"""{"path":"{{name}}","text":"igual"}""");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("resource_changed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.EqualTo(effectMayHaveOccurred));
        });
    }

    // P2.4 (ajuste c3): file.write and filesystem.create.directory write only in the person's folders. A provider whose
    // every known folder is its own folder writes, by name, where its list, search and handles read.
    private static LocalFilesystemProvider InOwnFolder(string root, IRecycleBin? bin = null) => bin is null
        ? new LocalFilesystemProvider(root) { KnownFolderPath = _ => Path.GetFullPath(root) }
        : new LocalFilesystemProvider(root, bin) { KnownFolderPath = _ => Path.GetFullPath(root) };

    // The real provider, except that its hash read-back never matches (or fails, or its transfer fails after moving).
    private sealed class MisreadingProvider(LocalFilesystemProvider inner) : IFilesystemProvider
    {
        internal bool TransferFailsAfterEffect { get; init; }
        internal string? HashFailure { get; init; }

        public FilesystemListResult List(string relativeDirectory, int limit) => inner.List(relativeDirectory, limit);
        public FilesystemListResult Search(string query, int limit) => inner.Search(query, limit);
        public FilesystemTextResult ReadText(string resourceId, int maximumBytes) => inner.ReadText(resourceId, maximumBytes);
        public FilesystemEntry Hash(string resourceId) => HashFailure is { } code
            ? throw new FilesystemProviderException(code)
            : inner.Hash(resourceId) with { Sha256 = new string('0', 64) };
        public FilesystemMutationResult CreateDirectory(string path) => inner.CreateDirectory(path);
        public FilesystemMutationResult WriteText(string path, string text, string? expectedSha256, bool append = false) =>
            inner.WriteText(path, text, expectedSha256, append);
        public FilesystemMutationResult Transfer(
            string resourceId, string destinationRelativePath, string expectedSha256, bool move)
        {
            FilesystemMutationResult moved = inner.Transfer(resourceId, destinationRelativePath, expectedSha256, move);
            return TransferFailsAfterEffect
                ? throw new FilesystemProviderException("verification_failed") { EffectMayHaveOccurred = true }
                : moved;
        }
        public BackupReceipt CreateBackup(string resourceId, string expectedSha256) =>
            inner.CreateBackup(resourceId, expectedSha256);
        public BackupListResult ListBackups(int limit) => inner.ListBackups(limit);
        public BackupReceipt VerifyBackup(string backupId) => inner.VerifyBackup(backupId);
        public FilesystemMutationResult RestoreBackup(string backupId, string destinationRelativePath) =>
            inner.RestoreBackup(backupId, destinationRelativePath);
    }

    private static ValueTask<OperationOutcome> Handle(IFilesystemProvider provider, string operation, string arguments)
    {
        using JsonDocument document = JsonDocument.Parse(arguments);
        return new FilesystemHandler(operation, provider).ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", document.RootElement.Clone()),
            CancellationToken.None);
    }

    [Test]
    public void BackupCreateVerifyAndRestorePreserveExactHash()
    {
        using TemporaryDirectory temporary = new();
        var provider = InOwnFolder(temporary.Path);
        FilesystemMutationResult source = provider.WriteText("origen.txt", "respaldo", null);
        BackupReceipt created = provider.CreateBackup(source.ResourceId, source.Sha256!);
        BackupReceipt verified = provider.VerifyBackup(created.BackupId);
        FilesystemMutationResult restored = provider.RestoreBackup(created.BackupId, "restaurado.txt");

        Assert.Multiple(() =>
        {
            Assert.That(verified, Is.EqualTo(created));
            Assert.That(restored.Sha256, Is.EqualTo(created.Sha256));
            Assert.That(File.ReadAllText(Path.Combine(temporary.Path, "restaurado.txt")), Is.EqualTo("respaldo"));
        });
    }

    // Auditoría final V3: «verified» compares the backup's bytes with the SHA-256 recorded when it was made; a backup
    // changed since, or one without that record, is not verified and is never restored.
    [TestCase(true)]
    [TestCase(false)]
    public void ABackupChangedSinceItWasMadeOrWithoutItsRecordedHashIsNotVerifiedNorRestored(bool changed)
    {
        using TemporaryDirectory temporary = new();
        var provider = InOwnFolder(temporary.Path);
        FilesystemMutationResult source = provider.WriteText("origen.txt", "respaldo", null);
        BackupReceipt created = provider.CreateBackup(source.ResourceId, source.Sha256!);
        string backups = Path.Combine(temporary.Path, ".backups");
        if (changed)
        {
            File.WriteAllText(Path.Combine(backups, created.BackupId + ".bin"), "otra cosa");
        }
        else
        {
            File.Delete(Path.Combine(backups, created.BackupId + ".sha256"));
        }

        BackupReceipt verified = provider.VerifyBackup(created.BackupId);

        Assert.Multiple(() =>
        {
            Assert.That(created.Verified, Is.True);
            Assert.That(verified.Verified, Is.False);
            Assert.That(provider.ListBackups(1).Backups.Single().Verified, Is.False);
            Assert.That(() => provider.RestoreBackup(created.BackupId, "restaurado.txt"),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("backup_not_verified"));
            Assert.That(File.Exists(Path.Combine(temporary.Path, "restaurado.txt")), Is.False);
        });
    }

    [Test]
    public void BackupListReturnsVerifiedNewestFirstAndHonorsLimit()
    {
        using TemporaryDirectory temporary = new();
        var provider = InOwnFolder(temporary.Path);
        FilesystemMutationResult first = provider.WriteText("uno.txt", "uno", null);
        BackupReceipt older = provider.CreateBackup(first.ResourceId, first.Sha256!);
        FilesystemMutationResult second = provider.WriteText("dos.txt", "dos", null);
        BackupReceipt newer = provider.CreateBackup(second.ResourceId, second.Sha256!);
        File.SetLastWriteTimeUtc(
            Path.Combine(temporary.Path, ".backups", older.BackupId + ".bin"),
            DateTime.UtcNow.AddMinutes(-2));
        File.SetLastWriteTimeUtc(
            Path.Combine(temporary.Path, ".backups", newer.BackupId + ".bin"),
            DateTime.UtcNow);

        BackupListResult listed = provider.ListBackups(1);

        Assert.Multiple(() =>
        {
            Assert.That(listed.Count, Is.EqualTo(1));
            Assert.That(listed.Backups.Single().BackupId, Is.EqualTo(newer.BackupId));
            Assert.That(listed.Backups.Single().Verified, Is.True);
            Assert.That(listed.Backups.Single().BackupId, Is.Not.EqualTo(older.BackupId));
        });
    }

    [TestCase("../escape.txt")]
    [TestCase("C:\\escape.txt")]
    public void AbsoluteOrEscapingDestinationsFailClosed(string path)
    {
        using TemporaryDirectory temporary = new();
        var provider = InOwnFolder(temporary.Path);
        Assert.That(() => provider.WriteText(path, "x", null),
            Throws.TypeOf<FilesystemProviderException>());
    }

    // P2.4 (ajuste c3): file.write and filesystem.create.directory act only in the person's folders: a path outside all of
    // them is refused before any effect, with no other way said (there is none); a list outside the working folder is
    // refused as before.
    [Test]
    public void APathOutsideThePersonsFoldersIsRefusedBeforeAnyEffect()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        Directory.CreateDirectory(sandbox);
        var provider = new LocalFilesystemProvider(sandbox) { KnownFolderPath = Absent(temporary) };
        string outside = Path.Combine(temporary.Path, "fuera");

        FilesystemProviderException written = Assert.Throws<FilesystemProviderException>(
            () => provider.WriteText(Path.Combine(outside, "nota.txt"), "uno", null))!;
        FilesystemProviderException created = Assert.Throws<FilesystemProviderException>(
            () => provider.CreateDirectory(outside))!;
        FilesystemProviderException listed = Assert.Throws<FilesystemProviderException>(
            () => provider.List(outside, 10))!;

        Assert.Multiple(() =>
        {
            Assert.That(written.Code, Is.EqualTo("path_outside_folder"));
            Assert.That(written.Result, Is.Null);
            Assert.That(created.Code, Is.EqualTo("path_outside_folder"));
            Assert.That(Directory.Exists(outside), Is.False);
            Assert.That(listed.Code, Is.EqualTo("path_outside_sandbox"));
            Assert.That(listed.Result, Is.Null);
        });
    }

    // FT/proveedores goal (e2e E019): a full path that lies in a known folder of the person's is made there, the
    // subfolders included; one in no known folder is refused, and «..» never leaves the folder.
    [Test]
    public void AFullPathIsMadeInTheKnownFolderItLiesIn()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "BAXY-bench"));
        var provider = new LocalFilesystemProvider(Path.Combine(temporary.Path, "sandbox"), bin)
        {
            KnownFolderPath = folder => folder == "home" ? home : Path.Combine(temporary.Path, "absent", folder),
        };

        FilesystemMutationResult made = provider.CreateDirectory(Path.Combine(home, "BAXY-bench", "proyecto"));
        FilesystemMutationResult written = provider.WriteText(
            Path.Combine(home, "BAXY-bench", "compras.txt"), "pan, leche y huevos", null);

        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(Path.Combine(home, "BAXY-bench", "proyecto")), Is.True);
            Assert.That(made.FullPath, Is.EqualTo(Path.Combine(home, "BAXY-bench", "proyecto")));
            Assert.That(File.ReadAllText(Path.Combine(home, "BAXY-bench", "compras.txt")), Is.EqualTo("pan, leche y huevos"));
            Assert.That(written.FullPath, Is.EqualTo(Path.Combine(home, "BAXY-bench", "compras.txt")));
            Assert.That(made.Folder, Is.EqualTo("home"));
            Assert.That(() => provider.WriteText(Path.Combine(temporary.Path, "fuera.txt"), "dos", null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("path_outside_folder"));
            Assert.That(() => provider.WriteText(Path.Combine(home, "..", "fuera2.txt"), "tres", null),
                Throws.TypeOf<FilesystemProviderException>());
            Assert.That(() => provider.WriteText(Path.Combine(home, "a\0b.txt"), "cuatro", null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("invalid_path"));
            Assert.That(File.Exists(Path.Combine(temporary.Path, "fuera.txt")), Is.False);
            Assert.That(File.Exists(Path.Combine(temporary.Path, "fuera2.txt")), Is.False);
        });
    }

    // P2.4 (ajuste c3; E006/E024: «en la carpeta BAXY-bench» was written in BAXY's working folder, with the person's
    // BAXY-bench in their home): a path that names no known folder is in the person's home, a name alone directly in it,
    // and the receipt says the folder (home) and the full path; nothing is written in the working folder.
    [Test]
    public async Task APathThatNamesNoKnownFolderIsInTheHomeFolder()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "proyecto"));
        var provider = new LocalFilesystemProvider(sandbox, bin)
        {
            KnownFolderPath = folder => folder == "home" ? home : Path.Combine(temporary.Path, "absent", folder),
        };

        JsonElement same = await WriteMessage(provider, """{"path":"proyecto/notas.txt","text":"uno"}""");
        JsonElement single = await WriteMessage(provider, """{"path":"notas.txt","text":"dos"}""");

        Assert.Multiple(() =>
        {
            Assert.That(same.GetProperty("folder").GetString(), Is.EqualTo("home"));
            Assert.That(same.GetProperty("fullPath").GetString(), Is.EqualTo(Path.Combine(home, "proyecto", "notas.txt")));
            Assert.That(same.TryGetProperty("next", out _), Is.False);
            Assert.That(File.ReadAllText(Path.Combine(home, "proyecto", "notas.txt")), Is.EqualTo("uno"));
            Assert.That(single.GetProperty("folder").GetString(), Is.EqualTo("home"));
            Assert.That(File.ReadAllText(Path.Combine(home, "notas.txt")), Is.EqualTo("dos"));
            Assert.That(Directory.EnumerateFiles(sandbox, "*", SearchOption.AllDirectories), Is.Empty);
        });
    }

    // Al máximo, flujos (P263, 26 of 27 runs: «crea la carpeta Proyectos en Documentos» → relativePath
    // «Documentos/Proyectos» with no folder, made in BAXY's working folder): a first part that names one of the person's
    // known folders, in Spanish or English, is that folder, where Windows really keeps it (OneDrive's included), and the
    // receipt's full path says so; «Imágenes» is the person's Pictures (inside their home), never a «home\Imágenes» that
    // does not exist; «home» first is a folder of that name inside the home folder.
    [Test]
    public async Task AFirstPartNamingAKnownFolderIsThatFolderWhereWindowsKeepsIt()
    {
        using TemporaryDirectory temporary = new();
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        string home = Path.Combine(temporary.Path, "home");
        string documents = Path.Combine(temporary.Path, "OneDrive", "Documentos");
        string pictures = Path.Combine(home, "Pictures");
        string desktop = Path.Combine(temporary.Path, "OneDrive", "Escritorio");
        foreach (string folder in new[] { home, documents, pictures, desktop })
            Directory.CreateDirectory(folder);
        var provider = new LocalFilesystemProvider(sandbox, bin)
        {
            KnownFolderPath = folder => folder switch
            {
                "home" => home,
                "documents" => documents,
                "pictures" => pictures,
                "desktop" => desktop,
                _ => Path.Combine(temporary.Path, "absent", folder),
            },
        };

        FilesystemMutationResult made = provider.CreateDirectory("Documentos/Proyectos");
        FilesystemMutationResult english = provider.WriteText(@"documents\Proyectos\notas.txt", "uno", null);
        FilesystemMutationResult accented = provider.WriteText("ESCRITORIO/lista.txt", "dos", null);
        JsonElement told = await WriteMessage(provider, """{"path":"Imágenes/foto.txt","text":"tres"}""");
        FilesystemMutationResult named = provider.WriteText("home/Documentos/nota.txt", "cuatro", null);

        Assert.Multiple(() =>
        {
            Assert.That(made.FullPath, Is.EqualTo(Path.Combine(documents, "Proyectos")));
            Assert.That(Directory.Exists(Path.Combine(documents, "Proyectos")), Is.True);
            Assert.That(english.FullPath, Is.EqualTo(Path.Combine(documents, "Proyectos", "notas.txt")));
            Assert.That(english.Folder, Is.EqualTo("documents"));
            Assert.That(accented.FullPath, Is.EqualTo(Path.Combine(desktop, "lista.txt")));
            Assert.That(Directory.Exists(Path.Combine(sandbox, "Documentos")), Is.False);
            Assert.That(Directory.Exists(Path.Combine(sandbox, "documents")), Is.False);
            // Imágenes is the person's Pictures, in their home.
            Assert.That(told.GetProperty("folder").GetString(), Is.EqualTo("home"));
            Assert.That(told.GetProperty("fullPath").GetString(), Is.EqualTo(Path.Combine(pictures, "foto.txt")));
            // «home» first: a folder named Documentos inside the home folder.
            Assert.That(named.FullPath, Is.EqualTo(Path.Combine(home, "Documentos", "nota.txt")));
        });
    }

    // Renew al máximo (B-SYS-1): BAXY's own state (its data root, where confirmation-mode lives, and the rest of its
    // private area) is not one of the person's files. Written through the home folder or by its full path, the model
    // turned Bypass on with a LowReversible file.write; now that is refused before any effect, and the working folder,
    // which lives inside that area, still works.
    [Test]
    public void BaxysOwnStateIsNeverWrittenThroughAKnownFolderOrAFullPath()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string privateArea = Path.Combine(home, "AppData", "Local", "BAXY");
        string sandbox = Path.Combine(privateArea, "1", "filesystem-sandbox");
        Directory.CreateDirectory(sandbox);
        var provider = new LocalFilesystemProvider(sandbox)
        {
            KnownFolderPath = folder => folder == "home" ? home : Path.Combine(temporary.Path, "absent", folder),
            PrivateRoots = [privateArea],
        };
        string mode = Path.Combine(privateArea, "1", "confirmation-mode");

        Assert.Multiple(() =>
        {
            Assert.That(() => provider.WriteText("AppData/Local/BAXY/1/confirmation-mode", "bypass", null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("path_reserved"));
            Assert.That(() => provider.WriteText(mode, "bypass", null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("path_reserved"));
            Assert.That(() => provider.CreateDirectory("AppData/Local/BAXY/renew"),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("path_reserved"));
            Assert.That(File.Exists(mode), Is.False);
            provider.WriteText(Path.Combine(sandbox, "nota.txt"), "trabajo", null);
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "nota.txt")), Is.EqualTo("trabajo"));
            provider.WriteText("AppData/Local/otra-app/ajustes.txt", "suyo", null);
            Assert.That(File.Exists(Path.Combine(home, "AppData", "Local", "otra-app", "ajustes.txt")), Is.True);
        });
    }

    // Revisión de calidad (archivos): «descarga.exe:Zone.Identifier» is no file of the person's but the mark Windows keeps
    // on what came from the internet (SmartScreen reads it before running it); a stream of a file is never written,
    // replaced, appended to nor made through a file tool, with or without a folder.
    [Test]
    public void AStreamOfAFileIsNeverWritten()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(home);
        string program = Path.Combine(home, "descarga.exe");
        File.WriteAllText(program, "MZ");
        const string mark = "[ZoneTransfer]\r\nZoneId=3\r\n";
        File.WriteAllText(program + ":Zone.Identifier", mark);
        var bin = new KnownFileToolsTests.FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var provider = new LocalFilesystemProvider(Path.Combine(temporary.Path, "sandbox"), bin)
        {
            KnownFolderPath = folder => folder == "home" ? home : Path.Combine(temporary.Path, "absent", folder),
            PrivateRoots = [],
        };
        string markHash = Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(Encoding.UTF8.GetBytes(mark)));

        Assert.Multiple(() =>
        {
            Assert.That(() => provider.WriteText("descarga.exe:Zone.Identifier", "", markHash),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("invalid_path"));
            Assert.That(() => provider.WriteText("descarga.exe:Zone.Identifier", "ZoneId=0", null, append: true),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("invalid_path"));
            Assert.That(() => provider.WriteText("descarga.exe:otro", "x", null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("invalid_path"));
            Assert.That(() => provider.CreateDirectory("carpeta:flujo"),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("invalid_path"));
            Assert.That(File.ReadAllText(program + ":Zone.Identifier"), Is.EqualTo(mark));
            Assert.That(File.ReadAllText(program), Is.EqualTo("MZ"));
            Assert.That(bin.Recycled, Is.Empty);
            Assert.That(Directory.EnumerateFileSystemEntries(home).Select(Path.GetFileName), Is.EqualTo(new[] { "descarga.exe" }));
        });
    }

    // Revisión de calidad (archivos): the working folder lives inside BAXY's own area and is usable through home, but its
    // backups are not: written through home they were replaced (a backup's bytes and its recorded hash), and a restore
    // then gave the forged bytes as a verified backup.
    [Test]
    public void TheWorkingFoldersBackupsAreNeverWrittenThroughAKnownFolder()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string privateArea = Path.Combine(home, "AppData", "Local", "BAXY");
        string sandbox = Path.Combine(privateArea, "1", "filesystem-sandbox");
        Directory.CreateDirectory(sandbox);
        var provider = new LocalFilesystemProvider(sandbox)
        {
            KnownFolderPath = folder => folder == "home" ? home : Path.Combine(temporary.Path, "absent", folder),
            PrivateRoots = [privateArea],
        };
        string id = "backup_" + new string('a', 32);
        const string backups = "AppData/Local/BAXY/1/filesystem-sandbox/.backups/";

        Assert.Multiple(() =>
        {
            Assert.That(() => provider.WriteText(backups + id + ".bin", "falso", null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("path_reserved"));
            Assert.That(() => provider.WriteText(backups + id + ".sha256", new string('b', 64), null),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("path_reserved"));
            Assert.That(() => provider.CreateDirectory(backups + "dentro"),
                Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("path_reserved"));
            Assert.That(Directory.EnumerateFileSystemEntries(Path.Combine(sandbox, ".backups")), Is.Empty);
            provider.WriteText("AppData/Local/BAXY/1/filesystem-sandbox/nota.txt", "trabajo", null);
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "nota.txt")), Is.EqualTo("trabajo"));
        });
    }

    // Revisión de fase 3: what Windows runs at sign-in (the Startup folders) is not written through the home folder, by
    // its full path, by its 8.3 alias or as a folder inside it, nor appended to; a file.write there would run at the next
    // sign-in. Refused before any effect; the rest of AppData stays writable.
    [Test]
    public void NothingIsWrittenWhereWindowsRunsItAtSignIn()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        const string programs = "AppData/Roaming/Microsoft/Windows/Start Menu/Programs";
        string startup = Path.Combine(home, programs.Replace('/', Path.DirectorySeparatorChar), "Startup");
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        Directory.CreateDirectory(startup);
        Directory.CreateDirectory(sandbox);
        string existing = Path.Combine(startup, "suyo.cmd");
        File.WriteAllText(existing, "@echo suyo");
        var provider = new LocalFilesystemProvider(sandbox)
        {
            KnownFolderPath = folder => folder == "home" ? home : Path.Combine(temporary.Path, "absent", folder),
            PrivateRoots = [],
            AutostartRoots = [startup],
        };
        string startMenu = Path.GetDirectoryName(Path.GetDirectoryName(startup)!)!;
        string alias = Path.Combine(Path.GetDirectoryName(startMenu)!, Path.GetFileName(ShortPath(startMenu)), "Programs",
            "Startup");

        Assert.Multiple(() =>
        {
            foreach (TestDelegate write in (TestDelegate[])[
                () => provider.WriteText(programs + "/Startup/x.cmd", "calc", null),
                () => provider.WriteText(Path.Combine(startup, "x.cmd"), "calc", null),
                () => provider.WriteText(Path.Combine(alias, "x.cmd"), "calc", null),
                () => provider.WriteText(programs + "/Startup/suyo.cmd", "calc", null, append: true),
                () => provider.CreateDirectory(programs + "/Startup/sub"),
            ])
            {
                Assert.That(write, Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("path_autostart"));
            }
            Assert.That(Directory.EnumerateFileSystemEntries(startup), Is.EqualTo(new[] { existing }));
            Assert.That(File.ReadAllText(existing), Is.EqualTo("@echo suyo"));
            provider.WriteText(programs + "/otra-app/ajustes.txt", "suyo", null);
            Assert.That(File.Exists(Path.Combine(Path.GetDirectoryName(startup)!, "otra-app", "ajustes.txt")), Is.True);
        });
    }

    // Revisión de fase 3: PowerShell runs the profiles in Documents\WindowsPowerShell and Documents\PowerShell every time
    // it opens without -NoProfile; no file.write (nor append, nor a folder) goes there through the documents folder or by
    // full path. The folders come from where Windows says Documents is, not from a user name; the rest of Documents
    // (a sibling with a similar name too) stays writable.
    [Test]
    public void NothingIsWrittenWherePowerShellRunsItAtStart()
    {
        using TemporaryDirectory temporary = new();
        string documents = Path.Combine(temporary.Path, "OneDrive", "Documentos");
        string sandbox = Path.Combine(temporary.Path, "sandbox");
        string windowsPowerShell = Path.Combine(documents, "WindowsPowerShell");
        Directory.CreateDirectory(windowsPowerShell);
        Directory.CreateDirectory(sandbox);
        string existing = Path.Combine(windowsPowerShell, "Microsoft.PowerShell_profile.ps1");
        File.WriteAllText(existing, "# suyo");
        IReadOnlyList<string> roots = AutostartArea.RootsFrom(folder =>
            folder == Environment.SpecialFolder.MyDocuments ? documents : Path.Combine(temporary.Path, "absent", folder.ToString()));
        var provider = new LocalFilesystemProvider(sandbox)
        {
            KnownFolderPath = folder => folder == "documents" ? documents : Path.Combine(temporary.Path, "absent", folder),
            PrivateRoots = [],
            AutostartRoots = roots,
        };

        Assert.Multiple(() =>
        {
            foreach (TestDelegate write in (TestDelegate[])[
                () => provider.WriteText("Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1", "calc", null, append: true),
                () => provider.WriteText("Documents/WindowsPowerShell/profile.ps1", "calc", null),
                () => provider.WriteText("Documents/PowerShell/Microsoft.PowerShell_profile.ps1", "calc", null),
                () => provider.WriteText("Documents/PowerShell/Microsoft.VSCode_profile.ps1", "calc", null),
                () => provider.WriteText(Path.Combine(documents, "PowerShell", "profile.ps1"), "calc", null),
                () => provider.CreateDirectory("Documents/PowerShell"),
                () => provider.CreateDirectory("Documents/WindowsPowerShell/Modules/m"),
            ])
            {
                Assert.That(write, Throws.TypeOf<FilesystemProviderException>()
                    .With.Property(nameof(FilesystemProviderException.Code)).EqualTo("path_autostart"));
            }
            Assert.That(Directory.EnumerateFileSystemEntries(windowsPowerShell), Is.EqualTo(new[] { existing }));
            Assert.That(File.ReadAllText(existing), Is.EqualTo("# suyo"));
            Assert.That(Directory.Exists(Path.Combine(documents, "PowerShell")), Is.False);
            provider.WriteText("Documents/PowerShellNotas/perfil.txt", "suyo", null);
            Assert.That(File.Exists(Path.Combine(documents, "PowerShellNotas", "perfil.txt")), Is.True);
        });
    }

    // The profile folders guarded by default are the ones under the Documents Windows names (redirected or not yet made).
    [Test]
    public void ThePowerShellProfileFoldersFollowWindowsDocuments()
    {
        string documents = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments,
            Environment.SpecialFolderOption.DoNotVerify);
        Assume.That(Path.IsPathFullyQualified(documents), Is.True);

        Assert.That(AutostartArea.DefaultRoots(), Is.SupersetOf(new[]
        {
            Path.GetFullPath(Path.Combine(documents, "WindowsPowerShell")),
            Path.GetFullPath(Path.Combine(documents, "PowerShell")),
        }));
    }

    // The 8.3 alias Windows keeps for a folder («Start Menu» is STARTM~1 where the volume makes them).
    private static string ShortPath(string path)
    {
        char[] buffer = new char[1024];
        uint length = GetShortPathNameW(path, buffer, (uint)buffer.Length);
        return length is > 0 and < 1024 ? new string(buffer, 0, (int)length) : path;
    }

    [System.Runtime.InteropServices.DllImport("kernel32.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
    private static extern uint GetShortPathNameW(string longPath, [System.Runtime.InteropServices.Out] char[] shortPath, uint length);

    // What the model reads of a file.write: the observed part of its message.
    private static async Task<JsonElement> WriteMessage(IFilesystemProvider provider, string arguments)
    {
        OperationOutcome outcome = await Handle(provider, "file.write", arguments);
        Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
        using JsonDocument message = JsonDocument.Parse(OperationVisibleFacts.FromOutcome("file.write", outcome));
        return message.RootElement.GetProperty("observed").Clone();
    }

    // Known folders that do not exist: a path under the test's temporary folder is in none of them.
    private static Func<string, string> Absent(TemporaryDirectory temporary) =>
        folder => Path.Combine(temporary.Path, "absent", folder);

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-fs-tests",
                Guid.NewGuid().ToString("N", CultureInfo.InvariantCulture));
            Directory.CreateDirectory(Path);
        }
        public string Path { get; }
        public void Dispose() { if (Directory.Exists(Path)) Directory.Delete(Path, recursive: true); }
    }
}
