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

    // Ronda 25 (latency): the boot greeting loses its moment when the person submits, not when the turn starts 0.7-1.2 s
    // later (after the request's own parsing), so its composition never takes the mind's serial lane ahead of the request
    // (35 of 72 first turns of the bench waited ~1 s behind it). Contracase: a greeting queued in the turn that asked for
    // it («hola») keeps its moment.
    [Test]
    public async Task AWelcomeLosesItsMomentWhenThePersonSubmitsNotWhenTheTurnStarts()
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
            var isStale = typeof(MainWindowViewModel)
                .GetMethod("IsStalePendingMessage", BindingFlags.Instance | BindingFlags.NonPublic)!
                .CreateDelegate<Func<PendingModelMessage, bool>>(viewModel);
            MethodInfo dispatch = typeof(MainWindowViewModel)
                .GetMethod("DispatchMissionInputAsync", BindingFlags.Instance | BindingFlags.NonPublic)!;
            FieldInfo currentTurn = typeof(MainWindowViewModel)
                .GetField("_currentTurnTraceId", BindingFlags.Instance | BindingFlags.NonPublic)!;
            PendingModelMessage greeting = Welcome("t0");
            Assert.That(isStale(greeting), Is.False);

            // The input stops in the pipeline before any turn starts (it is empty): the current turn is still t0.
            Assert.ThrowsAsync<MissionInputRejectedException>(async () => await (Task)dispatch.Invoke(
                viewModel, [new MissionInput(string.Empty, MissionInputSource.Text), null, CancellationToken.None])!);
            Assert.That(currentTurn.GetValue(viewModel), Is.EqualTo("t0"));
            Assert.That(isStale(greeting), Is.True, "the person spoke: the greeting lost its moment");

            currentTurn.SetValue(viewModel, "t1");
            Assert.That(isStale(Welcome("t1")), Is.False, "a greeting asked for in the current turn is its answer");
        }
    }

    // Review of ronda 25: an input rejected before any turn opens marks the current turn's greeting stale. A new
    // conversation started after it greets under that same turn id, and its greeting is never dropped (the conversation
    // would stay empty).
    [Test]
    public async Task ANewConversationAfterARejectedInputStillGetsItsWelcome()
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
            var isStale = typeof(MainWindowViewModel)
                .GetMethod("IsStalePendingMessage", BindingFlags.Instance | BindingFlags.NonPublic)!
                .CreateDelegate<Func<PendingModelMessage, bool>>(viewModel);
            MethodInfo dispatch = typeof(MainWindowViewModel)
                .GetMethod("DispatchMissionInputAsync", BindingFlags.Instance | BindingFlags.NonPublic)!;
            Assert.ThrowsAsync<MissionInputRejectedException>(async () => await (Task)dispatch.Invoke(
                viewModel, [new MissionInput(string.Empty, MissionInputSource.Text), null, CancellationToken.None])!);
            Assert.That(isStale(Welcome("t0")), Is.True, "the rejected input still lost the old greeting its moment");

            Assert.That(viewModel.StartNewUiSession(), Is.True);
            Assert.That(isStale(Welcome("t0")), Is.False, "the new conversation's greeting under the same turn id");
        }
    }

    private static PendingModelMessage Welcome(string traceId)
    {
        UserMessageDraft draft = UserMessagePolicy.Create(TurnVisibleFacts.Welcome(), UserMessageEvent.Welcome);
        return new PendingModelMessage(draft, string.Empty, ModelMessageComposer.CreateFacts(draft), traceId);
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
