using System.IO;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// LEG1 §5 (2026-11-09): a copy from Steam or itch.io may not register to start with Windows (only the installed copy and the
/// owner's checkout do: WindowsAutostartRegistration), and Settings called it a development copy that opens with
/// run_renew.cmd. The packager's distribution.json beside app\ says which store's copy it is.
/// </summary>
[TestFixture]
public sealed class AutostartStoreCopyTests
{
    [TestCase("steam", "steam_copy")]
    [TestCase("itch", "itch_copy")]
    [TestCase("github", "not_this_copy")]
    [TestCase(null, "not_this_copy")]
    public void ACopyThatMayNotStartWithWindowsSaysWhoseItIs(string? channel, string blocked)
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-autostart-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(root, "app"));
        try
        {
            if (channel is not null)
            {
                File.WriteAllText(Path.Combine(root, "distribution.json"),
                    "{\"schema\":\"baxy.distribution.v1\",\"channel\":\"" + channel + "\"}");
            }

            Assert.Multiple(() =>
            {
                Assert.That(FieldProductChannel.AutostartBlocked(null, Path.Combine(root, "app")), Is.EqualTo(blocked));
                Assert.That(FieldProductChannel.AutostartBlocked(true, Path.Combine(root, "app")), Is.Null, "it may: nothing blocks it");
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
