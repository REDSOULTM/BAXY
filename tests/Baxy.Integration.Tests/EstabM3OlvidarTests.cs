using System.IO;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización M3 (identity live check on the notebook 2026-10-12, cu-v3/estab/I_identidad_notebook_4.md, Release
/// 9b7d8d757, 2 of 2): with «color favorito de prueba: turquesa» kept, «Olvidá mi color favorito de prueba» was asked
/// «¿Qué alcance deseas eliminar de tus memorias locales: todo, exacto, tipo o tema?» and «No, cancelá» then ended «No
/// pude contarte cómo salió lo que pediste.».
/// </summary>
[TestFixture]
public sealed class EstabM3OlvidarTests
{
    private static readonly string[] LiveKeys = ["favorite_color", "color_favorito_de_prueba"];

    private static JsonObject ClarificationFields()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
        {
            directory = directory.Parent;
        }

        return (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
            directory?.FullName ?? throw new DirectoryNotFoundException("Baxy.slnx was not found."),
            "src", "baxy_mind", "data", "clarification_fields.v1.json")))!;
    }

    private static HashSet<string> Listed(JsonObject fields, string list) =>
        ((JsonObject)fields[list]!)
            .SelectMany(entry => ((JsonArray)entry.Value!).Select(field => entry.Key + "." + (string)field!))
            .ToHashSet(StringComparer.Ordinal);

    [Test]
    public void EveryClosedValueArgumentOfTheCatalogIsEitherInternalOrSaidInWords()
    {
        JsonObject fields = ClarificationFields();
        HashSet<string> internalFields = Listed(fields, "internal");
        HashSet<string> askedInWords = Listed(fields, "askedInWords");
        var closed = new HashSet<string>(StringComparer.Ordinal);
        Assert.Multiple(() =>
        {
            foreach (ProductOperationDescriptor descriptor in ProductCatalog.Descriptors)
            {
                foreach (OperationArgumentProperty property in descriptor.ArgumentsSchema.Properties)
                {
                    string name = descriptor.Name + "." + property.Name;
                    if (MainWindowViewModel.FixedByContract(property))
                    {
                        // The contract's own value is filled, never asked, and never listed.
                        Assert.That(internalFields.Contains(name) || askedInWords.Contains(name), Is.False, name);
                        continue;
                    }

                    if (property.AllowedValues.Count < 2)
                    {
                        continue;
                    }

                    closed.Add(name);
                    Assert.That(internalFields.Contains(name) ^ askedInWords.Contains(name), Is.True, name);
                }
            }

            // No stale entry: every listed argument is a closed-value argument of the real catalog.
            Assert.That(internalFields.Union(askedInWords).Except(closed), Is.Empty);
            Assert.That(internalFields, Does.Contain("memory.forget.scope"));
        });
    }

    [Test]
    public void TheContractsOwnValuesOfAForgetAreNeverNamedToThePerson()
    {
        ProductOperationDescriptor forget = ProductCatalog.Descriptors.Single(descriptor => descriptor.Name == "memory.forget");
        string[] fixedByContract = forget.ArgumentsSchema.Properties
            .Where(MainWindowViewModel.FixedByContract)
            .Select(property => property.Name)
            .ToArray();
        Assert.That(fixedByContract, Is.EquivalentTo(new[] { "confirmationRequired", "version" }));
    }

    [TestCase("color_favorito_de_prueba", "color_favorito_de_prueba")]
    [TestCase("favorite_color", "favorite_color")]
    [TestCase("color_de_prueba", "color_favorito_de_prueba")]
    public void TheDatumNamedInThePersonsWordsIsTheKeptKey(string asked, string kept) =>
        Assert.That(MemoryPanel.Candidates(asked, LiveKeys), Is.EqualTo(new[] { kept }));

    [Test]
    public void SeveralKeptKeysWithTheAskedWordsAreAskedByTheirNames()
    {
        IReadOnlyList<string> candidates = MemoryPanel.Candidates("color", LiveKeys);
        Assert.Multiple(() =>
        {
            Assert.That(candidates, Is.EquivalentTo(LiveKeys));
            Assert.That(
                OperationFloor.MemoryKeysSentence(candidates.Select(key => MemoryPanel.Label(key)).ToArray(), english: false),
                Is.EqualTo("¿Cuál quieres que olvide: tu color favorito o tu color favorito de prueba?"));
            Assert.That(
                OperationFloor.MemoryKeysSentence(
                    candidates.Select(key => MemoryPanel.Label(key, english: true)).ToArray(), english: true),
                Is.EqualTo("Which one should I forget: your favorite color or your color favorito de prueba?"));
        });
    }

    [Test]
    public void ContracaseAShorterKeptKeyIsNeverTheLongerDatumAsked()
    {
        // Only «color favorito» kept: «olvidá mi color favorito de prueba» never forgets it; it says it was not kept.
        IReadOnlyList<string> candidates = MemoryPanel.Candidates("color_favorito_de_prueba", ["favorite_color"]);
        Assert.Multiple(() =>
        {
            Assert.That(candidates, Is.Empty);
            Assert.That(
                OperationFloor.MemoryKeysSentence([MemoryPanel.Label("color_favorito_de_prueba")], english: false),
                Is.EqualTo("No tengo guardado nada de tu color favorito de prueba, así que no olvidé nada."));
            Assert.That(MemoryPanel.Candidates("reunion", LiveKeys), Is.Empty);
        });
    }

    [Test]
    public void ACancelledQuestionIsSaidByTheFloorNeverTheCompositionFailure()
    {
        string source = TurnVisibleFacts.Status("clarification_cancelled");
        var draft = new UserMessageDraft(source, "status", null);
        const string Said = "Vale, lo dejo: no hice nada.";
        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.Final((JsonObject)JsonNode.Parse(source)!, english: false), Is.EqualTo(Said));
            Assert.That(
                ModelMessageComposer.DeterministicFinal(draft, "No, cancelá", ModelMessageComposer.CreateFacts(draft), string.Empty),
                Is.EqualTo(Said));
            Assert.That(
                OperationFloor.Final((JsonObject)JsonNode.Parse(source)!, english: true),
                Is.EqualTo("OK, I'll leave it: I didn't do anything."));
        });
    }

    [Test]
    public void ContracaseAnotherStatusWithoutAnActIsStillNoFloor()
    {
        string source = TurnVisibleFacts.Status("acting");
        Assert.That(OperationFloor.Final((JsonObject)JsonNode.Parse(source)!, english: false), Is.Null);
    }
}
