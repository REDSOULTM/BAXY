using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class AudioStatusHandlerTests
{
    private const string EndpointHash =
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    [Test]
    public void DefinitionIsReadOnly()
    {
        var handler = new AudioStatusHandler(new StubProvider());

        Assert.Multiple(() =>
        {
            Assert.That(handler.Definition.Name, Is.EqualTo(AudioOperationIds.Status));
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.ReadOnly));
        });
    }

    [TestCase("null")]
    [TestCase("[]")]
    [TestCase("{\"extra\":true}")]
    public async Task NonEmptyOrNonObjectArgumentsNeverReachProvider(string json)
    {
        var provider = new StubProvider();
        var handler = new AudioStatusHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(json),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(provider.StatusCallCount, Is.Zero);
        });
    }

    [TestCase(37, false, "activo")]
    [TestCase(0, true, "silenciado")]
    public async Task VerifiedObservationIsProjectedWithoutRawEndpointIdentity(
        int volumePercent,
        bool muted,
        string expectedMuteState)
    {
        OperationInvocation invocation = Invocation("{}");
        var receipt = Success(invocation.InvocationId, volumePercent, muted);
        var provider = new StubProvider(status: _ => receipt);
        var handler = new AudioStatusHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);
        JsonElement result = outcome.Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(Message(outcome), Does.Contain($"{volumePercent} %"));
            Assert.That(Message(outcome), Does.Contain(expectedMuteState));
            Assert.That(provider.LastStatusQuery?.InvocationId,
                Is.EqualTo(invocation.InvocationId));
            Assert.That(result.GetProperty("operation").GetString(),
                Is.EqualTo(AudioOperationIds.Status));
            Assert.That(result.GetProperty("targetId").GetString(),
                Is.EqualTo(AudioTargetIds.DefaultOutput));
            Assert.That(result.GetProperty("endpointIdHash").GetString(),
                Is.EqualTo(EndpointHash));
            Assert.That(result.GetProperty("state").GetProperty("volumePercent").GetInt32(),
                Is.EqualTo(volumePercent));
            Assert.That(result.GetProperty("state").GetProperty("muted").GetBoolean(),
                Is.EqualTo(muted));
        });
    }

    [Test]
    public async Task ProviderFailureRemainsUnverifiedAndSanitized()
    {
        OperationInvocation invocation = Invocation("{}");
        var receipt = new AudioStatusReceipt(
            invocation.InvocationId,
            AudioOperationIds.Status,
            AudioTargetIds.DefaultOutput,
            EndpointIdHash: null,
            State: null,
            Verified: false,
            AudioControlErrorCodes.NoDefaultOutput);
        var handler = new AudioStatusHandler(new StubProvider(status: _ => receipt));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.Verified, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(AudioControlErrorCodes.NoDefaultOutput));
            Assert.That(Message(outcome).ToLowerInvariant(), Does.Not.Contain("endpoint"));
        });
    }

    [Test]
    public async Task ForgedEvidenceFailsClosed()
    {
        OperationInvocation invocation = Invocation("{}");
        AudioStatusReceipt forged = Success(invocation.InvocationId, 42, muted: false) with
        {
            EndpointIdHash = "raw-device-id",
        };
        var handler = new AudioStatusHandler(new StubProvider(status: _ => forged));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode,
                Is.EqualTo(AudioControlErrorCodes.VerificationFailed));
        });
    }

    private static AudioStatusReceipt Success(
        string invocationId,
        int volumePercent,
        bool muted) => new(
            invocationId,
            AudioOperationIds.Status,
            AudioTargetIds.DefaultOutput,
            EndpointHash,
            new AudioEndpointState(volumePercent, muted),
            Verified: true,
            ErrorCode: null);

    private static OperationInvocation Invocation(string json) => new(
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        JsonDocument.Parse(json).RootElement.Clone());

    private static string Message(OperationOutcome outcome) =>
        OperationOutcomeNarration.For(AudioOperationIds.Status, outcome);

    private sealed class StubProvider(
        Func<AudioStatusQuery, AudioStatusReceipt>? status = null) : IAudioControlProvider
    {
        private readonly Func<AudioStatusQuery, AudioStatusReceipt> _status =
            status ?? (query => Success(query.InvocationId, 55, muted: false));

        public int StatusCallCount { get; private set; }

        public AudioStatusQuery? LastStatusQuery { get; private set; }

        public ValueTask<AudioStatusReceipt> GetStatusAsync(
            AudioStatusQuery query,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            StatusCallCount++;
            LastStatusQuery = query;
            return ValueTask.FromResult(_status(query));
        }

        public ValueTask<AudioControlReceipt> SetVolumeAsync(
            AudioVolumeCommand command,
            CancellationToken cancellationToken) =>
            throw new InvalidOperationException("Unexpected volume mutation.");

        public ValueTask<AudioControlReceipt> SetMuteAsync(
            AudioMuteCommand command,
            CancellationToken cancellationToken) =>
            throw new InvalidOperationException("Unexpected mute mutation.");
    }
}
