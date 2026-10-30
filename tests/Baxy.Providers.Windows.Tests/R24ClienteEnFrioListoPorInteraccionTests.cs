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
    private static readonly ClientFocus SearchInput = new("Edit", "Quick switcher", true, "42.9.3", InDialog: true);
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
    public void ReadinessIsContentShown()
    {
        Assert.Multiple(() =>
        {
            // Readiness is content (C14: no title test, no fixed settle): a loading screen shows none, and nothing
            // read is not ready.
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

    // Contracaso: a window nobody can read is said as such (Unanswered), not as a window without content; the caller
    // does not say it ready either way (C14).
    [Test]
    public async Task AWindowThatCannotBeReadIsSaidUnanswered()
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
    // itself while the shortcut does nothing yet. Ronda final 28: a composer, outside any dialog, is never taken for
    // the search; and a composer whose picture changed (the name is there as a draft) or is unreadable keeps the
    // possible effect.
    [TestCase(false)]
    [TestCase(true)]
    public void AComposerFocusedByItselfIsNotSaidUntouchedWhenItsPictureChanged(bool beforeOnAPanel)
    {
        ClientFocus? before = beforeOnAPanel ? Button : null;
        Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(before, Composer), Is.False);
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
    private static readonly ClientFocus ActiveRow = new("ListItem", "Ron92", false, "42.9.8", InDialog: true);

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
    // discord que llego en 10 min»; the read after Ctrl+K still shows the composer. Ronda final 27 (regla 3): the name is
    // never typed into a switcher not seen open (with the switcher already open, Ctrl+K closed it and the name went into
    // the person's message box): the shortcut once more, then refused, on any client.
    [Test]
    public async Task ARunningClientWhoseSearchIsNotSeenRetriesAndThenRefuses()
    {
        WindowsDesktopMessagingAutomation.InputWait wait = await WindowsDesktopMessagingAutomation.AwaitOpenedInputAsync(
            Script(Focused(Composer)), Focused(Composer), TimeSpan.FromMilliseconds(60), TimeSpan.FromMilliseconds(5),
            CancellationToken.None);
        Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.InputWait.NotOpened));
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(wait, retried: false),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Retry));
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(wait, retried: true),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Refuse));
            Assert.That(WindowsDesktopMessagingAutomation.ComposerUntouched(wait, composerChanged: false), Is.False);
            // Contracaso: the cold client of t1-c09 retries once and then never types.
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(wait, retried: false),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Retry));
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(wait, retried: true),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Refuse));
            // Only a seen input types, on any client; a window nobody can read is refused after the retry.
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(
                    WindowsDesktopMessagingAutomation.InputWait.Opened, retried: true),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Type));
            Assert.That(WindowsDesktopMessagingAutomation.AfterSearchWait(
                    WindowsDesktopMessagingAutomation.InputWait.Unanswered, retried: true),
                Is.EqualTo(WindowsDesktopMessagingAutomation.SearchStep.Refuse));
        });
    }

    // Ronda final 28 (regla 3): a focus inside a dialog (the switcher already open, on its field or its active row)
    // sends no key; a channel or message row, or the composer, outside any dialog, is no open switcher. After the
    // shortcut only a new focus inside a dialog is the switcher: the composer that takes the focus when Ctrl+K closed
    // an open switcher is not, and neither are the rows of Discord's own lists.
    [Test]
    public void OnlyAFocusInsideADialogIsTheSwitcher()
    {
        var composer = new ClientFocus("Edit", "Mensaje @Ana", true, "7.2");
        var channelRow = new ClientFocus("TreeItem", "general", false, "7.4");
        var switcherField = new ClientFocus("Edit", "Buscador", true, "9.1", InDialog: true);
        var switcherRow = new ClientFocus("ListItem", "Ana", false, "9.2", InDialog: true);
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.SearchStateUnknown(switcherRow), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.SearchStateUnknown(switcherField), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.SearchStateUnknown(channelRow), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.SearchStateUnknown(composer), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.SearchStateUnknown(null), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(composer, switcherField), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(channelRow, switcherRow), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(switcherField, composer), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(composer, channelRow), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.ShortcutOpenedInput(null, composer), Is.False);
        });
    }

    // Ronda final 29 (regla 3): client.channel.locate counts its Ctrl+K before pressing it, and any failure after it
    // (a switcher that opened late and is then taken for a dialog, a lost front) keeps the possible effect.
    [Test]
    public void TheChannelLookupSaysAKeyWentOutOnEveryFailureAfterIt()
    {
        DirectoryInfo? root = new(AppContext.BaseDirectory);
        while (root is not null && !File.Exists(Path.Combine(root.FullName, "Baxy.slnx")))
        {
            root = root.Parent;
        }

        Assert.That(root, Is.Not.Null, "Baxy.slnx was not found.");
        string source = File.ReadAllText(Path.Combine(
            root!.FullName, "src", "Baxy.Providers.Windows", "External", "WindowsDeviceControlAdapter.cs"));
        int sent = source.IndexOf("$state.sent=$true", StringComparison.Ordinal);
        Assert.Multiple(() =>
        {
            Assert.That(sent, Is.GreaterThan(0));
            Assert.That(sent, Is.LessThan(source.IndexOf("[void][BaxyMarkedKeys]::Character([char]'k',$true)", StringComparison.Ordinal)));
            Assert.That(source, Does.Contain("leftShown=$leftShown;sent=$state.sent}"));
            Assert.That(source, Does.Contain("|| Bool(root, \"leftShown\") || Bool(root, \"sent\"));"));
            Assert.That(source, Does.Contain("'client_dialog_after_shortcut'"));
            // Rows count only once the switcher's field holds the name and they changed since before typing; a switcher
            // not closed is said.
            Assert.That(source, Does.Contain("($now -join \"`n\") -ne $rowsBefore -and (Field-Shows $label)"));
            Assert.That(source, Does.Contain("leftOpen=$state.leftOpen}"));
            Assert.That(source, Does.Contain("effectObserved: Bool(root, \"leftShown\") || Bool(root, \"leftOpen\")"));
        });
    }

    [Test]
    public void TheDiscordSearchTypesOnlyIntoASwitcherSeenOpen()
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
            Assert.That(source, Does.Contain("AfterSearchWait(input, retried: true) == SearchStep.Refuse"));
            Assert.That(source, Does.Not.Contain("ClientStartedRecently"));
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
            Steps.Add("send:" + recipient.Name);
            return ValueTask.FromResult(new DesktopMessageObservation(true, true, "hash", null));
        }

        public ValueTask<DesktopMessageObservation> DraftAsync(ResolvedRecipient recipient, string text, CancellationToken cancellationToken)
        {
            Steps.Add("draft:" + recipient.Name);
            return ValueTask.FromResult(new DesktopMessageObservation(true, true, "hash", null));
        }
    }

    // t1-c09#1 («Ron92»), t2-c07#1 («Ron92»), t3-c07 t1 («ron92»); a recipient that does not exist ends the same way.
    [TestCase("Ron92")]
    [TestCase("ron92")]
    [TestCase("NadieSeLlamaAsi")]
    public async Task TheColdClientCasesAnswerNotOpenedWithoutEffectAndNothingIsTyped(string recipient)
    {
        var automation = new ColdClient(WindowsDesktopMessagingAutomation.UnverifiedChat(42, 7, composerUntouched: true));
        using var adapter = new DesktopMessagingAdapter(automation);
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "message.draft",
            JsonDocument.Parse($$"""{"channel":"discord","recipient":"{{recipient}}","text":"hola"}""").RootElement.Clone(),
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

    // Contracaso: a chat that was verified goes on to the draft as before.
    [Test]
    public async Task AVerifiedChatStillResolves()
    {
        var automation = new ColdClient(new DesktopRecipientObservation(true, true, 42, 7, null, "Ron92"));
        using var adapter = new DesktopMessagingAdapter(automation);
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "message.draft",
            JsonDocument.Parse("""{"channel":"discord","recipient":"Ron92","text":"hola"}""").RootElement.Clone(),
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(automation.Steps, Is.EqualTo(new[] { "ensure:discord", "resolve:discord:Ron92", "draft:Ron92" }));
        });
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
            """{"ok":true,"error":"","content":true,"focused":{"kind":"Edit","name":"Quick switcher","editable":true,"id":"42.9.3","dialog":true}}""");
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

    // Ajuste c3 (F09, M6, live on the notebook): client.channel.locate with no match said switcherNotClosed and the next
    // look had the focus on the switcher's dialog itself. The script's Dialog-Of walked from the element's parent, so a
    // focus on the dialog was in no dialog: no Escape went and the switcher stayed open. The script's own Dialog-Of,
    // taken by its syntax tree, over described elements: the dialog itself is the dialog; the client's window, a page
    // and an element of another process are in none.
    [Test]
    public void TheSwitchersDialogHoldingTheFocusItselfIsTheDialogTheEscapeCloses()
    {
        string script = WindowsDeviceControlAdapter.ClientChannelLocateScript;
        string run = """
            $ErrorActionPreference='Stop'
            Add-Type -AssemblyName UIAutomationClient;Add-Type -AssemblyName UIAutomationTypes
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseInput($env:BAXY_LOCATE_SCRIPT,[ref]$tokens,[ref]$errors)
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Dialog-Of' },$true))
            if($found.Count -ne 1){ throw 'Dialog-Of missing' }
            . ([scriptblock]::Create($found[0].Extent.Text))
            $clientPid=7;$h=[IntPtr]100
            function New-Element([int]$process,[int]$handle,$type){ return (New-Object psobject -Property @{ Current=(New-Object psobject -Property @{ ProcessId=$process; NativeWindowHandle=$handle; ControlType=$type }) }) }
            $window=[System.Windows.Automation.ControlType]::Window
            $dialog=New-Element 7 0 $window
            $answers=@(
              [string]([object]::ReferenceEquals((Dialog-Of $dialog),$dialog)),
              [string]($null -eq (Dialog-Of (New-Element 7 100 $window))),
              [string]($null -eq (Dialog-Of (New-Element 7 0 ([System.Windows.Automation.ControlType]::Document)))),
              [string]($null -eq (Dialog-Of (New-Element 9 0 $window))))
            [Console]::Out.Write(($answers -join ','))
            """;
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
        {
            start.ArgumentList.Add(argument);
        }

        start.ArgumentList.Add(Convert.ToBase64String(System.Text.Encoding.Unicode.GetBytes(run)));
        start.Environment["BAXY_LOCATE_SCRIPT"] = script;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        Assert.That(output.Trim().Split(','), Is.EqualTo(new[]
        {
            "True", // the switcher's dialog holding the focus is that dialog: the Escape goes to it
            "True", // the client's own window is no dialog
            "True", // a page is no dialog
            "True", // another process's element is in none
        }));
        // Review of privacy: the Escape goes only to the dialog holding the name typed (the switcher), never to another.
        Assert.That(script, Does.Contain("if(-not ($null -ne $typedIn -and (Field-Shows $text $typedIn) -and (Client-InFront))){return $true}"));
        Assert.That(script, Does.Contain("$state.leftOpen=Close-Switcher $label"));
    }

    // Ajuste c3 (live on the PC, 30-10, Discord 1.0.9266): client.channel.locate with no match still said
    // switcherNotClosed. Traced live: the first Escape only empties the switcher's field and leaves the switcher open
    // with the focus in it (2.3 s later still there); a second Escape closes it. The script's own Close-Switcher, taken by
    // its syntax tree, over a described switcher: each case gives the Escapes sent and whether it was left open.
    // Each counter-case leaves exactly one guard to decide (review of privacy): the other dialog and the lost front have
    // an empty field too.
    [TestCase("empties", "2,False")] // the live Discord: the first Escape empties the field, the second closes it
    [TestCase("closes", "1,False")] // a switcher that one Escape closes gets one Escape
    [TestCase("otherDialog", "1,True")] // the focus went to another dialog with an empty field (a call): no second Escape
    [TestCase("stillTyped", "1,True")] // the same dialog still holds the name: the Escape did nothing, no second one
    [TestCase("frontLost", "1,True")] // the front left Discord, the field empty: no second Escape (another window)
    [TestCase("notTyped", "0,True")] // the switcher does not hold the name typed: no Escape at all
    [TestCase("otherFirst", "0,True")] // the focus is on another dialog with an empty field from the start: no Escape
    [TestCase("noFront", "0,True")] // the switcher holds the name but Discord is not in front: no Escape
    public void TheSwitcherEmptiedByTheFirstEscapeIsClosedByASecondOneInTheSameDialog(string client, string expected)
    {
        string run = """
            $ErrorActionPreference='Stop'
            $tokens=$null;$errors=$null
            $ast=[System.Management.Automation.Language.Parser]::ParseInput($env:BAXY_LOCATE_SCRIPT,[ref]$tokens,[ref]$errors)
            $found=@($ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Close-Switcher' },$true))
            if($found.Count -ne 1){ throw 'Close-Switcher missing' }
            . ([scriptblock]::Create($found[0].Extent.Text))
            $client=$env:BAXY_CLIENT;$switcher=@{escapes=0};$dialog=New-Object psobject;$other=New-Object psobject
            function Start-Sleep { }
            function Send-Escape { $switcher.escapes++ }
            function Client-InFront { -not ($client -eq 'noFront' -or ($client -eq 'frontLost' -and $switcher.escapes -gt 0)) }
            function Same-Element($a,$b){ [object]::ReferenceEquals($a,$b) }
            function Focus-Dialog {
              if($client -eq 'otherFirst'){ return $other }
              if($switcher.escapes -eq 0){ return $dialog }
              switch($client){
                'empties' { if($switcher.escapes -eq 1){ return $dialog }; return $null }
                'closes' { return $null }
                'otherDialog' { return $other }
                default { return $dialog }
              }
            }
            # What the field of the dialog asked about holds: another dialog's field is empty; the switcher's holds the
            # name until an Escape empties it (only a switcher that stays open with the name keeps it).
            function Field-Shows([string]$text,$in){
              if($null -eq $in){ throw 'Field-Shows without its dialog' }
              $holds=$(if(-not [object]::ReferenceEquals($in,$dialog)){''}elseif($client -eq 'notTyped'){''}elseif($switcher.escapes -eq 0 -or $client -eq 'stillTyped'){'zzqxprueba'}else{''})
              $holds -eq $text
            }
            $open=Close-Switcher 'zzqxprueba'
            [Console]::Out.Write([string]$switcher.escapes + ',' + [string]$open)
            """;
        var start = new ProcessStartInfo("powershell.exe")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand" })
        {
            start.ArgumentList.Add(argument);
        }

        start.ArgumentList.Add(Convert.ToBase64String(System.Text.Encoding.Unicode.GetBytes(run)));
        start.Environment["BAXY_LOCATE_SCRIPT"] = WindowsDeviceControlAdapter.ClientChannelLocateScript;
        start.Environment["BAXY_CLIENT"] = client;
        using Process process = Process.Start(start)!;
        Task<string> error = process.StandardError.ReadToEndAsync();
        string output = process.StandardOutput.ReadToEnd();
        Assert.That(process.WaitForExit(60_000), Is.True, "the script answers");
        Assert.That(process.ExitCode, Is.EqualTo(0), error.Result);
        Assert.That(output.Trim(), Is.EqualTo(expected));
    }
}
