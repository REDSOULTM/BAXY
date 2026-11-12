using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// INS-9: «keep your data» keeps more than what BAXY remembers. The uninstall screen names what stays and says how much
/// room it takes and where, so the choice is made knowing it.
/// </summary>
[TestFixture]
internal sealed class KeptDataTests
{
    private const string Folder = @"C:\Users\someone\AppData\Local\BAXY";
    private string directory = string.Empty;

    [SetUp]
    public void SetUp()
    {
        directory = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName());
        Directory.CreateDirectory(directory);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(directory, recursive: true);

    // Measured in a BAXY in use (2026-11-09): of 287 MB, 190 were screenshots and 22 a model's download; the keys of the
    // companies the person connected are there too.
    [TestCase("es", "modelos", "capturas de pantalla", "claves")]
    [TestCase("en", "models", "screenshots", "keys")]
    public void The_uninstall_screen_names_what_keeping_the_data_keeps(string language, string models, string captures, string keys)
    {
        Assert.That(Of(language).UninstallBody, Does.Contain(models).And.Contain(captures).And.Contain(keys));
        Assert.That(Of(language).UninstallBodyShared, Does.Contain(models).And.Contain(captures).And.Contain(keys));
    }

    [TestCase("es")]
    [TestCase("en")]
    public void The_uninstall_screen_says_how_much_the_data_takes_and_where(string language)
    {
        Texts texts = Of(language);

        Assert.Multiple(() =>
        {
            Assert.That(texts.UninstallBodyFor(rings: 0, 3_000_000_000, Folder), Does.Match("3[.,]0 GB").And.Contain(Folder));
            Assert.That(texts.UninstallBodyFor(rings: 0, 287_400_000, Folder), Does.Contain("287 MB").And.Contain(Folder));
            Assert.That(texts.UninstallBodyFor(rings: 0, 2_000, Folder), Does.Contain("1 MB"), "never «0 MB» for what is there");
            Assert.That(texts.UninstallBodyFor(rings: 2, 3_000_000_000, Folder), Does.Contain(texts.UninstallRings).And.Contain(Folder));
        });
    }

    // Before the folder is measured, and when there is none, the screen gives no figure.
    [TestCase("es")]
    [TestCase("en")]
    public void The_uninstall_screen_gives_no_figure_it_does_not_have(string language)
    {
        Texts texts = Of(language);

        Assert.That(texts.UninstallBodyFor(rings: 0, dataBytes: 0, Folder), Is.EqualTo(texts.UninstallBody));
    }

    [Test]
    public void The_data_folder_is_measured_whole()
    {
        WindowsPlaces places = new(
            Path.Combine(directory, "BAXY.lnk"), "unused", "unused", Path.Combine(directory, "data"), Path.Combine(directory, "other"));
        Assert.That(WindowsIntegration.DataBytes(places), Is.Zero, "no folder, nothing kept");
        Directory.CreateDirectory(Path.Combine(places.Data, "1", "captures"));
        File.WriteAllBytes(Path.Combine(places.Data, "1", "captures", "capture.bmp"), new byte[3000]);
        File.WriteAllBytes(Path.Combine(places.Data, "1", "memory.json"), new byte[200]);
        File.WriteAllBytes(Path.Combine(places.Data, "model.gguf"), new byte[50]);

        Assert.That(WindowsIntegration.DataBytes(places), Is.EqualTo(3250));
    }

    private static Texts Of(string language) => language == "es" ? Texts.Spanish : Texts.English;
}
