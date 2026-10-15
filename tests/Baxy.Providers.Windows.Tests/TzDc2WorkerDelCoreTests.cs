using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo TZ-DC2 (tandas z3/z4 en el notebook, fable/estab-fase3 a99fa5bea, t1-c09 t1 «mandale a Ron92 por discord que
/// hoy no llego a jugar, que arranquen sin mi», Discord abierto en otra vista). z3: message.recipient.resolve volvió a
/// los 7,46 s con «recipient_identity_not_verified» y efecto; message.send no corrió. Medido en el registro de procesos
/// de la tanda: el Core lanzó un PowerShell 25 ms después de empezar el resolve (17:17:29,536 → 17:17:29,561): el
/// worker de UI Automation propio de la sonda de mensajería, que cada Core arrancaba en su primera búsqueda (el de
/// computer use ya estaba arriba desde el arranque del Core, 17:14:18). Hasta que contestaba, cada lectura era
/// «Unanswered»: la búsqueda tomó el camino a ciegas (1,4 s fijos tras el atajo, 1,2 s fijos tras teclear, pulsar la
/// primera fila, 3 s de título sin el nombre), 0,15 + 1,0 + 0,3 + 1,4 + 0,24 + 1,2 + 3,0 ≈ 7,3 s. Las 13 búsquedas del
/// notebook (n1…z4) son bimodales: ~4,0 s a ciegas (5 enviadas, 2 fallidas: n1 t1 y z3 t1) y ~2,5–3,0 s leídas (4 de 4).
/// Ahora la sonda lee por el worker del Core, arrancado por su prewarm, y la primera lectura de la primera búsqueda
/// contesta. Lecturas guionizadas: nada aquí pulsa ni teclea.
/// </summary>
[TestFixture]
public sealed class TzDc2WorkerDelCoreTests
{
    // The views the warm path reads in Discord (X1 / R24): the open chat's composer, the switcher's input, the row.
    private const string OtherChatComposer =
        """{"ok":true,"error":"","content":true,"focused":{"kind":"Edit","name":"Enviar mensaje a #general","editable":true,"id":"42.7.1"}}""";
    private const string SwitcherInput =
        """{"ok":true,"error":"","content":true,"focused":{"kind":"Edit","name":"Quick switcher","editable":true,"id":"42.9.3"}}""";
    private const string RecipientRow =
        """{"ok":true,"error":"","content":true,"focused":{"kind":"ListItem","name":"Ron92 .wolfsoultm.4191","editable":false,"id":"42.9.8"}}""";

    private static readonly TimeSpan Poll = TimeSpan.FromMilliseconds(5);

    /// <summary>A worker the Core's prewarm already started: its own prewarm returns at once.</summary>
    private sealed class StartedWorker(params string[] answers) : IUiaWorker
    {
        private int _next;

        internal int Commands => _next;

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken) =>
            ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(answers[Math.Min(_next++, answers.Length - 1)]));
    }

    /// <summary>A worker still starting (z3: born with the search): its prewarm ends only when released.</summary>
    private sealed class StartingWorker(string answer) : IUiaWorker
    {
        internal TaskCompletionSource Up { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);

        internal int Commands { get; private set; }

        public ValueTask PrewarmAsync(CancellationToken cancellationToken) => new(Up.Task);

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            Commands++;
            return ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(answer));
        }
    }

    private static string Name(ClientInteraction read) => read.Focused?.Name ?? string.Empty;

    // z3 corrected: the first read of the Core's first search answers (no earlier prewarm of the probe, as on the
    // «any» path), the switcher's input is seen at once and the row that names the recipient ends the wait.
    [Test]
    public async Task TheFirstSearchOfACoreReadsTheClientThroughTheCoresWorker()
    {
        var worker = new StartedWorker(OtherChatComposer, SwitcherInput, SwitcherInput, RecipientRow);
        var probe = new UiaClientInteractionProbe(worker);
        Func<CancellationToken, ValueTask<ClientInteraction>> read = token => probe.ReadAsync(42, content: false, token);

        ClientInteraction before = await read(CancellationToken.None);
        var clock = Stopwatch.StartNew();
        WindowsDesktopMessagingAutomation.InputWait input = await WindowsDesktopMessagingAutomation.AwaitOpenedInputAsync(
            read, before, WindowsDesktopMessagingAutomation.SearchInputBudget, Poll, CancellationToken.None);
        bool named = await WindowsDesktopMessagingAutomation.AwaitNamedResultAsync(
            read, name => name.Contains("Ron92", StringComparison.Ordinal), Poll, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(before.Answered, Is.True);
            Assert.That(Name(before), Is.EqualTo("Enviar mensaje a #general"));
            Assert.That(input, Is.EqualTo(WindowsDesktopMessagingAutomation.InputWait.Opened));
            Assert.That(named, Is.True);
            Assert.That(clock.Elapsed, Is.LessThan(WindowsDesktopMessagingAutomation.SearchInputBudget));
        });
    }

    // Contracaso (the R24 promise kept): a worker still starting is never waited for by a turn. Its reads are
    // Unanswered and it is not asked; the search keeps its timed path (what z3 ran: the whole 1.4 s, «Unanswered»).
    // Once it is up, the next read answers.
    [Test]
    public async Task AWorkerStillStartingIsNotWaitedForAndAnswersOnceUp()
    {
        var worker = new StartingWorker(SwitcherInput);
        var probe = new UiaClientInteractionProbe(worker);
        Func<CancellationToken, ValueTask<ClientInteraction>> read = token => probe.ReadAsync(42, content: false, token);

        ClientInteraction before = await read(CancellationToken.None);
        var clock = Stopwatch.StartNew();
        WindowsDesktopMessagingAutomation.InputWait input = await WindowsDesktopMessagingAutomation.AwaitOpenedInputAsync(
            read, before, TimeSpan.FromMilliseconds(60), Poll, CancellationToken.None);
        TimeSpan waited = clock.Elapsed;
        int askedWhileStarting = worker.Commands;
        worker.Up.SetResult();
        ClientInteraction after = ClientInteraction.Unanswered;
        for (int attempt = 0; attempt < 200 && !after.Answered; attempt++)
        {
            after = await read(CancellationToken.None);
            if (!after.Answered)
            {
                await Task.Delay(5);
            }
        }

        Assert.Multiple(() =>
        {
            Assert.That(before, Is.EqualTo(ClientInteraction.Unanswered));
            Assert.That(input, Is.EqualTo(WindowsDesktopMessagingAutomation.InputWait.Unanswered));
            Assert.That(waited, Is.GreaterThanOrEqualTo(TimeSpan.FromMilliseconds(50)));
            Assert.That(askedWhileStarting, Is.Zero);
            Assert.That(after.Answered, Is.True);
            Assert.That(Name(after), Is.EqualTo("Quick switcher"));
        });
    }

    // Contracaso z4 (Discord opened by the turn, sent and verified in 10.1 s): with the Core's worker the client's
    // content is read from the first look, so a window that already shows it is ready without the 2 s settle.
    [Test]
    public async Task AClientOpenedByTheTurnIsReadyAtItsFirstLook()
    {
        var probe = new UiaClientInteractionProbe(new StartedWorker(OtherChatComposer));
        WindowsDesktopMessagingAutomation.ContentWait content = await WindowsDesktopMessagingAutomation.AwaitClientContentAsync(
            token => probe.ReadAsync(42, content: true, token), TimeSpan.FromSeconds(1), Poll, CancellationToken.None);
        Assert.That(content, Is.EqualTo(WindowsDesktopMessagingAutomation.ContentWait.Ready));
    }

    // The wiring: the Core's provider gives computer use and the messaging clients one UI Automation worker, the one
    // its prewarm starts (Program.cs), never a second one born with the first search.
    [Test]
    public void ComputerUseAndTheMessagingProbeShareTheCoresWorker()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-tzdc2-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            using var provider = new WindowsExternalCapabilityProvider(root);
            IExternalOperationAdapter[] adapters = Field<IExternalOperationAdapter[]>(provider, "_adapters");
            WindowsVisibleControlAdapter visible = adapters.OfType<WindowsVisibleControlAdapter>().Single();
            DesktopMessagingAdapter messaging = adapters.OfType<DesktopMessagingAdapter>().Single();
            object automation = Field<object>(messaging, "_automation");
            object probe = automation.GetType()
                .GetProperty("Probe", BindingFlags.Instance | BindingFlags.NonPublic)!
                .GetValue(automation)!;

            Assert.Multiple(() =>
            {
                Assert.That(probe, Is.InstanceOf<UiaClientInteractionProbe>());
                Assert.That(Field<IUiaWorker>(probe, "_worker"), Is.SameAs(Field<IUiaWorker>(visible, "_worker")));
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private static T Field<T>(object owner, string name) =>
        (T)(owner.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic)
            ?? throw new MissingFieldException(owner.GetType().Name, name)).GetValue(owner)!;
}
