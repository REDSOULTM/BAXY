using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M108 (M107's report): on a verified effect the final gate let through a promise of the act («Voy a hacerlo
/// enseguida.», «I'll do it right away») and contract tokens («verified=true succeeded=true», field names, error codes,
/// camelCase identifiers, JSON fragments). The App's twin judges the same as the mind
/// (llm.visible_reply_promises_the_act, llm.visible_reply_leaks_a_contract_token): tests/data/c03_m108_gate_twins.json
/// is read on both sides. Every phrasing here is our own.
/// </summary>
[TestFixture]
public sealed class M108PuertaTests
{
    private const string BluetoothOff =
        """{"kind":"operation","operation":"bluetooth.radio.set","polarity":"success","verified":true,"succeeded":true,"observed":{"state":false}}""";

    private const string BluetoothFailed =
        """{"kind":"operation","operation":"bluetooth.radio.set","polarity":"failure","verified":false,"succeeded":false,"error":"provider_failed"}""";

    private static JsonObject Fixture() => (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
        FindRepositoryRoot(), "tests", "data", "c03_m108_gate_twins.json")))!;

    private static IEnumerable<TestCaseData> PromiseCases()
    {
        int index = 0;
        foreach (JsonNode? row in (JsonArray)Fixture()["promises"]!)
        {
            yield return new TestCaseData((string)row!["reply"]!, (bool)row["promise"]!).SetName($"Promise({index++})");
        }
    }

    private static IEnumerable<TestCaseData> TokenCases()
    {
        int index = 0;
        foreach (JsonNode? row in (JsonArray)Fixture()["tokens"]!)
        {
            yield return new TestCaseData(
                (string)row!["reply"]!, row["situation"]!.ToJsonString(), (string)row["said"]!, (bool)row["leaks"]!)
                .SetName($"Token({index++})");
        }
    }

    [TestCaseSource(nameof(PromiseCases))]
    public void TheAppReadsAPromiseAsTheMindDoes(string reply, bool promise) =>
        Assert.That(UserMessagePolicy.PromisesTheAct(reply), Is.EqualTo(promise), reply);

    [TestCaseSource(nameof(TokenCases))]
    public void TheAppReadsAContractTokenAsTheMindDoes(string reply, string situation, string said, bool leaks) =>
        Assert.That(UserMessagePolicy.LeaksContractToken(reply, situation, said), Is.EqualTo(leaks), reply);

    [TestCase("Voy a hacerlo enseguida.", "apagá el bluetooth")]
    [TestCase("I'll do it right away.", "turn the bluetooth off")]
    [TestCase("Procederé a apagar el bluetooth.", "apagá el bluetooth")]
    public void AVerifiedEffectIsNeverPromised(string reply, string said)
    {
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(reply, new UserMessageDraft(BluetoothOff, "status", null), said),
            Is.EqualTo("promised_effect"));
        // A failure promised nothing that happened: its own checks judge it, not this one.
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(reply, new UserMessageDraft(BluetoothFailed, "error", null), said),
            Is.Not.EqualTo("promised_effect"));
    }

    [TestCase("Listo, verified=true succeeded=true.")]
    [TestCase("Apagué el Bluetooth (succeeded: true).")]
    [TestCase("Apagué el Bluetooth: {\"state\": \"off\"}.")]
    [TestCase("Apagué el Bluetooth; state=off.")]
    [TestCase("Apagué el Bluetooth con el código 0x80070005.")]
    public void AContractTokenInAReportIsInternalCode(string reply) =>
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                reply, new UserMessageDraft(BluetoothOff, "status", null), "apagá el bluetooth"),
            Is.EqualTo("internal_code"));

    [Test]
    public void AReportToldDoneStillPublishes()
    {
        var draft = new UserMessageDraft(BluetoothOff, "status", null);
        Assert.Multiple(() =>
        {
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason("Apagué el Bluetooth.", draft, "apagá el bluetooth"),
                Is.Null);
            // The floor every verified action falls back on passes the same gate.
            Assert.That(
                ModelMessageComposer.DeterministicFinal(
                    draft, "apagá el bluetooth", ModelMessageComposer.CreateFacts(draft), "Voy a hacerlo enseguida."),
                Is.EqualTo("Apagué el Bluetooth."));
        });
    }

    private static string FindRepositoryRoot()
    {
        // Read while the cases are built, before any test context exists.
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException("No repository root above the test directory.");
    }
}
