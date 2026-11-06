using Baxy.Providers.Windows.Audio;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew audit (2026-10-15): the application whose volume changes is the one named — a word of its name is the
/// process name, exactly — never another one that shares a prefix.
/// </summary>
[TestFixture]
public sealed class AudioSessionMatchTests
{
    [TestCase("Spotify", "Spotify", true)]
    [TestCase("chrome", "Google Chrome", true)]
    [TestCase("opera", "Opera GX", true)]
    [TestCase("Discord", "discord", true)]
    [TestCase("WindowsTerminal", "Windows Media Player", false)]
    [TestCase("chromium", "Chrome", false)]
    [TestCase("spotifywebhelper", "Spotify", false)]
    // Encargo 82 (vivo del 81, volumen 0/2): a process named like a package, said whole, with its dots or by its words;
    // its parts alone are not it.
    [TestCase("Contoso.Sound.Deck", "Contoso.Sound.Deck", true)]
    [TestCase("Contoso.Sound.Deck", "contoso sound deck", true)]
    [TestCase("Contoso.Sound.Deck", "Contoso.Sound", false)]
    [TestCase("Contoso.Sound.Deck", "Sound", false)]
    public void A_word_of_the_name_is_the_process_exactly(string process, string application, bool matches) =>
        Assert.That(WindowsCoreAudioPlatform.ApplicationSessionMatches(process, application), Is.EqualTo(matches));

    // Uso 81 (privacy review): the name an application writes for its own session reaches the model in a failure's next;
    // it goes without control characters and at most 64 characters long, never splitting a surrogate pair.
    [Test]
    public void A_shown_name_is_bounded_and_without_control_characters()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsCoreAudioPlatform.ShownName(" Discord\r\n PTB\t"), Is.EqualTo("Discord PTB"));
            Assert.That(WindowsCoreAudioPlatform.ShownName("\u0007"), Is.Null);
            Assert.That(WindowsCoreAudioPlatform.ShownName(null), Is.Null);
            Assert.That(WindowsCoreAudioPlatform.ShownName(new string('a', 80)), Has.Length.EqualTo(64));
            Assert.That(WindowsCoreAudioPlatform.ShownName(new string('a', 63) + "😀b"), Is.EqualTo(new string('a', 63)));
        });
    }

    // Encargo 17 (banco uso-cf8d, R09: «edge» with msedge holding audio said no session): with no process of that name,
    // the session whose program's own name (its product name, or the name Windows gives the person's browser) is the
    // name said, or ends with it as whole words, or has it among its abbreviations in the data, is the application's.
    // Invented program names only, except the data's own abbreviations.
    private static readonly Dictionary<string, string[]> ProductNames = new(StringComparer.Ordinal)
    {
        ["zuvbrowse"] = ["Vendra Zuvi"],
        ["zuvbrowsehost"] = ["Vendra Zuvi Host"],
        ["lumplay"] = ["Lumo Player"],
        ["kestra"] = ["Kestra"],
        ["oxpanel"] = ["Orvel Panel Browser"],
        ["qimbo"] = ["Qimbo Browser"],
        ["msedge"] = ["Microsoft Edge"],
    };

    private static int[] Named(string application, params string[] processes) =>
        [.. WindowsCoreAudioPlatform.NamedSessions(processes, application, index => ProductNames[processes[index]])];

    [Test]
    public void A_name_said_short_of_its_product_name_is_that_program_session() =>
        Assert.That(Named("zuvi", "lumplay", "zuvbrowse", "zuvbrowse"), Is.EqualTo(new[] { 1, 2 }));

    [Test]
    public void The_whole_product_name_is_that_program_session() =>
        Assert.That(Named("Vendra Zuvi", "lumplay", "zuvbrowse"), Is.EqualTo(new[] { 1 }));

    [Test]
    public void A_product_name_that_only_holds_the_name_further_in_is_another_program() =>
        Assert.That(Named("zuvi", "zuvbrowsehost", "zuvbrowse"), Is.EqualTo(new[] { 1 }));

    [Test]
    public void An_abbreviation_in_the_data_names_its_program() =>
        Assert.That(Named("el edge", "lumplay", "msedge"), Is.EqualTo(new[] { 1 }));

    [Test]
    public void The_process_named_wins_over_a_product_name() =>
        Assert.That(Named("kestra", "kestra", "lumplay"), Is.EqualTo(new[] { 0 }));

    [Test]
    public void A_name_two_programs_end_with_is_none_of_them() =>
        Assert.That(Named("browser", "oxpanel", "qimbo"), Is.Empty);

    // Encargo 82 (vivo del 81): a Store application's executable has no description and its session no name, so the name
    // the person sees named nothing, and the model then moved the whole PC's volume (15 of 20). Its name is its item in
    // the Apps folder, by its application id. Against the machine's own shell: an id no application has is no name.
    [Test]
    public void A_packaged_application_is_named_as_windows_shows_it()
    {
        string? shown = WindowsCoreAudioPlatform.AppsFolderName("Microsoft.WindowsCalculator_8wekyb3d8bbwe!App");
        Assert.Multiple(() =>
        {
            Assert.That(WindowsCoreAudioPlatform.AppsFolderName("Contoso.NoSuchPackage_0000000000000!App"), Is.Null);
            Assert.That(WindowsCoreAudioPlatform.AppsFolderName(""), Is.Null);
        });
        if (shown is null)
            Assert.Ignore("This machine has no Calculator from the Store.");
        Assert.That(shown, Does.Not.Contain("!"), "a name, not the id");
        Assert.That(shown, Does.Not.Contain("_8wekyb3d8bbwe"));
    }

    [Test]
    public void The_first_word_of_a_product_name_is_not_it() =>
        Assert.That(Named("lumo", "lumplay"), Is.Empty);
}
