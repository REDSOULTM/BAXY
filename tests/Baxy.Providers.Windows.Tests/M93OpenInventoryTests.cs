using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// M93 (DEV-D v3u, HEAD 30861483). D-s119 «Abrir la app de photos.» and D-w11-t5 «¿Me abres el Spotify?»: the mission
/// journal of the run (window-v3u-devD/journal/missions.jsonl) has app.open failed with «inventory_failed» for both
/// packaged apps, in about a second (shell trace t119: core.call 339341 → 340449 ms), while «Calculadora» (its own
/// provider) was reused and Google Keep was «app_not_found». In v3r the same Fotos window was reused. One visible process
/// whose package identity could not be read threw out of the whole open inventory.
/// </summary>
[TestFixture]
public sealed class M93OpenInventoryTests
{
    private static string? Unreadable() =>
        throw new ApplicationInventoryException("The visible process application identity could not be opened.");

    [Test]
    public void AnUnreadableProcessIsJudgedByItsNameWhenOpening()
    {
        bool kept = WindowsInstalledApplicationPlatform.TryReadPackagedIdentity(
            Unreadable, strongIdentityOnly: false, out string? applicationId);

        Assert.Multiple(() =>
        {
            Assert.That(kept, Is.True);
            Assert.That(applicationId, Is.Null);
        });
    }

    [Test]
    public void TheStrongInventoryStillSkipsAnUnreadableProcess()
    {
        bool kept = WindowsInstalledApplicationPlatform.TryReadPackagedIdentity(
            Unreadable, strongIdentityOnly: true, out string? applicationId);

        Assert.Multiple(() =>
        {
            Assert.That(kept, Is.False);
            Assert.That(applicationId, Is.Null);
        });
    }

    [Test]
    public void AReadableIdentityIsKeptInBothInventories()
    {
        const string photos = "Microsoft.Windows.Photos_8wekyb3d8bbwe!App";
        foreach (bool strong in new[] { false, true })
        {
            bool kept = WindowsInstalledApplicationPlatform.TryReadPackagedIdentity(
                () => photos, strong, out string? applicationId);
            Assert.Multiple(() =>
            {
                Assert.That(kept, Is.True);
                Assert.That(applicationId, Is.EqualTo(photos));
            });
        }
    }
}
