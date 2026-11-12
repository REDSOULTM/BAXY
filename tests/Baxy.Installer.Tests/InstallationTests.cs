using System.IO.Compression;
using System.Net;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

[TestFixture]
internal sealed class InstallationTests
{
    private const string BaseUrl = "https://example.test/release/";
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
    public async Task Installs_a_release_cut_in_parts_with_both_servers()
    {
        Dictionary<string, byte[]> assets = [];
        ReleaseArchive release = Cut("release", Zip(
            ("app/Baxy.exe", "the app"),
            ("models/model.gguf", new string('m', 5000)),
            ("llama/server.txt", "cuda"),
            ("llama-vulkan/server.txt", "vulkan")), assets);
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        using HttpClient http = new(new Assets(assets));

        await Make(paths, http, release).RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("the app"));
        Assert.That(new FileInfo(Path.Combine(paths.Root, "models", "model.gguf")).Length, Is.EqualTo(5000));
        Assert.That(await File.ReadAllTextAsync(Path.Combine(paths.Root, "llama", "server.txt")), Is.EqualTo("cuda"));
        Assert.That(await File.ReadAllTextAsync(Path.Combine(paths.Root, "llama-vulkan", "server.txt")), Is.EqualTo("vulkan"));
        Assert.That(Directory.Exists(paths.Downloads), Is.False);
        Assert.That(Directory.Exists(paths.Staging), Is.False);
    }

    [Test]
    public async Task A_cut_download_continues_from_what_is_on_disk()
    {
        byte[] content = RandomNumberGenerator.GetBytes(4096);
        ReleasePart part = new("part.001", content.Length, Hash(content));
        await File.WriteAllBytesAsync(Path.Combine(directory, part.File), content[..1000]);
        Assets assets = new(new Dictionary<string, byte[]> { [part.File] = content });
        using HttpClient http = new(assets);

        string path = await Fetcher(http).FetchAsync(BaseUrl, part, directory, _ => { }, CancellationToken.None);

        Assert.That(assets.FirstRangeStart, Is.EqualTo(1000));
        Assert.That(await File.ReadAllBytesAsync(path), Is.EqualTo(content));
    }

    [Test]
    public void Bytes_with_the_wrong_hash_are_never_kept()
    {
        byte[] content = Encoding.UTF8.GetBytes("not what the manifest says");
        ReleasePart part = new("part.001", content.Length, new string('0', 64));
        using HttpClient http = new(new Assets(new Dictionary<string, byte[]> { [part.File] = content }));

        Assert.ThrowsAsync<InvalidDataException>(() =>
            Fetcher(http).FetchAsync(BaseUrl, part, directory, _ => { }, CancellationToken.None));
        Assert.That(File.Exists(Path.Combine(directory, part.File)), Is.False);
    }

    [Test]
    public void A_zip_entry_outside_the_installation_is_refused_and_nothing_is_replaced()
    {
        Dictionary<string, byte[]> assets = [];
        ReleaseArchive evil = Cut("evil", Zip(("../outside.txt", "x"), ("app/Baxy.exe", "evil")), assets);
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(paths.Root);
        File.WriteAllText(Path.Combine(paths.Root, "kept.txt"), "kept");
        using HttpClient http = new(new Assets(assets));

        Assert.ThrowsAsync<InvalidDataException>(() =>
            Make(paths, http, evil).RunAsync((_, _, _) => { }, CancellationToken.None));

        Assert.That(File.Exists(Path.Combine(directory, "outside.txt")), Is.False);
        Assert.That(File.Exists(Path.Combine(paths.Root, "kept.txt")), Is.True);
    }

    [Test]
    public void A_folder_in_use_is_reported_and_keeps_what_it_had()
    {
        Dictionary<string, byte[]> assets = [];
        ReleaseArchive common = Cut("common", Zip(("app/Baxy.exe", "new")), assets);
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(paths.Root);
        string running = Path.Combine(paths.Root, "running.txt");
        using FileStream open = new(running, FileMode.Create, FileAccess.Write, FileShare.None);
        using HttpClient http = new(new Assets(assets));

        Assert.ThrowsAsync<InstallBlockedException>(() =>
            Make(paths, http, common).RunAsync((_, _, _) => { }, CancellationToken.None));

        Assert.That(File.Exists(running), Is.True);
    }

    [Test]
    public async Task A_swap_that_stopped_halfway_gets_its_only_copy_back_when_the_install_is_cancelled()
    {
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(Path.Combine(paths.Previous, "app"));
        await File.WriteAllTextAsync(Path.Combine(paths.Previous, "app", "Baxy.exe"), "the app");
        await File.WriteAllTextAsync(Path.Combine(paths.Previous, "kept.txt"), "kept");
        Dictionary<string, byte[]> assets = [];
        ReleaseArchive common = Cut("common", Zip(("app/Baxy.exe", "new")), assets);
        using HttpClient http = new(new Assets(assets));
        using CancellationTokenSource cancelled = new();
        await cancelled.CancelAsync();

        Assert.CatchAsync<OperationCanceledException>(() =>
            Make(paths, http, common).RunAsync((_, _, _) => { }, cancelled.Token));

        Assert.That(File.Exists(Path.Combine(paths.Root, "kept.txt")), Is.True);
        Assert.That(Directory.Exists(paths.Previous), Is.False);
    }

    [Test]
    public async Task What_cannot_be_cleaned_after_the_swap_does_not_fail_a_finished_install()
    {
        Dictionary<string, byte[]> assets = [];
        ReleaseArchive common = Cut("common", Zip(("app/Baxy.exe", "new")), assets);
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        InstallPaths.MarkAsBaxys(paths.Downloads);
        string held = Path.Combine(paths.Downloads, "held.txt");
        using HttpClient http = new(new Assets(assets));
        using (new FileStream(held, FileMode.Create, FileAccess.Write, FileShare.None))
        {
            await Make(paths, http, common).RunAsync((_, _, _) => { }, CancellationToken.None);
        }

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("new"));
        // UNI1 (REV8 U4): what stays beside the folder carries BAXY's mark, so an uninstall knows it is BAXY's.
        Assert.That(File.Exists(Path.Combine(paths.Downloads, InstallPaths.MarkName)), Is.True);
        Assert.That(File.Exists(Path.Combine(paths.Root, InstallPaths.MarkName)), Is.True);
    }

    [Test]
    public async Task A_connection_that_keeps_dropping_is_followed_while_it_moves_forward()
    {
        byte[] content = RandomNumberGenerator.GetBytes(40);
        ReleasePart part = new("part.001", content.Length, Hash(content));
        using HttpClient http = new(new Dropping(content, bytesPerRequest: 2));

        string path = await Fetcher(http).FetchAsync(BaseUrl, part, directory, _ => { }, CancellationToken.None);

        Assert.That(await File.ReadAllBytesAsync(path), Is.EqualTo(content));
    }

    [Test]
    public void A_connection_that_never_moves_forward_ends_with_a_failure()
    {
        byte[] content = RandomNumberGenerator.GetBytes(40);
        ReleasePart part = new("part.001", content.Length, Hash(content));
        Dropping dropping = new(content, bytesPerRequest: 0);
        using HttpClient http = new(dropping);

        Assert.CatchAsync<HttpRequestException>(() =>
            Fetcher(http).FetchAsync(BaseUrl, part, directory, _ => { }, CancellationToken.None));
        Assert.That(dropping.Requests, Is.LessThan(20));
    }

    [Test]
    public void A_part_that_keeps_arriving_damaged_is_not_downloaded_again_and_again()
    {
        byte[] content = Encoding.UTF8.GetBytes("not what the manifest says");
        ReleasePart part = new("part.001", content.Length, new string('0', 64));
        Dropping whole = new(content, bytesPerRequest: content.Length);
        using HttpClient http = new(whole);

        Assert.ThrowsAsync<InvalidDataException>(() =>
            Fetcher(http).FetchAsync(BaseUrl, part, directory, _ => { }, CancellationToken.None));
        Assert.That(whole.Requests, Is.LessThanOrEqualTo(3));
    }

    [Test]
    public async Task A_retry_counts_what_is_already_on_the_disk_as_needed_no_more()
    {
        byte[] content = RandomNumberGenerator.GetBytes(1000);
        ReleasePart part = new("part.001", content.Length, Hash(content));
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Installation installation = new(
            new ReleaseManifest("1.0.0", BaseUrl, 5000, [new ReleaseArchive("a", [part])]),
            paths,
            Fetcher(new HttpClient(new Assets(new Dictionary<string, byte[]>()))));
        Directory.CreateDirectory(paths.Downloads);
        await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, part.File), content[..400]);
        await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, "other.bin"), new byte[300]);
        Directory.CreateDirectory(Path.Combine(paths.Staging, "app"));
        await File.WriteAllBytesAsync(Path.Combine(paths.Staging, "app", "half.bin"), new byte[2000]);

        Assert.That(installation.RequiredBytes, Is.EqualTo(6000));
        Assert.That(installation.StillNeededBytes, Is.EqualTo(6000 - 400 - 2000));
    }

    [Test]
    public void Removing_a_folder_in_use_changes_nothing_so_the_uninstall_can_be_tried_again()
    {
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(Path.Combine(paths.Root, "app"));
        string running = Path.Combine(paths.Root, "app", "Baxy.exe");
        using (new FileStream(running, FileMode.Create, FileAccess.Write, FileShare.None))
        {
            Assert.Catch<IOException>(() => WindowsIntegration.RemoveFolders(paths));
            Assert.That(File.Exists(running), Is.True);
        }

        WindowsIntegration.RemoveFolders(paths);

        Assert.That(Directory.Exists(paths.Root), Is.False);
    }

    [Test]
    public void Removing_also_takes_what_a_cancelled_install_left_beside_it()
    {
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        foreach (string folder in new[] { paths.Root, paths.Staging, paths.Previous, paths.Downloads })
        {
            // UNI1 (REV8 U4): the install leaves its mark in what it makes; a folder that only shares the name stays.
            InstallPaths.MarkAsBaxys(folder);
            File.WriteAllText(Path.Combine(folder, "x.txt"), "x");
        }

        WindowsIntegration.RemoveFolders(paths);

        Assert.That(Directory.GetFileSystemEntries(directory), Is.Empty);
    }

    [Test]
    public void A_folder_an_earlier_removal_left_does_not_block_the_next_one()
    {
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        InstallPaths.MarkAsBaxys(paths.Root + ".removing-earlier");
        File.WriteAllText(Path.Combine(paths.Root + ".removing-earlier", "x.txt"), "x");
        Directory.CreateDirectory(paths.Root);

        WindowsIntegration.RemoveFolders(paths);

        Assert.That(Directory.GetFileSystemEntries(directory), Is.Empty);
    }

    [Test]
    public void An_asset_the_server_says_is_not_there_is_asked_for_only_once()
    {
        byte[] content = RandomNumberGenerator.GetBytes(40);
        ReleasePart part = new("part.001", content.Length, Hash(content));
        Refusing refusing = new();
        using HttpClient http = new(refusing);

        HttpRequestException? refused = Assert.ThrowsAsync<HttpRequestException>(() =>
            Fetcher(http).FetchAsync(BaseUrl, part, directory, _ => { }, CancellationToken.None));

        Assert.That(refusing.Requests, Is.EqualTo(1));
        Assert.That(Failures.Classify(refused!, baxyIsOpen: () => false), Is.EqualTo(FailureKind.Other));
    }

    [Test]
    public void A_full_disk_is_not_waited_on_as_if_it_were_the_connection()
    {
        IOException full = new("full", unchecked((int)0x80070070));

        Assert.That(Failures.IsDiskFull(full), Is.True);
        Assert.That(Failures.IsDiskFull(new IOException("locked")), Is.False);
        Assert.That(Failures.Classify(full, baxyIsOpen: () => false), Is.EqualTo(FailureKind.Disk));
    }

    [Test]
    public async Task A_half_unpacked_folder_from_an_earlier_try_is_gone_before_the_download()
    {
        Dictionary<string, byte[]> assets = [];
        ReleaseArchive common = Cut("common", Zip(("app/Baxy.exe", "new")), assets);
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        InstallPaths.MarkAsBaxys(paths.Staging);
        await File.WriteAllTextAsync(Path.Combine(paths.Staging, "old.txt"), "old");
        using HttpClient http = new(new Assets(assets));
        bool stagingWasThere = true;

        await Make(paths, http, common).RunAsync(
            (phase, _, _) =>
            {
                if (phase == InstallPhase.Downloading)
                {
                    stagingWasThere = Directory.Exists(paths.Staging);
                }
            },
            CancellationToken.None);

        Assert.That(stagingWasThere, Is.False);
        Assert.That(File.Exists(Path.Combine(paths.Root, "old.txt")), Is.False);
    }

    // UPD1 (REV10 M4): an update deleted <folder>.old, .new and .download by their name alone.
    [TestCase(".old")]
    [TestCase(".new")]
    [TestCase(".download")]
    public async Task A_folder_beside_that_only_shares_the_name_is_left_and_the_update_says_so(string suffix)
    {
        Dictionary<string, byte[]> assets = [];
        ReleaseArchive common = Cut("common", Zip(("app/Baxy.exe", "new")), assets);
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(Path.Combine(paths.Root, "app"));
        await File.WriteAllTextAsync(paths.App, "before");
        string neighbour = paths.Root + suffix;
        Directory.CreateDirectory(neighbour);
        string mine = Path.Combine(neighbour, "my-backup.txt");
        await File.WriteAllTextAsync(mine, "the person's");
        using HttpClient http = new(new Assets(assets));

        NotBaxysException refused = Assert.ThrowsAsync<NotBaxysException>(() =>
            Make(paths, http, common).RunAsync((_, _, _) => { }, CancellationToken.None))!;

        Assert.That(refused.Folder, Is.EqualTo(neighbour));
        Assert.That(await File.ReadAllTextAsync(mine), Is.EqualTo("the person's"));
        Assert.That(Directory.GetFileSystemEntries(neighbour), Has.Length.EqualTo(1), "no mark written into it");
        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("before"));
        Assert.That(Failures.Classify(refused, baxyIsOpen: () => false), Is.EqualTo(FailureKind.NotBaxys));
    }

    // Blind review of UPD1: an installer up to 1.4.2 made the .download for the Windows components without a mark, and left
    // one half downloaded when it failed. That folder is BAXY's.
    [Test]
    public async Task A_download_folder_holding_only_the_windows_components_an_older_installer_left_is_baxys()
    {
        Dictionary<string, byte[]> assets = [];
        ReleaseArchive common = Cut("common", Zip(("app/Baxy.exe", "new")), assets);
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(paths.Downloads);
        await File.WriteAllTextAsync(Path.Combine(paths.Downloads, "vc_redist.x64.exe"), "half");
        using HttpClient http = new(new Assets(assets));

        await Make(paths, http, common).RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("new"));
        Assert.That(Directory.Exists(paths.Downloads), Is.False);
    }

    // REM1 (REV12 A-1): an installer before UNI1 (1.3.x) downloaded the release's parts into an unmarked .download and kept
    // them when the download was cut, to resume. Another version's parts, a part half downloaded and the Windows
    // components beside them are BAXY's, and the update goes on.
    [Test]
    public async Task The_parts_an_installer_before_the_mark_left_half_downloaded_are_baxys()
    {
        Dictionary<string, byte[]> assets = [];
        ReleaseArchive common = Cut("common", Zip(("app/Baxy.exe", "new")), assets);
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(Path.Combine(paths.Root, "app"));
        await File.WriteAllTextAsync(paths.App, "before");
        Directory.CreateDirectory(paths.Downloads);
        byte[] older = Zip(("app/Baxy.exe", new string('o', 4000)), ("core/x.dll", new string('c', 4000)));
        byte[] gpu = Zip(("llama/x.dll", "gpu"));
        await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, "baxy-1.3.1.zip.000"), older[..(older.Length / 2)]);
        await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, "baxy-1.3.1.zip.001"), older[(older.Length / 2)..^10]);
        await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, "baxy-1.3.1-nvidia.zip.000"), gpu[..20]);
        await File.WriteAllTextAsync(Path.Combine(paths.Downloads, "vc_redist.x64.exe"), "half");
        using HttpClient http = new(new Assets(assets));

        Assert.That(InstallPaths.IsBaxys(paths.Downloads), Is.True);
        await Make(paths, http, common).RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("new"));
        Assert.That(Directory.Exists(paths.Downloads), Is.False);
    }

    // REM1 (REV12 A-1): what makes them BAXY's is what they hold, not their name. Zip parts that are not a BAXY release
    // (no app\Baxy.exe first), a part whose first piece is not there, or a file of the person's beside them stay.
    [TestCase("zip of the person's")]
    [TestCase("a part without its first")]
    [TestCase("a file of the person's beside BAXY's parts")]
    [TestCase("a zip of the person's beside BAXY's parts")]
    public async Task Parts_that_are_not_a_baxy_release_are_left(string what)
    {
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(paths.Downloads);
        byte[] baxy = Zip(("app/Baxy.exe", new string('o', 4000)));
        switch (what)
        {
            case "zip of the person's":
                byte[] photos = Zip(("fotos/playa.jpg", new string('p', 4000)));
                await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, "fotos.zip.000"), photos[..100]);
                break;
            case "a zip of the person's beside BAXY's parts":
                await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, "baxy-1.3.1.zip.000"), baxy[..100]);
                byte[] mine = Zip(("fotos/playa.jpg", new string('p', 4000)));
                await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, "fotos.zip.000"), mine[..100]);
                await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, "fotos.zip.001"), mine[100..]);
                break;
            case "a part without its first":
                await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, "baxy-1.3.1.zip.000"), baxy[..100]);
                await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, "otra.zip.001"), baxy[100..]);
                break;
            default:
                await File.WriteAllBytesAsync(Path.Combine(paths.Downloads, "baxy-1.3.1.zip.000"), baxy[..100]);
                await File.WriteAllTextAsync(Path.Combine(paths.Downloads, "mi-respaldo.txt"), "the person's");
                break;
        }

        Assert.That(InstallPaths.IsBaxys(paths.Downloads), Is.False);
        Assert.That(() => paths.RefuseWhatIsNotBaxys(), Throws.TypeOf<NotBaxysException>());
    }

    [Test]
    public async Task What_an_earlier_baxy_left_beside_it_is_still_cleaned()
    {
        Dictionary<string, byte[]> assets = [];
        ReleaseArchive common = Cut("common", Zip(("app/Baxy.exe", "new")), assets);
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(Path.Combine(paths.Root, "app"));
        await File.WriteAllTextAsync(paths.App, "before");
        // An older BAXY moved aside (no mark before UNI1, but its app), a marked download and an empty half-made folder.
        InstallPaths older = new(paths.Previous);
        Directory.CreateDirectory(Path.Combine(older.Root, "app"));
        await File.WriteAllTextAsync(older.App, "older");
        InstallPaths.MarkAsBaxys(paths.Downloads);
        await File.WriteAllTextAsync(Path.Combine(paths.Downloads, "left.001"), "x");
        Directory.CreateDirectory(paths.Staging);
        using HttpClient http = new(new Assets(assets));

        await Make(paths, http, common).RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(await File.ReadAllTextAsync(paths.App), Is.EqualTo("new"));
        Assert.That(Directory.Exists(paths.Previous) || Directory.Exists(paths.Downloads) || Directory.Exists(paths.Staging), Is.False);
    }

    [Test]
    public void A_folder_in_use_is_only_blamed_on_baxy_when_a_baxy_is_open()
    {
        InstallBlockedException blocked = new("in use", new IOException("in use"));

        Assert.That(Failures.Classify(blocked, baxyIsOpen: () => true), Is.EqualTo(FailureKind.Open));
        Assert.That(Failures.Classify(blocked, baxyIsOpen: () => false), Is.EqualTo(FailureKind.Other));
    }

    [Test]
    public void A_local_file_error_is_not_told_as_a_lost_connection()
    {
        IOException local = new("the file is locked");
        IOException dropped = new("connection reset", new System.Net.Sockets.SocketException());

        Assert.That(Failures.Classify(local, baxyIsOpen: () => false), Is.EqualTo(FailureKind.Other));
        Assert.That(Failures.Classify(dropped, baxyIsOpen: () => false), Is.EqualTo(FailureKind.Network));
    }

    [TestCase("CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US", true)]
    [TestCase("CN=x, O=Microsoft Corporation Foo LLC, C=US", false)]
    [TestCase("CN=O=Microsoft Corporation, O=Someone Else, C=US", false)]
    public void Only_microsoft_itself_passes_as_the_signer(string subject, bool passes)
    {
        Assert.That(Prerequisites.IsMicrosoftSubject(subject), Is.EqualTo(passes));
    }

    [TestCase(@"PCI\VEN_10DE&DEV_2803", GpuSupport.Measured)]
    [TestCase(@"pci\ven_1002&dev_73ef", GpuSupport.Measured)]
    [TestCase(@"PCI\VEN_8086&DEV_9A49", GpuSupport.NotMeasured)]
    [TestCase(@"PCI\VEN_1414&DEV_008C", GpuSupport.None)]
    public void What_is_said_follows_the_vendor(string device, GpuSupport support)
    {
        Assert.That(MachineGpu.Choose([new GpuAdapter(device, 8_000_000_000)]), Is.EqualTo(support));
    }

    [Test]
    public void Nvidia_wins_beside_integrated_graphics_and_a_small_card_is_told()
    {
        GpuSupport laptop = MachineGpu.Choose([
            new GpuAdapter(@"PCI\VEN_8086&DEV_9A49", null),
            new GpuAdapter(@"PCI\VEN_10DE&DEV_1F99", 2_000_000_000),
        ]);

        Assert.That(laptop, Is.EqualTo(GpuSupport.TooLittleMemory));
    }

    // UNI1 (REV8 F1): the plain address «only this machine» is decided on the host the address goes to (RFC 3986:
    // authority = [ userinfo "@" ] host [ ":" port ]), not on how its text begins.
    [TestCase("http://127.0.0.1:18791/", true)]
    [TestCase("https://github.com/REDSOULTM/BAXY/releases/download/v1.3.4/", true)]
    [TestCase("http://127.0.0.1:80@example.test/download/", false)]
    [TestCase("http://127.0.0.1:18791@example.test/", false)]
    [TestCase("http://127.0.0.1.example.test:80/", false)]
    [TestCase("http://example.test/", false)]
    public void A_plain_address_is_only_this_machines_by_its_host(string baseUrl, bool accepted)
    {
        string json = $$"""
            {"version":"1","baseUrl":"{{baseUrl}}","installedBytes":1,
             "archives":[{"name":"a","parts":[{"file":"a.001","bytes":1,
             "sha256":"0000000000000000000000000000000000000000000000000000000000000000"}]}]}
            """;

        TestDelegate parse = () => ReleaseManifest.Parse(new MemoryStream(Encoding.UTF8.GetBytes(json)));
        if (accepted)
        {
            Assert.DoesNotThrow(parse);
        }
        else
        {
            Assert.Throws<InvalidDataException>(parse);
        }
    }

    [Test]
    public void A_manifest_with_a_path_as_asset_name_is_refused()
    {
        const string json = """
            {"version":"1","baseUrl":"https://example.test/","installedBytes":1,
             "archives":[{"name":"a","parts":[{"file":"../x","bytes":1,
             "sha256":"0000000000000000000000000000000000000000000000000000000000000000"}]}]}
            """;

        Assert.Throws<InvalidDataException>(() => ReleaseManifest.Parse(new MemoryStream(Encoding.UTF8.GetBytes(json))));
    }

    // CUDA EULA 2.1 licenses the SDK for applications «only for use in systems with NVIDIA GPUs»: the folder that carries
    // it reaches only a machine with one (https://docs.nvidia.com/cuda/eula/index.html, read 2026-11-06).
    [TestCase("PCI\\VEN_1002&DEV_73EF")]
    [TestCase("PCI\\VEN_8086&DEV_46A6")]
    [TestCase("")]
    public async Task A_machine_without_an_nvidia_gpu_never_downloads_the_cuda_part(string deviceId)
    {
        (ReleaseManifest manifest, Dictionary<string, byte[]> assets, long baseBytes) = ReleaseWithACudaPart();
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        Assets server = new(assets);
        using HttpClient http = new(server);

        ReleaseManifest chosen = manifest.ForMachine([new GpuAdapter(deviceId, null)]);
        await new Installation(chosen, paths, Fetcher(http)).RunAsync((_, _, _) => { }, CancellationToken.None);

        Assert.That(server.Requested, Has.None.Contains("nvidia"));
        Assert.That(Directory.Exists(Path.Combine(paths.Root, "llama")), Is.False);
        Assert.That(File.Exists(Path.Combine(paths.Root, "llama-vulkan", "server.txt")), Is.True);
        Assert.That(chosen.InstalledBytes, Is.EqualTo(100));
        Assert.That(new Installation(chosen, paths, Fetcher(http)).RequiredBytes, Is.EqualTo(100 + baseBytes));
    }

    [TestCase("PCI\\VEN_10DE&DEV_2560")]
    [TestCase("pci\\ven_10de&dev_2560")]
    public async Task A_machine_with_an_nvidia_gpu_gets_both_parts(string deviceId)
    {
        (ReleaseManifest manifest, Dictionary<string, byte[]> assets, long _) = ReleaseWithACudaPart();
        InstallPaths paths = new(Path.Combine(directory, "BAXY-App"));
        long lastTotal = 0;
        using HttpClient http = new(new Assets(assets));

        ReleaseManifest chosen = manifest.ForMachine([new GpuAdapter("PCI\\VEN_8086&DEV_46A6", null), new GpuAdapter(deviceId, null)]);
        await new Installation(chosen, paths, Fetcher(http)).RunAsync(
            (phase, _, total) =>
            {
                if (phase == InstallPhase.Unpacking)
                {
                    lastTotal = total;
                }
            },
            CancellationToken.None);

        Assert.That(await File.ReadAllTextAsync(Path.Combine(paths.Root, "llama", "server.txt")), Is.EqualTo("cuda"));
        Assert.That(await File.ReadAllTextAsync(Path.Combine(paths.Root, "licenses", "LICENSE-llama.cpp.txt")), Is.EqualTo("MIT"));
        Assert.That(File.Exists(paths.App), Is.True);
        Assert.That(chosen.InstalledBytes, Is.EqualTo(150));
        Assert.That(lastTotal, Is.EqualTo(150), "the bar counts both parts: it does not fill with the first");
    }

    [Test]
    public void A_manifest_with_a_part_for_an_unknown_kind_of_gpu_is_refused()
    {
        const string json = """
            {"version":"1","baseUrl":"https://example.test/","installedBytes":1,
             "archives":[{"name":"a","gpuVendor":"nvidia","parts":[{"file":"x","bytes":1,
             "sha256":"0000000000000000000000000000000000000000000000000000000000000000"}]}]}
            """;

        Assert.Throws<InvalidDataException>(() => ReleaseManifest.Parse(new MemoryStream(Encoding.UTF8.GetBytes(json))));
    }

    [Test]
    public void The_field_names_the_release_script_writes_are_read()
    {
        const string json = """
            {"version":"1","baseUrl":"https://example.test/","installedBytes":7,
             "archives":[{"name":"a","parts":[{"file":"x","bytes":1,
             "sha256":"0000000000000000000000000000000000000000000000000000000000000000"}]},
             {"name":"b","gpuVendor":"10de","installedBytes":5,"parts":[{"file":"y","bytes":1,
             "sha256":"0000000000000000000000000000000000000000000000000000000000000000"}]}]}
            """;

        ReleaseManifest manifest = ReleaseManifest.Parse(new MemoryStream(Encoding.UTF8.GetBytes(json)));

        Assert.That(manifest.ForMachine([new GpuAdapter("PCI\\VEN_10DE&DEV_1", null)]).InstalledBytes, Is.EqualTo(12));
        Assert.That(manifest.ForMachine([new GpuAdapter("PCI\\VEN_1002&DEV_1", null)]).Archives.Select(archive => archive.Name), Is.EqualTo(new[] { "a" }));
    }

    // The MIT license of .NET asks for its text in every copy, and this exe is one before anything is installed. The Windows SDK
    // projections it carries are redistributable «subject to the license terms for the software»
    // (https://learn.microsoft.com/en-us/legal/windows-sdk/redist, read 2026-11-07): those terms go inside it too.
    [TestCase("Baxy.Installer.licenses.dotnet-LICENSE.txt", ".NET Foundation")]
    [TestCase("Baxy.Installer.licenses.dotnet-runtime-THIRD-PARTY-NOTICES.txt", "third-party libraries")]
    [TestCase("Baxy.Installer.licenses.dotnet-wpf-THIRD-PARTY-NOTICES.txt", "third-party libraries")]
    [TestCase("Baxy.Installer.licenses.CsWinRT-LICENSE.txt", "Microsoft")]
    [TestCase("Baxy.Installer.licenses.Windows-SDK-License.rtf", "WINDOWS SOFTWARE DEVELOPMENT KIT")]
    public void The_exe_carries_the_licenses_of_its_runtime_inside_it(string resource, string phrase)
    {
        using Stream? stream = typeof(ReleaseManifest).Assembly.GetManifestResourceStream(resource);

        Assert.That(stream, Is.Not.Null);
        using StreamReader reader = new(stream!);
        Assert.That(reader.ReadToEnd(), Does.Contain(phrase));
    }

    // Like scripts/build_github_release.py, the NVIDIA part repeats licenses the main archive already carries, with the same bytes.
    private static (ReleaseManifest Manifest, Dictionary<string, byte[]> Assets, long BaseBytes) ReleaseWithACudaPart()
    {
        Dictionary<string, byte[]> assets = [];
        ReleaseArchive common = Cut(
            "baxy.zip", Zip(("app/Baxy.exe", "the app"), ("llama-vulkan/server.txt", "vulkan"), ("licenses/LICENSE-llama.cpp.txt", "MIT")), assets);
        ReleaseArchive nvidia = Cut(
            "baxy-nvidia.zip", Zip(("llama/server.txt", "cuda"), ("licenses/LICENSE-llama.cpp.txt", "MIT")), assets) with { GpuVendor = "10de", InstalledBytes = 50 };
        return (new ReleaseManifest("1.0.0", BaseUrl, 100, [common, nvidia]), assets, common.Bytes);
    }

    private static Installation Make(InstallPaths paths, HttpClient http, params ReleaseArchive[] archives) =>
        new(new ReleaseManifest("1.0.0", BaseUrl, 1, archives), paths, Fetcher(http));

    private static PartFetcher Fetcher(HttpClient http) => new(http, retryDelay: TimeSpan.Zero);

    private static string Hash(byte[] content) => Convert.ToHexStringLower(SHA256.HashData(content));

    private static ReleaseArchive Cut(string name, byte[] zip, Dictionary<string, byte[]> assets)
    {
        int half = zip.Length / 2;
        byte[][] pieces = [zip[..half], zip[half..]];
        List<ReleasePart> parts = [];
        for (int index = 0; index < pieces.Length; index++)
        {
            string file = $"{name}.{index:000}";
            assets[file] = pieces[index];
            parts.Add(new ReleasePart(file, pieces[index].Length, Hash(pieces[index])));
        }

        return new ReleaseArchive(name, parts);
    }

    private static byte[] Zip(params (string Name, string Text)[] entries)
    {
        using MemoryStream memory = new();
        using (ZipArchive zip = new(memory, ZipArchiveMode.Create, leaveOpen: true))
        {
            foreach ((string name, string text) in entries)
            {
                using StreamWriter writer = new(zip.CreateEntry(name).Open());
                writer.Write(text);
            }
        }

        return memory.ToArray();
    }

    /// <summary>Each request delivers a few more bytes and then the connection drops, as a bad line does.</summary>
    private sealed class Dropping(byte[] content, int bytesPerRequest) : HttpMessageHandler
    {
        internal int Requests { get; private set; }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Requests++;
            int start = (int)(request.Headers.Range?.Ranges.First().From ?? 0);
            int end = Math.Min(content.Length, start + bytesPerRequest);
            HttpResponseMessage response = new(start > 0 ? HttpStatusCode.PartialContent : HttpStatusCode.OK)
            {
                Content = new StreamContent(new CutStream(content[start..end], cut: end < content.Length)),
            };
            return Task.FromResult(response);
        }
    }

    private sealed class Refusing : HttpMessageHandler
    {
        internal int Requests { get; private set; }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Requests++;
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.NotFound));
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

    private sealed class Assets(IReadOnlyDictionary<string, byte[]> files) : HttpMessageHandler
    {
        internal long? FirstRangeStart { get; private set; }

        internal List<string> Requested { get; } = [];

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Requested.Add(request.RequestUri!.Segments[^1]);
            byte[] content = files[request.RequestUri!.Segments[^1]];
            long start = request.Headers.Range?.Ranges.First().From ?? 0;
            FirstRangeStart ??= start;
            HttpResponseMessage response = new(start > 0 ? HttpStatusCode.PartialContent : HttpStatusCode.OK)
            {
                Content = new ByteArrayContent(content[(int)start..]),
            };
            response.Content.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
            return Task.FromResult(response);
        }
    }
}
