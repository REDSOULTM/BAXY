using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// Al máximo, K-2 refinada (2026-10-22): Enter or space with neither target nor onto asks in normal mode only where it
/// may send or run something. The policy still asks (it cannot see where the key lands); the handler's preflight reads
/// the window the key goes to and lowers it when that window is neither a messaging client nor a console. A window that
/// is one of them, or that cannot be read, keeps the question.
/// </summary>
[TestFixture]
public sealed class KeyPressLandingTests
{
    // Window 1: a browser's search box; 2: a messaging client; 3: a console; anything else cannot be read.
    private static readonly HashSet<long> Ordinary = [1];

    [Test]
    public async Task EnterWithNoTargetInASearchWindowGoesWithoutAsking()
    {
        (OperationResponse response, LandingHandler handler) = await Press("""{"key":"enter","window":1}""");

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(handler.PreflightCount, Is.EqualTo(1));
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
        });
    }

    [TestCase("""{"key":"enter","window":2}""")]
    [TestCase("""{"key":"space","window":2}""")]
    [TestCase("""{"key":"enter","window":3}""")]
    [TestCase("""{"key":"enter","window":9}""")]
    [TestCase("""{"key":"enter"}""")]
    public async Task EnterWithNoTargetInAMessagingConsoleOrUnknownWindowAsks(string arguments)
    {
        (OperationResponse response, LandingHandler handler) = await Press(arguments);

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    // Contracaso: what the step declares is judged as before, whatever window it names: onto a send control it asks.
    [Test]
    public async Task ADeclaredLandingIsJudgedAsBefore()
    {
        (OperationResponse response, LandingHandler handler) = await Press(
            """{"key":"enter","window":1,"onto":"Enviar"}""");

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    // Contracaso: a lowered risk lifts only the undeclared-landing rule, never what the arguments say (an overwrite).
    [Test]
    public void ALoweredPressStillAsksForWhatItsArgumentsSay()
    {
        JsonElement overwrite = JsonDocument.Parse("""{"key":"enter","consequence":"overwrite"}""").RootElement.Clone();
        JsonElement plain = JsonDocument.Parse("""{"key":"enter"}""").RootElement.Clone();

        Assert.Multiple(() =>
        {
            Assert.That(RiskPolicy.Evaluate(OperationRisk.Reversible, ConfirmationMode.Normal, "input.key.press", overwrite,
                landingRead: true), Is.EqualTo(PolicyDecision.RequireConfirmation));
            Assert.That(RiskPolicy.Evaluate(OperationRisk.Reversible, ConfirmationMode.Normal, "input.key.press", plain,
                landingRead: true), Is.EqualTo(PolicyDecision.Allow));
            Assert.That(RiskPolicy.Evaluate(OperationRisk.Reversible, ConfirmationMode.Normal, "input.key.press", plain),
                Is.EqualTo(PolicyDecision.RequireConfirmation));
        });
    }

    private static async Task<(OperationResponse, LandingHandler)> Press(string arguments)
    {
        var handler = new LandingHandler();
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationResponse response = await engine.ExecuteAsync(
            new OperationRequest(
                ProtocolTypes.OperationRequest,
                Guid.NewGuid().ToString("D"),
                Guid.NewGuid().ToString("D"),
                Guid.NewGuid().ToString("D"),
                "input.key.press",
                JsonDocument.Parse(arguments).RootElement.Clone()),
            CancellationToken.None);
        return (response, handler);
    }

    // The Core handler's shape: lowered only on a window it read as ordinary; otherwise the declared risk stands.
    private sealed class LandingHandler : IOperationHandler, IInvocationPreflight
    {
        public int ExecutionCount { get; private set; }

        public int PreflightCount { get; private set; }

        public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("input.key.press");

        public ValueTask<InvocationPreflightResult> PreflightAsync(JsonElement arguments, CancellationToken cancellationToken)
        {
            PreflightCount++;
            bool ordinary = RiskPolicy.PressesUndeclared("input.key.press", arguments)
                && arguments.TryGetProperty("window", out JsonElement window)
                && Ordinary.Contains(window.GetInt64());
            return ValueTask.FromResult(ordinary
                ? InvocationPreflightResult.Lowered(OperationRisk.Reversible)
                : InvocationPreflightResult.Proceed);
        }

        public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
        {
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Success(invocation.Arguments));
        }
    }
}
