using System.Text.Json;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// FT/proveedores goal (live check of the App, 2026-10-18): the App checks at start that its operation labels
/// (src/Baxy.App/Assets/operation-labels.v1.json) name exactly the catalog's operations, and ends on a mismatch. Since
/// app.restart and display.mode.set joined the catalog without labels, the whole App closed at start (the conductor,
/// which the benches use, never builds the view, so no bench saw it). Here the mismatch fails a suite instead.
/// </summary>
[TestFixture]
public sealed class OperationLabelsCoverageTests
{
    [Test]
    public void EveryCatalogOperationHasALabelAndNoLabelIsExtra()
    {
        string labels = Path.Combine(RepositoryRoot(), "src", "Baxy.App", "Assets", "operation-labels.v1.json");
        using JsonDocument document = JsonDocument.Parse(File.ReadAllText(labels));
        string[] labelled = [.. document.RootElement.GetProperty("operations").EnumerateObject().Select(static p => p.Name)];
        string[] catalog = [.. ProductCatalog.ToolDescriptors.Select(static d => d.Name)];

        Assert.Multiple(() =>
        {
            Assert.That(catalog.Except(labelled, StringComparer.Ordinal), Is.Empty, "catalog operations with no label");
            Assert.That(labelled.Except(catalog, StringComparer.Ordinal), Is.Empty, "labels of no catalog operation");
        });
    }

    // Steam (2026-11-04): an English interface shows each operation's English title and its theme in English; one
    // missing would show the Spanish word, so the App ends at start without it, and here a suite fails instead.
    [Test]
    public void EveryLabelAndThemeHasItsEnglishWords()
    {
        string labels = Path.Combine(RepositoryRoot(), "src", "Baxy.App", "Assets", "operation-labels.v1.json");
        using JsonDocument document = JsonDocument.Parse(File.ReadAllText(labels));
        JsonElement root = document.RootElement;
        string[] untitled = [.. root.GetProperty("operations").EnumerateObject()
            .Where(static p => !p.Value.TryGetProperty("en", out JsonElement en) || string.IsNullOrWhiteSpace(en.GetString()))
            .Select(static p => p.Name)];
        string[] themes = [.. root.GetProperty("groups").EnumerateObject().Select(static p => p.Name)];
        string[] englishThemes = [.. root.GetProperty("groupsEn").EnumerateObject()
            .Where(static p => !string.IsNullOrWhiteSpace(p.Value.GetString())).Select(static p => p.Name)];

        Assert.Multiple(() =>
        {
            Assert.That(untitled, Is.Empty, "operations with no English title");
            Assert.That(englishThemes, Is.EquivalentTo(themes), "themes with no English name");
        });
    }

    private static string RepositoryRoot()
    {
        for (DirectoryInfo? directory = new(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            if (File.Exists(Path.Combine(directory.FullName, "src", "Baxy.App", "Assets", "operation-labels.v1.json")))
                return directory.FullName;
        }

        throw new DirectoryNotFoundException("The repository root was not found above the test's folder.");
    }
}
