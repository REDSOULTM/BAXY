using System.Diagnostics;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo X1 (tandas n1/n2 en el notebook, fable/estab-fase3 9b7d8d757, t1-c09 «mandale a Ron92 por discord que hoy no
/// llego a jugar, que arranquen sin mi»). n2: el cliente ya mostraba el MD de Ron92 (lo dejó n1 t4-c03), el título lo
/// nombró y message.recipient.resolve volvió en 0,2 s; message.send se verificó. n1: el cliente estaba en otra vista,
/// la búsqueda tardó 8 s y volvió «recipient_identity_not_verified» con efecto: tras teclear el nombre se pulsaba la
/// primera fila a los 1,2 s fijos, cuando el cliente aún no había filtrado (G1 midió el texto tecleado 0,6–2,6 s tarde
/// en esa máquina), y se abría otro chat. Ahora la fila se pulsa cuando el resultado activo nombra al destinatario.
/// Lecturas guionizadas: nada aquí pulsa ni teclea.
/// </summary>
[TestFixture]
public sealed class X1EnvioBusquedaTests
{
    private static readonly ClientFocus RecipientRow = new("ListItem", "Ron92 .wolfsoultm.4191", false, "42.9.8");
    private static readonly ClientFocus RecentRow = new("ListItem", "general, Canal de texto, Servidor", false, "42.9.5");
    private static readonly ClientFocus SearchInput = new("Edit", "Quick switcher", true, "42.9.3");
    private static readonly TimeSpan Poll = TimeSpan.FromMilliseconds(5);
    private static readonly TimeSpan Slack = TimeSpan.FromMilliseconds(15);

    private static Func<CancellationToken, ValueTask<ClientInteraction>> Script(params ClientInteraction[] reads)
    {
        int next = 0;
        return _ => ValueTask.FromResult(reads[Math.Min(next++, reads.Length - 1)]);
    }

    private static ClientInteraction Focused(ClientFocus focus) => new(true, false, focus);

    private static bool NamesRon92(string name) => WindowsDesktopMessagingAutomation.NamesRecipient(name, "Ron92");

    // n1: the active result is still the row from before the filter; it names the recipient later, and only then
    // does the wait end (the old fixed 1.2 s clicked the other chat).
    [Test]
    public async Task ARecipientRowDrawnLateIsWaitedFor()
    {
        var clock = Stopwatch.StartNew();
        (bool named, string? row) = await WindowsDesktopMessagingAutomation.AwaitNamedResultAsync(
            Script(Focused(RecentRow), Focused(RecentRow), Focused(RecentRow), Focused(RecipientRow)),
            NamesRon92, Poll, CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(named, Is.True);
            Assert.That(row, Is.EqualTo(RecipientRow.Name));
            Assert.That(clock.Elapsed, Is.LessThan(WindowsDesktopMessagingAutomation.SearchResultBudget));
        });
    }

    // Contracaso «el turno no se alarga»: a client that filters at once ends the wait before the old fixed 1.2 s.
    [Test]
    public async Task ARecipientRowSeenAtOnceEndsBeforeTheOldFixedWait()
    {
        var clock = Stopwatch.StartNew();
        (bool named, _) = await WindowsDesktopMessagingAutomation.AwaitNamedResultAsync(
            Script(Focused(RecipientRow)), NamesRon92, Poll, CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(named, Is.True);
            Assert.That(clock.Elapsed, Is.LessThan(WindowsDesktopMessagingAutomation.UnreadResultWait));
        });
    }

    // A row that never names the recipient is waited for the whole budget, never past it, and is said (C3).
    [Test]
    public async Task ARowThatNeverNamesTheRecipientEndsAtTheBudget()
    {
        var clock = Stopwatch.StartNew();
        (bool named, string? row) = await WindowsDesktopMessagingAutomation.AwaitNamedResultAsync(
            Script(Focused(RecentRow)), NamesRon92, Poll, CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(named, Is.False);
            Assert.That(row, Is.EqualTo(RecentRow.Name));
            Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(WindowsDesktopMessagingAutomation.SearchResultBudget - Slack));
            Assert.That(clock.Elapsed, Is.LessThan(WindowsDesktopMessagingAutomation.SearchResultBudget + TimeSpan.FromSeconds(1)));
        });
    }

    // Contracaso: with no result row to read (nothing answers, or the focus stays on the input) the old fixed wait is
    // kept whole and no longer, and no row is said (C3: nothing is clicked after it).
    [Test]
    public async Task WithNoRowToReadTheOldFixedWaitIsKept()
    {
        foreach (ClientInteraction read in new[] { ClientInteraction.Unanswered, Focused(SearchInput) })
        {
            var clock = Stopwatch.StartNew();
            (bool named, string? row) = await WindowsDesktopMessagingAutomation.AwaitNamedResultAsync(
                Script(read), NamesRon92, Poll, CancellationToken.None);
            Assert.Multiple(() =>
            {
                Assert.That(named, Is.False);
                Assert.That(row, Is.Null);
                Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(WindowsDesktopMessagingAutomation.UnreadResultWait - Slack));
                Assert.That(clock.Elapsed, Is.LessThan(WindowsDesktopMessagingAutomation.SearchResultBudget));
            });
        }

        Assert.That(WindowsDesktopMessagingAutomation.UnreadResultWait, Is.EqualTo(TimeSpan.FromMilliseconds(1200)));
    }

    // The adapter waits for the named row instead of the fixed 1.2 s, matches rows as it matches the title, clicks the
    // row only once it named the recipient (C3), and the resolve never presses Enter in the client's search (the send
    // is message.send's alone: nothing is sent twice).
    [Test]
    public void TheSearchWaitsForTheNamedRowAndNeverSends()
    {
        DirectoryInfo? root = new(AppContext.BaseDirectory);
        while (root is not null && !File.Exists(Path.Combine(root.FullName, "Baxy.slnx")))
        {
            root = root.Parent;
        }

        Assert.That(root, Is.Not.Null, "Baxy.slnx was not found.");
        string source = File.ReadAllText(Path.Combine(
            root!.FullName, "src", "Baxy.Providers.Windows", "External", "DesktopMessagingAdapter.cs"));
        int typed = source.IndexOf("(bool named, string? row) = await AwaitNamedResultAsync(", StringComparison.Ordinal);
        int clicked = source.IndexOf("ClickAtRelative(handle, 0.5, DiscordSwitcherFirstRowHeightFraction);", StringComparison.Ordinal);
        Assert.Multiple(() =>
        {
            Assert.That(typed, Is.GreaterThan(0));
            Assert.That(clicked, Is.GreaterThan(typed));
            Assert.That(source, Does.Contain("Read, name => NamesRecipient(name, recipient), InteractionPoll"));
            Assert.That(source[typed..clicked], Does.Contain("if (named)"));
            Assert.That(source, Does.Not.Contain("await Task.Delay(1200, cancellationToken)"));
            Assert.That(source[typed..clicked], Does.Not.Contain("VirtualKeyReturn"));
        });
    }
}
