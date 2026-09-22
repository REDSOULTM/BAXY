using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo G): instalar y desinstalar
/// software es cosa del gestor de paquetes de Windows; las salidas de winget
/// grabadas en este PC (español) alimentan un corredor falso.
/// </summary>
[TestFixture]
public sealed class WingetPackageAdapterTests
{
    private const string SearchSpotify = """
        Nombre                       Id                             Versión             Coincidencia            Origen
        ---------------------------------------------------------------------------------------------------------------
        Spotify                      Spotify.Spotify                1.3.1.234.g59d6bf59 ProductCode: spotify    winget
        Toastify                     Aleab.Toastify                 1.11.2              Tag: spotify            winget
        Spotube                      KRTirtho.Spotube               5.1.2               Tag: spotify            winget
        """;

    private const string SearchPhotoshop = """
        Nombre                                            Id                             Versión    Coincidencia   Origen
        --------------------------------------------------------------------------------------------------------------------
        Mirror for Photoshop Server                       Hex.MirrorForPhotoshopServer   2025.12.66 Tag: photoshop winget
        蓝湖                                              JinweiZhiguang.Lanhu.Photoshop 2.417.0    Tag: photoshop winget
        Adobe Photoshop                                   XPFD4T9N395QN6                 Unknown                   msstore
        Adobe Express Photos (formerly Photoshop Express) 9WZDNCRFJ27N                   Unknown                   msstore
        """;

    private const string ListDiscord = """
        Nombre  Id             Versión  Origen
        ---------------------------------------
        Discord XPDC2RH70K22MN 1.0.9258 winget
        """;

    private const string ShowSpotify = """
        Encontrado Spotify [Spotify.Spotify]
        Versión: 1.3.1.234.g59d6bf59
        Editor: Spotify AB
        """;

    private const string Nothing = "No se encontró ningún paquete que coincida con los criterios de entrada.";

    [Test]
    public void TheAlignedTableIsReadByItsIdColumn()
    {
        List<WingetPackageAdapter.PackageRow> rows = WingetPackageAdapter.ParseTable(SearchPhotoshop);

        Assert.Multiple(() =>
        {
            Assert.That(rows, Has.Count.EqualTo(4));
            Assert.That(rows[0].Name, Is.EqualTo("Mirror for Photoshop Server"));
            Assert.That(rows[0].Id, Is.EqualTo("Hex.MirrorForPhotoshopServer"));
            Assert.That(rows[0].Version, Is.EqualTo("2025.12.66"));
            Assert.That(rows[0].Source, Is.EqualTo("winget"));
            Assert.That(rows[2].Name, Is.EqualTo("Adobe Photoshop"));
            Assert.That(rows[2].Id, Is.EqualTo("XPFD4T9N395QN6"));
            Assert.That(rows[2].Source, Is.EqualTo("msstore"));
        });
    }

    // WINGET2085 «instala 7-Zip»: a version inside the display name is not the id.
    [Test]
    public void WingetTableReadsTheIdFromItsColumnNotFromANameVersion()
    {
        const string output =
            "Nombre                    Id        Versión    Origen\r\n"
            + "------------------------------------------------------\r\n"
            + "7-Zip 26.03 (x64 edition) 7zip.7zip 26.03.00.0 winget\r\n";

        List<WingetPackageAdapter.PackageRow> rows = WingetPackageAdapter.ParseTable(output);

        Assert.That(rows, Has.Count.EqualTo(1));
        Assert.Multiple(() =>
        {
            Assert.That(rows[0].Id, Is.EqualTo("7zip.7zip"));
            Assert.That(rows[0].Name, Is.EqualTo("7-Zip 26.03 (x64 edition)"));
        });
    }

    [Test]
    public async Task ANameWithOneExactMatchIsPreparedWithItsIdAndRecorded()
    {
        string root = NewRoot();
        var runner = new ScriptedRunner(args =>
            args[0] == "search" ? (0, SearchSpotify)
            : args[0] == "list" ? (1, Nothing)
            : (1, string.Empty));
        var adapter = new WingetPackageAdapter(runner, root, _ => null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "package.install.prepare",
            JsonSerializer.SerializeToElement(new { packageId = "spotify" }),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True);
        JsonElement result = receipt.Result!.Value;
        string confirmationId = result.GetProperty("confirmationId").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("packageId").GetString(), Is.EqualTo("Spotify.Spotify"));
            Assert.That(result.GetProperty("resolvedVersion").GetString(), Is.EqualTo("1.3.1.234.g59d6bf59"));
            Assert.That(result.GetProperty("source").GetString(), Is.EqualTo("winget_search_unique_name"));
            Assert.That(result.GetProperty("installed").GetBoolean(), Is.False);
            Assert.That(confirmationId, Does.StartWith("winget_"));
            Assert.That(File.Exists(Path.Combine(root, confirmationId + ".json")), Is.True);
            Assert.That(runner.Calls.Select(call => call[0]), Is.EqualTo(new[] { "search", "list" }));
        });
    }

    [Test]
    public async Task AnExactIdIsPreparedByShowWithoutSearching()
    {
        var runner = new ScriptedRunner(args =>
            args[0] == "show" ? (0, ShowSpotify)
            : args[0] == "list" ? (0, "Nombre  Id  Versión  Origen\n----\nSpotify Spotify.Spotify 1.3.0.277 winget")
            : (1, string.Empty));
        var adapter = new WingetPackageAdapter(runner, NewRoot(), _ => null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "package.install.prepare",
            JsonSerializer.SerializeToElement(new { packageId = "Spotify.Spotify" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("installed").GetBoolean(), Is.True);
            Assert.That(receipt.Result!.Value.TryGetProperty("confirmationId", out _), Is.False);
            Assert.That(runner.Calls[0][0], Is.EqualTo("show"));
        });
    }

    [Test]
    public async Task ANameWingetDoesNotOfferExactlyIsNotResolved()
    {
        var runner = new ScriptedRunner(args => args[0] == "search" ? (0, SearchPhotoshop) : (1, Nothing));
        var adapter = new WingetPackageAdapter(runner, NewRoot(), _ => null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "package.install.prepare",
            JsonSerializer.SerializeToElement(new { packageId = "Photoshop" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("winget_package_not_resolved"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public async Task TheCommitInstallsThePreparedIdAndVerifiesItInTheList()
    {
        string root = NewRoot();
        var runner = new ScriptedRunner(args =>
            args[0] == "search" ? (0, SearchSpotify)
            : args[0] == "list" && args.Contains("--exact") ? (1, Nothing)
            : (1, string.Empty));
        List<IReadOnlyList<string>> launched = [];
        var adapter = new WingetPackageAdapter(runner, root, args => { launched.Add(args); return 999_999; });
        ExternalCapabilityReceipt prepared = await adapter.InvokeAsync(
            "package.install.prepare",
            JsonSerializer.SerializeToElement(new { packageId = "spotify" }),
            CancellationToken.None);
        string confirmationId = prepared.Result!.Value.GetProperty("confirmationId").GetString()!;
        runner.Script = args => args[0] == "list" ? (0, ListDiscord.Replace("Discord XPDC2RH70K22MN 1.0.9258", "Spotify Spotify.Spotify 1.3.1.234", StringComparison.Ordinal)) : (1, string.Empty);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "package.install.commit",
            JsonSerializer.SerializeToElement(new { confirmationId }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(launched, Has.Count.EqualTo(1));
            Assert.That(launched[0], Is.EqualTo(new[]
            {
                "install", "--id", "Spotify.Spotify", "--exact", "--silent",
                "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity",
            }));
            Assert.That(receipt.Result!.Value.GetProperty("installed").GetBoolean(), Is.True);
            Assert.That(File.Exists(Path.Combine(root, confirmationId + ".json")), Is.False);
        });
    }

    [Test]
    public async Task ACommitWithoutItsPreparationTouchesNothing()
    {
        var runner = new ScriptedRunner(_ => (1, string.Empty));
        List<IReadOnlyList<string>> launched = [];
        var adapter = new WingetPackageAdapter(runner, NewRoot(), args => { launched.Add(args); return 1; });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "package.install.commit",
            JsonSerializer.SerializeToElement(new { confirmationId = "winget_000000000000000000000000" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("winget_confirmation_not_prepared"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(launched, Is.Empty);
        });
    }

    [Test]
    public async Task AnInstalledNameIsUninstalledByItsIdAndVerifiedAbsent()
    {
        bool removed = false;
        var runner = new ScriptedRunner(args =>
            args[0] == "list" && !args.Contains("--exact") ? (0, ListDiscord)
            : args[0] == "list" ? (removed ? (1, Nothing) : (0, ListDiscord))
            : (1, string.Empty));
        List<IReadOnlyList<string>> launched = [];
        var adapter = new WingetPackageAdapter(runner, NewRoot(), args => { launched.Add(args); removed = true; return 999_999; });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "package.uninstall",
            JsonSerializer.SerializeToElement(new { packageId = "discord" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(launched[0], Is.EqualTo(new[]
            {
                "uninstall", "--id", "XPDC2RH70K22MN", "--exact", "--silent",
                "--accept-source-agreements", "--disable-interactivity",
            }));
            Assert.That(receipt.Result!.Value.GetProperty("removed").GetBoolean(), Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("name").GetString(), Is.EqualTo("Discord"));
        });
    }

    [Test]
    public async Task UninstallingWhatIsNotInstalledIsAnHonestAbsenceBeforeAnyEffect()
    {
        var runner = new ScriptedRunner(_ => (1, Nothing));
        List<IReadOnlyList<string>> launched = [];
        var adapter = new WingetPackageAdapter(runner, NewRoot(), args => { launched.Add(args); return 1; });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "package.uninstall",
            JsonSerializer.SerializeToElement(new { packageId = "Photoshop" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("winget_package_not_installed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(launched, Is.Empty);
        });
    }

    [Test]
    public async Task MissingWingetIsAStableFailure()
    {
        var runner = new ScriptedRunner(_ => throw new System.ComponentModel.Win32Exception(2, "winget.exe was not found"));
        var adapter = new WingetPackageAdapter(runner, NewRoot(), _ => null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "package.install.prepare",
            JsonSerializer.SerializeToElement(new { packageId = "Microsoft.PowerToys" }),
            CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("winget_adapter_unavailable"));
    }

    private static string NewRoot()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-winget-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        return root;
    }

    private sealed class ScriptedRunner(Func<IReadOnlyList<string>, (int ExitCode, string Output)> script)
        : IExternalProcessRunner
    {
        internal Func<IReadOnlyList<string>, (int ExitCode, string Output)> Script { get; set; } = script;

        internal List<IReadOnlyList<string>> Calls { get; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable,
            IReadOnlyList<string> arguments,
            TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            Calls.Add(arguments);
            (int exitCode, string output) = Script(arguments);
            return ValueTask.FromResult(new ExternalProcessResult(exitCode, output, string.Empty));
        }
    }
}
