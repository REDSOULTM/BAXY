using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests.Audio;

// W2 (A2, A3, A5: «silencia Lumitrak» muted the whole PC). What is muted is typed: scope «app» mutes one application's
// own sessions, or nothing when it has none; the whole PC is muted only by a call that says scope «pc». No real audio:
// the endpoint and the sessions are substitutes.
[TestFixture]
public sealed class AppMuteTests
{
    [Test]
    public void TheMuteSaysWhatItMutesAndTheWholePcIsNotTheDefault()
    {
        JsonElement schema = ProductCatalog.CreateToolDescriptor(ProductCatalog.CreateDefinition("audio.mute"))
            .ArgumentsSchema;

        Assert.Multiple(() =>
        {
            Assert.That(schema.GetProperty("required").EnumerateArray().Select(static e => e.GetString()),
                Does.Contain("scope"));
            Assert.That(schema.GetProperty("properties").GetProperty("scope").GetProperty("enum").EnumerateArray()
                .Select(static e => e.GetString()), Is.EquivalentTo(new[] { "app", "pc" }));
            Assert.That(schema.GetProperty("properties").TryGetProperty("app", out _), Is.True);
        });
    }

    [Test]
    public async Task AnApplicationsMuteNeverReachesTheWholePc()
    {
        var endpoint = new CountingEndpoint();
        int applicationCalls = 0;
        var handler = new AudioMuteHandler(endpoint, (_, _) =>
        {
            applicationCalls++;
            return ValueTask.FromResult(OperationOutcome.Failure(AppSessionNotFound.MuteErrorCode));
        });

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"scope":"app","app":"Lumitrak","state":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(endpoint.Mutes, Is.Zero);
            Assert.That(applicationCalls, Is.EqualTo(1));
            Assert.That(outcome.ErrorCode, Is.EqualTo(AppSessionNotFound.MuteErrorCode));
        });
    }

    [TestCase("""{"state":true}""")]
    [TestCase("""{"scope":"pc","app":"Lumitrak","state":true}""")]
    [TestCase("""{"scope":"app","state":true}""")]
    [TestCase("""{"scope":"todo","state":true}""")]
    public async Task AMuteThatDoesNotSayItsScopeRunsNothing(string arguments)
    {
        var endpoint = new CountingEndpoint();
        var handler = new AudioMuteHandler(endpoint, static (_, _) => throw new AssertionException("no app call"));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(endpoint.Mutes, Is.Zero);
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
        });
    }

    // Control: the whole PC said as such is muted as before.
    [Test]
    public async Task TheWholePcSaidAsSuchIsMuted()
    {
        var endpoint = new CountingEndpoint();
        var handler = new AudioMuteHandler(endpoint, static (_, _) => throw new AssertionException("no app call"));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"scope":"pc","state":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(endpoint.Mutes, Is.EqualTo(1));
            Assert.That(outcome.Succeeded && outcome.Verified, Is.True, outcome.ErrorCode);
        });
    }

    [Test]
    public async Task AnApplicationWithNoSoundIsNotMutedAndTheResultSaysWhatPlays()
    {
        bool crossed = false;
        var adapter = new WindowsAppMuteAdapter(
            (_, _, beforeEffect, _) =>
            {
                crossed = beforeEffect is null;
                return null;
            },
            static () => [new AudioSessionProgram("Spotify", "Spotify"), new AudioSessionProgram("msedge", null)]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.mute", Json("""{"scope":"app","app":"Lumitrak","state":true}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(crossed, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("app_audio_not_found"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(result.GetProperty("muted").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("appsWithAudio").EnumerateArray().Select(static e => e.GetString()),
                Is.EqualTo(new[] { "Spotify", "msedge" }));
            Assert.That(result.GetProperty("next").GetString(), Does.StartWith("nothing was muted")
                .And.Contain("\"Lumitrak\"").And.Not.Contain("audio_mute"));
        });
    }

    // One application with audio whose name matches what was said, by form: the next leads with the same call naming it.
    [Test]
    public async Task AnApplicationWhoseNameMatchesOneThatPlaysLeadsWithThatCall()
    {
        var adapter = new WindowsAppMuteAdapter(
            static (_, _, _, _) => null,
            static () => [new AudioSessionProgram("Spotify", "Spotify")]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.mute", Json("""{"scope":"app","app":"la musica de spotify","state":true}"""), CancellationToken.None);

        Assert.That(receipt.Result!.Value.GetProperty("next").GetString(),
            Does.StartWith("audio_mute").And.Contain("\"app\":\"Spotify\"").And.Contain("\"scope\":\"app\""));
    }

    [Test]
    public async Task AnApplicationThatPlaysIsMutedAndSaysSo()
    {
        bool? asked = null;
        var adapter = new WindowsAppMuteAdapter((_, muted, beforeEffect, _) =>
        {
            beforeEffect?.Invoke();
            asked = muted;
            return new ApplicationSessionAdjustment("Spotify", 2, 64, 64, true, "endpoint-1", Changed: true);
        });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.mute", Json("""{"scope":"app","app":"spotify","state":true}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.True);
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(result.GetProperty("muted").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("processName").GetString(), Is.EqualTo("Spotify"));
            Assert.That(result.GetProperty("level").GetInt32(), Is.EqualTo(64));
        });
    }

    [Test]
    public async Task AnApplicationMuteThatDidNotTakeSaysTheStateReadAfter()
    {
        var adapter = new WindowsAppMuteAdapter((_, _, beforeEffect, _) =>
        {
            beforeEffect?.Invoke();
            return new ApplicationSessionAdjustment("Spotify", 1, 64, 64, false, "endpoint-1", Changed: false);
        });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.mute", Json("""{"scope":"app","app":"spotify","state":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("mute_postread_mismatch"));
            Assert.That(receipt.Result!.Value.GetProperty("stateAfter").GetProperty("muted").GetBoolean(), Is.False);
        });
    }

    // W3 (R6-3): «discord y spotify» matched two applications; the receipt names both, not only the first.
    [Test]
    public async Task AMuteThatMatchedSeveralApplicationsNamesEveryOne()
    {
        var adapter = new WindowsAppMuteAdapter((_, _, beforeEffect, _) =>
        {
            beforeEffect?.Invoke();
            return new ApplicationSessionAdjustment("Discord", 3, 64, 64, true, "endpoint-1", Changed: true,
                WindowsCoreAudioPlatform.SessionsByProcess(["Discord", "Spotify", "Discord"], [true, true, true]));
        });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.mute", Json("""{"scope":"app","app":"discord y spotify","state":true}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        JsonElement[] processes = [.. result.GetProperty("processes").EnumerateArray()];
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(processes.Select(static p => p.GetProperty("processName").GetString()),
                Is.EqualTo(new[] { "Discord", "Spotify" }));
            Assert.That(processes.Select(static p => p.GetProperty("sessionCount").GetInt32()), Is.EqualTo(new[] { 2, 1 }));
            Assert.That(processes.All(static p => p.GetProperty("muted").GetBoolean()), Is.True);
            Assert.That(result.TryGetProperty("processName", out _), Is.False);
            Assert.That(result.GetProperty("sessionCount").GetInt32(), Is.EqualTo(3));
        });
    }

    // Control: one application keeps the receipt it had.
    [Test]
    public async Task AMuteOfOneApplicationNamesItsProcess()
    {
        var adapter = new WindowsAppMuteAdapter(static (_, _, _, _) =>
            new ApplicationSessionAdjustment("Spotify", 2, 64, 64, true, "endpoint-1", Changed: true,
                WindowsCoreAudioPlatform.SessionsByProcess(["Spotify", "Spotify"], [true, true])));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.mute", Json("""{"scope":"app","app":"spotify","state":true}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("processName").GetString(), Is.EqualTo("Spotify"));
            Assert.That(result.TryGetProperty("processes", out _), Is.False);
        });
    }

    // W3 (R6-6): an unmute that left one session muted is not done; a mute is done when every session is muted.
    [TestCase(false, new[] { true, true }, new[] { false, true }, true)]
    [TestCase(false, new[] { true, true }, new[] { false, false }, false)]
    [TestCase(true, new[] { false, false }, new[] { true, false }, false)]
    [TestCase(true, new[] { false, false }, new[] { true, true }, true)]
    public void TheStateReadAfterIsMutedWhileWhatWasAskedIsNotReached(
        bool mute, bool[] before, bool[] after, bool muted) =>
        Assert.That(WindowsCoreAudioPlatform.MutedAfter(mute, before, after), Is.EqualTo(muted));

    // W3 (R6-1, R6-5): unmuting an application with scope app reaches its sessions and says the state read after.
    [Test]
    public async Task AnApplicationIsUnmutedWithScopeApp()
    {
        bool? asked = null;
        var adapter = new WindowsAppMuteAdapter((_, muted, beforeEffect, _) =>
        {
            beforeEffect?.Invoke();
            asked = muted;
            return new ApplicationSessionAdjustment("Spotify", 1, 64, 64, false, "endpoint-1", Changed: true);
        });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.mute", Json("""{"scope":"app","app":"spotify","state":false}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.False);
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Result!.Value.GetProperty("muted").GetBoolean(), Is.False);
        });
    }

    // W3 (R6-5): an application with no session had no mute read, so its unmute does not say muted false.
    [Test]
    public async Task AnUnmuteOfAnApplicationWithNoSoundDoesNotSayItsMute()
    {
        var adapter = new WindowsAppMuteAdapter(
            static (_, _, _, _) => null,
            static () => [new AudioSessionProgram("Spotify", "Spotify")]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.mute", Json("""{"scope":"app","app":"Lumitrak","state":false}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("app_audio_not_found"));
            Assert.That(result.TryGetProperty("muted", out _), Is.False);
            Assert.That(result.GetProperty("next").GetString(), Does.StartWith("nothing was unmuted")
                .And.Contain("could not be read").And.Not.Contain("nothing was muted"));
        });
    }

    // W3 (R6-1): «quítale el mute» after an application was muted unmutes the whole PC; the result says which
    // applications stay muted on their own, and how to unmute one, so it is not taken for all the sound back.
    [TestCase(true, "the PC's sound is on; ")]
    [TestCase(false, "the PC's sound was already on, so this call changed nothing; ")]
    public async Task TheWholePcsUnmuteSaysWhichApplicationsStayMuted(bool pcMuted, string start)
    {
        var endpoint = new CountingEndpoint(pcMuted);
        var handler = new AudioMuteHandler(endpoint, static (_, _) => throw new AssertionException("no app call"),
            static () => ["Spotify"]);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"scope":"pc","state":false}"""), CancellationToken.None);

        JsonElement result = outcome.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded && outcome.Verified, Is.True, outcome.ErrorCode);
            Assert.That(result.GetProperty("appsMuted").EnumerateArray().Select(static e => e.GetString()),
                Is.EqualTo(new[] { "Spotify" }));
            Assert.That(result.GetProperty("next").GetString(), Does.StartWith(start).And.Contain("Spotify")
                .And.Contain("scope \"app\", state false"));
            Assert.That(result.GetProperty("final").GetProperty("muted").GetBoolean(), Is.False);
        });
    }

    // Controls: a mute of the whole PC, or an unmute with no application muted, keeps the result it had.
    [TestCase(true, new[] { "Spotify" })]
    [TestCase(false, new string[0])]
    public async Task TheWholePcsMuteOrAnUnmuteWithNoApplicationMutedSaysNoApplications(bool state, string[] muted)
    {
        var endpoint = new CountingEndpoint();
        var handler = new AudioMuteHandler(endpoint, static (_, _) => throw new AssertionException("no app call"),
            () => muted);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation($$"""{"scope":"pc","state":{{(state ? "true" : "false")}}}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.TryGetProperty("appsMuted", out _), Is.False);
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out _), Is.False);
        });
    }

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private static OperationInvocation Invocation(string arguments) =>
        new("request", "mission", "invocation", Json(arguments));

    private sealed class CountingEndpoint(bool muted = false) : IAudioControlProvider
    {
        private static readonly string Hash = new('a', 64);
        private AudioEndpointState _state = new(40, muted);

        internal int Mutes { get; private set; }

        public ValueTask<AudioStatusReceipt> GetStatusAsync(AudioStatusQuery query, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new AudioStatusReceipt(query.InvocationId, AudioOperationIds.Status,
                AudioTargetIds.DefaultOutput, Hash, _state, true, null));

        public ValueTask<AudioControlReceipt> SetVolumeAsync(AudioVolumeCommand command, CancellationToken cancellationToken) =>
            throw new AssertionException("no volume");

        public ValueTask<AudioControlReceipt> SetMuteAsync(AudioMuteCommand command, CancellationToken cancellationToken)
        {
            Mutes++;
            AudioEndpointState before = _state;
            _state = before with { Muted = command.State };
            return ValueTask.FromResult(new AudioControlReceipt(command.InvocationId, AudioOperationIds.Mute,
                AudioTargetIds.DefaultOutput, Hash, null, command.State, before, _state, Applied: true,
                Reconciled: false, Verified: true, ErrorCode: null));
        }
    }
}
