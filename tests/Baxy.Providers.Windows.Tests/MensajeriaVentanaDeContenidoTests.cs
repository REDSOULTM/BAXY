using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real 2026-11-05 (G6 on a client that is a WinUI frame over a WebView2 window of a process it started): the frame's
/// tree has no field, so a client on the screen was told still starting, and its chat search had moved from the fixed
/// point the flow clicked. Scripted reads only: nothing here clicks or types.
/// </summary>
[TestFixture]
public sealed class MensajeriaVentanaDeContenidoTests
{
    private const nint Frame = 100;
    private const nint Content = 200;

    // What the client's window measured at 125 %, in screen pixels: the window, its search field and a composer.
    private static readonly ScreenBox Window = new(-975, 1073, 1600, 1000);
    private static readonly ClientField Search = new("42.1", new ScreenBox(-835, 1194, 298, 21));
    private static readonly ClientField Composer = new("42.9", new ScreenBox(-300, 1990, 700, 30));

    private sealed class ScriptedProbe : IClientInteractionProbe
    {
        internal List<nint> Asked { get; } = [];

        public void Prewarm()
        {
        }

        public ValueTask<ClientInteraction> ReadAsync(nint handle, bool content, CancellationToken cancellationToken)
        {
            Asked.Add(handle);
            return ValueTask.FromResult(new ClientInteraction(true, handle == Content, null));
        }

        public ValueTask<IReadOnlyList<ClientField>> EditableFieldsAsync(nint handle, CancellationToken cancellationToken)
        {
            Asked.Add(handle);
            return ValueTask.FromResult<IReadOnlyList<ClientField>>(handle == Content ? [Search] : []);
        }

        public ValueTask<bool> SelectFocusedTextAsync(nint handle, CancellationToken cancellationToken)
        {
            Asked.Add(handle);
            return ValueTask.FromResult(handle == Content);
        }
    }

    [Test]
    public async Task AClientOnTheScreenIsReadyWhenItsContentIsDrawnByAProcessItStarted()
    {
        var reads = new ScriptedProbe();
        var probe = new ContentWindowProbe(reads, _ => [Content]);

        WindowsDesktopMessagingAutomation.ContentWait wait = await WindowsDesktopMessagingAutomation.AwaitClientContentAsync(
            token => probe.ReadAsync(Frame, content: true, token),
            TimeSpan.FromSeconds(1),
            TimeSpan.FromMilliseconds(1),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(wait, Is.EqualTo(WindowsDesktopMessagingAutomation.ContentWait.Ready));
            Assert.That(reads.Asked, Has.All.EqualTo(Content));
        });
    }

    [Test]
    public async Task EveryReadGoesToTheContentWindow()
    {
        var reads = new ScriptedProbe();
        var probe = new ContentWindowProbe(reads, _ => [Content]);

        IReadOnlyList<ClientField> fields = await probe.EditableFieldsAsync(Frame, CancellationToken.None);
        bool selected = await probe.SelectFocusedTextAsync(Frame, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(fields, Is.EqualTo(new[] { Search }));
            Assert.That(selected, Is.True);
            Assert.That(reads.Asked, Has.All.EqualTo(Content));
        });
    }

    // Control: a client that draws in its own window is read as before.
    [Test]
    public async Task AClientThatDrawsInItsOwnWindowIsReadAsItself()
    {
        var reads = new ScriptedProbe();
        ClientInteraction read = await new ContentWindowProbe(reads, _ => [])
            .ReadAsync(Frame, content: true, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.ContentShown, Is.False);
            Assert.That(reads.Asked, Is.EqualTo(new[] { Frame }));
        });
    }

    [Test]
    public void TheChatSearchIsTheTopmostFieldOnTheWindowsLeft()
    {
        ClientField lower = Search with { Id = "42.2", Box = Search.Box with { Top = Search.Box.Top + 300 } };
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.ChatSearchField([Composer, lower, Search], Window), Is.EqualTo(Search));
            // The composer alone (the view without its search) is never taken for it: nothing is clicked or typed then.
            Assert.That(WindowsDesktopMessagingAutomation.ChatSearchField([Composer], Window), Is.Null);
            Assert.That(WindowsDesktopMessagingAutomation.ChatSearchField([], Window), Is.Null);
        });
    }

    [Test]
    public void OnlyThatFieldHoldingTheFocusLetsTheNameBeTyped()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.HoldsTheFocus(Search, [Composer, Search with { HasFocus = true }]), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.HoldsTheFocus(Search, [Composer with { HasFocus = true }, Search]), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.HoldsTheFocus(Search, [Search]), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.HoldsTheFocus(Search, []), Is.False);
        });
    }

    [Test]
    public void TheWorkersBoxesAreRead()
    {
        using JsonDocument answer = JsonDocument.Parse(
            """
            {"ok":true,"content":true,
             "focused":{"kind":"DataItem","name":"Ana","editable":false,"id":"7.1","dialog":true,"box":{"x":-10,"y":20,"w":300,"h":40}},
             "fields":[{"id":"7.2","box":{"x":1,"y":2,"w":3,"h":4},"focused":true},{"id":"7.3","box":null}]}
            """);

        ClientInteraction read = UiaClientInteractionProbe.Parse(answer.RootElement);
        IReadOnlyList<ClientField> fields = UiaClientInteractionProbe.ParseFields(answer.RootElement);

        Assert.Multiple(() =>
        {
            Assert.That(read.Focused?.Box, Is.EqualTo(new ScreenBox(-10, 20, 300, 40)));
            Assert.That(read.Focused?.Box?.CentreX, Is.EqualTo(140));
            Assert.That(read.Focused?.Box?.CentreY, Is.EqualTo(40));
            Assert.That(fields, Is.EqualTo(new[] { new ClientField("7.2", new ScreenBox(1, 2, 3, 4), HasFocus: true) }));
        });
    }

    // A person under two names: the account a row of the switcher gives, and the titles it may be matched in.
    [TestCase("Ana, usuario, ana.91", "ana.91")]
    [TestCase("Ana, usuario", null)]
    [TestCase("Ana", null)]
    [TestCase("Ana Pérez, usuario, anap", null)]
    [TestCase("Ana, Bea, Carlos", null)]
    [TestCase("Ana, Canal de texto, Mi servidor", null)]
    public void OnlyARowNamedExactlyGivesItsAccount(string row, string? account) =>
        Assert.That(WindowsDesktopMessagingAutomation.RowAccount(row, "Ana"), Is.EqualTo(account));

    [Test]
    public void AnAccountOnlyCountsInTheConversationsHeader()
    {
        ScreenBox window = new(6, 1, 1364, 730);
        Assert.Multiple(() =>
        {
            // Measured: a button of the header, at 56 px with a band of 125 at 125 %.
            Assert.That(WindowsDesktopMessagingAutomation.ShownInHeader([new(339, 56, 41, 22)], window, 125), Is.True);
            // The list of chats beside it, or a message below, may show that account while another chat is open.
            Assert.That(WindowsDesktopMessagingAutomation.ShownInHeader([new(100, 300, 60, 20)], window, 125), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.ShownInHeader([], window, 125), Is.False);
        });
    }

    // Measured on the real chat, at 125 %: the same words as a preview in the list and as the message in the conversation.
    [Test]
    public void OnlyWhatLiesInTheConversationsPaneCountsAsAMessage()
    {
        ScreenBox window = new(-975, 1073, 1600, 1000);
        ScreenBox preview = new(window.Left + 177, 1400, 232, 18);
        ScreenBox message = new(window.Left + 701, 1815, 294, 18);
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.InConversationPane([preview], window, 500), Is.Zero);
            Assert.That(WindowsDesktopMessagingAutomation.InConversationPane([preview, message], window, 500), Is.EqualTo(1));
            Assert.That(WindowsDesktopMessagingAutomation.InConversationPane([], window, 500), Is.Zero);
        });
    }

    [Test]
    public void TheWorkersPlacesOfANameAreRead()
    {
        using JsonDocument answer = JsonDocument.Parse("""{"ok":true,"shownAt":[{"x":1,"y":2,"w":3,"h":4}]}""");
        using JsonDocument none = JsonDocument.Parse("""{"ok":true,"shownAt":[]}""");
        Assert.Multiple(() =>
        {
            Assert.That(UiaClientInteractionProbe.ParseShownBoxes(answer.RootElement), Is.EqualTo(new[] { new ScreenBox(1, 2, 3, 4) }));
            Assert.That(UiaClientInteractionProbe.ParseShownBoxes(none.RootElement), Is.Empty);
            Assert.That(UiaClientInteractionProbe.ParseShownBoxes(null), Is.Empty);
        });
    }

    [Test]
    public void OnlyADirectChatsTitleCanBeMatchedByTheAccount()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.DirectChatTitle("@Ana - Discord"), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.DirectChatTitle("#general | Amigos - Discord"), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.DirectChatTitle("Discord"), Is.False);
        });
    }

    [Test]
    public void AWorkerThatDidNotAnswerShowsNoFields()
    {
        using JsonDocument failed = JsonDocument.Parse("""{"ok":false,"error":"active_window_not_found"}""");
        Assert.Multiple(() =>
        {
            Assert.That(UiaClientInteractionProbe.ParseFields(failed.RootElement), Is.Empty);
            Assert.That(UiaClientInteractionProbe.ParseFields(null), Is.Empty);
        });
    }
}
