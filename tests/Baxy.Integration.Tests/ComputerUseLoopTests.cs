using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// The computer-use loop end to end over a scripted screen and a scripted
/// mind (documentacion/computer-use/CONTRATO_VISTA_ACCION.md §4): chained
/// sub-goals, the OCR text asked only when needed, the short settle and the
/// bounded wait after app.open, the no-progress guard and the page: baseline.
/// </summary>
[TestFixture]
public sealed class ComputerUseLoopTests
{
    private string _root = string.Empty;

    [SetUp]
    public void CreateRoot()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-cu-loop-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
    }

    [TearDown]
    public void DeleteRoot()
    {
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, recursive: true);
        }
    }

    // A scripted screen and mind behind the loop's two delegates.
    private sealed class Harness
    {
        internal readonly List<JsonObject> Looks = [];
        internal readonly List<(string Operation, JsonObject Arguments)> Acts = [];
        internal readonly List<ComputerUseStepRequest> Requests = [];
        internal readonly List<TimeSpan> Delays = [];
        internal Func<JsonObject, JsonObject?> Screen { get; set; } = static _ => null;
        internal Func<ComputerUseStepRequest, MindComputerUseStep?> Mind { get; set; } = static _ => null;
        internal Func<string, JsonObject, JsonObject> Receipt { get; set; } = static (_, _) => new JsonObject { ["surfaceChanged"] = true };

        internal ComputerUseMission.Context Context(string root, ComputerUseProcedures? procedures = null) => new()
        {
            Execute = (prepared, _, _) =>
            {
                var arguments = (JsonObject)JsonNode.Parse(prepared.Arguments.GetRawText())!;
                if (prepared.OperationName == "input.visible.controls")
                {
                    Looks.Add(arguments);
                    return Task.FromResult(Respond(prepared, Screen(arguments)));
                }

                Acts.Add((prepared.OperationName, arguments));
                return Task.FromResult(Respond(prepared, Receipt(prepared.OperationName, arguments)));
            },
            Decide = (request, _) =>
            {
                Requests.Add(request);
                return Task.FromResult(Mind(request));
            },
            Registry = new RetryableOperationRegistry(Path.Combine(root, "outbox-" + Guid.NewGuid().ToString("N") + ".jsonl")),
            MarkResolved = static (registry, prepared) =>
            {
                registry.MarkResolved(prepared);
                return true;
            },
            SetStatus = static _ => { },
            Procedures = procedures,
            Delay = (delay, _) =>
            {
                Delays.Add(delay);
                return Task.CompletedTask;
            },
        };

        private static OperationResponse Respond(PreparedOperation prepared, JsonObject? result)
        {
            bool ok = result is not null;
            using JsonDocument document = JsonDocument.Parse((result ?? new JsonObject()).ToJsonString());
            return new OperationResponse(
                ProtocolTypes.OperationResponse, prepared.InvocationId, prepared.MissionId, prepared.InvocationId,
                ok ? OperationStatuses.Completed : OperationStatuses.Failed, "{}", ok, false,
                document.RootElement.Clone(), ok ? null : "view_unavailable");
        }
    }

    private static JsonObject Window(string title, string process, int processId, bool requested, JsonArray controls, params string[] text)
    {
        var view = new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["title"] = title,
                ["process"] = process,
                ["processId"] = processId,
                ["requested"] = requested,
            },
            ["controls"] = controls,
        };
        if (text.Length > 0)
        {
            view["text"] = new JsonObject { ["C"] = new JsonArray([.. text.Select(line => (JsonNode?)JsonValue.Create(line))]) };
        }

        return view;
    }

    private static JsonObject Control(int index, string kind, string name, string state = "", string? value = null) => new()
    {
        ["i"] = index,
        ["kind"] = kind,
        ["name"] = name,
        ["state"] = state,
        ["value"] = value,
    };

    private static MindComputerUseStep Step(string operation, JsonObject arguments) => new(operation, arguments, string.Empty);

    private static PendingMindPlanExecution Execution(string objective, JsonObject arguments) =>
        new(objective, [new MindPlanStep("step_1", ComputerUseMission.OperationName, objective, [], "literal", arguments)]);

    private static JsonObject Observed(ComputerUseMission.Result result) =>
        (JsonObject)JsonNode.Parse(result.Response!.Result!.Value.GetRawText())!;

    private static bool AskedText(JsonObject look) => (bool?)look["includeText"] == true;

    [Test]
    public async Task AChainedMissionRunsItsSubgoalsInOrderEachWithItsOwnApplicationCheckAndProcedure()
    {
        bool typed = false;
        var harness = new Harness
        {
            Screen = look => (string?)look["application"] switch
            {
                "Steam" => Window("Steam", "steamwebhelper", 12, true,
                    [Control(0, "Button", "Biblioteca"), Control(1, "Button", "Tienda")]),
                "Bloc de notas" => Window("Sin título - Bloc de notas", "Notepad", 30, true,
                    [Control(0, "Edit", "Texto", value: typed ? "hola" : ""), Control(1, "MenuItem", "Archivo")]),
                _ => null,
            },
            Mind = request => request.Subgoal == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Biblioteca" })
                : Step("input.text.type", new JsonObject { ["text"] = "hola" }),
        };
        harness.Receipt = (operation, _) =>
        {
            typed |= operation == "input.text.type";
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "abre la biblioteca de Steam y escribe hola en el Bloc de notas",
            ["application"] = null,
            ["successCheck"] = null,
            ["steps"] = new JsonArray
            {
                new JsonObject { ["goal"] = "ir a la biblioteca", ["application"] = "Steam", ["successCheck"] = "stepDone:input.visible.click:biblioteca" },
                new JsonObject { ["goal"] = "escribir hola", ["application"] = "Bloc de notas", ["successCheck"] = "value:Texto=hola" },
            },
        };
        var procedures = new ComputerUseProcedures(Path.Combine(_root, "procedures.v1.json"));

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root, procedures), Execution("abre la biblioteca y escribe hola", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        JsonArray subgoals = observed["subgoals"]!.AsArray();
        Assert.Multiple(() =>
        {
            Assert.That(result.Response!.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That((int?)observed["stepCount"], Is.EqualTo(2));
            Assert.That(subgoals, Has.Count.EqualTo(2));
            Assert.That((bool?)subgoals[0]!["reached"], Is.True);
            Assert.That((int?)subgoals[0]!["stepCount"], Is.EqualTo(1));
            Assert.That((string?)subgoals[0]!["satisfiedBy"], Is.EqualTo("stepDone:input.visible.click:biblioteca"));
            Assert.That((string?)subgoals[1]!["application"], Is.EqualTo("Bloc de notas"));
            Assert.That((string?)subgoals[1]!["satisfiedBy"], Is.EqualTo("value:Texto=hola"));
            Assert.That((int?)observed["steps"]![1]!["subgoal"], Is.EqualTo(1));
            Assert.That(observed.ToJsonString(), Does.Not.Contain("viewHash"));

            // The mind is given the current sub-goal and only its history.
            Assert.That(harness.Requests.Select(request => (request.Subgoal, request.SubgoalCount, request.Goal, request.Application)),
                Is.EqualTo(new[] { (0, 2, "ir a la biblioteca", (string?)"Steam"), (1, 2, "escribir hola", (string?)"Bloc de notas") }));
            Assert.That(harness.Requests[1].History, Is.Empty);
            Assert.That(harness.Requests[0].Objective, Is.EqualTo("abre la biblioteca y escribe hola"));

            // The click's receipt answers the first check without a new look; the second sub-goal looks for its own
            // application, without the Steam process the first one adopted.
            Assert.That(harness.Looks, Has.Count.EqualTo(3));
            Assert.That((string?)harness.Looks[1]["application"], Is.EqualTo("Bloc de notas"));
            Assert.That(harness.Looks[1]["processId"], Is.Null);
            Assert.That((int?)harness.Looks[2]["processId"], Is.EqualTo(30));
            Assert.That(harness.Delays, Is.All.EqualTo(ComputerUseMission.Settle));

            // Each sub-goal is learned under its own key.
            Assert.That(procedures.Find("Steam", "ir a la biblioteca"), Is.Not.Null);
            Assert.That(procedures.Find("Bloc de notas", "escribir hola"), Is.Not.Null);
        });
    }

    [Test]
    public async Task AChainStopsAtTheFirstSubgoalThatFailsAndSaysWhichOnesWereReached()
    {
        var harness = new Harness
        {
            Screen = _ => Window("Steam", "steamwebhelper", 12, true, [Control(0, "Button", "Biblioteca"), Control(1, "Button", "Tienda")]),
            Mind = request => request.Subgoal == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Biblioteca" })
                : Step("none", new JsonObject()),
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ve a la biblioteca y luego a la tienda de puntos",
            ["steps"] = new JsonArray
            {
                new JsonObject { ["goal"] = "ir a la biblioteca", ["application"] = "Steam", ["successCheck"] = "stepDone:input.visible.click:biblioteca" },
                new JsonObject { ["goal"] = "ir a la tienda de puntos", ["application"] = "Steam", ["successCheck"] = "text:puntos" },
                new JsonObject { ["goal"] = "canjear", ["application"] = "Steam", ["successCheck"] = null },
            },
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("ve a la biblioteca y luego a la tienda de puntos", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        JsonArray subgoals = observed["subgoals"]!.AsArray();
        Assert.Multiple(() =>
        {
            Assert.That(result.Response!.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_no_step_visible"));
            Assert.That(subgoals.Select(item => (bool?)item!["reached"]), Is.EqualTo(new bool?[] { true, false, false }));
            Assert.That((int?)subgoals[2]!["stepCount"], Is.EqualTo(0));
            // Same application: the adopted window is kept for the next sub-goal.
            Assert.That((int?)harness.Looks[^1]["processId"], Is.EqualTo(12));
        });
    }

    [Test]
    public async Task WithoutStepsTheMissionIsOneGoalAsBeforeAndTheDecisionSaysSoToTheMind()
    {
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ => Window("Steam", "steamwebhelper", 12, true,
                [Control(0, "Button", "Biblioteca", clicked ? "selected" : ""), Control(1, "Button", "Tienda")]),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Biblioteca" }),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["selected"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "ir a la biblioteca", ["application"] = "Steam", ["successCheck"] = "control:Biblioteca:selected" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("ve a la biblioteca de Steam", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(observed["subgoals"], Is.Null);
            Assert.That(observed["steps"]![0]!["subgoal"], Is.Null);
            Assert.That((harness.Requests[0].Subgoal, harness.Requests[0].SubgoalCount, harness.Requests[0].BudgetLeft), Is.EqualTo((0, 1, 12)));
            Assert.That(harness.Delays, Is.EqualTo(new[] { ComputerUseMission.Settle }));
        });
    }

    // The OCR text costs about a second per look: the first look of a goal takes it; after that only a check that
    // reads written text (or a goal whose target the controls do not name) asks for it again.
    [TestCase("control:Biblioteca:selected", false)]
    [TestCase("text:juegos y software", true)]
    public async Task TheTextIsReadOnlyWhenTheCheckOrTheGoalNeedsIt(string check, bool secondLookReadsText)
    {
        bool clicked = false;
        var harness = new Harness
        {
            Screen = look => Window("Steam", "steamwebhelper", 12, true,
                [Control(0, "Button", "Biblioteca", clicked ? "selected" : ""), Control(1, "Button", "Tienda")],
                AskedText(look) && clicked ? ["Juegos y Software"] : []),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Biblioteca" }),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["selected"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "ir a la biblioteca", ["application"] = "Steam", ["successCheck"] = check };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("ve a la biblioteca", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Response!.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(harness.Looks.Select(AskedText), Is.EqualTo(new[] { true, secondLookReadsText }));
        });
    }

    [Test]
    public async Task ACheckHeldByTheReceiptsEndsWithOneLookWithoutText()
    {
        var harness = new Harness
        {
            Screen = _ => Window("Steam", "steamwebhelper", 12, true, [Control(0, "Button", "Biblioteca"), Control(1, "Button", "Tienda")]),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Biblioteca" }),
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a la biblioteca",
            ["application"] = "Steam",
            ["successCheck"] = "stepDone:input.visible.click:biblioteca",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("ve a la biblioteca", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((string?)Observed(result)["satisfiedBy"], Is.EqualTo("stepDone:input.visible.click:biblioteca"));
            Assert.That(harness.Looks.Select(AskedText), Is.EqualTo(new[] { true, false }));
        });
    }

    [TestCase("ir a la biblioteca", "Steam", "control:Biblioteca", false, false)]
    [TestCase("ir a la biblioteca", "Steam", "text:Biblioteca", false, true)]
    [TestCase("ir a la biblioteca", "Steam", "process:steam&page:biblioteca", false, true)]
    [TestCase("abrir los ajustes avanzados", "Steam", "control:Biblioteca", false, true)]
    [TestCase("abrir steam", "Steam", "control:Biblioteca", false, true)]
    [TestCase("ir a la biblioteca", "Steam", "control:Biblioteca", true, true)]
    public void TheNeedForTextIsDecidedOverTheLastViewOfTheSubgoal(
        string goal, string application, string check, bool onlyOneControl, bool expected)
    {
        JsonArray controls = onlyOneControl
            ? [Control(0, "Document", "Steam")]
            : [Control(0, "Button", "Biblioteca"), Control(1, "Button", "Tienda")];
        JsonObject view = Window("Steam", "steamwebhelper", 12, true, controls);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.NeedsText(goal, application, check, view), Is.EqualTo(expected));
            Assert.That(ComputerUseMission.NeedsText(goal, application, check, previousView: null), Is.True,
                "the first look of a sub-goal always reads the text");
        });
    }

    [Test]
    public async Task TheSameActFromAScreenItAlreadyLeftIsNotTakenAgain()
    {
        bool menuOpen = false;
        int requests = 0;
        var harness = new Harness
        {
            Screen = _ => menuOpen
                ? Window("App", "app", 5, true, [Control(0, "Button", "Menú"), Control(1, "MenuItem", "Perfil"), Control(2, "MenuItem", "Salir")])
                : Window("App", "app", 5, true, [Control(0, "Button", "Menú"), Control(1, "Button", "Inicio")]),
            Mind = _ => ++requests <= 3
                ? Step("input.visible.click", new JsonObject { ["label"] = "Menú" })
                : Step("none", new JsonObject()),
        };
        harness.Receipt = (_, _) =>
        {
            menuOpen = !menuOpen;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "ver el perfil", ["application"] = "App", ["successCheck"] = "control:Perfil:selected" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("mira mi perfil", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        JsonArray steps = observed["steps"]!.AsArray();
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Has.Count.EqualTo(2), "the third «Menú» from the starting screen is not executed");
            Assert.That(steps, Has.Count.EqualTo(3));
            Assert.That((bool?)steps[2]!["ok"], Is.False);
            Assert.That((string?)steps[2]!["error"], Is.EqualTo("computer_use_no_progress"));
            Assert.That((string?)harness.Requests[3].History[^1]!["error"], Is.EqualTo("computer_use_no_progress"));
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_no_step_visible"));
        });
    }

    // Measured on Steam: the editor in front before app.open is not the application; the page reached is measured
    // against the application's own first look, after a bounded wait that ends as soon as its window shows.
    [Test]
    public async Task AfterOpeningTheLoopWaitsForTheWindowAndMeasuresThePageAgainstIt()
    {
        string[] editor = ["Notas de la reunión", "Lunes", "Comprar pan", "Llamar a Ana", "Revisar el informe", "Fin"];
        string[] store = ["TIENDA", "BIBLIOTECA COMUNIDAD", "Explorar", "Buscar en la tienda", "REBAJAS DE OTOÑO", "Lista de deseados", "Novedades"];
        string[] menu = [.. store, "Inicio", "Colecciones", "Descargas"];
        int stage = 0;
        int pollsAfterOpening = 0;
        var harness = new Harness
        {
            Screen = _ =>
            {
                if (stage == 0 || (stage == 1 && pollsAfterOpening++ == 0))
                {
                    return Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Document", "Texto")], editor);
                }

                return Window("Steam", "steamwebhelper", 12, true, [Control(0, "Document", "Steam")], stage == 1 ? store : menu);
            },
            Mind = request => request.View["window"]!["title"]!.GetValue<string>() switch
            {
                "Notas - Bloc de notas" => Step("app.open", new JsonObject { ["appId"] = "Steam" }),
                _ when stage == 1 => Step("input.visible.click", new JsonObject { ["label"] = "Biblioteca" }),
                _ => Step("none", new JsonObject()),
            },
        };
        harness.Receipt = (operation, _) =>
        {
            stage += 1;
            return operation == "app.open"
                ? new JsonObject { ["processId"] = 12, ["name"] = "Steam" }
                : new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "ir a la biblioteca", ["application"] = "Steam", ["successCheck"] = "page:biblioteca" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("ve a la biblioteca de Steam", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            // Against the editor every line of the menu is new; against Steam's own store most are kept.
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_no_step_visible"));
            Assert.That(harness.Delays, Is.All.EqualTo(ComputerUseMission.Settle));
            Assert.That(harness.Delays, Has.Count.EqualTo(2), "one poll while the window was not there, one settle after the click");
            Assert.That(AskedText(harness.Looks[1]), Is.False, "the wait for the window reads no text");
        });
    }

    // Safety review 2026-10-07: a key or a text goes to the window the step was decided on, named in its arguments so
    // the provider brings it to the front or sends nothing (also after a «sí», with BAXY's own window in front).
    // Live v5/v6 (2026-10-07): Excel and Word opened on their start page, «Libro en blanco» offered and focused.
    private static JsonObject StartPage(bool created)
    {
        JsonObject view = created
            ? Window("Libro1 - Excel", "EXCEL", 40, true,
                [Control(0, "TabItem", "Inicio", "selected"), Control(1, "TabItem", "Insertar")])
            : Window("Excel", "EXCEL", 40, true,
                [Control(0, "ListItem", "Inicio", "selected"), Control(1, "ListItem", "Libro en blanco", "selected focused"),
                 Control(2, "ListItem", "Presupuesto 2026")]);
        view["window"]!["hwnd"] = created ? 5150 : 5140;
        return view;
    }

    [Test]
    public async Task ABlankDocumentCreatedFromAStartPageIsWaitedForUntilItsWindowReplacesThePage()
    {
        bool entered = false;
        int looksAfterEnter = 0;
        var harness = new Harness
        {
            // The new document's window takes two looks to replace the start page.
            Screen = _ => StartPage(created: entered && ++looksAfterEnter > 2),
        };
        harness.Mind = request => harness.Acts.Count == 0
            ? new MindComputerUseStep("input.key.press", new JsonObject { ["key"] = "enter" }, "creo el elemento en blanco", "expects_title_change")
            : Step("input.visible.click", new JsonObject { ["label"] = "Insertar", ["index"] = 1 });
        harness.Receipt = (operation, _) =>
        {
            entered |= operation == "input.key.press";
            return operation == "input.visible.click"
                ? new JsonObject { ["selected"] = true, ["surfaceChanged"] = true }
                : new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a la pestaña insertar",
            ["application"] = "Excel",
            ["successCheck"] = "stepDone:input.visible.click:insertar",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Excel andá a la pestaña Insertar", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "input.key.press", "input.visible.click" }));
            // The Enter goes to the start page it was decided on; the mind decides the next step on the new window.
            Assert.That((long?)harness.Acts[0].Arguments["window"], Is.EqualTo(5140L));
            Assert.That((string?)harness.Requests[1].View["window"]!["title"], Is.EqualTo("Libro1 - Excel"));
            Assert.That(harness.Requests, Has.Count.EqualTo(2));
        });
    }

    [Test]
    public async Task AStartPageWithNoDocumentOpenIsSaidAsTheCauseNotAsAMissingControl()
    {
        var harness = new Harness
        {
            Screen = _ => StartPage(created: false),
            Mind = _ => new MindComputerUseStep("none", new JsonObject(), "la aplicación está en su página de inicio", "no_document_open"),
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a la pestaña diseno",
            ["application"] = "Excel",
            ["successCheck"] = "control:diseno:selected|title:diseno",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Excel abrí presupuesto.xlsx y andá a la pestaña Diseño", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(result.Response!.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_no_document_open"));
            Assert.That(harness.Acts, Is.Empty);
        });
    }

    [Test]
    public async Task KeysAndTextNameTheWindowOfTheViewTheyWereDecidedOn()
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Window("Sin título - Bloc de notas", "Notepad", 31, true, [Control(0, "Document", "Editor de texto", "focused", "")]);
                view["window"]!["hwnd"] = 4660;
                return view;
            },
        };
        harness.Mind = request => harness.Acts.Count == 0
            ? Step("input.text.type", new JsonObject { ["text"] = "hola" })
            : Step("input.key.press", new JsonObject { ["key"] = "enter" });
        var arguments = new JsonObject
        {
            ["goal"] = "escribir hola",
            ["application"] = "Bloc de notas",
            ["successCheck"] = "stepDone:input.key.press:enter",
        };

        await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el bloc de notas escribí hola", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "input.text.type", "input.key.press" }));
            Assert.That(harness.Acts.Select(act => (long?)act.Arguments["window"]), Is.All.EqualTo(4660L));
        });
    }

    [Test]
    public async Task NothingIsTypedInAWindowThatIsNotTheNamedApplication()
    {
        var harness = new Harness
        {
            // The application's window was not found: the view fell back to what is in front, the person's editor.
            Screen = _ =>
            {
                JsonObject view = Window("SteamLocalAdapter.cs - BAXY - Visual Studio Code", "Code", 77, false, [Control(0, "Document", "(document)", "focused")]);
                view["window"]!["hwnd"] = 999;
                return view;
            },
            Mind = _ => Step("input.text.type", new JsonObject { ["text"] = "hola" }),
        };
        var arguments = new JsonObject { ["goal"] = "escribir hola", ["application"] = "Steam" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Steam escribí hola", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Is.Empty);
            Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_window_not_application"));
        });
    }

    // A browser on a site (the address field holds a web address), with or without its page exposed: the frame's
    // controls, and the page a document the size of the window's body (synthetic, shaped like Opera on 2026-10-07).
    private static JsonObject Browser(bool pageShown)
    {
        string page = pageShown
            ? """
              {"i": 3, "kind": "Document", "name": "Ciudad - Wikipedia", "state": "readonly", "rect": {"x": 53, "y": 136, "w": 1519, "h": 825}},
              {"i": 4, "kind": "Edit", "name": "Buscar en Wikipedia", "value": "", "rect": {"x": 435, "y": 157, "w": 506, "h": 41}}
              """
            : """{"i": 3, "kind": "Document", "name": "Cargando…", "rect": {"x": 106, "y": 13, "w": 22, "h": 22}}""";
        return (JsonObject)JsonNode.Parse($$$"""
            {
              "window": {"title": "es.wikipedia.org/wiki/Ciudad - Navegador", "process": "browser", "processId": 40, "requested": true,
                         "rect": {"x": 0, "y": 0, "w": 1575, "h": 965}},
              "controls": [
                {"i": 0, "kind": "Button", "name": "Buscar pestañas", "rect": {"x": 1426, "y": 5, "w": 37, "h": 37}},
                {"i": 1, "kind": "Edit", "name": "Campo de dirección", "value": "https://es.wikipedia.org/wiki/Ciudad", "rect": {"x": 211, "y": 54, "w": 969, "h": 37}},
                {"i": 2, "kind": "Button", "name": "Nueva pestaña", "rect": {"x": 344, "y": 13, "w": 22, "h": 22}},
                {{{page}}}
              ]
            }
            """)!;
    }

    [Test]
    public async Task ALookAtABrowserWaitsBoundedUntilItsPageIsExposedAndTheMindGetsTheRectangles()
    {
        var arguments = new JsonObject
        {
            ["goal"] = "buscar Ciudad",
            ["application"] = "Opera",
            ["successCheck"] = "stepDone:input.visible.click:buscar en wikipedia",
        };
        int looks = 0;
        var loading = new Harness
        {
            Screen = _ => Browser(pageShown: ++looks > 2),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Buscar en Wikipedia", ["index"] = 4 }),
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            loading.Context(_root), Execution("buscá Ciudad", arguments), arguments, CancellationToken.None);

        // A page that never comes is waited for a bounded number of looks, once for that title; then the mind decides
        // on what is there.
        var never = new Harness
        {
            Screen = _ => Browser(pageShown: false),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Campo de dirección", ["index"] = 1 }),
            Receipt = static (_, _) => new JsonObject { ["surfaceChanged"] = true },
        };
        var twice = new JsonObject
        {
            ["goal"] = "buscar Ciudad",
            ["application"] = "Opera",
            ["successCheck"] = "text:nunca",
            ["budgetSteps"] = 2,
        };
        await ComputerUseMission.RunAsync(never.Context(_root), Execution("buscá Ciudad", twice), twice, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.True);
            Assert.That(loading.Delays.Count(delay => delay == ComputerUseMission.PageLookInterval), Is.EqualTo(2));
            JsonObject seen = loading.Requests[0].View;
            Assert.That(seen["controls"]!.AsArray().Any(node => (string?)node!["name"] == "Buscar en Wikipedia"), Is.True);
            Assert.That((int?)seen["window"]!["rect"]!["w"], Is.EqualTo(1575));
            Assert.That((int?)seen["controls"]![3]!["rect"]!["h"], Is.EqualTo(825));
            Assert.That(never.Requests, Has.Count.EqualTo(2));
            Assert.That(never.Delays.Count(delay => delay == ComputerUseMission.PageLookInterval), Is.EqualTo(ComputerUseMission.PageLooks));
            Assert.That(ComputerUseMission.PageNotExposed(Browser(pageShown: true)), Is.False);
        });
    }

    // A learned procedure stored for (application, goal), as an earlier run left it.
    private ComputerUseProcedures Learned(string application, string goal, params JsonObject[] steps)
    {
        string path = Path.Combine(_root, "procedures.v1.json");
        var document = new JsonObject
        {
            ["version"] = 1,
            ["procedures"] = new JsonObject
            {
                [ComputerUseProcedures.Key(application, goal)] = new JsonObject
                {
                    ["application"] = application,
                    ["goal"] = goal,
                    ["steps"] = new JsonArray([.. steps.Select(step => (JsonNode?)step)]),
                    ["successCheck"] = null,
                    ["runs"] = 3,
                    ["replays"] = 0,
                },
            },
        };
        File.WriteAllText(path, document.ToJsonString());
        return new ComputerUseProcedures(path);
    }

    private static JsonObject LearnedStep(string operation, JsonObject arguments) =>
        new() { ["operation"] = operation, ["arguments"] = arguments, ["expect"] = "surfaceChanged" };

    // Measured live 2026-10-07 (v2-s13): the application already in front, its learned app.open changed nothing and the
    // replayed click on a label of an earlier screen failed; the mission ended «la pantalla dejó de cambiar» with no
    // decision of the routine or the model. A deviated replay hands the mission over on a fresh count, and the stale
    // procedure is forgotten.
    [Test]
    public async Task AFailedLearnedStepHandsTheMissionToTheRoutineAndTheProcedureIsForgotten()
    {
        bool arrived = false;
        var harness = new Harness
        {
            Screen = _ => arrived
                ? Window("Canal - Chat", "chat", 7, true, [Control(0, "Button", "Buscar"), Control(1, "TreeItem", "Canal", "selected")])
                : Window("Inicio - Chat", "chat", 7, true, [Control(0, "Button", "Buscar"), Control(1, "ListItem", "Tarjeta antigua")]),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Buscar" }),
        };
        harness.Receipt = (operation, arguments) =>
        {
            if (operation == "app.open")
            {
                return new JsonObject { ["processId"] = 7, ["alreadyRunning"] = true };
            }

            if ((string?)arguments["label"] == "Tarjeta antigua")
            {
                return null!;
            }

            arrived = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        ComputerUseProcedures procedures = Learned("Chat", "ir a canal",
            LearnedStep("app.open", new JsonObject { ["appId"] = "Chat" }),
            LearnedStep("input.visible.click", new JsonObject { ["label"] = "Tarjeta antigua" }));
        var arguments = new JsonObject { ["goal"] = "ir a canal", ["application"] = "Chat", ["successCheck"] = "control:canal:selected" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root, procedures), Execution("en Chat andá al canal", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        JsonArray steps = observed["steps"]!.AsArray();
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True, (string?)observed["stoppedBy"]);
            Assert.That(harness.Acts.Select(act => act.Operation),
                Is.EqualTo(new[] { "app.open", "input.visible.click", "input.visible.click" }));
            Assert.That(steps.Select(step => (string?)step!["source"]), Is.EqualTo(new[] { "procedure", "procedure", "model" }));
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "the routine and the model decide once the replay deviated");
            Assert.That((bool?)harness.Requests[0].History[^1]!["ok"], Is.False);
            Assert.That(procedures.Find("Chat", "ir a canal"), Is.Null, "a replay that deviated is not kept");
            Assert.That(new ComputerUseProcedures(Path.Combine(_root, "procedures.v1.json")).Find("Chat", "ir a canal"), Is.Null);
        });
    }

    [Test]
    public async Task AProcedureWhoseReplayDidNotReachTheGoalIsForgottenOneThatNeverRanIsKept()
    {
        var failing = new Harness
        {
            Screen = _ => Window("Inicio - Chat", "chat", 7, true, [Control(0, "Button", "Ajustes"), Control(1, "Button", "Ayuda")]),
            Mind = _ => Step("none", new JsonObject()),
        };
        ComputerUseProcedures procedures = Learned("Chat", "ir a perfil",
            LearnedStep("input.visible.click", new JsonObject { ["label"] = "Ajustes" }));
        var arguments = new JsonObject { ["goal"] = "ir a perfil", ["application"] = "Chat", ["successCheck"] = "control:perfil:selected" };

        ComputerUseMission.Result failed = await ComputerUseMission.RunAsync(
            failing.Context(_root, procedures), Execution("en Chat andá al perfil", arguments), arguments, CancellationToken.None);

        var blind = new Harness { Screen = _ => null };
        ComputerUseProcedures kept = Learned("Chat", "ir a perfil",
            LearnedStep("input.visible.click", new JsonObject { ["label"] = "Ajustes" }));
        ComputerUseMission.Result unseen = await ComputerUseMission.RunAsync(
            blind.Context(_root, kept), Execution("en Chat andá al perfil", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(failed)["reached"], Is.False);
            Assert.That(failing.Acts, Has.Count.EqualTo(1), "the learned click was replayed");
            Assert.That(procedures.Find("Chat", "ir a perfil"), Is.Null);
            Assert.That((string?)Observed(unseen)["stoppedBy"], Is.EqualTo("computer_use_view_unavailable"));
            Assert.That(kept.Find("Chat", "ir a perfil"), Is.Not.Null, "a procedure that never ran is no evidence against it");
        });
    }
}
