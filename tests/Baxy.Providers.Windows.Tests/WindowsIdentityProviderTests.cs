using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsIdentityProviderTests
{
    [Test]
    public async Task IdentityRequiresTwoIdenticalNonemptyObservations()
    {
        var expected = new WindowsIdentitySnapshot("DESKTOP", "emma", "DESKTOP\\emma");
        var probe = new FakeIdentityProbe(expected, expected);
        var provider = new WindowsIdentityProvider(probe);

        WindowsIdentitySnapshot? result = await provider.ReadVerifiedAsync(
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.EqualTo(expected));
            Assert.That(probe.Reads, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task IdentityRejectsAChangedSecondObservation()
    {
        var provider = new WindowsIdentityProvider(new FakeIdentityProbe(
            new WindowsIdentitySnapshot("DESKTOP", "emma", "DESKTOP\\emma"),
            new WindowsIdentitySnapshot("DESKTOP", "other", "DESKTOP\\other")));

        Assert.That(
            await provider.ReadVerifiedAsync(CancellationToken.None),
            Is.Null);
    }

    private sealed class FakeIdentityProbe(params WindowsIdentitySnapshot[] snapshots)
        : IWindowsIdentityProbe
    {
        private readonly Queue<WindowsIdentitySnapshot> _snapshots = new(snapshots);
        public int Reads { get; private set; }

        public WindowsIdentitySnapshot Read()
        {
            Reads++;
            return _snapshots.Dequeue();
        }
    }
}
