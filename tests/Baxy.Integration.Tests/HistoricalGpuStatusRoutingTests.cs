using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class HistoricalGpuStatusRoutingTests
{
    private const string OracleFileSha256 =
        "fa43313f72384202788a4d01a2f66756e574623c5c071089173a7250d1a58e33";
    private const string CorpusFileSha256 =
        "9d8b2d095dcd0bafb9d2a7bb616876b34b6b0321d53597211c37a26473ac436e";
    private const string PositiveIdsSha256 =
        "61d2265b499313c85e30d84e207ec462a0e166d4f88352549c1456f8d80335e4";
    private const string PositiveRecordsSha256 =
        "36ec73ee52e75f856a10dc4fdca8aa6868015b6f3af1eb1d202303ddd4ef171e";
    private const string CompositionIdsSha256 =
        "d3c640324b210ec2ad0475648dd4e7a6b22c01bd5585c5c9767701661a667643";
    private const string CompositionRecordsSha256 =
        "c7dff98d56bdbb61a1f2fa00235d7155958a24dcc5e0145cc03852dd1a40f97b";
    private const string HardNegativeIdsSha256 =
        "481280cb9d3e3978ac34cbbb5a849226a17c54247480c369fea6068af98275c6";
    private const string HardNegativeRecordsSha256 =
        "4cff5e3572cba6aa6aaba8e1369880644115d0fab54b47cf8e8afdf7096a0c39";

    [Test]
    public void FrozenGpuOracleRetainsExactCorpusSetsAndDigests()
    {
        OracleData oracle = LoadOracleData();
        using JsonDocument document = JsonDocument.Parse(
            File.ReadAllText(oracle.OraclePath, Encoding.UTF8));
        JsonElement root = document.RootElement;
        JsonElement groups = root.GetProperty("groups");

        string[] positiveIds = root.GetProperty("canonical_cases")
            .EnumerateArray()
            .SelectMany(static item => item.GetProperty("ids").EnumerateArray())
            .Select(static item => item.GetString()!)
            .ToArray();
        string[] compositionIds = ReadCategorizedIds(root, "composition_cases");
        string[] hardNegativeIds = ReadCategorizedIds(root, "hard_negative_cases");
        string[] selectedIds = [.. positiveIds, .. compositionIds, .. hardNegativeIds];

        Assert.Multiple(() =>
        {
            Assert.That(HashFile(oracle.OraclePath), Is.EqualTo(OracleFileSha256));
            Assert.That(HashFile(oracle.CorpusPath), Is.EqualTo(CorpusFileSha256));
            Assert.That(root.GetProperty("oracle_id").GetString(),
                Is.EqualTo("baxy.system-status.gpu-local.v1"));

            AssertFrozenGroup(
                groups.GetProperty("positive_union"),
                positiveIds,
                26,
                PositiveIdsSha256,
                PositiveRecordsSha256,
                oracle.TextById);
            AssertFrozenGroup(
                groups.GetProperty("composition"),
                compositionIds,
                17,
                CompositionIdsSha256,
                CompositionRecordsSha256,
                oracle.TextById);
            AssertFrozenGroup(
                groups.GetProperty("hard_negative"),
                hardNegativeIds,
                34,
                HardNegativeIdsSha256,
                HardNegativeRecordsSha256,
                oracle.TextById);

            Assert.That(positiveIds.Distinct(StringComparer.Ordinal).Count(), Is.EqualTo(26));
            Assert.That(compositionIds.Distinct(StringComparer.Ordinal).Count(), Is.EqualTo(17));
            Assert.That(
                hardNegativeIds.Distinct(StringComparer.Ordinal).Count(),
                Is.EqualTo(34));
            Assert.That(selectedIds.Distinct(StringComparer.Ordinal).Count(), Is.EqualTo(77));
            Assert.That(
                ReadIds(groups.GetProperty("composition")),
                Is.EquivalentTo(compositionIds));
            Assert.That(
                ReadIds(groups.GetProperty("hard_negative")),
                Is.EquivalentTo(hardNegativeIds));
        });
    }

    [TestCaseSource(nameof(PositiveOracleCases))]
    public void FrozenStandaloneGpuQueriesRouteToTheirExactScope(
        string text,
        string expectedScope,
        string messageId)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, $"{messageId}: {text}");
            Assert.That(operation?.Name, Is.EqualTo("system.status"), messageId);
            Assert.That(
                operation?.Arguments["scope"]?.GetValue<string>(),
                Is.EqualTo(expectedScope),
                messageId);
            Assert.That(operation?.Arguments, Has.Count.EqualTo(1), messageId);
        });
    }

    [TestCaseSource(nameof(CompositionOracleCases))]
    [TestCaseSource(nameof(HardNegativeOracleCases))]
    public void FrozenGpuCompositionsAndHardNegativesFailClosed(
        string text,
        string category,
        string messageId)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.False, $"{category}/{messageId}: {text}");
            Assert.That(operation, Is.Null, $"{category}/{messageId}");
        });
    }

    private static IEnumerable<TestCaseData> PositiveOracleCases()
    {
        OracleData oracle = LoadOracleData();
        using JsonDocument document = JsonDocument.Parse(
            File.ReadAllText(oracle.OraclePath, Encoding.UTF8));
        foreach (JsonElement canonicalCase in document.RootElement
            .GetProperty("canonical_cases")
            .EnumerateArray())
        {
            string scope = canonicalCase.GetProperty("scope").GetString()!;
            foreach (JsonElement idElement in canonicalCase.GetProperty("ids").EnumerateArray())
            {
                string messageId = idElement.GetString()!;
                yield return new TestCaseData(oracle.TextById[messageId], scope, messageId)
                    .SetName($"NaturalGpu_{scope}_{messageId}");
            }
        }
    }

    private static IEnumerable<TestCaseData> CompositionOracleCases() =>
        NonRouteOracleCases("composition_cases", "composition");

    private static IEnumerable<TestCaseData> HardNegativeOracleCases() =>
        NonRouteOracleCases("hard_negative_cases", "hard_negative");

    private static IEnumerable<TestCaseData> NonRouteOracleCases(
        string propertyName,
        string casePrefix)
    {
        OracleData oracle = LoadOracleData();
        using JsonDocument document = JsonDocument.Parse(
            File.ReadAllText(oracle.OraclePath, Encoding.UTF8));
        foreach (JsonElement categorizedCase in document.RootElement
            .GetProperty(propertyName)
            .EnumerateArray())
        {
            string category = categorizedCase.GetProperty("category").GetString()!;
            foreach (JsonElement idElement in categorizedCase.GetProperty("ids").EnumerateArray())
            {
                string messageId = idElement.GetString()!;
                yield return new TestCaseData(oracle.TextById[messageId], category, messageId)
                    .SetName($"NaturalGpu_{casePrefix}_{category}_{messageId}");
            }
        }
    }

    private static void AssertFrozenGroup(
        JsonElement group,
        IReadOnlyCollection<string> ids,
        int count,
        string idsSha256,
        string recordsSha256,
        IReadOnlyDictionary<string, string> textById)
    {
        Assert.Multiple(() =>
        {
            Assert.That(group.GetProperty("count").GetInt32(), Is.EqualTo(count));
            Assert.That(group.GetProperty("ids_sha256").GetString(), Is.EqualTo(idsSha256));
            Assert.That(
                group.GetProperty("records_sha256").GetString(),
                Is.EqualTo(recordsSha256));
            Assert.That(ComputeIdsDigest(ids), Is.EqualTo(idsSha256));
            Assert.That(
                ComputeRecordsDigest(ids, textById),
                Is.EqualTo(recordsSha256));
        });
    }

    private static string[] ReadCategorizedIds(JsonElement root, string propertyName) =>
        root.GetProperty(propertyName)
            .EnumerateArray()
            .SelectMany(static item => item.GetProperty("ids").EnumerateArray())
            .Select(static item => item.GetString()!)
            .ToArray();

    private static string[] ReadIds(JsonElement group) =>
        group.GetProperty("ids")
            .EnumerateArray()
            .Select(static item => item.GetString()!)
            .ToArray();

    private static string ComputeIdsDigest(IEnumerable<string> ids)
    {
        string payload = string.Concat(ids
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .Select(static id => $"{id}\n"));
        return HashBytes(Encoding.UTF8.GetBytes(payload));
    }

    private static string ComputeRecordsDigest(
        IEnumerable<string> ids,
        IReadOnlyDictionary<string, string> textById)
    {
        string payload = string.Concat(ids
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .Select(id => $"{id}\t{NormalizeLiteral(textById[id])}\n"));
        return HashBytes(Encoding.UTF8.GetBytes(payload));
    }

    private static string NormalizeLiteral(string value)
    {
        string normalized = value.Normalize(NormalizationForm.FormC);
        var builder = new StringBuilder(normalized.Length);
        bool pendingSpace = false;
        foreach (char character in normalized)
        {
            if (char.IsWhiteSpace(character))
            {
                pendingSpace = builder.Length > 0;
                continue;
            }

            if (pendingSpace)
            {
                builder.Append(' ');
                pendingSpace = false;
            }

            builder.Append(char.ToLowerInvariant(character));
        }

        return builder.ToString().Normalize(NormalizationForm.FormC);
    }

    private static string HashFile(string path) => HashBytes(File.ReadAllBytes(path));

    private static string HashBytes(byte[] bytes) =>
        Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    private static OracleData LoadOracleData()
    {
        string repositoryRoot = FindRepositoryRoot();
        string oraclePath = Path.Combine(
            repositoryRoot,
            "tests",
            "data",
            "gpu_status_corpus_oracle.json");
        string corpusPath = Path.Combine(
            repositoryRoot,
            "tests",
            "data",
            "historical_messages.jsonl");
        var textById = new Dictionary<string, string>(StringComparer.Ordinal);

        foreach (string line in File.ReadLines(corpusPath, Encoding.UTF8))
        {
            using JsonDocument row = JsonDocument.Parse(line);
            JsonElement root = row.RootElement;
            textById.Add(
                root.GetProperty("message_id").GetString()!,
                root.GetProperty("text_literal").GetString()!);
        }

        return new OracleData(oraclePath, corpusPath, textById);
    }

    private static string FindRepositoryRoot()
    {
        DirectoryInfo? directory = new(TestContext.CurrentContext.TestDirectory);
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException("No se encontró la raíz versionada de BAXY.");
    }

    private sealed record OracleData(
        string OraclePath,
        string CorpusPath,
        IReadOnlyDictionary<string, string> TextById);
}
