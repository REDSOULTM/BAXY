using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class VoiceFeedbackTests
{
    [TestCase("wake", null, "conversation", "voice_wake_listening", "Te escucho.")]
    [TestCase("wake", null, "conversation", "voice_wake_listening", "Estoy listo para ayudarte con lo que necesites.")]
    [TestCase("ignored", "transcript_doubtful", "clarification", "voice_transcript_uncertain", "No alcancé a entenderte. ¿Lo repites?")]
    [TestCase("ignored", "transcript_doubtful", "clarification", "voice_transcript_uncertain", "¿Podrías repetir lo que dijiste?")]
    public async Task VoiceFeedbackUsesSharedComposer(
        string eventName, string? reason, string intent, string cause, string authored)
    {
        UserMessageDraft draft = TurnVisibleFacts.VoiceFeedback(eventName, reason)!;
        Assert.That(draft, Is.Not.Null);
        Assert.That(draft.Intent, Is.EqualTo(intent));
        Assert.That((string?)JsonNode.Parse(draft.Source)!["cause"], Is.EqualTo(cause));
        Assert.That(UserMessagePolicy.IsStructuredFacts(draft.Source), Is.True);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        ModelMessageCompositionOutcome result = await ModelMessageComposer.ComposeAsync(
            draft, string.Empty, facts,
            (_, actualIntent, actualFacts, _, _) =>
            {
                Assert.That(actualIntent, Is.EqualTo(intent));
                Assert.That((string?)actualFacts["situation"], Is.EqualTo(draft.Source));
                return Task.FromResult<MindComposedMessage?>(new MindComposedMessage(authored));
            },
            cpuFallback: false, allowRecovery: false, CancellationToken.None);
        Assert.That(result.Text, Is.EqualTo(authored));
        Assert.That(result.Failure, Is.Null);
    }

    [TestCase("wake_detected", null)]
    [TestCase("ignored", "wake_not_present")]
    [TestCase("ignored", "turn_not_authorized")]
    [TestCase("barge_in", null)]
    public void BackgroundOrIntermediateEventsDoNotCreateReplies(string eventName, string? reason)
    {
        Assert.That(TurnVisibleFacts.VoiceFeedback(eventName, reason), Is.Null);
    }

    [Test]
    public async Task WakeAcknowledgementExpiresWhenListeningStopsButRepeatRequestDoesNot()
    {
        SynchronizationContext? previous = SynchronizationContext.Current;
        MainWindowViewModel viewModel;
        try
        {
            SynchronizationContext.SetSynchronizationContext(new InlineContext());
            viewModel = new MainWindowViewModel();
        }
        finally
        {
            SynchronizationContext.SetSynchronizationContext(previous);
        }

        await using (viewModel)
        {
            var receive = typeof(MainWindowViewModel)
                .GetMethod("OnMindVoiceEvent", BindingFlags.Instance | BindingFlags.NonPublic)!
                .CreateDelegate<Action<JsonObject>>(viewModel);
            var isStale = typeof(MainWindowViewModel)
                .GetMethod("IsStalePendingMessage", BindingFlags.Instance | BindingFlags.NonPublic)!
                .CreateDelegate<Func<PendingModelMessage, bool>>(viewModel);
            PendingModelMessage acknowledgement = Pending("wake", null);
            PendingModelMessage repeat = Pending("ignored", "transcript_doubtful");
            receive(new JsonObject { ["event"] = "state", ["mode"] = "wake" });
            Assert.That(isStale(acknowledgement), Is.False);
            receive(new JsonObject { ["event"] = "state", ["mode"] = "off" });
            Assert.That(isStale(acknowledgement), Is.True);
            Assert.That(isStale(repeat), Is.False);

            typeof(MainWindowViewModel)
                .GetField("_currentTurnTraceId", BindingFlags.Instance | BindingFlags.NonPublic)!
                .SetValue(viewModel, "t1");
            Assert.That(isStale(repeat), Is.True, "A new request supersedes an old repeat prompt.");
        }
    }

    private static PendingModelMessage Pending(string eventName, string? reason)
    {
        UserMessageDraft draft = TurnVisibleFacts.VoiceFeedback(eventName, reason)!;
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        facts["voiceFeedback"] = true;
        return new PendingModelMessage(draft, string.Empty, facts, "t0");
    }

    private sealed class InlineContext : SynchronizationContext
    {
        public override void Post(SendOrPostCallback callback, object? state) => callback(state);
    }
}
