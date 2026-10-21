using Baxy.App;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// The heartbeat's «llamada» (src/Baxy.App/MicrophoneUse.cs, linked here: the App has no test project). Uso real
/// 2026-10-21: old Discord folders and a game, months old, were read as holding the microphone now.
/// </summary>
[TestFixture]
public sealed class MicrophoneUseTests
{
    private static readonly long Boot = new DateTime(2026, 10, 21, 17, 0, 0, DateTimeKind.Utc).ToFileTimeUtc();
    private static readonly long April = new DateTime(2026, 4, 30, 5, 31, 0, DateTimeKind.Utc).ToFileTimeUtc();
    private static readonly long Now = new DateTime(2026, 10, 21, 17, 25, 0, DateTimeKind.Utc).ToFileTimeUtc();
    private const string Old = @"C:\Users\x\AppData\Local\Discord\app-1.0.9235\Discord.exe";
    private const string Current = @"C:\Users\x\AppData\Local\Discord\app-1.0.9264\Discord.exe";

    private static bool Running(string path) => string.Equals(path, Current, StringComparison.OrdinalIgnoreCase);

    [Test]
    public void AUseStartedBeforeThisBootIsNotACall() =>
        Assert.That(MicrophoneUse.StillHeld(April, Boot, Current, Running), Is.False);

    [Test]
    public void AUseOfAnExecutableThatNoLongerRunsIsNotACall() =>
        Assert.That(MicrophoneUse.StillHeld(Now, Boot, Old, Running), Is.False);

    [Test]
    public void AUseSinceThisBootOfARunningExecutableIsACall() =>
        Assert.That(MicrophoneUse.StillHeld(Now, Boot, Current, Running), Is.True);

    [Test]
    public void APackagedAppsUseSinceThisBootIsACall() =>
        Assert.That(MicrophoneUse.StillHeld(Now, Boot, null, _ => false), Is.True);
}
