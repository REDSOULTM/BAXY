using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class HistoricalNaturalNoteRoutingTests
{
    private static readonly string[] PureCreateMessageIds =
    [
        "msg_0e99f895089e0fecf296", "msg_ba842091538ae94db32d",
        "msg_e3510b4683a4d0747fa7", "msg_60e810a450af9d93d276",
        "msg_01ba1292cb34d5fe8222", "msg_46e0056061e1621362b9",
        "msg_6beb99a8ecf9de6f91e7", "msg_fc15883ec0d7d9ab6795",
        "msg_f720e2b687df6f27f361", "msg_517f56be57c7585c3927",
        "msg_1cd4ba8805e4a9015a84", "msg_ed1b9aed10a17a244395",
        "msg_4c9beeafeb6c36860c4e", "msg_0031a8379de701d91722",
        "msg_d9209e0afa8ae62dd09f", "msg_065ada0f51385c0bb693",
        "msg_4f5c4b65e10df0f42d6f", "msg_4a0c6989d6cea247bb93",
        "msg_334d1192ce73241d00c3", "msg_943f7e0d27f239c8ecd7",
        "msg_6f1f526c24791dd8a09f", "msg_7ef7f5a51565c456990a",
        "msg_17d6d23a93b9fdfbc4a7", "msg_6a17c7ca9c56eef44668",
        "msg_4fc8c9d7f17f109f622e", "msg_05815b1f7ed3356ed83e",
        "msg_28784f217336fc024205", "msg_c975dffde8882e6a269f",
        "msg_26688fc9df48cade1c2a", "msg_cde28dd81fd88c4274f2",
        "msg_c646318001c2a380596d", "msg_cf3eea35c8e3d2f3ba2f",
        "msg_632eb4a30689a394c8b8", "msg_b14a538670a69b7c64e3",
        "msg_5990b86c8169673f4989", "msg_5e01e5c137f73568315f",
        "msg_9de486303560859a1d52", "msg_158a31242d680e50b5e8",
        "msg_13f89054e158fd2240c0", "msg_b434842c2ab18411c075",
    ];

    private static readonly string[] RequiredNegativeMessageIds =
    [
        "msg_7c256b645072935e9e83",
        "msg_ed0ecbea6bea16fe0367",
        "msg_e9c09e3d70e78ec2e3a5",
        "msg_2228daab0656d917c9b4",
        "msg_4e97379e52d11ae44481",
        "msg_079860b4df098a092582",
        "msg_5b6e3e42db1ef32e7547",
    ];

    [Test]
    public void FrozenPureNoteCreateOracleRoutesFortyOfForty()
    {
        Dictionary<string, CorpusRow> corpus = LoadCorpus();

        Assert.That(PureCreateMessageIds, Has.Length.EqualTo(40));
        Assert.That(
            PureCreateMessageIds.Distinct(StringComparer.Ordinal).ToArray(),
            Has.Length.EqualTo(40));
        foreach (string messageId in PureCreateMessageIds)
        {
            Assert.That(corpus.TryGetValue(messageId, out CorpusRow? row), Is.True, messageId);
            Assert.That(row!.AcceptanceScope, Is.EqualTo("product_1_0"), messageId);
            Assert.That(row.Operations, Is.EqualTo(new[] { "note.manage" }), messageId);

            bool parsed = NaturalNoteRequestParser.TryParse(row.TextLiteral, out RoutedOperation? operation);
            Assert.Multiple(() =>
            {
                Assert.That(parsed, Is.True, $"{messageId}: {row.TextLiteral}");
                Assert.That(operation?.Name, Is.EqualTo("note.create"), messageId);
                Assert.That(operation?.Arguments["title"]?.GetValue<string>(), Is.Not.Empty, messageId);
                Assert.That(operation?.Arguments["content"]?.GetValue<string>(), Is.Not.Empty, messageId);
            });
        }
    }

    [Test]
    public void FrozenFilesystemNoiseAndComposedReminderNeverClaimNoteCreate()
    {
        Dictionary<string, CorpusRow> corpus = LoadCorpus();

        foreach (string messageId in RequiredNegativeMessageIds)
        {
            Assert.That(corpus.TryGetValue(messageId, out CorpusRow? row), Is.True, messageId);
            bool parsed = NaturalNoteRequestParser.TryParse(row!.TextLiteral, out RoutedOperation? operation);

            Assert.Multiple(() =>
            {
                Assert.That(
                    parsed,
                    Is.False,
                    $"{messageId} must remain outside this standalone note slice: {row.TextLiteral}");
                Assert.That(operation, Is.Null, messageId);
            });
        }
    }

    private static Dictionary<string, CorpusRow> LoadCorpus()
    {
        string path = FindCorpusPath();
        var rows = new Dictionary<string, CorpusRow>(StringComparer.Ordinal);
        foreach (string line in File.ReadLines(path))
        {
            using JsonDocument document = JsonDocument.Parse(line);
            JsonElement root = document.RootElement;
            string id = root.GetProperty("message_id").GetString()!;
            string text = root.GetProperty("text_literal").GetString()!;
            string acceptanceScope = root.GetProperty("acceptance_scope").GetString()!;
            string[] operations = root.GetProperty("operations")
                .EnumerateArray()
                .Select(static operation => operation.GetString()!)
                .ToArray();
            rows.Add(id, new CorpusRow(id, text, acceptanceScope, operations));
        }

        return rows;
    }

    private static string FindCorpusPath()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null)
        {
            string candidate = Path.Combine(
                directory.FullName,
                "tests",
                "data",
                "historical_messages.jsonl");
            if (File.Exists(candidate))
            {
                return candidate;
            }

            directory = directory.Parent;
        }

        throw new FileNotFoundException("Could not locate the frozen historical message corpus.");
    }

    private sealed record CorpusRow(
        string MessageId,
        string TextLiteral,
        string AcceptanceScope,
        IReadOnlyList<string> Operations);
}
