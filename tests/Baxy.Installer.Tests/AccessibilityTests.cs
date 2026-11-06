using System.Globalization;
using System.Reflection;
using System.Text.Json;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

[TestFixture]
internal sealed class AccessibilityTests
{
    private static readonly string[] LinesInBothLanguages = ["es", "en"];

    private static IEnumerable<Palette> Palettes() => [Theme.Dark, Theme.Light, Theme.HighContrast];

    [TestCaseSource(nameof(Palettes))]
    public void Text_and_controls_pass_wcag_on_every_palette(Palette palette)
    {
        Assert.Multiple(() =>
        {
            Assert.That(Contrast(palette.Text, palette.Background), Is.GreaterThanOrEqualTo(4.5), "text");
            Assert.That(Contrast(palette.Second, palette.Background), Is.GreaterThanOrEqualTo(4.5), "second");
            Assert.That(Contrast(palette.Ok, palette.Background), Is.GreaterThanOrEqualTo(4.5), "done");
            Assert.That(Contrast(palette.Now, palette.Background), Is.GreaterThanOrEqualTo(4.5), "now");
            Assert.That(Contrast(palette.OnPrimary, palette.Primary), Is.GreaterThanOrEqualTo(4.5), "primary");
            Assert.That(Contrast(palette.OnPrimary, palette.PrimaryHover), Is.GreaterThanOrEqualTo(4.5), "primary hover");
            Assert.That(Contrast(palette.Text, palette.QuietHover), Is.GreaterThanOrEqualTo(4.5), "quiet hover");
            Assert.That(Contrast(palette.PanelText, palette.Panel), Is.GreaterThanOrEqualTo(4.5), "panel");
            Assert.That(Contrast(palette.PanelText, palette.PanelHover), Is.GreaterThanOrEqualTo(4.5), "panel hover");
            Assert.That(Contrast(palette.Line, palette.Background), Is.GreaterThanOrEqualTo(3), "control border");
            Assert.That(Contrast(palette.PanelLine, palette.Panel), Is.GreaterThanOrEqualTo(3), "panel border");
            Assert.That(Contrast(palette.Bar, palette.Track), Is.GreaterThanOrEqualTo(3), "progress");
            Assert.That(Contrast(palette.Ring, palette.Background), Is.GreaterThanOrEqualTo(3), "focus ring");
            Assert.That(Contrast(palette.PanelRing, palette.Panel), Is.GreaterThanOrEqualTo(3), "panel focus ring");
        });
    }

    [Test]
    public void Every_voice_line_is_recorded_and_said_in_both_languages()
    {
        Assembly installer = typeof(Texts).Assembly;
        using Stream linesFile = File.OpenRead(Path.Combine(TestContext.CurrentContext.TestDirectory, "lines.json"));
        using JsonDocument lines = JsonDocument.Parse(linesFile);
        foreach (string language in LinesInBothLanguages)
        {
            foreach (JsonProperty line in lines.RootElement.GetProperty(language).EnumerateObject())
            {
                using Stream? clip = installer.GetManifestResourceStream($"Baxy.Installer.voice.{language}_{line.Name}");
                Assert.That(clip, Is.Not.Null, $"{language}_{line.Name}");
            }
        }

        foreach (FailureKind kind in Enum.GetValues<FailureKind>())
        {
            string line = Failures.VoiceLine(kind);
            Assert.That(lines.RootElement.GetProperty("es").TryGetProperty(line, out _), Is.True, line);
        }
    }

    [Test]
    public void The_person_is_told_the_real_cause_of_a_failure()
    {
        Assert.Multiple(() =>
        {
            Assert.That(
                Classify(new InstallBlockedException("x", new IOException())),
                Is.EqualTo(FailureKind.Open));
            Assert.That(Classify(new PrerequisiteException("x")), Is.EqualTo(FailureKind.Windows));
            Assert.That(Classify(new InvalidDataException("x")), Is.EqualTo(FailureKind.Damaged));
            Assert.That(Classify(new HttpRequestException("x")), Is.EqualTo(FailureKind.Network));
            Assert.That(Classify(new IOException("full", unchecked((int)0x80070070))), Is.EqualTo(FailureKind.Disk));
            Assert.That(Classify(new NotSupportedException("x")), Is.EqualTo(FailureKind.Other));
        });

        static FailureKind Classify(Exception failure) => Failures.Classify(failure, baxyIsOpen: () => true);
    }

    [TestCase("es", "tu propia clave de una empresa de IA")]
    [TestCase("en", "your own key from an AI company")]
    public void The_license_says_what_leaves_the_pc_when_the_person_connects_a_company(string language, string words)
    {
        Assert.That(WindowsIntegration.LicenseText(language), Does.Match(words));
    }

    [TestCase("es", "Restricciones de uso")]
    [TestCase("en", "Use restrictions")]
    public void The_license_carries_the_use_restrictions_the_voice_requires(string language, string section)
    {
        string license = WindowsIntegration.LicenseText(language);

        Assert.That(license, Does.Contain(section));
        Assert.That(license, Does.Contain("OpenRAIL-M"));
        Assert.That(license, Does.Not.Contain("Steam"));
    }

    [Test]
    public void The_voice_starts_off_when_a_baxy_that_could_hear_it_is_open()
    {
        using Mutex open = new(false, @"Local\BAXY.Product.App");
        using Voice voice = new();

        Assert.That(Voice.BaxyIsOpen(), Is.True);
        Assert.That(voice.IsOn, Is.False);
    }

    [Test]
    public async Task Pause_holds_the_work_until_the_person_resumes()
    {
        PauseGate gate = new();
        gate.Pause();
        Task held = gate.WaitAsync(CancellationToken.None);

        await Task.Delay(30);
        Assert.That(held.IsCompleted, Is.False);

        gate.Resume();
        await held;
        Assert.That(gate.IsPaused, Is.False);
    }

    private static double Contrast(string first, string second)
    {
        double one = Luminance(first);
        double two = Luminance(second);
        return (Math.Max(one, two) + 0.05) / (Math.Min(one, two) + 0.05);
    }

    private static double Luminance(string hex)
    {
        double Channel(int start)
        {
            double value = int.Parse(hex.AsSpan(start, 2), NumberStyles.HexNumber, CultureInfo.InvariantCulture) / 255d;
            return value <= 0.03928 ? value / 12.92 : Math.Pow((value + 0.055) / 1.055, 2.4);
        }

        return (0.2126 * Channel(1)) + (0.7152 * Channel(3)) + (0.0722 * Channel(5));
    }
}
