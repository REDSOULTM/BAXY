using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;

namespace Baxy.Core.Operations;

// W2 (A2, A3, A5: «silencia Lumitrak» muted the whole PC): what is muted is typed. Scope «pc» is the default output
// (this provider, as before); scope «app» is one application's audio sessions (muteApplication, the per-app mute of the
// mixer), which mutes nothing when the application has none and says so. A call without a scope runs nothing: the whole
// PC is muted only when the call says so.
// W3 (R6-1): an application's own mute is apart from the PC's and persists across restarts (Microsoft Learn, Audio
// Sessions), so the whole PC's unmute says which applications stay muted (mutedApplications, read after it).
internal sealed class AudioMuteHandler(
    IAudioControlProvider provider,
    Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> muteApplication,
    Func<IReadOnlyList<string>>? mutedApplications = null) : IOperationHandler
{
    private readonly IAudioControlProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));
    private readonly Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> _muteApplication =
        muteApplication ?? throw new ArgumentNullException(nameof(muteApplication));
    private readonly Func<IReadOnlyList<string>> _mutedApplications = mutedApplications ?? (static () => []);

    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition(AudioOperationIds.Mute);

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!HasOnlyMuteArguments(invocation.Arguments))
        {
            return OperationOutcome.InvalidArguments(Definition, invocation.Arguments);
        }

        AudioMuteArguments arguments;
        try
        {
            arguments = JsonSerializer.Deserialize(
                invocation.Arguments,
                CoreJsonContext.Default.AudioMuteArguments)
                ?? throw new JsonException("Arguments cannot be null.");
        }
        catch (JsonException)
        {
            return OperationOutcome.InvalidArguments(Definition, invocation.Arguments);
        }

        bool named = !string.IsNullOrWhiteSpace(arguments.App);
        if (arguments.Scope == "app" && named)
        {
            return await _muteApplication(invocation, cancellationToken).ConfigureAwait(false);
        }

        if (arguments.Scope != "pc" || named)
        {
            return OperationOutcome.InvalidArguments(Definition, invocation.Arguments);
        }

        AudioControlReceipt receipt = await _provider.SetMuteAsync(
            new AudioMuteCommand(invocation.InvocationId, arguments.State),
            cancellationToken).ConfigureAwait(false);
        if (!AudioControlEvidence.HasConsistentEnvelope(
                receipt,
                invocation.InvocationId,
                AudioOperationIds.Mute,
                requestedLevel: null,
                arguments.State))
        {
            return AudioControlEvidence.VerificationFailure(receipt);
        }

        if (!receipt.Verified)
        {
            return AudioControlEvidence.ProviderFailure(receipt);
        }

        AudioEndpointState baseline = receipt.Baseline!;
        AudioEndpointState final = receipt.Final!;
        if (final.Muted != arguments.State
            || baseline.VolumePercent != final.VolumePercent)
        {
            return AudioControlEvidence.VerificationFailure(receipt, final);
        }

        AudioStatusReceipt observed = await _provider.GetStatusAsync(
            new AudioStatusQuery(invocation.InvocationId),
            cancellationToken).ConfigureAwait(false);
        if (!AudioControlEvidence.MatchesIndependentStatus(receipt, observed))
        {
            return AudioControlEvidence.VerificationFailure(receipt, AudioControlEvidence.ReadAfter(receipt, observed));
        }

        JsonElement serialized = AudioControlEvidence.SerializeVerified(receipt);
        if (!arguments.State && _mutedApplications() is { Count: > 0 } silent)
        {
            serialized = WithApplicationsMuted(serialized, silent, alreadyOn: !baseline.Muted);
        }
        return OperationOutcome.Success(serialized);
    }

    // W3 (R6-1): the PC's sound is on and these applications' own mute is still on; the model decides whether the
    // person meant one of them. Anthropic, «Writing effective tools for agents»: a result with the context the next
    // step needs instead of a bare state. alreadyOn: the PC was not muted, so the call changed nothing (said plainly: with
    // «the PC's sound is on» alone the model answered «the PC is sounding again», 2 of 2 on W3's held-out).
    private static JsonElement WithApplicationsMuted(JsonElement serialized, IReadOnlyList<string> silent, bool alreadyOn)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            foreach (JsonProperty property in serialized.EnumerateObject())
            {
                property.WriteTo(writer);
            }
            writer.WriteStartArray("appsMuted");
            foreach (string application in silent)
            {
                writer.WriteStringValue(application);
            }
            writer.WriteEndArray();
            writer.WriteString("next", (alreadyOn ? "the PC's sound was already on, so this call changed nothing; "
                    : "the PC's sound is on; ") + "these applications have their own mute on and stay "
                + $"silent until it is taken off: {string.Join(", ", silent)}. If the person meant one of them, "
                + $"{WireNames.Of(AudioOperationIds.Mute)} with scope \"app\", state false and its name in app unmutes it");
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }

    // The arguments are state (a boolean), scope and app (strings), and nothing else.
    private static bool HasOnlyMuteArguments(JsonElement arguments)
    {
        if (arguments.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        foreach (JsonProperty property in arguments.EnumerateObject())
        {
            bool expected = property.Name switch
            {
                "state" => property.Value.ValueKind is JsonValueKind.True or JsonValueKind.False,
                "scope" or "app" => property.Value.ValueKind == JsonValueKind.String,
                _ => false,
            };
            if (!expected)
            {
                return false;
            }
        }

        return true;
    }
}
