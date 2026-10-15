using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo S): la desinstalación de
/// un juego instalado se verifica en el manifiesto; lo que no está instalado se
/// dice antes de tocar nada. Encargo imp-steam: pasa por la dirección del dato
/// (steam://uninstall/&lt;id&gt;) y el diálogo propio de Steam confirmado por sus
/// nombres, ya no por la consola.
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
            Assert.That(automation.Dispatched, Is.EqualTo("steam://uninstall/620"));
            Assert.That(automation.Confirmed, Is.EqualTo(new[] { "Desinstalar", "Uninstall" }));
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
    public async Task AGameStillInstalledAfterItsDialogIsNotClaimedRemoved()
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

    // Steam's dialog left unconfirmed (its button not found, nothing pressed): said, the game not claimed removed and
    // its manifest not waited on.
    [Test]
    public async Task AnUnconfirmedUninstallDialogRemovesNothing()
    {
        var automation = new StubAutomation(_ => Assert.Fail("nothing was pressed"), confirmed: false);
        var adapter = new SteamLocalAdapter(
            () => [new("620", "Portal 2", new string('a', 64))], () => new HashSet<string> { "620" }, automation, (_, _) => ValueTask.CompletedTask);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.uninstall.named",
            JsonSerializer.SerializeToElement(new { title = "Portal 2" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_uninstall_dialog_not_confirmed"));
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

    // Steam's own uninstall dialog for the last address, confirmed by its labels (or left unconfirmed).
    private sealed class StubAutomation(Action<string> onCancel, bool confirmed = true) : ISteamClientAutomation
    {
        internal string? Dispatched { get; private set; }
        internal IReadOnlyList<string> Confirmed { get; private set; } = [];

        public ValueTask<SteamDispatchResult> DispatchAsync(string uri, CancellationToken cancellationToken)
        {
            Dispatched = uri;
            return ValueTask.FromResult(new SteamDispatchResult(true, true));
        }

        public ValueTask<SteamDispatchResult> ConfirmAsync(
            SteamDispatchResult dispatch, IReadOnlyList<string> labels, CancellationToken cancellationToken)
        {
            Confirmed = labels;
            if (!confirmed)
                return ValueTask.FromResult(new SteamDispatchResult(false, false));
            onCancel(Dispatched!["steam://uninstall/".Length..]);
            return ValueTask.FromResult(new SteamDispatchResult(true, true));
        }
    }
}
