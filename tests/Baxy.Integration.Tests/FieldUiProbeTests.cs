using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class FieldUiProbeTests
{
    private static readonly TimeSpan Stable = TimeSpan.FromMilliseconds(1000);

    [Test]
    public void TextLineIsATurnAndKeepsItsTags()
    {
        ProbeCommand command = FieldUiProbe.ParseCommand(
            """{"text":"ponme algo","conversation":"t1-c01","turn":2}""");

        Assert.Multiple(() =>
        {
            Assert.That(command.Kind, Is.EqualTo(ProbeCommandKind.Turn));
            Assert.That(command.Text, Is.EqualTo("ponme algo"));
            Assert.That((string?)command.Tags?["conversation"], Is.EqualTo("t1-c01"));
            Assert.That((int?)command.Tags?["turn"], Is.EqualTo(2));
        });
    }

    [TestCase("""{"cmd":"session.new"}""")]
    [TestCase("""{"cmd":"new-session"}""")]
    [TestCase("""{"cmd":"sessions/new"}""")]
    public void SessionCommandOpensANewSession(string line)
    {
        Assert.That(
            FieldUiProbe.ParseCommand(line).Kind,
            Is.EqualTo(ProbeCommandKind.NewSession));
    }

    [Test]
    public void UnknownCommandIsReportedNotTypedIntoTheWindow()
    {
        // Contracaso: un cmd desconocido nunca se teclea como texto.
        ProbeCommand command = FieldUiProbe.ParseCommand(
            """{"cmd":"session.drop","text":"hola"}""");

        Assert.Multiple(() =>
        {
            Assert.That(command.Kind, Is.EqualTo(ProbeCommandKind.Invalid));
            Assert.That(command.Diagnostic, Is.EqualTo("unknown_cmd"));
        });
    }

    [TestCase("")]
    [TestCase("   ")]
    [TestCase("""{"text":"   "}""")]
    [TestCase("""{"expect":"sin texto"}""")]
    public void BlankLinesAndEmptyTextAreSkipped(string line)
    {
        Assert.That(FieldUiProbe.ParseCommand(line).Kind, Is.EqualTo(ProbeCommandKind.Skip));
    }

    [TestCase("{not json", "invalid_json")]
    [TestCase("[1,2]", "not_an_object")]
    public void MalformedLinesAreInvalid(string line, string diagnostic)
    {
        ProbeCommand command = FieldUiProbe.ParseCommand(line);

        Assert.Multiple(() =>
        {
            Assert.That(command.Kind, Is.EqualTo(ProbeCommandKind.Invalid));
            Assert.That(command.Diagnostic, Is.EqualTo(diagnostic));
        });
    }

    [Test]
    public void MillisecondArgumentsFallBackWhenAbsentOrInvalid()
    {
        string[] arguments = ["--ui-turn-timeout-ms=90000", "--ui-stable-ms=abc"];

        Assert.Multiple(() =>
        {
            Assert.That(
                FieldUiProbe.MillisecondsOf(arguments, FieldUiProbe.TurnTimeoutArgument, Stable),
                Is.EqualTo(TimeSpan.FromSeconds(90)));
            Assert.That(
                FieldUiProbe.MillisecondsOf(arguments, FieldUiProbe.StableArgument, Stable),
                Is.EqualTo(Stable));
            Assert.That(
                FieldUiProbe.MillisecondsOf(["--ui-stable-ms=0"], FieldUiProbe.StableArgument, Stable),
                Is.EqualTo(Stable));
        });
    }

    [Test]
    public void SurfaceParsesTheScriptResult()
    {
        ProbeSurface surface = ProbeSurface.Parse(
            "\"{\\\"input\\\":true,\\\"enabled\\\":true,\\\"draft\\\":0,\\\"progress\\\":0,\\\"rows\\\":7}\"");

        Assert.Multiple(() =>
        {
            Assert.That(surface.Rows, Is.EqualTo(7));
            Assert.That(surface.Idle, Is.True);
            Assert.That(ProbeSurface.Parse("null").Idle, Is.False);
            Assert.That(ProbeSurface.Parse("garbage").Idle, Is.False);
        });
    }

    [Test]
    public void TurnSettlesOnlyAfterIdleAndStableRows()
    {
        var tracker = new TurnSettleTracker(rowsBefore: 4, Stable);

        Assert.Multiple(() =>
        {
            // El borrador sigue lleno mientras /turn no vuelve.
            Assert.That(tracker.Observe(Ms(0), Surface(rows: 5, draft: 10)), Is.False);
            // Progreso visible: aún no.
            Assert.That(tracker.Observe(Ms(500), Surface(rows: 6, progress: 8)), Is.False);
            // Ociosa, pero recién llega una fila: empieza la ventana.
            Assert.That(tracker.Observe(Ms(900), Surface(rows: 7)), Is.False);
            Assert.That(tracker.Observe(Ms(1500), Surface(rows: 7)), Is.False);
            // Una fila tardía (la respuesta compuesta) reinicia la ventana.
            Assert.That(tracker.Observe(Ms(1800), Surface(rows: 8)), Is.False);
            Assert.That(tracker.Observe(Ms(2700), Surface(rows: 8)), Is.False);
            Assert.That(tracker.Observe(Ms(2800), Surface(rows: 8)), Is.True);
            Assert.That(tracker.Grew, Is.True);
        });
    }

    [Test]
    public void BeforePlusTwoRowsIsNotEnoughToSettle()
    {
        // Contracaso de la espera antigua: dos filas nuevas con el turno en
        // curso (fila del usuario + progreso) no terminan el turno.
        var tracker = new TurnSettleTracker(rowsBefore: 1, Stable);

        Assert.Multiple(() =>
        {
            Assert.That(tracker.Observe(Ms(0), Surface(rows: 3, draft: 5)), Is.False);
            Assert.That(tracker.Observe(Ms(5000), Surface(rows: 3, draft: 5)), Is.False);
        });
    }

    [Test]
    public void DisabledInputNeverSettles()
    {
        var tracker = new TurnSettleTracker(rowsBefore: 0, Stable);

        Assert.Multiple(() =>
        {
            Assert.That(tracker.Observe(Ms(0), Surface(rows: 2, enabled: false)), Is.False);
            Assert.That(tracker.Observe(Ms(5000), Surface(rows: 2, enabled: false)), Is.False);
            // Vuelve a habilitarse: la ventana empieza ahí, no antes.
            Assert.That(tracker.Observe(Ms(5100), Surface(rows: 2)), Is.False);
            Assert.That(tracker.Observe(Ms(6100), Surface(rows: 2)), Is.True);
        });
    }

    [Test]
    public void SessionClearThatShrinksTheLogStillSettles()
    {
        // session.new vacía el registro y añade su fila SYSTEM: menos filas
        // que al empezar no es un turno publicado, pero sí termina.
        var tracker = new TurnSettleTracker(rowsBefore: 9, Stable);

        Assert.Multiple(() =>
        {
            Assert.That(tracker.Observe(Ms(0), Surface(rows: 1)), Is.False);
            Assert.That(tracker.Observe(Ms(1000), Surface(rows: 1)), Is.True);
            Assert.That(tracker.Grew, Is.False);
        });
    }

    [Test]
    public void FreshRowsAreTheNewestFirstPrefix()
    {
        // La lista se pinta con la más nueva primero (useEventStream antepone
        // cada entrada): lo nuevo del turno 2 es la cabeza, no la cola.
        ProbeRow[] before = [Row("BAXY", "Hola."), Row("YOU", "hola"), Row("SYSTEM", "new session")];
        ProbeRow[] after =
        [
            Row("BAXY", "Son las diez."),
            Row("YOU", "¿Qué hora es?"),
            .. before,
        ];

        int fresh = ProbeRow.FreshCount(before, after);

        Assert.Multiple(() =>
        {
            Assert.That(fresh, Is.EqualTo(2));
            Assert.That(
                after[..fresh].Select(row => row.Msg),
                Is.EqualTo(new[] { "Son las diez.", "¿Qué hora es?" }));
        });
    }

    [Test]
    public void FreshRowsAtTheCapComeFromTheHeadNotTheCount()
    {
        // Contracaso: al tope de filas el recuento no crece; las dos nuevas
        // entran por la cabeza y las dos más viejas salen por la cola.
        ProbeRow[] before = Enumerable.Range(0, 80).Select(n => Row("BAXY", $"r{n}")).ToArray();
        ProbeRow[] after = [Row("BAXY", "nueva"), Row("YOU", "pregunta"), .. before[..78]];

        Assert.Multiple(() =>
        {
            Assert.That(ProbeRow.FreshCount(before, after), Is.EqualTo(2));
            // Nada cambió: nada nuevo.
            Assert.That(ProbeRow.FreshCount(before, before), Is.EqualTo(0));
        });
    }

    [Test]
    public void RepeatedRowsDoNotFoolTheAlignment()
    {
        // La misma pareja repetida: alinear sólo la cabeza diría «0 nuevas».
        ProbeRow[] before = [Row("BAXY", "Hecho."), Row("YOU", "otra vez"), Row("SYSTEM", "new session")];
        ProbeRow[] after = [Row("BAXY", "Hecho."), Row("YOU", "otra vez"), .. before];

        Assert.That(ProbeRow.FreshCount(before, after), Is.EqualTo(2));
    }

    [Test]
    public void FreshRowsWhenNothingWasShownOrTheLogWasCleared()
    {
        ProbeRow[] after = [Row("BAXY", "Hola."), Row("YOU", "hola")];

        Assert.Multiple(() =>
        {
            Assert.That(ProbeRow.FreshCount([], after), Is.EqualTo(2));
            // La sesión se vació a mitad: nada coincide y todo lo que se ve es nuevo.
            Assert.That(ProbeRow.FreshCount([Row("BAXY", "vieja")], after), Is.EqualTo(2));
        });
    }

    [Test]
    public void SameCountWithANewHeadIsStillMovingAtTheCap()
    {
        var tracker = new TurnSettleTracker(rowsBefore: 80, Stable, headBefore: "a");

        Assert.Multiple(() =>
        {
            Assert.That(tracker.Observe(Ms(0), Surface(rows: 80, head: "a")), Is.False);
            Assert.That(tracker.Grew, Is.False);
            // Llega la respuesta: mismas 80 filas, otra cabeza. La ventana se reinicia.
            Assert.That(tracker.Observe(Ms(900), Surface(rows: 80, head: "b")), Is.False);
            Assert.That(tracker.Observe(Ms(1500), Surface(rows: 80, head: "b")), Is.False);
            Assert.That(tracker.Observe(Ms(2500), Surface(rows: 80, head: "b")), Is.True);
            Assert.That(tracker.Grew, Is.True);
        });
    }

    [Test]
    public void SendGateGoesAtOnceWhenThePreviousTurnSettled()
    {
        var gate = new SendGate(Stable, Ms(15000), Ms(60000), requireStable: false);

        Assert.That(gate.Observe(Ms(0), Surface(rows: 3)), Is.EqualTo(SendGateState.Ready));
    }

    [Test]
    public void SendGateWaitsForAQuietSurfaceAfterAnUnsettledTurn()
    {
        // El turno anterior agotó su tope con /turn pendiente: teclear ya
        // sobrescribiría su borrador y su respuesta tardía caería en este.
        var gate = new SendGate(Stable, Ms(15000), Ms(60000), requireStable: true);

        Assert.Multiple(() =>
        {
            Assert.That(gate.Observe(Ms(0), Surface(rows: 3, draft: 9)), Is.EqualTo(SendGateState.Wait));
            Assert.That(gate.Observe(Ms(500), Surface(rows: 5)), Is.EqualTo(SendGateState.Wait));
            Assert.That(gate.Observe(Ms(1000), Surface(rows: 5)), Is.EqualTo(SendGateState.Wait));
            Assert.That(gate.Observe(Ms(1500), Surface(rows: 5)), Is.EqualTo(SendGateState.Ready));
        });
    }

    [Test]
    public void SendGateGivesUpWithoutSendingWhenNeverIdle()
    {
        var gate = new SendGate(Stable, Ms(15000), Ms(60000), requireStable: false);

        Assert.Multiple(() =>
        {
            Assert.That(gate.Observe(Ms(0), Surface(rows: 3, draft: 9)), Is.EqualTo(SendGateState.Wait));
            Assert.That(
                gate.Observe(Ms(60000), Surface(rows: 3, draft: 9)),
                Is.EqualTo(SendGateState.NotIdle));
        });
    }

    [Test]
    public void SendGateNeverTakesASuspendedReadForAnEmptyLog()
    {
        // Recién restaurada, la lectura vuelve vacía: no es «cero filas».
        var gate = new SendGate(Stable, Ms(15000), Ms(60000), requireStable: false);

        Assert.Multiple(() =>
        {
            Assert.That(gate.Observe(Ms(0), default), Is.EqualTo(SendGateState.Wait));
            Assert.That(gate.Observe(Ms(800), Surface(rows: 6)), Is.EqualTo(SendGateState.Ready));
        });

        var never = new SendGate(Stable, Ms(15000), Ms(60000), requireStable: false);
        Assert.That(never.Observe(Ms(15000), default), Is.EqualTo(SendGateState.NoSurface));
    }

    [TestCase("200", true)]
    [TestCase("204", true)]
    [TestCase("409", false)]
    [TestCase("500", false)]
    [TestCase("timeout", false)]
    [TestCase("unreachable", false)]
    [TestCase("", false)]
    public void OnlyA2xxResetsTheSession(string status, bool reset)
    {
        Assert.That(FieldUiProbe.IsSessionReset(status), Is.EqualTo(reset));
    }

    [Test]
    public void ProbeAlwaysShutsDownAndNeverLetsAScriptFailureEscape()
    {
        string root = RepositoryRoot();
        string probe = File.ReadAllText(Path.Combine(root, "src", "Baxy.App", "FieldUiProbe.cs"));
        string window = File.ReadAllText(Path.Combine(root, "src", "Baxy.App", "MainWindow.xaml.cs"));

        Assert.Multiple(() =>
        {
            // Todo ExecuteScriptAsync pasa por ProbePage (que atrapa el campo
            // suspendido o la vista cerrada y pone tope a cada lectura): sólo hay
            // una llamada directa, la que se le entrega.
            Assert.That(probe.Split("core.ExecuteScriptAsync(").Length - 1, Is.EqualTo(1));
            Assert.That(probe, Does.Match(@"new ProbePage\(\s*script => core\.ExecuteScriptAsync\(script\)"));
            // Encargo PH: cada espera de la sonda deja de esperar a una página colgada.
            Assert.That(probe.Split("!page.Unresponsive)").Length - 1, Is.EqualTo(4));
            Assert.That(probe, Does.Contain("Terminal(\"error\""));
            // Rewritten by encargo I2 (tanda fin2 t4: a llama-server outlived the probe): the probe still always ends
            // the process, now by the tray's own «Salir» (RequestExit: the window's ordered teardown, then Shutdown);
            // only without a presence host does it shut down directly.
            Assert.That(
                window,
                Does.Match(@"finally\s*\{[^{}]*if \(_presence is not null\)\s*\{\s*_presence\.RequestExit\(\);\s*\}"
                    + @"\s*else\s*\{\s*Application\.Current\.Shutdown\(\);"));
            Assert.That(
                window,
                Does.Match(@"Close\(\);\s*if \(_presence is not null\)\s*\{\s*Application\.Current\?\.Shutdown\(\);"));
        });
    }

    [Test]
    public async Task HungReadReturnsWithinItsBudgetAndThePageIsMarkedUnresponsive()
    {
        // Encargo PH (tanda n3 t4): ExecuteScriptAsync no volvió y la sonda esperó 7 h.
        int calls = 0;
        var never = new TaskCompletionSource<string>();
        var page = new ProbePage(
            _ =>
            {
                calls++;
                return never.Task;
            },
            Ms(50),
            Ms(200));

        Assert.That(await page.RunAsync("read"), Is.Null);
        Assert.Multiple(() =>
        {
            Assert.That(page.Hangs, Is.EqualTo(1));
            Assert.That(page.Unresponsive, Is.False);
        });

        // Mientras la lectura colgada no vuelve, no se encola otra.
        Assert.That(await page.RunAsync("read"), Is.Null);
        Assert.That(calls, Is.EqualTo(1));

        await Task.Delay(Ms(300));
        Assert.Multiple(() =>
        {
            Assert.That(page.Unresponsive, Is.True);
            Assert.That(page.Hangs, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task PageThatAnswersAgainIsReadNormally()
    {
        // Contracaso: si la lectura colgada vuelve, la página deja de estar
        // colgada y las lecturas siguientes se ejecutan.
        var first = new TaskCompletionSource<string>();
        int calls = 0;
        var page = new ProbePage(
            _ => ++calls == 1 ? first.Task : Task.FromResult("\"ok\""),
            Ms(50),
            Ms(50));

        Assert.That(await page.RunAsync("read"), Is.Null);
        await Task.Delay(Ms(100));
        Assert.That(page.Unresponsive, Is.True);

        first.SetResult("tarde");
        Assert.That(page.Unresponsive, Is.False);
        Assert.That(await page.RunAsync("read"), Is.EqualTo("\"ok\""));
        Assert.That(calls, Is.EqualTo(2));
    }

    [Test]
    public async Task QuickAnswersAndClosedViewsAreNeverHangs()
    {
        // Contracaso: una lectura normal no cuenta como colgada, y una vista
        // suspendida o cerrada (WebView2 lanza) es «sin superficie», no un cuelgue.
        var answering = new ProbePage(_ => Task.FromResult("\"x\""), Ms(50), Ms(50));
        var closed = new ProbePage(
            _ => throw new InvalidOperationException("suspendida"),
            Ms(50),
            Ms(50));
        var faulted = new ProbePage(
            _ => Task.FromException<string>(new InvalidOperationException("cerrada")),
            Ms(50),
            Ms(50));

        Assert.That(await answering.RunAsync("read"), Is.EqualTo("\"x\""));
        Assert.That(await closed.RunAsync("read"), Is.Null);
        Assert.That(await faulted.RunAsync("read"), Is.Null);
        Assert.Multiple(() =>
        {
            Assert.That(answering.Hangs + closed.Hangs + faulted.Hangs, Is.Zero);
            Assert.That(answering.Unresponsive || closed.Unresponsive || faulted.Unresponsive, Is.False);
        });
    }

    [Test]
    public void ProbeWindowRestoresOnlyWhenMinimized()
    {
        string source = File.ReadAllText(
            Path.Combine(RepositoryRoot(), "src", "Baxy.App", "FieldUiProbe.cs"));

        Assert.Multiple(() =>
        {
            // SW_SHOWNOACTIVATE: restaurar sin quitarle el foco a la persona.
            Assert.That(source, Does.Contain("ShowNoActivate = 4"));
            // Sólo se toca una ventana suspendida: minimizada u oculta por la X.
            Assert.That(source, Does.Contain("if (!window.IsMinimized && !window.IsHidden)"));
            // Oculta, se muestra sin activar (SW_SHOWNA).
            Assert.That(source, Does.Contain("_window.ShowActivated = false;"));
            Assert.That(source, Does.Not.Contain("Activate()"));
            Assert.That(source, Does.Not.Contain("SetForegroundWindow"));
        });
    }

    private static TimeSpan Ms(int value) => TimeSpan.FromMilliseconds(value);

    private static ProbeRow Row(string src, string msg) => new(src, msg, "10:00:00");

    private static string RepositoryRoot()
    {
        DirectoryInfo? root = new(TestContext.CurrentContext.TestDirectory);
        while (root is not null && !File.Exists(Path.Combine(root.FullName, "Baxy.slnx")))
        {
            root = root.Parent;
        }

        Assert.That(root, Is.Not.Null);
        return root!.FullName;
    }

    private static ProbeSurface Surface(
        int rows,
        int draft = 0,
        int progress = 0,
        bool enabled = true,
        string? head = null) =>
        new(InputPresent: true, InputEnabled: enabled, draft, progress, rows, head);
}
