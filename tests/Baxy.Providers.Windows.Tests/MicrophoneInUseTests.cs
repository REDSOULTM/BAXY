using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// v3 r22 revisión (bloqueante 3, «cierra Teams» en plena reunión): whether an application captures the microphone
/// is read from the record Windows keeps for its own microphone-in-use indicator (CapabilityAccessManager
/// ConsentStore\microphone): a packaged application under its package family, any other under NonPackaged with its
/// path written with '#'. A start with no stop is a capture still open. The registry is a fake here.
/// </summary>
[TestFixture]
public sealed class MicrophoneInUseTests
{
    private const string MeetingPath = @"C:\Users\person\AppData\Local\Meeting\app\Meeting.exe";
    private const string MeetingKey = @"NonPackaged\C:#Users#person#AppData#Local#Meeting#app#Meeting.exe";

    [Test]
    public void TheKeysNameThePackageFamilyTheCatalogFamilyAndTheExecutablePath()
    {
        IReadOnlyList<string> keys = MicrophoneInUse.KeysFor(
            "Vendor.Meeting_abc123!App", MeetingPath, "Vendor.Chat_def456");

        Assert.That(keys, Is.EqualTo(new[] { "Vendor.Chat_def456", "Vendor.Meeting_abc123", MeetingKey }));
    }

    [Test]
    public void ARelativeOrMissingIdentityNamesNoKey() =>
        Assert.That(MicrophoneInUse.KeysFor(null, "Meeting.exe", null), Is.Empty);

    [Test]
    public void AStartWithNoStopIsACaptureInProgress() =>
        Assert.That(MicrophoneInUse.Capturing([MeetingKey], Store((MeetingKey, 133_000_000_000_000_000, 0))),
            Is.True);

    [Test]
    public void AStartWithNoStopValueIsACaptureInProgress() =>
        Assert.That(MicrophoneInUse.Capturing([MeetingKey], Store((MeetingKey, 133_000_000_000_000_000, null))),
            Is.True);

    [Test]
    public void ACaptureThatStoppedIsNotInProgress() =>
        // Contracaso: the last call ended (a stop recorded after the start).
        Assert.That(MicrophoneInUse.Capturing(
                [MeetingKey], Store((MeetingKey, 133_000_000_000_000_000, 133_000_000_000_000_100))),
            Is.False);

    [Test]
    public void AnApplicationThatNeverUsedTheMicrophoneIsNotCapturing() =>
        // Contracaso: no key, or a key with no recorded use.
        Assert.Multiple(() =>
        {
            Assert.That(MicrophoneInUse.Capturing([MeetingKey], Store()), Is.False);
            Assert.That(MicrophoneInUse.Capturing([MeetingKey], Store((MeetingKey, null, null))), Is.False);
        });

    [Test]
    public void AnotherApplicationsCaptureDoesNotCount() =>
        Assert.That(MicrophoneInUse.Capturing(
                [MeetingKey], Store((@"NonPackaged\C:#Other#Other.exe", 133_000_000_000_000_000, 0))),
            Is.False);

    private static Func<string, (long? Start, long? Stop)?> Store(
        params (string Key, long? Start, long? Stop)[] entries) =>
        key => entries.Where(entry => string.Equals(entry.Key, key, StringComparison.OrdinalIgnoreCase))
            .Select(static entry => ((long? Start, long? Stop)?)(entry.Start, entry.Stop))
            .FirstOrDefault();
}
