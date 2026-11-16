using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// ARR3 (AMD8 §3, 15-11-2026): the installer's window spoke its agreement line on a friend's machine whose BAXY had its
/// voice off. The window keeps quiet for a BAXY whose voice the person turned off, as the update without a window does;
/// a new installation, with no settings yet, speaks as before.
/// </summary>
[TestFixture]
internal sealed class WindowVoiceTests
{
    private string directory = string.Empty;
    private string profile = string.Empty;
    private string usual = string.Empty;

    [SetUp]
    public void SetUp()
    {
        directory = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName());
        profile = Path.Combine(directory, "BAXY", "2");
        usual = Path.Combine(directory, "BAXY", "1");
        Directory.CreateDirectory(Path.Combine(profile, "updates"));
        Directory.CreateDirectory(usual);
        Directory.CreateDirectory(Path.Combine(directory, "Downloads"));
    }

    [TearDown]
    public void TearDown() => Directory.Delete(directory, recursive: true);

    [Test]
    public void The_window_an_update_opens_keeps_quiet_for_a_baxy_whose_voice_is_off()
    {
        File.WriteAllText(Path.Combine(profile, "field-settings.v1.json"), "{\"voiceMuted\":true}");

        Assert.That(Program.MaySpeak(noVoice: false, Path.Combine(profile, "updates"), usual), Is.False);
    }

    [Test]
    public void An_installer_run_by_hand_or_the_uninstaller_keeps_quiet_for_the_usual_baxy_whose_voice_is_off()
    {
        File.WriteAllText(Path.Combine(usual, "field-settings.v1.json"), "{\"voiceMuted\":true,\"web\":true}");

        Assert.Multiple(() =>
        {
            Assert.That(Program.MaySpeak(noVoice: false, Path.Combine(directory, "Downloads"), usual), Is.False);
            Assert.That(Program.MaySpeak(noVoice: false, directory, usual), Is.False, "a folder with nothing beside it");
        });
    }

    [Test]
    public void The_baxy_the_installer_runs_for_decides_over_the_usual_one()
    {
        File.WriteAllText(Path.Combine(usual, "field-settings.v1.json"), "{\"voiceMuted\":true}");
        File.WriteAllText(Path.Combine(profile, "field-settings.v1.json"), "{\"voiceMuted\":false}");

        Assert.That(Program.MaySpeak(noVoice: false, Path.Combine(profile, "updates"), usual), Is.True);
    }

    [Test]
    public void A_new_installation_with_no_settings_yet_speaks_as_before()
    {
        Assert.Multiple(() =>
        {
            Assert.That(Program.MaySpeak(noVoice: false, Path.Combine(directory, "Downloads"), usual), Is.True);
            Assert.That(Program.MaySpeak(noVoice: false, Path.Combine(profile, "updates"), usual), Is.True);
            Assert.That(Program.MaySpeak(noVoice: true, Path.Combine(directory, "Downloads"), usual), Is.False, "--no-voice");
        });

        File.WriteAllText(Path.Combine(usual, "field-settings.v1.json"), "{\"web\":true}");
        Assert.That(Program.MaySpeak(noVoice: false, Path.Combine(directory, "Downloads"), usual), Is.True, "nothing said of the voice");
    }
}
