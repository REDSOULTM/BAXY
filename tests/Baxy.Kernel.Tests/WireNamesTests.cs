using System.Text.Json;
using System.Text.RegularExpressions;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// e01442da5 (src/baxy_mind/wire.py): the name the model sees for an operation is no longer always its id with «.» → «_»
/// (audio.volume is audio_volume_set beside audio_volume_adjust). The texts the App and the providers give the model
/// built the old name by hand and named calls the model is not shown. WireNames gives the mind's names; the reference
/// tests/fixtures/wire_names.v1.json, checked here and against Wires (tests/test_mind_wire.py), keeps them the same.
/// </summary>
[TestFixture]
public sealed class WireNamesTests
{
    [Test]
    public void TheProductCatalogsWireNamesAreTheMindsForEveryOperation()
    {
        using JsonDocument reference = JsonDocument.Parse(File.ReadAllText(
            Path.Combine(RepositoryRoot(), "tests", "fixtures", "wire_names.v1.json")));
        string[] fixedNames = [.. reference.RootElement.GetProperty("fixed").EnumerateArray()
            .Select(static name => name.GetString()!)];
        (string Operation, string Name)[] names = [.. reference.RootElement.GetProperty("names").EnumerateObject()
            .Select(static p => (p.Name, p.Value.GetString()!))];

        Assert.Multiple(() =>
        {
            Assert.That(WireNames.MindTools, Is.EqualTo(fixedNames));
            // The App sends the catalog in this order (ProductCatalog.ValidateAgainst), and the mind names it so.
            Assert.That(names.Select(static n => n.Operation),
                Is.EqualTo(ProductCatalog.ToolDescriptors.Select(static d => d.Name)));
            Assert.That(names.Select(static n => (n.Operation, WireNames.Of(n.Operation))), Is.EqualTo(names));
        });
    }

    [Test]
    public void TheShortNameOfAPairGetsASuffixAndTheOthersKeepTheirs()
    {
        var wires = new WireNames(
            ["x.level", "x.level.adjust", "y.go", "y.go.named", "z.one", "w.find", "w.finds"], []);
        Assert.Multiple(() =>
        {
            Assert.That(new[] { "x.level", "x.level.adjust", "y.go", "y.go.named", "z.one", "w.find", "w.finds" }
                .Select(wires.Name), Is.EqualTo(new[]
                {
                    "x_level_set", "x_level_adjust", "y_go_set", "y_go_named", "z_one", "w_find_set", "w_finds",
                }));
            Assert.That(wires.Name("q.r"), Is.EqualTo("q_r"));
            Assert.That(WireNames.Of("audio.volume"), Is.EqualTo("audio_volume_set"));
            Assert.That(WireNames.Of("audio.volume.adjust"), Is.EqualTo("audio_volume_adjust"));
        });
    }

    [Test]
    public void ASuffixThatClashesByShapeIsTheNextOne()
    {
        // a_b_set is taken by another operation, a_bset is the same letters but for «_», set_a_b the same parts.
        var taken = new WireNames(["a.b", "a.b.c", "a.b.set"], []);
        var letters = new WireNames(["a.b", "a.b.c", "a.bset"], []);
        var parts = new WireNames(["a.b", "a.b.c", "set.a.b"], []);
        Assert.Multiple(() =>
        {
            Assert.That(taken.Name("a.b"), Is.EqualTo("a_b_2set"));
            Assert.That(letters.Name("a.b"), Is.EqualTo("a_b_2set"));
            Assert.That(parts.Name("a.b"), Is.EqualTo("a_b_2set"));
            // A fixed name the model is shown makes a catalog name short too.
            Assert.That(new WireNames(["ask"], ["ask_user"]).Name("ask"), Is.EqualTo("ask_set"));
        });
    }

    // A short name whose every suffix still begins with another name shown (calculate_x with the mind's calculate) has
    // no name to take: the rule says so by name, as wire.py does, and never loops.
    [Test]
    public void AShortNameNoSuffixCanPartFromAnotherNameIsAClearErrorNeverAHang()
    {
        InvalidOperationException error = Settle(["calculate.x", "calculate.x.y"], WireNames.MindTools)
            ?? throw new AssertionException("the names settled where no suffix can part them");
        Assert.That(error.Message, Is.EqualTo(
            "no wire name for calculate.x: calculate_x_set to calculate_x_9set all clash with the names of calculate"));
    }

    [Test]
    public void TheSuffixesGoUpTo9SetAndPastItTheNamesAreAnError()
    {
        string[] taken = ["a.b", "a.b.c", "a.b.set", .. Enumerable.Range(2, 7).Select(static k => $"a.b.{k}set")];
        Assert.That(new WireNames(taken, []).Name("a.b"), Is.EqualTo("a_b_9set"));
        InvalidOperationException error = Settle([.. taken, "a.b.9set"], [])
            ?? throw new AssertionException("a tenth suffix was taken");
        Assert.That(error.Message, Is.EqualTo("no wire name for a.b: a_b_set to a_b_9set all clash with the names of "
            + "a.b.2set, a.b.3set, a.b.4set, a.b.5set, a.b.6set, a.b.7set, a.b.8set, a.b.9set, a.b.set"));
    }

    // The names of a catalog with a time limit: a rule that loops fails the test instead of hanging the suite.
    private static InvalidOperationException? Settle(string[] operations, IReadOnlyList<string> fixedNames)
    {
        var settling = Task.Run(() => new WireNames(operations, fixedNames));
        try
        {
            if (!settling.Wait(TimeSpan.FromSeconds(20)))
                throw new AssertionException($"the names of {string.Join(", ", operations)} did not settle within 20 s");
        }
        catch (AggregateException wrapped) when (wrapped.InnerException is InvalidOperationException error)
        {
            return error;
        }

        return null;
    }

    // Each text the App and the providers give the model names a call by WireNames: none builds a name by hand, and none
    // writes the old name of a renamed operation in a string. It reads line by line: a name on a continuation line of a
    // raw """ literal, or one built another way than Replace, is not seen here.
    [Test]
    public void NoSourceTextNamesACallByAWireNameTheModelIsNotShown()
    {
        string root = RepositoryRoot();
        string[] renamed = [.. ProductCatalog.ToolDescriptors
            .Select(static d => d.Name)
            .Where(static op => WireNames.Of(op) != op.Replace('.', '_'))
            .Select(static op => op.Replace('.', '_'))];
        var oldName = new Regex("\"[^\"\\n]*\\b(" + string.Join('|', renamed.Select(Regex.Escape)) + ")\\b(?!_)",
            RegexOptions.CultureInvariant);
        var found = new List<string>();
        foreach (string file in Directory.EnumerateFiles(Path.Combine(root, "src"), "*.cs", SearchOption.AllDirectories))
        {
            if (file.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}", StringComparison.Ordinal)
                || file.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}", StringComparison.Ordinal)
                || Path.GetFileName(file) == "WireNames.cs")
                continue;
            string[] lines = File.ReadAllLines(file);
            for (int index = 0; index < lines.Length; index++)
            {
                string line = lines[index].TrimStart();
                if (line.StartsWith("//", StringComparison.Ordinal))
                    continue;
                if (line.Contains("Replace('.', '_')", StringComparison.Ordinal)
                    || line.Contains("Replace(\".\", \"_\"", StringComparison.Ordinal)
                    || oldName.IsMatch(line))
                    found.Add($"{Path.GetRelativePath(root, file)}:{index + 1}");
            }
        }

        Assert.That(found, Is.Empty);
    }

    private static string RepositoryRoot()
    {
        for (DirectoryInfo? directory = new(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            if (File.Exists(Path.Combine(directory.FullName, "tests", "fixtures", "wire_names.v1.json")))
                return directory.FullName;
        }

        throw new DirectoryNotFoundException("The repository root was not found above the test's folder.");
    }
}
