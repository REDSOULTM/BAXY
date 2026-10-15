using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización, encargo C (banco c2, 2.ª corrida de lug-1): «abrí la página de Rocket League en Steam» reads as out
/// of this world by «rocket», so the conversation checks judged the verified mission's report, and «Listo, estoy en
/// «rocket league».» died as unverified_success: the turn ended with no answer. A report of a result the Core verified
/// claims a verified success; an unverified one still cannot say «Listo».
/// </summary>
[TestFixture]
public sealed class EstabCLugaresFinalTests
{
    private const string Request = "abrí la página de Rocket League en Steam";

    private static string Mission(bool verified)
    {
        string state = verified ? "true" : "false";
        return "{\"kind\":\"operation\",\"operation\":\"mission.computer.use\",\"polarity\":\""
            + (verified ? "success" : "failure") + "\",\"verified\":" + state + ",\"succeeded\":" + state
            + ",\"observed\":{\"goal\":\"ir a pagina de rocket league\",\"application\":\"Steam\",\"reached\":" + state + "}}";
    }

    private static async Task<string?> PublishedAsync(bool verified, string mindText)
    {
        var draft = new UserMessageDraft(Mission(verified), "status", null);
        ModelMessageCompositionOutcome outcome = await ModelMessageComposer.ComposeAsync(
            draft, Request, ModelMessageComposer.CreateFacts(draft),
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(new(mindText, Reproducible: true)),
            cpuFallback: false, allowRecovery: true, CancellationToken.None);
        return outcome.Text ?? "rejected: " + outcome.Failure;
    }

    [Test]
    public async Task AVerifiedArrivalIsToldEvenWhenTheRequestReadsAsOutOfThisWorld()
    {
        const string said = "Listo, estoy en «rocket league».";
        Assert.That(await PublishedAsync(verified: true, said), Is.EqualTo(said));
    }

    [Test]
    public void AnUnverifiedSuccessIsStillRefused() =>
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(Request, "Listo, estoy en «rocket league»."),
            Is.EqualTo("unverified_success"));
}
