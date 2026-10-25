using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Filesystem;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew agent tools (2026-10-15): file.find lists a known folder or finds files under it by name or by a text
/// inside them, and file.edit replaces an exact text in one of them with its previous version sent to the Recycle Bin
/// first (a stand-in bin here: the real one is checked by <see cref="WindowsRecycleBinLiveCheck"/>).
/// </summary>
[TestFixture]
public sealed class KnownFileToolsTests
{
    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    /// <summary>A bin that takes every file (or none) into a folder of its own, as the Recycle Bin would.</summary>
    // FT/proveedores goal (review of receipts): a file another program holds open with no sharing is that file in use,
    // not its folder unavailable.
    [Test]
    public async Task AFileHeldOpenByAnotherProgramIsInUse()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(home);
        string path = Path.Combine(home, "ventas.csv");
        await File.WriteAllTextAsync(path, "a;b");
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["home"] = [home] },
            new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), true));

        ExternalCapabilityReceipt read;
        using (new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
        {
            read = await adapter.InvokeAsync(
                "file.read", Json("""{"folder":"home","fileName":"ventas.csv"}"""), CancellationToken.None);
        }

        Assert.That(read.ErrorCode, Is.EqualTo("file_in_use"));
    }

    // Renew al máximo (B-SYS-1): BAXY's private area is not one of the person's files, under home or anywhere: file.edit
    // could turn confirmation-mode from normal to bypass. Read, edit, trash or a search there are refused or skip it.
    [Test]
    public async Task BaxysOwnStateIsNeitherReadEditedNorFound()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string privateArea = Path.Combine(home, "AppData", "Local", "BAXY");
        string mode = Path.Combine(privateArea, "1", "confirmation-mode");
        Directory.CreateDirectory(Path.GetDirectoryName(mode)!);
        await File.WriteAllTextAsync(mode, "normal");
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["home"] = [home] }, bin,
            [privateArea]);

        ExternalCapabilityReceipt edited = await adapter.InvokeAsync("file.edit", Json(
            """{"folder":"home","fileName":"AppData\\Local\\BAXY\\1\\confirmation-mode","oldText":"normal","newText":"bypass"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt byFullPath = await adapter.InvokeAsync("file.read", Json(
            JsonSerializer.Serialize(new { folder = "home", fileName = mode })), CancellationToken.None);
        ExternalCapabilityReceipt inside = await adapter.InvokeAsync("file.find", Json(
            """{"folder":"home","subdirectory":"AppData/Local/BAXY"}"""), CancellationToken.None);
        ExternalCapabilityReceipt around = await adapter.InvokeAsync("file.find", Json(
            """{"folder":"home","subdirectory":"AppData/Local","query":"confirmation-mode"}"""), CancellationToken.None);
        ExternalCapabilityReceipt trashed = await adapter.InvokeAsync("filesystem.known.trash.named", Json(
            """{"folder":"home","subdirectory":"AppData/Local","fileName":"BAXY"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(edited.ErrorCode, Is.EqualTo("path_reserved"));
            Assert.That(byFullPath.ErrorCode, Is.EqualTo("path_reserved"));
            Assert.That(inside.ErrorCode, Is.EqualTo("path_reserved"));
            Assert.That(around.Result?.GetProperty("matchCount").GetInt32(), Is.Zero);
            Assert.That(trashed.EffectObserved, Is.False);
            Assert.That(File.ReadAllText(mode), Is.EqualTo("normal"));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // Renew al máximo (auditoría de flujos, archivos): a subdirectory reached through a link part way («AppData\Local\
    // Application Data» is Windows' own junction back to AppData\Local) is refused like one that is itself a link; only
    // the last part was checked, so BAXY's area was listed and its confirmation-mode edited to bypass through it.
    [Test]
    public async Task ASubdirectoryThroughALinkPartWayIsRefused()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string local = Path.Combine(home, "AppData", "Local");
        string privateArea = Path.Combine(local, "BAXY");
        string mode = Path.Combine(privateArea, "1", "confirmation-mode");
        Directory.CreateDirectory(Path.GetDirectoryName(mode)!);
        await File.WriteAllTextAsync(mode, "normal");
        _ = Baxy.Tests.NtfsTestJunction.Create(Path.Combine(local, "Application Data"), local);
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["home"] = [home] }, bin,
            [privateArea]);

        ExternalCapabilityReceipt listed = await adapter.InvokeAsync("file.find", Json(
            """{"folder":"home","subdirectory":"AppData/Local/Application Data/BAXY/1"}"""), CancellationToken.None);
        ExternalCapabilityReceipt edited = await adapter.InvokeAsync("file.edit", Json(
            """{"folder":"home","subdirectory":"AppData/Local/Application Data/BAXY/1","fileName":"confirmation-mode","oldText":"normal","newText":"bypass"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(listed.ErrorCode, Is.EqualTo("known_subdirectory_reparse_point"));
            Assert.That(edited.ErrorCode, Is.EqualTo("known_subdirectory_reparse_point"));
            Assert.That(File.ReadAllText(mode), Is.EqualTo("normal"));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // Renew al máximo (auditoría de flujos, archivos): «¿qué hay en C:\Users\ana\Documents?» with the folder's own full
    // path as subdirectory is the folder itself; it was refused as known_path_outside_folder, a path outside it.
    [Test]
    public async Task TheKnownFolderItselfNamedByItsFullPathIsTheFolder()
    {
        using TemporaryDirectory temporary = new();
        string documents = Path.Combine(temporary.Path, "Documentos");
        Directory.CreateDirectory(documents);
        await File.WriteAllTextAsync(Path.Combine(documents, "informe.txt"), "hola");
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["documents"] = [documents] },
            new FolderRecycleBin(Path.Combine(temporary.Path, "bin")), []);

        ExternalCapabilityReceipt listed = await adapter.InvokeAsync("file.find", Json(JsonSerializer.Serialize(
            new { folder = "documents", subdirectory = documents + Path.DirectorySeparatorChar })), CancellationToken.None);
        ExternalCapabilityReceipt read = await adapter.InvokeAsync("file.read", Json(JsonSerializer.Serialize(
            new { folder = "documents", subdirectory = documents, fileName = "informe.txt" })), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(listed.Verified, Is.True, listed.ErrorCode);
            Assert.That(listed.Result?.GetProperty("entries")[0].GetProperty("name").GetString(), Is.EqualTo("informe.txt"));
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.GetProperty("text").GetString(), Is.EqualTo("hola"));
        });
    }

    // Renew al máximo (auditoría de flujos, archivos): a folder that holds BAXY's own area («Local» under AppData) is not
    // sent to the Recycle Bin by name: B-SYS-1 refused the area itself, and the folder around it took it all the same.
    [Test]
    public async Task AFolderHoldingBaxysOwnStateIsNotTrashed()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string privateArea = Path.Combine(home, "AppData", "Local", "BAXY");
        string mode = Path.Combine(privateArea, "1", "confirmation-mode");
        Directory.CreateDirectory(Path.GetDirectoryName(mode)!);
        await File.WriteAllTextAsync(mode, "normal");
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["home"] = [home] }, bin,
            [privateArea]);

        ExternalCapabilityReceipt trashed = await adapter.InvokeAsync("filesystem.known.trash.named", Json(
            """{"folder":"home","subdirectory":"AppData","fileName":"Local"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(trashed.ErrorCode, Is.EqualTo("path_reserved"));
            Assert.That(trashed.EffectObserved, Is.False);
            Assert.That(File.ReadAllText(mode), Is.EqualTo("normal"));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // Revisión de fase 3: a file in the Startup folder (Windows runs it at sign-in) is read and found as any other, but
    // file.edit does not change it, named by its path, its full path or its subdirectory.
    [Test]
    public async Task AFileWindowsRunsAtSignInIsReadButNotEdited()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string startup = Path.Combine(home, "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs", "Startup");
        string script = Path.Combine(startup, "arranque.cmd");
        Directory.CreateDirectory(startup);
        await File.WriteAllTextAsync(script, "@echo hola");
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["home"] = [home] }, bin, [],
            autostartRoots: [startup]);
        Task<ExternalCapabilityReceipt> Run(string operation, object arguments) =>
            adapter.InvokeAsync(operation, Json(JsonSerializer.Serialize(arguments)), CancellationToken.None).AsTask();

        ExternalCapabilityReceipt read = await Run("file.read", new { folder = "home", fileName = script });
        ExternalCapabilityReceipt found = await Run("file.find",
            new { folder = "home", subdirectory = "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup" });
        ExternalCapabilityReceipt byPath = await Run("file.edit", new
        {
            folder = "home", fileName = "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/arranque.cmd",
            oldText = "hola", newText = "calc",
        });
        ExternalCapabilityReceipt byFullPath = await Run("file.edit",
            new { folder = "home", fileName = script, oldText = "hola", newText = "calc" });
        ExternalCapabilityReceipt bySubdirectory = await Run("file.edit", new
        {
            folder = "home", subdirectory = "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup",
            fileName = "arranque.cmd", oldText = "hola", newText = "calc",
        });

        Assert.Multiple(() =>
        {
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.GetProperty("text").GetString(), Is.EqualTo("@echo hola"));
            Assert.That(found.Verified, Is.True, found.ErrorCode);
            Assert.That(found.Result?.GetProperty("entries")[0].GetProperty("name").GetString(), Is.EqualTo("arranque.cmd"));
            foreach (ExternalCapabilityReceipt edited in (ExternalCapabilityReceipt[])[byPath, byFullPath, bySubdirectory])
            {
                Assert.That(edited.ErrorCode, Is.EqualTo("path_autostart"));
                Assert.That(edited.EffectMayHaveOccurred, Is.False);
            }
            Assert.That(File.ReadAllText(script), Is.EqualTo("@echo hola"));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // Revisión de fase 3: the PowerShell profile in Documents (run every time PowerShell opens) is read as any other file,
    // but file.edit does not change it.
    [Test]
    public async Task APowerShellProfileIsReadButNotEdited()
    {
        using TemporaryDirectory temporary = new();
        string documents = Path.Combine(temporary.Path, "Documents");
        string profile = Path.Combine(documents, "PowerShell", "Microsoft.PowerShell_profile.ps1");
        Directory.CreateDirectory(Path.GetDirectoryName(profile)!);
        await File.WriteAllTextAsync(profile, "Set-Location hola");
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["documents"] = [documents] }, bin, [],
            autostartRoots: AutostartArea.RootsFrom(folder => folder == Environment.SpecialFolder.MyDocuments ? documents : null));
        Task<ExternalCapabilityReceipt> Run(string operation, object arguments) =>
            adapter.InvokeAsync(operation, Json(JsonSerializer.Serialize(arguments)), CancellationToken.None).AsTask();

        ExternalCapabilityReceipt read = await Run("file.read", new { folder = "documents", fileName = profile });
        ExternalCapabilityReceipt edited = await Run("file.edit", new
        {
            folder = "documents", fileName = "PowerShell/Microsoft.PowerShell_profile.ps1", oldText = "hola", newText = "calc",
        });

        Assert.Multiple(() =>
        {
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.GetProperty("text").GetString(), Is.EqualTo("Set-Location hola"));
            Assert.That(edited.ErrorCode, Is.EqualTo("path_autostart"));
            Assert.That(edited.EffectMayHaveOccurred, Is.False);
            Assert.That(File.ReadAllText(profile), Is.EqualTo("Set-Location hola"));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // Revisión de calidad (archivos): with no file or folder named exactly so, a folder with the same words otherwise
    // separated («informe_final» for «informe final») went whole to the bin after a yes asked for «informe final». It is
    // a candidate now, by its own name and as a folder, before the yes; named exactly, it is trashed as before.
    [Test]
    public async Task AFolderThatOnlyHasTheWordsOfTheNameIsACandidateNotTrashed()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string folder = Path.Combine(home, "informe_final");
        Directory.CreateDirectory(folder);
        await File.WriteAllTextAsync(Path.Combine(folder, "capitulo.txt"), "uno");
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"));
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["home"] = [home] }, bin, []);

        ExternalCapabilityReceipt? asked = await adapter.PreflightAsync("filesystem.known.trash.named", Json(
            """{"folder":"home","fileName":"informe final"}"""), CancellationToken.None);
        ExternalCapabilityReceipt trashed = await adapter.InvokeAsync("filesystem.known.trash.named", Json(
            """{"folder":"home","fileName":"informe final"}"""), CancellationToken.None);
        bool before = Directory.Exists(folder);
        ExternalCapabilityReceipt? exact = await adapter.PreflightAsync("filesystem.known.trash.named", Json(
            """{"folder":"home","fileName":"informe_final"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked?.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(trashed.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(trashed.EffectMayHaveOccurred, Is.False);
            JsonElement candidate = trashed.Result!.Value.GetProperty("candidates")[0];
            Assert.That(candidate.GetProperty("name").GetString(), Is.EqualTo("informe_final"));
            Assert.That(candidate.GetProperty("isFolder").GetBoolean(), Is.True);
            Assert.That(before, Is.True);
            Assert.That(bin.Recycled, Is.Empty);
            Assert.That(exact, Is.Null, "named exactly, the yes is asked for it");
        });
    }

    // Revisión de calidad (archivos): the previous version went to the bin and the edited text could not take its place
    // (a sync client took the name meanwhile): the edited text, deleted with the temporary file, was lost and the file
    // was gone from its place. The edited text stays beside it, named, as file.write keeps it.
    [Test]
    public async Task AnEditWhoseNewTextCannotTakeThePlaceKeepsTheNewText()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(home);
        string path = Path.Combine(home, "lista.txt");
        await File.WriteAllTextAsync(path, "pan y leche");
        var bin = new RetakenNameBin(Path.Combine(temporary.Path, "bin"));
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]> { ["home"] = [home] }, bin, []);

        ExternalCapabilityReceipt edited = await adapter.InvokeAsync("file.edit", Json(
            """{"folder":"home","fileName":"lista.txt","oldText":"leche","newText":"huevos"}"""), CancellationToken.None);

        string[] kept = [.. Directory.EnumerateFiles(home, ".baxy-edit-*")];
        Assert.Multiple(() =>
        {
            Assert.That(edited.ErrorCode, Is.EqualTo("known_edit_not_completed_previous_recycled"));
            Assert.That(edited.EffectMayHaveOccurred, Is.True);
            Assert.That(File.ReadAllText(bin.Recycled.Single()), Is.EqualTo("pan y leche"));
            Assert.That(kept, Has.Length.EqualTo(1));
            Assert.That(kept.Select(File.ReadAllText), Is.EqualTo(new[] { "pan y huevos" }));
            Assert.That(edited.Result?.GetProperty("newTextFile").GetString(), Is.EqualTo(Path.GetFileName(kept.Single())));
        });
    }

    // A bin that takes the file, after which something else takes its name (a folder here).
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

    internal sealed class FolderRecycleBin(string folder, bool accepts = true) : IRecycleBin
    {
        internal List<string> Recycled { get; } = [];

        public bool Recycle(string path)
        {
            if (!accepts) return false;
            Directory.CreateDirectory(folder);
            string destination = Path.Combine(folder, Guid.NewGuid().ToString("N") + "_" + Path.GetFileName(path));
            if (Directory.Exists(path)) Directory.Move(path, destination); else File.Move(path, destination);
            Recycled.Add(destination);
            return true;
        }
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "baxy-file-tools-tests-" + Guid.NewGuid().ToString("N"));

        internal TemporaryDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    // BAXY Renew al máximo W5 (velocidad): a bare name found nowhere is walked once, keeping the files with its stem on
    // the way; the candidates are the ones the second walk gave, in its order, cut where it cut them. Found more than
    // CandidatesShown times, the walk stops where the name's own walk stopped.
    [TestCase(0)]
    [TestCase(1)]
    [TestCase(7)]
    public async Task ANameFoundNowhereOrTooOftenGivesTheCandidatesOfTheWalksItReplaces(int exact)
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, string documents, _) = Folders(temporary);
        for (int i = 0; i < 8; i++)
        {
            string folder = Path.Combine(i % 2 == 0 ? desktop : documents, $"sub{i}");
            Directory.CreateDirectory(folder);
            await File.WriteAllTextAsync(Path.Combine(folder, i % 3 == 0 ? "informe.docx" : "informe.pdf"), "x");
            if (i < exact)
                await File.WriteAllTextAsync(Path.Combine(folder, "informe"), "y");
        }

        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"all_known","fileName":"informe"}"""), CancellationToken.None);

        // The walks it replaces: the name's own, then (none found) the stem's, each the first six in walk order.
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true, IgnoreInaccessible = true, AttributesToSkip = FileAttributes.ReparsePoint,
            MaxRecursionDepth = 12,
        };
        (string Folder, string Path)[] walk = [.. new[] { ("desktop", desktop), ("documents", documents) }
            .SelectMany(root => Directory.EnumerateFiles(root.Item2, "*", options)
                .Select(file => (root.Item1, Path.GetRelativePath(root.Item2, file))))];
        (string, string)[] named = [.. walk.Where(item => Path.GetFileName(item.Path) == "informe").Take(6)];
        (string, string)[] stems = [.. walk.Where(item => Path.GetFileNameWithoutExtension(item.Path) == "informe").Take(6)];
        (string, string)[] expected = named.Length > 1 ? named : stems;
        if (exact == 1)
        {
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.GetProperty("text").GetString(), Is.EqualTo("y"));
            return;
        }

        JsonElement[] candidates = [.. read.Result!.Value.GetProperty("candidates").EnumerateArray()];
        Assert.Multiple(() =>
        {
            Assert.That(read.ErrorCode, Is.EqualTo(exact > 1 ? "known_file_ambiguous" : "known_file_not_found"));
            Assert.That(candidates.Select(item => (item.GetProperty("folder").GetString()!,
                item.GetProperty("relativePath").GetString()!)), Is.EqualTo(expected.Take(5)));
            Assert.That(read.Result!.Value.TryGetProperty("candidatesTruncated", out JsonElement cut) && cut.GetBoolean(),
                Is.EqualTo(expected.Length > 5));
        });
    }

    private static (WindowsKnownFileAdapter Adapter, string Desktop, string Documents, FolderRecycleBin Bin) Folders(
        TemporaryDirectory temporary, bool binAccepts = true)
    {
        string desktop = Path.Combine(temporary.Path, "desktop");
        string documents = Path.Combine(temporary.Path, "documents");
        Directory.CreateDirectory(desktop);
        Directory.CreateDirectory(documents);
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), binAccepts);
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]>
        {
            ["desktop"] = [desktop],
            ["documents"] = [documents],
        }, bin);
        return (adapter, desktop, documents, bin);
    }

    [Test]
    public async Task FindListsTheTopLevelFindsNamesAndPatternsAndGivesRelativePaths()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, string documents, _) = Folders(temporary);
        Directory.CreateDirectory(Path.Combine(desktop, "proyectos", "tesis"));
        await File.WriteAllTextAsync(Path.Combine(desktop, "presupuesto 2026.xlsx"), "x");
        await File.WriteAllTextAsync(Path.Combine(desktop, "proyectos", "tesis", "capitulo1.pdf"), "x");
        await File.WriteAllTextAsync(Path.Combine(documents, "Presupuesto viejo.txt"), "x");
        File.SetLastWriteTimeUtc(Path.Combine(documents, "Presupuesto viejo.txt"), DateTime.UtcNow.AddDays(-3));

        ExternalCapabilityReceipt listed = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"desktop"}"""), CancellationToken.None);
        ExternalCapabilityReceipt named = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"all_known","query":"presupuesto","order":"recent"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt pattern = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"all_known","query":"*.pdf"}"""), CancellationToken.None);
        ExternalCapabilityReceipt inside = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"desktop","subdirectory":"proyectos"}"""), CancellationToken.None);
        ExternalCapabilityReceipt missing = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"desktop","subdirectory":"no-existe"}"""), CancellationToken.None);

        Assert.That(listed.Verified, Is.True, listed.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(listed.EffectObserved, Is.False);
            Assert.That(listed.Result?.GetProperty("mode").GetString(), Is.EqualTo("list"));
            Assert.That(listed.Result?.GetProperty("entries").EnumerateArray()
                    .Select(entry => entry.GetProperty("kind").GetString() + ":" + entry.GetProperty("name").GetString()),
                Is.EqualTo(new[] { "folder:proyectos", "file:presupuesto 2026.xlsx" }));
            // Holdout v4 (falsedad, «no había .bak» with them in a subfolder): the listing is of the top level, its
            // folder was not opened, and it says so.
            Assert.That(listed.Result?.GetProperty("depth").GetString(), Is.EqualTo("top_level"));
            Assert.That(listed.Result?.GetProperty("subfoldersNotOpened").GetInt32(), Is.EqualTo(1));
            Assert.That(listed.Result?.GetProperty("readInPart").GetBoolean(), Is.True);
            Assert.That(named.Result?.GetProperty("files").EnumerateArray()
                    .Select(file => file.GetProperty("folder").GetString() + ":" + file.GetProperty("name").GetString()),
                Is.EqualTo(new[] { "desktop:presupuesto 2026.xlsx", "documents:Presupuesto viejo.txt" }));
            Assert.That(pattern.Result?.GetProperty("files")[0].GetProperty("relativePath").GetString(),
                Is.EqualTo(Path.Combine("proyectos", "tesis", "capitulo1.pdf")));
            Assert.That(pattern.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(inside.Result?.GetProperty("entries")[0].GetProperty("relativePath").GetString(),
                Is.EqualTo(Path.Combine("proyectos", "tesis")));
            Assert.That(missing.ErrorCode, Is.EqualTo("known_subdirectory_not_found"));
            Assert.That(named.Result?.GetRawText(), Does.Not.Contain(temporary.Path.Replace("\\", "\\\\")));
        });
    }

    // The profile root (home) is read when it is named; «all_known» stays the known folders, so a file of the profile
    // is not found twice and AppData is never walked by a search of everything.
    [Test]
    public async Task HomeIsReadWhenNamedAndAllKnownLeavesItOut()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string desktop = Path.Combine(home, "Desktop");
        Directory.CreateDirectory(Path.Combine(home, "BAXY-bench"));
        Directory.CreateDirectory(desktop);
        await File.WriteAllTextAsync(Path.Combine(home, "BAXY-bench", "lista.txt"), "pan\n");
        await File.WriteAllTextAsync(Path.Combine(desktop, "lista vieja.txt"), "leche\n");
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]>
        {
            ["desktop"] = [desktop],
            ["home"] = [home],
        }, new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), true));

        ExternalCapabilityReceipt inHome = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"home","query":"lista"}"""), CancellationToken.None);
        ExternalCapabilityReceipt everywhere = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"all_known","query":"lista"}"""), CancellationToken.None);
        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"BAXY-bench/lista.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(inHome.Verified, Is.True, inHome.ErrorCode);
            Assert.That(inHome.Result?.GetProperty("files").EnumerateArray()
                .Select(file => file.GetProperty("relativePath").GetString()),
                Does.Contain(Path.Combine("BAXY-bench", "lista.txt")));
            Assert.That(everywhere.Result?.GetProperty("files").EnumerateArray()
                .Select(file => file.GetProperty("relativePath").GetString()),
                Is.EqualTo(new[] { "lista vieja.txt" }));
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.ToString(), Does.Contain("pan"));
        });
    }

    // The model copies the path the person said (e2e p3 F013): a full path inside the named folder is the same place as
    // its relative path, and one outside it is refused before anything is read.
    [Test]
    public async Task AFullPathInsideTheFolderIsItsRelativePathAndOneOutsideIsRefused()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "BAXY-bench"));
        await File.WriteAllTextAsync(Path.Combine(home, "BAXY-bench", "lista.txt"), "pan\n");
        await File.WriteAllTextAsync(Path.Combine(temporary.Path, "fuera.txt"), "secreto\n");
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]>
        {
            ["home"] = [home],
        }, new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), true));
        string Args(string key, string value) => JsonSerializer.Serialize(new Dictionary<string, string>
        {
            ["folder"] = "home", [key] = value,
        });

        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "file.read", Json(Args("fileName", Path.Combine(home, "BAXY-bench", "lista.txt"))), CancellationToken.None);
        ExternalCapabilityReceipt found = await adapter.InvokeAsync(
            "file.find", Json(Args("subdirectory", Path.Combine(home, "BAXY-bench"))), CancellationToken.None);
        ExternalCapabilityReceipt outside = await adapter.InvokeAsync(
            "file.read", Json(Args("fileName", Path.Combine(temporary.Path, "fuera.txt"))), CancellationToken.None);
        ExternalCapabilityReceipt outsideFolder = await adapter.InvokeAsync(
            "file.find", Json(Args("subdirectory", temporary.Path)), CancellationToken.None);
        // A full path to a file directly in the folder that is not there is not another file of that name below it.
        ExternalCapabilityReceipt elsewhere = await adapter.InvokeAsync(
            "file.read", Json(Args("fileName", Path.Combine(home, "lista.txt"))), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.ToString(), Does.Contain("pan"));
            Assert.That(found.Verified, Is.True, found.ErrorCode);
            Assert.That(found.Result?.GetProperty("entries").EnumerateArray()
                .Select(entry => entry.GetProperty("relativePath").GetString()),
                Is.EqualTo(new[] { Path.Combine("BAXY-bench", "lista.txt") }));
            Assert.That(outside.ErrorCode, Is.EqualTo("known_path_outside_folder"));
            Assert.That(outside.Result?.ToString() ?? string.Empty, Does.Not.Contain("secreto"));
            Assert.That(outsideFolder.ErrorCode, Is.EqualTo("known_path_outside_folder"));
            Assert.That(elsewhere.Verified, Is.False);
            Assert.That(elsewhere.Result?.ToString() ?? string.Empty, Does.Not.Contain("pan"));
        });
    }

    // A named file or folder goes to the Recycle Bin, where the person restores it; when the bin cannot take it, it
    // stays where it was.
    [Test]
    public async Task TrashSendsTheNamedFileOrFolderToTheRecycleBin()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, _, FolderRecycleBin bin) = Folders(temporary);
        await File.WriteAllTextAsync(Path.Combine(desktop, "viejo.txt"), "x");
        Directory.CreateDirectory(Path.Combine(desktop, "CarterTest", "sub"));
        await File.WriteAllTextAsync(Path.Combine(desktop, "CarterTest", "sub", "a.txt"), "x");
        using TemporaryDirectory other = new();
        (WindowsKnownFileAdapter refusing, string refusingDesktop, _, _) = Folders(other, binAccepts: false);
        await File.WriteAllTextAsync(Path.Combine(refusingDesktop, "queda.txt"), "x");

        ExternalCapabilityReceipt file = await adapter.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"desktop","fileName":"viejo.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt folder = await adapter.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"desktop","fileName":"CarterTest"}"""), CancellationToken.None);
        ExternalCapabilityReceipt refused = await refusing.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"desktop","fileName":"queda.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(file.Verified, Is.True, file.ErrorCode);
            Assert.That(file.Result?.GetProperty("inRecycleBin").GetBoolean(), Is.True);
            Assert.That(File.Exists(Path.Combine(desktop, "viejo.txt")), Is.False);
            Assert.That(folder.Verified, Is.True, folder.ErrorCode);
            Assert.That(folder.Result?.GetProperty("entries").GetInt32(), Is.EqualTo(2));
            Assert.That(Directory.Exists(Path.Combine(desktop, "CarterTest")), Is.False);
            Assert.That(bin.Recycled, Has.Count.EqualTo(2));
            Assert.That(refused.ErrorCode, Is.EqualTo("known_file_not_recycled"));
            Assert.That(File.Exists(Path.Combine(refusingDesktop, "queda.txt")), Is.True);
        });
    }

    // Renew al máximo (E027): found nowhere in the folders walked, the result says nothing else was searched and which
    // configured folder searches more (the answer was «no lo encontré en ninguna carpeta de tu PC»); with
    // BAXY_AYUDAS=none, the folders walked alone.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AFileFoundNowhereSaysNothingElseWasSearched(string aids, bool hint)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        string desktop = Path.Combine(home, "desktop");
        Directory.CreateDirectory(Path.Combine(home, "BAXY-bench"));
        Directory.CreateDirectory(desktop);
        await File.WriteAllTextAsync(Path.Combine(home, "BAXY-bench", "viejo.txt"), "x");
        var adapter = new WindowsKnownFileAdapter(new Dictionary<string, string[]>
        {
            ["desktop"] = [desktop],
            ["home"] = [home],
        }, new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), true));

        ExternalCapabilityReceipt missing = await adapter.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"all_known","fileName":"viejo.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(missing.Result!.Value.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo("viejo.txt is not in desktop, subfolders included; nothing else "
                    + "on the PC was searched; folder \"home\" searches more"));
            }
        });
    }

    // Renew al máximo (w6, rutas): a call limited to a subfolder says that subfolder, never only its known folder: «not in
    // home, subfolders included» was read as the whole home folder searched. A listing says what it listed and that it
    // did not walk the subfolders; a path is looked up only at its place.
    [Test]
    public async Task ALookInASubfolderSaysThatSubfolder()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "taller", "sub"));
        await File.WriteAllTextAsync(Path.Combine(home, "taller", "a.txt"), "a");
        await File.WriteAllTextAsync(Path.Combine(home, "taller", "sub", "b.txt"), "b");
        await File.WriteAllTextAsync(Path.Combine(home, "lejos.txt"), "c");
        WindowsKnownFileAdapter adapter = Home(home);

        ExternalCapabilityReceipt found = await adapter.InvokeAsync("file.find",
            Json("""{"folder":"home","subdirectory":"taller","query":"*.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt listed = await adapter.InvokeAsync("file.find",
            Json("""{"folder":"home","subdirectory":"taller","order":"size"}"""), CancellationToken.None);
        ExternalCapabilityReceipt trash = await adapter.InvokeAsync("filesystem.known.trash.named",
            Json("""{"folder":"home","subdirectory":"taller","fileName":"lejos.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt read = await adapter.InvokeAsync("file.read",
            Json("""{"folder":"home","subdirectory":"taller","fileName":"lejos.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt byPath = await adapter.InvokeAsync("file.read",
            Json("""{"folder":"home","fileName":"taller/lejos.txt"}"""), CancellationToken.None);

        static string[] Strings(JsonElement array) => [.. array.EnumerateArray().Select(item => item.GetString()!)];
        Assert.Multiple(() =>
        {
            Assert.That(Strings(found.Result!.Value.GetProperty("searchScope").GetProperty("folders")),
                Is.EqualTo(new[] { "home/taller" }));
            Assert.That(Strings(listed.Result!.Value.GetProperty("listed")), Is.EqualTo(new[] { "home/taller" }));
            Assert.That(listed.Result!.Value.GetProperty("topLevelOnly").GetBoolean(), Is.True);
            Assert.That(Strings(trash.Result!.Value.GetProperty("searchedFolders")), Is.EqualTo(new[] { "home/taller" }));
            Assert.That(trash.Result!.Value.GetProperty("next").GetString(), Does.StartWith(
                "lejos.txt is not in home/taller, subfolders included; nothing else on the PC was searched"));
            Assert.That(read.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(Strings(read.Result!.Value.GetProperty("searchedFolders")), Is.EqualTo(new[] { "home/taller" }));
            Assert.That(read.Result!.Value.GetProperty("next").GetString(), Does.StartWith(
                "lejos.txt is not in home/taller, subfolders included"));
            Assert.That(byPath.Result!.Value.GetProperty("walked").GetBoolean(), Is.False);
            Assert.That(byPath.Result!.Value.TryGetProperty("next", out _), Is.False);
        });
    }

    // BAXY Renew (notebook): a name found nowhere says the folders walked; found twice, the places, as file.read
    // gives them; neither sends anything to the bin.
    [Test]
    public async Task TrashSaysWhereItLookedAndTheMatchesItCouldNotChooseBetween()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, string documents, FolderRecycleBin bin) = Folders(temporary);
        await File.WriteAllTextAsync(Path.Combine(desktop, "notas.txt"), "x");
        Directory.CreateDirectory(Path.Combine(documents, "viejas"));
        await File.WriteAllTextAsync(Path.Combine(documents, "viejas", "notas.txt"), "x");

        ExternalCapabilityReceipt missing = await adapter.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"all_known","fileName":"nada.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt ambiguous = await adapter.InvokeAsync(
            "filesystem.known.trash.named", Json("""{"folder":"all_known","fileName":"notas.txt"}"""), CancellationToken.None);

        JsonElement[] candidates = [.. ambiguous.Result!.Value.GetProperty("candidates").EnumerateArray()];
        Assert.Multiple(() =>
        {
            Assert.That(missing.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(missing.EffectMayHaveOccurred, Is.False);
            Assert.That(missing.Result!.Value.GetProperty("searchedFolders").EnumerateArray().Select(item => item.GetString()),
                Is.EqualTo(new[] { "desktop", "documents" }));
            Assert.That(ambiguous.ErrorCode, Is.EqualTo("known_file_ambiguous"));
            Assert.That(candidates.Select(item => (item.GetProperty("folder").GetString(),
                    item.GetProperty("relativePath").GetString(), item.GetProperty("name").GetString())),
                Is.EquivalentTo(new[]
                {
                    ("desktop", "notas.txt", "notas.txt"),
                    ("documents", Path.Combine("viejas", "notas.txt"), "notas.txt"),
                }));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // Al máximo, flujos («¿Borro viejo.txt?» → «sí» → «no existe»): the name is looked up before the person is asked;
    // none or several is that refusal now (with its places), one leaves the call to ask; the read trashes nothing.
    [Test]
    public async Task TheReadBeforeTheYesRefusesANameThatIsNotThereOnce()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, string documents, FolderRecycleBin bin) = Folders(temporary);
        await File.WriteAllTextAsync(Path.Combine(desktop, "notas.txt"), "x");
        await File.WriteAllTextAsync(Path.Combine(documents, "notas.txt"), "x");
        await File.WriteAllTextAsync(Path.Combine(desktop, "viejo.txt"), "x");

        ExternalCapabilityReceipt? missing = await adapter.PreflightAsync(
            "filesystem.known.trash.named", Json("""{"folder":"all_known","fileName":"nada.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt? ambiguous = await adapter.PreflightAsync(
            "filesystem.known.trash.named", Json("""{"folder":"all_known","fileName":"notas.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt? one = await adapter.PreflightAsync(
            "filesystem.known.trash.named", Json("""{"folder":"desktop","fileName":"viejo.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing?.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(ambiguous?.ErrorCode, Is.EqualTo("known_file_ambiguous"));
            Assert.That(ambiguous?.Result?.GetProperty("candidates").GetArrayLength(), Is.EqualTo(2));
            Assert.That(one, Is.Null);
            Assert.That(bin.Recycled, Is.Empty);
            Assert.That(File.Exists(Path.Combine(desktop, "viejo.txt")), Is.True);
        });
    }

    [TestCase("", 0)]
    [TestCase("uno", 1)]
    [TestCase("uno\n", 1)]
    [TestCase("uno\ndos", 2)]
    [TestCase("uno\r\ndos\r\n", 2)]
    [TestCase("uno\rdos", 2)]
    [TestCase("uno\n\n", 2)]
    [TestCase("\n", 1)]
    public void LinesAreCountedAsAnEditorShowsThem(string text, int lines) =>
        Assert.That(WindowsKnownFileAdapter.LineCount(text), Is.EqualTo(lines));

    // «¿cuál es el archivo más grande?» (e2e p6 E020): the largest first, listing or searching.
    [Test]
    public async Task OrderBySizePutsTheLargestFirst()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, _, _) = Folders(temporary);
        Directory.CreateDirectory(Path.Combine(desktop, "fotos"));
        await File.WriteAllTextAsync(Path.Combine(desktop, "chico.txt"), "x");
        await File.WriteAllTextAsync(Path.Combine(desktop, "mediano.txt"), new string('x', 50));
        await File.WriteAllTextAsync(Path.Combine(desktop, "fotos", "grande.txt"), new string('x', 500));

        ExternalCapabilityReceipt listed = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"desktop","order":"size"}"""), CancellationToken.None);
        ExternalCapabilityReceipt searched = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"desktop","query":"*.txt","order":"size"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(listed.Result?.GetProperty("entries").EnumerateArray()
                    .Select(entry => entry.GetProperty("name").GetString()),
                Is.EqualTo(new[] { "mediano.txt", "chico.txt", "fotos" }));
            Assert.That(searched.Result?.GetProperty("files").EnumerateArray()
                    .Select(file => file.GetProperty("name").GetString() + ":" + file.GetProperty("size").GetInt64()),
                Is.EqualTo(new[] { "grande.txt:500", "mediano.txt:50", "chico.txt:1" }));
            Assert.That(searched.Result?.GetProperty("searchScope").GetProperty("timeLimitReached").GetBoolean(),
                Is.False);
        });
    }

    [Test]
    public async Task FindByContentGivesTheFirstMatchingLineAndSkipsWhatIsNotText()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, _, string documents, _) = Folders(temporary);
        Directory.CreateDirectory(Path.Combine(documents, "actas"));
        await File.WriteAllTextAsync(Path.Combine(documents, "actas", "lunes.md"),
            "# Acta\n\nTemas varios\nAcordamos la Reunión con Juan el jueves.\nOtra reunión con Juan.\n");
        await File.WriteAllTextAsync(Path.Combine(documents, "compras.txt"), "pan\nleche\n");
        await File.WriteAllBytesAsync(Path.Combine(documents, "foto.jpg"), [0xFF, 0xD8, 0, 0, 0, 1, 2, 0, 0, 0]);
        await File.WriteAllTextAsync(Path.Combine(documents, "grande.log"), new string('x', 1_100_000));

        ExternalCapabilityReceipt found = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"documents","content":"reunión con juan"}"""), CancellationToken.None);
        ExternalCapabilityReceipt narrowed = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"documents","content":"pan","query":"*.md"}"""), CancellationToken.None);

        Assert.That(found.Verified, Is.True, found.ErrorCode);
        Assert.Multiple(() =>
        {
            JsonElement file = found.Result!.Value.GetProperty("files")[0];
            Assert.That(found.Result?.GetProperty("mode").GetString(), Is.EqualTo("content"));
            Assert.That(found.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(file.GetProperty("relativePath").GetString(), Is.EqualTo(Path.Combine("actas", "lunes.md")));
            Assert.That(file.GetProperty("line").GetInt32(), Is.EqualTo(4));
            Assert.That(file.GetProperty("lineText").GetString(), Is.EqualTo("Acordamos la Reunión con Juan el jueves."));
            JsonElement scope = found.Result!.Value.GetProperty("searchScope");
            Assert.That(scope.GetProperty("filesScanned").GetInt32(), Is.EqualTo(4));
            Assert.That(scope.GetProperty("skippedNotText").GetInt32(), Is.EqualTo(1));
            Assert.That(scope.GetProperty("skippedTooLarge").GetInt32(), Is.EqualTo(1));
            // Holdout v4 (falsedad): two files were not read as text, so the search read only part of the folder.
            Assert.That(found.Result?.GetProperty("readInPart").GetBoolean(), Is.True);
            Assert.That(narrowed.Result?.GetProperty("count").GetInt32(), Is.Zero);
            // Every *.md file was read as text: nothing read in part.
            Assert.That(narrowed.Result?.TryGetProperty("readInPart", out _), Is.False);
        });
    }

    // file.read of a PDF: the text it carries, through the mind runtime's pypdf, in pages like a text file.
    [Test]
    public async Task APdfIsReadThroughTheMindRuntimeInPages()
    {
        if (WindowsKnownFileAdapter.FindMindPython() is null)
            Assert.Ignore("The registered mind runtime (pypdf) is not installed on this machine.");
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, _, string documents, _) = Folders(temporary);
        await File.WriteAllBytesAsync(Path.Combine(documents, "informe.pdf"),
            TextPdf("Primera pagina del informe", "Segunda pagina con el cierre"));

        ExternalCapabilityReceipt first = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"documents","fileName":"informe.pdf","maximumCharacters":200}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt rest = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"documents","fileName":"informe.pdf","offset":28}"""),
            CancellationToken.None);

        Assert.That(first.Verified, Is.True, first.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(first.Result?.GetProperty("kind").GetString(), Is.EqualTo("pdf"));
            Assert.That(first.Result?.GetProperty("pages").GetInt32(), Is.EqualTo(2));
            Assert.That(first.Result?.GetProperty("characters").GetInt32(), Is.EqualTo(56));
            Assert.That(first.Result?.GetProperty("hasMore").GetBoolean(), Is.False);
            Assert.That(first.Result?.GetProperty("text").GetString(),
                Is.EqualTo("Primera pagina del informe\n\nSegunda pagina con el cierre"));
            Assert.That(rest.Result?.GetProperty("offset").GetInt32(), Is.EqualTo(28));
            Assert.That(rest.Result?.GetProperty("text").GetString(), Is.EqualTo("Segunda pagina con el cierre"));
        });
    }

    // A minimal PDF with one line of Helvetica text per page.
    private static byte[] TextPdf(params string[] pages)
    {
        var objects = new List<string>
        {
            "<< /Type /Catalog /Pages 2 0 R >>",
            "",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        };
        var kids = new List<int>();
        foreach (string text in pages)
        {
            string stream = $"BT /F1 12 Tf 72 712 Td ({text}) Tj ET";
            objects.Add($"<< /Length {stream.Length} >>\nstream\n{stream}\nendstream");
            int content = objects.Count;
            objects.Add($"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content} 0 R "
                + "/Resources << /Font << /F1 3 0 R >> >> >>");
            kids.Add(objects.Count);
        }
        objects[1] = $"<< /Type /Pages /Kids [{string.Join(" ", kids.Select(kid => $"{kid} 0 R"))}] /Count {kids.Count} >>";
        var output = new StringBuilder("%PDF-1.4\n");
        var offsets = new List<int>();
        for (int index = 0; index < objects.Count; index++)
        {
            offsets.Add(output.Length);
            output.Append(CultureInfo.InvariantCulture, $"{index + 1} 0 obj\n{objects[index]}\nendobj\n");
        }
        int xref = output.Length;
        output.Append(CultureInfo.InvariantCulture, $"xref\n0 {objects.Count + 1}\n0000000000 65535 f \n");
        foreach (int offset in offsets) output.Append(CultureInfo.InvariantCulture, $"{offset:D10} 00000 n \n");
        output.Append(CultureInfo.InvariantCulture, $"trailer\n<< /Size {objects.Count + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n");
        return Encoding.ASCII.GetBytes(output.ToString());
    }

    [Test]
    public async Task EditReplacesTheOneOccurrenceRecyclesThePreviousVersionAndKeepsTheBom()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, _, FolderRecycleBin bin) = Folders(temporary);
        string path = Path.Combine(desktop, "notas.txt");
        string original = "Reunión el lunes\r\nComprar pan el lunes temprano\r\n";
        await File.WriteAllTextAsync(path, original, new UTF8Encoding(true));
        byte[] before = await File.ReadAllBytesAsync(path);

        ExternalCapabilityReceipt ambiguous = await adapter.InvokeAsync(
            "file.edit", Json("""{"folder":"desktop","fileName":"notas.txt","oldText":"lunes","newText":"martes"}"""),
            CancellationToken.None);
        byte[] untouched = await File.ReadAllBytesAsync(path);
        ExternalCapabilityReceipt once = await adapter.InvokeAsync(
            "file.edit",
            Json("""{"folder":"desktop","fileName":"notas.txt","oldText":"Reunión el lunes","newText":"Reunión el martes"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt absent = await adapter.InvokeAsync(
            "file.edit", Json("""{"folder":"desktop","fileName":"notas.txt","oldText":"domingo","newText":"sábado"}"""),
            CancellationToken.None);
        byte[] after = await File.ReadAllBytesAsync(path);

        Assert.That(once.Verified, Is.True, once.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(ambiguous.ErrorCode, Is.EqualTo("known_edit_text_not_unique"));
            Assert.That(ambiguous.Result?.GetProperty("occurrences").GetInt32(), Is.EqualTo(2));
            Assert.That(untouched, Is.EqualTo(before));
            Assert.That(once.EffectObserved, Is.True);
            Assert.That(once.Result?.GetProperty("replacements").GetInt32(), Is.EqualTo(1));
            Assert.That(once.Result?.GetProperty("previousVersionRecycled").GetBoolean(), Is.True);
            Assert.That(once.Result?.GetProperty("previousSha256").GetString(),
                Is.EqualTo(Convert.ToHexStringLower(SHA256.HashData(before))));
            Assert.That(once.Result?.GetProperty("sha256").GetString(),
                Is.EqualTo(Convert.ToHexStringLower(SHA256.HashData(after))));
            Assert.That(once.Result?.GetProperty("newTextOccurrences").GetInt32(), Is.EqualTo(1));
            Assert.That(after[..3], Is.EqualTo(new byte[] { 0xEF, 0xBB, 0xBF }));
            Assert.That(Encoding.UTF8.GetString(after[3..]),
                Is.EqualTo("Reunión el martes\r\nComprar pan el lunes temprano\r\n"));
            Assert.That(bin.Recycled, Has.Count.EqualTo(1));
            Assert.That(File.ReadAllBytes(bin.Recycled[0]), Is.EqualTo(before));
            Assert.That(absent.ErrorCode, Is.EqualTo("known_edit_text_not_found"));
            Assert.That(Directory.GetFiles(desktop), Is.EqualTo(new[] { path }));
        });
    }

    // Renew al máximo (w8): a log its program holds open for writing is read (and searched by content), not refused as
    // file_in_use or skipped as unreadable.
    [Test]
    public async Task ALogStillOpenForWritingIsReadAndSearched()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, _, _) = Folders(temporary);
        string path = Path.Combine(desktop, "servidor.log");
        using var logger = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read);
        logger.Write(Encoding.UTF8.GetBytes("inicio\nerror: disco lleno\n"));
        logger.Flush();

        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "file.read", Json("""{"folder":"desktop","fileName":"servidor.log"}"""), CancellationToken.None);
        ExternalCapabilityReceipt found = await adapter.InvokeAsync(
            "file.find", Json("""{"folder":"desktop","content":"disco lleno"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.GetProperty("text").GetString(), Is.EqualTo("inicio\nerror: disco lleno\n"));
            Assert.That(found.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
        });
    }

    // Renew al máximo (w8, F015): file.edit got the file's name as oldText and the refusal only said «not found»; it now
    // says that oldText was the name and what to do, and any oldText the file does not hold as asked says what to do.
    [Test]
    public async Task AnEditGivenTheFileNameAsItsTextSaysSoAndWhatToDo()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, _, FolderRecycleBin bin) = Folders(temporary);
        string path = Path.Combine(desktop, "notas.txt");
        await File.WriteAllTextAsync(path, "Reunión el lunes\n");

        ExternalCapabilityReceipt name = await adapter.InvokeAsync(
            "file.edit", Json("""{"folder":"desktop","fileName":"notas.txt","oldText":"notas.txt","newText":"x"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt other = await adapter.InvokeAsync(
            "file.edit", Json("""{"folder":"desktop","fileName":"notas.txt","oldText":"reunion","newText":"x"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(name.ErrorCode, Is.EqualTo("known_edit_text_not_found"));
            Assert.That(name.Result?.GetProperty("next").GetString(),
                Does.StartWith("oldText was the file's name").And.Contain("file_read"));
            Assert.That(other.Result?.GetProperty("next").GetString(),
                Does.StartWith("the file does not hold oldText exactly").And.Contain("file_read"));
            Assert.That(File.ReadAllText(path), Is.EqualTo("Reunión el lunes\n"));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    [Test]
    public async Task EditReplacesEveryOccurrenceWhenAskedAndChangesNothingWhenTheBinRefuses()
    {
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, _, string documents, FolderRecycleBin bin) = Folders(temporary);
        string path = Path.Combine(documents, "informe.md");
        await File.WriteAllTextAsync(path, "Año 2024. Cierre 2024. Meta 2024.\n");
        using TemporaryDirectory refusing = new();
        (WindowsKnownFileAdapter noBin, _, string otherDocuments, _) = Folders(refusing, binAccepts: false);
        string kept = Path.Combine(otherDocuments, "informe.md");
        await File.WriteAllTextAsync(kept, "Año 2024.\n");
        byte[] ansi = [0x63, 0x61, 0x66, 0xE9, 0x0A];
        await File.WriteAllBytesAsync(Path.Combine(documents, "ansi.txt"), ansi);

        ExternalCapabilityReceipt all = await adapter.InvokeAsync(
            "file.edit",
            Json("""{"folder":"documents","fileName":"informe.md","oldText":"2024","newText":"2025","replaceAll":true}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt refused = await noBin.InvokeAsync(
            "file.edit", Json("""{"folder":"documents","fileName":"informe.md","oldText":"2024","newText":"2025"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt encoding = await adapter.InvokeAsync(
            "file.edit", Json("""{"folder":"documents","fileName":"ansi.txt","oldText":"caf","newText":"te"}"""),
            CancellationToken.None);

        Assert.That(all.Verified, Is.True, all.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(all.Result?.GetProperty("replacements").GetInt32(), Is.EqualTo(3));
            Assert.That(all.Result?.GetProperty("oldTextOccurrencesNow").GetInt32(), Is.Zero);
            Assert.That(File.ReadAllText(path), Is.EqualTo("Año 2025. Cierre 2025. Meta 2025.\n"));
            Assert.That(bin.Recycled, Has.Count.EqualTo(1));
            Assert.That(refused.Verified, Is.False);
            Assert.That(refused.ErrorCode, Is.EqualTo("previous_version_not_recycled"));
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            Assert.That(File.ReadAllText(kept), Is.EqualTo("Año 2024.\n"));
            Assert.That(Directory.GetFiles(otherDocuments), Is.EqualTo(new[] { kept }));
            Assert.That(encoding.ErrorCode, Is.EqualTo("known_text_encoding_unsupported"));
            Assert.That(File.ReadAllBytes(Path.Combine(documents, "ansi.txt")), Is.EqualTo(ansi));
        });
    }

    // Renew al máximo (velocidad): a clock that stands still for the first files a walk looks at and then jumps past
    // its time limit, so a test stops the walk where it wants.
    private static Func<DateTime> StopAfter(int files)
    {
        DateTime start = new(2026, 10, 23, 12, 0, 0, DateTimeKind.Utc);
        int calls = 0;
        // The first call sets the deadline; each file looked at asks once more.
        return () => calls++ <= files ? start : start.AddHours(1);
    }

    private static WindowsKnownFileAdapter Home(string home, Func<DateTime>? utcNow = null) =>
        new(new Dictionary<string, string[]> { ["home"] = [home] },
            new FolderRecycleBin(Path.Combine(Path.GetDirectoryName(home)!, "bin"), true), utcNow: utcNow);

    // e2e pc-lote (notas.txt in home): file.read walked the whole profile with no limit (12-83 s) to refuse two copies
    // seen at once. With file.find's limit the walk stops, and what it says is only what it walked.
    [Test]
    public async Task ABareNameFoundOnceBeforeTheLimitIsReadAsTheOneSeenNotTheOnlyOne()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "sub"));
        await File.WriteAllTextAsync(Path.Combine(home, "notas.txt"), "arriba");
        await File.WriteAllTextAsync(Path.Combine(home, "sub", "notas.txt"), "abajo");

        ExternalCapabilityReceipt stopped = await Home(home, StopAfter(1)).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"notas.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt whole = await Home(home).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"notas.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(stopped.ErrorCode, Is.Null);
            JsonElement result = stopped.Result!.Value;
            Assert.That(result.GetProperty("text").GetString(), Is.EqualTo("arriba"));
            Assert.That(result.GetProperty("relativePath").GetString(), Is.EqualTo("notas.txt"));
            Assert.That(result.GetProperty("onlyFileOfThatName").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("searchScope").GetProperty("timeLimitReached").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("searchScope").GetProperty("timeLimitSeconds").GetDouble(), Is.EqualTo(8));
            Assert.That(whole.ErrorCode, Is.EqualTo("known_file_ambiguous"));
            Assert.That(whole.Result!.Value.TryGetProperty("searchScope", out _), Is.False);
        });
    }

    // A whole walk says what it said before: a read of the one file of that name carries no walk facts.
    [Test]
    public async Task AWholeWalkReadsAsBefore()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "sub"));
        await File.WriteAllTextAsync(Path.Combine(home, "sub", "registro.log"), "evento 1");

        ExternalCapabilityReceipt read = await Home(home).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"registro.log"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.ErrorCode, Is.Null);
            Assert.That(read.Result!.Value.GetProperty("text").GetString(), Is.EqualTo("evento 1"));
            Assert.That(read.Result!.Value.TryGetProperty("relativePath", out _), Is.False);
            Assert.That(read.Result!.Value.TryGetProperty("onlyFileOfThatName", out _), Is.False);
            Assert.That(read.Result!.Value.TryGetProperty("searchScope", out _), Is.False);
        });
    }

    // Two seen before the limit are ambiguous (that much is proven), and the places are the ones seen so far.
    [Test]
    public async Task TwoSeenBeforeTheLimitAreAmbiguousAndSaySoFar()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        foreach (string folder in new[] { "a", "b", Path.Combine("c", "d") })
        {
            Directory.CreateDirectory(Path.Combine(home, folder));
            await File.WriteAllTextAsync(Path.Combine(home, folder, "notas.txt"), folder);
        }

        ExternalCapabilityReceipt stopped = await Home(home, StopAfter(2)).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"notas.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(stopped.ErrorCode, Is.EqualTo("known_file_ambiguous"));
            JsonElement result = stopped.Result!.Value;
            Assert.That(result.GetProperty("candidates").EnumerateArray()
                    .Select(item => item.GetProperty("relativePath").GetString()),
                Is.EqualTo(new[] { Path.Combine("a", "notas.txt"), Path.Combine("b", "notas.txt") }));
            Assert.That(result.GetProperty("searchScope").GetProperty("timeLimitReached").GetBoolean(), Is.True);
        });
    }

    // None in what was walked is never «not there»: the walk stopped, and the rest of the folder was not searched.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task NoneBeforeTheLimitSaysTheRestWasNotSearched(string aids, bool hint)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "lejos"));
        await File.WriteAllTextAsync(Path.Combine(home, "otro.txt"), "x");
        await File.WriteAllTextAsync(Path.Combine(home, "lejos", "notas.txt"), "x");

        ExternalCapabilityReceipt stopped = await Home(home, StopAfter(1)).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"notas.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt nowhere = await Home(home).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"nada.txt"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(stopped.ErrorCode, Is.EqualTo("known_file_not_found"));
            JsonElement result = stopped.Result!.Value;
            Assert.That(result.GetProperty("searchScope").GetProperty("timeLimitReached").GetBoolean(), Is.True);
            Assert.That(result.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo("the search of home stopped at its 8 s limit: notas.txt is not "
                    + "in the part walked, and the rest was not searched; a subdirectory or the relativePath file_find "
                    + "gives looks only there"));
            }
            Assert.That(nowhere.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(nowhere.Result!.Value.GetProperty("searchScope").TryGetProperty("timeLimitReached", out _),
                Is.False);
            // Renew al máximo (w6, rutas): a whole walk that found nothing says where it walked and that nothing else was.
            Assert.That(nowhere.Result!.Value.TryGetProperty("next", out JsonElement whole), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(whole.GetString(), Is.EqualTo(
                    "nada.txt is not in home, subfolders included; nothing else on the PC was searched"));
            }
        });
    }

    // A name that is nowhere gives its stems from the same walk (it walked twice: once for the name, once for them).
    [Test]
    public async Task TheStemsOfANameThatIsNowhereComeFromTheSameWalk()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "sub"));
        await File.WriteAllTextAsync(Path.Combine(home, "sub", "notas.md"), "x");
        int calls = 0;
        DateTime start = DateTime.UtcNow;

        ExternalCapabilityReceipt missing = await Home(home, () => { calls++; return start; }).InvokeAsync(
            "file.read", Json("""{"folder":"home","fileName":"notas"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(missing.Result!.Value.GetProperty("candidates").EnumerateArray()
                .Select(item => item.GetProperty("relativePath").GetString()), Is.EqualTo(new[]
                {
                    Path.Combine("sub", "notas.md"),
                }));
            // One deadline and one look at the one file: a single walk.
            Assert.That(calls, Is.EqualTo(2));
        });
    }

    // An edit of the one seen before the limit writes nothing: a deeper copy that was not walked may be the one meant.
    // It names the one seen, says the walk stopped and (aid search_scope) the call that edits it; its path edits it.
    // Holdout v6 V6E055 (s1 of the final version): «found» after «stopped» and the call only described, the model
    // answered «no encontré ideas.txt» in 2 of 4 runs instead of calling again; the call is said as said_folder says it.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AnEditOfTheOneSeenBeforeTheLimitChangesNothingAndNamesIt(string aids, bool hint)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "home");
        Directory.CreateDirectory(Path.Combine(home, "sub"));
        await File.WriteAllTextAsync(Path.Combine(home, "notas.txt"), "lunes");
        await File.WriteAllTextAsync(Path.Combine(home, "sub", "notas.txt"), "lunes");
        var bin = new FolderRecycleBin(Path.Combine(temporary.Path, "bin"), true);
        var adapter = new WindowsKnownFileAdapter(
            new Dictionary<string, string[]> { ["home"] = [home] }, bin, utcNow: StopAfter(1));

        ExternalCapabilityReceipt refused = await adapter.InvokeAsync("file.edit", Json(
            """{"folder":"home","fileName":"notas.txt","oldText":"lunes","newText":"martes"}"""), CancellationToken.None);
        ExternalCapabilityReceipt byPath = await Home(home, StopAfter(0)).InvokeAsync("file.edit", Json(
            """{"folder":"home","fileName":"sub/notas.txt","oldText":"lunes","newText":"martes"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("known_file_search_incomplete"));
            Assert.That(refused.EffectObserved, Is.False);
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            JsonElement result = refused.Result!.Value;
            Assert.That(result.GetProperty("relativePath").GetString(), Is.EqualTo("notas.txt"));
            Assert.That(result.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("searchScope").GetProperty("timeLimitReached").GetBoolean(), Is.True);
            Assert.That(result.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Is.EqualTo("nothing was changed: the search of home found notas.txt and "
                    + "stopped at its 8 s limit before the rest of the folder, so another file of that name may be there. "
                    + "If notas.txt is the file the person means, call file_edit again with fileName \"notas.txt\""));
            }
            Assert.That(File.ReadAllText(Path.Combine(home, "notas.txt")), Is.EqualTo("lunes"), "nothing was written");
            Assert.That(bin.Recycled, Is.Empty, "nothing went to the bin");
            // Named by its place, the file is looked up there with no walk: the edit goes ahead.
            Assert.That(byPath.ErrorCode, Is.Null);
            Assert.That(File.ReadAllText(Path.Combine(home, "sub", "notas.txt")), Is.EqualTo("martes"));
        });
    }

    // Holdout v5 (V5E052, «manda a la papelera factura marzo punto pdf de documentos facturas pyme»): a voice dictates no
    // hyphen, and «factura marzo.pdf» matched nothing while factura-marzo.pdf was there; nothing was offered, so the
    // file could never be reached. With aid near_names, a name matched by no file exactly gives, from the same walk, the
    // names with the same words under other separators, case or accents (and, for a read or an edit, another
    // extension), as candidates with that fact; nothing is trashed, read or edited by them, and the exact name named
    // again is the one the core asks the yes for. Off (BAXY_AYUDAS without it), or with nothing alike, it is as before.
    // (Holdout v6 V6F010: a name with only its separators otherwise is that file, ANameSaidWithOtherSeparatorsIsThatFile-
    // AndTwoSuchAreAmbiguous; here the names alike also differ in accents.)
    [TestCase("all", true)]
    [TestCase("search_scope", false)]
    public async Task ANameAlmostTheSameGivesTheExactNamesAndActsOnNone(string aids, bool near)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, string documents, FolderRecycleBin bin) = Folders(temporary);
        string pyme = Path.Combine(documents, "facturas pyme");
        Directory.CreateDirectory(pyme);
        Directory.CreateDirectory(Path.Combine(desktop, "fotos_añejas"));
        string factura = Path.Combine(pyme, "facturación-marzo.pdf");
        string informe = Path.Combine(pyme, "Informe_Reunión.txt");
        string cancion = Path.Combine(desktop, "canción.txt");
        await File.WriteAllTextAsync(factura, "x");
        await File.WriteAllTextAsync(informe, "lunes");
        await File.WriteAllTextAsync(cancion, "lunes");

        ExternalCapabilityReceipt trash = await adapter.InvokeAsync("filesystem.known.trash.named", Json(
            """{"folder":"documents","subdirectory":"facturas pyme","fileName":"facturacion marzo.pdf"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt? asked = await adapter.PreflightAsync("filesystem.known.trash.named", Json(
            """{"folder":"documents","subdirectory":"facturas pyme","fileName":"facturacion marzo.pdf"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt folder = await adapter.InvokeAsync("filesystem.known.trash.named", Json(
            """{"folder":"desktop","fileName":"Fotos Anejas"}"""), CancellationToken.None);
        ExternalCapabilityReceipt read = await adapter.InvokeAsync("file.read", Json(
            """{"folder":"all_known","fileName":"informe reunion.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt byPath = await adapter.InvokeAsync("file.read", Json(
            """{"folder":"documents","fileName":"facturas pyme/informe reunion"}"""), CancellationToken.None);
        ExternalCapabilityReceipt edit = await adapter.InvokeAsync("file.edit", Json(
            """{"folder":"desktop","fileName":"CANCION.TXT","oldText":"lunes","newText":"martes"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt nothingAlike = await adapter.InvokeAsync("filesystem.known.trash.named", Json(
            """{"folder":"documents","subdirectory":"facturas pyme","fileName":"factura abril.pdf"}"""),
            CancellationToken.None);
        // The exact name, named again, is one target: the read before the yes leaves the call to ask.
        ExternalCapabilityReceipt? exact = await adapter.PreflightAsync("filesystem.known.trash.named", Json(
            """{"folder":"documents","subdirectory":"facturas pyme","fileName":"facturación-marzo.pdf"}"""),
            CancellationToken.None);

        static string[] Names(ExternalCapabilityReceipt receipt) =>
            receipt.Result!.Value.TryGetProperty("candidates", out JsonElement candidates)
                ? [.. candidates.EnumerateArray().Select(item => item.GetProperty("relativePath").GetString()!)]
                : [];
        static string? Next(ExternalCapabilityReceipt? receipt) =>
            receipt?.Result is { } result && result.TryGetProperty("next", out JsonElement next) ? next.GetString() : null;
        const string elsewhere = "; nothing else on the PC was searched; folder \"desktop\" or \"documents\" searches more";
        Assert.Multiple(() =>
        {
            foreach (ExternalCapabilityReceipt refused in new[] { trash, folder, read, byPath, edit, nothingAlike })
            {
                Assert.That(refused.ErrorCode, Is.EqualTo("known_file_not_found"));
                Assert.That(refused.EffectMayHaveOccurred, Is.False);
            }
            Assert.That(asked?.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(Names(trash), Is.EqualTo(near ? new[] { Path.Combine("facturas pyme", "facturación-marzo.pdf") } : []));
            Assert.That(Names(asked!), Is.EqualTo(Names(trash)));
            Assert.That(Names(folder), Is.EqualTo(near ? new[] { "fotos_añejas" } : []));
            Assert.That(Names(read), Is.EqualTo(near ? new[] { Path.Combine("facturas pyme", "Informe_Reunión.txt") } : []));
            Assert.That(Names(byPath), Is.EqualTo(near ? new[] { Path.Combine("facturas pyme", "Informe_Reunión.txt") } : []));
            Assert.That(Names(edit), Is.EqualTo(near ? new[] { "canción.txt" } : []));
            Assert.That(Next(trash), Is.EqualTo(near
                ? "no file or folder is named exactly facturacion marzo.pdf; these have the same words with other "
                    + "separators, case or accents: \"facturación-marzo.pdf\"; to use one, call again with its exact name "
                    + "as fileName"
                : "facturacion marzo.pdf is not in documents/facturas pyme, subfolders included" + elsewhere));
            Assert.That(Next(read), Is.EqualTo(near
                ? "no file is named exactly informe reunion.txt; these have the same words with other separators, "
                    + "case, accents or extension: \"Informe_Reunión.txt\"; to use one, call again with its exact name "
                    + "as fileName"
                : "informe reunion.txt is not in desktop, documents, subfolders included; nothing else on the PC was "
                    + "searched"));
            Assert.That(Next(byPath), near ? Does.Contain("\"Informe_Reunión.txt\"") : Is.Null);
            // Nothing alike is the refusal of before, whatever the aid.
            Assert.That(Names(nothingAlike), Is.Empty);
            Assert.That(Next(nothingAlike), Is.EqualTo(
                "factura abril.pdf is not in documents/facturas pyme, subfolders included" + elsewhere));
            Assert.That(read.Result!.Value.TryGetProperty("text", out _), Is.False, "nothing was read");
            Assert.That(File.ReadAllText(cancion), Is.EqualTo("lunes"), "nothing was edited");
            Assert.That(File.Exists(factura), Is.True, "nothing was trashed");
            Assert.That(Directory.Exists(Path.Combine(desktop, "fotos_añejas")), Is.True);
            Assert.That(bin.Recycled, Is.Empty);
            Assert.That(exact, Is.Null);
        });
    }

    // Holdout v6 (V6F010, in every configuration): «lista invitados» said, lista_invitados.txt there, and the search
    // found nothing, so the answer was that it did not exist. A voice dictates no separator: a name is its words whatever
    // separates them (space, -, _, .), in the search, the read, the edit and the bin alike, with or without the aids. A
    // name spelled exactly is still the one meant before one that only has its words, and two that only have its words
    // are two candidates: nothing is read, edited or trashed by choosing one.
    [TestCase("all")]
    [TestCase("none")]
    public async Task ANameSaidWithOtherSeparatorsIsThatFileAndTwoSuchAreAmbiguous(string aids)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, string documents, FolderRecycleBin bin) = Folders(temporary);
        string invitados = Path.Combine(desktop, "lista_invitados.txt");
        string exact = Path.Combine(documents, "plan viaje.txt");
        string presupuesto = Path.Combine(documents, "Presupuesto-2026.xlsx");
        string[] notas = [Path.Combine(desktop, "notas_reunion.txt"), Path.Combine(documents, "notas-reunion.txt")];
        await File.WriteAllTextAsync(invitados, "Ana");
        await File.WriteAllTextAsync(exact, "exacto");
        await File.WriteAllTextAsync(Path.Combine(desktop, "plan_viaje.txt"), "parecido");
        await File.WriteAllTextAsync(presupuesto, "x");
        foreach (string nota in notas)
            await File.WriteAllTextAsync(nota, "lunes");
        Task<ExternalCapabilityReceipt> Run(string operation, string arguments) =>
            adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None).AsTask();

        ExternalCapabilityReceipt found = await Run("file.find", """{"folder":"all_known","query":"lista invitados"}""");
        ExternalCapabilityReceipt read = await Run("file.read", """{"folder":"all_known","fileName":"lista invitados.txt"}""");
        ExternalCapabilityReceipt edited = await Run("file.edit",
            """{"folder":"desktop","fileName":"Lista-Invitados.txt","oldText":"Ana","newText":"Ana y Pedro"}""");
        ExternalCapabilityReceipt exactRead = await Run("file.read", """{"folder":"all_known","fileName":"plan viaje.txt"}""");
        ExternalCapabilityReceipt? asked = await adapter.PreflightAsync("filesystem.known.trash.named", Json(
            """{"folder":"documents","fileName":"presupuesto 2026.xlsx"}"""), CancellationToken.None);
        ExternalCapabilityReceipt trashed = await Run("filesystem.known.trash.named",
            """{"folder":"documents","fileName":"presupuesto 2026.xlsx"}""");
        ExternalCapabilityReceipt twoRead = await Run("file.read", """{"folder":"all_known","fileName":"notas reunion.txt"}""");
        ExternalCapabilityReceipt twoEdit = await Run("file.edit",
            """{"folder":"all_known","fileName":"notas reunion.txt","oldText":"lunes","newText":"martes"}""");
        ExternalCapabilityReceipt twoTrash = await Run("filesystem.known.trash.named",
            """{"folder":"all_known","fileName":"notas reunion.txt"}""");

        static string[] Candidates(ExternalCapabilityReceipt receipt) =>
            [.. receipt.Result!.Value.GetProperty("candidates").EnumerateArray()
                .Select(item => item.GetProperty("name").GetString()!).Order(StringComparer.Ordinal)];
        Assert.Multiple(() =>
        {
            Assert.That(found.Result!.Value.GetProperty("matchCount").GetInt32(), Is.EqualTo(1));
            Assert.That(found.Result!.Value.GetProperty("files")[0].GetProperty("name").GetString(),
                Is.EqualTo("lista_invitados.txt"));
            Assert.That(read.ErrorCode, Is.Null);
            Assert.That(read.Result!.Value.GetProperty("text").GetString(), Is.EqualTo("Ana"));
            Assert.That(edited.ErrorCode, Is.Null);
            Assert.That(edited.Result!.Value.GetProperty("reviewLabel").GetString(), Is.EqualTo("lista_invitados.txt"));
            Assert.That(File.ReadAllText(invitados), Is.EqualTo("Ana y Pedro"));
            Assert.That(exactRead.Result!.Value.GetProperty("text").GetString(), Is.EqualTo("exacto"));
            Assert.That(asked, Is.Null, "one file has those words: the yes is asked for it");
            Assert.That(trashed.ErrorCode, Is.Null);
            Assert.That(trashed.Result!.Value.GetProperty("reviewLabel").GetString(), Is.EqualTo("Presupuesto-2026.xlsx"));
            Assert.That(File.Exists(presupuesto), Is.False);
            foreach (ExternalCapabilityReceipt two in new[] { twoRead, twoEdit, twoTrash })
            {
                Assert.That(two.ErrorCode, Is.EqualTo("known_file_ambiguous"));
                Assert.That(two.EffectMayHaveOccurred, Is.False);
                Assert.That(Candidates(two), Is.EqualTo(new[] { "notas-reunion.txt", "notas_reunion.txt" }));
            }
            Assert.That(twoRead.Result!.Value.TryGetProperty("text", out _), Is.False, "nothing was read");
            Assert.That(notas.Select(File.ReadAllText), Is.All.EqualTo("lunes"), "nothing was edited");
            string[] recycled = [.. bin.Recycled.Select(path => Path.GetFileName(path)[33..])];
            Assert.That(recycled, Does.Contain("Presupuesto-2026.xlsx"));
            Assert.That(recycled, Has.None.StartsWith("notas"), "nothing was trashed");
            Assert.That(notas.All(File.Exists), Is.True);
        });
    }

    // Holdout v5 (V5E047): a subdirectory that does not exist walked no folder, and the result said «X is not in no
    // folder». With aid missing_subdirectory it says the subfolder named is not in that known folder, as a relative path.
    [TestCase("all", true)]
    [TestCase("search_scope", false)]
    public async Task ASubdirectoryThatDoesNotExistSaysSo(string aids, bool missing)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, _, string documents, FolderRecycleBin bin) = Folders(temporary);
        Directory.CreateDirectory(Path.Combine(documents, "facturas pyme"));
        await File.WriteAllTextAsync(Path.Combine(documents, "facturas pyme", "factura.pdf"), "x");

        ExternalCapabilityReceipt trash = await adapter.InvokeAsync("filesystem.known.trash.named", Json(
            """{"folder":"documents","subdirectory":"facturas pymes","fileName":"factura.pdf"}"""), CancellationToken.None);
        ExternalCapabilityReceipt read = await adapter.InvokeAsync("file.read", Json(
            """{"folder":"documents","subdirectory":"facturas pymes/2026","fileName":"factura.pdf"}"""),
            CancellationToken.None);

        const string before = "factura.pdf is not in no folder, subfolders included; nothing else on the PC was "
            + "searched; folder \"desktop\" or \"documents\" searches more";
        Assert.Multiple(() =>
        {
            Assert.That(trash.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(read.ErrorCode, Is.EqualTo("known_file_not_found"));
            Assert.That(trash.Result!.Value.GetProperty("next").GetString(), Is.EqualTo(missing
                ? "documents has no subfolder \"facturas pymes\" (documents/facturas pymes does not exist), so "
                    + "factura.pdf was not looked for; file_find on documents with no subdirectory lists its folders"
                : before));
            Assert.That(read.Result!.Value.GetProperty("next").GetString(), Is.EqualTo(missing
                ? "documents has no subfolder \"facturas pymes/2026\" (documents/facturas pymes/2026 does not exist), "
                    + "so factura.pdf was not looked for; file_find on documents with no subdirectory lists its folders"
                : before));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }

    // Práctica e2e V6E035 («¿qué archivo de mi carpeta X tiene anotado el dato Y?»): file.find with query Y, a search of
    // names, found nothing three times and the answer was «ningún archivo en X menciona Y», with Y written inside one of
    // them. With aid find_content_next a name search with no match says that only names were matched, how many files
    // under it had their text unread, and the call that searches inside them; a pattern, a match, a search by content,
    // an empty folder or a walk stopped by its time limit say nothing more.
    [TestCase("all", true)]
    [TestCase("search_scope", false)]
    public async Task ANameSearchWithNoMatchSaysTheTextOfItsFilesWasNotSearched(string aids, bool aid)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, _, string documents, _) = Folders(temporary);
        string viaje = Path.Combine(documents, "Viaje Sur");
        Directory.CreateDirectory(Path.Combine(viaje, "fotos"));
        await File.WriteAllTextAsync(Path.Combine(viaje, "datos.txt"), "Patente: AB-12\nHotel: Central\n");
        await File.WriteAllTextAsync(Path.Combine(viaje, "fotos", "lista.txt"), "playa, cerro\n");
        await File.WriteAllTextAsync(Path.Combine(viaje, "fotos", "ruta.txt"), "norte\n");
        await File.WriteAllTextAsync(Path.Combine(documents, "patente.txt"), "x");
        Task<ExternalCapabilityReceipt> Run(string arguments) =>
            adapter.InvokeAsync("file.find", Json(arguments), CancellationToken.None).AsTask();

        ExternalCapabilityReceipt byName = await Run(
            """{"folder":"documents","subdirectory":"Viaje Sur","query":"patente"}""");
        ExternalCapabilityReceipt whole = await Run("""{"folder":"documents","query":"hotel"}""");
        ExternalCapabilityReceipt pattern = await Run("""{"folder":"documents","subdirectory":"Viaje Sur","query":"*.pdf"}""");
        ExternalCapabilityReceipt matched = await Run("""{"folder":"documents","query":"patente"}""");
        ExternalCapabilityReceipt byContent = await Run(
            """{"folder":"documents","subdirectory":"Viaje Sur","content":"pasaporte"}""");
        ExternalCapabilityReceipt empty = await Run("""{"folder":"desktop","query":"patente"}""");
        ExternalCapabilityReceipt inside = await Run(
            """{"folder":"documents","subdirectory":"Viaje Sur","content":"patente"}""");

        static string? Next(ExternalCapabilityReceipt receipt) =>
            receipt.Result!.Value.TryGetProperty("next", out JsonElement next) ? next.GetString() : null;
        Assert.Multiple(() =>
        {
            Assert.That(byName.Verified, Is.True, byName.ErrorCode);
            Assert.That(byName.Result!.Value.GetProperty("matchCount").GetInt32(), Is.Zero);
            Assert.That(Next(byName), Is.EqualTo(aid
                ? "no file name in documents/Viaje Sur contains \"patente\": this search matched names only, so the "
                    + "text inside its 3 files was not searched; to search inside them, call file_find with folder "
                    + "\"documents\", subdirectory \"Viaje Sur\" and content \"patente\""
                : null));
            Assert.That(Next(whole), Is.EqualTo(aid
                ? "no file name in documents contains \"hotel\": this search matched names only, so the text inside "
                    + "its 4 files was not searched; to search inside them, call file_find with folder \"documents\" "
                    + "and content \"hotel\""
                : null));
            Assert.That(Next(pattern), Is.Null);
            Assert.That(Next(matched), Is.Null);
            Assert.That(Next(byContent), Is.Null);
            Assert.That(Next(empty), Is.Null);
            // The call it names finds the file.
            Assert.That(inside.Result!.Value.GetProperty("files")[0].GetProperty("name").GetString(),
                Is.EqualTo("datos.txt"));
        });
    }

    // Holdout v5 (V5E061): the oldText of a file.edit was the whole content of another file (found by the «Sin título»
    // of a Notepad window), and the model then replaced this one whole. With aid edit_text_absent the refusal adds the
    // fact that this file holds no such text and may not be the file the person means; it forbids nothing.
    [TestCase("all", true)]
    [TestCase("search_scope", false)]
    public async Task AnEditWhoseTextIsNotInTheFileSaysItMayNotBeTheFileMeant(string aids, bool fact)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        (WindowsKnownFileAdapter adapter, string desktop, _, FolderRecycleBin bin) = Folders(temporary);
        string path = Path.Combine(desktop, "Sin título.txt");
        await File.WriteAllTextAsync(path, "lista de compras\n");

        ExternalCapabilityReceipt edit = await adapter.InvokeAsync("file.edit", Json(
            """{"folder":"desktop","fileName":"Sin título.txt","oldText":"Hola mundo","newText":"Hola BAXY"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(edit.ErrorCode, Is.EqualTo("known_edit_text_not_found"));
            Assert.That(edit.Result!.Value.GetProperty("next").GetString(), Is.EqualTo(
                "the file does not hold oldText exactly as given (spaces, line breaks and accents count); "
                + (fact ? "Sin título.txt holds no such text, so it may not be the file the person means; " : "")
                + "nothing was changed; oldText must be the exact text inside the file, copied from file_read; "
                + "file_write with the whole new content replaces all of it"));
            Assert.That(File.ReadAllText(path), Is.EqualTo("lista de compras\n"));
            Assert.That(bin.Recycled, Is.Empty);
        });
    }
}
