using System.Diagnostics;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Ronda 24 «cliente-en-frio-listo-por-interaccion» (uso real r23: t1-c09#1 «mandale a Ron92 por discord que hoy no
/// llego a jugar…», t2-c07#1 «… que llego en 10 min…», t3-c07 t1 «mandale a ron92 por discord que ya voy saliendo…»,
/// client closed). The client was taken as ready at its first title (its loading screen already carries its name),
/// the chat search was driven with fixed waits over a client that did not answer yet, the title was read once and
/// the resolve came back «recipient_identity_not_verified» with an effect, so the turn said «No pude confirmar el
/// resultado con «Ron92»». Now: ready is interactive content, the search is used once a new input holds the focus, the
/// title is polled for 3 s, and a chat not opened without touching a composer is «recipient_not_opened», no effect.
/// Scripted reads only: nothing here clicks or types.
/// </summary>
[TestFixture]
public sealed class R24ClienteEnFrioListoPorInteraccionTests
{
    private static readonly ClientFocus Composer = new("Edit", "Message @Ana", true, "42.7.1");
    private static readonly ClientFocus SearchInput = new("Edit", "Quick switcher", true, "42.9.3");
    private static readonly ClientFocus Button = new("Button", "Settings", false, "42.2.2");

    private static Func<CancellationToken, ValueTask<ClientInteraction>> Script(params ClientInteraction[] reads)
    {
        int next = 0;
        return _ => ValueTask.FromResult(reads[Math.Min(next++, reads.Length - 1)]);
    }

    private static ClientInteraction Loading => new(true, false, null);

    private static ClientInteraction Shown(ClientFocus? focus = null) => new(true, true, focus);

    private static ClientInteraction Focused(ClientFocus? focus) => new(true, false, focus);

    // --------------------------------------------------------------- 1. ready is interaction, not a title

    [Test]
    public void TheLoadingScreenTitleAloneIsNotReadiness()
    {
        Assert.Multiple(() =>
        {
            // The title test still passes the loading screen (it is not the updater) ...
            Assert.That(WindowsDesktopMessagingAutomation.ClientWindowReady("Discord"), Is.True);
            // ... so readiness also asks for content: a loading screen shows none, nothing read is not ready.
            Assert.That(WindowsDesktopMessagingAutomation.ClientInteractionReady(Loading), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.ClientInteractionReady(ClientInteraction.Unanswered), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.ClientInteractionReady(Shown()), Is.True);
        });
    }

    [Test]
    public async Task AColdClientIsReadyWhenItsContentShows()
    {
        var reads = Script(Loading, Loading, Shown());
        WindowsDesktopMessagingAutomation.ContentWait wait = await WindowsDesktopMessagingAutomation.AwaitClientContentAsync(
            reads, TimeSpan.FromSeconds(5), TimeSpan.FromMilliseconds(1), CancellationToken.None);
        Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.ContentWait.Ready));
    }

    [Test]
    public async Task AClientThatNeverShowsContentIsNotVerified()
    {
        WindowsDesktopMessagingAutomation.ContentWait wait = await WindowsDesktopMessagingAutomation.AwaitClientContentAsync(
            Script(Loading), TimeSpan.FromMilliseconds(60), TimeSpan.FromMilliseconds(5), CancellationToken.None);
        Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.ContentWait.NotShown));
    }

    // Contracaso: a window nobody can read keeps the timed path of before (the caller's settle), never «not ready».
    [Test]
    public async Task AWindowThatCannotBeReadKeepsTheTimedPath()
    {
        WindowsDesktopMessagingAutomation.ContentWait wait = await WindowsDesktopMessagingAutomation.AwaitClientContentAsync(
            Script(ClientInteraction.Unanswered), TimeSpan.FromMilliseconds(60), TimeSpan.FromMilliseconds(5),
            CancellationToken.None);
        Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.ContentWait.Unanswered));
    }

    // --------------------------------------------------------------- the search input is waited for, bounded

    [Test]
    public void ANewFocusedEditableFieldIsTheOpenedInput()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(Composer, SearchInput), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(null, SearchInput), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(Button, SearchInput), Is.True);
            // The composer that kept the focus is not a search: typing there would write into the conversation.
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(Composer, Composer), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(Composer, Button), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(Composer, null), Is.False);
        });
    }

    // Contracaso «con el cliente ya abierto el turno no se alarga»: the input seen at once ends the wait well before
    // the old fixed 1.4 s.
    [Test]
    public async Task AnInputThatOpensAtOnceEndsTheWaitEarly()
    {
        var clock = Stopwatch.StartNew();
        WindowsDesktopMessagingAutomation.InputWait wait = await WindowsDesktopMessagingAutomation.AwaitOpenedInputAsync(
            Script(Focused(SearchInput)), Focused(Composer), WindowsDesktopMessagingAutomation.SearchInputBudget,
            TimeSpan.FromMilliseconds(10), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.InputWait.Opened));
            Assert.That(clock.Elapsed, Is.LessThan(WindowsDesktopMessagingAutomation.SearchInputBudget));
        });
    }

    [Test]
    public async Task AFocusThatStaysOnTheComposerIsNotOpened()
    {
        WindowsDesktopMessagingAutomation.InputWait wait = await WindowsDesktopMessagingAutomation.AwaitOpenedInputAsync(
            Script(Focused(Composer)), Focused(Composer), TimeSpan.FromMilliseconds(60), TimeSpan.FromMilliseconds(5),
            CancellationToken.None);
        Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.InputWait.NotOpened));
    }

    [Test]
    public async Task AnInputThatOpensLateIsStillSeenWithinTheBudget()
    {
        WindowsDesktopMessagingAutomation.InputWait wait = await WindowsDesktopMessagingAutomation.AwaitOpenedInputAsync(
            Script(Focused(Composer), Focused(Composer), Focused(SearchInput)), Focused(Composer), TimeSpan.FromSeconds(2),
            TimeSpan.FromMilliseconds(5), CancellationToken.None);
        Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.InputWait.Opened));
    }

    [Test]
    public async Task UnreadableFocusIsUnansweredNotNotOpened()
    {
        WindowsDesktopMessagingAutomation.InputWait wait = await WindowsDesktopMessagingAutomation.AwaitOpenedInputAsync(
            Script(ClientInteraction.Unanswered), Focused(null), TimeSpan.FromMilliseconds(40), TimeSpan.FromMilliseconds(5),
            CancellationToken.None);
        Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.InputWait.Unanswered));
    }

    // Revisión 1, caso (a): the first messaging turn after BAXY starts reads «before» while the worker is still
    // coming up (Unanswered). A worker that answers within the budget sees the open conversation's composer focused;
    // with nothing to compare with, that is never «opened», and the old fixed wait is kept whole.
    [Test]
    public async Task WithoutABeforeReadTheComposerIsNeverTakenForAnOpenedInput()
    {
        TimeSpan budget = TimeSpan.FromMilliseconds(120);
        var clock = Stopwatch.StartNew();
        WindowsDesktopMessagingAutomation.InputWait wait = await WindowsDesktopMessagingAutomation.AwaitOpenedInputAsync(
            Script(Focused(Composer)), ClientInteraction.Unanswered, budget, TimeSpan.FromMilliseconds(5),
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.InputWait.Unanswered));
            Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(budget - TimeSpan.FromMilliseconds(15)));
            // Unanswered never lets the turn say the composer was untouched.
            Assert.That(
                WindowsDesktopMessagingAutomation.ComposerUntouched(wait, composerChanged: false), Is.False);
        });
    }

    // Revisión 1, caso (b): a cold client whose focus was on a panel (or nowhere) mounts and focuses the composer by
    // itself while the shortcut does nothing yet. The focus alone cannot tell it from a search input, so the
    // composer's picture decides: changed (the name is there as a draft) or unreadable keeps the possible effect.
    [TestCase(false)]
    [TestCase(true)]
    public void AComposerFocusedByItselfIsNotSaidUntouchedWhenItsPictureChanged(bool beforeOnAPanel)
    {
        ClientFocus? before = beforeOnAPanel ? Button : null;
        Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(before, Composer), Is.True);
        bool untouched = WindowsDesktopMessagingAutomation.ComposerUntouched(
            WindowsDesktopMessagingAutomation.InputWait.Opened, composerChanged: true);
        DesktopRecipientObservation observation = WindowsDesktopMessagingAutomation.UnverifiedChat(42, 7, untouched);
        Assert.Multiple(() =>
        {
            Assert.That(untouched, Is.False);
            Assert.That(observation.EffectObserved, Is.True);
            Assert.That(observation.ErrorCode, Is.EqualTo("recipient_identity_not_verified"));
        });
    }

    // Contracaso: the name went into the search input the shortcut opened and the composer looks as before: nothing
    // was written, said as «recipient_not_opened» without effect.
    [Test]
    public void AnOpenedSearchWithTheComposerUnchangedIsUntouched()
    {
        bool untouched = WindowsDesktopMessagingAutomation.ComposerUntouched(
            WindowsDesktopMessagingAutomation.InputWait.Opened, composerChanged: false);
        DesktopRecipientObservation observation = WindowsDesktopMessagingAutomation.UnverifiedChat(42, 7, untouched);
        Assert.Multiple(() =>
        {
            Assert.That(untouched, Is.True);
            Assert.That(observation.EffectObserved, Is.False);
            Assert.That(observation.ErrorCode, Is.EqualTo(WindowsDesktopMessagingAutomation.RecipientNotOpened));
            Assert.That(
                WindowsDesktopMessagingAutomation.ComposerUntouched(
                    WindowsDesktopMessagingAutomation.InputWait.Unanswered, composerChanged: false),
                Is.False);
        });
    }

    // The adapter wires both checks: the before read is passed whole, and the composer is pictured before the
    // shortcut and compared once the search is closed.
    [Test]
    public void TheDiscordSearchComparesTheComposerPictureBeforeSayingUntouched()
    {
        DirectoryInfo? root = new(AppContext.BaseDirectory);
        while (root is not null && !File.Exists(Path.Combine(root.FullName, "Baxy.slnx")))
        {
            root = root.Parent;
        }

        Assert.That(root, Is.Not.Null, "Baxy.slnx was not found.");
        string source = File.ReadAllText(Path.Combine(
            root!.FullName, "src", "Baxy.Providers.Windows", "External", "DesktopMessagingAdapter.cs"));
        Assert.Multiple(() =>
        {
            Assert.That(source, Does.Contain("byte[]? composerBefore = TryCaptureComposer(handle, channel);"));
            Assert.That(source, Does.Contain("composerChanged = ComposerChanged(handle, channel, composerBefore);"));
            Assert.That(source, Does.Contain("UnverifiedChat(handle, processId, ComposerUntouched(input, composerChanged))"));
            Assert.That(source, Does.Not.Contain("composerUntouched: input == InputWait.Opened"));
            Assert.That(source, Does.Not.Contain("Read, before.Focused,"));
        });
    }

    // Revisión 2 de r24, bloqueante 1: a web client's search keeps the keys in its input but UI Automation reports the
    // focus on the active result row (aria-activedescendant). A newly focused row is the search open.
    private static readonly ClientFocus ActiveRow = new("ListItem", "Ron92", false, "42.9.8");

    [Test]
    public async Task AnActiveResultRowThatTakesTheFocusIsTheOpenedSearch()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(Composer, ActiveRow), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(null, ActiveRow), Is.True);
            // Contracasos: the same row before and after opened nothing, and a button or a panel never is a search.
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(ActiveRow, ActiveRow), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(Composer, Button), Is.False);
            Assert.That(
                WindowsDesktopMessagingAutomation.ShortcutOpenedInput(
                    Composer, new ClientFocus("Pane", "Discord", false, "42.1.1")),
                Is.False);
        });
        WindowsDesktopMessagingAutomation.InputWait wait = await WindowsDesktopMessagingAutomation.AwaitOpenedInputAsync(
            Script(Focused(Composer), Focused(ActiveRow)), Focused(Composer), TimeSpan.FromSeconds(2),
            TimeSpan.FromMilliseconds(5), CancellationToken.None);
        Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.InputWait.Opened));
    }

    // Bloqueante 1, escenario de la revisión: Discord already running on another person's DM, «mandale a Ron92 por
    // discord que llego en 10 min»; the read after Ctrl+K still shows the composer. The search is not refused: the
    // name is typed after the old fixed wait, as t4-c03 did before the branch, and the turn never claims the composer
    // untouched. Only a client started just now retries and then refuses.
    [Test]
    public async Task ARunningClientWhoseSearchIsNotSeenKeepsThePathThatSent()
    {
        WindowsDesktopMessagingAutomation.InputWait wait = await WindowsDesktopMessagingAutomation.AwaitOpenedInputAsync(
            Script(Focused(Composer)), Focused(Composer), TimeSpan.FromMilliseconds(60), TimeSpan.FromMilliseconds(5),
            CancellationToken.None);
        Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.InputWait.NotOpened));
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(wait, clientStartedRecently: false, retried: false),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Type));
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(wait, clientStartedRecently: false, retried: true),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Type));
            Assert.That(WindowsDesktopMessagingAutomation.ComposerUntouched(wait, composerChanged: false), Is.False);
            // Contracaso: the cold client of t1-c09 retries once and then never types.
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(wait, clientStartedRecently: true, retried: false),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Retry));
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(wait, clientStartedRecently: true, retried: true),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Refuse));
            // A seen input, or a window nobody can read, types on any client.
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(
                    WindowsDesktopMessagingAutomation.InputWait.Opened, clientStartedRecently: true, retried: true),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Type));
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(
                    WindowsDesktopMessagingAutomation.InputWait.Unanswered, clientStartedRecently: true, retried: true),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Type));
        });
    }

    [Test]
    public void AClientIsColdOnlyRightAfterItsProcessStarted()
    {
        var now = new DateTime(2026, 10, 9, 21, 0, 0);
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.ClientStartedRecently(now.AddSeconds(-20), now), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.ClientStartedRecently(now.AddMinutes(-5), now), Is.False);
            // A start time that cannot be read is a running client: the path that sent before is kept.
            Assert.That(WindowsDesktopMessagingAutomation.ClientStartedRecently(null, now), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.ClientStartedRecently(now.AddSeconds(5), now), Is.False);
            // This test's own process started just now; one that does not exist has no start time.
            Assert.That(WindowsDesktopMessagingAutomation.ProcessStartTime(Environment.ProcessId), Is.Not.Null);
            Assert.That(WindowsDesktopMessagingAutomation.ProcessStartTime(-1), Is.Null);
        });
    }

    [Test]
    public void TheDiscordSearchRefusesOnlyOnAClientStartedJustNow()
    {
        DirectoryInfo? root = new(AppContext.BaseDirectory);
        while (root is not null && !File.Exists(Path.Combine(root.FullName, "Baxy.slnx")))
        {
            root = root.Parent;
        }

        Assert.That(root, Is.Not.Null, "Baxy.slnx was not found.");
        string source = File.ReadAllText(Path.Combine(
            root!.FullName, "src", "Baxy.Providers.Windows", "External", "DesktopMessagingAdapter.cs"));
        Assert.Multiple(() =>
        {
            Assert.That(source, Does.Contain("bool coldClient = ClientStartedRecently(ProcessStartTime(processId), DateTime.Now);"));
            Assert.That(source, Does.Contain("AfterSearchWait(input, coldClient, retried: true) == SearchStep.Refuse"));
            Assert.That(source, Does.Not.Contain("if (input == InputWait.NotOpened)"));
        });
    }

    // --------------------------------------------------------------- 2. the title is read for a while, not once

    [Test]
    public async Task ATitleThatArrivesAfterTheFirstReadIsSeen()
    {
        int reads = 0;
        bool seen = await WindowsDesktopMessagingAutomation.PollUntilAsync(
            _ => ValueTask.FromResult(++reads >= 4), WindowsDesktopMessagingAutomation.ChatTitleBudget,
            TimeSpan.FromMilliseconds(5), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(seen, Is.True);
            Assert.That(reads, Is.EqualTo(4));
        });
    }

    [Test]
    public async Task ATitleThatNeverNamesTheRecipientEndsAtTheBudget()
    {
        int reads = 0;
        var clock = Stopwatch.StartNew();
        bool seen = await WindowsDesktopMessagingAutomation.PollUntilAsync(
            _ => { reads++; return ValueTask.FromResult(false); }, TimeSpan.FromMilliseconds(80),
            TimeSpan.FromMilliseconds(10), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(seen, Is.False);
            Assert.That(reads, Is.GreaterThan(1));
            Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(2)));
        });
        Assert.That(WindowsDesktopMessagingAutomation.ChatTitleBudget, Is.EqualTo(TimeSpan.FromSeconds(3)));
    }

    // --------------------------------------------------------------- 3. a chat not opened is said as such

    [Test]
    public void AChatNotOpenedWithoutTouchingAComposerHasNoEffect()
    {
        DesktopRecipientObservation untouched = WindowsDesktopMessagingAutomation.UnverifiedChat(42, 7, composerUntouched: true);
        DesktopRecipientObservation maybe = WindowsDesktopMessagingAutomation.UnverifiedChat(42, 7, composerUntouched: false);
        Assert.Multiple(() =>
        {
            Assert.That(untouched.Verified, Is.False);
            Assert.That(untouched.EffectObserved, Is.False);
            Assert.That(untouched.ErrorCode, Is.EqualTo(WindowsDesktopMessagingAutomation.RecipientNotOpened));
            // Contracaso: text that may have reached a composer keeps the possible effect and its old code.
            Assert.That(maybe.EffectObserved, Is.True);
            Assert.That(maybe.ErrorCode, Is.EqualTo("recipient_identity_not_verified"));
        });
    }

    private sealed class ColdClient(DesktopRecipientObservation resolve) : IDesktopMessagingAutomation
    {
        internal List<string> Steps { get; } = [];

        public ValueTask<DesktopClientReadiness> EnsureClientOpenAsync(string channel, CancellationToken cancellationToken)
        {
            Steps.Add("ensure:" + channel);
            return ValueTask.FromResult(new DesktopClientReadiness(true, true, null));
        }

        public ValueTask<DesktopRecipientObservation> ResolveAsync(string channel, string recipient, CancellationToken cancellationToken)
        {
            Steps.Add($"resolve:{channel}:{recipient}");
            return ValueTask.FromResult(resolve);
        }

        public ValueTask<DesktopMessageObservation> SendAsync(ResolvedRecipient recipient, string text, CancellationToken cancellationToken)
        {
            Steps.Add("send:" + recipient.DisplayName);
            return ValueTask.FromResult(new DesktopMessageObservation(true, true, "hash", null));
        }
    }

    private static string TemporaryStore() =>
        Path.Combine(Path.GetTempPath(), "baxy-r24-" + Guid.NewGuid().ToString("N"), "recipient-channels.v1.json");

    // t1-c09#1 («Ron92»), t2-c07#1 («Ron92»), t3-c07 t1 («ron92»); a recipient that does not exist ends the same way.
    [TestCase("Ron92")]
    [TestCase("ron92")]
    [TestCase("NadieSeLlamaAsi")]
    public async Task TheColdClientCasesAnswerNotOpenedWithoutEffectAndNothingIsTyped(string recipient)
    {
        var automation = new ColdClient(WindowsDesktopMessagingAutomation.UnverifiedChat(42, 7, composerUntouched: true));
        using var adapter = new DesktopMessagingAdapter(automation, TemporaryStore());
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "message.recipient.resolve",
            JsonDocument.Parse($$"""{"channel":"discord","recipient":"{{recipient}}"}""").RootElement.Clone(),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("recipient_not_opened"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(automation.Steps, Is.EqualTo(new[] { "ensure:discord", "resolve:discord:" + recipient }));
        });
    }

    // Contracaso: a chat that was verified goes on to the send as before.
    [Test]
    public async Task AVerifiedChatStillResolves()
    {
        var automation = new ColdClient(new DesktopRecipientObservation(true, true, 42, 7, null));
        using var adapter = new DesktopMessagingAdapter(automation, TemporaryStore());
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "message.recipient.resolve",
            JsonDocument.Parse("""{"channel":"discord","recipient":"Ron92"}""").RootElement.Clone(),
            CancellationToken.None);
        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
    }

    // --------------------------------------------------------------- the probe over the worker

    private sealed class ScriptedWorker(string answer) : IUiaWorker
    {
        internal List<string> Commands { get; } = [];

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Commands.Add(commandJson);
            return ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(answer));
        }
    }

    [Test]
    public async Task TheProbeAsksTheWorkerOnlyOnceItIsUpAndReadsItsAnswer()
    {
        var worker = new ScriptedWorker(
            """{"ok":true,"error":"","content":true,"focused":{"kind":"Edit","name":"Quick switcher","editable":true,"id":"42.9.3"}}""");
        var probe = new UiaClientInteractionProbe(worker);
        probe.Prewarm();
        ClientInteraction read = ClientInteraction.Unanswered;
        for (int attempt = 0; attempt < 200 && !read.Answered; attempt++)
        {
            read = await probe.ReadAsync(42, content: true, CancellationToken.None);
            if (!read.Answered)
            {
                await Task.Delay(5);
            }
        }

        Assert.Multiple(() =>
        {
            Assert.That(read.Answered, Is.True);
            Assert.That(read.ContentShown, Is.True);
            Assert.That(read.Focused, Is.EqualTo(SearchInput));
            Assert.That(worker.Commands, Has.All.Contains("\"cmd\":\"interaction\""));
        });
    }

    [Test]
    public void AFailedWorkerAnswerIsUnanswered()
    {
        using JsonDocument failed = JsonDocument.Parse("""{"ok":false,"error":"active_window_not_found"}""");
        Assert.That(UiaClientInteractionProbe.Parse(failed.RootElement), Is.EqualTo(ClientInteraction.Unanswered));
        Assert.That(UiaClientInteractionProbe.Parse(null), Is.EqualTo(ClientInteraction.Unanswered));
    }

    // The worker reads a window without input: the command exists and names no app.
    [Test]
    public void TheWorkerInteractionCommandIsReadOnlyAndNamesNoApp()
    {
        string script = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        int start = script.IndexOf("function Do-Interaction(", StringComparison.Ordinal);
        Assert.That(start, Is.GreaterThan(0));
        // The function ends at its closing brace at the start of a line.
        int end = script.IndexOf("\n}", start, StringComparison.Ordinal);
        Assert.That(end, Is.GreaterThan(start));
        string body = script[start..end];
        Assert.Multiple(() =>
        {
            Assert.That(script, Does.Contain("elseif($cmd -eq 'interaction'){ Send-Line (Do-Interaction $request) }"));
            foreach (string forbidden in new[] { "SetFocus", "Invoke(", "SendInput", "SetValue", "discord", "whatsapp" })
            {
                Assert.That(body, Does.Not.Contain(forbidden).IgnoreCase, forbidden);
            }
        });
    }
}
