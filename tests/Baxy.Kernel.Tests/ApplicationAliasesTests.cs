using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// Encargo 12: the non-ambiguous abbreviations of an application or a channel (src/baxy_mind/data/app_aliases.v1.json,
/// read by <see cref="ApplicationAliases"/>). The owner's one accepted help is a name-equivalence list: «wsp» names
/// WhatsApp, «ds» names Discord, and an ambiguous common word («un disco», «la tele») names no app.
/// </summary>
[TestFixture]
public sealed class ApplicationAliasesTests
{
    // The real case (03-11): «… por wsp» names WhatsApp, and «ds» names Discord, each as a whole word.
    [TestCase("dile a Nadia que llego tarde por wsp", "whatsapp", true)]
    [TestCase("escríbele al grupo por ds", "discord", true)]
    [TestCase("mándale un wasap a Nadia", "WhatsApp", true)]
    // An abbreviation only as part of a longer word is not it («wspized» is not «wsp»).
    [TestCase("eso me lo wspearon ayer", "whatsapp", false)]
    // The name itself is the caller's own check, not this one: this list is only the abbreviations.
    [TestCase("escríbele por whatsapp", "whatsapp", false)]
    // An ambiguous common word kept out of the list is not the app (encargo: «disco», «tele», «max»).
    [TestCase("pon un disco de los Beatles", "discord", false)]
    [TestCase("voy a ver la tele un rato", "Telegram", false)]
    [TestCase("súbele al máximo el volumen", "HBO Max", false)]
    [TestCase("necesito ver el código de esto", "Visual Studio Code", false)]
    public void ANameIsSaidByItsNonAmbiguousAbbreviation(string said, string name, bool names) =>
        Assert.That(ApplicationAliases.Names(said, name), Is.EqualTo(names));

    [Test]
    public void AnAppWithNoListedAbbreviationNamesNothing()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ApplicationAliases.Names("abre la configuración de sonido", "Configuración del sistema"), Is.False);
            Assert.That(ApplicationAliases.Names("hola", null), Is.False);
            Assert.That(ApplicationAliases.Names(null, "whatsapp"), Is.False);
            Assert.That(ApplicationAliases.Of("una app que no existe"), Is.Empty);
        });
    }

    // Looked up by its name or by one of its own abbreviations, an app gives the same list.
    [Test]
    public void TheAbbreviationsAreFoundByNameOrByAnotherAbbreviation()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ApplicationAliases.Of("WhatsApp"), Does.Contain("wsp"));
            Assert.That(ApplicationAliases.Of("wsp"), Does.Contain("guasap"));
            Assert.That(ApplicationAliases.Of("Discord"), Is.EqualTo(new[] { "ds" }));
        });
    }

    // Banco de uso 2026-11-03 (S01): a catalog value names its app by any of its forms, and every form gives all of
    // them, the app's name first.
    [Test]
    public void EveryFormGivesAllTheFormsOfItsApplication()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ApplicationAliases.FormsOf("disney_plus"), Does.Contain("disney plus"));
            Assert.That(ApplicationAliases.FormsOf("disney_plus"), Is.EqualTo(ApplicationAliases.FormsOf("Disney+")));
            Assert.That(ApplicationAliases.FormsOf("wsp")[0], Is.EqualTo("whatsapp"));
            Assert.That(ApplicationAliases.FormsOf("Discord"), Is.EqualTo(new[] { "discord", "ds" }));
            Assert.That(ApplicationAliases.FormsOf("una app que no existe"), Is.Empty);
            Assert.That(ApplicationAliases.FormsOf(null), Is.Empty);
        });
    }

    // The data load, and every folded form (a name or an abbreviation) names one app only: an abbreviation shared by two
    // apps or equal to a name is a data bug the reader refuses whole.
    [Test]
    public void TheDataLoadWithEveryFormUnique()
    {
        using Stream stream = typeof(ApplicationAliases).Assembly.GetManifestResourceStream("Baxy.Kernel.AppAliases.json")!;
        using JsonDocument document = JsonDocument.Parse(stream);
        IReadOnlyDictionary<string, IReadOnlyList<string>> read = ApplicationAliases.Read(document);

        Assert.That(read, Is.Not.Empty);
        Assert.That(read["whatsapp"], Does.Contain("wsp"));
    }

    [TestCase("{\"applications\":{\"A\":{\"aliases\":[\"x\"]},\"B\":{\"aliases\":[\"x\"]}}}")]
    [TestCase("{\"applications\":{\"A\":{\"aliases\":[\"b\"]},\"B\":{\"aliases\":[\"y\"]}}}")]
    [TestCase("{\"applications\":{\"A\":{\"aliases\":[\"a\"]}}}")]
    [TestCase("{\"applications\":{\"A\":{\"aliases\":[\"  \"]}}}")]
    public void MalformedDataIsRefusedWhole(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        Assert.That(() => ApplicationAliases.Read(document), Throws.InstanceOf<InvalidDataException>());
    }

    // Sentences an agent wrote without seeing the code (Data/app-aliases.heldout.v1.json): an abbreviation names its app,
    // an ambiguous common word does not.
    [TestCaseSource(nameof(HeldOut))]
    public void HeldOutSentences(string phrase, string app, bool names) =>
        Assert.That(ApplicationAliases.Names(phrase, app), Is.EqualTo(names));

    private static IEnumerable<TestCaseData> HeldOut()
    {
        string path = Path.Combine(TestContext.CurrentContext.TestDirectory, "Data", "app-aliases.heldout.v1.json");
        JsonNode data = JsonNode.Parse(File.ReadAllText(path))!;
        foreach ((string kind, bool names) in new[] { ("positivas", true), ("negativas", false) })
        {
            JsonArray items = data[kind]!.AsArray();
            for (int index = 0; index < items.Count; index++)
            {
                string phrase = (string)items[index]!["frase"]!;
                string app = (string)items[index]!["app"]!;
                yield return new TestCaseData(phrase, app, names).SetName($"HeldOut {kind} {index + 1}");
            }
        }
    }
}
