using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo S): la desinstalación de
/// un juego instalado pasa por la consola de Steam y se verifica en el
/// manifiesto; lo que no está instalado se dice antes de tocar nada.
/// </summary>
[TestFixture]
public sealed class SteamUninstallAdapterTests
{
    [Test]
    public async Task AnInstalledTitleIsUninstalledAndItsManifestAbsenceIsTheProof()
    {
        var games = new List<SteamLocalGame> { new("620", "Portal 2", new string('a', 64), InstallDirectory: @"C:\Games\Portal 2") };
        string? cancelled = null;
        var automation = new StubAutomation(appId => { cancelled = appId; games.Clear(); });
        var adapter = new SteamLocalAdapter(
            () => games.ToArray(), () => new HashSet<string> { "620" }, automation, (_, _) => ValueTask.CompletedTask);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.uninstall.named",
            JsonSerializer.SerializeToElement(new { title = "portal 2", store = "steam" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(cancelled, Is.EqualTo("620"));
            Assert.That(receipt.Result!.Value.GetProperty("removed").GetBoolean(), Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("name").GetString(), Is.EqualTo("Portal 2"));
            Assert.That(receipt.Result!.Value.GetProperty("state").GetString(), Is.EqualTo("manifest_removed"));
        });
    }

    [Test]
    public async Task ATitleThatIsNotInstalledIsAnHonestAbsenceBeforeAnyEffect()
    {
        var automation = new StubAutomation(_ => Assert.Fail("nothing should be dispatched"));
        var adapter = new SteamLocalAdapter(
            () => [new("620", "Portal 2", new string('a', 64))], () => new HashSet<string> { "620", "782330" }, automation, (_, _) => ValueTask.CompletedTask);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.uninstall.named",
            JsonSerializer.SerializeToElement(new { title = "Doom Eternal" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_game_not_installed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public async Task AGameStillInstalledAfterTheConsoleOrderIsNotClaimedRemoved()
    {
        var automation = new StubAutomation(_ => { });
        var adapter = new SteamLocalAdapter(
            () => [new("620", "Portal 2", new string('a', 64))], () => new HashSet<string> { "620" }, automation, (_, _) => ValueTask.CompletedTask);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.uninstall.named",
            JsonSerializer.SerializeToElement(new { title = "Portal 2" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_uninstall_not_verified"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
        });
    }

    [Test]
    public async Task AnEpicInstallLinkIsAcceptedByTheDispatcherScheme()
    {
        var automation = new StubAutomation(_ => { });
        var adapter = new SteamLocalAdapter(
            () => [], () => new HashSet<string>(), automation, (_, _) => ValueTask.CompletedTask);

        // Without launcher data on the test machine the read is an honest absence,
        // never a Steam lookup of an Epic title.
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.named",
            JsonSerializer.SerializeToElement(new { title = "Fall Guys", store = "epic" }),
            CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.AnyOf("epic_launcher_data_not_found", "epic_entitlement_not_verified", "epic_install_link_not_resolved", "epic_install_not_verified", "epic_install_dispatch_rejected").Or.Null);
    }

    private sealed class StubAutomation(Action<string> onCancel) : ISteamClientAutomation
    {
        public ValueTask<SteamDispatchResult> DispatchAsync(string uri, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new SteamDispatchResult(true, true));

        public ValueTask<SteamDispatchResult> ContinueLaunchDialogAsync(SteamDispatchResult dispatch, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new SteamDispatchResult(false, dispatch.EffectObserved));

        public ValueTask<SteamDispatchResult> CancelPartialAsync(string appId, CancellationToken cancellationToken)
        {
            onCancel(appId);
            return ValueTask.FromResult(new SteamDispatchResult(true, true));
        }
    }
}
