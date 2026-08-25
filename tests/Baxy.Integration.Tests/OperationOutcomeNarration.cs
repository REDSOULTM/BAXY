using System.Text.Json;
using Baxy.App;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

internal static class OperationOutcomeNarration
{
    internal static string For(string operation, OperationOutcome outcome) =>
        ProductOperationNarrator.Instance.Narrate(operation, outcome);

    internal static JsonElement AssertFacts(string operation, OperationOutcome outcome)
    {
        string source = For(operation, outcome);
        using JsonDocument document = JsonDocument.Parse(source);
        JsonElement facts = document.RootElement.Clone();
        bool verifiedSuccess = outcome.Succeeded && outcome.Verified;

        Assert.Multiple(() =>
        {
            Assert.That(UserMessagePolicy.IsStructuredFacts(source), Is.True);
            Assert.That(UserMessagePolicy.IsSafe(source), Is.True);
            Assert.That(facts.GetProperty("kind").GetString(), Is.EqualTo("operation"));
            Assert.That(facts.GetProperty("operation").GetString(), Is.EqualTo(operation));
            Assert.That(
                facts.GetProperty("polarity").GetString(),
                Is.EqualTo(verifiedSuccess ? "success" : "failure"));
            Assert.That(facts.GetProperty("verified").GetBoolean(), Is.EqualTo(outcome.Verified));
            Assert.That(facts.GetProperty("succeeded").GetBoolean(), Is.EqualTo(outcome.Succeeded));
            Assert.That(
                facts.TryGetProperty("error", out JsonElement error)
                    ? error.GetString()
                    : null,
                Is.EqualTo(outcome.ErrorCode));
            Assert.That(
                facts.TryGetProperty("effectUncertain", out JsonElement uncertain)
                    && uncertain.GetBoolean(),
                Is.EqualTo(outcome.EffectMayHaveOccurred));
        });

        return facts;
    }
}
