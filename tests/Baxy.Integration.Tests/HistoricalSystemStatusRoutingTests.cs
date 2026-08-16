using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class HistoricalSystemStatusRoutingTests
{
    private const string OracleIdsSha256 =
        "9d55e3fafc60a588da7714ee1dd795378952cc3f986ed166a3dd545b3027f21e";

    private static readonly IReadOnlyDictionary<string, string[]> FrozenOracle =
        new Dictionary<string, string[]>(StringComparer.Ordinal)
        {
            ["cpu_memory"] =
            [
                "msg_1b10f518d3a54a52103a", "msg_20b6293099f2393a3026",
                "msg_23261ba16990dd80130f",
                "msg_5e47a2d7f88129f56a6c", "msg_7128be69af136c3032af",
                "msg_8fa0f789802d70c81573", "msg_b45afb22aa0132d1092a",
                "msg_cd8f172667f68f08e1f3", "msg_fc8f93ee6fb552356737",
            ],
            ["os_memory"] =
            [
                "msg_4c186b4828cf129838d2",
            ],
            ["battery"] =
            [
                "msg_00a8b77f51db69cc6625", "msg_03c69e42c98bec49536e",
                "msg_0b2df230af7f2303d6d2", "msg_0c2c1faad4bf7ca17fd1",
                "msg_1367a802f3c484db00d0", "msg_13ab9b41ffbf6860f88d",
                "msg_1fbb7dc86b947fe738b9", "msg_226a30b0fab310b2893b",
                "msg_2303bb88385a5552c97b", "msg_28ec8a11dbcca85009d4",
                "msg_28fdb57bb44f2db1b65c", "msg_29cd6cc51c6c60557475",
                "msg_330fab34b78c64470515", "msg_33e3d0f43f11dd8a38c5",
                "msg_3401b41bbdb0b91c81cd", "msg_35242ed123d1396bd479",
                "msg_3669594851930777ae61", "msg_37571c47a6774976617a",
                "msg_37ac160341d4e5ad23e2", "msg_381ded3a073eeba2903a",
                "msg_3f359f97357b5dd469d2", "msg_3fe75c578ce9a1e1faef",
                "msg_4252c062f2071e925ab2", "msg_4a2778fda098b4686eec",
                "msg_579b236f7ff82f71f0fc", "msg_58cde7c561ccac797421",
                "msg_6107ebd6e8281cb94feb", "msg_615898d6aaf0a920f7fa",
                "msg_62a1b63fe1482bd6fb30", "msg_687c2cd4248266170a63",
                "msg_8028ef3e3772881729a9", "msg_850e2ee4687c7da9d245",
                "msg_8518b6e7a2392d7bf7b9", "msg_89f3882e515a81b7f3c7",
                "msg_8d1dd3714ddf9e322aff", "msg_9f86bb511b74e3d2b664",
                "msg_a2c2c8a8b31dff96523f", "msg_aa422669e62dddb095a4",
                "msg_aad30185d86d239ce147", "msg_ace7633316285e2c8656",
                "msg_b7c014ef61a6755331e0", "msg_bafac813d014fbb2a15a",
                "msg_bb0bc97c23e0e16718b2", "msg_c0875f8440c94ce6799c",
                "msg_c188deb88836db670e92", "msg_c2e917a658a0224c6d68",
                "msg_c627cd2787014fc97779", "msg_d48f36c9eb67bf79540c",
                "msg_d4d325ae9120ec615055", "msg_d7f98136681c60610e53",
                "msg_d9ba9d655592702c06dd", "msg_e01c75cc87aed22483b8",
                "msg_e44ee8a08234a2745848", "msg_ec21923f796104db8e8e",
                "msg_f8394fb6c47282ed5759", "msg_fa6c2d7609aa682d4c2f",
            ],
            ["disk"] =
            [
                "msg_0660623b5155db643ab1", "msg_1d2ef1e28942279a791c",
                "msg_4b8ae093e066839125ee", "msg_5d99ed85c52a0dc8a51a",
                "msg_7cd3230900ef186e0185", "msg_9359c85e8f250b16b94d",
                "msg_9766c944bc0c9785d6e6", "msg_9a7a5d524a34d96e9724",
                "msg_e45e4ddcff8d049c673d", "msg_ef178564427a36fd2800",
            ],
            ["cpu"] =
            [
                "msg_0c35a4ab3357b902e2de", "msg_1068ffca264cf133e21b",
                "msg_2df3e502cfc925b58696", "msg_3893c62b7c6455ca3fd7",
                "msg_39e94e3e6204fe2cca15", "msg_5e6e437f330520ca1094",
                "msg_775598372e639878cabf", "msg_8db03204a6bb4974fc3c",
                "msg_a258feee1b0b3d323ab7", "msg_dc4d8073ed3639d4a969",
                "msg_e9ec74d817987b707c10", "msg_fa16ccc70caa9c2dd63a",
            ],
            ["memory"] =
            [
                "msg_0860401a0578783b147b", "msg_0a57b5b49653e71b6321",
                "msg_1154418458a05d3a4f0d", "msg_123626fa859a6b023cf9",
                "msg_160a0d65c84b0414480f", "msg_2b867fdbfa754c00e9ee",
                "msg_2f3e6242f3cd272c1c2f", "msg_3167fccc13f13ba3d119",
                "msg_37eac1ca65ec94567c41", "msg_38ab75e09b274d9ecfb4",
                "msg_39b3a744540a01a89e00", "msg_3ff06df1faddf685121c",
                "msg_5f79a1eb6731168f7a04", "msg_65a3b4ffe69ce9a4c247",
                "msg_7b6fdd5c68d0fd40f41e", "msg_81c578c76efb6415c96d",
                "msg_9b3e16550b172b7f6b7c", "msg_a8a4dd88aff90bf93447",
                "msg_a8fc5cafaae468cf0d6c", "msg_bdfe932b38aee47486f5",
                "msg_c08f974a34fcc985ac77", "msg_c2ee9957c3fc225a613a",
                "msg_da4598700c095c819f5d", "msg_e390ce61eb73d2499048",
                "msg_f0c7934bff964e689728",
            ],
        };

    private static readonly string[] FrozenOutOfSliceIds =
    [
        "msg_b360355cf3bd084c8ee7", // precios GPU
        "msg_2bbdf20a7c33da9d1a5e", // procesos por CPU
        "msg_3fd8baee41adca84b928", // lista de procesos por CPU
        "msg_ff07b4b9b35fa485a05c", // lista de procesos por RAM
        "msg_2c7f53e3c5151eae045c", // fecha + RAM
        "msg_0f4f82ecaf27cb692ca3", // hora + IP + RAM
        "msg_7c49d0bfdb816988a82e", // RAM de un proceso concreto
        "msg_ae78f1e68cca6ba406aa", // precio de CPU
    ];

    [Test]
    public void FrozenReadOnlyStatusOracleRoutesOneHundredThirteenOfOneHundredThirteen()
    {
        Dictionary<string, CorpusRow> corpus = LoadCorpus();
        (string Scope, string Id)[] expected = FrozenOracle
            .SelectMany(static pair => pair.Value.Select(id => (pair.Key, id)))
            .OrderBy(static item => item.id, StringComparer.Ordinal)
            .Select(static item => (item.Key, item.id))
            .ToArray();
        string digest = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(
            string.Concat(string.Join('\n', expected.Select(static item => item.Id)), "\n"))))
            .ToLowerInvariant();

        Assert.Multiple(() =>
        {
            Assert.That(expected, Has.Length.EqualTo(113));
            Assert.That(
                expected.Select(static item => item.Id).Distinct().ToArray(),
                Has.Length.EqualTo(113));
            Assert.That(digest, Is.EqualTo(OracleIdsSha256));
        });

        var literals = new HashSet<string>(StringComparer.Ordinal);
        var sources = new HashSet<string>(StringComparer.Ordinal);
        var missions = new HashSet<string>(StringComparer.Ordinal);
        foreach ((string expectedScope, string messageId) in expected)
        {
            Assert.That(corpus.TryGetValue(messageId, out CorpusRow? row), Is.True, messageId);
            Assert.Multiple(() =>
            {
                Assert.That(row!.AcceptanceScope, Is.EqualTo("product_1_0"), messageId);
                Assert.That(row.Class, Is.EqualTo("user_mission"), messageId);
                Assert.That(row.Operations, Is.EqualTo(new[] { "system.status" }), messageId);
            });

            bool parsed = NaturalNoteRequestParser.TryParse(
                row!.TextLiteral,
                out RoutedOperation? operation);
            Assert.Multiple(() =>
            {
                Assert.That(parsed, Is.True, $"{messageId}: {row.TextLiteral}");
                Assert.That(operation?.Name, Is.EqualTo("system.status"), messageId);
                Assert.That(
                    operation?.Arguments["scope"]?.GetValue<string>(),
                    Is.EqualTo(expectedScope),
                    messageId);
                Assert.That(operation?.Arguments, Has.Count.EqualTo(1), messageId);
            });

            literals.Add(row.TextLiteral);
            sources.Add(row.Source);
            missions.Add(row.CanonicalMissionId);
        }

        Assert.Multiple(() =>
        {
            Assert.That(literals, Has.Count.EqualTo(50));
            Assert.That(sources, Has.Count.EqualTo(9));
            Assert.That(missions, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public void FrozenGpuKnowledgeProcessAndCompositionRowsRemainOutsideThisSlice()
    {
        Dictionary<string, CorpusRow> corpus = LoadCorpus();
        foreach (string messageId in FrozenOutOfSliceIds)
        {
            Assert.That(corpus.TryGetValue(messageId, out CorpusRow? row), Is.True, messageId);
            bool parsed = NaturalNoteRequestParser.TryParse(
                row!.TextLiteral,
                out RoutedOperation? operation);

            Assert.Multiple(() =>
            {
                Assert.That(parsed, Is.False, $"{messageId}: {row.TextLiteral}");
                Assert.That(operation, Is.Null, messageId);
            });
        }
    }

    private static Dictionary<string, CorpusRow> LoadCorpus()
    {
        var rows = new Dictionary<string, CorpusRow>(StringComparer.Ordinal);
        foreach (string line in File.ReadLines(FindCorpusPath()))
        {
            using JsonDocument document = JsonDocument.Parse(line);
            JsonElement root = document.RootElement;
            string id = root.GetProperty("message_id").GetString()!;
            rows.Add(id, new CorpusRow(
                root.GetProperty("text_literal").GetString()!,
                root.GetProperty("acceptance_scope").GetString()!,
                root.GetProperty("class").GetString()!,
                root.GetProperty("operations")
                    .EnumerateArray()
                    .Select(static value => value.GetString()!)
                    .ToArray(),
                root.GetProperty("source").GetString()!,
                root.GetProperty("canonical_mission_id").GetString()!));
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
        string TextLiteral,
        string AcceptanceScope,
        string Class,
        IReadOnlyList<string> Operations,
        string Source,
        string CanonicalMissionId);
}
