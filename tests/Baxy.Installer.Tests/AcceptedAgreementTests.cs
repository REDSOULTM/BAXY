using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// PRV2 (decisión A5, 2026-11-10; INS-10): an update installed a changed agreement without showing it. The window asks
/// for it when the agreement the installation accepted is not this one, or is not known; the same one is not asked
/// again. Every place is a temporary folder of the test's own.
/// </summary>
[TestFixture]
internal sealed class AcceptedAgreementTests
{
    private string directory = string.Empty;
    private InstallPaths paths = null!;

    [SetUp]
    public void SetUp()
    {
        directory = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName());
        paths = new InstallPaths(Path.Combine(directory, "BAXY-App"));
        Directory.CreateDirectory(Path.GetDirectoryName(paths.App)!);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(directory, recursive: true);

    [Test]
    public void A_first_install_is_not_asked_again_it_says_so_on_its_greeting()
    {
        Assert.That(AcceptedAgreement.MustBeAccepted(paths, AcceptedAgreement.Read(paths)), Is.False);
    }

    [Test]
    public void An_installation_that_recorded_nothing_is_asked_once()
    {
        File.WriteAllText(paths.App, "the app");  // every BAXY installed before this version

        Assert.That(AcceptedAgreement.Read(paths), Is.Null);
        Assert.That(AcceptedAgreement.MustBeAccepted(paths, AcceptedAgreement.Read(paths)), Is.True);

        AcceptedAgreement.Write(paths, AcceptedAgreement.Current);
        Assert.That(AcceptedAgreement.MustBeAccepted(paths, AcceptedAgreement.Read(paths)), Is.False, "asked again");
    }

    [Test]
    public void A_changed_agreement_is_asked_and_the_same_one_is_not()
    {
        File.WriteAllText(paths.App, "the app");
        string earlier = AcceptedAgreement.Of(
            WindowsIntegration.LicenseText("es") + "\nUna cláusula nueva.", WindowsIntegration.LicenseText("en"));
        AcceptedAgreement.Write(paths, earlier);

        Assert.That(AcceptedAgreement.Read(paths), Is.EqualTo(earlier));
        Assert.That(AcceptedAgreement.MustBeAccepted(paths, earlier), Is.True);
        Assert.That(AcceptedAgreement.MustBeAccepted(paths, AcceptedAgreement.Current), Is.False);
    }

    [Test]
    public void The_fingerprint_is_the_text_in_both_languages_not_its_line_endings()
    {
        string spanish = WindowsIntegration.LicenseText("es").Replace("\r\n", "\n", StringComparison.Ordinal);
        string english = WindowsIntegration.LicenseText("en").Replace("\r\n", "\n", StringComparison.Ordinal);

        Assert.Multiple(() =>
        {
            Assert.That(AcceptedAgreement.Of(spanish.Replace("\n", "\r\n", StringComparison.Ordinal), english),
                Is.EqualTo(AcceptedAgreement.Current));
            Assert.That(AcceptedAgreement.Of(spanish, english + " "), Is.Not.EqualTo(AcceptedAgreement.Current));
            Assert.That(AcceptedAgreement.Of(english, spanish), Is.Not.EqualTo(AcceptedAgreement.Current));
            Assert.That(AcceptedAgreement.Current, Does.Match("^[0-9a-f]{64}$"));
        });
    }

    [TestCase("")]
    [TestCase("no es una huella")]
    [TestCase("ABCDEF")]
    public void A_record_that_is_not_a_fingerprint_counts_as_not_known(string content)
    {
        File.WriteAllText(paths.App, "the app");
        Directory.CreateDirectory(Path.Combine(paths.Root, "licenses"));
        File.WriteAllText(Path.Combine(paths.Root, "licenses", AcceptedAgreement.FileName), content);

        Assert.That(AcceptedAgreement.Read(paths), Is.Null);
        Assert.That(AcceptedAgreement.MustBeAccepted(paths, null), Is.True);
    }

    [TestCase("es", "No muestra el acuerdo de licencia", "Si el acuerdo de licencia no es el que aceptaste")]
    [TestCase("en", "It does not show the license agreement", "If the license agreement is not the one you accepted")]
    public void The_help_says_what_quiet_and_update_do_with_the_agreement(string language, string quiet, string update)
    {
        string help = CommandLine.HelpText(language, @"C:\Users\someone\AppData\Local\Programs\BAXY-App");

        Assert.That(help, Does.Contain(quiet));
        Assert.That(help, Does.Contain(update));
        Assert.That(help, Does.Not.Contain("sin preguntar de\n"));
        Assert.That(help, Does.Not.Contain("without asking again"));
    }
}
