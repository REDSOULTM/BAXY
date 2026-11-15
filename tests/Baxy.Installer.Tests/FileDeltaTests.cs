using System.IO.Compression;
using System.Net;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// AUT1 (orden del dueño, 13-11-2026): an update downloads only the files that differ, verifies each by its SHA-256,
/// leaves BAXY as it was when anything fails, and goes on from what an earlier try left.
/// </summary>
[TestFixture]
internal sealed class FileDeltaTests
{
    private const string BaseUrl = "https://example.test/release/";
    private static readonly byte[] Model = RandomNumberGenerator.GetBytes(6000);
    private string directory = string.Empty;

    [SetUp]
    public void SetUp()
    {
        directory = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName());
        Directory.CreateDirectory(directory);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(directory, recursive: true);

    [Test]
    public async Task An_update_downloads_only_the_files_that_differ()
    {
        InstallPaths paths = Installed();
        Release release = Release.Of(NewFiles());
        RangeServer server = new(release.Assets);
        using HttpClient http = new(server);
        Installation installation = release.Installation(paths, http);

        await installation.RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the new app"));
        Assert.That(await File.ReadAllBytesAsync(In(paths.Root, "models/model.gguf")), Is.EqualTo(Model));
        Assert.That(await File.ReadAllTextAsync(In(paths.Root, "mind/a.py")), Is.EqualTo("a = 2  # changed" + Padding));
        Assert.That(await File.ReadAllTextAsync(In(paths.Root, "mind/b.py")), Is.EqualTo("b = 1"));
        Assert.That(await File.ReadAllTextAsync(In(paths.Root, "mind/c.py")), Is.EqualTo("c = 1  # new"));
        Assert.That(File.Exists(In(paths.Root, "mind/gone.py")), Is.False, "a file the release no longer has goes");
        long differing = release.Packed("app/Baxy.exe", "mind/a.py", "mind/c.py");
        Assert.That(installation.DownloadedBytes, Is.EqualTo(differing));
        Assert.That((installation.KeptFiles, installation.TakenFiles), Is.EqualTo((2, 3)));
        ReleaseFile model = release.File("models/model.gguf");
        Assert.That(server.Ranges.Any(range => release.Covers(range, model)), Is.False, "the model was not downloaded");
        Assert.That(server.Served, Is.LessThan(release.Zip.Length / 2));
        Assert.That(new[] { paths.Downloads, paths.Staging, paths.Previous }.Any(Directory.Exists), Is.False);
    }

    [Test]
    public async Task Neighbours_in_the_zip_come_in_one_request_and_what_lies_between_is_counted()
    {
        InstallPaths paths = Installed();
        Release release = Release.Of(NewFiles());
        RangeServer server = new(release.Assets);
        using HttpClient http = new(server);
        Installation installation = release.Installation(paths, http, gap: 256);

        await installation.RunAsync((_, _, _) => { }, CancellationToken.None);

        // mind/a.py and mind/c.py have only mind/b.py between them; the app is beyond the model, further than the gap.
        Assert.That(server.Ranges, Has.Count.EqualTo(2));
        Assert.That(await File.ReadAllTextAsync(In(paths.Root, "mind/c.py")), Is.EqualTo("c = 1  # new"));
        Assert.That(installation.DownloadedBytes, Is.EqualTo(server.Served));
        Assert.That(installation.DownloadedBytes, Is.GreaterThan(release.Packed("app/Baxy.exe", "mind/a.py", "mind/c.py")));
    }

    [Test]
    public async Task The_folder_before_is_kept_until_the_new_one_started_and_comes_back_as_it_was()
    {
        InstallPaths paths = Installed();
        Release release = Release.Of(NewFiles());
        using HttpClient http = new(new RangeServer(release.Assets));
        Installation installation = release.Installation(paths, http);

        await installation.RunAsync((_, _, _) => { }, CancellationToken.None, keepPrevious: true);

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the new app"));
        Assert.That(await File.ReadAllTextAsync(Path.Combine(paths.Previous, "app", "Baxy.exe")), Is.EqualTo("the old app"));

        installation.RollBack();

        Assert.That(Tree(paths.Root), Is.EqualTo(OldFiles().ToDictionary(file => file.Name, file => Convert.ToHexString(file.Content))));
        Assert.That(installation.HasReplaced, Is.False);
        Assert.That(new[] { paths.Staging, paths.Previous }.Any(Directory.Exists), Is.False);
    }

    // Blind review A-1: Windows holding the folder before must never leave the installation folder with no BAXY in it.
    [Test]
    public async Task A_way_back_that_windows_refuses_leaves_a_baxy_in_the_folder()
    {
        InstallPaths paths = Installed();
        Release release = Release.Of(NewFiles());
        using HttpClient http = new(new RangeServer(release.Assets));
        Installation installation = release.Installation(paths, http, moveAttempts: 1);
        await installation.RunAsync((_, _, _) => { }, CancellationToken.None, keepPrevious: true);

        // The folder before is a process's working folder: Windows does not move it (W1, own measurement).
        string here = Environment.CurrentDirectory;
        Environment.CurrentDirectory = Path.Combine(paths.Previous, "mind");
        try
        {
            Assert.That(installation.RollBack, Throws.InstanceOf<IOException>().Or.InstanceOf<UnauthorizedAccessException>());
        }
        finally
        {
            Environment.CurrentDirectory = here;
        }

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the new app"), "the new one is back in the folder");
        Assert.That(await File.ReadAllTextAsync(Path.Combine(paths.Previous, "app", "Baxy.exe")), Is.EqualTo("the old app"));

        installation.RollBack();

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the old app"), "once Windows lets go, the way back works");
    }

    // Blind review B-1: a file left in the downloads by an earlier try was installed for being there, unread.
    [Test]
    public void A_downloaded_file_whose_bytes_are_not_the_release_s_is_not_installed_for_being_there()
    {
        InstallPaths paths = Installed();
        Release release = Release.Of(NewFiles());
        ReleaseFile app = release.File("app/Baxy.exe");
        string store = Path.Combine(paths.Downloads, RangeFetcher.StoreName);
        Directory.CreateDirectory(store);
        File.WriteAllBytes(RangeFetcher.Kept(store, app), new byte[app.Bytes]);
        InstallPaths.MarkAsBaxys(paths.Downloads);
        using HttpClient http = new(new RangeServer(release.Assets));

        Assert.That(
            async () => await release.Installation(paths, http).RunAsync((_, _, _) => { }, CancellationToken.None),
            Throws.InstanceOf<InvalidDataException>());

        Assert.That(File.ReadAllText(paths.App), Is.EqualTo("the old app"));
        Assert.That(File.Exists(RangeFetcher.Kept(store, app)), Is.False, "it is deleted: the next try downloads it");
    }

    // Blind review B-2: where a file goes is checked again when it is placed, whoever built the manifest in memory.
    [TestCase("../outside.txt")]
    [TestCase("mind/../../outside.txt")]
    public void No_file_is_ever_placed_outside_the_installation(string path)
    {
        ReleaseFile outside = new(path, 1, new string('0', 64), "baxy.zip", 40, 1, ReleaseFile.Stored);

        Assert.That(() => FileDelta.InRoot(Path.Combine(directory, "BAXY-App"), outside), Throws.InstanceOf<InvalidDataException>());
    }

    // Blind review C-2: bytes the archive does not have.
    [Test]
    public async Task A_file_manifest_that_points_beyond_the_archive_is_not_used()
    {
        InstallPaths paths = Installed();
        Release release = Release.Of(NewFiles());
        ReleaseFile app = release.File("app/Baxy.exe");
        FileManifest beyond = release.Files with
        {
            Files = [.. release.Files.Files.Select(file => file == app ? app with { Offset = release.Zip.Length + 10 } : file)],
        };
        RangeServer server = new(release.Assets);
        using HttpClient http = new(server);
        Installation installation = new(
            release.Manifest, paths, new PartFetcher(http, retryDelay: TimeSpan.Zero), files: beyond,
            ranges: new RangeFetcher(http, retryDelay: TimeSpan.Zero));

        await installation.RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(server.Ranges.All(range => range.Whole), Is.True, "the parts are taken whole");
        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the new app"));
    }

    [Test]
    public async Task The_old_folder_goes_once_the_new_one_started()
    {
        InstallPaths paths = Installed();
        Release release = Release.Of(NewFiles());
        using HttpClient http = new(new RangeServer(release.Assets));
        Installation installation = release.Installation(paths, http);
        await installation.RunAsync((_, _, _) => { }, CancellationToken.None, keepPrevious: true);

        installation.DropPrevious();

        Assert.That(Directory.Exists(paths.Previous), Is.False);
        // The files the two folders named together are still whole in the one that stays.
        Assert.That(await File.ReadAllBytesAsync(In(paths.Root, "models/model.gguf")), Is.EqualTo(Model));
        Assert.That(await File.ReadAllTextAsync(In(paths.Root, "mind/b.py")), Is.EqualTo("b = 1"));
    }

    [Test]
    public void A_file_that_arrives_with_another_hash_is_never_installed()
    {
        InstallPaths paths = Installed();
        Release release = Release.Of(NewFiles());
        ReleaseFile app = release.File("app/Baxy.exe");
        byte[] zip = [.. release.Zip];
        zip[app.Offset + 2] ^= 0xFF;
        RangeServer server = new(Release.Cut(zip));
        using HttpClient http = new(server);

        Assert.That(
            async () => await release.Installation(paths, http).RunAsync((_, _, _) => { }, CancellationToken.None),
            Throws.InstanceOf<InvalidDataException>());

        Assert.That(Tree(paths.Root), Is.EqualTo(OldFiles().ToDictionary(file => file.Name, file => Convert.ToHexString(file.Content))));
        Assert.That(Directory.Exists(paths.Staging), Is.False);
        Assert.That(File.Exists(RangeFetcher.Kept(Path.Combine(paths.Downloads, RangeFetcher.StoreName), app)), Is.False);
    }

    [Test]
    public async Task A_cut_download_changes_nothing_and_the_next_try_goes_on_from_what_is_here()
    {
        InstallPaths paths = Installed(withModel: false);
        Release release = Release.Of(NewFiles());
        ReleaseFile app = release.File("app/Baxy.exe");
        ReleaseFile model = release.File("models/model.gguf");
        // The line gives the app whole and 1,000 bytes of the model, and then nothing more.
        RangeServer cut = new(release.Assets) { Budget = app.Packed + 1000 };
        using HttpClient first = new(cut);

        Assert.That(
            async () => await release.Installation(paths, first, wholeAbove: 1).RunAsync((_, _, _) => { }, CancellationToken.None),
            Throws.InstanceOf<HttpRequestException>());

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the old app"), "BAXY is as it was");
        string store = Path.Combine(paths.Downloads, RangeFetcher.StoreName);
        Assert.That(File.Exists(RangeFetcher.Kept(store, app)), Is.True);
        long here = new FileInfo(RangeFetcher.Kept(store, model) + ".part").Length;
        Assert.That(here, Is.EqualTo(1000));

        RangeServer healthy = new(release.Assets);
        using HttpClient second = new(healthy);
        Installation again = release.Installation(paths, second, wholeAbove: 1);
        await again.RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the new app"));
        Assert.That(await File.ReadAllBytesAsync(In(paths.Root, "models/model.gguf")), Is.EqualTo(Model));
        Assert.That(healthy.Ranges.Any(range => release.Covers(range, app)), Is.False, "the app was already here");
        Assert.That(healthy.Ranges.Min(range => release.Global(range)), Is.EqualTo(model.Offset + 1000), "the model goes on from its byte 1000");
        Assert.That(again.DownloadedBytes, Is.EqualTo(release.Packed("models/model.gguf", "mind/a.py", "mind/c.py") - 1000));
    }

    [Test]
    public async Task A_file_the_zip_deflated_also_goes_on_from_its_last_byte()
    {
        // The biggest files of an update (the app's exes) are deflated in the zip: a cut must not start them over.
        byte[] app = Encoding.ASCII.GetBytes(Convert.ToBase64String(RandomNumberGenerator.GetBytes(30_000)));
        (string Name, byte[] Content, bool Stored)[] entries = [.. NewFiles().Select(file => file.Name == "app/Baxy.exe" ? (file.Name, app, false) : file)];
        InstallPaths paths = Installed();
        Release release = Release.Of(entries);
        ReleaseFile packed = release.File("app/Baxy.exe");
        Assert.That(packed.Method, Is.EqualTo(ReleaseFile.Deflated));
        RangeServer cut = new(release.Assets) { Budget = 5000 };
        using HttpClient first = new(cut);

        Assert.That(
            async () => await release.Installation(paths, first, wholeAbove: 1).RunAsync((_, _, _) => { }, CancellationToken.None),
            Throws.InstanceOf<HttpRequestException>());

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the old app"));
        RangeServer healthy = new(release.Assets);
        using HttpClient second = new(healthy);
        Installation again = release.Installation(paths, second, wholeAbove: 1);
        await again.RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(await File.ReadAllBytesAsync(paths.App), Is.EqualTo(app));
        Assert.That(healthy.Ranges.Min(range => release.Global(range)), Is.EqualTo(packed.Offset + 5000));
        Assert.That(again.DownloadedBytes, Is.EqualTo(release.Packed("app/Baxy.exe", "mind/a.py", "mind/c.py") - 5000));
    }

    [Test]
    public async Task With_no_room_on_the_drive_nothing_is_downloaded_or_changed()
    {
        InstallPaths paths = Installed();
        Release release = Release.Of(NewFiles());
        RangeServer server = new(release.Assets);
        using HttpClient http = new(server);
        Installation installation = release.Installation(paths, http, freeBytes: 10);

        IOException? full = Assert.ThrowsAsync<IOException>(
            async () => await installation.RunAsync((_, _, _) => { }, CancellationToken.None));

        Assert.That(Failures.IsDiskFull(full!), Is.True);
        Assert.That(Failures.Classify(full!, () => false), Is.EqualTo(FailureKind.Disk));
        Assert.That(server.Ranges, Is.Empty);
        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the old app"));
    }

    // A file with nothing in it (Python's packages are full of them) has no bytes to ask for, and is installed all the same.
    [Test]
    public async Task A_new_empty_file_is_installed_without_asking_for_any_byte()
    {
        (string Name, byte[] Content, bool Stored)[] entries =
            [.. NewFiles(), ("mind/pkg/__init__.py", [], true), ("mind/pkg/other/__init__.py", [], true)];
        InstallPaths paths = Installed();
        Release release = Release.Of(entries);
        using HttpClient http = new(new RangeServer(release.Assets));
        Installation installation = release.Installation(paths, http);

        await installation.RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(new FileInfo(In(paths.Root, "mind/pkg/__init__.py")).Length, Is.Zero);
        Assert.That(File.Exists(In(paths.Root, "mind/pkg/other/__init__.py")), Is.True);
        Assert.That(installation.DownloadedBytes, Is.EqualTo(release.Packed("app/Baxy.exe", "mind/a.py", "mind/c.py")));
    }

    // The window's «Pause» holds the files taken alone as it holds the parts.
    [Test]
    public async Task While_paused_no_file_is_downloaded()
    {
        InstallPaths paths = Installed();
        Release release = Release.Of(NewFiles());
        RangeServer server = new(release.Assets);
        using HttpClient http = new(server);
        PauseGate pause = new();
        pause.Pause();
        Installation installation = new(
            release.Manifest, paths, new PartFetcher(http, retryDelay: TimeSpan.Zero), files: release.Files,
            ranges: new RangeFetcher(http, retryDelay: TimeSpan.Zero, gap: 0, gate: () => pause));

        Task running = installation.RunAsync((_, _, _) => { }, CancellationToken.None);
        await Task.Delay(300);

        Assert.That(running.IsCompleted, Is.False);
        Assert.That(server.Served, Is.Zero, "nothing came while paused");
        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the old app"));

        pause.Resume();
        await running;

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the new app"));
    }

    // The window looked at the space of a whole install (some 10 GB) before an update that downloads 94 MB.
    [Test]
    public void An_update_is_not_refused_beforehand_for_the_space_of_a_whole_install()
    {
        Release release = Release.Of(NewFiles());
        using HttpClient http = new(new RangeServer(release.Assets));

        long overBaxy = release.Installation(Installed(), http).StillNeededBytes;
        long fresh = release.Installation(new InstallPaths(Path.Combine(directory, "empty", "BAXY-App")), http).StillNeededBytes;

        Assert.That(overBaxy, Is.Zero, "what differs is known, and its space looked at, once the installed files are read");
        Assert.That(fresh, Is.EqualTo(release.Manifest.InstalledBytes + release.Zip.Length));
    }

    [Test]
    public async Task A_server_that_does_not_answer_ranges_gets_the_parts_whole()
    {
        InstallPaths paths = Installed();
        Release release = Release.Of(NewFiles());
        RangeServer server = new(release.Assets) { IgnoresRanges = true };
        using HttpClient http = new(server);

        await release.Installation(paths, http).RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the new app"));
        Assert.That(await File.ReadAllBytesAsync(In(paths.Root, "models/model.gguf")), Is.EqualTo(Model));
        Assert.That(File.Exists(In(paths.Root, "mind/gone.py")), Is.False);
    }

    [Test]
    public async Task A_first_install_takes_the_parts_whole()
    {
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Release release = Release.Of(NewFiles());
        RangeServer server = new(release.Assets);
        using HttpClient http = new(server);
        Installation installation = release.Installation(paths, http);

        await installation.RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(server.Ranges.All(range => range.Whole), Is.True);
        Assert.That((installation.KeptFiles, installation.TakenFiles), Is.EqualTo((0, 0)));
        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the new app"));
    }

    [Test]
    public async Task When_more_than_half_differs_the_parts_are_taken_whole()
    {
        InstallPaths paths = Installed(withModel: false);
        Release release = Release.Of(NewFiles());
        RangeServer server = new(release.Assets);
        using HttpClient http = new(server);

        await release.Installation(paths, http).RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(server.Ranges.All(range => range.Whole), Is.True);
        Assert.That(await File.ReadAllBytesAsync(In(paths.Root, "models/model.gguf")), Is.EqualTo(Model));
    }

    [Test]
    public async Task A_kept_file_is_checked_by_its_bytes_not_by_its_size()
    {
        InstallPaths paths = Installed();
        // Same length as the release's, other bytes: it is downloaded.
        await File.WriteAllTextAsync(In(paths.Root, "mind/b.py"), "b = 9");
        Release release = Release.Of(NewFiles());
        using HttpClient http = new(new RangeServer(release.Assets));
        Installation installation = release.Installation(paths, http);

        await installation.RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(await File.ReadAllTextAsync(In(paths.Root, "mind/b.py")), Is.EqualTo("b = 1"));
        Assert.That((installation.KeptFiles, installation.TakenFiles), Is.EqualTo((1, 4)));
    }

    [TestCase("../outside.txt")]
    [TestCase("app/../../outside.txt")]
    [TestCase("/rooted.txt")]
    [TestCase("C:/rooted.txt")]
    [TestCase("app\\Baxy.exe")]
    [TestCase("app//Baxy.exe")]
    public void A_file_manifest_that_names_a_path_outside_the_installation_is_refused(string path)
    {
        string json = $$"""
            {"version":"1","files":[{"path":{{System.Text.Json.JsonSerializer.Serialize(path)}},"bytes":1,"sha256":"{{new string('0', 64)}}",
             "archive":"a.zip","offset":40,"packed":1,"method":0}]}
            """;

        Assert.That(() => FileManifest.Parse(new MemoryStream(Encoding.UTF8.GetBytes(json))), Throws.InstanceOf<InvalidDataException>());
    }

    [Test]
    public void The_carried_file_manifest_counts_only_when_release_json_names_it_by_hash()
    {
        Release release = Release.Of(NewFiles());
        byte[] carried = Encoding.UTF8.GetBytes(System.Text.Json.JsonSerializer.Serialize(new
        {
            version = "2.0.0",
            files = release.Files.Files.Select(file => new
            {
                path = file.Path, bytes = file.Bytes, sha256 = file.Sha256, archive = file.Archive, offset = file.Offset,
                packed = file.Packed, method = file.Method,
            }),
        }));
        ReleaseFiles named = new("files.json", carried.Length, Convert.ToHexStringLower(SHA256.HashData(carried)));
        ReleaseManifest manifest = release.Manifest with { Files = named };

        Assert.That(FileManifest.Named(carried, manifest)!.Files, Has.Count.EqualTo(release.Files.Files.Count));
        Assert.That(FileManifest.Named([.. carried, (byte)' '], manifest), Is.Null, "other bytes");
        Assert.That(FileManifest.Named(carried, manifest with { Files = null }), Is.Null, "a release that names none");
        Assert.That(FileManifest.Named(carried, manifest with { Version = "2.0.1" }), Is.Null, "another version's");
        Assert.That(FileManifest.Named(null, manifest), Is.Null);
    }

    private const string Padding = "\n# xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx";

    private static (string Name, byte[] Content, bool Stored)[] OldFiles() =>
    [
        ("app/Baxy.exe", Encoding.UTF8.GetBytes("the old app"), false),
        ("models/model.gguf", Model, true),
        ("mind/a.py", Encoding.UTF8.GetBytes("a = 1"), false),
        ("mind/b.py", Encoding.UTF8.GetBytes("b = 1"), false),
        ("mind/gone.py", Encoding.UTF8.GetBytes("gone = 1"), false),
    ];

    private static (string Name, byte[] Content, bool Stored)[] NewFiles() =>
    [
        ("app/Baxy.exe", Encoding.UTF8.GetBytes("the new app"), false),
        ("models/model.gguf", Model, true),
        ("mind/a.py", Encoding.UTF8.GetBytes("a = 2  # changed" + Padding), false),
        ("mind/b.py", Encoding.UTF8.GetBytes("b = 1"), false),
        ("mind/c.py", Encoding.UTF8.GetBytes("c = 1  # new"), false),
    ];

    private InstallPaths Installed(bool withModel = true)
    {
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        foreach ((string name, byte[] content, _) in OldFiles().Where(file => withModel || file.Name != "models/model.gguf"))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(In(paths.Root, name))!);
            File.WriteAllBytes(In(paths.Root, name), content);
        }

        return paths;
    }

    private static string In(string root, string name) => Path.Combine(root, name.Replace('/', Path.DirectorySeparatorChar));

    private static Dictionary<string, string> Tree(string root) => Directory
        .EnumerateFiles(root, "*", SearchOption.AllDirectories)
        .ToDictionary(
            file => Path.GetRelativePath(root, file).Replace(Path.DirectorySeparatorChar, '/'),
            file => Convert.ToHexString(File.ReadAllBytes(file)));

    /// <summary>A release of one zip in two parts, with its files.json as scripts/build_github_release.py writes it.</summary>
    private sealed record Release(byte[] Zip, Dictionary<string, byte[]> Assets, ReleaseManifest Manifest, FileManifest Files)
    {
        private const string Name = "baxy.zip";

        internal static Release Of((string Name, byte[] Content, bool Stored)[] entries)
        {
            using MemoryStream memory = new();
            using (ZipArchive zip = new(memory, ZipArchiveMode.Create, leaveOpen: true))
            {
                foreach ((string name, byte[] content, bool stored) in entries)
                {
                    using Stream entry = zip.CreateEntry(name, stored ? CompressionLevel.NoCompression : CompressionLevel.Optimal).Open();
                    entry.Write(content);
                }
            }

            byte[] bytes = memory.ToArray();
            Dictionary<string, byte[]> assets = Cut(bytes);
            ReleaseArchive archive = new(Name, [.. assets.Select(asset => new ReleasePart(asset.Key, asset.Value.Length, Hash(asset.Value)))]);
            Dictionary<string, byte[]> contents = entries.ToDictionary(entry => entry.Name, entry => entry.Content);
            return new Release(
                bytes,
                assets,
                new ReleaseManifest("2.0.0", BaseUrl, entries.Sum(entry => (long)entry.Content.Length), [archive]),
                new FileManifest("2.0.0", Listed(bytes, contents)));
        }

        /// <summary>Two parts, cut inside the model so that it comes from both.</summary>
        internal static Dictionary<string, byte[]> Cut(byte[] zip)
        {
            int half = zip.Length / 2;
            return new Dictionary<string, byte[]> { [Name + ".000"] = zip[..half], [Name + ".001"] = zip[half..] };
        }

        internal Installation Installation(
            InstallPaths paths, HttpClient http, long? freeBytes = null, int wholeAbove = 0, long gap = 0, int moveAttempts = 5)
        {
            // wholeAbove: a release so big beside what differs that it is taken file by file even with the model missing.
            ReleaseManifest manifest = wholeAbove == 0
                ? Manifest
                : Manifest with { Archives = [Manifest.Archives[0] with { Parts = [.. Manifest.Archives[0].Parts, new ReleasePart("never", 1 << 20, new string('0', 64))] }] };
            PartFetcher parts = new(http, retryDelay: TimeSpan.Zero);
            RangeFetcher ranges = new(http, retryDelay: TimeSpan.Zero, gap: gap);
            return freeBytes is { } free
                ? new Installation(manifest, paths, parts, moveAttempts, Files, ranges) { FreeBytes = () => free }
                : new Installation(manifest, paths, parts, moveAttempts, Files, ranges);
        }

        internal ReleaseFile File(string path) => Files.Files.Single(file => file.Path == path);

        internal long Packed(params string[] paths) => paths.Sum(path => File(path).Packed);

        /// <summary>Where a request's first byte is in the zip.</summary>
        internal long Global((string Part, long From, long To, bool Whole) range) =>
            range.From + (range.Part.EndsWith(".001", StringComparison.Ordinal) ? Zip.Length / 2 : 0);

        internal bool Covers((string Part, long From, long To, bool Whole) range, ReleaseFile file)
        {
            long from = Global(range);
            long to = from + (range.To - range.From);
            return from < file.Offset + file.Packed && to >= file.Offset;
        }

        private static string Hash(byte[] content) => Convert.ToHexStringLower(SHA256.HashData(content));

        // The zip's central directory (PKWARE APPNOTE.TXT 4.3.12) and each entry's local header (4.3.7).
        private static List<ReleaseFile> Listed(byte[] zip, Dictionary<string, byte[]> contents)
        {
            int end = zip.AsSpan().LastIndexOf(new byte[] { 0x50, 0x4b, 0x05, 0x06 });
            int count = BitConverter.ToUInt16(zip, end + 10);
            int at = (int)BitConverter.ToUInt32(zip, end + 16);
            List<ReleaseFile> files = [];
            for (int index = 0; index < count; index++)
            {
                int method = BitConverter.ToUInt16(zip, at + 10);
                long packed = BitConverter.ToUInt32(zip, at + 20);
                long size = BitConverter.ToUInt32(zip, at + 24);
                int nameLength = BitConverter.ToUInt16(zip, at + 28);
                int local = (int)BitConverter.ToUInt32(zip, at + 42);
                string name = Encoding.UTF8.GetString(zip, at + 46, nameLength);
                long offset = local + 30 + BitConverter.ToUInt16(zip, local + 26) + BitConverter.ToUInt16(zip, local + 28);
                files.Add(new ReleaseFile(name, size, Hash(contents[name]), Name, offset, packed, method));
                at += 46 + nameLength + BitConverter.ToUInt16(zip, at + 30) + BitConverter.ToUInt16(zip, at + 32);
            }

            return files;
        }
    }

    /// <summary>A server of release assets that answers Range requests as GitHub's does, and notes each one.</summary>
    private sealed class RangeServer(IReadOnlyDictionary<string, byte[]> files) : HttpMessageHandler
    {
        internal List<(string Part, long From, long To, bool Whole)> Ranges { get; } = [];

        internal long Served { get; private set; }

        /// <summary>A server that sends the whole file whatever range is asked (RFC 9110 lets it).</summary>
        internal bool IgnoresRanges { get; init; }

        /// <summary>The bytes the line gives before every connection drops; null for a line that holds.</summary>
        internal long? Budget { get; set; }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string name = request.RequestUri!.Segments[^1];
            byte[] content = files[name];
            RangeItemHeaderValue? asked = IgnoresRanges ? null : request.Headers.Range?.Ranges.First();
            long from = asked?.From ?? 0;
            long to = asked?.To ?? content.Length - 1;
            Ranges.Add((name, from, to, asked is null));
            byte[] slice = content[(int)from..(int)(to + 1)];
            int given = (int)Math.Min(slice.Length, Budget ?? slice.Length);
            Budget -= given;
            Served += given;
            HttpResponseMessage response = new(asked is null ? HttpStatusCode.OK : HttpStatusCode.PartialContent)
            {
                Content = new StreamContent(new CutStream(slice[..given], cut: given < slice.Length)),
            };
            if (asked is not null)
            {
                response.Content.Headers.ContentRange = new ContentRangeHeaderValue(from, to, content.Length);
            }

            return Task.FromResult(response);
        }
    }

    private sealed class CutStream(byte[] bytes, bool cut) : MemoryStream(bytes)
    {
        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            int read = await base.ReadAsync(buffer, cancellationToken);
            return read == 0 && cut ? throw new IOException("connection reset") : read;
        }

        public override Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken) =>
            ReadAsync(buffer.AsMemory(offset, count), cancellationToken).AsTask();
    }
}
