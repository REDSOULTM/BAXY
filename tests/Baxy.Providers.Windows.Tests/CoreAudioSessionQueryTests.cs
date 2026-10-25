using Baxy.Providers.Windows.Audio;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Revisión nb-q-apps2: a session that gives its control interface but not its volume interface no longer keeps the
/// control's COM reference. The QueryInterface and Release calls are fakes; no audio object is touched.
/// </summary>
[TestFixture]
public sealed class CoreAudioSessionQueryTests
{
    [Test]
    public void AControlWithoutAVolumeIsReleased()
    {
        var released = new List<nint>();
        int calls = 0;

        bool both = WindowsCoreAudioPlatform.QuerySessionInterfaces(
            0x1000,
            (nint _, in Guid _, out nint pointer) =>
            {
                calls++;
                pointer = calls == 1 ? 0x2000 : 0;
                return calls == 1 ? 0 : unchecked((int)0x80004002); // E_NOINTERFACE for the volume
            },
            released.Add,
            out nint control,
            out nint volume);

        Assert.Multiple(() =>
        {
            Assert.That(both, Is.False);
            Assert.That(released, Is.EqualTo(new nint[] { 0x2000 }));
            Assert.That(control, Is.EqualTo(nint.Zero));
            Assert.That(volume, Is.EqualTo(nint.Zero));
        });
    }

    [Test]
    public void BothInterfacesAreKeptAndNothingIsReleased()
    {
        var released = new List<nint>();
        int calls = 0;

        bool both = WindowsCoreAudioPlatform.QuerySessionInterfaces(
            0x1000,
            (nint _, in Guid _, out nint pointer) =>
            {
                pointer = ++calls == 1 ? 0x2000 : 0x3000;
                return 0;
            },
            released.Add,
            out nint control,
            out nint volume);

        Assert.Multiple(() =>
        {
            Assert.That(both, Is.True);
            Assert.That(released, Is.Empty);
            Assert.That(control, Is.EqualTo((nint)0x2000));
            Assert.That(volume, Is.EqualTo((nint)0x3000));
        });
    }
}
