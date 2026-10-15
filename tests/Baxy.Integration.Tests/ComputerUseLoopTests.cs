using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// The computer-use loop end to end over a scripted screen and a scripted
/// mind (documentacion/computer-use/CONTRATO_VISTA_ACCION.md §4): chained
/// sub-goals, the OCR text asked only when needed, the short settle and the
/// bounded wait after app.open, the no-progress guard and the page: baseline.
/// </summary>
[TestFixture]
public sealed partial class ComputerUseLoopTests
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

        // The mission's clock (ms): a receipt that stands for a wait for the person's pause advances it.
        internal long Now { get; set; }

        internal ComputerUseMission.Context Context(
            string root, ComputerUseLabelTranslations? translations = null,
            ComputerUseTypedLedger? typed = null, Baxy.Providers.Windows.External.IMissionFrontSignal? front = null) => new()
            {
                Front = front,
                LabelTranslations = translations,
                TypedInSession = typed,
                Execute = (prepared, _, _) =>
                {
                    var arguments = (JsonObject)JsonNode.Parse(prepared.Arguments.GetRawText())!;
                    if (prepared.OperationName == "input.visible.controls")
                    {
                        Looks.Add(arguments);
                        return Task.FromResult(Respond(prepared, AsTheProviderReads(arguments, Screen(arguments))));
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
                NowMs = () => Now,
                Delay = (delay, _) =>
                {
                    Delays.Add(delay);
                    return Task.CompletedTask;
                },
            };

        // Ronda 26: as the provider answers a look that asked only who is in front when the application named has no
        // window (identityIfAbsent): that window's identity, no controls and no text, marked «identityOnly». The App
        // reads only that mark (ComputerUseViewIdentityTests pins the provider's side of it).
        private static JsonObject? AsTheProviderReads(JsonObject look, JsonObject? view)
        {
            // A read that fails (no window in its answer) fails as it does.
            if (view?["window"] is null || (bool?)look["identityIfAbsent"] != true || (bool?)view["window"]!["requested"] == true)
            {
                return view;
            }

            var identity = new JsonObject { ["identityOnly"] = true, ["window"] = view["window"]?.DeepClone(), ["controls"] = new JsonArray() };
            // r29: the provider's word that the application asked for is a live process raised above BAXY.
            if ((bool?)view["applicationElevated"] == true && (int?)look["processId"] is > 0)
            {
                identity["applicationElevated"] = true;
            }

            return identity;
        }

        private static OperationResponse Respond(PreparedOperation prepared, JsonObject? result)
        {
            // A receipt «failWith» answers the act as failed with that error (a label not found); with «effectUncertain»
            // it failed after pressing (its post-read did not hold).
            string? failWith = (string?)result?["failWith"];
            bool ok = result is not null && failWith is null;
            using JsonDocument document = JsonDocument.Parse((ok ? result! : new JsonObject()).ToJsonString());
            return new OperationResponse(
                ProtocolTypes.OperationResponse, prepared.InvocationId, prepared.MissionId, prepared.InvocationId,
                ok ? OperationStatuses.Completed : OperationStatuses.Failed, "{}", ok, false,
                document.RootElement.Clone(), ok ? null : failWith ?? "view_unavailable",
                EffectMayHaveOccurred: !ok && (bool?)result?["effectUncertain"] == true);
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
    public async Task AFileOpenedWithTheApplicationIsTheWindowTheMissionGoesOnIn()
    {
        // cu-v3-abrir-archivo (r9 v3-15, v3-17): the gallery of Fotos in front of the mission, no Open dialog in it.
        // The mind's file.open hands the file to Fotos by the shell; the next look is the window it opened (its process),
        // titled by the file, and that title proves the sub-goal.
        bool opened = false;
        var harness = new Harness
        {
            Screen = look => opened && (int?)look["processId"] == 41
                ? Window("paisaje.jpg", "Photos", 41, true, [Control(0, "Button", "Editar")], "JPG", "1920 x 1080")
                : Window("Fotos", "Photos", 40, true, [Control(0, "ListItem", "Galería", "selected"), Control(1, "Edit", "Buscar en la galería")]),
            Mind = _ => Step("file.open", new JsonObject
            {
                ["folder"] = "documents",
                ["name"] = "baxy-prueba-v3\\paisaje.jpg",
                ["application"] = "Fotos",
            }),
        };
        harness.Receipt = (operation, _) =>
        {
            opened |= operation == "file.open";
            return new JsonObject { ["processId"] = 41, ["windowTitle"] = "paisaje.jpg", ["alreadyRunning"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "abrir el archivo D:\\Perfil\\Documentos\\baxy-prueba-v3\\paisaje.jpg",
            ["application"] = "Fotos",
            ["successCheck"] = "title:paisaje",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abre la foto paisaje.jpg en fotos", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "file.open" }), "no click, key or text in the gallery");
            Assert.That((string?)harness.Acts[0].Arguments["application"], Is.EqualTo("Fotos"));
            Assert.That((int?)harness.Looks[^1]["processId"], Is.EqualTo(41));
            Assert.That((string?)observed["steps"]![0]!["windowTitle"], Is.EqualTo("paisaje.jpg"));
        });
    }

    [Test]
    public async Task TheApplicationsWindowOnAnotherFileIsNoFileOpenedUntilItsFileOpenIsDone()
    {
        // Review of cu-v3-abrir-archivo, finding 2: «abrí notas.txt en el bloc de notas» with the Bloc de notas already
        // on «lista.txt - Bloc de notas»: its title holds «notas» and, before, the first look reached the mission with no
        // act. The check the mind plans asks for the sub-goal's own file.open; the window titled by the file after it is
        // the arrival.
        bool opened = false;
        var harness = new Harness
        {
            Screen = _ => opened
                ? Window("notas.txt - Bloc de notas", "Notepad", 50, true, [Control(0, "Document", "Editor de texto")])
                : Window("lista.txt - Bloc de notas", "Notepad", 50, true, [Control(0, "Document", "Editor de texto")]),
            Mind = _ => Step("file.open", new JsonObject
            {
                ["folder"] = "documents",
                ["name"] = "baxy-prueba-v3\\notas.txt",
                ["application"] = "Bloc de notas",
            }),
        };
        harness.Receipt = (operation, _) =>
        {
            opened |= operation == "file.open";
            return new JsonObject { ["processId"] = 50, ["windowTitle"] = "notas.txt - Bloc de notas", ["name"] = "notas.txt" };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "abrir el archivo D:\\Perfil\\Documentos\\baxy-prueba-v3\\notas.txt",
            ["application"] = "Bloc de notas",
            ["successCheck"] = "title:notas&stepDone:file.open",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abri notas.txt en el bloc de notas", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        var before = Window("lista.txt - Bloc de notas", "Notepad", 50, true, []);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:notas&stepDone:file.open", before, [], out _), Is.False,
                "the application's window on another file, nothing opened");
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "file.open" }), "the file was opened");
        });
    }

    [Test]
    public async Task AFileNotOpenedStopsWithItsCauseForTheFinal()
    {
        // Review of cu-v3-abrir-archivo, finding 4: the mind's stop «file_not_opened:<cause>» reaches the observation
        // as its own stop with the cause (never «no vi un control con el que seguir»).
        var harness = new Harness
        {
            Screen = _ => Window("Fotos", "Photos", 40, true, [Control(0, "ListItem", "Galería", "selected")]),
            Mind = _ => new MindComputerUseStep("none", new JsonObject(), "hay más de un archivo «dup.png»",
                "file_not_opened:file_ambiguous"),
        };
        var arguments = new JsonObject
        {
            ["goal"] = "abrir el archivo dup.png",
            ["application"] = "Fotos",
            ["successCheck"] = "title:dup&stepDone:file.open",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abri dup.png en fotos", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_file_not_opened"));
            Assert.That((string?)observed["fileNotOpened"], Is.EqualTo("file_ambiguous"));
            Assert.That(harness.Acts, Is.Empty, "nothing done in the gallery");
        });
    }

    [Test]
    public async Task AChainedMissionRunsItsSubgoalsInOrderEachWithItsOwnApplicationAndCheck()
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
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abre la biblioteca y escribe hola", arguments), arguments, CancellationToken.None);

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

            // Estabilización, fase 3: no sequence is learned nor replayed; nothing of the mission speaks of one.
            Assert.That(observed.ToJsonString(), Does.Not.Contain("procedure"));
            Assert.That(Directory.GetFiles(_root, "procedures*", SearchOption.AllDirectories), Is.Empty);
        });
    }

    // r8 (measured live: 11 of 27 chained transitions looked again at once, ~600 ms each): the look that proved a
    // sub-goal reached is the next sub-goal's first look when nothing was done in between on the same application; the
    // next sub-goal's notes start from that view as read, not from the first sub-goal's.
    [Test]
    public async Task TheLookThatReachedASubgoalIsTheNextSubgoalsFirstLookOnTheSameApplication()
    {
        string selected = string.Empty;
        var harness = new Harness
        {
            Screen = _ => Window("Steam", "steamwebhelper", 12, true,
                [Control(0, "Button", "Biblioteca", selected == "Biblioteca" ? "selected" : ""),
                 Control(1, "Button", "Tienda", selected == "Tienda" ? "selected" : "")]),
            Mind = request => request.Subgoal == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Biblioteca" })
                : Step("input.visible.click", new JsonObject { ["label"] = "Tienda" }),
        };
        harness.Receipt = (_, arguments) =>
        {
            selected = (string?)arguments["label"] ?? string.Empty;
            return new JsonObject { ["selected"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ve a la biblioteca y después a la tienda",
            ["steps"] = new JsonArray
            {
                new JsonObject { ["goal"] = "ir a la biblioteca", ["application"] = "Steam", ["successCheck"] = "control:Biblioteca:selected" },
                new JsonObject { ["goal"] = "ir a la tienda", ["application"] = "Steam", ["successCheck"] = "control:Tienda:selected" },
            },
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("ve a la biblioteca y después a la tienda", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(observed["subgoals"]!.AsArray().Select(item => (bool?)item!["reached"]), Is.EqualTo(new bool?[] { true, true }));
            // Look, click, look (reached and reused), click, look: three looks, not four.
            Assert.That(harness.Looks, Has.Count.EqualTo(3));
            Assert.That(harness.Acts.Select(act => (string?)act.Arguments["label"]), Is.EqualTo(new[] { "Biblioteca", "Tienda" }));
            // The second sub-goal's mind saw the reused view without the first sub-goal's notes.
            Assert.That(harness.Requests[1].History, Is.Empty);
            Assert.That(harness.Requests[1].View["textBeforeClick"], Is.Null);
        });
    }

    [Test]
    public async Task TheNextSubgoalLooksAgainWhenItsApplicationIsAnother()
    {
        bool clicked = false;
        bool typed = false;
        var harness = new Harness
        {
            Screen = look => (string?)look["application"] switch
            {
                "Steam" => Window("Steam", "steamwebhelper", 12, true,
                    [Control(0, "Button", "Biblioteca", clicked ? "selected" : ""), Control(1, "Button", "Tienda")]),
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
            clicked |= operation == "input.visible.click";
            typed |= operation == "input.text.type";
            return new JsonObject { ["selected"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "abre la biblioteca de Steam y escribe hola en el Bloc de notas",
            ["steps"] = new JsonArray
            {
                new JsonObject { ["goal"] = "ir a la biblioteca", ["application"] = "Steam", ["successCheck"] = "control:Biblioteca:selected" },
                new JsonObject { ["goal"] = "escribir hola", ["application"] = "Bloc de notas", ["successCheck"] = "value:Texto=hola" },
            },
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abre la biblioteca y escribe hola", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.True);
            Assert.That(harness.Looks.Select(look => (string?)look["application"]),
                Is.EqualTo(new[] { "Steam", "Steam", "Bloc de notas", "Bloc de notas" }));
        });
    }

    // r4a M2 (g1, a game launcher drawn by CEF), kept by revisión D (H4: the person may bring their window up): ctrl_k and ctrl_f focused its search box, but both looks were read with
    // the window behind the person's, where that focus does not show; two identical looks stopped the mission as «the
    // screen stopped changing» before «Cuphead» was typed. A look taken behind after a key does not count.
    [Test]
    public async Task KeysLookedAtWithTheWindowBehindDoNotCountAsActsThatLeftTheScreenUnchanged()
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Window("Lanzador", "lanzador", 12, true, [Control(0, "Pane", "Lanzador")], "Tienda", "Biblioteca");
                view["window"]!["hwnd"] = 4660;
                view["window"]!["foreground"] = false;
                return view;
            },
        };
        harness.Mind = request => request.History.Count switch
        {
            0 => Step("input.key.press", new JsonObject { ["key"] = "ctrl_k" }),
            1 => Step("input.key.press", new JsonObject { ["key"] = "ctrl_f" }),
            _ => Step("input.text.type", new JsonObject { ["text"] = "Cuphead" }),
        };
        harness.Receipt = static (_, _) => new JsonObject { ["method"] = "keyboard" };
        var arguments = new JsonObject
        {
            ["goal"] = "buscar Cuphead",
            ["application"] = "Lanzador",
            ["successCheck"] = "stepDone:input.text.type:=cuphead",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("buscá Cuphead en el lanzador", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Select(act => act.Operation),
                Is.EqualTo(new[] { "input.key.press", "input.key.press", "input.text.type" }));
            Assert.That((string?)observed["stoppedBy"], Is.Not.EqualTo("computer_use_surface_unchanged"));
        });
    }

    // r4a M2 (g1, a game launcher drawn by CEF): ctrl_k focused its search box, a focus that shows only while the window
    // is active. Estabilización D: the key goes with the mission's window in front, which it keeps, so the look after it
    // is read active and shows the box; «Cuphead» is typed next (before, a look behind did not count instead).
    [Test]
    public async Task AKeyWhoseEffectShowsOnlyInFrontIsReadFromTheLookAfterIt()
    {
        var harness = new Harness();
        harness.Screen = _ =>
        {
            JsonObject view = harness.Acts.Count switch
            {
                0 => Window("Lanzador", "lanzador", 12, true, [Control(0, "Pane", "Lanzador")], "Tienda", "Biblioteca"),
                1 => Window("Lanzador", "lanzador", 12, true, [Control(0, "Pane", "Lanzador"), Control(1, "Edit", "Buscar juegos", "focused")], "Tienda", "Biblioteca"),
                _ => Window("Lanzador", "lanzador", 12, true, [Control(0, "Pane", "Lanzador"), Control(1, "Edit", "Buscar juegos", "focused", "Cuphead")], "Tienda", "Biblioteca"),
            };
            view["window"]!["hwnd"] = 4660;
            view["window"]!["foreground"] = true;
            return view;
        };
        harness.Mind = request => request.History.Count switch
        {
            0 => Step("input.key.press", new JsonObject { ["key"] = "ctrl_k" }),
            1 => Step("input.text.type", new JsonObject { ["text"] = "Cuphead" }),
            _ => null,
        };
        harness.Receipt = static (_, _) => new JsonObject { ["method"] = "keyboard" };
        var arguments = new JsonObject
        {
            ["goal"] = "buscar Cuphead",
            ["application"] = "Lanzador",
            ["successCheck"] = "stepDone:input.text.type:=cuphead",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("buscá Cuphead en el lanzador", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Select(act => act.Operation),
                Is.EqualTo(new[] { "input.key.press", "input.text.type" }));
            Assert.That((string?)observed["stoppedBy"], Is.Not.EqualTo("computer_use_surface_unchanged"));
        });
    }

    // Ronda 20b, revisión 2 (bloqueante 1): the check of the whole form a sub-goal belongs to (formCheck, from the plan)
    // reaches the mind with that sub-goal's step request, so it switches a lock off before the first field and evaluates
    // the form again before accepting it. Contracase: a sub-goal of no form sends none.
    [TestCase("value:ancho=500&value:alto=500", "value:ancho=500&value:alto=500")]
    [TestCase(null, null)]
    public async Task TheFormCheckOfASubgoalReachesTheMind(string? formCheck, string? expected)
    {
        var harness = new Harness();
        harness.Screen = _ => Window("Sin título - Paint", "mspaint", 41, true, [
            Control(0, "Edit", "Horizontal", "focused"), Control(1, "Edit", "Vertical"), Control(2, "Button", "Aceptar")]);
        harness.Mind = _ => new MindComputerUseStep("none", new JsonObject(), "no veo cómo seguir", "no_step_visible");
        var first = new JsonObject
        {
            ["goal"] = "poner ancho en 500",
            ["application"] = "Paint",
            ["successCheck"] = "value:ancho=500",
        };
        if (formCheck is not null)
        {
            first["formCheck"] = formCheck;
        }

        var arguments = new JsonObject
        {
            ["goal"] = "poner ancho en 500; luego hacer clic en aceptar",
            ["steps"] = new JsonArray
            {
                first,
                new JsonObject { ["goal"] = "hacer clic en aceptar", ["application"] = "Paint", ["successCheck"] = "stepDone:input.visible.click:aceptar" },
            },
        };

        await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en paint cambiá el tamaño a 500 por 500", arguments), arguments,
            CancellationToken.None);

        Assert.That(harness.Requests, Is.Not.Empty);
        Assert.That(harness.Requests[0].FormCheck, Is.EqualTo(expected));
    }

    // Review of fable/cu-v3-menus-teclas, findings 2 and 7 (t-menu-3: ctrl_k brought up Notepad's «Vínculo» and Escape
    // left it open, and the next sub-goal pressed ctrl_k again): the loop itself writes on a key's step whether the
    // mind's routine pressed it (never the model's) and the names that appeared with it, hands them to the mind, and
    // carries a search key closed with Escape to the next sub-goal as spent on the application it was pressed on.
    [Test]
    public async Task AKeysStepCarriesItsRoutineWhatAppearedWithItAndWhereItWasSpent()
    {
        string selected = string.Empty;
        var harness = new Harness();
        harness.Screen = _ =>
        {
            JsonArray menus = [Control(0, "MenuItem", "Archivo", selected == "Archivo" ? "selected" : "collapsed"),
                               Control(1, "MenuItem", "Ver", selected == "Ver" ? "selected" : "collapsed"),
                               Control(2, "Document", "Editor de texto")];
            if (harness.Acts.Count > 0)
            {
                menus.Add(Control(3, "Edit", "Mostrar texto", "focused"));
                menus.Add(Control(4, "Button", "Cancelar"));
            }

            return Window("*hello world: Bloc de notas", "Notepad", 31, true, menus);
        };
        harness.Mind = request => (request.Subgoal, request.History.Count) switch
        {
            (0, 0) => new MindComputerUseStep("input.key.press", new JsonObject { ["key"] = "ctrl_k" }, "lo busco", Source: "rule"),
            (0, 1) => new MindComputerUseStep("input.key.press", new JsonObject { ["key"] = "escape" }, "cierro", Source: "model"),
            (0, _) => new MindComputerUseStep("input.visible.click", new JsonObject { ["label"] = "Ver", ["index"] = 1 }, "abro", Source: "model"),
            _ => new MindComputerUseStep("none", new JsonObject(), "no veo cómo seguir", "no_step_visible"),
        };
        harness.Receipt = (operation, arguments) =>
        {
            if (operation == "input.visible.click")
            {
                selected = (string?)arguments["label"] ?? string.Empty;
                return new JsonObject { ["selected"] = true };
            }

            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "andá a ver y después a archivo",
            ["steps"] = new JsonArray
            {
                new JsonObject { ["goal"] = "ir a ver", ["application"] = "Bloc de notas", ["successCheck"] = "control:Ver:selected" },
                new JsonObject { ["goal"] = "ir a archivo", ["application"] = "Bloc de notas", ["successCheck"] = "control:Archivo:selected" },
            },
        };

        await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el bloc de notas andá a ver y después a archivo", arguments), arguments,
            CancellationToken.None);

        ComputerUseStepRequest afterEscape = harness.Requests.First(request => request.Subgoal == 0 && request.History.Count == 2);
        var key = (JsonObject)afterEscape.History[0]!;
        var escape = (JsonObject)afterEscape.History[1]!;
        ComputerUseStepRequest next = harness.Requests.First(request => request.Subgoal == 1);
        Assert.Multiple(() =>
        {
            Assert.That((string?)key["key"], Is.EqualTo("ctrl_k"));
            Assert.That((bool?)key["rule"], Is.True);
            Assert.That(((JsonArray)key["appeared"]!).Select(name => (string?)name),
                Is.EquivalentTo(new[] { "mostrar texto", "cancelar" }));
            // Contracase: the model's key is no routine's, and a key that brought nothing up made nothing appear.
            Assert.That(escape["rule"], Is.Null);
            Assert.That((JsonArray)escape["appeared"]!, Is.Empty);
            // The next sub-goal gets the key spent on the application the loop pressed it on (finding 7).
            Assert.That(next.History, Has.Count.EqualTo(1));
            Assert.That((bool?)next.History[0]!["spent"], Is.True);
            Assert.That((string?)next.History[0]!["key"], Is.EqualTo("ctrl_k"));
            Assert.That((string?)next.History[0]!["process"], Is.EqualTo("Notepad"));
        });
    }

    // Contracases: two clicks that changed nothing still stop the mission, and so do two keys looked at with the window
    // in front (where their effect would show).
    [TestCase("input.visible.click", false)]
    [TestCase("input.key.press", true)]
    public async Task TwoActsThatLeftTheScreenUnchangedStillStop(string operation, bool inFront)
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Window("Lanzador", "lanzador", 12, true, [Control(0, "Button", "Tienda")]);
                view["window"]!["hwnd"] = 4660;
                view["window"]!["foreground"] = inFront;
                return view;
            },
        };
        harness.Mind = _ => operation == "input.visible.click"
            ? Step(operation, new JsonObject { ["label"] = "Tienda" })
            : Step(operation, new JsonObject { ["key"] = "ctrl_f" });
        harness.Receipt = static (_, _) => new JsonObject { ["name"] = "Tienda", ["kind"] = "Button", ["surfaceChanged"] = false };
        var arguments = new JsonObject
        {
            ["goal"] = "buscar Cuphead",
            ["application"] = "Lanzador",
            ["successCheck"] = "stepDone:input.text.type:=cuphead",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("buscá Cuphead en el lanzador", arguments), arguments, CancellationToken.None);

        Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_surface_unchanged"));
    }

    // Contracase (review of fable/cu-v3-rafaga): a key delivered by a message or a field's value reaches the window
    // behind as well; two identical looks after it still stop the mission.
    [TestCase("postmessage")]
    [TestCase("setvalue")]
    public async Task KeysDeliveredWithoutTheKeyboardAndLookedAtBehindStillStop(string method)
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Window("Lanzador", "lanzador", 12, true, [Control(0, "Pane", "Lanzador")], "Tienda", "Biblioteca");
                view["window"]!["hwnd"] = 4660;
                view["window"]!["foreground"] = false;
                return view;
            },
        };
        harness.Mind = _ => Step("input.key.press", new JsonObject { ["key"] = "ctrl_f" });
        harness.Receipt = (_, _) => new JsonObject { ["method"] = method };
        var arguments = new JsonObject
        {
            ["goal"] = "buscar Cuphead",
            ["application"] = "Lanzador",
            ["successCheck"] = "stepDone:input.text.type:=cuphead",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("buscá Cuphead en el lanzador", arguments), arguments, CancellationToken.None);

        Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_surface_unchanged"));
    }

    // Live e2 («pick the blue color» on a palette without «Azul»): «blue» and «azul» were not found and the mission
    // stopped as «the screen stopped changing» before the palette's own shade was tried. A click that found nothing
    // is no act that left the screen unchanged.
    [Test]
    public async Task LabelsNotFoundDoNotCountAsActsThatLeftTheScreenUnchanged()
    {
        var harness = new Harness
        {
            Screen = _ => Window("Sin título - Dibujo", "dibujo", 12, true, [Control(0, "Button", "Lápiz")]),
        };
        harness.Mind = request => Step("input.visible.click", new JsonObject
        {
            ["label"] = request.History.Count switch { 0 => "blue", 1 => "azul", _ => "Añil" },
        });
        harness.Receipt = (_, arguments) => (string?)arguments["label"] is "blue" or "azul"
            ? new JsonObject { ["failWith"] = "visible_button_not_found" }
            : new JsonObject { ["name"] = "Añil", ["kind"] = "ListItem", ["surfaceChanged"] = true };
        var arguments = new JsonObject
        {
            ["goal"] = "seleccionar blue",
            ["application"] = "Dibujo",
            ["successCheck"] = "stepDone:input.visible.click:=blue|stepDone:input.visible.click:=azul|stepDone:input.visible.click:=anil",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("pick the blue color", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That((int?)observed["stepCount"], Is.EqualTo(3));
        });
    }

    // Pasada r15b (v3-27): a click on a field's label that did nothing (ok=false) and a click on another field that left
    // the screen as it was stopped the mission «the screen stopped changing» before the model typed. Review of
    // paro-campo (finding 3): the pressed click whose post-read failed still counts as an act that left the screen as
    // it was. Ronda 25 (libro §4.2: the stalled screen's «one more step» went 0 of 4 in the bench, c7, u9, x7): the two
    // acts that left the screen as it was stop the mission, said as such; no third act, no «stalled» mark.
    [Test]
    public async Task AClickPressedThatLeftTheScreenAsItWasCountsAndTwoSuchStopWithoutOneMoreStep()
    {
        bool typed = false;
        var harness = new Harness
        {
            Screen = _ => Window("Mapa de caracteres", "charmap", 12, true,
                [Control(0, "Edit", "Caracteres para copiar:", value: typed ? "euro" : ""), Control(1, "Document", "Buscar:"),
                 Control(2, "Text", "Caracteres para copiar:")], typed ? ["euro"] : []),
        };
        harness.Mind = request => request.History.Count switch
        {
            0 => Step("input.visible.click", new JsonObject { ["label"] = "Caracteres para copiar:", ["index"] = 2 }),
            1 => Step("input.visible.click", new JsonObject { ["label"] = "Buscar:", ["index"] = 1 }),
            _ => Step("input.text.type", new JsonObject { ["text"] = "euro", ["field"] = "Caracteres para copiar", ["replace"] = true }),
        };
        harness.Receipt = (operation, arguments) =>
        {
            if (operation == "input.text.type")
            {
                typed = true;
                return new JsonObject { ["method"] = "setvalue", ["surfaceChanged"] = true };
            }

            return (int?)arguments["index"] == 2
                ? new JsonObject { ["failWith"] = "visible_button_postread_unchanged" }
                : new JsonObject { ["name"] = "Buscar:", ["kind"] = "Document", ["surfaceChanged"] = false };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "copia el simbolo del euro",
            ["application"] = "Mapa de caracteres",
            ["successCheck"] = "text:euro",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abre el mapa de caracteres y copia el simbolo del euro", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Select(act => act.Operation).ToArray(),
                Is.EqualTo(new[] { "input.visible.click", "input.visible.click" }), observed.ToJsonString());
            Assert.That(harness.Requests.Any(request => request.History.Count == 2), Is.False);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_surface_unchanged"));
        });
    }

    // Review of paro-campo (finding 3), contracase: a model that presses one control after another on a window that
    // never answers (each click sent, each post-read unchanged) stops «the screen stopped changing» after the second
    // click (ronda 25: no more step), never pressing on until the budget runs out.
    [Test]
    public async Task ClicksPressedOnAWindowThatNeverAnswersStopAsAnUnchangedScreen()
    {
        string[] labels = ["Seleccionar", "Copiar", "Ayuda", "Avanzada", "Buscar"];
        var harness = new Harness
        {
            Screen = _ => Window("Mapa de caracteres", "charmap", 12, true,
                [Control(0, "Button", "Seleccionar"), Control(1, "Button", "Copiar"), Control(2, "Button", "Ayuda"),
                 Control(3, "Button", "Avanzada"), Control(4, "Button", "Buscar")], "Arial"),
        };
        harness.Mind = request => Step("input.visible.click", new JsonObject
        {
            ["label"] = labels[Math.Min(request.History.Count, 4)],
            ["index"] = Math.Min(request.History.Count, 4),
        });
        harness.Receipt = (_, _) => new JsonObject { ["failWith"] = "visible_button_postread_unchanged" };
        var arguments = new JsonObject
        {
            ["goal"] = "copia el simbolo del euro",
            ["application"] = "Mapa de caracteres",
            ["successCheck"] = "text:euro",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abre el mapa de caracteres y copia el simbolo del euro", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_surface_unchanged"), observed.ToJsonString());
            Assert.That(harness.Acts.Count(act => act.Operation == "input.visible.click"), Is.EqualTo(2));
        });
    }

    // Review of r25-fix-foco-tras-mirada: a UIA click focuses the control it pressed. Five different buttons pressed on a
    // surface that never changes, the keyboard following each click, stop after the second as an unchanged screen: a
    // focus that only went to the pressed control is no change (only one sent elsewhere is, the r24b ctrl_f case).
    [Test]
    public async Task ClicksWhoseFocusOnlyFollowsThePressedControlStillStopAsAnUnchangedScreen()
    {
        string[] labels = ["Seleccionar", "Copiar", "Ayuda", "Avanzada", "Buscar"];
        int pressed = -1;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Window("Mapa de caracteres", "charmap", 12, true,
                    [Control(0, "Button", "Seleccionar"), Control(1, "Button", "Copiar"), Control(2, "Button", "Ayuda"),
                     Control(3, "Button", "Avanzada"), Control(4, "Button", "Buscar")], "Arial");
                view["window"]!["focused"] = pressed < 0 ? null : new JsonObject { ["kind"] = "Button", ["name"] = labels[pressed] };
                return view;
            },
        };
        harness.Mind = request => Step("input.visible.click", new JsonObject
        {
            ["label"] = labels[Math.Min(request.History.Count, 4)],
            ["index"] = Math.Min(request.History.Count, 4),
        });
        harness.Receipt = (_, arguments) =>
        {
            pressed = (int?)arguments["index"] ?? 0;
            return new JsonObject { ["name"] = labels[pressed], ["kind"] = "Button", ["surfaceChanged"] = false };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "copia el simbolo del euro",
            ["application"] = "Mapa de caracteres",
            ["successCheck"] = "text:euro",
            ["budgetSteps"] = 8,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abre el mapa de caracteres y copia el simbolo del euro", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_surface_unchanged"), observed.ToJsonString());
            Assert.That(harness.Acts.Count(act => act.Operation == "input.visible.click"), Is.EqualTo(2));
        });
    }

    // Review of paro-campo (finding 4) and ronda 25 (libro §4.2): no «stalled» mark ever stands on the steps the mind
    // reads; two clicks that left the screen as it was stop before a third that would have changed it.
    [Test]
    public async Task TwoUnchangedScreensStopBeforeAThirdActAndNoStepIsMarkedStalled()
    {
        bool opened = false;
        var harness = new Harness
        {
            Screen = _ => opened
                ? Window("Mapa de caracteres", "charmap", 12, true,
                    [Control(0, "Button", "Seleccionar"), Control(1, "Button", "Copiar"), Control(2, "Button", "Avanzada"),
                     Control(3, "Edit", "Buscar:")], "Buscar:")
                : Window("Mapa de caracteres", "charmap", 12, true,
                    [Control(0, "Button", "Seleccionar"), Control(1, "Button", "Copiar"), Control(2, "Button", "Avanzada")],
                    "Arial"),
        };
        harness.Mind = request => request.History.Count switch
        {
            0 => Step("input.visible.click", new JsonObject { ["label"] = "Seleccionar", ["index"] = 0 }),
            1 => Step("input.visible.click", new JsonObject { ["label"] = "Copiar", ["index"] = 1 }),
            2 => Step("input.visible.click", new JsonObject { ["label"] = "Avanzada", ["index"] = 2 }),
            _ => Step("none", new JsonObject()),
        };
        harness.Receipt = (_, arguments) =>
        {
            if ((int?)arguments["index"] == 2)
            {
                opened = true;
                return new JsonObject { ["name"] = "Avanzada", ["kind"] = "Button", ["surfaceChanged"] = true };
            }

            return new JsonObject { ["name"] = (string?)arguments["label"], ["kind"] = "Button", ["surfaceChanged"] = false };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "copia el simbolo del euro",
            ["application"] = "Mapa de caracteres",
            ["successCheck"] = "text:euro",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abre el mapa de caracteres y copia el simbolo del euro", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_surface_unchanged"), observed.ToJsonString());
            Assert.That(harness.Acts.Count, Is.EqualTo(2));
            Assert.That(harness.Requests.SelectMany(request => request.History).Select(step => step?["stalled"]), Is.All.Null);
        });
    }

    // Pasada r15b (C2, v3-28) gave the mind one more step after two verified acts that left the screen as it was; ronda
    // 25 (libro §4.2, 0 of 4 in the bench) removed it: whatever the next act would do, the mission stops there, said as
    // «the screen stopped changing», and no step carries a «stalled» mark.
    [TestCase(true)]
    [TestCase(false)]
    public async Task TwoVerifiedActsThatLeftTheScreenAsItWasStopWhateverTheNextWouldDo(bool retryChangesTheScreen)
    {
        string font = "Arial";
        var harness = new Harness
        {
            Screen = _ => Window("Mapa de caracteres", "charmap", 12, true,
                [Control(0, "ComboBox", "Fuente:", "collapsed", value: font), Control(1, "Button", "Seleccionar"),
                 Control(2, "Button", "Ayuda")], font),
        };
        harness.Mind = request => request.History.Count switch
        {
            0 => Step("input.visible.click", new JsonObject { ["label"] = "Fuente:", ["index"] = 0 }),
            1 => Step("input.visible.click", new JsonObject { ["label"] = "Seleccionar", ["index"] = 1 }),
            2 => Step("input.text.type", new JsonObject { ["text"] = "Wingdings", ["field"] = "Fuente", ["replace"] = true }),
            _ => Step("none", new JsonObject()),
        };
        harness.Receipt = (operation, arguments) =>
        {
            if (operation == "input.text.type" && retryChangesTheScreen)
            {
                font = "Wingdings";
                return new JsonObject { ["method"] = "select", ["surfaceChanged"] = true };
            }

            return new JsonObject { ["name"] = (string?)arguments["label"], ["kind"] = "Button", ["surfaceChanged"] = false };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "poner Wingdings en Fuente",
            ["application"] = "Mapa de caracteres",
            ["successCheck"] = "text:wingdings",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el mapa de caracteres poné la fuente wingdings", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests.SelectMany(request => request.History).Select(step => step?["stalled"]), Is.All.Null);
            Assert.That(harness.Acts.Select(act => act.Operation),
                Is.EqualTo(new[] { "input.visible.click", "input.visible.click" }));
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_surface_unchanged"));
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

    // Lectura-ruta (r9 v3-61): the start page of the security window as the first look read it (the frozen view of the
    // case: «Inicio» selected, the sections listed and their summaries), and the virus page the click brings.
    private static JsonObject SecurityWindow(bool onVirusPage) => Window(
        "Seguridad de Windows", "SecHealthUI", 41, true,
        [
            Control(0, "ListItem", "Inicio", onVirusPage ? "" : "selected"),
            Control(1, "ListItem", "Protección contra virus y amenazas", onVirusPage ? "selected" : ""),
            Control(2, "ListItem", "Protección de cuentas"),
            Control(3, "ListItem", "Historial de protección"),
            Control(4, "ListItem", "Protección contra virus y amenazas, No se requiere ninguna acción."),
        ],
        onVirusPage
            ? ["Protección contra virus y amenazas", "Amenazas actuales", "Último examen: 08-10-2026 10:28 (examen rápido)"]
            : ["Seguridad de un vistazo", "Protección contra virus y amenazas", "No se requiere ninguna acción."]);

    private static JsonObject SecurityQuestion(string goal) => new()
    {
        ["goal"] = goal,
        ["application"] = "Seguridad de Windows",
        ["successCheck"] = "title:Seguridad de Windows|process:Seguridad de Windows",
    };

    [Test]
    public async Task AQuestionTheOpenedWindowDoesNotAnswerIsNoArrivalOnTheFirstLook()
    {
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ => SecurityWindow(clicked),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Protección contra virus y amenazas", ["index"] = 1 }),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        JsonObject arguments = SecurityQuestion(
            "abrir Seguridad de Windows" + OperationFloor.QuestionMark + "decime cuándo fue el último examen de virus");

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en seguridad de windows decime cuándo fue el último examen de virus", arguments),
            arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "the first look asks the model instead of ending");
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "input.visible.click" }));
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That((int?)observed["stepCount"], Is.EqualTo(1));
        });
    }

    [Test]
    public async Task AQuestionTheFirstLookAnswersEndsOnTheModelsCitationWithoutActs()
    {
        var harness = new Harness
        {
            Screen = _ => SecurityWindow(onVirusPage: true),
            Mind = _ => Step("done", new JsonObject { ["evidence"] = "Último examen: 08-10-2026 10:28 (examen rápido)" }),
        };
        JsonObject arguments = SecurityQuestion(
            "abrir Seguridad de Windows" + OperationFloor.QuestionMark + "decime cuándo fue el último examen de virus");

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en seguridad de windows decime cuándo fue el último examen de virus", arguments),
            arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That((string?)observed["satisfiedBy"], Is.EqualTo("model_evidence"));
            Assert.That(harness.Acts, Is.Empty);
        });
    }

    // Pasada r15b (v3-43): the power options page of the control panel, still loading (its «Cargando» bar at 0) and
    // then loaded with the plan chosen.
    private static JsonObject PowerPage(bool loaded) => Window(
        "Opciones de energía", "explorer", 61, true,
        loaded
            ?
            [
                Control(0, "Hyperlink", "Elegir el comportamiento de los botones de inicio/apagado"),
                Control(1, "RadioButton", "Equilibrado", "selected"),
                Control(2, "RadioButton", "Economizador", ""),
            ]
            : [Control(0, "Button", "Actualizar «Opciones de energía» (F5)"), Control(1, "ProgressBar", "Cargando", "", "0")]);

    private static JsonObject PowerQuestion() => new()
    {
        ["goal"] = "abrir Opciones de energía en el Panel de control" + OperationFloor.QuestionMark + "decime qué plan de energía está activo",
        ["application"] = "Panel de control",
        ["successCheck"] = "stepDone:input.visible.click:opciones de energia",
    };

    private static JsonObject SystemAndSecurity() => Window(
        "Sistema y seguridad", "explorer", 61, true,
        [Control(0, "Hyperlink", "Opciones de energía"), Control(1, "Hyperlink", "Sistema")]);

    [Test]
    public async Task AQuestionsLookStillLoadingIsReadAgainUntilItShowsTheDatum()
    {
        // Pasada r15b B1+C1 (v3-43): the click to the page proved the step, and the look after it still showed the page
        // loading; the mission read it again until it was drawn, and the plan chosen is in the screen it ends on.
        bool clicked = false;
        int loadingLooks = 0;
        var harness = new Harness
        {
            Screen = _ => !clicked ? SystemAndSecurity() : loadingLooks++ < 2 ? PowerPage(loaded: false) : PowerPage(loaded: true),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Opciones de energía", ["index"] = 0 }),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        JsonObject arguments = PowerQuestion();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("decime qué plan de energía está activo", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "only the click was decided");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.ReadyInterval), Is.EqualTo(2));
            Assert.That(observed["screen"]?["values"]?.ToJsonString(), Does.Contain("Equilibrado"));
            Assert.That(observed["screen"]?["values"]?.ToJsonString(), Does.Not.Contain("Cargando"));
        });
    }

    // Ronda 20b (v3-43, pasada r18): the page as it really came, the Explorer's «Cargando» bar at 0 that never goes away,
    // and the plan said only in a link's name.
    private static JsonObject PowerPageAsSeen(string? barValue = "0") => Window(
        "Opciones de energía", "explorer", 61, true,
        [
            Control(0, "Button", "Actualizar «Opciones de energía» (F5)"),
            Control(1, "ProgressBar", "Cargando", "", barValue),
            Control(2, "Hyperlink", "Elegir el comportamiento de los botones de inicio/apagado"),
            Control(3, "Hyperlink", "Cambiar la configuración del plan Equilibrado"),
        ]);

    [Test]
    public async Task AStillLoadingBarIsFurnitureAndTheQuestionReadsWhatTheClickBroughtUp()
    {
        // v3-43: the click reached «Opciones de energía» with «…del plan Equilibrado» shown, the bar stood at 0 through
        // every read again, and the mission answered «No pude». The bar standing still is furniture of the window: the
        // check closes on the link the click brought up that names the plan, and the final quotes it.
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ => clicked ? PowerPageAsSeen() : SystemAndSecurity(),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Opciones de energía", ["index"] = 0 }),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        JsonObject arguments = PowerQuestion();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("decime qué plan de energía está activo", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "only the click was decided");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.ReadyInterval), Is.EqualTo(ComputerUseMission.ReadyLooks));
            Assert.That(observed["screen"]?["values"]?.ToJsonString(), Does.Contain("plan Equilibrado"));
            Assert.That(observed["screen"]?["values"]?.ToJsonString(), Does.Not.Contain("Cargando"));
        });
    }

    [TestCase("moving")]
    [TestCase("indeterminate")]
    public async Task ALoadingBarThatMovesOrHasNoValueIsStillLoading(string bar)
    {
        // Counter-case: a page that really loads (its bar advances, or is indeterminate: no value) is read again, and
        // the question never closes on it: the model is asked on it (its «none» ends the mission unreached).
        bool clicked = false;
        int looks = 0;
        var harness = new Harness
        {
            Screen = _ => !clicked ? SystemAndSecurity()
                : PowerPageAsSeen(bar == "moving" ? (looks++ * 20).ToString(System.Globalization.CultureInfo.InvariantCulture) : null),
            Mind = _ => clicked
                ? Step("none", new JsonObject())
                : Step("input.visible.click", new JsonObject { ["label"] = "Opciones de energía", ["index"] = 0 }),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        JsonObject arguments = PowerQuestion();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("decime qué plan de energía está activo", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.False);
            Assert.That(harness.Requests, Has.Count.EqualTo(2), "the model was asked on the loading page");
            Assert.That((bool?)harness.Requests[1].View["questionPending"], Is.True, "the question is pending there");
        });
    }

    [Test]
    public void AStillBarIsRememberedByItsWindowsProcessNotItsTitle()
    {
        JsonObject first = PowerPageAsSeen();
        JsonObject moving = PowerPageAsSeen("35");
        JsonObject indeterminate = PowerPageAsSeen(null);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.LoadingBarsSignature(first), Is.EqualTo(ComputerUseMission.LoadingBarsSignature(PowerPageAsSeen())));
            Assert.That(ComputerUseMission.LoadingBarsSignature(moving), Is.Not.EqualTo(ComputerUseMission.LoadingBarsSignature(first)));
            Assert.That(ComputerUseMission.LoadingBarsSignature(indeterminate), Is.Null, "an indeterminate bar is never still");
            ComputerUseMission.MarkLoadingBarsStill(first);
            Assert.That(ComputerUseMission.ShowsLoading(first), Is.False, "a still bar is furniture");
            Assert.That(ComputerUseMission.ScreenExcerpt(first)["values"], Is.Null, "and no fact the final quotes");
        });
    }

    [TestCase("Cambiar la configuración del plan Equilibrado", true, false)]
    [TestCase("Cambiar la configuración del plan Equilibrado", false, true)]
    [TestCase("Elegir el comportamiento de los botones de inicio/apagado", true, true)]
    [TestCase("Opciones de energía", true, true)]
    public void OnlyANameTheActBroughtUpThatCarriesAWordOfTheQuestionIsItsDatum(string name, bool appeared, bool unread)
    {
        // The link names the plan («plan» is a content word of the question): what the window says about it. A name
        // that was already there, one that shares no word with the question, or one that only repeats the place asked
        // for («energía» is the goal's own place and the window's title) is no datum.
        JsonObject view = Window("Opciones de energía", "explorer", 61, true,
            [Control(0, "Button", "Actualizar"), Control(1, "Hyperlink", name)]);
        string asked = (string)PowerQuestion()["goal"]!;
        string[] brought = appeared ? [ComputerUseSuccessCheck.Fold(name)] : [];
        Assert.That(ComputerUseMission.QuestionDatumUnread(asked, "stepDone:input.visible.click:opciones de energia", view, appeared: brought),
            Is.EqualTo(unread));
    }

    // Integración ronda 20b: both readings of the question's datum at once. The sub-goal's own click chose the entry
    // «Opciones de energía» (pasada r18: no datum of the window) and brought up the link that names the plan (r20b-3:
    // the window's word about it). The link is the datum; without it the entry the act chose alone is none.
    [Test]
    public void ANameTheActBroughtUpStaysTheDatumBesideTheEntryTheActChose()
    {
        JsonObject view = Window("Opciones de energía", "explorer", 61, true,
            [Control(0, "ListItem", "Opciones de energía", "selected"), Control(1, "Hyperlink", "Cambiar la configuración del plan Equilibrado")]);
        string asked = (string)PowerQuestion()["goal"]!;
        JsonArray pressed =
        [
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Opciones de energía", ["ok"] = true,
                ["surfaceChanged"] = true,
            },
        ];
        string[] brought = [ComputerUseSuccessCheck.Fold("Cambiar la configuración del plan Equilibrado")];
        const string By = "stepDone:input.visible.click:opciones de energia";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.QuestionDatumUnread(asked, By, view, pressed, brought), Is.False, "the link brought up is the datum");
            Assert.That(ComputerUseMission.QuestionDatumUnread(asked, By, view, pressed), Is.True, "the entry the act chose is no datum");
            Assert.That(ComputerUseMission.QuestionDatumUnread(asked, By, view, appeared: brought), Is.False);
        });
    }

    [Test]
    public async Task AQuestionsCheckNeverClosesOnAPageThatNeverLoaded()
    {
        // Counter-case (C1): the page stayed loading past every read again; the step's receipt is no answer, so the model
        // is asked on it instead of the mission closing with no datum (its «none» ends it unreached).
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ => clicked ? PowerPage(loaded: false) : SystemAndSecurity(),
            Mind = request => clicked
                ? Step("none", new JsonObject())
                : Step("input.visible.click", new JsonObject { ["label"] = "Opciones de energía", ["index"] = 0 }),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        JsonObject arguments = PowerQuestion();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("decime qué plan de energía está activo", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That(harness.Requests, Has.Count.EqualTo(2), "the model was asked on the loading page");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.ReadyInterval),
                Is.GreaterThanOrEqualTo(ComputerUseMission.ReadyLooks), "read again, bounded");
        });
    }

    [Test]
    public async Task AQuestionWhoseOpenedFileShowsItsDatumStillEndsWithoutTheModel()
    {
        // v3-18 twin: «abrí paisaje.jpg y decime sus dimensiones»: the viewer's bar shows «1920 x 1080» right after the
        // file opened; a line read on the look is the datum, and the mission ends on its check as before.
        bool opened = false;
        var harness = new Harness
        {
            Screen = _ => opened
                ? Window("paisaje.jpg", "Photos", 41, true, [Control(0, "Button", "Editar"), Control(1, "Button", "Información del archivo")], "JPG", "1920 x 1080")
                : Window("Fotos", "Photos", 41, true, [Control(0, "ListItem", "Galería", "selected"), Control(1, "Edit", "Buscar en la galería")]),
            Mind = _ => Step("file.open", new JsonObject
            {
                ["folder"] = "documents",
                ["name"] = "baxy-prueba-v3\\paisaje.jpg",
                ["application"] = "Fotos",
            }),
        };
        harness.Receipt = (operation, _) =>
        {
            opened |= operation == "file.open";
            return new JsonObject { ["processId"] = 41, ["windowTitle"] = "paisaje.jpg", ["alreadyRunning"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "abrir el archivo D:\\Perfil\\Documentos\\baxy-prueba-v3\\paisaje.jpg" + OperationFloor.QuestionMark
                + "decime las dimensiones de la imagen",
            ["application"] = "Fotos",
            ["successCheck"] = "title:paisaje&stepDone:file.open",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abrí paisaje.jpg y decime sus dimensiones", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "only the opening was decided");
            Assert.That(observed["screen"]?["numbers"]?.ToJsonString(), Does.Contain("1920 x 1080"));
        });
    }

    [TestCase("stepDone:input.visible.click:opciones de energia", "loading", true)]
    [TestCase("stepDone:input.visible.click:opciones de energia", "blank", true)]
    [TestCase("title:paisaje&stepDone:file.open", "blank", true)]
    [TestCase("stepDone:input.visible.click:opciones de energia", "valued", false)]
    [TestCase("title:paisaje&stepDone:file.open", "written", false)]
    [TestCase("control:Equilibrado", "blank", false)]
    [TestCase("model_evidence", "loading", false)]
    public void AQuestionsCheckThatReadsNoValueNeedsADatumOnALoadedLook(string satisfiedBy, string look, bool unread)
    {
        JsonObject view = look switch
        {
            "loading" => PowerPage(loaded: false),
            "valued" => PowerPage(loaded: true),
            "written" => Window("paisaje.jpg", "Photos", 41, true, [Control(0, "Button", "Editar")], "1920 x 1080"),
            _ => Window("paisaje.jpg", "Photos", 41, true, [Control(0, "Button", "Editar")]),
        };
        string asked = "abrir algo" + OperationFloor.QuestionMark + "decime el valor";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.QuestionDatumUnread(asked, satisfiedBy, view), Is.EqualTo(unread));
            Assert.That(ComputerUseMission.QuestionDatumUnread("abrir algo", satisfiedBy, view), Is.False, "a goal without a question");
        });
    }

    [Test]
    public void OnlyALoadingIndicatorMarksALookNotReady()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ShowsLoading(PowerPage(loaded: false)), Is.True);
            Assert.That(ComputerUseMission.ShowsLoading(Window("paisaje.jpg", "Photos", 41, true, [Control(0, "ProgressBar", "Ocupado")])), Is.True);
            Assert.That(ComputerUseMission.ShowsLoading(PowerPage(loaded: true)), Is.False);
            // Counter-case: a progress bar that measures something (a download, a volume) is no loading of the window.
            Assert.That(ComputerUseMission.ShowsLoading(Window("Descargas", "app", 41, true, [Control(0, "ProgressBar", "Descarga de setup.exe", "", "40")])), Is.False);
            // A text that says loading beside nothing placed is no indicator (a written one counts only as the whole view).
            Assert.That(ComputerUseMission.ShowsLoading(Window("Página", "app", 41, true, [Control(0, "Text", "Cargando")])), Is.False);
        });
    }

    // Ronda 20 P8 (v3-29): a notes application opening on «Cargando Notas rápidas...», a Group and a Text in the
    // middle, its caption buttons the only thing to act on, as read in the r18 pass.
    private static JsonObject OpeningOn(string written, params JsonObject[] more)
    {
        JsonArray controls =
        [
            new JsonObject { ["kind"] = "Button", ["name"] = "Minimizar Notas rápidas", ["zone"] = "T" },
            new JsonObject { ["kind"] = "Button", ["name"] = "Maximizar Notas rápidas", ["zone"] = "TR" },
            new JsonObject { ["kind"] = "Button", ["name"] = "Cerrar Notas rápidas", ["zone"] = "TR" },
            new JsonObject { ["kind"] = "Window", ["name"] = "Notas rápidas", ["state"] = "readonly", ["value"] = "Notas rápidas", ["zone"] = "T" },
            new JsonObject { ["kind"] = "Group", ["name"] = written, ["zone"] = "C" },
            new JsonObject { ["kind"] = "Text", ["name"] = written, ["zone"] = "C" },
            new JsonObject { ["kind"] = "TitleBar", ["name"] = "Notas rápidas", ["zone"] = "T" },
        ];
        foreach (JsonObject control in more)
        {
            controls.Add(control);
        }

        return Window("Notas rápidas", "Microsoft.Notes", 41, true, controls);
    }

    [Test]
    public void AWrittenLoadingIndicatorMarksALookNotReadyOnlyWhereItIsTheWholeView()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ShowsLoading(OpeningOn("Cargando Notas rápidas...")), Is.True);
            Assert.That(ComputerUseMission.ShowsLoading(OpeningOn("Loading your notes")), Is.True);
            // Counter-cases: content beside it (a field, a button of its own) is a window drawn; «Ocupado» written is a
            // fact (a calendar's «Mostrar como: Ocupado»), never a wait.
            Assert.That(ComputerUseMission.ShowsLoading(OpeningOn("Cargando Notas rápidas...",
                new JsonObject { ["kind"] = "Edit", ["name"] = "Buscar", ["zone"] = "T" })), Is.False);
            Assert.That(ComputerUseMission.ShowsLoading(OpeningOn("Cargando Notas rápidas...",
                new JsonObject { ["kind"] = "Button", ["name"] = "Nueva nota", ["zone"] = "TL" })), Is.False);
            Assert.That(ComputerUseMission.ShowsLoading(OpeningOn("Ocupado")), Is.False);
            Assert.That(ComputerUseMission.ShowsLoading(OpeningOn("Mostrar como: Ocupado")), Is.False);
        });
    }

    [Test]
    public void ABusyBarIsNoFactWhileABusyItemChosenIsOne()
    {
        // Review of fable/cu-v3-carga-preguntas (finding 4): «Ocupado» names a loading indicator only on a ProgressBar.
        // A calendar's «Mostrar como: Ocupado» chosen (or a messenger's «Busy» status) is the window's fact: the final
        // quotes it and a question's check counts it as a datum; the bar is dropped from what the final quotes.
        JsonObject chosen = Window("Reunión", "calendar", 41, true, [Control(0, "ListItem", "Ocupado", "selected")]);
        JsonObject both = Window("Reunión", "calendar", 41, true,
            [Control(0, "ProgressBar", "Ocupado", "", "0"), Control(1, "ListItem", "Busy", "selected")]);
        string asked = "abrir la reunión" + OperationFloor.QuestionMark + "decime cómo se muestra";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ShowsLoading(chosen), Is.False);
            Assert.That(ComputerUseMission.QuestionDatumUnread(asked, "stepDone:input.visible.click:reunion", chosen), Is.False);
            Assert.That(ComputerUseMission.ScreenExcerpt(chosen)["values"]?.ToJsonString(), Does.Contain("Ocupado"));
            JsonArray values = (JsonArray)ComputerUseMission.ScreenExcerpt(both)["values"]!;
            Assert.That(values.Select(item => (string?)item?["name"]), Is.EqualTo(new[] { "Busy" }), "the bar is no fact");
            // Counter-case: the bar alone still marks the look not ready, and a question's check does not close on it.
            Assert.That(ComputerUseMission.ShowsLoading(both), Is.True);
            Assert.That(ComputerUseMission.QuestionDatumUnread(asked, "stepDone:input.visible.click:reunion",
                Window("Reunión", "calendar", 41, true, [Control(0, "ProgressBar", "Busy", "", "0")])), Is.True);
        });
    }

    [Test]
    public async Task ALoadingBarThatNeverGoesAwayIsReadAgainOnceNotOnEveryLook()
    {
        // Review of fable/cu-v3-carga-preguntas (finding 5): a window with a permanent «Cargando» bar paid the reads again
        // on every look of the mission. They are paid once; a later look of the same window that still shows it is
        // taken as it is, and the mission goes on deciding (here: one more act on it, then «none»).
        int decided = 0;
        var harness = new Harness
        {
            Screen = _ => PowerPage(loaded: false),
            Mind = _ => decided++ < 2
                ? Step("input.visible.click", new JsonObject { ["label"] = "Actualizar «Opciones de energía» (F5)", ["index"] = 0 })
                : Step("none", new JsonObject()),
        };
        harness.Receipt = (_, _) => new JsonObject { ["surfaceChanged"] = true };
        var arguments = new JsonObject
        {
            ["goal"] = "actualizar la página de Opciones de energía",
            ["application"] = "Panel de control",
            ["successCheck"] = "text:Equilibrado",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("actualizá opciones de energía", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests, Has.Count.GreaterThanOrEqualTo(2), "later looks of the window were decided on");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.ReadyInterval),
                Is.EqualTo(ComputerUseMission.ReadyLooks), "the reads again were paid once");
        });
    }

    [Test]
    public async Task AnOpeningWithoutAQuestionStillEndsOnTheWindowsOwnCheck()
    {
        // Contracase: «abrí Seguridad de Windows» asks nothing of the window; its title is the arrival, no model asked.
        var harness = new Harness { Screen = _ => SecurityWindow(onVirusPage: false) };
        JsonObject arguments = SecurityQuestion("abrir Seguridad de Windows");

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abrí seguridad de windows", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.True);
            Assert.That(harness.Requests, Is.Empty);
        });
    }

    [TestCase("title:Seguridad de Windows", true)]
    [TestCase("process:Seguridad de Windows", true)]
    [TestCase("title:Seguridad de Windows&process:Seguridad de Windows", true)]
    [TestCase("header:Seguridad de un vistazo", true)]
    [TestCase("process:Seguridad de Windows&similar:Seguridad", true)]
    [TestCase("control:Último examen", false)]
    [TestCase("title:Seguridad de Windows&page:virus", false)]
    [TestCase("model_evidence", false)]
    public void OnlyTheWindowsIdentityLeavesAQuestionUnlookedFor(string satisfiedBy, bool unlooked)
    {
        string asked = "abrir Seguridad de Windows" + OperationFloor.QuestionMark + "decime cuándo fue el último examen";
        JsonArray opened = [new JsonObject { ["operation"] = "app.open", ["ok"] = true, ["changed"] = true }];
        JsonArray clicked = [Opened(), Click(ok: true, changed: true)];
        // Review of lectura-ruta (finding 3): a click that failed, the no-progress refusal, or one that changed nothing
        // moved nowhere; the question is still unlooked for.
        JsonArray failed = [Opened(), Click(ok: false, changed: false)];
        JsonArray cycled = [Opened(), Click(ok: false, changed: true, error: "computer_use_no_progress")];
        JsonArray unchanged = [Opened(), Click(ok: true, changed: false)];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.QuestionUnlookedFor(asked, satisfiedBy, opened), Is.EqualTo(unlooked));
            Assert.That(ComputerUseMission.QuestionUnlookedFor(asked, satisfiedBy, new JsonArray()), Is.EqualTo(unlooked));
            Assert.That(ComputerUseMission.QuestionUnlookedFor(asked, satisfiedBy, clicked), Is.False, "after an act the check stands");
            Assert.That(ComputerUseMission.QuestionUnlookedFor(asked, satisfiedBy, failed), Is.EqualTo(unlooked), "a failed click");
            Assert.That(ComputerUseMission.QuestionUnlookedFor(asked, satisfiedBy, cycled), Is.EqualTo(unlooked), "no progress");
            Assert.That(ComputerUseMission.QuestionUnlookedFor(asked, satisfiedBy, unchanged), Is.EqualTo(unlooked), "no change");
            Assert.That(ComputerUseMission.QuestionUnlookedFor("abrir Seguridad de Windows", satisfiedBy, opened), Is.False,
                "a goal without a question");
        });

        static JsonObject Opened() => new() { ["operation"] = "app.open", ["ok"] = true, ["changed"] = true };

        static JsonObject Click(bool ok, bool changed, string? error = null)
        {
            var step = new JsonObject { ["operation"] = "input.visible.click", ["ok"] = ok, ["changed"] = changed };
            if (error is not null)
            {
                step["error"] = error;
            }

            return step;
        }
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task AQuestionIsNoArrivalByTheTitleAfterAnActThatMovedNowhere(bool fails)
    {
        // Review of lectura-ruta (finding 3): the click on the first look fails (or presses the page already shown) and
        // the screen stays on «Inicio»; the window's title holding there is still no answer: the model is asked again.
        var harness = new Harness { Screen = _ => SecurityWindow(onVirusPage: false) };
        harness.Mind = _ => harness.Requests.Count == 1
            ? Step("input.visible.click", new JsonObject { ["label"] = "Protección contra virus y amenazas", ["index"] = 1 })
            : null;
        harness.Receipt = (_, _) => fails
            ? new JsonObject { ["failWith"] = "label_not_found" }
            : new JsonObject { ["surfaceChanged"] = false };
        JsonObject arguments = SecurityQuestion(
            "abrir Seguridad de Windows" + OperationFloor.QuestionMark + "decime cuándo fue el último examen de virus");

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en seguridad de windows decime cuándo fue el último examen de virus", arguments),
            arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests, Has.Count.EqualTo(2), "asked again instead of ending on the title");
            Assert.That((bool?)Observed(result)["reached"], Is.Not.True);
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

    // Measured 2026-10-07 on a store: 185 ms after Enter in its search box the results page listed 17 of 52 controls
    // (a placeholder layout) and the model rightly saw no step; the mission ended there instead of waiting for it.
    private static JsonObject SearchBox() => Window("Tienda", "store", 21, true,
    [
        Control(0, "Edit", "Buscar", "focused", "Spotify"), Control(1, "ListItem", "spotify"), Control(2, "ListItem", "spotify lite"),
        Control(3, "Button", "Perfil de usuario"), Control(4, "ListItem", "Inicio", "selected"), Control(5, "ListItem", "Juegos"),
    ], "Tienda", "Inicio", "Juegos");

    private static JsonObject TornDown() => Window("Tienda", "store", 21, true,
        [Control(0, "Button", "Perfil de usuario", "focused"), Control(1, "Custom", "SearchPageLayout"), Control(2, "Text", "placeholder text")],
        "Tienda");

    private static JsonObject Results() => Window("Tienda", "store", 21, true,
    [
        Control(0, "Edit", "Buscar", "", "Spotify"), Control(1, "ListItem", "Spotify: musica y podcasts Aplicacion"),
        Control(2, "Button", "Obtener"), Control(3, "Button", "Perfil de usuario"), Control(4, "ListItem", "Inicio", "selected"),
    ], "Tienda", "Spotify: musica y podcasts", "Obtener");

    private static readonly JsonObject SearchArguments = new()
    {
        ["goal"] = "buscar Spotify",
        ["application"] = "Tienda",
        ["successCheck"] = "stepDone:input.key.press:enter&text:podcasts",
    };

    [Test]
    public async Task AScreenTornDownByTheActIsLookedAtAgainUntilItIsRedrawnBeforeSayingThereIsNoStep()
    {
        bool entered = false;
        int looksAfterEnter = 0;
        var harness = new Harness
        {
            Screen = _ => !entered ? SearchBox() : looksAfterEnter++ < 2 ? TornDown() : Results(),
            Mind = request => request.View["controls"]!.AsArray().Any(control => (string?)control!["kind"] == "Edit")
                ? Step("input.key.press", new JsonObject { ["key"] = "enter" })
                // The mind's «none» carries its default code (live v1: the redraw was never awaited because of it).
                : new MindComputerUseStep("none", new JsonObject(), string.Empty, "no_step_visible"),
        };
        harness.Receipt = (_, _) =>
        {
            entered = true;
            return new JsonObject();
        };
        JsonObject arguments = SearchArguments.DeepClone().AsObject();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en la tienda buscá Spotify", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True, (string?)observed["stoppedBy"]);
            Assert.That(harness.Acts, Has.Count.EqualTo(1), "only the Enter is acted; the wait presses nothing");
            Assert.That(harness.Requests, Has.Count.EqualTo(2), "the model is asked once on the torn-down screen");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.PageLookInterval), Is.LessThanOrEqualTo(ComputerUseMission.PageLooks));
        });
    }

    [Test]
    public async Task AScreenThatDidNotShrinkAfterTheActIsNotWaitedForWhenTheModelSeesNoStep()
    {
        bool entered = false;
        var harness = new Harness
        {
            // After the act the screen lists as much as before: nothing was torn down, the model's «none» stands.
            Screen = _ => !entered ? SearchBox() : Window("Tienda", "store", 21, true,
            [
                Control(0, "Edit", "Buscar", "", "Spotify"), Control(1, "Text", "Sin conexión"), Control(2, "Button", "Reintentar"),
                Control(3, "Button", "Perfil de usuario"), Control(4, "ListItem", "Inicio", "selected"), Control(5, "ListItem", "Juegos"),
            ], "Tienda", "Sin conexión"),
            Mind = request => request.History.Count == 0
                ? Step("input.key.press", new JsonObject { ["key"] = "enter" })
                : Step("none", new JsonObject()),
        };
        harness.Receipt = (_, _) =>
        {
            entered = true;
            return new JsonObject();
        };
        JsonObject arguments = SearchArguments.DeepClone().AsObject();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en la tienda buscá Spotify", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_no_step_visible"));
            Assert.That(harness.Delays, Does.Not.Contain(ComputerUseMission.PageLookInterval));
            Assert.That(harness.Looks, Has.Count.EqualTo(2));
        });
    }

    [Test]
    public async Task AScreenTornDownThatIsNeverRedrawnIsWaitedForOnceBoundedAndThenTheModelsNoneStands()
    {
        bool entered = false;
        var harness = new Harness
        {
            Screen = _ => !entered ? SearchBox() : TornDown(),
            Mind = request => request.History.Count == 0
                ? Step("input.key.press", new JsonObject { ["key"] = "enter" })
                : Step("none", new JsonObject()),
        };
        harness.Receipt = (_, _) =>
        {
            entered = true;
            return new JsonObject();
        };
        JsonObject arguments = SearchArguments.DeepClone().AsObject();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en la tienda buscá Spotify", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_no_step_visible"));
            Assert.That(harness.Requests, Has.Count.EqualTo(2), "the model is not asked again on a screen that did not change");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.PageLookInterval), Is.EqualTo(ComputerUseMission.PageLooks));
        });
    }

    // Encargo V1 (banco final, fable/estab-fase3 0650deac3, v1 «en la Microsoft Store buscá Spotify»): the store's own
    // looks of the three runs. Before the Enter, its home page with the query typed (60 controls); 0.5 to 0.7 s after it,
    // the results page still loading (20 controls: a layout and placeholder text); 2 to 3 s after it, the results.
    private static JsonObject StoreHome(bool typed) => Window("Tienda", "store", 21, true,
    [
        Control(0, "Edit", "Buscar", typed ? "" : "focused", typed ? "Spotify" : null), Control(1, "ListItem", "Inicio", "selected"),
        Control(2, "Hyperlink", "Clasificación por edades: 3+. Haz clic para más información."),
        Control(3, "Button", "Página 1"), Control(4, "Button", "Página 2"), Control(5, "Button", "Página 3"),
        Control(6, "Button", "Página 4"), Control(7, "Button", "Página 5"), Control(8, "Button", "Página 6"),
        Control(9, "Button", "Página 7"), Control(10, "Button", "Call of Duty: Modern Warfare 4"),
        Control(11, "Button", "Roblox - Windows. 444 clasificaciones totales. Clasificación ... strellas. Gratis"),
        Control(12, "Button", "Minecraft: Java & Bedrock Edition for PC. Incluido con Game ... trellas. $32.490"),
        Control(13, "Button", "Instagram. 617 clasificaciones totales. Clasificación media ... strellas. Gratis"),
        Control(14, "Button", "Netflix. Clasificación media de 4,2 sobre 5 estrellas. Gratis"),
        Control(15, "Button", "TikTok. 218 clasificaciones totales. Clasificación media de ... strellas. Gratis"),
        Control(16, "Button", "Canva. Clasificación media de 4,9 sobre 5 estrellas. Gratis"),
        Control(17, "Button", "Perfil de usuario"), Control(18, "ListItem", "Aplicaciones"), Control(19, "ListItem", "Juegos"),
        Control(20, "ListItem", "Descargas"), Control(21, "ListItem", "Biblioteca"),
        Control(22, "Window", "Tienda", "readonly", "Tienda"),
    ], "Tienda", "Tendencias de juegos", "Tendencias en aplicaciones");

    private static JsonObject StoreLoading() => Window("Tienda", "store", 21, true,
    [
        Control(4, "Button", "Perfil de usuario", "focused"), Control(5, "ListItem", "Inicio", "selected"),
        Control(6, "ListItem", "Aplicaciones"), Control(7, "ListItem", "Juegos"), Control(8, "ListItem", "Temas"),
        Control(9, "ListItem", "Novedades"), Control(10, "ListItem", "Descargas"), Control(11, "ListItem", "Biblioteca"),
        Control(12, "Window", "Tienda", "readonly", "Tienda"), Control(14, "Text", "Tienda"),
        Control(15, "Custom", "SearchPageV2Layout"),
        Control(16, "Text", "placeholder text placeholder text placeholder text placehold"), Control(19, "Custom", "(custom)"),
    ], "Tienda", "Spotify", "la", "Aplicaciones", "Juegos", "Temas", "Novedades", "Descargas", "Biblioteca");

    private static JsonObject StoreResults() => Window("Tienda", "store", 21, true,
    [
        Control(0, "Edit", "Buscar", "", "Spotify"), Control(1, "ListItem", "Inicio", "selected"),
        Control(2, "Button", "Filtros", "off focused"), Control(3, "Button", "Todos los departamentos", "on"),
        Control(4, "Button", "Spotify: Música y podcasts. 971 clasificaciones totales. Cla ... llas. Instaladas"),
        Control(5, "Button", "Apple Music. 413 clasificaciones totales. Clasificación medi ... strellas. Gratis"),
        Control(6, "Button", "TIDAL - Música en directo. 63 clasificaciones totales. Clasi ... strellas. Gratis"),
        Control(7, "Button", "Deezer Music. 118 clasificaciones totales. Clasificación med ... strellas. Gratis"),
        Control(8, "Button", "Aplicaciones", "off"), Control(9, "Button", "Juegos", "off"),
        Control(10, "Window", "Tienda", "readonly", "Tienda"),
    ], "Tienda", "«Spotify»", "Spotify: Música y podcasts", "Apple Music", "TIDAL");

    private static Harness StoreSearch(Func<int, JsonObject> afterEnter, string code, string reason)
    {
        int looksAfterEnter = 0;
        bool typed = false;
        bool entered = false;
        var harness = new Harness
        {
            Screen = _ => !entered ? StoreHome(typed) : afterEnter(looksAfterEnter++),
            Mind = request => request.History.Count switch
            {
                0 => Step("input.text.type", new JsonObject { ["text"] = "Spotify" }),
                1 => Step("input.key.press", new JsonObject { ["key"] = "enter" }),
                _ => new MindComputerUseStep("none", new JsonObject(), reason, code),
            },
        };
        harness.Receipt = (operation, _) =>
        {
            typed |= operation == "input.text.type";
            entered |= operation == "input.key.press";
            return operation == "input.text.type"
                ? new JsonObject { ["method"] = "setvalue", ["textLength"] = 7 }
                : new JsonObject();
        };
        return harness;
    }

    private static JsonObject StoreSearchArguments() => new()
    {
        ["goal"] = "buscar Spotify",
        ["application"] = "Tienda",
        ["successCheck"] = "stepDone:input.text.type&stepDone:input.key.press:enter&text:spotify",
    };

    private const string EchoRefused = "lo que escribí se ve porque lo escribí; citá algo del resultado";

    // How each run's mind ended its step on the loading look: fin1 and fin2 cited the typed query twice and the
    // validation refused it («evidence_not_visible»: the stop said «no vi un control» on a page that arrived 2 s later);
    // fin3 answered «none» on its retry and the page was awaited.
    [TestCase("evidence_not_visible", EchoRefused, TestName = "V1_fin1_fin2_refused_echo_awaits_the_page")]
    [TestCase("no_step_visible", "", TestName = "V1_fin3_model_none_awaits_the_page")]
    public async Task ASearchWhosePageWasStillLoadingIsLookedAtAgainAndToldAsDone(string code, string reason)
    {
        Harness harness = StoreSearch(look => look < 2 ? StoreLoading() : StoreResults(), code, reason);
        JsonObject arguments = StoreSearchArguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en la tienda buscá Spotify", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True, (string?)observed["stoppedBy"]);
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "input.text.type", "input.key.press" }),
                "the wait presses nothing");
            Assert.That(harness.Requests, Has.Count.EqualTo(3), "the model is asked once on the loading page");
        });
    }

    [Test]
    public async Task ASearchWhosePageNeverArrivesStillSaysItCouldNotAfterTheBoundedWait()
    {
        // Contracase of V1: the same refused citation on a results page that never loads: the wait is bounded and the
        // stop stays «no vi un control», nothing told as done.
        Harness harness = StoreSearch(_ => StoreLoading(), "evidence_not_visible", EchoRefused);
        JsonObject arguments = StoreSearchArguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en la tienda buscá Spotify", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo(ComputerUseMission.NoStepVisible));
            Assert.That(harness.Acts, Has.Count.EqualTo(2), "the wait presses nothing");
            Assert.That(harness.Requests, Has.Count.EqualTo(3), "the model is not asked again on a page that did not change");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.PageLookInterval), Is.EqualTo(ComputerUseMission.PageLooks));
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
            // v3 point 1: an application opened cold has started when two looks at least StartSettle apart coincide
            // (measured: a launcher's page filled from 16 to 35 lines on the same window), so the first look of its
            // window is followed by one more, StartSettle later.
            // r30 (banco Br28, y8): the verified click on the place changed the window (its menu) without showing the
            // place: it may still be drawing, so it is looked at once more, Settle later, before the model is asked.
            Assert.That(harness.Delays, Is.EqualTo(new[] { ComputerUseMission.Settle, ComputerUseMission.StartSettle, ComputerUseMission.Settle, ComputerUseMission.Settle }),
                "one poll while the window was not there, one look StartSettle later that coincides, one settle after the click, one look more at its arrival");
            // Ronda 26: while the application has no window, neither the first look nor the wait for its window reads
            // anything of the editor in front (no tree, no text: only who is in front); once a window of the
            // application was read, every look is whole.
            Assert.That(harness.Looks.Take(2).Select(look => (bool?)look["identityIfAbsent"]), Is.All.True,
                "the first look and the poll while the window was not there ask only who is in front");
            Assert.That(harness.Looks.Skip(3).All(look => look["identityIfAbsent"] is null), Is.True,
                "no look after the application's window was read");
        });
    }

    // lat-apertura-clic (r13a): after a cold app.open the wait for the window reads one look at a time and ends as soon
    // as the window shows its interface. Ronda 26: each look is read once, with the text the look asked for (before, it
    // was read without OCR and at once again with it). The opened window here is a list whose values change on every
    // look (Servicios: 43 s after its opening, 2 looks of 20 s each); before, two identical looks were demanded and it
    // was looked at twice per round until StartWait (20 s).
    private static JsonObject Opened(string title, int controls, int round, string? named = null)
    {
        var listed = new JsonArray();
        for (int index = 0; index < controls; index++)
        {
            listed.Add(Control(index, "DataItem", index == 0 && named is not null ? named : $"Elemento {index}", "", $"{round * (index + 1)}"));
        }

        return Window(title, "app", 12, true, listed);
    }

    private static async Task<(Harness Harness, List<int> Opening)> OpenColdAsync(
        Func<int, JsonObject> opened, string goal, string root, string check = "control:zzzz", string application = "Aplicación")
    {
        bool open = false;
        int round = 0;
        int decidedAt = -1;
        var harness = new Harness
        {
            Screen = _ => open ? opened(++round) : Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Document", "Texto")]),
        };
        harness.Mind = request =>
        {
            if ((string?)request.View["window"]!["title"] == "Notas - Bloc de notas")
            {
                return Step("app.open", new JsonObject { ["appId"] = application });
            }

            decidedAt = decidedAt < 0 ? harness.Looks.Count : decidedAt;
            return Step("none", new JsonObject());
        };
        harness.Receipt = (_, _) =>
        {
            open = true;
            return new JsonObject { ["processId"] = 12 };
        };
        var arguments = new JsonObject { ["goal"] = goal, ["application"] = application, ["successCheck"] = check };
        _ = await ComputerUseMission.RunAsync(
            harness.Context(root), Execution(goal + " en la aplicación", arguments), arguments, CancellationToken.None);
        // The looks taken from the opening until the first decision on the opened window: whether each asked the text.
        List<int> opening = [.. harness.Looks.Skip(1).Take(decidedAt - 1).Select(look => AskedText(look) ? 1 : 0)];
        return (harness, opening);
    }

    // Ronda 20b, palanca 8 (pasada r18, v3-62): a window opened that shows only its frame (a title bar, its caption
    // buttons, the system menu chain) and on which the model sees no step is not a screen without a step: it is looked
    // at again, bounded, and the content that arrives is decided on. Contracase: one that never shows more stops with
    // its own cause («la aplicación no terminó de mostrarse»), not with «no step visible».
    private static JsonObject FrameOnly(string title)
    {
        JsonObject bar = Control(0, "TitleBar", title);
        bar["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 800, ["h"] = 32 };
        JsonObject close = Control(1, "Button", "Cerrar " + title);
        close["rect"] = new JsonObject { ["x"] = 754, ["y"] = 0, ["w"] = 46, ["h"] = 32 };
        JsonObject menu = Control(2, "MenuItem", "Sistema");
        menu["systemMenu"] = true;
        return Window(title, "app", 12, true, [bar, close, menu], title);
    }

    private static async Task<(ComputerUseMission.Result Result, List<string> Decided, Harness Harness)> OpenFrameAsync(int frameLooks, string root)
    {
        bool open = false;
        int looks = 0;
        var decided = new List<string>();
        var harness = new Harness
        {
            Screen = _ =>
            {
                if (!open)
                {
                    return Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Document", "Texto")]);
                }

                return ++looks <= frameLooks
                    ? FrameOnly("Seguridad")
                    : Window("Seguridad", "app", 12, true, [Control(0, "ListItem", "Inicio"), Control(1, "ListItem", "Protección")]);
            },
        };
        harness.Mind = request =>
        {
            if ((string?)request.View["window"]!["title"] == "Notas - Bloc de notas")
            {
                return Step("app.open", new JsonObject { ["appId"] = "Seguridad" });
            }

            decided.Add(string.Join("|", (request.View["controls"] as JsonArray ?? []).OfType<JsonObject>().Select(control => (string?)control["name"])));
            return Step("none", new JsonObject());
        };
        harness.Receipt = (_, _) =>
        {
            open = true;
            return new JsonObject { ["processId"] = 12, ["alreadyRunning"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "ir a firewall", ["application"] = "Seguridad", ["successCheck"] = "control:zzzz" };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(root), Execution("ir a firewall en seguridad", arguments), arguments, CancellationToken.None);
        return (result, decided, harness);
    }

    [Test]
    public async Task ANoneOnAWindowThatShowsOnlyItsFrameLooksAgainUntilItsContentArrives()
    {
        (ComputerUseMission.Result result, List<string> decided, _) = await OpenFrameAsync(frameLooks: 3, _root);
        (ComputerUseMission.Result empty, List<string> decidedEmpty, Harness emptyHarness) = await OpenFrameAsync(frameLooks: 10_000, _root);

        Assert.Multiple(() =>
        {
            Assert.That(decided, Has.Count.EqualTo(2), "once on the frame, once on the content that arrived");
            Assert.That(decided[^1], Does.Contain("Protección"));
            Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_no_step_visible"));
            Assert.That(decidedEmpty, Has.Count.EqualTo(1), "a frame that never fills is decided on once");
            Assert.That((string?)Observed(empty)["stoppedBy"], Is.EqualTo("computer_use_app_not_shown"));
            Assert.That(emptyHarness.Delays.Where(delay => delay == ComputerUseMission.PageLookInterval).Sum(delay => delay.TotalMilliseconds),
                Is.LessThanOrEqualTo(ComputerUseMission.StartWait.TotalMilliseconds), "bounded by StartWait");
        });
    }

    // Review of palanca 8 (finding 2): a dialog an act brought up that the provider reads as frame alone (frameOnly) is
    // looked at again, bounded; still empty, it stops with the window's own cause, never «la aplicación no terminó de
    // mostrarse, así que no pulsé nada en ella» after a click in that application.
    [Test]
    public async Task ADialogLeftAsFrameAloneAfterAnActNeverSaysNothingWasPressed()
    {
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ =>
            {
                if (!clicked)
                {
                    JsonObject add = Control(0, "Button", "Añadir escena");
                    add["rect"] = new JsonObject { ["x"] = 40, ["y"] = 600, ["w"] = 24, ["h"] = 24 };
                    return Window("OBS 31.0.0 - Perfil: Sin título", "obs64", 12, true, [add, Control(1, "List", "Escenas")]);
                }

                JsonObject dialog = FrameOnly("Añadir escena");
                dialog["frameOnly"] = true;
                return dialog;
            },
            Mind = request => (request.View["controls"] as JsonArray ?? []).OfType<JsonObject>()
                .Any(control => (string?)control["name"] == "Añadir escena" && (string?)control["kind"] == "Button")
                ? Step("input.visible.click", new JsonObject { ["label"] = "Añadir escena" })
                : Step("none", new JsonObject()),
        };
        harness.Receipt = (operation, _) =>
        {
            clicked |= operation == "input.visible.click";
            return new JsonObject { ["ok"] = true, ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "crear una escena llamada Pruebas", ["application"] = "OBS", ["successCheck"] = "control:Pruebas" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en obs crea una escena llamada pruebas", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        string final = OperationFloor.Final(new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = "mission.computer.use",
            ["polarity"] = "failure",
            ["verified"] = true,
            ["succeeded"] = false,
            ["observed"] = observed.DeepClone(),
        }, english: false) ?? string.Empty;
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Select(act => act.Operation), Does.Contain("input.visible.click"));
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_window_not_shown"));
            Assert.That(final, Does.Not.Contain("no pulsé nada"));
            Assert.That(final, Does.Contain("sólo mostró su marco"));
        });
    }

    // Ronda 20b, palanca 8, objetivo 3 (pasada r18, v3-44): in the Control Panel «Ver dispositivos e impresoras» makes
    // Windows open Settings in the packaged apps' frame. The click's receipt names that window (handedTo) and the mission
    // follows it: the next look is bound to Settings' process, read as the requested window, and decided on.
    // Contracase: a click whose receipt names no other window keeps the mission on the Control Panel.
    private async Task<(List<string> Decided, Harness Harness, ComputerUseMission.Result Result)> HandedClickAsync(
        bool handed, JsonObject? handedTo = null)
    {
        var decided = new List<string>();
        var harness = new Harness
        {
            Screen = arguments =>
            {
                if ((int?)arguments["processId"] == 88)
                {
                    // Review 3 of palanca 8 (B1): the person's own document, the window their Ctrl+N or Enter opened.
                    JsonObject word = Window("Informe final.docx - Word", "WINWORD", 88, true, [Control(0, "Button", "Negrita")]);
                    word["window"]!["hwnd"] = 700;
                    word["window"]!["personInputAgoMs"] = 40;
                    return word;
                }

                JsonObject view = (int?)arguments["processId"] == 77
                    ? Window("Configuración", "SystemSettings", 77, true, [Control(0, "ListItem", "Impresoras y escáneres")])
                    : Window("Todos los elementos de Panel de control", "explorer", 30, true,
                        [Control(0, "Hyperlink", "Ver dispositivos e impresoras"), Control(1, "Hyperlink", "Agregar un dispositivo")]);
                view["window"]!["hwnd"] = (int?)arguments["processId"] == 77 ? 900 : 300;
                return view;
            },
        };
        harness.Mind = request =>
        {
            string title = (string?)request.View["window"]!["title"] ?? string.Empty;
            decided.Add(title);
            return title.Contains("Panel de control", StringComparison.Ordinal) && decided.Count == 1
                ? Step("input.visible.click", new JsonObject { ["label"] = "Ver dispositivos e impresoras" })
                : Step("none", new JsonObject());
        };
        harness.Receipt = (operation, _) => operation == "input.visible.click" && handed
            ? new JsonObject
            {
                ["cascadeStage"] = "uia_handoff",
                ["handedTo"] = handedTo?.DeepClone() ?? new JsonObject
                {
                    ["hwnd"] = 900,
                    ["title"] = "Configuración",
                    ["process"] = "SystemSettings",
                    ["processId"] = 77,
                    ["born"] = true,
                },
            }
            : new JsonObject { ["failWith"] = "visible_button_postread_unchanged", ["effectUncertain"] = true };
        var arguments = new JsonObject
        {
            ["goal"] = "go to devices and printers and tell me which printer is the default",
            ["application"] = "Panel de control",
            ["successCheck"] = "control:zzzz",
        };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("control panel, go to devices and printers", arguments), arguments, CancellationToken.None);
        return (decided, harness, result);
    }

    [Test]
    public async Task AClickThatHandsItsEffectToAnotherProcesssWindowIsFollowed()
    {
        (List<string> decided, Harness harness, _) = await HandedClickAsync(handed: true);
        (List<string> stayed, Harness stayedHarness, _) = await HandedClickAsync(handed: false);

        Assert.Multiple(() =>
        {
            Assert.That(decided, Does.Contain("Configuración"), "the window the click handed its effect to is decided on");
            Assert.That(harness.Looks.Skip(1).Any(look => (int?)look["processId"] == 77), Is.True, "looks bound to its process");
            Assert.That(stayed, Does.Not.Contain("Configuración"));
            Assert.That(stayedHarness.Looks.Any(look => (int?)look["processId"] == 77), Is.False);
        });
    }

    [Test]
    public void AHandedWindowIsFollowedOnlyWhenTheClickHeldAndNeverAsTheSharedFrameHost()
    {
        JsonObject Record(bool ok, string process) => new()
        {
            ["operation"] = "input.visible.click",
            ["ok"] = ok,
            ["handedTo"] = new JsonObject
            {
                ["hwnd"] = 900,
                ["title"] = "Configuración",
                ["process"] = process,
                ["processId"] = 77,
                ["born"] = true,
            },
        };

        static bool Follow(JsonObject state, JsonObject record) =>
            ComputerUseMission.FollowHandedWindow(state, record, [record.DeepClone()], DateTimeOffset.UtcNow, out _);

        var followed = new JsonObject { ["processId"] = 30, ["windows"] = new JsonArray(300L), ["family"] = new JsonArray(30) };
        var failed = new JsonObject { ["processId"] = 30 };
        var shared = new JsonObject { ["processId"] = 30 };
        Assert.Multiple(() =>
        {
            Assert.That(Follow(followed, Record(true, "SystemSettings")), Is.True);
            Assert.That((int?)followed["processId"], Is.EqualTo(77));
            Assert.That(followed["windows"], Is.Null, "the Control Panel's windows are forgotten");
            Assert.That(followed["family"], Is.Null);
            Assert.That((followed["handedWindows"] as JsonArray)?.Count, Is.EqualTo(1));
            // Contracase: a click that did not hold, and the frame host shared by every packaged app.
            Assert.That(Follow(failed, Record(false, "SystemSettings")), Is.False);
            Assert.That((int?)failed["processId"], Is.EqualTo(30));
            Assert.That(Follow(shared, Record(true, "ApplicationFrameHost")), Is.False);
            Assert.That((int?)shared["processId"], Is.EqualTo(30));
        });
    }

    // Review 3 of palanca 8 (B1): a window the click's receipt names as handed is followed only through the guard of
    // every window that comes during a mission. The person's Ctrl+N in their Word, or Enter on a file in their folder,
    // during the click's post-read opens a window of theirs: the mission stays on its own window and never decides on
    // theirs, and the click is told unchanged as before. One already open before the click (their browser taking a
    // link) is not followed either unless the request names it.
    private static readonly JsonObject PersonsWord = new()
    {
        ["hwnd"] = 700,
        ["title"] = "Informe final.docx - Word",
        ["process"] = "WINWORD",
        ["processId"] = 88,
        ["born"] = true,
        ["personInputAgoMs"] = 40,
    };

    [Test]
    public async Task AWindowThePersonOpenedDuringTheClickIsNeverFollowed()
    {
        (List<string> decided, Harness harness, _) = await HandedClickAsync(handed: true, handedTo: PersonsWord);

        Assert.Multiple(() =>
        {
            Assert.That(decided, Does.Not.Contain("Informe final.docx - Word"), "the person's document is never decided on");
            Assert.That(harness.Looks.Any(look => (int?)look["processId"] == 88), Is.False, "no look bound to their process");
            Assert.That(harness.Acts.Count(act => act.Operation == "input.visible.click"), Is.EqualTo(1),
                "nothing pressed after the click: never in their window");
        });
    }

    [Test]
    public void AHandedWindowOfThePersonIsRefusedAndTheClickToldUnchanged()
    {
        JsonObject Record(JsonObject handed) => new()
        {
            ["operation"] = "input.visible.click",
            ["label"] = "Ver dispositivos e impresoras",
            ["ok"] = true,
            ["changed"] = true,
            ["handedTo"] = handed.DeepClone(),
        };

        static (bool Followed, string Why) Follow(JsonObject state, JsonObject record) =>
            (ComputerUseMission.FollowHandedWindow(state, record, [record], DateTimeOffset.UtcNow, out string why), why);

        var typed = new JsonObject { ["processId"] = 30, ["windows"] = new JsonArray(300L) };
        JsonObject typedRecord = Record(PersonsWord);
        // The person's input reached its process or the shell after the act (Enter on a file in their folder).
        JsonObject near = (JsonObject)PersonsWord.DeepClone();
        near.Remove("personInputAgoMs");
        near["personNearAgoMs"] = 50;
        var brought = new JsonObject
        {
            ["processId"] = 30,
            ["windows"] = new JsonArray(300L),
            ["lastActUtc"] = DateTimeOffset.UtcNow.AddSeconds(-2).ToString("O", System.Globalization.CultureInfo.InvariantCulture),
        };
        JsonObject broughtRecord = Record(near);
        // Their browser, open before the click, taking the front.
        var open = new JsonObject { ["processId"] = 30, ["windows"] = new JsonArray(300L) };
        JsonObject openRecord = Record(new JsonObject
        {
            ["hwnd"] = 650,
            ["title"] = "Bandeja de entrada - Navegador",
            ["process"] = "browser",
            ["processId"] = 66,
            ["born"] = false,
        });
        Assert.Multiple(() =>
        {
            Assert.That(Follow(typed, typedRecord), Is.EqualTo((false, "person")));
            Assert.That((int?)typed["processId"], Is.EqualTo(30), "the mission stays on its own process");
            Assert.That(typed["windows"], Is.Not.Null, "and on its own windows");
            Assert.That((bool?)typedRecord["ok"], Is.False);
            Assert.That((string?)typedRecord["error"], Is.EqualTo("visible_button_postread_unchanged"));
            Assert.That(typedRecord["handedTo"], Is.Null);
            Assert.That(typedRecord["changed"], Is.Null);
            Assert.That(Follow(brought, broughtRecord), Is.EqualTo((false, "person_since_act")));
            Assert.That((int?)brought["processId"], Is.EqualTo(30));
            Assert.That(Follow(open, openRecord), Is.EqualTo((false, "already_open")));
            Assert.That((int?)open["processId"], Is.EqualTo(30));
        });
    }

    // Ronda 26, review (B1): a look that says only who is in front was not read; it holds no check (the editor in front
    // titled «calculadora.py» is not «title:calculadora» reached), so nothing is reused from it: the mind is
    // asked, the application is opened, and the check holds on the application's own window.
    [Test]
    public async Task ALookThatSaysOnlyWhoIsInFrontHoldsNoCheck()
    {
        bool open = false;
        var harness = new Harness
        {
            Screen = _ => open
                ? Window("Calculadora", "CalculatorApp", 12, true, [Control(0, "Button", "Uno"), Control(1, "Button", "Dos")])
                : Window("calculadora.py - Editor", "editor", 9, false, [Control(0, "Document", "Texto")]),
        };
        harness.Mind = _ => open ? Step("none", new JsonObject()) : Step("app.open", new JsonObject { ["appId"] = "Calculadora" });
        harness.Receipt = (_, _) =>
        {
            open = true;
            return new JsonObject { ["processId"] = 12 };
        };
        var arguments = new JsonObject { ["goal"] = "abrir la calculadora", ["application"] = "Calculadora", ["successCheck"] = "title:calculadora" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abre la calculadora", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)harness.Looks[0]["identityIfAbsent"], Is.True, "the first look asks only who is in front");
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "the check did not close on it: the mind was asked");
            Assert.That(harness.Requests[0].View["controls"]!.AsArray(), Is.Empty, "over who is in front, nothing of the editor");
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "app.open" }));
            Assert.That((bool?)Observed(result)["reached"], Is.True, "on the application's own window");
        });
    }

    // Ronda 26, review (B2): over who is in front only an opening is decided. The provider did not resolve the window in
    // front for the application and the mind sees a step other than opening (it takes it for the application's by its
    // process): the window is looked at whole, once, and decided on again; no later look asks only who is in front.
    [Test]
    public async Task AnythingButAnOpeningIsDecidedOnTheWindowLookedAtWhole()
    {
        var decidedOn = new List<int>();
        var harness = new Harness
        {
            Screen = _ => Window("Sin título: Bloc de notas", "notepad", 9, false, [Control(0, "MenuItem", "Archivo"), Control(1, "Document", "Texto")]),
        };
        harness.Mind = request =>
        {
            decidedOn.Add(request.View["controls"]!.AsArray().Count);
            return Step("none", new JsonObject());
        };
        var arguments = new JsonObject { ["goal"] = "escribir hola", ["application"] = "Notepad", ["successCheck"] = "control:zzzz" };

        _ = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("escribe hola en notepad", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)harness.Looks[0]["identityIfAbsent"], Is.True);
            Assert.That(harness.Looks, Has.Count.GreaterThanOrEqualTo(2), "looked at again");
            Assert.That(harness.Looks.Skip(1).All(look => look["identityIfAbsent"] is null), Is.True, "whole from then on");
            Assert.That(decidedOn, Is.EqualTo(new[] { 0, 2 }), "the «none» that stands is the one over the window read whole");
            Assert.That(harness.Acts, Is.Empty);
        });
    }

    [Test]
    public async Task AColdOpeningWhoseInterfaceIsUpIsTakenWhenItStopsGrowingNotWhenItsValuesHold()
    {
        (Harness harness, List<int> opening) = await OpenColdAsync(round => Opened("Servicios", 30, round), "ver los servicios", _root);

        TestContext.Out.WriteLine($"looks after the opening: {opening.Count}, paced {harness.Delays.Sum(delay => delay.TotalMilliseconds)} ms");
        Assert.Multiple(() =>
        {
            Assert.That(opening, Is.EqualTo(new[] { 1, 1 }), "two looks, each read once with its text");
            Assert.That(harness.Delays.Take(2).Sum(delay => delay.TotalMilliseconds), Is.LessThan(1000));
        });
    }

    // r29 (bancos r27, cd y c24b: 40 cold openings showed their whole interface at the first look and waited StartSettle
    // for a second look that read the same, or one control apart, in all 40): an interface that is up and shows no
    // loading is looked at again one Settle later and taken when its tree reads the same. One look alone never says so.
    [Test]
    public async Task AColdOpeningWhoseInterfaceIsUpIsLookedAtAgainOneSettleLater()
    {
        (Harness harness, List<int> opening) = await OpenColdAsync(_ => Opened("Calculadora", 30, 1), "calcular 8 por 7", _root);

        Assert.Multiple(() =>
        {
            Assert.That(opening, Is.EqualTo(new[] { 1, 1 }), "still two looks that coincide");
            Assert.That(harness.Delays[0], Is.EqualTo(ComputerUseMission.Settle), "the look that confirms it comes one Settle later");
        });
    }

    // Counter-cases of r29. An interface that is up and still grows is looked at one Settle apart until two looks
    // coincide (never taken while it changes); one that shows a loading bar is not hurried: its next look waits what is
    // left of StartSettle, as before.
    [Test]
    public async Task AnInterfaceThatIsUpIsNeverTakenWhileItGrowsNorHurriedWhileItLoads()
    {
        int[] sizes = [25, 40, 60, 60];
        (Harness growing, List<int> grew) = await OpenColdAsync(
            round => Opened("Programador", sizes[Math.Min(round, sizes.Length) - 1], 1), "ver las tareas", _root);
        (Harness loading, List<int> loaded) = await OpenColdAsync(
            round =>
            {
                JsonObject view = Opened("Ajustes", 30, 1);
                if (round is 2 or 3)
                {
                    view["controls"]!.AsArray().Add(Control(30, "ProgressBar", "Cargando", "", $"{round * 10}"));
                }

                return view;
            },
            "ver las tareas", _root);

        Assert.Multiple(() =>
        {
            Assert.That(grew, Is.EqualTo(new[] { 1, 1, 1, 1 }), "25, 40 and 60 grow; the second 60 is the first still one");
            Assert.That(growing.Delays.Take(3), Is.All.EqualTo(ComputerUseMission.Settle));
            Assert.That(loaded.Count, Is.GreaterThanOrEqualTo(4), "not taken on a look that shows it loading");
            Assert.That(loading.Delays[1], Is.GreaterThan(ComputerUseMission.Settle), "the look after one that shows it loading is not hurried");
        });
    }

    [Test]
    public async Task AColdOpeningThatShowsTheControlTheGoalNamesIsTakenAtItsFirstLook()
    {
        (_, List<int> opening) = await OpenColdAsync(round => Opened("Iniciador", 4, round, named: "Biblioteca"), "ir a la biblioteca", _root,
            "control:biblioteca:current|title:biblioteca|page:biblioteca|control:library:current|title:library|mark:biblioteca");

        Assert.That(opening, Is.EqualTo(new[] { 1 }), "the first look shows it, read once with its text");
    }

    // Estabilización N1 (banco h2 n1, «abrí Paint, elegí el lápiz y después el color rojo»): Paint's first look after a
    // cold opening, its ribbon still loading (83 controls, no «Lápiz», «Relleno» nor «Texto»), was decided on because the
    // goal's verb «seleccionar» named its «Seleccionar» tool; the click on «lapiz» failed and the mission stopped. The
    // target is what the planned check names: that look is looked at again, and the next one (114, «Lápiz») is taken.
    // Counter-case (banco h1 n1): a first look whose ribbon already shows «Lápiz» is taken at once, as before.
    [Test]
    public async Task APaintRibbonStillLoadingWithoutTheTargetIsLookedAtAgain()
    {
        const string check = "control:=lapiz:selected|control:=lapiz:on|stepDone:input.visible.click:=lapiz"
            + "|control:=pencil:selected|control:=pencil:on|stepDone:input.visible.click:=pencil";
        (_, List<int> partial) = await OpenColdAsync(
            round => round == 1 ? PaintRibbon(withTools: false, 83) : PaintRibbon(withTools: true, 114),
            "seleccionar lapiz", _root, check, "Paint");
        (_, List<int> whole) = await OpenColdAsync(round => PaintRibbon(withTools: true, 92), "seleccionar lapiz", _root, check, "Paint");

        Assert.Multiple(() =>
        {
            Assert.That(partial, Is.EqualTo(new[] { 1, 1 }), "the ribbon without «Lápiz» is looked at again");
            Assert.That(whole, Is.EqualTo(new[] { 1 }), "a ribbon showing «Lápiz» is taken at its first look");
            Assert.That(ComputerUseMission.TargetActionable(check, "Paint", PaintRibbon(withTools: false, 83)), Is.False,
                "«Seleccionar» is the goal's verb, not its target");
            Assert.That(ComputerUseMission.TargetActionable("stepDone:input.key.press:enter|stepDone:input.text.type:seleccionar",
                "Paint", PaintRibbon(withTools: false, 83)), Is.False, "of a step done only a click's label names a target");
        });
    }

    // Encargo CS (banco fz1 s12, «en Steam andá a la biblioteca» with Steam closed after a restart): the first window was
    // Steam's updater (journal: «Actualizando Steam...» at 0 on three looks, «Verificando instalación...», «Cancelar»
    // alone); the opening took it at its second look, the model's «open» on its only control pressed «Cancelar» and the
    // start was cancelled. Now the updater is looked at, never decided on, past StartWait, and the main window that
    // replaces it is the one decided on.
    private const string LibraryCheck =
        "control:biblioteca:current|title:biblioteca|page:biblioteca|control:library:current|title:library|page:library|mark:biblioteca|mark:library";

    // The real controls of Steam's updater window in banco fz1 s12 (9 controls; the frame's own buttons, the texts, the bar).
    private static JsonObject SteamUpdater() => Window("Steam", "steam", 12, true,
        [
            Control(0, "Button", "Cancelar"),
            Control(1, "TitleBar", "Steam"),
            Control(2, "Button", "Minimizar"),
            Control(3, "Button", "Maximizar", "disabled"),
            Control(4, "Text", "Actualizando Steam..."),
            Control(5, "ProgressBar", "Actualizando Steam...", "", "0"),
            Control(6, "Text", "Verificando instalación..."),
            Control(7, "Button", "Cerrar"),
            Control(8, "Pane", "Steam"),
        ],
        "Actualizando Steam...", "Verificando instalación...", "Cancelar");

    [Test]
    public async Task AnUpdaterWindowOfAnApplicationJustStartedIsWaitedOnNeverDecidedOn()
    {
        const int updaterLooks = 30;
        (Harness harness, List<int> opening) = await OpenColdAsync(
            round => round <= updaterLooks ? SteamUpdater() : Opened("Steam", 30, 1, named: "Biblioteca"),
            "ir a biblioteca", _root, LibraryCheck, "Steam");

        Assert.Multiple(() =>
        {
            Assert.That(opening, Has.Count.EqualTo(updaterLooks + 1), "every look of the updater, then the main window");
            Assert.That(harness.Requests.Select(request => (string?)request.View["window"]!["title"]),
                Is.EqualTo(new[] { "Notas - Bloc de notas", "Steam" }), "decided before opening and on the main window only");
            Assert.That(harness.Requests[^1].View["controls"]!.AsArray().Any(control => (string?)control!["name"] == "Cancelar"),
                Is.False, "the updater's «Cancelar» never reached the model");
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "app.open" }), "nothing pressed");
            Assert.That(harness.Delays.Skip(1).Take(updaterLooks - 1).Sum(delay => delay.TotalMilliseconds),
                Is.GreaterThan(ComputerUseMission.StartWait.TotalMilliseconds), "waited past StartWait, bounded by ColdStartWait");
        });
    }

    // Counter-case: an updater that never gives way stops at ColdStartWait, said as an application that did not finish
    // showing itself, and nothing is decided on it nor pressed in it.
    [Test]
    public async Task AnUpdaterThatNeverGivesWayStopsAtTheColdStartCapWithoutPressingAnything()
    {
        bool open = false;
        var harness = new Harness
        {
            Screen = _ => open ? SteamUpdater() : Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Document", "Texto")]),
        };
        harness.Mind = _ => Step("app.open", new JsonObject { ["appId"] = "Steam" });
        harness.Receipt = (_, _) =>
        {
            open = true;
            return new JsonObject { ["processId"] = 12, ["alreadyRunning"] = false };
        };
        var arguments = new JsonObject { ["goal"] = "ir a biblioteca", ["application"] = "Steam", ["successCheck"] = LibraryCheck };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Steam andá a la biblioteca", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_app_not_shown"));
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "only the opening was decided");
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "app.open" }));
            Assert.That(harness.Delays.Sum(delay => delay.TotalMilliseconds),
                Is.InRange(ComputerUseMission.ColdStartWait.TotalMilliseconds, ComputerUseMission.ColdStartWait.TotalMilliseconds + 2000));
        });
    }

    // Counter-cases: a mission that asks to cancel the update has its target in that window (the check names «Cancelar»),
    // and an application already running (no cold start) is taken at its first look: no extra wait.
    [Test]
    public async Task AnUpdaterIsTakenAtOnceWhenTheCheckNamesItsControlOrTheApplicationWasRunning()
    {
        (_, List<int> asked) = await OpenColdAsync(_ => SteamUpdater(), "cancelar la actualizacion", _root,
            "stepDone:input.visible.click:cancelar", "Steam");
        bool open = false;
        var harness = new Harness
        {
            Screen = _ => open ? SteamUpdater() : Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Document", "Texto")]),
        };
        harness.Mind = request => (string?)request.View["window"]!["title"] == "Notas - Bloc de notas"
            ? Step("app.open", new JsonObject { ["appId"] = "Steam" })
            : Step("none", new JsonObject());
        harness.Receipt = (_, _) =>
        {
            open = true;
            return new JsonObject { ["processId"] = 12, ["alreadyRunning"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "ir a biblioteca", ["application"] = "Steam", ["successCheck"] = LibraryCheck };
        _ = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Steam andá a la biblioteca", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.EqualTo(new[] { 1 }), "the check names «Cancelar»: decided on at its first look");
            Assert.That(harness.Requests, Has.Count.EqualTo(2), "already running: decided on at once");
            Assert.That(harness.Delays.Where(delay => delay == ComputerUseMission.RetiePause), Is.Empty, "no splash wait");
            Assert.That(ComputerUseMission.ProgressSplash(SteamUpdater(), LibraryCheck, "Steam"), Is.True);
            Assert.That(ComputerUseMission.ProgressSplash(Opened("Explorador", 30, 1), LibraryCheck, "Explorador"), Is.False);
            Assert.That(ComputerUseMission.StartCap(new JsonObject()), Is.EqualTo(ComputerUseMission.StartWait));
            Assert.That(ComputerUseMission.StartCap(new JsonObject { ["progressSplash"] = true }), Is.EqualTo(ComputerUseMission.ColdStartWait));
        });
    }

    // The real controls of Paint's first look in banco h2 (withTools: false) and h1 n1 (the tools group drawn).
    private static JsonObject PaintRibbon(bool withTools, int controlCount)
    {
        string[] tools = withTools ? ["Lápiz", "Relleno", "Texto"] : [];
        string[] buttons = [.. tools, "Borrador", "Selector de colores", "Lupa", "Triángulo", "Triángulo rectángulo", "Diamante",
            "Pentágono", "Hexágono", "Flecha derecha", "Flecha izquierda", "Flecha arriba", "Flecha abajo",
            "Estrella de cuatro puntos", "Estrella de cinco puntos", "Estrella de seis puntas"];
        var controls = new JsonArray
        {
            Control(0, "MenuItem", "Archivo", "collapsed"),
            Control(1, "MenuItem", "Editar", "collapsed"),
            Control(2, "MenuItem", "Ver", "collapsed"),
            Control(3, "RadioButton", "Seleccionar", "collapsed", "Rectángulo"),
            Control(4, "RadioButton", "Pinceles", "selected collapsed", "Cepillo"),
            Control(5, "RadioButton", "Color 1: Negro", "selected"),
            Control(6, "RadioButton", "Color 2: Blanco"),
        };
        foreach (string name in buttons)
        {
            controls.Add(Control(controls.Count, "Button", name, "off"));
        }

        controls.Add(Control(controls.Count, "Slider", "Tamaño", "readonly", "3 píxel"));
        controls.Add(Control(controls.Count, "Slider", "Zoom", "readonly", "100 por ciento"));
        return InWindow(32837210, Window("Sin título - Paint", "mspaint", 12, true, controls), controlCount);
    }

    // Counter-case: an interface still being built (its tree grows look after look) is waited on until it stops growing.
    [Test]
    public async Task AColdOpeningWhoseTreeStillGrowsIsWaitedOn()
    {
        int[] sizes = [25, 40, 60, 60, 60];
        (_, List<int> opening) = await OpenColdAsync(round => Opened("Programador", sizes[Math.Min(round, sizes.Length) - 1], 1), "ver las tareas", _root);

        Assert.That(opening, Is.EqualTo(new[] { 1, 1, 1, 1 }), "25, 40 and 60 grow; the second 60 is the first still one");
    }

    private static JsonObject InWindow(long hwnd, JsonObject view, int? controlCount = null)
    {
        ((JsonObject)view["window"]!)["hwnd"] = hwnd;
        if (controlCount is { } counted)
        {
            view["controlCount"] = counted;
        }

        return view;
    }

    private static JsonArray Buttons(int count, string prefix)
    {
        var listed = new JsonArray();
        for (int index = 0; index < count; index++)
        {
            listed.Add(Control(index, "Button", $"{prefix} {index}"));
        }

        return listed;
    }

    // Review of lat-apertura-clic (finding 2, probe A): «Inicio» with 60 controls, then another window of the
    // application with 25 buttons whose names change on every look. The count alone took it at the new window's first
    // look, half drawn; now its tree never reads twice the same, so it is waited on.
    [Test]
    public async Task AnotherWindowOfTheApplicationWhoseButtonsStillChangeIsNotTakenAsStill()
    {
        (_, List<int> opening) = await OpenColdAsync(
            round => round == 1
                ? InWindow(100, Opened("Inicio", 60, 1))
                : InWindow(200, Window("Inicio", "app", 12, true, Buttons(25, "Paso " + round))),
            "ver las tareas", _root);

        Assert.That(opening.Count, Is.GreaterThan(3), "not taken at the new window's first look");
    }

    // Finding 2: a window that shrinks (60 → 25) is not still; the same 25 twice are.
    [Test]
    public async Task AWindowThatShrinksIsNotTakenAsStill()
    {
        (_, List<int> opening) = await OpenColdAsync(
            round => InWindow(100, round == 1 ? Opened("Panel", 60, 1) : Opened("Panel", 25, 1)), "ver las tareas", _root);

        Assert.That(opening, Is.EqualTo(new[] { 1, 1, 1 }), "60, then 25 (shrank), then 25 again: still");
    }

    // Finding 2: a tree past the view's cap (60 shown each time) that still grows is told by its whole count.
    [Test]
    public async Task ATreePastTheViewsCapIsWaitedOnWhileItsWholeCountGrows()
    {
        int[] totals = [80, 120, 150, 150, 150];
        (_, List<int> opening) = await OpenColdAsync(
            round => InWindow(100, Opened("Visor", 60, 1), totals[Math.Min(round, totals.Length) - 1]), "ver las tareas", _root);

        Assert.That(opening, Is.EqualTo(new[] { 1, 1, 1, 1 }), "80, 120 and 150 grow past the cap; the second 150 is still");
    }

    // Review 1 of motor-listas-abiertas (finding 2): a tree past the cap that grows slowly (7 controls a look, under
    // 5 % of it) with the same 60 shown is still loading; it is taken only once its whole count stops growing.
    [Test]
    public async Task ATreePastTheViewsCapThatGrowsSlowlyIsStillWaitedOn()
    {
        int[] totals = [150, 157, 164, 171, 171];
        (_, List<int> opening) = await OpenColdAsync(
            round => InWindow(100, Opened("Visor", 60, 1), totals[Math.Min(round, totals.Length) - 1]), "ver las tareas", _root);

        Assert.That(opening, Is.EqualTo(new[] { 1, 1, 1, 1, 1 }), "157, 164 and 171 still grow; the second 171 is still");
    }

    // Review of lat-apertura-clic (finding 3, probe B): «cerrar esta pestana» on a window whose caption button is
    // «Cerrar», with «Atras» and «Adelante» and a written «Cargando…» that grows: no control a person acts on is named
    // by the goal as a whole word («esta» is inside «pestana» and «restaurar»), so its first look does not end the wait.
    [Test]
    public async Task ACaptionButtonOrAWordInsideAnotherIsNotTheGoalsTarget()
    {
        (_, List<int> opening) = await OpenColdAsync(
            round => InWindow(100, Window("Navegador", "app", 12, true,
            [
                Control(0, "Button", "Cerrar"),
                Control(1, "Button", "Restaurar"),
                Control(2, "Button", "Atras"),
                Control(3, "Button", "Adelante"),
                Control(4, "Text", "Cargando " + new string('i', Math.Min(round, 3))),
            ])),
            "cerrar esta pestana", _root, "stepDone:input.visible.click:cerrar esta pestana");

        Assert.That(opening.Count, Is.GreaterThanOrEqualTo(3), "taken only once its tree stops changing");
        Assert.That(ComputerUseMission.TargetActionable("stepDone:input.visible.click:cerrar esta pestana", "app", InWindow(100, Window(
            "Navegador", "app", 12, true, [Control(0, "TabItem", "Nueva pestana")]))), Is.True, "counter-case: a tab named by the target's own word");
        Assert.That(ComputerUseMission.TargetActionable("control:biblioteca:current|title:biblioteca", "app", Window("Iniciador", "app", 12, true,
            [Control(0, "Text", "Cargando tu biblioteca"), Control(1, "Button", "Atras")])), Is.False,
            "a written text is no control to act on");
    }

    // Review of lat-apertura-clic (finding 1): the Core answers one request at a time and cannot stop one it was sent,
    // so an act that outlasts what is left of the mission's time is not cut on the App's side (the cut stopped nothing:
    // the click could still land after «se agotó el tiempo», and the next request queued behind it). Its own answer is
    // waited for and recorded as it is; the mission then stops with its honest cause and sends no other act.
    [Test]
    public async Task AnActThatOutlastsTheMissionsTimeIsWaitedForAndNothingIsSentAfterIt()
    {
        var harness = new Harness
        {
            Screen = _ => Window("Iniciador", "app", 12, true, [Control(0, "Button", "Biblioteca"), Control(1, "Button", "Tienda")]),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Biblioteca", ["index"] = 0 }),
        };
        ComputerUseMission.Context seam = harness.Context(_root);
        var sent = new List<string>();
        bool clickAnswered = false;
        var context = new ComputerUseMission.Context
        {
            Execute = async (prepared, timeout, token) =>
            {
                sent.Add(prepared.OperationName);
                if (prepared.OperationName == "input.visible.click")
                {
                    // A click whose label wait outlasts the mission's time (a launcher still drawing), and which the
                    // Core finishes whatever the App does.
                    await Task.Delay(TimeSpan.FromMilliseconds(700), CancellationToken.None);
                    clickAnswered = true;
                }

                return await seam.Execute(prepared, timeout, token);
            },
            Decide = seam.Decide,
            Registry = seam.Registry,
            MarkResolved = seam.MarkResolved,
            SetStatus = seam.SetStatus,
            Delay = seam.Delay,
            NowMs = seam.NowMs,
            MissionTime = TimeSpan.FromMilliseconds(400),
        };
        var arguments = new JsonObject { ["goal"] = "ir a la biblioteca", ["application"] = "Iniciador", ["successCheck"] = "control:biblioteca:selected" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            context, Execution("andá a la biblioteca", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        int click = sent.IndexOf("input.visible.click");
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_time_exhausted"));
            Assert.That(clickAnswered, Is.True, "the mission ended only once the act had answered");
            Assert.That(sent.Count(operation => operation == "input.visible.click"), Is.EqualTo(1), "never sent again");
            Assert.That(sent.Skip(click + 1).Where(operation => operation != "input.visible.controls"), Is.Empty,
                "no other act after the mission's time ran out");
        });
    }

    // Counter-case: a small window (a handful of controls, no named target) whose controls still change is not taken
    // until two looks apart coincide (v3 point 1).
    [Test]
    public async Task AColdSmallWindowThatStillChangesIsWaitedOnUntilTwoLooksCoincide()
    {
        // Its written text never reads twice the same (the OCR's jitter): a window with a tree is compared by its tree.
        (Harness harness, List<int> opening) = await OpenColdAsync(
            round =>
            {
                JsonObject view = Opened("Lanzador", 5, Math.Min(round, 3));
                view["text"] = new JsonObject { ["C"] = new JsonArray($"Tareas {round}") };
                return view;
            },
            "ver las tareas", _root);

        Assert.Multiple(() =>
        {
            Assert.That(opening.Count, Is.InRange(4, 5), "rounds 1, 2 and 3 differ; the fourth coincides, whatever it writes");
            // Ronda 26: each look of the wait is read once, with the text the sub-goal's look asked for; a window with a
            // tree is still compared by its tree (the text its looks carry never makes it «changing»: StartingLook).
            Assert.That(opening, Has.All.EqualTo(1), "one read per look, none again for the text");
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
                // The look says its process shows no other window (ventana-misión: every look a mission may tie itself
                // to carries «others»; one that does not say counts as several, and nothing is written there).
                view["window"]!["others"] = new JsonArray();
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

    // Integration of round 2 (contract «Seguridad v2»): with no application named the mission works on the window in
    // front; when that is VS Code (the view marks it «protected» by its process), «guardá esto como baxy-x.txt» types
    // and presses nothing and says why. Goal v3 destino: Notepad in front, not opened by the mission nor resolved for
    // it, takes no key either (stopped with computer_use_no_application).
    [TestCase(true)]
    [TestCase(false)]
    public async Task WithNoApplicationNamedNothingIsDoneInAProtectedWindowInFront(bool editorInFront)
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = editorInFront
                    ? Window("ComputerUseMission.cs - BAXY - Visual Studio Code", "Code", 77, false, [Control(0, "Document", "(document)", "focused")])
                    : Window("Sin título - Bloc de notas", "Notepad", 31, false, [Control(0, "Document", "Editor de texto", "focused", "")]);
                view["window"]!["hwnd"] = editorInFront ? 999 : 4660;
                if (editorInFront)
                    view["window"]!["protected"] = true;
                return view;
            },
            Mind = request => Step("input.key.press", new JsonObject { ["key"] = "ctrl_shift_s" }),
        };
        var arguments = new JsonObject { ["goal"] = "guardar como baxy-x.txt", ["application"] = null, ["successCheck"] = "stepDone:input.key.press:ctrl_shift_s" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("guardá esto como baxy-x.txt", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            if (editorInFront)
            {
                Assert.That(harness.Acts, Is.Empty);
                Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_window_protected"));
            }
            else
            {
                // Goal v3 destino (r5a M5, v3-35 T3): with no application resolved the window in front is the
                // person's; it takes no key either, and the stop says no application was known (before, Notepad in
                // front took the key: that is the behaviour the goal removes).
                Assert.That(harness.Acts, Is.Empty);
                Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_no_application"));
            }
        });
    }

    // Integración ronda 5 (seguridad): with no application resolved, a click on the person's window in front is not
    // sent either (t-menu-1 right-clicked there); counter-case: the person named that window («en esta ventana…»), the
    // mind's frontWindow, and the same key reaches it.
    [TestCase(false)]
    [TestCase(true)]
    public async Task WithNoApplicationTheWindowInFrontIsTouchedOnlyWhenThePersonNamedIt(bool named)
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Window("Sin título - Bloc de notas", "Notepad", 31, false, [Control(0, "Document", "Editor de texto", "focused", "")]);
                view["window"]!["hwnd"] = 4660;
                return view;
            },
            Mind = request => Step("input.key.press", new JsonObject { ["key"] = "ctrl_shift_s" }),
        };
        var arguments = new JsonObject { ["goal"] = "guardar como baxy-x.txt", ["application"] = null, ["successCheck"] = "stepDone:input.key.press:ctrl_shift_s" };
        if (named)
            arguments["frontWindow"] = true;

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en esta ventana guardá esto como baxy-x.txt", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            if (named)
            {
                Assert.That(harness.Acts, Is.Not.Empty);
                Assert.That((string?)Observed(result)["stoppedBy"], Is.Not.EqualTo("computer_use_no_application"));
            }
            else
            {
                Assert.That(harness.Acts, Is.Empty);
                Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_no_application"));
            }
        });
    }

    [Test]
    public async Task WithNoApplicationAClickOnThePersonsWindowIsNotSent()
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Window("Sin título - Bloc de notas", "Notepad", 31, false, [Control(0, "MenuItem", "Archivo", "")]);
                view["window"]!["hwnd"] = 4660;
                return view;
            },
            Mind = request => Step("input.visible.click", new JsonObject { ["index"] = 0, ["label"] = "Archivo" }),
        };
        var arguments = new JsonObject { ["goal"] = "abrir el menú Archivo", ["application"] = null, ["successCheck"] = null };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abrí el menú Archivo", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Is.Empty);
            Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_no_application"));
        });
    }

    // v3 point 0, fix 3: an act that needs the real input and found the person busy (no pause within the wait) or was
    // stopped by their input is not given up at once (fable/cu-v3-reintento-pausa): it is tried again after their next
    // pause, the same act and without asking the mind, PersonPauseRetries times; then the mission stops with that cause
    // and the final says it in their words (tests/data/cu_floor_twins.json, cu-failed-person-*).
    [TestCase("input_user_not_paused")]
    [TestCase("input_user_interrupted")]
    public async Task AnActStoppedByThePersonsInputIsTriedAfterTheirPausesThenStopsWithThatCause(string code)
    {
        var harness = new Harness
        {
            Screen = _ => Window("Sin título - Bloc de notas", "Notepad", 31, true, [Control(0, "Document", "Editor de texto", "focused", "")]),
            Mind = _ => Step("input.text.type", new JsonObject { ["text"] = "hola" }),
            Receipt = (_, _) => new JsonObject { ["failWith"] = code },
        };
        var arguments = new JsonObject { ["goal"] = "escribir hola", ["application"] = "Bloc de notas" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el bloc de notas escribí hola", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Has.Count.EqualTo(1 + ComputerUseMission.PersonPauseRetries));
            Assert.That(harness.Acts.Select(act => act.Arguments["text"]?.ToJsonString()).Distinct(), Has.Exactly(1).Items);
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "a try after the pause is the same act, not a new decision");
            Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo(code));
        });
    }

    // Contracase: the person types without stopping. Each try waits for a pause that never comes (the clock runs); once
    // PersonPauseRetryMs has passed since the act began nothing more is tried and the cause is said. An act whose
    // first wait already took the whole ceiling is not tried again at all.
    [TestCase(3_000, 3)]
    [TestCase(8_000, 1)]
    public async Task APersonWhoNeverPausesGetsTheCauseOnceTheCeilingPassed(int waitPerTry, int acts)
    {
        var harness = new Harness
        {
            Screen = _ => Window("Sin título - Bloc de notas", "Notepad", 31, true, [Control(0, "Document", "Editor de texto", "focused", "")]),
            Mind = _ => Step("input.text.type", new JsonObject { ["text"] = "hola" }),
        };
        harness.Receipt = (_, _) =>
        {
            harness.Now += waitPerTry;
            return new JsonObject { ["failWith"] = "input_user_not_paused" };
        };
        var arguments = new JsonObject { ["goal"] = "escribir hola", ["application"] = "Bloc de notas" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el bloc de notas escribí hola", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Has.Count.EqualTo(acts));
            Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("input_user_not_paused"));
        });
    }

    // An act the person's input stopped before it pressed, tried after their pause, goes through: the mission goes on
    // as after any act, and nothing of the person's stop is said.
    [Test]
    public async Task AnActInterruptedBeforeItPressedGoesThroughAfterThePersonsPause()
    {
        var harness = new Harness
        {
            Screen = _ => Window("Sin título - Bloc de notas", "Notepad", 31, true, [Control(0, "Document", "Editor de texto", "focused", "")]),
        };
        harness.Mind = _ => harness.Acts.Count == 0 ? Step("input.text.type", new JsonObject { ["text"] = "hola" }) : null;
        harness.Receipt = (_, _) => harness.Acts.Count == 1
            ? new JsonObject { ["failWith"] = "input_user_interrupted" }
            : new JsonObject { ["surfaceChanged"] = true };
        var arguments = new JsonObject { ["goal"] = "escribir hola", ["application"] = "Bloc de notas" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el bloc de notas escribí hola", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Has.Count.EqualTo(2));
            Assert.That(harness.Acts[1].Arguments.ToJsonString(), Is.EqualTo(harness.Acts[0].Arguments.ToJsonString()));
            Assert.That((string?)observed["stoppedBy"], Is.Not.EqualTo("input_user_interrupted"));
            Assert.That((bool?)observed["steps"]![0]!["ok"], Is.True, "the step is the try that went through");
        });
    }

    // Banco r6 (s12, g1, n7, x10, y10, n5): a click pressed in the person's pause, whose post-read their typing cut
    // short (effect uncertain). Looked at again behind their window, the window shows the click's effect: the step is
    // verified by that look, the click is never pressed again, and the place is reached.
    [Test]
    public async Task AClickWhosePostReadThePersonCutShortIsVerifiedByTheLookAfterTheirPause()
    {
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = SteamCapture(clicked ? "library" : "store");
                view["window"]!["foreground"] = false;
                if (clicked)
                {
                    view["window"]!["title"] = "Steam - Biblioteca";
                }

                return view;
            },
            Mind = _ => clicked ? null : Step("input.visible.click", new JsonObject { ["label"] = "BIBLIOTECA" }),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["failWith"] = "input_user_interrupted", ["effectUncertain"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a biblioteca",
            ["application"] = "Steam",
            ["successCheck"] = GoToLibrary,
            ["budgetSteps"] = 3,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Steam andá a la biblioteca", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Has.Count.EqualTo(1), "an act that had its effect is not repeated");
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That((bool?)observed["steps"]![0]!["ok"], Is.True);
            Assert.That((string?)observed["steps"]![0]!["verifiedBy"], Is.EqualTo("look_after_person_pause"));
        });
    }

    // Contracase: looked at again, a window with an accessible tree (its controls' states read) still shows what the
    // click was decided on: the click did nothing, and it is pressed again after the person's pause.
    [Test]
    public async Task AClickWhoseWindowStillShowsTheSameAfterThePauseIsPressedAgain()
    {
        bool reached = false;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = SteamCapture(reached ? "library" : "store");
                view["window"]!["foreground"] = false;
                view["controls"] = new JsonArray(
                    Control(0, "Button", "TIENDA", reached ? "" : "selected"), Control(1, "Button", "BIBLIOTECA", reached ? "selected" : ""));
                if (reached)
                {
                    view["window"]!["title"] = "Steam - Biblioteca";
                }

                return view;
            },
        };
        harness.Mind = _ => harness.Acts.Count == 0 ? Step("input.visible.click", new JsonObject { ["label"] = "BIBLIOTECA" }) : null;
        harness.Receipt = (_, _) =>
        {
            if (harness.Acts.Count == 1)
            {
                return new JsonObject { ["failWith"] = "input_user_interrupted", ["effectUncertain"] = true };
            }

            reached = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a biblioteca",
            ["application"] = "Steam",
            ["successCheck"] = GoToLibrary,
            ["budgetSteps"] = 3,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Steam andá a la biblioteca", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Has.Count.EqualTo(2));
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.PersonEffectLookInterval),
                Is.GreaterThanOrEqualTo(ComputerUseMission.PersonEffectLooks), "looked at for the effect before pressing again");
            Assert.That((bool?)observed["reached"], Is.True);
        });
    }

    // Review of fable/cu-v3-reintento-pausa. Contracase: a window without an accessible tree reads only as its text,
    // which does not show what a press often changes alone (a toggle, a play button's icon): its text unchanged says
    // nothing of the click, which is not pressed again (it would undo it); the mission stops with the person's cause.
    [Test]
    public async Task AClickOnAWindowWithoutATreeWhoseTextStillShowsTheSameIsNotPressedAgain()
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = SteamCapture("store");
                view["window"]!["foreground"] = false;
                return view;
            },
        };
        harness.Mind = _ => harness.Acts.Count == 0 ? Step("input.visible.click", new JsonObject { ["label"] = "BIBLIOTECA" }) : null;
        harness.Receipt = (_, _) => new JsonObject { ["failWith"] = "input_user_interrupted", ["effectUncertain"] = true };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a biblioteca",
            ["application"] = "Steam",
            ["successCheck"] = GoToLibrary,
            ["budgetSteps"] = 3,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Steam andá a la biblioteca", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Has.Count.EqualTo(1));
            Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("input_user_interrupted"));
        });
    }

    // Review of fable/cu-v3-reintento-pausa. Contracase: a text whose typing the person's input cut short partway left
    // its first letters in the field. The field changed behind the person's window, but that is no proof of the text:
    // the step is not verified by a look nor typed again (the letters would repeat), the session does not count the
    // text as typed, and the mission stops with the person's cause.
    [Test]
    public async Task ATextCutShortPartwayIsNeitherVerifiedByALookNorTypedAgain()
    {
        var ledger = new ComputerUseTypedLedger();
        bool cut = false;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Window("Sin título - Bloc de notas", "Notepad", 31, true,
                    [Control(0, "Document", "Editor de texto", "focused", cut ? "ho" : ""), Control(1, "Button", "Cerrar")]);
                view["window"]!["foreground"] = false;
                return view;
            },
            Mind = _ => cut ? null : Step("input.text.type", new JsonObject { ["text"] = "hola" }),
        };
        harness.Receipt = (_, _) =>
        {
            cut = true;
            return new JsonObject { ["failWith"] = "input_user_interrupted", ["effectUncertain"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "escribir hola", ["application"] = "Bloc de notas" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root, typed: ledger), Execution("en el bloc de notas escribí hola", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Has.Count.EqualTo(1), "the letters already typed are not typed again");
            Assert.That((bool?)observed["steps"]![0]!["ok"], Is.Not.True);
            Assert.That((string?)observed["steps"]![0]!["verifiedBy"], Is.Null);
            Assert.That(ledger.Texts, Is.Empty, "a text typed in part is not counted as typed");
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("input_user_interrupted"));
        });
    }

    // Contracase: the window changed, but it holds the front (the person's keys could have gone into it): the change
    // proves nothing of the click, it is not pressed again, and the mission stops with the person's cause.
    [Test]
    public async Task AClickWhoseWindowChangedInFrontIsNeitherVerifiedNorPressedAgain()
    {
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = SteamCapture(clicked ? "library" : "store");
                view["window"]!["foreground"] = clicked;
                return view;
            },
            Mind = _ => clicked ? null : Step("input.visible.click", new JsonObject { ["label"] = "BIBLIOTECA" }),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["failWith"] = "input_user_interrupted", ["effectUncertain"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a biblioteca",
            ["application"] = "Steam",
            ["successCheck"] = GoToLibrary,
            ["budgetSteps"] = 3,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Steam andá a la biblioteca", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Has.Count.EqualTo(1));
            Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("input_user_interrupted"));
        });
    }

    // Contracase: any other failed act (a label not found) is not the person's doing; the mission asks for another step.
    [Test]
    public async Task AnActThatFailedForAnotherReasonDoesNotStopTheMissionAtOnce()
    {
        var harness = new Harness
        {
            Screen = _ => Window("Sin título - Bloc de notas", "Notepad", 31, true, [Control(0, "Document", "Editor de texto", "focused", "")]),
            Receipt = (_, _) => new JsonObject { ["failWith"] = "visible_button_not_found" },
        };
        harness.Mind = _ => harness.Acts.Count == 0 ? Step("input.text.type", new JsonObject { ["text"] = "hola" }) : null;
        var arguments = new JsonObject { ["goal"] = "escribir hola", ["application"] = "Bloc de notas" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el bloc de notas escribí hola", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests, Has.Count.GreaterThan(1));
            Assert.That((string?)Observed(result)["stoppedBy"], Is.Not.EqualTo("visible_button_not_found"));
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

    // v3 punto 5 (live 2026-10-07 v2-s12, v2-c17): Steam already on its library replayed a click on «BIBLIOTECA»,
    // which only opened its menu, and the mission ended «Parece que ya estabas…». The first look now reads the row of
    // navigation labels: the library marked, the sub-goal is reached with no step.
    private const string GoToLibrary =
        "control:biblioteca:current|title:biblioteca|page:biblioteca|control:library:current|title:library|page:library|mark:biblioteca|mark:library";

    private static JsonObject SteamCapture(string name, string? coveredBy = null)
    {
        JsonObject view = ComputerUseMarkTests.Capture(name, coveredBy);
        view["window"]!["processId"] = 12;
        view["window"]!["requested"] = true;
        return view;
    }

    // Banco r23b x10: the launcher opened behind the person's window (window.coveredBy) is read from its own drawing (v3
    // point 0), so its marked row tells the place as on an uncovered window: never «No pude llegar a Biblioteca».
    [TestCase(null)]
    [TestCase("Spotify Premium")]
    public async Task AWindowAlreadyOnThePlaceItsRowMarksIsReachedOnItsFirstLookWithNoStep(string? coveredBy)
    {
        var harness = new Harness
        {
            Screen = _ => SteamCapture("library", coveredBy),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "BIBLIOTECA" }),
        };
        var arguments = new JsonObject { ["goal"] = "ir a biblioteca", ["application"] = "Steam", ["successCheck"] = GoToLibrary };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Steam andá a la biblioteca", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That((string?)observed["satisfiedBy"], Is.EqualTo("mark:biblioteca"));
            Assert.That((int?)observed["stepCount"], Is.Zero);
            Assert.That(harness.Acts, Is.Empty, "no click over the place already shown");
            Assert.That(harness.Requests, Is.Empty, "no model");
            // The marked label is the item chosen in the window's navigation, as the window writes it: the final
            // «Ya estás en «Biblioteca».» is told from it (tests/data/cu_floor_twins.json, cu-reached-already-there).
            Assert.That(observed["screen"]!["values"]![0]!.ToJsonString(), Is.EqualTo("""{"name":"BIBLIOTECA","state":"selected"}"""));
            Assert.That(OperationFloor.Final(new JsonObject
            {
                ["kind"] = "operation",
                ["operation"] = "mission.computer.use",
                ["polarity"] = "success",
                ["verified"] = true,
                ["succeeded"] = true,
                ["observed"] = observed.DeepClone(),
            }, english: false), Is.EqualTo("Ya estás en «Biblioteca»."));
        });
    }

    // r30 (bancos Br28 y Bb3tb: e3, n4, s04, «ir a stopwatch» closed on control:cronometro:current and the model worded
    // the final): a mission of one goal carries, as a chain's parts do, how the window wrote what its term read, and
    // the final names that from the facts, not the person's word for it.
    [Test]
    public async Task R30AMissionOfOneGoalTellsItsPlaceAsTheWindowWroteIt()
    {
        var harness = new Harness { Screen = _ => SteamCapture("library"), Mind = _ => null };
        var arguments = new JsonObject { ["goal"] = "ir a library", ["application"] = "Steam", ["successCheck"] = GoToLibrary };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("in Steam go to the library", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        JsonObject Situation(JsonObject seen) => new()
        {
            ["kind"] = "operation",
            ["operation"] = "mission.computer.use",
            ["polarity"] = "success",
            ["verified"] = true,
            ["succeeded"] = true,
            ["observed"] = seen,
        };
        var unread = (JsonObject)observed.DeepClone();
        unread.Remove("arrivedAs");
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That((string?)observed["satisfiedBy"], Is.EqualTo("mark:biblioteca"));
            Assert.That((string?)observed["arrivedAs"], Is.EqualTo("BIBLIOTECA"));
            Assert.That(OperationFloor.Final(Situation((JsonObject)observed.DeepClone()), english: true),
                Is.EqualTo("You're already in «Biblioteca»."));
            // Contracase: without what the term read, only the person's word is left.
            Assert.That(OperationFloor.Final(Situation(unread), english: true), Is.EqualTo("You're already in «library»."));
        });
    }

    // r30 (bancos Br28 y Bb3tb: 213 ms from arguments.end to computer_use.start in the first mission of a process, 54 in
    // the next ones): the start-up pays the mission path's first use. It takes no context, so it can dispatch, look at,
    // journal or keep nothing; what it warms is the real path: arguments the catalog's schema accepts and the loop's
    // own asynchronous methods (a compiler that named them otherwise would leave it warming nothing).
    [Test]
    public async Task R30TheStartUpPaysTheMissionPathsFirstUseAndDispatchesNothing()
    {
        await ComputerUseMission.WarmAsync();

        var arguments = new JsonObject { ["goal"] = UserMessagePhrases.ReadersWarmupRequest };
        string[] loops = [.. typeof(ComputerUseMission).GetNestedTypes(System.Reflection.BindingFlags.NonPublic)
            .Where(type => typeof(System.Runtime.CompilerServices.IAsyncStateMachine).IsAssignableFrom(type)
                && type.GetMethod("MoveNext", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic) is not null)
            .Select(type => type.Name)];
        Assert.Multiple(() =>
        {
            Assert.That(MindPlanBoundary.ArgumentsSatisfyExactSchema(ComputerUseMission.OperationName, arguments), Is.True);
            Assert.That(loops, Has.Some.Contains(nameof(ComputerUseMission.RunAsync)));
        });
    }

    [Test]
    public async Task AnotherApplicationsWindowInFrontIsNeverThePlaceReached()
    {
        // Review 2026-10-07: «abre Epic Games y andá a la biblioteca» with Epic closed. The adapter reads the window in
        // front (requested=false): Steam on its library, «BIBLIOTECA» blue. Never reached there, never «Ya estás en».
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = ComputerUseMarkTests.Capture("library", requested: false);
                view["window"]!["processId"] = 12;
                return view;
            },
            Mind = _ => null,
        };
        var arguments = new JsonObject { ["goal"] = "ir a biblioteca", ["application"] = "Epic Games", ["successCheck"] = GoToLibrary };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abre Epic Games y andá a la biblioteca", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That((string?)observed["satisfiedBy"], Is.Null);
            Assert.That(OperationFloor.Final(new JsonObject
            {
                ["kind"] = "operation",
                ["operation"] = "mission.computer.use",
                ["polarity"] = "failure",
                ["verified"] = true,
                ["succeeded"] = false,
                ["observed"] = observed.DeepClone(),
            }, english: false) ?? string.Empty, Does.Not.StartWith("Ya estás en"));
        });
    }

    [Test]
    public async Task APlaceReachedAfterAPressWhosePostReadDidNotHoldIsNeverAlreadyThere()
    {
        // Review 2026-10-07: Steam on its store, the click on «BIBLIOTECA» pressed but the slow page changed after the
        // verification window (visible_click_postread_invalid, effect may have occurred). The next look is the
        // library: BAXY navigated there, so the final is the place reached, never «Ya estás en», and the label it
        // pressed is not judged by its ink (mark:).
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = SteamCapture(clicked ? "library" : "store");
                if (clicked)
                {
                    view["window"]!["title"] = "Steam - Biblioteca";
                }

                return view;
            },
            Mind = _ => clicked ? null : Step("input.visible.click", new JsonObject { ["label"] = "BIBLIOTECA" }),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["failWith"] = "visible_click_postread_invalid", ["effectUncertain"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a biblioteca",
            ["application"] = "Steam",
            ["successCheck"] = GoToLibrary,
            ["budgetSteps"] = 3,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Steam andá a la biblioteca", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That((string?)observed["satisfiedBy"], Is.EqualTo("title:biblioteca"));
            Assert.That((bool?)observed["steps"]![0]!["effectUncertain"], Is.True);
            Assert.That(ComputerUseSuccessCheck.Atom("mark:biblioteca", SteamCapture("library"), (JsonArray)observed["steps"]!), Is.False,
                "the label it pressed");
            Assert.That(OperationFloor.Final(new JsonObject
            {
                ["kind"] = "operation",
                ["operation"] = "mission.computer.use",
                ["polarity"] = "success",
                ["verified"] = true,
                ["succeeded"] = true,
                ["observed"] = observed.DeepClone(),
            }, english: false), Is.EqualTo("Listo, estoy en «Biblioteca»."));
        });
    }

    [Test]
    public async Task OnAnotherPageAClickOnThePlacesLabelThatOnlyOpensItsMenuNeverPasses()
    {
        // Contracase: Steam on its store; the click on «BIBLIOTECA» only opens its menu under it and the row still
        // marks «TIENDA». Never reached, and never «parece que ya estabas».
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = SteamCapture("store");
                if (clicked)
                {
                    ((JsonArray)view["text"]!["TL"]!).Add("Página principal");
                }

                return view;
            },
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "BIBLIOTECA" }),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["surfaceChanged"] = true, ["name"] = "BIBLIOTECA", ["cascadeStage"] = "ocr" };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a biblioteca",
            ["application"] = "Steam",
            ["successCheck"] = GoToLibrary,
            ["budgetSteps"] = 3,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Steam andá a la biblioteca", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That(harness.Acts, Is.Not.Empty);
            Assert.That((string?)observed["stoppedBy"], Is.Not.EqualTo("computer_use_already_there_unconfirmed"));
        });
    }

    // ------------------------------------------------------ translated labels (§4.4.1)

    private static MindComputerUseStep TranslatedClick(string label, int index, string from, params string[] names) => new(
        "input.visible.click", new JsonObject { ["label"] = label, ["index"] = index }, string.Empty, string.Empty,
        new JsonObject { ["from"] = from, ["to"] = label },
        new JsonObject
        {
            ["label"] = from,
            ["names"] = new JsonArray([.. names.Select(name => (JsonNode?)JsonValue.Create(name))]),
            ["source"] = "model",
        });

    [Test]
    public async Task AClickOnATranslationTheViewShowsExtendsTheCheckAndIsKeptForTheNextRequest()
    {
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ => Window("Configuración", "SystemSettings", 40, true,
                [Control(0, "ListItem", "Hora e idioma", "selected"),
                 Control(1, "Button", "Fecha y hora", clicked ? "selected" : ""),
                 Control(2, "Button", "Idioma y región")]),
            Mind = _ => TranslatedClick("Fecha y hora", 1, "date and time", "Fecha y hora", "Date & time"),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["selected"] = true };
        };
        var translations = new ComputerUseLabelTranslations(Path.Combine(_root, "label-translations.v1.json"));
        var arguments = new JsonObject
        {
            ["goal"] = "ir a date and time",
            ["application"] = "Configuración",
            ["successCheck"] = "control:date and time:selected|title:date and time",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root, translations: translations), Execution("in Settings go to date and time", arguments),
            arguments, CancellationToken.None);

        // The next mission's request carries this label's entry and nothing else.
        var reloaded = new ComputerUseLabelTranslations(Path.Combine(_root, "label-translations.v1.json"));
        reloaded.Rejected("night light", ["Luz nocturna"]);
        JsonObject? entry = reloaded.EntryFor("ir a date and time");
        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.True);
            Assert.That((string?)Observed(result)["satisfiedBy"], Is.EqualTo("control:==Fecha y hora:selected"));
            Assert.That(harness.Requests[0].LabelTranslations, Is.Null, "nothing learned yet");
            JsonObject stored = reloaded.Find("date and time")!;
            Assert.That((string?)stored["names"]![0], Is.EqualTo("Fecha y hora"));
            Assert.That((int?)stored["seenOnScreen"], Is.EqualTo(1));
            Assert.That(entry!.Select(pair => pair.Key), Is.EqualTo(new[] { "date and time" }));
            Assert.That(entry!["date and time"]!.AsObject().Select(pair => pair.Key), Is.EqualTo(new[] { "names" }));
            Assert.That(reloaded.EntryFor("ir a la hora"), Is.Null, "a label the goal does not name whole is not sent");
        });
    }

    [Test]
    public async Task AnAliasTheViewDoesNotShowExtendsNothingAndCountsARejection()
    {
        bool clicked = false;
        int asked = 0;
        var harness = new Harness
        {
            // «Fecha y hora» is not on screen when the mind claims it; a page of that name would appear after.
            Screen = _ => Window("Configuración", "SystemSettings", 40, true, clicked
                ? [Control(0, "Button", "Fecha y hora", "selected")]
                : [Control(0, "ListItem", "Hora e idioma", "selected"), Control(1, "Button", "Idioma y región")]),
            Mind = _ => ++asked == 1
                ? TranslatedClick("Fecha y hora", 1, "date and time", "Fecha y hora")
                : Step("none", new JsonObject()),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["failWith"] = "visible_button_not_found" };
        };
        var translations = new ComputerUseLabelTranslations(Path.Combine(_root, "label-translations.v1.json"));
        var arguments = new JsonObject
        {
            ["goal"] = "ir a date and time",
            ["application"] = "Configuración",
            ["successCheck"] = "control:date and time:selected",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root, translations: translations), Execution("in Settings go to date and time", arguments),
            arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.False, "the planned check never holds on an unvalidated alias");
            // Its name did appear after the click, so the translation is not rejected; nor is it learned: the
            // sub-goal never got there through it.
            Assert.That(translations.Find("date and time"), Is.Null);
        });
    }

    [Test]
    public void ThreeRejectionsInARowForgetATranslationAndASightingResetsThem()
    {
        var translations = new ComputerUseLabelTranslations(Path.Combine(_root, "label-translations.v1.json"));
        translations.Rejected("crop", ["Recortar"]);
        translations.Rejected("crop", ["Recortar"]);
        translations.Seen("crop", ["Recortar"], "Recortar");
        translations.Rejected("crop", ["Recortar"]);
        translations.Rejected("crop", ["Recortar"]);
        int? beforeTheThird = (int?)translations.Find("crop")?["rejected"];
        translations.Rejected("crop", ["Recortar"]);

        Assert.Multiple(() =>
        {
            Assert.That(beforeTheThird, Is.EqualTo(2));
            Assert.That(translations.Find("crop"), Is.Null);
            Assert.That(new ComputerUseLabelTranslations(Path.Combine(_root, "label-translations.v1.json")).Find("crop"), Is.Null);
        });
    }

    [Test]
    public void AnAliasRenamesOnlyTheAtomsThatNameThePlaceWhole()
    {
        var steps = new JsonArray
        {
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Recortar", ["ok"] = true },
        };
        var aliases = new JsonObject { ["crop"] = new JsonArray("Recortar") };
        var view = Window("Configuración", "SystemSettings", 40, true, [Control(0, "Button", "Date & time", "selected")]);
        var dateAliases = new JsonObject { ["fecha y hora"] = new JsonArray("Date & time") };

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:crop", steps, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:crop", steps, out string? by, aliases), Is.True);
            Assert.That(by, Is.EqualTo("stepDone:input.visible.click:==Recortar"));
            // A key named like the place is no click on it; a longer name holding it is not renamed.
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.key.press:crop", steps, out _, aliases), Is.False);
            Assert.That(ComputerUseSuccessCheck.WithAliases(["control:crop tool:selected"], aliases).Count(), Is.EqualTo(1));
            // A translation with «&» (a separator of the check's text) is matched atom by atom, never re-parsed.
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:fecha y hora:selected", view, [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:fecha y hora:selected", view, [], out string? dated, dateAliases), Is.True);
            Assert.That(dated, Is.EqualTo("control:==Date & time:selected"));
        });
    }

    private static JsonObject DateAndTime() => new()
    {
        ["goal"] = "ir a date and time",
        ["application"] = "Configuración",
        ["successCheck"] = "control:date and time:selected",
    };

    [Test]
    public async Task AnAliasClickedThatDoesNotGetThereIsNeverLearnedAsSeen()
    {
        // The alias is on screen and the click works, but the place it opens is not the one asked (it never shows
        // selected): the cache must not learn it, the rejection counts once, and the alias stops extending the check.
        int asked = 0;
        var harness = new Harness
        {
            Screen = _ => Window("Configuración", "SystemSettings", 40, true,
                [Control(0, "ListItem", "Hora e idioma", "selected"), Control(1, "Button", "Fecha y hora"),
                 Control(2, "Button", "Idioma y región")]),
            Mind = _ => ++asked == 1
                ? TranslatedClick("Fecha y hora", 1, "date and time", "Fecha y hora")
                : Step("none", new JsonObject()),
        };
        var translations = new ComputerUseLabelTranslations(Path.Combine(_root, "label-translations.v1.json"));
        JsonObject arguments = DateAndTime();
        var execution = Execution("in Settings go to date and time", arguments);

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root, translations: translations), execution, arguments, CancellationToken.None);

        JsonObject? stored = new ComputerUseLabelTranslations(Path.Combine(_root, "label-translations.v1.json")).Find("date and time");
        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.False);
            Assert.That(harness.Acts.Count(act => act.Operation == "input.visible.click"), Is.EqualTo(1));
            Assert.That((int?)stored!["seenOnScreen"], Is.EqualTo(0), "a click alone proves nothing");
            Assert.That((int?)stored!["rejected"], Is.EqualTo(1));
            Assert.That(stored!["onScreen"], Is.Null);
            Assert.That(translations.ConfirmedFor("ir a date and time"), Is.Null);
        });
    }

    [Test]
    public async Task AMissionReachedThroughAnAliasStillReachesTheSecondTimeThroughTheArmedAlias()
    {
        string cache = Path.Combine(_root, "label-translations.v1.json");

        async Task<(JsonObject Observed, Harness Harness)> RunOnceAsync(Func<ComputerUseStepRequest, MindComputerUseStep?> mind)
        {
            bool clicked = false;
            var harness = new Harness
            {
                Screen = _ => Window("Configuración", "SystemSettings", 40, true,
                    [Control(0, "ListItem", "Hora e idioma", "selected"),
                     Control(1, "Button", "Fecha y hora", clicked ? "selected" : ""),
                     Control(2, "Button", "Idioma y región")]),
                Mind = mind,
            };
            harness.Receipt = (_, _) =>
            {
                clicked = true;
                return new JsonObject { ["selected"] = true };
            };
            JsonObject arguments = DateAndTime();
            ComputerUseMission.Result run = await ComputerUseMission.RunAsync(
                harness.Context(_root, new ComputerUseLabelTranslations(cache)),
                Execution("in Settings go to date and time", arguments), arguments, CancellationToken.None);
            return (Observed(run), harness);
        }

        (JsonObject first, _) = await RunOnceAsync(_ => TranslatedClick("Fecha y hora", 1, "date and time", "Fecha y hora"));
        // The second time the mind clicks the shown name without translating it: the check still holds through the
        // alias the first mission reached by, armed from the cache when the sub-goal starts.
        (JsonObject second, Harness again) = await RunOnceAsync(_ => Step("input.visible.click", new JsonObject { ["label"] = "Fecha y hora" }));

        Assert.Multiple(() =>
        {
            Assert.That((bool?)first["reached"], Is.True);
            Assert.That((bool?)second["reached"], Is.True, "the click on the alias still reaches the place said");
            Assert.That((string?)second["satisfiedBy"], Is.EqualTo("control:==Fecha y hora:selected"));
            Assert.That(again.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "input.visible.click" }));
            Assert.That((int?)new ComputerUseLabelTranslations(cache).Find("date and time")!["seenOnScreen"], Is.EqualTo(2));
        });
    }

    [Test]
    public async Task StepsBeforeThePlaceAppearsNeitherRejectNorForgetItsTranslation()
    {
        // The place shows only at the fourth look (a search first): every step before reports the translation, none
        // of its names is on screen yet, and that is no rejection. The model is asked once: later requests carry the
        // names this mission already has.
        int asked = 0;
        var translation = new JsonObject
        {
            ["label"] = "date and time",
            ["names"] = new JsonArray("Fecha y hora"),
            ["source"] = "model",
        };
        var harness = new Harness
        {
            Screen = _ => Window("Configuración", "SystemSettings", 40, true, asked >= 3
                ? [Control(0, "ListItem", "Hora e idioma", "selected"), Control(1, "Button", "Fecha y hora", asked >= 4 ? "selected" : "")]
                : [Control(0, "Edit", "Buscar una configuración"), Control(1, "ListItem", "Sistema", "selected"),
                   Control(2, "Text", "Resultados " + asked)]),
            Mind = _ => ++asked < 4
                ? new MindComputerUseStep("input.key.press", new JsonObject { ["key"] = "tab" }, string.Empty, string.Empty, null,
                    translation.DeepClone().AsObject())
                : TranslatedClick("Fecha y hora", 1, "date and time", "Fecha y hora"),
        };
        var translations = new ComputerUseLabelTranslations(Path.Combine(_root, "label-translations.v1.json"));
        JsonObject arguments = DateAndTime();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root, translations: translations), Execution("in Settings go to date and time", arguments),
            arguments, CancellationToken.None);

        JsonObject? stored = new ComputerUseLabelTranslations(Path.Combine(_root, "label-translations.v1.json")).Find("date and time");
        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.True);
            Assert.That(harness.Requests, Has.Count.EqualTo(4));
            Assert.That(harness.Requests[0].LabelTranslations, Is.Null);
            Assert.That(harness.Requests.Skip(1).All(request =>
                (string?)request.LabelTranslations?["date and time"]?["names"]?[0] == "Fecha y hora"), Is.True,
                "the names looked up at the first step travel with the next ones");
            Assert.That((int?)stored!["seenOnScreen"], Is.EqualTo(1));
            Assert.That((int?)stored!["rejected"], Is.EqualTo(0));
        });
    }

    [Test]
    public async Task ATranslationNoLookShowsCountsOneRejectionPerMission()
    {
        var translation = new JsonObject
        {
            ["label"] = "date and time",
            ["names"] = new JsonArray("Fecha y hora"),
            ["source"] = "model",
        };
        var harness = new Harness
        {
            Screen = _ => Window("Configuración", "SystemSettings", 40, true,
                [Control(0, "Edit", "Buscar una configuración"), Control(1, "ListItem", "Sistema", "selected")]),
            Mind = _ => new MindComputerUseStep("input.key.press", new JsonObject { ["key"] = "tab" }, string.Empty, string.Empty,
                null, translation.DeepClone().AsObject()),
        };
        harness.Receipt = (_, _) => new JsonObject { ["surfaceChanged"] = true };
        var translations = new ComputerUseLabelTranslations(Path.Combine(_root, "label-translations.v1.json"));
        JsonObject arguments = DateAndTime();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root, translations: translations), Execution("in Settings go to date and time", arguments),
            arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.False);
            Assert.That(harness.Requests, Has.Count.GreaterThanOrEqualTo(2));
            Assert.That((int?)translations.Find("date and time")!["rejected"], Is.EqualTo(1), "one mission, one rejection");
        });
    }

    [Test]
    public void AnAliasNamesTheControlWholeNeverALongerOneThatHoldsIt()
    {
        var aliases = new JsonObject { ["data"] = new JsonArray("Datos") };
        var longer = Window("Configuración", "SystemSettings", 40, true, [Control(0, "Button", "Uso de datos", "selected")]);
        var exact = Window("Libro1 - Excel", "EXCEL", 41, true, [Control(0, "TabItem", "Datos", "selected")]);
        var clickedLonger = new JsonArray
        {
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Uso de datos", ["ok"] = true },
        };

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:data:selected", longer, [], out _, aliases), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:data:selected", exact, [], out string? by, aliases), Is.True);
            Assert.That(by, Is.EqualTo("control:==Datos:selected"));
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:data", clickedLonger, out _, aliases), Is.False);
            // The planned atoms keep their meaning: «control:=datos» still finds «Uso de datos» as a whole word.
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=datos:selected", longer, [], out _), Is.True);
        });
    }

    // ------------------------------------------------------- falsos éxitos v3 M1: the model's «done» in a goal of doing

    private static async Task<(JsonObject Observed, ComputerUseMission.Result Result)> RunDone(
        Harness harness, string goal, string application, string root, ComputerUseTypedLedger? typed = null)
    {
        var arguments = new JsonObject { ["goal"] = goal, ["application"] = application };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(root, typed: typed), Execution(goal, arguments), arguments, CancellationToken.None);
        return (Observed(result), result);
    }

    // Pasada r15b (t-drag-4): choosing a tool shown chosen already («Línea» on) is told as it was. Estabilización L: a
    // goal of drawing never reaches the loop (a declared limit, ComputerUseLoopTests.EstabL), so its «no_drag» refusal
    // of an «already» done went with the drag.
    [TestCase("elegí la herramienta Línea", true)]
    public async Task AToolAlreadyChosenIsToldAsItWas(string goal, bool reached)
    {
        var harness = new Harness
        {
            Screen = _ => Window("Sin título - Paint", "mspaint", 41, true, [Control(0, "Button", "Línea", "on"), Control(1, "Button", "Lápiz", "off")]),
            Mind = _ => Step("done", new JsonObject { ["evidence"] = "Línea", ["already"] = true }),
        };

        (JsonObject observed, _) = await RunDone(harness, goal, "Paint", _root);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"] == true, Is.EqualTo(reached));
            if (!reached)
            {
                Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_seen_not_done"));
            }
        });
    }

    // Twin of v3-17 (turn 2, «recórtala en proporción cuadrada»): the plan had no check and the model said done on the
    // first look, citing the gallery; the final said «Listo, lo hice en «Fotos»». Nothing was done. Estabilización R16:
    // that done is refused by the mind's judge (cu_validate._checked_act: tests/test_computer_use.py
    // test_a_done_with_no_act_in_a_goal_of_doing_is_refused); the App's twin of it went. What the App owes that judge
    // is its inputs: the application's first look and a history with no step.
    [Test]
    public async Task TheMindsJudgeOfADoneWithNoActGetsTheFirstLookAndNoStep()
    {
        var harness = new Harness
        {
            Screen = _ => Window("Fotos", "Photos", 40, true, [Control(0, "ListItem", "Galería"), Control(1, "Edit", "Buscar en la galería")]),
            Mind = _ => Step("done", new JsonObject { ["evidence"] = "Galería" }),
        };

        await RunDone(harness, "recortar la imagen en proporción cuadrada", "Fotos", _root);

        Assert.Multiple(() =>
        {
            Assert.That((string?)harness.Requests[0].View["firstLook"], Does.StartWith("fotos\n").And.Contain("galeria"));
            Assert.That(harness.Requests[0].History, Is.Empty);
            Assert.That(harness.Acts, Is.Empty);
        });
    }

    // Twin of v3-40 (turn 3, «renombra la tab a pruebas»): a click and a text, then done citing the prompt the
    // terminal showed before any of it. What the first look showed proves no act. Estabilización R16: the mind's judge
    // refuses it (cu_first_look, «seen_at_start»: tests/test_cu_estab_r16_juez_unico.py); the App hands it the
    // sub-goal's first look, kept from before the acts.
    [Test]
    public async Task TheMindsJudgeGetsTheFirstLookFromBeforeTheActs()
    {
        int acts = 0;
        var harness = new Harness
        {
            Screen = _ => acts == 0
                ? Window("Windows PowerShell", "WindowsTerminal", 41, true,
                    new JsonArray { Control(0, "TabItem", "Windows PowerShell", "selected") }, @"PS C:\Users\usuario>")
                : Window("Windows PowerShell", "WindowsTerminal", 41, true,
                    new JsonArray { Control(0, "TabItem", "Windows PowerShell", "selected"), Control(1, "MenuItem", "Cambiar nombre de pestaña") },
                    acts < 2 ? @"PS C:\Users\usuario>" : @"PS C:\Users\usuario> pruebas", acts < 2 ? string.Empty : "pruebas"),
        };
        harness.Receipt = (_, _) =>
        {
            acts++;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        harness.Mind = request => request.History.Count switch
        {
            0 => Step("input.visible.click", new JsonObject { ["label"] = "Windows PowerShell" }),
            1 => Step("input.text.type", new JsonObject { ["text"] = "pruebas" }),
            _ => Step("done", new JsonObject { ["evidence"] = @"PS C:\Users\usuario>" }),
        };

        await RunDone(harness, "renombrar la pestaña a pruebas", "Terminal", _root);

        string? firstLook = (string?)harness.Requests[^1].View["firstLook"];
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Has.Count.EqualTo(2));
            Assert.That(harness.Requests[^1].History, Has.Count.EqualTo(2));
            Assert.That(firstLook, Does.Contain(@"ps c:\users\usuario>"));
            Assert.That(firstLook, Does.Not.Contain("pruebas"), "the first look is the one before the acts");
        });
    }

    // Twin of v3-35 (turn 3, «ahora ponla de color morado»): «morado» typed, then done citing «Hoy hace moradosu», the
    // typed text glued to another word. A text BAXY typed proves no act where only the written text shows it.
    // Estabilización R16: the mind's judge refuses it (tests/test_computer_use.py
    // test_a_done_citing_the_typed_text_glued_to_another_word_is_refused); the App hands it the text typed, as no query.
    [Test]
    public async Task TheMindsJudgeGetsTheTextTypedIntoTheNote()
    {
        bool typed = false;
        JsonObject Notes(string text)
        {
            JsonObject view = Window("Notas", "Notes", 42, true, [Control(0, "Document", "Nota", value: text)], text);
            // The keyboard is in the note itself (a named field, not a search): its text is no query's echo.
            view["window"]!["focused"] = new JsonObject { ["kind"] = "Document", ["name"] = "Nota" };
            return view;
        }

        var harness = new Harness { Screen = _ => typed ? Notes("Hoy hace moradosu") : Notes("Hoy hace su") };
        harness.Mind = request => request.History.Count == 0
            ? Step("input.text.type", new JsonObject { ["text"] = "morado" })
            : Step("done", new JsonObject { ["evidence"] = "Hoy hace moradosu" });
        harness.Receipt = (operation, _) =>
        {
            typed |= operation == "input.text.type";
            return new JsonObject { ["surfaceChanged"] = true };
        };

        await RunDone(harness, "poner la nota de color morado", "Notas", _root);

        JsonArray history = harness.Requests[^1].History;
        Assert.Multiple(() =>
        {
            Assert.That((string?)history[0]!["operation"], Is.EqualTo("input.text.type"));
            Assert.That((string?)history[0]!["text"], Is.EqualTo("morado"));
            Assert.That(history[0]!["query"], Is.Null, "the note is no box that only searches");
        });
    }

    // Twin of v3-17 (turn 3, «guárdala como copia»): the gallery's search box still held the name typed a turn before,
    // and the done cited it. What BAXY typed this session proves no later act (the mind's judge, given the session's
    // ledger: estabilización R16, the App's twin went); the same screen without that typing in the ledger is a new line
    // the act brought, and reaches.
    [Test]
    public async Task TheMindsJudgeGetsWhatAnEarlierTurnTyped()
    {
        const string Typed = "imagen prueba.png de la carpeta baxy-prueba-v3";
        async Task<(JsonObject Observed, JsonObject LastView)> Run(ComputerUseTypedLedger ledger)
        {
            bool clicked = false;
            var harness = new Harness
            {
                Screen = _ => clicked
                    ? Window("Fotos", "Photos", 43, true, [Control(0, "Button", "Guardar como")], Typed)
                    : Window("Fotos", "Photos", 43, true, [Control(0, "Button", "Guardar como")]),
            };
            harness.Mind = request => request.History.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Guardar como" })
                : Step("done", new JsonObject { ["evidence"] = Typed });
            harness.Receipt = (_, _) =>
            {
                clicked = true;
                return new JsonObject { ["surfaceChanged"] = true };
            };
            (JsonObject observed, _) = await RunDone(harness, "guardar la imagen como copia en esa misma carpeta", "Fotos", _root, ledger);
            return (observed, harness.Requests[^1].View);
        }

        var earlier = new ComputerUseTypedLedger();
        earlier.Add(Typed);
        (_, JsonObject told) = await Run(earlier);
        (JsonObject counter, JsonObject untold) = await Run(new ComputerUseTypedLedger());

        Assert.Multiple(() =>
        {
            Assert.That(told["typedInSession"]!.AsArray().Select(text => (string?)text), Does.Contain(Typed));
            Assert.That(untold["typedInSession"], Is.Null);
            Assert.That((bool?)counter["reached"], Is.True);
            Assert.That((string?)counter["satisfiedBy"], Is.EqualTo("model_evidence"));
        });
    }

    // Counter-cases of the judge: a click that opens the dialog the button named (its title is new), a reading that
    // cites a value already shown, and a mission that types a text into a field so the ledger keeps it.
    [Test]
    public async Task ADoneAfterAnActCitingWhatItBroughtStillReaches()
    {
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ => clicked
                ? Window("Imprimir", "Notepad", 44, true, [Control(0, "Button", "Aceptar")])
                : Window("Sin título - Bloc de notas", "Notepad", 44, true, [Control(0, "MenuItem", "Imprimir")]),
        };
        harness.Mind = request => request.History.Count == 0
            ? Step("input.visible.click", new JsonObject { ["label"] = "Imprimir" })
            : Step("done", new JsonObject { ["evidence"] = "Imprimir" });
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        (JsonObject opened, _) = await RunDone(harness, "abrir el dialogo de imprimir", "Bloc de notas", _root);

        var reading = new Harness
        {
            Screen = _ => Window("Configuración", "SystemSettings", 45, true, [Control(0, "Text", "Versión 24H2")]),
            Mind = _ => Step("done", new JsonObject { ["evidence"] = "Versión 24H2" }),
        };
        (JsonObject read, _) = await RunDone(reading, "leer la version de Windows", "Configuración", _root);

        var ledger = new ComputerUseTypedLedger();
        bool typed = false;
        var writing = new Harness
        {
            Screen = _ => Window("Sin título - Bloc de notas", "Notepad", 46, true, [Control(0, "Document", "Texto", value: typed ? "hola" : "")]),
            Mind = request => Step("input.text.type", new JsonObject { ["text"] = "hola" }),
        };
        writing.Receipt = (_, _) =>
        {
            typed = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "escribir hola", ["application"] = "Bloc de notas", ["successCheck"] = "stepDone:input.text.type" };
        ComputerUseMission.Result wrote = await ComputerUseMission.RunAsync(
            writing.Context(_root, typed: ledger), Execution("escribí hola", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)opened["reached"], Is.True, "the dialog's title is new");
            Assert.That((bool?)read["reached"], Is.True, "a reading cites what shows");
            Assert.That((bool?)Observed(wrote)["reached"], Is.True, "a text arrives by its own check, not by the model's evidence");
            Assert.That(ledger.Texts, Is.EqualTo(new[] { "hola" }));
        });
    }

    // Review of falsos éxitos v3 M1: the first look a citation is judged against is the application's own, taken as the
    // page baseline is, never the window in front read before app.open (here an editor with its own «Recortar»). The
    // click on «Editar» brought «Recortar» into the application: done.
    [Test]
    public async Task TheFirstLookJudgedIsTheApplicationsOwnNotTheWindowInFrontBeforeOpening()
    {
        int stage = 0;
        var harness = new Harness
        {
            Screen = _ => stage switch
            {
                0 => Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Button", "Recortar"), Control(1, "Document", "Texto")]),
                1 => Window("Fotos", "Photos", 48, true, [Control(0, "Button", "Editar")]),
                _ => Window("Fotos", "Photos", 48, true, [Control(0, "Button", "Editar"), Control(1, "Button", "Recortar")]),
            },
            Mind = request => request.View["window"]!["title"]!.GetValue<string>() == "Notas - Bloc de notas"
                ? Step("app.open", new JsonObject { ["appId"] = "Fotos" })
                : request.History.OfType<JsonObject>().Any(step => (string?)step["operation"] == "input.visible.click")
                    ? Step("done", new JsonObject { ["evidence"] = "Recortar" })
                    : Step("input.visible.click", new JsonObject { ["label"] = "Editar" }),
        };
        harness.Receipt = (operation, _) =>
        {
            stage += 1;
            return operation == "app.open"
                ? new JsonObject { ["processId"] = 48, ["name"] = "Fotos" }
                : new JsonObject { ["surfaceChanged"] = true };
        };

        (JsonObject observed, _) = await RunDone(harness, "recortar la imagen", "Fotos", _root);

        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.Not.EqualTo("computer_use_seen_not_done"));
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That((string?)observed["satisfiedBy"], Is.EqualTo("model_evidence"));
        });
    }

    // Review of falsos éxitos v3 M1/M2, end to end: the App notes on the click whether the look after it brought
    // anything (UI Automation's receipt alone cannot tell), and hands the mind's mirror of the judge its verdicts (the
    // click that echoed the query, the text typed into a search) and the application's first look.
    [Test]
    public async Task TheMindsJudgeGetsTheAppsVerdictsAndTheFirstLook()
    {
        int stage = 0;
        JsonObject Settings(params JsonObject[] more)
        {
            JsonObject view = Window("Configuración", "SystemSettings", 50, true,
                [Control(0, "Edit", "Buscar una opción"), Control(1, "ListItem", "Inicio"), .. more]);
            view["window"]!["focused"] = new JsonObject { ["kind"] = "Edit", ["name"] = "Buscar una opción" };
            return view;
        }

        var harness = new Harness
        {
            // After the click the list of suggestions closed: the same controls as before typing.
            Screen = _ => stage == 1 ? Settings(Control(2, "ListItem", "Sistema")) : Settings(),
            Mind = request => request.History.Count switch
            {
                0 => Step("input.text.type", new JsonObject { ["text"] = "sistema" }),
                1 => Step("input.visible.click", new JsonObject { ["label"] = "Sistema" }),
                _ => Step("done", new JsonObject { ["evidence"] = "Inicio" }),
            },
        };
        harness.Receipt = (operation, _) =>
        {
            stage += 1;
            return operation == "input.visible.click"
                ? new JsonObject { ["surfaceChanged"] = false, ["absentOrDisabled"] = true, ["cascadeStage"] = "uia", ["name"] = "Sistema", ["kind"] = "ListItem" }
                : new JsonObject { ["surfaceChanged"] = true };
        };

        await RunDone(harness, "poner el modo oscuro", "Configuración", _root);

        ComputerUseStepRequest last = harness.Requests[^1];
        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests, Has.Count.EqualTo(3));
            Assert.That((bool?)last.History[0]!["query"], Is.True, "typed into a box that only searches");
            Assert.That((bool?)last.History[1]!["echo"], Is.True, "its own suggestion, and the look after it brought nothing");
            Assert.That((string?)harness.Requests[0].View["firstLook"], Does.StartWith("configuracion\n"));
        });
    }

    // ------------------------------------------------- «parece que ya estabas» on a window with a tree (r2 M3)

    private static JsonObject Player(params JsonObject[] extra)
    {
        JsonArray controls =
        [
            Control(0, "Button", "Inicio"), Control(1, "Button", "Buscar"), Control(2, "Edit", "¿Qué quieres reproducir?", value: ""),
            Control(3, "Button", "Tu biblioteca"), Control(4, "Button", "Crear lista"), Control(5, "Button", "Reproducir"),
            Control(6, "Button", "Siguiente"), Control(7, "Button", "Anterior"), Control(8, "Hyperlink", "Mix diario 1"),
            Control(9, "Hyperlink", "Mix diario 2"), Control(10, "Hyperlink", "Descubrimiento semanal"),
        ];
        foreach (JsonObject control in extra)
        {
            controls.Add(control);
        }

        return Window("Reproductor", "player", 40, true, controls);
    }

    private const string GoHome = "control:inicio:current|title:inicio";

    // Review 1 of r24b (B2), end to end: «ir a search» on a player read behind the person's window. The look an act is
    // decided on gives the keyboard's place before it (focusBeforeStep) and the application's first one (focusAtStart).
    private static async Task<JsonObject> GoToSearch(string root, bool firstInFront, JsonObject? focusedBefore, string operation, JsonObject act)
    {
        bool acted = false;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Player();
                view["window"]!["foreground"] = firstInFront || acted;
                view["window"]!["focused"] = acted
                    ? new JsonObject { ["kind"] = "Edit", ["name"] = "¿Qué quieres reproducir?" }
                    : focusedBefore?.DeepClone();
                return view;
            },
            Mind = request => request.History.Count == 0 ? Step(operation, act) : null,
        };
        harness.Receipt = (_, _) =>
        {
            acted = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a search",
            ["application"] = "Reproductor",
            ["successCheck"] = "focus:search",
            ["budgetSteps"] = 3,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(root),
            Execution("en el reproductor andá a buscar", arguments), arguments, CancellationToken.None);
        return Observed(result);
    }

    // B2: the window read behind names no focused element (a native window without the front has none with
    // HasKeyboardFocus; a partial read), the box already had the keyboard; the click on «Buscar» brought the window up
    // and the box is focused after it. The look the click was decided on did not know where the keyboard was: the click
    // proves no arrival (an empty signature behind is never «the keyboard moved»).
    [Test]
    public async Task AClickDecidedOnALookBehindThatNamesNoFocusProvesNoSearch()
    {
        JsonObject observed = await GoToSearch(_root, firstInFront: false, focusedBefore: null,
            "input.visible.click", new JsonObject { ["label"] = "Buscar" });

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.Not.True);
            Assert.That((string?)observed["satisfiedBy"], Is.Not.EqualTo("focus:search"));
        });
    }

    // B2 contracases: in front, no focused element is a fact (the keyboard on the document, which the list does not
    // carry) and ctrl_f moving it into the box arrives; behind, a look that names the focused element (the «Buscar»
    // button) still tells it, and the click that moved the keyboard into the box arrives.
    [Test]
    public async Task TheSearchArrivesWhenTheLookTheActWasDecidedOnKnewTheKeyboard()
    {
        JsonObject findKey = await GoToSearch(_root, firstInFront: true, focusedBefore: null,
            "input.key.press", new JsonObject { ["key"] = "ctrl_f" });
        JsonObject clickBehind = await GoToSearch(_root, firstInFront: false,
            new JsonObject { ["kind"] = "Button", ["name"] = "Buscar" }, "input.visible.click", new JsonObject { ["label"] = "Buscar" });

        Assert.Multiple(() =>
        {
            Assert.That((bool?)findKey["reached"], Is.True);
            Assert.That((string?)findKey["satisfiedBy"], Is.EqualTo("focus:search"));
            Assert.That((bool?)clickBehind["reached"], Is.True);
            Assert.That((string?)clickBehind["satisfiedBy"], Is.EqualTo("focus:search"));
        });
    }

    // Review 2 of r24b (B2), end to end: the player read behind names no focused element. Step 1 (ctrl_f) brings it
    // up with the box focused, unproved (decided on a look that did not know the keyboard); step 2 (click «Inicio»)
    // moves the keyboard to a group; step 3 (click «Buscar») moves it from that group into the box. The look after
    // step 1 is no start (a step of the sub-goal came before it): the start is unknown, there is no start guard, and
    // step 3, decided with the keyboard on the group, arrives. Contracase: decided with the keyboard already in the
    // box, the same click brings nothing.
    private static async Task<JsonObject> SearchAfterALateFrontLook(string root, string focusAfterHome)
    {
        int acted = 0;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Player();
                view["window"]!["foreground"] = acted > 0;
                view["window"]!["focused"] = acted switch
                {
                    0 => null,
                    2 => focusAfterHome == "Edit"
                        ? new JsonObject { ["kind"] = "Edit", ["name"] = "¿Qué quieres reproducir?" }
                        : new JsonObject { ["kind"] = "Group", ["name"] = "Inicio" },
                    _ => new JsonObject { ["kind"] = "Edit", ["name"] = "¿Qué quieres reproducir?" },
                };
                return view;
            },
            Mind = request => request.History.Count switch
            {
                0 => Step("input.key.press", new JsonObject { ["key"] = "ctrl_f" }),
                1 => Step("input.visible.click", new JsonObject { ["label"] = "Inicio" }),
                2 => Step("input.visible.click", new JsonObject { ["label"] = "Buscar" }),
                _ => null,
            },
        };
        harness.Receipt = (_, _) =>
        {
            acted++;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a search",
            ["application"] = "Reproductor",
            ["successCheck"] = "focus:search",
            ["budgetSteps"] = 4,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(root),
            Execution("en el reproductor andá a buscar", arguments), arguments, CancellationToken.None);
        return Observed(result);
    }

    [Test]
    public async Task AStartLookedAtAfterAStepIsNoGuardAndTheStepThatMovedTheKeyboardArrives()
    {
        JsonObject arrived = await SearchAfterALateFrontLook(_root, "Group");
        JsonObject stayed = await SearchAfterALateFrontLook(_root, "Edit");

        Assert.Multiple(() =>
        {
            Assert.That((bool?)arrived["reached"], Is.True);
            Assert.That((string?)arrived["satisfiedBy"], Is.EqualTo("focus:search"));
            Assert.That((bool?)stayed["reached"], Is.Not.True);
            Assert.That((string?)stayed["satisfiedBy"], Is.Not.EqualTo("focus:search"));
        });
    }

    [Test]
    public async Task AVerifiedClickOnThePlacesNavigationControlThatLeavesTheTreeAsItWasStopsAsProbablyAlreadyThere()
    {
        // Live r2 v8: the player had already settled on its home page; the click on «Inicio» changed nothing, and the
        // model went on to type «inicio» in the player's search. Now the mission looks once more and stops honestly.
        var harness = new Harness
        {
            Screen = _ => Player(),
            Mind = request => request.History.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Inicio" })
                : Step("input.text.type", new JsonObject { ["text"] = "inicio" }),
            Receipt = (_, _) => new JsonObject { ["surfaceChanged"] = true, ["cascadeStage"] = "uia", ["name"] = "Inicio", ["kind"] = "Button" },
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a inicio",
            ["application"] = "Reproductor",
            ["successCheck"] = GoHome,
            ["budgetSteps"] = 4,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el reproductor andá a Inicio", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.False, "never told as arrived");
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_already_there_unconfirmed"));
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "input.visible.click" }), "nothing typed");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.PageLookInterval), Is.EqualTo(ComputerUseMission.PageLooks),
                "looked again, bounded, before saying it (review r4: a slow page had its time to draw)");
        });
    }

    // Revision 2 of ronda 23: a chain's last sub-goal carries the mission's question to be read there («ir a inicio; y
    // responder: …»). It is still a going to its place: the click on the place that leaves the tree as it was stops as
    // «parece que ya estabas», never typing the place's name into the window's search.
    [Test]
    public async Task AChainsLastSubgoalThatAsksStillStopsAsProbablyAlreadyThere()
    {
        bool homeClicked = false;
        var harness = new Harness
        {
            Screen = _ => Player(),
            Mind = request =>
            {
                if (request.Subgoal == 0)
                {
                    return Step("input.visible.click", new JsonObject { ["label"] = "Reproducir" });
                }

                bool again = homeClicked;
                homeClicked = true;
                return again
                    ? Step("input.text.type", new JsonObject { ["text"] = "inicio" })
                    : Step("input.visible.click", new JsonObject { ["label"] = "Inicio" });
            },
            // The first sub-goal's press plays without moving the window (a moved window is no «ya estabas» to judge).
            Receipt = (_, arguments) => new JsonObject
            {
                ["surfaceChanged"] = (string?)arguments["label"] != "Reproducir",
                ["cascadeStage"] = "uia",
                ["name"] = (string?)arguments["label"],
                ["kind"] = "Button",
            },
        };
        var arguments = new JsonObject
        {
            ["goal"] = "hacer clic en reproducir; luego ir a inicio" + OperationFloor.QuestionMark + "decime qué mix está primero",
            ["application"] = null,
            ["successCheck"] = null,
            ["steps"] = new JsonArray
            {
                new JsonObject
                {
                    ["goal"] = "hacer clic en reproducir", ["application"] = "Reproductor",
                    ["successCheck"] = "stepDone:input.visible.click:reproducir",
                },
                new JsonObject
                {
                    ["goal"] = "ir a inicio" + OperationFloor.QuestionMark + "decime qué mix está primero",
                    ["application"] = "Reproductor", ["successCheck"] = GoHome,
                },
            },
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el reproductor dale a reproducir, andá a Inicio y decime qué mix está primero", arguments),
            arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.False, "never told as arrived");
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_already_there_unconfirmed"));
            Assert.That(harness.Acts.Select(act => act.Operation), Does.Not.Contain("input.text.type"), "nothing typed");
        });
    }

    // Contracase: a single mission whose own goal asks keeps reading on the place as before; the model gets its look
    // after the click and answers instead of the stop.
    [Test]
    public async Task ASingleMissionThatAsksKeepsReadingOnThePlace()
    {
        var harness = new Harness
        {
            Screen = _ => Player(),
            Mind = request => request.History.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Inicio" })
                : Step("done", new JsonObject { ["evidence"] = "Mix diario 1" }),
            Receipt = (_, _) => new JsonObject { ["surfaceChanged"] = true, ["cascadeStage"] = "uia", ["name"] = "Inicio", ["kind"] = "Button" },
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a inicio" + OperationFloor.QuestionMark + "decime qué mix está primero",
            ["application"] = "Reproductor",
            ["successCheck"] = GoHome,
            ["budgetSteps"] = 4,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el reproductor andá a Inicio y decime qué mix está primero", arguments),
            arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.Not.EqualTo("computer_use_already_there_unconfirmed"));
            Assert.That(harness.Requests, Has.Count.GreaterThanOrEqualTo(2), "the model had its look after the click");
        });
    }

    // Revision 2 of ronda 23 (the class of live n5): «abrí Configuración, andá a Red e internet, después a Wi-Fi y decime
    // a qué red estoy conectado» on a PC without Wi-Fi. The last sub-goal carries the question; the window's search typed
    // the place and listed nothing so called: the place is not there, said by its name, never a stop of the screen.
    [Test]
    public async Task AChainsLastSubgoalThatAsksForAPlaceTheWindowLacksSaysItIsNotThere()
    {
        bool typed = false;
        int asked = 0;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Window("Configuración", "SystemSettings", 30, true,
                [
                    Control(0, "Edit", "Cuadro de búsqueda, Buscar una opción", value: typed ? "wi-fi" : ""),
                    Control(1, "ListItem", "Red e Internet"), Control(2, "ListItem", "Ethernet"),
                    Control(3, "ListItem", "Modo avión"),
                ]);
                view["window"]!["focused"] = new JsonObject { ["kind"] = "Edit", ["name"] = "Cuadro de búsqueda, Buscar una opción" };
                return view;
            },
            Mind = request =>
            {
                if (request.Subgoal == 0)
                {
                    return Step("input.visible.click", new JsonObject { ["label"] = "Red e Internet" });
                }

                return asked++ == 0
                    ? Step("input.text.type", new JsonObject { ["text"] = "wi-fi" })
                    : new MindComputerUseStep("none", new JsonObject(), "no veo cómo seguir");
            },
        };
        harness.Receipt = (operation, _) =>
        {
            typed |= operation == "input.text.type";
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "hacer clic en red e internet; luego ir a wi-fi" + OperationFloor.QuestionMark + "decime a qué red estoy conectado",
            ["application"] = null,
            ["successCheck"] = null,
            ["steps"] = new JsonArray
            {
                new JsonObject
                {
                    ["goal"] = "hacer clic en red e internet", ["application"] = "Configuración",
                    ["successCheck"] = "stepDone:input.visible.click:red e internet",
                },
                new JsonObject
                {
                    ["goal"] = "ir a wi-fi" + OperationFloor.QuestionMark + "decime a qué red estoy conectado",
                    ["application"] = "Configuración", ["successCheck"] = "control:wi-fi:current|title:wi-fi",
                },
            },
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("andá a Red e internet, después a Wi-Fi y decime a qué red estoy conectado", arguments),
            arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_place_not_found"));
            Assert.That((string?)observed["missingPlace"], Is.EqualTo("wi-fi").IgnoreCase);
        });
    }

    // The place a goal goes to for the guards of the arrival: a chain's sub-goal that asks still goes to it; a single
    // mission whose own goal asks does not (contracase), as before.
    [Test]
    public void TheArrivalPlaceOfASubgoalThatAsksIsItsPlace()
    {
        string asking = "ir a wi-fi" + OperationFloor.QuestionMark + "decime a qué red estoy conectado";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ArrivalPlace(asking, chained: true), Is.EqualTo("wi-fi"));
            Assert.That(ComputerUseMission.ArrivalPlace(asking, chained: false), Is.Empty);
            Assert.That(ComputerUseMission.ArrivalPlace("ir a wi-fi", chained: false), Is.EqualTo("wi-fi"));
            Assert.That(ComputerUseMission.ArrivalPlace("hacer clic en wi-fi", chained: true), Is.Empty);
            Assert.That(ComputerUseMission.ArrivalPlace(null, chained: true), Is.Empty);
        });
    }

    // Review r4: the model's click on «Biblioteca» in a slow window, the page drawn on the fourth look after it. The window is looked at again before «parece que ya estabas» is said, and the late page arrives.
    [Test]
    public async Task AClickOnThePlaceWhosePageComesOnALaterLookArrivesInsteadOfAlreadyThere()
    {
        int clicks = 0;
        int looksAfterTheClick = 0;
        var harness = new Harness
        {
            Screen = _ =>
            {
                if (clicks > 0)
                {
                    looksAfterTheClick++;
                }

                JsonObject view = Player(Control(11, "Button", "Biblioteca"));
                view["window"]!["title"] = clicks > 0 && looksAfterTheClick > 3 ? "Biblioteca - Reproductor" : "Reproductor";
                return view;
            },
            Mind = request => request.History.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Biblioteca" })
                : Step("input.text.type", new JsonObject { ["text"] = "biblioteca" }),
        };
        harness.Receipt = (_, _) =>
        {
            clicks++;
            return new JsonObject { ["surfaceChanged"] = true, ["cascadeStage"] = "uia", ["name"] = "Biblioteca", ["kind"] = "Button" };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a biblioteca",
            ["application"] = "Reproductor",
            ["successCheck"] = "title:biblioteca",
            ["budgetSteps"] = 4,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el reproductor andá a Biblioteca", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "input.visible.click" }), "nothing typed");
        });
    }

    [Test]
    public async Task AClickOnThePlacesNameThatOpensAMenuIsNeverAlreadyThereOnATree()
    {
        // Contracase: the click on «Inicio» opened a menu (three new menu items): the window did something, so the
        // mission goes on and never says «parece que ya estabas».
        bool clicked = false;
        var harness = new Harness
        {
            Screen = _ => clicked
                ? Player(Control(11, "MenuItem", "Perfil"), Control(12, "MenuItem", "Configuración"))
                : Player(),
            Mind = request => request.History.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Inicio" })
                : new MindComputerUseStep("none", new JsonObject(), "no veo cómo seguir"),
        };
        harness.Receipt = (_, _) =>
        {
            clicked = true;
            return new JsonObject { ["surfaceChanged"] = true, ["cascadeStage"] = "uia", ["name"] = "Inicio", ["kind"] = "Button" };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a inicio",
            ["application"] = "Reproductor",
            ["successCheck"] = GoHome,
            ["budgetSteps"] = 4,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el reproductor andá a Inicio", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That((string?)observed["stoppedBy"], Is.Not.EqualTo("computer_use_already_there_unconfirmed"));
            Assert.That(harness.Requests, Has.Count.EqualTo(2), "the mission went on after the click");
        });
    }

    [Test]
    public void OnATreeOnlyANavigationClickThatLeftEverythingAsItWasReadsAsAlreadyThere()
    {
        JsonObject before = Player();
        JsonArray Clicked(string label, string kind = "Button") =>
        [
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = label, ["kind"] = kind },
        ];
        JsonObject After(JsonObject view)
        {
            view["controlsBeforeClick"] = new JsonObject { ["1"] = ComputerUseSuccessCheck.ControlNames(before) };
            view["selectedBeforeClick"] = new JsonObject { ["1"] = new JsonArray() };
            return view;
        }

        JsonObject same = After(Player());
        JsonObject menu = After(Player(Control(11, "MenuItem", "Perfil")));
        JsonObject expanded = After(Player());
        expanded["controls"]![0]!["state"] = "expanded";
        JsonObject page = Window("Reproductor", "player", 40, true,
        [
            Control(0, "Button", "Inicio"), Control(1, "Button", "Buscar"), Control(2, "Text", "Canciones que te gustan"),
            Control(3, "Button", "Ordenar"), Control(4, "Hyperlink", "Tema 1"), Control(5, "Hyperlink", "Tema 2"),
        ]);
        page = After(page);
        JsonObject unknown = Player();
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked("Inicio"), same), Is.True);
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked("Ir a Inicio"), same), Is.True,
                "the act of opening the place, named");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Inicio", Clicked("Inicio"), same, new JsonObject()), Is.True,
                "the end of the mission judges a tree the same way");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked("Inicio"), menu), Is.False, "a menu opened");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked("Inicio"), expanded), Is.False,
                "the clicked control left expanded");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked("Inicio"), page), Is.False, "the page changed");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked("Buscar"), same), Is.False, "another control");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked("Inicio", "MenuItem"), same), Is.False,
                "a menu bar's item opens something");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked("Inicio"), unknown), Is.False,
                "the controls before the click unknown");
        });
    }

    // Review r4: the place chosen by the click itself is a navigation, the opposite of being there already; the place
    // chosen before the click and still chosen is the window that was there. A look as long as a look lists does not
    // cover the window: what changed may be past it.
    [Test]
    public void OnATreeTheClickThatChoseThePlaceOrALookAtItsLimitIsNeverAlreadyThere()
    {
        JsonObject Side(string homeState, int extra = 0)
        {
            JsonArray controls =
            [
                Control(0, "TreeItem", "Inicio", homeState), Control(1, "TreeItem", "Explorar"), Control(2, "TreeItem", "Biblioteca"),
                Control(3, "Button", "Crear lista"), Control(4, "Button", "Reproducir"), Control(5, "Button", "Siguiente"),
            ];
            for (int i = 0; i < extra; i++)
            {
                controls.Add(Control(6 + i, "Hyperlink", $"Lista {i + 1}"));
            }

            return Window("Reproductor", "player", 40, true, controls);
        }

        JsonArray Clicked(bool selected = false) =>
        [
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Inicio", ["kind"] = "TreeItem",
                ["selected"] = selected,
            },
        ];
        JsonObject After(JsonObject view, JsonObject before)
        {
            view["controlsBeforeClick"] = new JsonObject { ["1"] = ComputerUseSuccessCheck.ControlNames(before) };
            view["selectedBeforeClick"] = new JsonObject { ["1"] = ComputerUseSuccessCheck.SelectedNames(before) };
            return view;
        }

        JsonObject wasThere = After(Side("selected"), Side("selected"));
        JsonObject chosenNow = After(Side("selected"), Side(""));
        JsonObject receiptOnly = After(Side(""), Side(""));
        int toTheLimit = ComputerUseMission.ViewControlLimit - 6;
        JsonObject atTheLimit = After(Side("", toTheLimit), Side("", toTheLimit));
        JsonObject underTheLimit = After(Side("", toTheLimit - 1), Side("", toTheLimit - 1));
        // Regresiones r4 (live v8): at the limit, the window's written text read from its whole drawing says whether
        // the page stayed.
        JsonArray Written(params string[] lines) => [.. lines.Select(line => (JsonNode?)JsonValue.Create(line))];
        JsonObject WithText(JsonObject view, JsonArray before, params string[] now)
        {
            view["text"] = new JsonObject { ["C"] = Written(now) };
            view["textBeforeClick"] = new JsonObject { ["1"] = before };
            return view;
        }

        // Lines as TextLines folds them, both before the click and now.
        string[] home = ["todo", "musica", "podcasts", "hecho para ti", "escuchado recientemente", "tus mixes", "novedades"];
        JsonObject textKept = WithText(After(Side("", toTheLimit), Side("", toTheLimit)), Written(home), home);
        JsonObject textChanged = WithText(After(Side("", toTheLimit), Side("", toTheLimit)), Written(home),
            "explorar todo", "generos", "podcasts", "listas", "novedades", "conciertos", "para ti");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked(selected: true), wasThere), Is.True,
                "the place was chosen before the click and still is");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked(), chosenNow), Is.False,
                "the place chosen now and not before: the click navigated");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked(selected: true), receiptOnly), Is.False,
                "the click's receipt says it chose the place");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked(), atTheLimit), Is.False,
                "a look at the limit of what a look lists, its written text unknown");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked(), textKept), Is.True,
                "at the limit, the written text of the whole window kept");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked(), textChanged), Is.False,
                "at the limit, the written text changed: the page changed past what the look lists");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Inicio", Clicked(), underTheLimit), Is.True,
                "under the limit, judged as usual");
        });
    }

    // Recibo del clic por estado (pasada r15b v3-52): OBS's «Ajustes» with «General» chosen; the second click on «Vídeo»
    // came back ok with surfaceChanged true and selected false (the picture changed because the focus moved). On a place
    // that is chosen when pressed, another item still chosen and the place not is a click without effect, never «ya
    // estabas»; the place chosen before and after still is.
    [Test]
    public void TwinV3_52_AChoiceThatDidNotTakeIsNeverAlreadyThere()
    {
        string[] pages = ["Apariencia", "Emisión", "Salida", "Audio", "Vídeo", "Atajos", "Accesibilidad", "Avanzado"];
        JsonObject Settings(string chosen)
        {
            JsonArray controls = [Control(2, "ListItem", "General", chosen == "General" ? "selected focused" : "")];
            for (int i = 0; i < pages.Length; i++)
            {
                controls.Add(Control(3 + i, "ListItem", pages[i], chosen == pages[i] ? "selected" : ""));
            }

            controls.Add(Control(11, "ComboBox", "Idioma", "collapsed", "Español"));
            return Window("Ajustes", "obs64", 52, true, controls);
        }

        JsonObject After(JsonObject view, JsonObject before)
        {
            view["controlsBeforeClick"] = new JsonObject { ["6"] = ComputerUseSuccessCheck.ControlNames(before) };
            view["selectedBeforeClick"] = new JsonObject { ["6"] = ComputerUseSuccessCheck.SelectedNames(before) };
            return view;
        }

        // By the kind the receipt names, or (selectable: false) only by the worker's «selectable» without a kind.
        JsonArray Clicked(bool selectable) =>
        [
            new JsonObject
            {
                ["step"] = 6, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Vídeo",
                ["kind"] = selectable ? "ListItem" : null, ["method"] = "invoke", ["selected"] = false,
                ["surfaceChanged"] = true, ["selectable"] = selectable ? null : true,
            },
        ];

        JsonObject focusOnly = After(Settings("General"), Settings("General"));
        JsonObject wasThere = After(Settings("Vídeo"), Settings("Vídeo"));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Vídeo", Clicked(selectable: true), focusOnly), Is.False,
                "«General» still chosen, «Vídeo» not: the click had no effect");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Vídeo", Clicked(selectable: true), focusOnly, new JsonObject()),
                Is.False, "the end of the mission judges it the same way");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Vídeo", Clicked(selectable: false), focusOnly), Is.False,
                "the receipt's «selectable» says it without the kind");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Vídeo", Clicked(selectable: true), wasThere), Is.True,
                "contracase: the place chosen before and after the click is still «ya estabas»");
        });
    }

    // Review of fable/cu-v3-recibo-del-clic-por-estado (finding 4): the worker's «selectable» reaches the step's record,
    // so the check's route by it runs in the app, not only when a test writes it into the step.
    [Test]
    public void TheReceiptsSelectableReachesTheStep()
    {
        using JsonDocument result = JsonDocument.Parse(
            """{"ok":true,"label":"Vídeo","method":"invoke","selected":false,"selectable":true,"surfaceChanged":true}""");
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse, "i", "m", "i", OperationStatuses.Completed, "{}", true, false,
            result.RootElement.Clone(), null);
        var record = new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Vídeo" };

        ComputerUseMission.RecordResponse(record, response);

        Assert.That((bool?)record["selectable"], Is.True);
    }

    // Review of the branch (finding 5): «another row of its list» is another chosen item of the place's kind and zone. A
    // tab chosen in another panel, or a row chosen in another zone's list, does not make «ya estabas» a click without
    // effect; a row of the same list still does.
    [Test]
    public void OnlyARowOfThePlacesOwnListMakesTheChoiceFail()
    {
        JsonObject Page(string otherKind, string otherZone)
        {
            JsonArray controls =
            [
                Control(2, otherKind, "General", "selected"),
                Control(3, "ListItem", "Vídeo"),
                Control(4, "ListItem", "Audio"),
                Control(5, "Button", "Aceptar"),
                Control(6, "Button", "Cancelar"),
                Control(7, "Button", "Aplicar"),
            ];
            ((JsonObject)controls[0]!)["zone"] = otherZone;
            ((JsonObject)controls[1]!)["zone"] = "TL";
            ((JsonObject)controls[2]!)["zone"] = "TL";
            JsonObject view = Window("Ajustes", "obs64", 52, true, controls);
            view["controlsBeforeClick"] = new JsonObject { ["6"] = ComputerUseSuccessCheck.ControlNames(view) };
            view["selectedBeforeClick"] = new JsonObject { ["6"] = ComputerUseSuccessCheck.SelectedNames(view) };
            return view;
        }

        JsonArray clicked =
        [
            new JsonObject
            {
                ["step"] = 6, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Vídeo",
                ["kind"] = "ListItem", ["method"] = "invoke", ["selected"] = false, ["surfaceChanged"] = true,
            },
        ];

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Vídeo", clicked, Page("TabItem", "TL")), Is.True,
                "a tab chosen elsewhere is not of the place's list");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Vídeo", clicked, Page("ListItem", "C")), Is.True,
                "a row chosen in another zone's list is not of the place's list");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs("Vídeo", clicked, Page("ListItem", "TL")), Is.False,
                "a row of the same list chosen and the place not: the click had no effect");
        });
    }

    // ------------------------------------------------------ pasada v3 r9: v3-42 on the views read live

    private static JsonObject ControlPanel(string page, bool clickedPlace)
    {
        if (clickedPlace)
        {
            return Window("Programas y características", "explorer", 46544, true,
                [Control(0, "Edit", "Buscar en Programas y características"), Control(1, "Text", "Desinstalar o cambiar un programa")]);
        }

        if (page == "home")
        {
            return Window("Panel de control", "explorer", 46544, true,
                [Control(0, "Hyperlink", "Sistema y seguridad"), Control(1, "Hyperlink", "Programas")]);
        }

        var view = (JsonObject)JsonNode.Parse(ComputerUseRealViews.V342ProgramsPage)!;
        view["window"]!["processId"] = 46544;
        return view;
    }

    private static (string Path, ShellTrace Trace) Traced()
    {
        string path = Path.Combine(Path.GetTempPath(), "baxy-cu-loop-trace-" + Guid.NewGuid().ToString("N") + ".jsonl");
        return (path, ShellTrace.TryCreate(path)!);
    }

    // The live mission (journal seq 490–506): one click on the link «Programas» of the Control Panel's home brought the
    // page «Programas», whose link «Programas y características» passed the sub-goal «ir a programas y caracteristicas»
    // as the page's header. On that same view it is no arrival, and the trace says no term held. Counter-case: the click
    // on that link opens the page, titled by its name; the trace says the check's second term (title:) held.
    [Test]
    public async Task V3_42_TheLinkToThePlaceOnThePageReachedIsNoArrivalAndTheTraceSaysWhichTermHeld()
    {
        var arguments = new JsonObject
        {
            ["goal"] = "ir a programas y caracteristicas",
            ["application"] = "Panel de control",
            ["successCheck"] = ComputerUseRealViews.V342Check1,
            ["budgetSteps"] = 4,
        };

        async Task<(JsonObject Observed, string Trace)> Run(bool followsTheLink)
        {
            string page = "home";
            bool clickedPlace = false;
            var harness = new Harness
            {
                Screen = _ => ControlPanel(page, clickedPlace),
                Mind = _ => page == "home"
                    ? Step("input.visible.click", new JsonObject { ["label"] = "Programas" })
                    : followsTheLink
                        ? Step("input.visible.click", new JsonObject { ["label"] = "Programas y características" })
                        : Step("none", new JsonObject()),
            };
            harness.Receipt = (_, act) =>
            {
                string label = (string?)act["label"] ?? string.Empty;
                clickedPlace |= label == "Programas y características";
                page = "programas";
                return new JsonObject { ["surfaceChanged"] = true, ["name"] = label, ["kind"] = "Hyperlink" };
            };

            (string path, ShellTrace trace) = Traced();
            try
            {
                ComputerUseMission.Result result;
                using (ShellTraceSink.Use(trace))
                {
                    result = await ComputerUseMission.RunAsync(
                        harness.Context(_root), Execution("en el panel de control anda a programas y caracteristicas", arguments),
                        arguments, CancellationToken.None);
                }

                trace.Dispose();
                return (Observed(result), File.ReadAllText(path));
            }
            finally
            {
                File.Delete(path);
            }
        }

        (JsonObject stayed, string stayedTrace) = await Run(followsTheLink: false);
        (JsonObject arrived, string arrivedTrace) = await Run(followsTheLink: true);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)stayed["reached"], Is.False);
            Assert.That(stayedTrace, Does.Not.Contain("computer_use.satisfied"));
            Assert.That((bool?)arrived["reached"], Is.True);
            Assert.That((string?)arrived["satisfiedBy"], Is.EqualTo("title:programas y caracteristicas"));
            Assert.That(arrivedTrace, Does.Contain("\"stage\":\"computer_use.satisfied\",\"detail\":\"subgoal.1.term.2.title\""));
        });
    }

    // ---------------------------------------------------------------- goal v3 ventana-misión (pasada r9)

    // The real views of t-long-2 (model_calls of v2-t-long-2, steps 47–49), frozen: Word's backstage «Abrir» over
    // Documento1 listing the owner's recent files, Documento1 itself, and the owner's thesis Word opened from that list.
    private const string ThesisTitle = "Proyecto_Puente_15_Dias_Desde_Maqueta  -  Modo de compatibilidad - Word";
    private const string LongTwoRequest =
        "en Word creá un documento en blanco, escribí «Informe semanal» como título, ponelo en negrita, centralo y guardalo como baxy-informe en Documentos\\baxy-prueba-v3";

    private static JsonObject Tied(JsonObject view, long hwnd, params long[] others)
    {
        view["window"]!["hwnd"] = hwnd;
        view["window"]!["root"] = hwnd;
        view["window"]!["others"] = new JsonArray([.. others.Select(other => (JsonNode?)other)]);
        return view;
    }

    private static JsonObject WordBackstageOpen() => Tied(Window("Documento1 - Word", "WINWORD", 60, true,
        [Control(8, "ListItem", "Abrir", "selected focused"), Control(12, "ListItem", "Guardar como"),
         Control(18, "TabItem", "Recientes", "selected"), Control(26, "Button", "Examinar"),
         Control(30, "ListItem", "Proyecto_Puente_15_Dias_Desde_Maqueta"),
         Control(31, "ListItem", "Estructura del Proyecto Puente Peatonal"),
         Control(32, "ListItem", "Proyecto_Puente_15_Dias_Borrador")]), 1001);

    private static JsonObject WordDocumentOne() => Tied(Window("Documento1 - Word", "WINWORD", 60, true,
        [Control(0, "Document", "Documento1"), Control(1, "Edit", "Contenido de la página 1"),
         Control(4, "Edit", "Buscar en documento", "", "Buscar en documento"), Control(12, "Button", "Guardar"),
         Control(22, "Button", "Pestaña Archivo"), Control(23, "TabItem", "Inicio", "selected")],
        "Informe semanal", "Página 1 de", "2 palabras"), 1001);

    private static JsonObject OwnersThesis(bool born)
    {
        JsonObject view = Window(ThesisTitle, "WINWORD", 60, true,
            [Control(0, "Button", "Reanudar lectura"), Control(3, "Edit", "Buscar en documento", "", "Buscar en documento"),
             Control(11, "Button", "NOTA PRELIMINAR"), Control(12, "Button", "2. Introducción"),
             Control(45, "TabItem", "Inicio", "selected"), Control(50, "Document", "Proyecto_Puente_15_Dias_Desde_Maqueta")],
            "Proyecto Pue... • Guardado v", "INSTITUTO EJEMPLO DE LA", "EVALUACIÓN Y SEGUIM");
        view["window"]!["hwnd"] = 2002L;
        view["window"]!["root"] = 2002L;
        view["window"]!["focused"] = new JsonObject { ["i"] = 50, ["name"] = "Proyecto_Puente_15_Dias_Desde_Maqueta", ["kind"] = "Document" };
        if (born)
        {
            view["window"]!["born"] = true;
        }

        return view;
    }

    private static bool Knows(JsonObject look, long hwnd) =>
        look["known"] is JsonArray known && known.Any(node => (long?)node == hwnd);

    [Test]
    public async Task TLong2TheOwnersDocumentOpenedFromTheRecentListIsNeverTheMissionsWindow()
    {
        // t-long-2: on Documento1's backstage «Abrir» the model clicked the owner's thesis in the recent list; Word opened
        // it in a window of its one process, and the look bound to the process took it (Ctrl+A, Escape and ribbon clicks
        // went there, and «Guardado» on it was cited as done). Now that window, an existing item opened by its name and
        // not named by the request, is refused: the look reads Documento1 again, and nothing is decided on the thesis.
        bool clicked = false;
        var harness = new Harness
        {
            Screen = look => !clicked ? WordBackstageOpen()
                : Knows(look, 2002) ? WordDocumentOne()
                : OwnersThesis(born: true),
        };
        harness.Mind = request => request.View["window"]?["title"]?.ToString() == ThesisTitle
            ? Step("input.key.press", new JsonObject { ["key"] = "ctrl_a" })
            : harness.Acts.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Proyecto_Puente_15_Dias_Desde_Maqueta", ["index"] = 30 })
                : new MindComputerUseStep("none", new JsonObject(), string.Empty);
        harness.Receipt = (operation, _) =>
        {
            clicked |= operation == "input.visible.click";
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "ponelo en negrita", ["application"] = "Word" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(LongTwoRequest, arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests.Select(request => request.View["window"]?["title"]?.ToString()),
                Has.None.EqualTo(ThesisTitle), "the thesis is never shown to the model");
            Assert.That(harness.Acts.Select(act => (long?)act.Arguments["window"]), Is.All.EqualTo(1001L), "every act on Documento1");
            Assert.That(harness.Acts.Select(act => act.Operation), Has.None.EqualTo("input.key.press"), "no Ctrl+A anywhere");
            Assert.That(harness.Looks.Any(look => Knows(look, 2002)), Is.True, "the thesis is known not to be the mission's");
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That(observed["window"]?["title"]?.ToString(), Is.EqualTo("Documento1 - Word"));
        });
    }

    [Test]
    public async Task TLong2AnArrivalIsNeverJudgedOnAnotherWindowThanTheTiedOne()
    {
        // t-long-2 (the judge): «Proyecto Pue... • Guardado» on the thesis passed for the save of Documento1. A window
        // the look did not flag as born but that is none of the mission's windows (a provider without the binding) is
        // judged the same way, never with the check: the check «title:guardado» never holds on it.
        bool clicked = false;
        var harness = new Harness
        {
            Screen = look => !clicked ? WordBackstageOpen() : Knows(look, 2002) ? WordDocumentOne() : OwnersThesis(born: false),
            Mind = request => request.View["window"]?["title"]?.ToString() == ThesisTitle
                ? Step("done", new JsonObject { ["evidence"] = "Proyecto Pue... • Guardado v" })
                : Step("input.visible.click", new JsonObject { ["label"] = "Proyecto_Puente_15_Dias_Desde_Maqueta", ["index"] = 30 }),
        };
        harness.Receipt = (operation, _) =>
        {
            clicked |= operation == "input.visible.click";
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "guardalo como baxy-informe",
            ["application"] = "Word",
            ["successCheck"] = "text:guardado",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(LongTwoRequest, arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.False, "never reached on the owner's thesis");
            Assert.That(harness.Requests.Select(request => request.View["window"]?["title"]?.ToString()), Has.None.EqualTo(ThesisTitle));
        });
    }

    [Test]
    public async Task TLong2ASaveAsDialogOfTheTiedWindowIsTheMission()
    {
        // Contracase: the «Guardar como» dialog Word opens for Documento1 came during the mission and Documento1 owns it:
        // it is the mission's, and the name is typed into its field. Review of the branch (finding 9): the person's input
        // reached the process meanwhile (personNearAgoMs), so only the owner keeps it (the act alone would not).
        bool saving = false;
        var harness = new Harness
        {
            Screen = _ =>
            {
                if (!saving)
                {
                    return WordDocumentOne();
                }

                JsonObject dialog = Window("Guardar como", "WINWORD", 60, true,
                    [Control(0, "Edit", "Nombre de archivo:", "focused"), Control(1, "Button", "Guardar"), Control(2, "Button", "Cancelar")]);
                dialog["window"]!["hwnd"] = 3003L;
                dialog["window"]!["root"] = 3003L;
                dialog["window"]!["owner"] = 1001L;
                dialog["window"]!["born"] = true;
                dialog["window"]!["personNearAgoMs"] = 0;
                return dialog;
            },
        };
        harness.Mind = _ => harness.Acts.Count == 0
            ? Step("input.key.press", new JsonObject { ["key"] = "ctrl_shift_s" })
            : harness.Acts.Count == 1
                ? Step("input.text.type", new JsonObject { ["text"] = "baxy-informe", ["field"] = "Nombre de archivo" })
                : new MindComputerUseStep("none", new JsonObject(), string.Empty);
        harness.Receipt = (operation, _) =>
        {
            saving |= operation == "input.key.press";
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "guardalo como baxy-informe", ["application"] = "Word" };

        await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(LongTwoRequest, arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "input.key.press", "input.text.type" }));
            Assert.That((long?)harness.Acts[1].Arguments["window"], Is.EqualTo(3003L), "the name goes to the dialog");
            Assert.That(harness.Requests[1].View["window"]?["title"]?.ToString(), Is.EqualTo("Guardar como"));
        });
    }

    [Test]
    public async Task TMenu1APropertiesWindowTheRequestNamesIsTheMissions()
    {
        // Contracase (t-menu-1 with the file manager resolved): «Propiedades: notas.txt» is a window of its own, not owned
        // by the folder window; the request names it (propiedades, notas.txt), so the mission goes on in it. The person's
        // input reached the process meanwhile (personNearAgoMs): only the name keeps it (finding 9).
        bool opened = false;
        var harness = new Harness
        {
            Screen = _ =>
            {
                if (!opened)
                {
                    return Tied(Window("baxy-prueba-v3", "explorer", 70, true,
                        [Control(0, "ListItem", "notas.txt", "selected"), Control(1, "MenuItem", "Propiedades")]), 700, 701);
                }

                JsonObject properties = Window("Propiedades: notas.txt", "explorer", 70, true,
                    [Control(0, "TabItem", "General", "selected"), Control(1, "Text", "Tamaño:"), Control(2, "Text", "60 bytes")]);
                properties["window"]!["hwnd"] = 702;
                properties["window"]!["root"] = 702;
                properties["window"]!["born"] = true;
                properties["window"]!["personNearAgoMs"] = 0;
                return properties;
            },
        };
        harness.Mind = _ => harness.Acts.Count == 0
            ? Step("input.visible.click", new JsonObject { ["label"] = "Propiedades", ["index"] = 1 })
            : Step("done", new JsonObject { ["evidence"] = "60 bytes" });
        harness.Receipt = (operation, _) =>
        {
            opened |= operation == "input.visible.click";
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "abrir las propiedades de notas.txt",
            ["application"] = "Explorador de archivos",
        };

        await ComputerUseMission.RunAsync(
            harness.Context(_root),
            Execution("en la carpeta baxy-prueba-v3 de Documentos haceme clic derecho en notas.txt y abrime las propiedades, quiero ver cuánto pesa", arguments),
            arguments, CancellationToken.None);

        Assert.That(harness.Requests[1].View["window"]?["title"]?.ToString(), Is.EqualTo("Propiedades: notas.txt"));
    }

    [Test]
    public async Task ABornWindowThePersonWorksInIsRefused()
    {
        // A window of the application's process that came during the mission but takes the person's input (they opened
        // and use it) is theirs: refused, the mission's window is read again. Review of the branch (finding 9): it came
        // after a verified act of the mission, so without the person's rule it would pass for one the act brought.
        bool clicked = false;
        var harness = new Harness
        {
            Screen = look =>
            {
                if (!clicked || Knows(look, 2002) || look["windows"] is null)
                {
                    return WordDocumentOne();
                }

                JsonObject theirs = OwnersThesis(born: true);
                theirs["window"]!["title"] = "Informe semanal - Word";
                theirs["window"]!["personInputAgoMs"] = 150;
                return theirs;
            },
        };
        harness.Mind = _ => harness.Acts.Count == 0
            ? Step("input.visible.click", new JsonObject { ["label"] = "Inicio", ["index"] = 23 })
            : new MindComputerUseStep("none", new JsonObject(), string.Empty);
        harness.Receipt = (operation, _) =>
        {
            clicked |= operation == "input.visible.click";
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "ponelo en negrita", ["application"] = "Word" };

        await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(LongTwoRequest, arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "input.visible.click" }), "the mission acted first");
            Assert.That(harness.Requests, Has.Count.GreaterThan(1));
            Assert.That(harness.Requests.Select(request => request.View["window"]?["title"]?.ToString()), Is.All.EqualTo("Documento1 - Word"));
            Assert.That(harness.Looks.Any(look => Knows(look, 2002)), Is.True, "the person's window is known not to be the mission's");
        });
    }

    // The real view of t-menu-1 and t-form-4 (model_calls, the only step): the meter's simulated person typing in a
    // Python window, in front, while the mission named no application.
    private static JsonObject SimulatedPersonsWindow(long? personInputAgoMs)
    {
        JsonObject view = Window("BAXY usuario simulado", "python", 9100, false,
            [Control(0, "Document", "el usuario escribe tranquilo mientras baxy hace", "focused"),
             Control(1, "MenuItem", "Sistema", "collapsed"), Control(2, "Button", "Minimizar"), Control(3, "Button", "Maximizar"),
             Control(4, "Button", "Cerrar"), Control(5, "TitleBar", "BAXY usuario simulado"), Control(6, "MenuBar", "Barra de menús del sistema")],
            "BAXY usuario simulado", "el usuario escribe tranquilo mientras baxy hac");
        view["window"]!["hwnd"] = 9101;
        view["window"]!["root"] = 9101;
        if (personInputAgoMs is long ago)
        {
            view["window"]!["personInputAgoMs"] = ago;
        }

        return view;
    }

    [TestCase("en la carpeta baxy-prueba-v3 de Documentos haceme clic derecho en notas.txt y abrime las propiedades, quiero ver cuánto pesa")]
    [TestCase("Ponme el texto seleccionado en Arial, tamaño 20 y en cursiva, desde el cuadro de diálogo de Fuente")]
    public async Task TMenu1AndTForm4ThePersonsWindowIsNeverTheDestinationOfAMissionWithNoApplication(string request)
    {
        // t-menu-1, t-form-4: with no application named the look read the window in front, the one the person was typing
        // in, showed it to the model and named it in the final («No pude hacerlo en «BAXY usuario simulado»»). Review of
        // the branch (finding 5): the model is asked over a blank view, nothing of the person's window in it, and an
        // answer that opens nothing ends the mission as before.
        var harness = new Harness
        {
            Screen = _ => SimulatedPersonsWindow(personInputAgoMs: 40),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Sistema", ["index"] = 1 }),
        };
        var arguments = new JsonObject { ["goal"] = request };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(request, arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests, Has.Count.EqualTo(1));
            Assert.That(harness.Requests.Select(asked => asked.View.ToJsonString()),
                Has.None.Contains("usuario simulado").And.None.Contains("Sistema").And.None.Contains("9101"),
                "the person's window is never shown to the model");
            Assert.That(harness.Acts, Is.Empty);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_no_application"));
            Assert.That(observed["window"], Is.Null, "the final names no window");
            Assert.That(observed["screen"], Is.Null, "nothing of the person's window is quoted");
        });
    }

    [Test]
    public async Task TMenu1FromTheBlankViewTheMissionMayStillOpenAnApplication()
    {
        // Review of the branch (finding 5), contracase: over the blank view the model opens the file manager; the opening
        // goes, and the mission goes on in the window it opened (its process), never in the person's.
        const string request = "en la carpeta baxy-prueba-v3 de Documentos haceme clic derecho en notas.txt y abrime las propiedades, quiero ver cuánto pesa";
        bool opened = false;
        var harness = new Harness
        {
            Screen = _ => opened
                ? Window("baxy-prueba-v3", "explorer", 70, true, [Control(0, "ListItem", "notas.txt"), Control(1, "MenuItem", "Propiedades")])
                : SimulatedPersonsWindow(personInputAgoMs: 40),
        };
        harness.Mind = asked => !opened
            ? Step("app.open", new JsonObject { ["appId"] = "Explorador de archivos" })
            : new MindComputerUseStep("none", new JsonObject(), string.Empty);
        harness.Receipt = (operation, _) =>
        {
            opened |= operation == "app.open";
            return new JsonObject { ["processId"] = 70 };
        };
        var arguments = new JsonObject { ["goal"] = request };

        await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(request, arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "app.open" }));
            Assert.That(harness.Requests, Has.Count.EqualTo(2));
            Assert.That(harness.Requests[0].View.ToJsonString(), Does.Not.Contain("usuario simulado"));
            Assert.That(harness.Requests[1].View["window"]?["title"]?.ToString(), Is.EqualTo("baxy-prueba-v3"));
        });
    }

    [Test]
    public async Task TheWindowInFrontTheRequestNamesIsStillTheDestination()
    {
        // Contracase: «en esta ventana…» names the window in front as the destination (frontWindow), also while the
        // person types in it: it is read for the mission as before.
        var harness = new Harness
        {
            Screen = _ => SimulatedPersonsWindow(personInputAgoMs: 40),
            Mind = _ => new MindComputerUseStep("none", new JsonObject(), string.Empty),
        };
        var arguments = new JsonObject { ["goal"] = "en esta ventana maximizala", ["frontWindow"] = true };

        await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en esta ventana maximizala", arguments), arguments, CancellationToken.None);

        Assert.That(harness.Requests, Has.Count.EqualTo(1));
    }

    private const string TDrag2Request = "En el panel de miniaturas arrastra la diapositiva «Tres» para que quede la primera";

    // Ronda 20 P2 (t-drag-2, pasada r18): the real view of its only step (model_calls), the simulated person typing in
    // front while the mission named no application, as the adapter now says it: from the detector seeded when it
    // started (personInputAgoMs), or, without Raw Input, only how long ago the session's last input came.
    private static JsonObject TDrag2View(long? personInputAgoMs = null, long? unknownAgoMs = null, bool foreground = true)
    {
        JsonObject view = SimulatedPersonsWindow(personInputAgoMs);
        view["window"]!["foreground"] = foreground;
        if (unknownAgoMs is long unknown)
        {
            view["window"]!["personInputUnknownAgoMs"] = unknown;
        }

        return view;
    }

    private async Task<(Harness Harness, JsonObject Observed)> RunWithNoApplicationAsync(JsonObject view, string request, bool frontWindow = false)
    {
        var harness = new Harness
        {
            Screen = _ => view.DeepClone().AsObject(),
            Mind = _ => new MindComputerUseStep("none", new JsonObject(), string.Empty),
        };
        var arguments = new JsonObject { ["goal"] = request };
        if (frontWindow)
        {
            arguments["frontWindow"] = true;
        }

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(request, arguments), arguments, CancellationToken.None);
        return (harness, Observed(result));
    }

    [TestCase(40L, null, TestName = "TDrag2_LookSaysThePersonWorksThere_HidesTheWindow")]
    [TestCase(null, 120L, TestName = "TDrag2_NoRawInput_RecentInput_HidesTheWindowInFront")]
    public async Task TDrag2ThePersonsWindowInFrontIsHiddenFromTheFirstLook(long? personAgo, long? unknownAgo)
    {
        // t-drag-2: the first look of the process came without the person's window and the final named «BAXY usuario
        // simulado». Only the App's half: once the look says the person works there (personInputAgoMs, the same path
        // as TMenu1AndTForm4 with SimulatedPersonsWindow) or, without Raw Input, that a recent input of unknown window
        // came, the model sees the blank view and the final names no window. The detector's half (the seed when it
        // starts, the missed input that marks the window in front, its own timer) is in UserInputPauseTests.
        (Harness harness, JsonObject observed) = await RunWithNoApplicationAsync(TDrag2View(personAgo, unknownAgo), TDrag2Request);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests, Has.Count.EqualTo(1));
            Assert.That(harness.Requests[0].View["window"]?["title"]?.ToString(), Is.Empty);
            Assert.That(harness.Requests[0].View["controls"]?.AsArray(), Is.Empty);
            Assert.That(harness.Requests.Select(asked => asked.View.ToJsonString()),
                Has.None.Contains("usuario simulado").And.None.Contains("9101"));
            Assert.That(harness.Acts, Is.Empty);
            Assert.That(observed["window"], Is.Null, "the final names no window");
            Assert.That(observed.ToJsonString(), Does.Not.Contain("usuario simulado"));
        });
    }

    [TestCase(9000L, null, true, TestName = "TDrag2Contra_PersonIdleLongerThanRecent_WindowShown")]
    [TestCase(null, 9000L, true, TestName = "TDrag2Contra_NoRawInput_OldInput_WindowShown")]
    [TestCase(null, 120L, false, TestName = "TDrag2Contra_NoRawInput_WindowBehind_WindowShown")]
    [TestCase(null, null, true, TestName = "TDrag2Contra_RawInputPersonElsewhere_WindowShown")]
    public async Task TDrag2ContracasesTheWindowInFrontIsStillShown(long? personAgo, long? unknownAgo, bool foreground)
    {
        // Contracases: the person idle longer than PersonRecentMs; without Raw Input (last_input_info) an old input, or
        // a look of a window that is not in front; with Raw Input their last input went elsewhere (no personInputAgoMs
        // and no unknown time: no window of the person is made up). The window is read for the mission as today.
        (Harness harness, _) = await RunWithNoApplicationAsync(TDrag2View(personAgo, unknownAgo, foreground), TDrag2Request);

        Assert.That(harness.Requests, Has.Count.EqualTo(1));
        Assert.That(harness.Requests[0].View.ToJsonString(), Does.Contain("usuario simulado"));
    }

    [Test]
    public async Task TDrag2ContraTheWindowInFrontTheRequestNamesIsReadWithoutRawInputToo()
    {
        // Contracase: «en esta ventana…» (frontWindow) uses the window in front on purpose, also with a recent input of
        // unknown window.
        (Harness harness, _) = await RunWithNoApplicationAsync(
            TDrag2View(unknownAgoMs: 50), "en esta ventana maximizala", frontWindow: true);

        Assert.That(harness.Requests, Has.Count.EqualTo(1));
        Assert.That(harness.Requests[0].View.ToJsonString(), Does.Contain("usuario simulado"));
    }

    [Test]
    public void TDrag2ContraTheUnknownInputWeighsOnlyALookNobodyAskedForInFrontWithNoApplication()
    {
        // Contracases of the rule without Raw Input: a requested look (an application named) or a look behind is not the
        // person's by it; the known window of the person (personInputAgoMs) decides alone; a mission with an application
        // named never hides a window by it.
        var state = new JsonObject { ["startedUtc"] = DateTimeOffset.UtcNow.ToString("O", System.Globalization.CultureInfo.InvariantCulture) };
        JsonObject requested = TDrag2View(unknownAgoMs: 50);
        requested["window"]!["requested"] = true;
        JsonObject known = TDrag2View(personInputAgoMs: 9000, unknownAgoMs: 50);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.PersonMayWorkInFront(TDrag2View(unknownAgoMs: 50)), Is.True);
            Assert.That(ComputerUseMissionWindow.PersonMayWorkInFront(TDrag2View(unknownAgoMs: ComputerUseMissionWindow.PersonRecentMs + 1)), Is.False);
            Assert.That(ComputerUseMissionWindow.PersonMayWorkInFront(requested), Is.False);
            Assert.That(ComputerUseMissionWindow.PersonMayWorkInFront(TDrag2View(unknownAgoMs: 50, foreground: false)), Is.False);
            Assert.That(ComputerUseMissionWindow.PersonMayWorkInFront(known), Is.False);
            Assert.That(ComputerUseMissionWindow.PersonsWindowWithoutApplication(
                state, "PowerPoint", TDrag2View(personInputAgoMs: 40, unknownAgoMs: 50), ofTheMission: false, DateTimeOffset.UtcNow), Is.False);
        });
    }

    [Test]
    public void TLong2CtrlAOrTextOnADocumentTheMissionNeitherOpenedNorCreatedNeedsTheRequestToNameIt()
    {
        // t-long-2 (rule 3): the thesis was already open with Documento1 beside it (another window of the process when the
        // mission took its window), BAXY neither opened nor created it and the request does not name it: Ctrl+A, Supr and
        // text on its content are refused; its search field is no content. «en mi documento Proyecto_Puente… de Word» names it.
        JsonObject thesis = OwnersThesis(born: false);
        thesis["window"]!["others"] = new JsonArray(1001L);
        thesis["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1600, ["h"] = 900 };
        JsonObject Tied(string objective)
        {
            var state = new JsonObject { ["objective"] = objective, ["application"] = "Word" };
            ComputerUseMission.AdoptWindow(state, "Word", thesis);
            ComputerUseMissionWindow.Tie(state, "Word", thesis, ofTheApplication: true, []);
            return state;
        }

        JsonObject unnamed = Tied(LongTwoRequest);
        JsonObject named = Tied("en mi documento Proyecto_Puente_15_Dias_Desde_Maqueta de Word seleccioná todo y ponelo en Arial");
        Assert.Multiple(() =>
        {
            foreach (string key in new[] { "ctrl_a", "delete", "backspace" })
            {
                Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = key }, thesis, unnamed, "Word"),
                    Is.False, key);
                Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = key }, thesis, named, "Word"),
                    Is.True, key + " named");
            }

            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", new JsonObject { ["text"] = "Informe semanal" }, thesis, unnamed, "Word"),
                Is.False, "text on the thesis");
            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", new JsonObject { ["text"] = "café", ["field"] = "Buscar en documento" }, thesis, unnamed, "Word"),
                Is.True, "its search field is no content");
            Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = "escape" }, thesis, unnamed, "Word"),
                Is.True, "a key that erases nothing");
            Assert.That(ComputerUseMission.BindToMissionWindow("input.visible.click", new JsonObject { ["label"] = "Inicio", ["index"] = 45 }, thesis, unnamed, "Word"),
                Is.True, "a click on no erasing command");
        });
    }

    // ---------------------------------------------------------------- review of ventana-misión (r2)

    // State tied to the thesis as t-long-2 had it: another window of Word's process (Documento1) beside it.
    private static (JsonObject Thesis, JsonObject State) ThesisTied(string objective, params long[] others)
    {
        JsonObject thesis = OwnersThesis(born: false);
        thesis["window"]!["others"] = new JsonArray([.. others.Select(other => (JsonNode?)other)]);
        thesis["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1600, ["h"] = 900 };
        var state = new JsonObject { ["objective"] = objective, ["application"] = "Word" };
        ComputerUseMission.AdoptWindow(state, "Word", thesis);
        ComputerUseMissionWindow.Tie(state, "Word", thesis, ofTheApplication: true, []);
        return (thesis, state);
    }

    [Test]
    public void TLong2EveryActThatMaySelectEraseOrReplaceTheThesisIsRefused()
    {
        // Finding 3: Ctrl+V, Enter, Space, Tab and Ctrl+Z replace or undo over a selection; a click on «Seleccionar
        // todo», «Cortar», «Borrar» or «Pegar» of the ribbon, and a drag over the content, select, move or erase it.
        (JsonObject thesis, JsonObject state) = ThesisTied(LongTwoRequest, 1001);
        Assert.Multiple(() =>
        {
            foreach (string key in new[] { "ctrl_v", "enter", "space", "tab", "ctrl_z", "ctrl_x", "ctrl_s", "ctrl_w" })
            {
                Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = key }, thesis, state, "Word"),
                    Is.False, key);
            }

            foreach (string label in new[] { "Seleccionar todo", "Cortar", "Borrar", "Pegar", "Select all", "Delete" })
            {
                Assert.That(ComputerUseMission.BindToMissionWindow("input.visible.click", new JsonObject { ["label"] = label, ["index"] = 12 }, thesis, state, "Word"),
                    Is.False, label);
            }

            // Contracases: moving, copying, finding and the ribbon's other commands change nothing.
            foreach (string key in new[] { "ctrl_c", "ctrl_f", "page_down", "home", "escape" })
            {
                Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = key }, thesis, state, "Word"),
                    Is.True, key);
            }

            Assert.That(ComputerUseMission.BindToMissionWindow("input.visible.click", new JsonObject { ["label"] = "2. Introducción", ["index"] = 12 }, thesis, state, "Word"),
                Is.True, "a heading of the navigation pane");
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.key.press", new JsonObject { ["key"] = "enter" }, thesis, state),
                Is.True, "the cause is the document");
        });
    }

    [Test]
    public void TLong2TheSoleWindowOfANamedApplicationTakesTextButNothingThatErases()
    {
        // Finding 4: Word open with the thesis alone (no other window of its process) and the request naming Word: the
        // window is the sole one, not named. Text and Enter go at the caret; Ctrl+A, Supr, a select-all click do not.
        // Another document in that window (a tab, another file opened in it) is no longer the sole one's: nothing goes.
        (JsonObject thesis, JsonObject state) = ThesisTied(LongTwoRequest);
        Assert.Multiple(() =>
        {
            Assert.That(state["named"], Is.Null, "the application named is no document named");
            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", new JsonObject { ["text"] = "hola" }, thesis, state, "Word"), Is.True);
            Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = "enter" }, thesis, state, "Word"), Is.True);
            foreach (string key in new[] { "ctrl_a", "delete", "backspace", "ctrl_v" })
            {
                Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = key }, thesis, state, "Word"),
                    Is.False, key);
            }

            Assert.That(ComputerUseMission.BindToMissionWindow("input.visible.click", new JsonObject { ["label"] = "Seleccionar todo", ["index"] = 12 }, thesis, state, "Word"),
                Is.False);
        });

        JsonObject otherTab = thesis.DeepClone().AsObject();
        otherTab["window"]!["title"] = "Diario personal - Word";
        Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", new JsonObject { ["text"] = "hola" }, otherTab, state, "Word"),
            Is.False, "another document in the sole window");
        // Contracase: the document the mission saved it as (a name it typed) is still the sole window's.
        state["steps"] = new JsonArray(new JsonObject { ["operation"] = "input.text.type", ["text"] = "resumen-semana", ["ok"] = true });
        JsonObject saved = thesis.DeepClone().AsObject();
        saved["window"]!["title"] = "resumen-semana.docx - Word";
        Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", new JsonObject { ["text"] = "hola" }, saved, state, "Word"),
            Is.True, "saved by the mission under the name it typed");
    }

    [Test]
    public void ALookThatDoesNotSayItsOtherWindowsCountsAsSeveral()
    {
        // Finding 6: a look that reached the application by its family (requested=false) did not say «others»; that is
        // no proof of a single window: nothing is named, and text on its content is refused.
        JsonObject thesis = OwnersThesis(born: false);
        thesis["window"]!["requested"] = false;
        var state = new JsonObject { ["objective"] = LongTwoRequest, ["application"] = "Word" };
        ComputerUseMissionWindow.Tie(state, "Word", thesis, ofTheApplication: true, []);
        Assert.Multiple(() =>
        {
            Assert.That(state["named"], Is.Null);
            Assert.That(state["sole"], Is.Null);
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", new JsonObject { ["text"] = "hola" }, thesis, state), Is.True);
        });
    }

    // ---------------------------------------------------------------- ronda 21: la guarda juzga lo que el acto altera

    private const string EdgeRequest = "en edge apretá ctrl t, andá a wikipedia y buscá curicó";

    // Pasada r18 v3-59: the person's Edge (reused, alreadyRunning) on a support page, the keyboard on the page's
    // read-only document; a draft field may be added over it.
    private static (JsonObject Page, JsonObject State) PersonsEdge(bool draft = false)
    {
        var controls = new JsonArray
        {
            Control(0, "TabItem", "Encontrar información sobre el dispositivo Windows | Microsoft Support", "selected"),
            Control(1, "Edit", "Barra de direcciones y búsqueda", "", "https://support.microsoft.com/es-es/windows"),
            Control(2, "Document", "Encontrar información sobre el dispositivo Windows | Microsoft Support", "readonly focused"),
        };
        controls[1]!["rect"] = new JsonObject { ["x"] = 200, ["y"] = 40, ["w"] = 900, ["h"] = 30 };
        controls[2]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 80, ["w"] = 1600, ["h"] = 820 };
        if (draft)
        {
            JsonObject body = Control(3, "Edit", "Cuerpo del mensaje", "focused", "Hola, te escribo por la reunión");
            body["rect"] = new JsonObject { ["x"] = 300, ["y"] = 200, ["w"] = 1000, ["h"] = 600 };
            controls.Add((JsonNode?)body);
        }

        JsonObject page = Tied(Window("Encontrar información sobre el dispositivo Windows - Microsoft Edge", "msedge", 70, true, controls), 3003, 3004);
        page["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1600, ["h"] = 900 };
        page["window"]!["focused"] = draft
            ? new JsonObject { ["i"] = 3, ["kind"] = "Edit", ["name"] = "Cuerpo del mensaje" }
            : new JsonObject { ["i"] = 2, ["kind"] = "Document", ["name"] = "Encontrar información" };
        var state = new JsonObject { ["objective"] = EdgeRequest, ["application"] = "Microsoft Edge" };
        ComputerUseMission.AdoptWindow(state, "Microsoft Edge", page);
        ComputerUseMissionWindow.Tie(state, "Microsoft Edge", page, ofTheApplication: true, []);
        return (page, state);
    }

    [Test]
    public void V3_59ANewTabOnTheReadOnlyPageOfThePersonsBrowserIsNoActOnADocument()
    {
        (JsonObject page, JsonObject state) = PersonsEdge();
        Assert.Multiple(() =>
        {
            Assert.That(state["created"], Is.Null, "the person's browser, reused");
            Assert.That(state["named"], Is.Null);
            foreach (string key in new[] { "ctrl_t", "ctrl_l", "ctrl_k" })
            {
                Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.key.press", new JsonObject { ["key"] = key }, page, state),
                    Is.False, key);
                Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = key }, page, state, "Microsoft Edge"),
                    Is.True, key);
            }
        });
    }

    [Test]
    public void ContracaseADraftThePersonWritesInTheBrowserKeepsEveryRefusal()
    {
        // Ronda 21 contracase: the keyboard on a large draft (an Edit no reader calls read-only) inside the same page:
        // a text, Delete, Ctrl+A and the chords that format an editor's text are refused as before.
        (JsonObject page, JsonObject state) = PersonsEdge(draft: true);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", new JsonObject { ["text"] = "hola" }, page, state, "Microsoft Edge"),
                Is.False, "a text over the draft");
            foreach (string key in new[] { "delete", "backspace", "ctrl_a", "enter", "ctrl_t", "ctrl_l" })
            {
                Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = key }, page, state, "Microsoft Edge"),
                    Is.False, key);
            }

            Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = "ctrl_f" }, page, state, "Microsoft Edge"),
                Is.True, "the find alters nothing");
        });
    }

    // Pasada r18 v3-36: a sticky note («baxy prueba») whose editor covers the window, no search, no menu.
    private static (JsonObject Note, JsonObject State) PersonsNote()
    {
        JsonObject editor = Control(0, "Edit", "Editor de notas", "", "baxy prueba");
        editor["rect"] = new JsonObject { ["x"] = 1, ["y"] = 40, ["w"] = 382, ["h"] = 350 };
        JsonObject note = Tied(Window("Notas rápidas", "Microsoft.Notes", 80, true, [editor]), 4004);
        note["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 384, ["h"] = 392 };
        var state = new JsonObject { ["objective"] = "en notas rápidas buscá dentista", ["application"] = "Notas rápidas" };
        ComputerUseMission.AdoptWindow(state, "Notas rápidas", note);
        ComputerUseMissionWindow.Tie(state, "Notas rápidas", note, ofTheApplication: true, []);
        return (note, state);
    }

    [Test]
    public void V3_36ARuleSearchKeyRefusedOnThePersonsNoteIsHandedToTheModel()
    {
        (JsonObject note, JsonObject state) = PersonsNote();
        var ctrlK = new JsonObject { ["key"] = "ctrl_k" };
        Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", ctrlK, note, state, "Notas rápidas"), Is.False,
            "the guard still refuses ctrl_k on the note's content");
        JsonObject? refused = ComputerUseMission.RefusalForTheModel("input.key.press", ctrlK, "rule", [], 1);
        Assert.That(refused, Is.Not.Null, "a rule's key that alters no content does not end the mission");
        Assert.Multiple(() =>
        {
            Assert.That((bool?)refused!["ok"], Is.False);
            Assert.That((bool?)refused["refused"], Is.True);
            Assert.That((string?)refused["error"], Is.EqualTo("document_not_named"));
            Assert.That((string?)refused["key"], Is.EqualTo("ctrl_k"));
            // The mind reads the refusal in the history.
            JsonObject item = (JsonObject)ComputerUseMission.HistoryForMind(new JsonArray(refused.DeepClone()), 0)[0]!;
            Assert.That((bool?)item["refused"], Is.True);
            Assert.That((string?)item["error"], Is.EqualTo("document_not_named"));
            // The find the mind presses instead is no act on the note's content.
            Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = "ctrl_f" }, note, state, "Notas rápidas"),
                Is.True);
        });
    }

    [Test]
    public void ContracaseTheModelsActOrAnAlteringKeyRefusedStillEndsTheMission()
    {
        (JsonObject note, JsonObject state) = PersonsNote();
        var ctrlK = new JsonObject { ["key"] = "ctrl_k" };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.RefusalForTheModel("input.key.press", ctrlK, "model", [], 1), Is.Null,
                "the model's own key");
            Assert.That(ComputerUseMission.RefusalForTheModel("input.key.press", ctrlK, null, [], 1), Is.Null,
                "a key with no source is the model's");
            foreach (string key in new[] { "ctrl_a", "delete", "backspace", "enter", "ctrl_v", "ctrl_x", "ctrl_z", "space", "tab" })
            {
                // The note is the sole window of the application named (its process showed no other): text and Enter,
                // Space or Tab go at its caret as before; what selects, erases or replaces does not.
                if (key is not ("enter" or "space" or "tab"))
                {
                    Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = key }, note, state, "Notas rápidas"),
                        Is.False, key);
                }

                Assert.That(ComputerUseMission.RefusalForTheModel("input.key.press", new JsonObject { ["key"] = key }, "rule", [], 1),
                    Is.Null, key);
            }

            Assert.That(ComputerUseMission.RefusalForTheModel("input.text.type", new JsonObject { ["text"] = "dentista" }, "rule", [], 1),
                Is.Null, "a text");
            Assert.That(ComputerUseMission.RefusalForTheModel("input.visible.click", new JsonObject { ["label"] = "Borrar todo" }, "rule", [], 1),
                Is.Null, "a click on an erasing command");
            // The same key refused twice in the sub-goal ends it.
            var earlier = new JsonArray(new JsonObject { ["operation"] = "input.key.press", ["key"] = "ctrl_k", ["ok"] = false, ["refused"] = true });
            Assert.That(ComputerUseMission.RefusalForTheModel("input.key.press", ctrlK, "rule", earlier, 2), Is.Null);
        });
    }

    [Test]
    public void ContracaseTheThesisInWordKeepsEveryRefusalAndItsErasingClicks()
    {
        // Ronda 21 contracase: Word's document is no read-only page: the chords that format it (Ctrl+T, Ctrl+L) and every
        // key that selects, erases or writes are refused on the person's thesis; a click on «Borrar todo» too.
        (JsonObject thesis, JsonObject state) = ThesisTied(LongTwoRequest, 1001);
        Assert.Multiple(() =>
        {
            foreach (string key in new[] { "ctrl_a", "delete", "backspace", "enter", "ctrl_t", "ctrl_l", "ctrl_k" })
            {
                Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = key }, thesis, state, "Word"),
                    Is.False, key);
            }

            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", new JsonObject { ["text"] = "hola" }, thesis, state, "Word"), Is.False);
            Assert.That(ComputerUseMission.BindToMissionWindow("input.visible.click", new JsonObject { ["label"] = "Borrar todo", ["index"] = 12 }, thesis, state, "Word"),
                Is.False);
        });
    }

    [Test]
    public void TheContentKeyClassesAreKeysOfTheCatalogsRepertoire()
    {
        Assert.Multiple(() =>
        {
            foreach (string name in new[] { "keeping", "container", "altering", "paste", "copy", "unseenEffect", "writtenEffect" })
            {
                Assert.That(OperationFloor.ContentKeyClass(name), Is.Not.Empty, name);
                foreach (string key in OperationFloor.ContentKeyClass(name))
                {
                    Assert.That(MindPlanBoundary.ArgumentsSatisfyExactSchema("input.key.press", new JsonObject { ["key"] = key }), Is.True,
                        $"{name}: {key}");
                }
            }

            Assert.That(OperationFloor.ContentKeyClass("keeping").Intersect(OperationFloor.ContentKeyClass("altering")), Is.Empty);
            // Review 4 of ronda 24: the keys whose effect lands on the written text are keys the signature does not see.
            Assert.That(OperationFloor.ContentKeyClass("writtenEffect").IsSubsetOf(OperationFloor.ContentKeyClass("unseenEffect")), Is.True);
        });
    }

    // Revisión 1, hallazgo a: the person's Edge with a web mail draft, looked at without the front (no focus known):
    // the page's document read-only, the draft's body an Edit smaller than a quarter of the window.
    private static (JsonObject Page, JsonObject State) PersonsEdgeWithASmallDraftAndNoFocus()
    {
        (JsonObject page, JsonObject state) = PersonsEdge();
        JsonArray controls = (JsonArray)page["controls"]!;
        controls[2]!["state"] = "readonly";
        JsonObject body = Control(3, "Edit", "Cuerpo del mensaje", "", "Hola, te escribo por la reunión");
        body["rect"] = new JsonObject { ["x"] = 300, ["y"] = 200, ["w"] = 700, ["h"] = 300 };
        controls.Add((JsonNode?)body);
        page["window"]!["focused"] = null;
        return (page, state);
    }

    [Test]
    public void FindingAWithTheFocusUnknownAReadOnlyPageStillCountsAsContent()
    {
        (JsonObject page, JsonObject state) = PersonsEdgeWithASmallDraftAndNoFocus();
        Assert.Multiple(() =>
        {
            foreach (string key in new[] { "backspace", "ctrl_x", "ctrl_v", "ctrl_z", "delete", "ctrl_a" })
            {
                Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.key.press", new JsonObject { ["key"] = key }, page, state),
                    Is.True, key);
                Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = key }, page, state, "Microsoft Edge"),
                    Is.False, key);
            }

            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", new JsonObject { ["text"] = "hola" }, page, state),
                Is.True, "a text with no field named goes where the keyboard is");
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.key.press", new JsonObject { ["key"] = "ctrl_f" }, page, state),
                Is.False, "the find alters nothing");
        });
    }

    [Test]
    public void ContracaseFindingAAKnownFocusOnTheReadOnlyPageKeepsItsExemption()
    {
        // The same page with the keyboard known to be on its read-only document: the new tab is no act on content.
        (JsonObject page, JsonObject state) = PersonsEdgeWithASmallDraftAndNoFocus();
        page["window"]!["focused"] = new JsonObject { ["i"] = 2, ["kind"] = "Document", ["name"] = "Encontrar información" };
        Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.key.press", new JsonObject { ["key"] = "ctrl_t" }, page, state),
            Is.False);
        // A text typed into the large draft by its index is still refused.
        ((JsonObject)((JsonArray)page["controls"]!)[3]!)["rect"] = new JsonObject { ["x"] = 300, ["y"] = 200, ["w"] = 1000, ["h"] = 600 };
        Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", new JsonObject { ["text"] = "hola", ["index"] = 3 }, page, state),
            Is.True);
    }

    [TestCase("input.key.press", "ctrl_t", "computer_use_document_not_named_container")]
    [TestCase("input.key.press", "Ctrl L", "computer_use_document_not_named_container")]
    [TestCase("input.key.press", "ctrl_k", "computer_use_document_not_named_key")]
    [TestCase("input.key.press", "ctrl_b", "computer_use_document_not_named_key")]
    [TestCase("input.key.press", "ctrl_a", "computer_use_document_not_named")]
    [TestCase("input.key.press", "backspace", "computer_use_document_not_named")]
    [TestCase("input.text.type", null, "computer_use_document_not_named")]
    [TestCase("input.visible.click", null, "computer_use_document_not_named")]
    public void FindingBTheStopSaysTheCauseOfTheRefusedAct(string operation, string? key, string cause)
    {
        var arguments = key is null ? new JsonObject { ["text"] = "hola", ["label"] = "Borrar todo" } : new JsonObject { ["key"] = key };
        Assert.That(ComputerUseMission.ForeignDocumentCause(operation, arguments), Is.EqualTo(cause));
    }

    [Test]
    public async Task FindingBTheModelsNewTabOnThePersonsThesisStopsWithThatCause()
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject thesis = OwnersThesis(born: false);
                thesis["window"]!["others"] = new JsonArray(1001L);
                return thesis;
            },
            Mind = _ => Step("input.key.press", new JsonObject { ["key"] = "ctrl_t" }),
        };
        var arguments = new JsonObject { ["goal"] = "ponelo en negrita", ["application"] = "Word" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(LongTwoRequest, arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        JsonObject Outcome(string error) => new()
        {
            ["kind"] = "operation",
            ["operation"] = "mission.computer.use",
            ["polarity"] = "failure",
            ["verified"] = false,
            ["succeeded"] = false,
            ["error"] = error,
            ["observed"] = observed.DeepClone(),
        };
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Is.Empty);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_document_not_named_container"));
            string? spanish = OperationFloor.Final(Outcome("computer_use_document_not_named_container"), english: false);
            Assert.That(spanish, Does.Contain("pestaña nueva"));
            Assert.That(spanish, Does.Not.Contain("borré"));
            string? english = OperationFloor.Final(Outcome("computer_use_document_not_named_container"), english: true);
            Assert.That(english, Does.Contain("new-tab"));
            Assert.That(english, Does.Not.Contain("erased"));
        });
    }

    [Test]
    public void FindingBARefusedKeyIsSpentOnItsApplicationForTheLaterSubgoals()
    {
        JsonObject refused = ComputerUseMission.RefusalForTheModel("input.key.press", new JsonObject { ["key"] = "ctrl_k" }, "rule", [], 1)!;
        refused["process"] = "Microsoft.Notes";
        var steps = new JsonArray
        {
            refused,
            new JsonObject { ["step"] = 2, ["operation"] = "input.key.press", ["key"] = "ctrl_f", ["ok"] = true },
        };
        Assert.Multiple(() =>
        {
            // A later sub-goal: the refused key comes as spent on that application.
            JsonArray later = ComputerUseMission.HistoryForMind(steps, 2);
            Assert.That(later.Count, Is.EqualTo(1));
            Assert.That((bool?)later[0]!["spent"], Is.True);
            Assert.That((string?)later[0]!["key"], Is.EqualTo("ctrl_k"));
            Assert.That((string?)later[0]!["process"], Is.EqualTo("Microsoft.Notes"));
            // Contracase: in its own sub-goal it is the refused step itself, never a spent one.
            JsonArray own = ComputerUseMission.HistoryForMind(steps, 0);
            Assert.That((bool?)own[0]!["refused"], Is.True);
            Assert.That(own[0]!["spent"], Is.Null);
            // Contracase: a key pressed with no refusal and no Escape after it is spent nowhere.
            Assert.That(ComputerUseMission.SpentKey(steps, 1), Is.Null);
        });
    }

    private static JsonObject BornWindow(string title, long hwnd, long? personNearAgoMs = null)
    {
        JsonObject view = Window(title, "chrome", 90, true, [Control(0, "Document", title)]);
        view["window"]!["hwnd"] = hwnd;
        view["window"]!["root"] = hwnd;
        view["window"]!["born"] = true;
        if (personNearAgoMs is long ago)
        {
            view["window"]!["personNearAgoMs"] = ago;
        }

        return view;
    }

    [TestCase(500L, false, "person_since_act")]
    [TestCase(9000L, true, "created")]
    [TestCase(null, true, "created")]
    public void AWindowThePersonBroughtAfterTheMissionsActIsNotTheMissions(long? personNearAgoMs, bool keeps, string why)
    {
        // Finding 1 (the reviewer's reproduction): the browser already running, a verified click on «Buscar», and then a
        // window of its process the person opened (from a folder, the taskbar, its own Ctrl+N): their input reached the
        // process or the shell after the act, so it is theirs. Contracase: their input came before the act.
        JsonObject first = Tied(Window("Google - Google Chrome", "chrome", 90, true, [Control(0, "Button", "Buscar")]), 9001);
        var steps = new JsonArray(
            new JsonObject { ["operation"] = "app.open", ["ok"] = true, ["alreadyRunning"] = true },
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Buscar", ["ok"] = true });
        DateTimeOffset now = DateTimeOffset.UtcNow;
        var state = new JsonObject { ["objective"] = "en Chrome buscá el clima de hoy", ["application"] = "Chrome", ["startedUtc"] = now.AddSeconds(-20).ToString("O") };
        ComputerUseMissionWindow.Tie(state, "Chrome", first, ofTheApplication: true, new JsonArray(steps[0]!.DeepClone()));
        ComputerUseMissionWindow.NoteAct(state, now.AddSeconds(-2));

        JsonObject theirs = BornWindow("Banco Estado - Mi cuenta - Google Chrome", 9002, personNearAgoMs);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.KeepsBorn(state, theirs, steps, now, out string said), Is.EqualTo(keeps));
            Assert.That(said, Is.EqualTo(why));
        });
    }

    [Test]
    public void TLong2TheThesisOpenedByKeyboardOrByALongerLabelIsTheItemNotTheMissions()
    {
        // Finding 2: the recent list showed the thesis (a ListItem of a look); Enter on it, or a click on a label that says
        // more than its name (its extension, its folder), or its name typed into «Abrir» opened it: it is that item, and
        // never the mission's. Contracase: a new document the mission created by its act is its own.
        var state = new JsonObject { ["objective"] = LongTwoRequest, ["application"] = "Word" };
        ComputerUseMissionWindow.Tie(state, "Word", WordBackstageOpen(), ofTheApplication: true, []);
        ComputerUseMissionWindow.NoteItems(state, WordBackstageOpen());
        JsonObject thesis = OwnersThesis(born: true);
        var byKey = new JsonArray(new JsonObject { ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true });
        var byLongLabel = new JsonArray(new JsonObject
        {
            ["operation"] = "input.visible.click",
            ["label"] = "Proyecto_Puente_15_Dias_Desde_Maqueta.docx Documentos",
            ["ok"] = true,
        });
        var typed = new JsonArray(new JsonObject
        {
            ["operation"] = "input.text.type",
            ["text"] = "Proyecto_Puente_15_Dias_Desde_Maqueta.docx",
            ["ok"] = true,
        });
        var bare = new JsonObject { ["objective"] = LongTwoRequest, ["application"] = "Word" };
        ComputerUseMissionWindow.Tie(bare, "Word", WordBackstageOpen(), ofTheApplication: true, []);
        JsonObject created = OwnersThesis(born: true);
        created["window"]!["title"] = "Documento2 - Word";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.KeepsBorn(state, thesis, byKey, DateTimeOffset.UtcNow, out string key), Is.False);
            Assert.That(key, Is.EqualTo("item_opened"));
            Assert.That(ComputerUseMissionWindow.KeepsBorn(bare, thesis, byLongLabel, DateTimeOffset.UtcNow, out string label), Is.False);
            Assert.That(label, Is.EqualTo("item_opened"));
            Assert.That(ComputerUseMissionWindow.KeepsBorn(bare, thesis, typed, DateTimeOffset.UtcNow, out string text), Is.False);
            Assert.That(text, Is.EqualTo("item_opened"));
            Assert.That(ComputerUseMissionWindow.KeepsBorn(state, created, byKey, DateTimeOffset.UtcNow, out string mine), Is.True);
            Assert.That(mine, Is.EqualTo("created"));
        });
    }

    [Test]
    public void H1TheNewWorkbookNamedLikeARecentFileIsTheMissions()
    {
        // Encargo H1 (tandas fin1/fin2 t4-c06 «bro abre excel y crea un blank workbook»): the start page listed the recent
        // «Libro1.xlsx»; the click on «Libro en blanco» made «Libro1 - Excel», which was refused as that recent item
        // (born.refused.item_opened) and the mission stopped as if its window had closed. A title named the way an editor
        // names a new document is the item only by what the mission pressed or typed, or after a key. Contracases: Enter
        // on the listed item, a click on it.
        JsonObject start = Tied(Window("Excel", "EXCEL", 70, true,
            [Control(3, "ListItem", "Inicio", "selected"), Control(12, "ListItem", "Libro en blanco", "selected"),
             Control(20, "ListItem", "Libro1.xlsx"), Control(21, "ListItem", "Presupuesto 2026.xlsx")]), 3001);
        JsonObject Fresh()
        {
            var state = new JsonObject { ["objective"] = "bro abre excel y crea un blank workbook", ["application"] = "Excel" };
            ComputerUseMissionWindow.Tie(state, "Excel", start.DeepClone().AsObject(), ofTheApplication: true, []);
            ComputerUseMissionWindow.NoteItems(state, start);
            return state;
        }

        var opening = new JsonObject
        {
            ["operation"] = "app.open",
            ["ok"] = false,
            ["error"] = "new_document_not_created",
            ["effectUncertain"] = true,
        };
        var blank = new JsonArray(opening.DeepClone(),
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Libro en blanco", ["ok"] = true });
        var byKey = new JsonArray(opening.DeepClone(),
            new JsonObject { ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true });
        var onTheItem = new JsonArray(opening.DeepClone(),
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Libro1.xlsx", ["ok"] = true });
        JsonObject workbook = BornWindow("Libro1 - Excel", 3002);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.KeepsBorn(Fresh(), workbook, blank, DateTimeOffset.UtcNow, out string made), Is.True);
            Assert.That(made, Is.EqualTo("created"));
            Assert.That(ComputerUseMissionWindow.KeepsBorn(Fresh(), workbook, byKey, DateTimeOffset.UtcNow, out string key), Is.False);
            Assert.That(key, Is.EqualTo("item_opened"));
            Assert.That(ComputerUseMissionWindow.KeepsBorn(Fresh(), workbook, onTheItem, DateTimeOffset.UtcNow, out string item), Is.False);
            Assert.That(item, Is.EqualTo("item_opened"));
        });
    }

    [Test]
    public void TLong2ASaveAsDialogThePersonsStrayKeyReachedIsStillTheMissions()
    {
        // Finding 7: the mission's «Guardar como» took the front while the person typed, and their key went into it: it
        // is still the dialog of the mission's window (its owner), kept; a window the person works in that no window of
        // the mission owns is still refused.
        var state = new JsonObject { ["objective"] = LongTwoRequest, ["application"] = "Word" };
        ComputerUseMissionWindow.Tie(state, "Word", WordDocumentOne(), ofTheApplication: true, []);
        JsonObject dialog = Window("Guardar como", "WINWORD", 60, true, [Control(0, "Edit", "Nombre de archivo:", "focused")]);
        dialog["window"]!["hwnd"] = 3003L;
        dialog["window"]!["owner"] = 1001L;
        dialog["window"]!["born"] = true;
        dialog["window"]!["personInputAgoMs"] = 20;
        JsonObject theirs = dialog.DeepClone().AsObject();
        theirs["window"]!["owner"] = 2002L;
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.KeepsBorn(state, dialog, [], DateTimeOffset.UtcNow, out string why), Is.True);
            Assert.That(why, Is.EqualTo("owned"));
            Assert.That(ComputerUseMissionWindow.KeepsBorn(state, theirs, [], DateTimeOffset.UtcNow, out string person), Is.False);
            Assert.That(person, Is.EqualTo("person"));
        });
    }

    [TestCase("en mi archivo notas escribí hola", "notas.txt - Bloc de notas", null, true)]
    [TestCase("en mi documento Tesis poné el título en negrita", "Tesis.docx - Word", null, true)]
    [TestCase("en mi documento Tesis poné el título en negrita", "Tesis • Guardado - Word", null, true)]
    [TestCase("abrí Word y escribí hola", "Word", "Word", false)]
    [TestCase("en el correo escribile a Ana", "Correo", "Correo", false)]
    [TestCase("en mi archivo notas escribí hola", "presupuesto.txt - Bloc de notas", null, false)]
    public void TheRequestNamesAWindowByItsDocumentNotByTheApplication(string objective, string title, string? application, bool named)
    {
        // Finding 8: the extension and a « • state» segment are no word the person has to say; a title that is only the
        // application's own name is no document the request names.
        Assert.That(ComputerUseMissionWindow.NamedByObjective(objective, title, application), Is.EqualTo(named));
    }

    [Test]
    public async Task TLong2EndToEndTheThesisTiedBesideDocumentOneStopsWithItsCause()
    {
        // Finding 9: end to end, the mission tied to the owner's thesis (Word's process showing Documento1 too) and the
        // model's Ctrl+A on it: nothing is pressed, and the mission stops with the cause the final says.
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject thesis = OwnersThesis(born: false);
                thesis["window"]!["others"] = new JsonArray(1001L);
                return thesis;
            },
            Mind = _ => Step("input.key.press", new JsonObject { ["key"] = "ctrl_a" }),
        };
        var arguments = new JsonObject { ["goal"] = "ponelo en negrita", ["application"] = "Word" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(LongTwoRequest, arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Is.Empty);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_document_not_named"));
            Assert.That(OperationFloor.Final(
                    new JsonObject
                    {
                        ["kind"] = "operation",
                        ["operation"] = "mission.computer.use",
                        ["polarity"] = "failure",
                        ["verified"] = false,
                        ["succeeded"] = false,
                        ["error"] = "computer_use_document_not_named",
                        ["observed"] = observed.DeepClone(),
                    },
                    english: false),
                Does.Contain("no lo abrí ni lo creé en este pedido y no me lo nombraste"));
        });
    }

    [Test]
    public void ADocumentTheMissionOpenedCold()
    {
        // Contracase: Documento1 in the Word the mission started (app.open, not already running) is its own: Ctrl+A there.
        JsonObject documentOne = WordDocumentOne();
        documentOne["window"]!["others"] = new JsonArray(2002L);
        var state = new JsonObject { ["objective"] = LongTwoRequest, ["application"] = "Word" };
        var steps = new JsonArray(new JsonObject { ["operation"] = "app.open", ["ok"] = true, ["alreadyRunning"] = false });
        ComputerUseMission.AdoptWindow(state, "Word", documentOne);
        ComputerUseMissionWindow.Tie(state, "Word", documentOne, ofTheApplication: true, steps);

        Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject { ["key"] = "ctrl_a" }, documentOne, state, "Word"), Is.True);
    }

    [TestCase(false, true, "created")]
    [TestCase(true, false, "no_act")]
    public void ALaunchersMainWindowAfterItsSplashIsTheMissionsWhenTheMissionStartedIt(bool alreadyRunning, bool keeps, string why)
    {
        // Review of ventana-misión: a launcher the mission started replaces its splash (the window the mission took)
        // with its main window, with no act in between: the start was the mission's act, so the window is its own. An
        // application already running that shows a new window by itself is not.
        JsonObject splash = Tied(Window("Iniciar sesión en Steam", "steam", 80, true, [Control(0, "Button", "Iniciar sesión")]), 8001);
        var steps = new JsonArray(new JsonObject { ["operation"] = "app.open", ["ok"] = true, ["alreadyRunning"] = alreadyRunning });
        var state = new JsonObject { ["objective"] = "abrí steam y andá a la biblioteca", ["application"] = "Steam" };
        ComputerUseMissionWindow.Tie(state, "Steam", splash, ofTheApplication: true, steps);
        JsonObject main = Window("Tienda", "steam", 80, true, [Control(0, "Button", "Biblioteca")]);
        main["window"]!["hwnd"] = 8002L;
        main["window"]!["born"] = true;

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.KeepsBorn(state, main, steps, DateTimeOffset.UtcNow, out string said), Is.EqualTo(keeps));
            Assert.That(said, Is.EqualTo(why));
        });
    }

    // Pasada r15b (t-form-1, t-long-3): the opener of a form is closed by the form an act of it brought up (check atom
    // appeared:), and so is a free sub-goal once its act brought up the control the next sub-goal checks; the next
    // sub-goal goes on. Contracases: the option shown from the start (a panel always there) closes neither, and the
    // model is asked again on the opener. Review of cierre-de-subobjetivos (finding 3): a free sub-goal with an effect
    // of its own (a drawing) is never closed by what its act brought up.
    [TestCase("appeared:pixeles|appeared:horizontal&appeared:vertical", false, true, Opener)]
    [TestCase("appeared:pixeles|appeared:horizontal&appeared:vertical", true, false, Opener)]
    [TestCase(null, false, true, Opener)]
    [TestCase(null, true, false, Opener)]
    [TestCase(null, false, true, "ir a la pestaña Imagen")]
    [TestCase(null, false, false, "dibujá una línea")]
    public async Task AFormOpenerClosesOnWhatItsActBroughtUp(string? openerCheck, bool shownFromStart, bool closes, string openerGoal)
    {
        var harness = new Harness();
        harness.Screen = _ =>
        {
            JsonArray controls = [Control(0, "Button", "Cambiar de tamaño y sesgar")];
            if (shownFromStart || harness.Acts.Count > 0)
            {
                controls.Add(Control(1, "RadioButton", "Píxeles"));
                controls.Add(Control(2, "Edit", "Horizontal", value: "1152"));
                controls.Add(Control(3, "Edit", "Vertical", value: "648"));
            }

            return Window("Sin título - Paint", "mspaint", 41, true, controls);
        };
        harness.Mind = request => (request.Subgoal, request.History.Count) switch
        {
            (0, 0) => new MindComputerUseStep(
                "input.visible.click", new JsonObject { ["label"] = "Cambiar de tamaño y sesgar", ["index"] = 0 }, "abro", Source: "model"),
            _ => new MindComputerUseStep("none", new JsonObject(), "no veo cómo seguir", "no_step_visible"),
        };
        var arguments = new JsonObject
        {
            ["goal"] = "cambiale el tamaño a la imagen",
            ["steps"] = new JsonArray
            {
                new JsonObject { ["goal"] = openerGoal, ["application"] = "Paint", ["successCheck"] = openerCheck },
                new JsonObject { ["goal"] = "activar pixeles", ["application"] = "Paint", ["successCheck"] = "control:pixeles:on|control:pixeles:selected" },
            },
        };

        await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Paint cambiale el tamaño a la imagen", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Count(act => act.Operation == "input.visible.click"), Is.EqualTo(1));
            Assert.That(harness.Requests.Any(request => request.Subgoal == 1), Is.EqualTo(closes));
            Assert.That(harness.Requests.Any(request => request.Subgoal == 0 && request.History.Count == 1), Is.EqualTo(!closes));
        });
    }

    private const string Opener = "abrir donde se ponen ancho (800) y alto (600)";

    [Test]
    public void AppearedHoldsOnlyForAControlAnActOfTheSubgoalBroughtUp()
    {
        JsonObject view = Window("Sin título - Paint", "mspaint", 41, true, [Control(0, "RadioButton", "Píxeles"), Control(1, "Edit", "Horizontal")]);
        var brought = new JsonArray { new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["appeared"] = new JsonArray("pixeles", "horizontal") } };
        var already = new JsonArray { new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["appeared"] = new JsonArray() } };
        var failed = new JsonArray { new JsonObject { ["operation"] = "input.visible.click", ["ok"] = false, ["appeared"] = new JsonArray("pixeles") } };
        JsonObject gone = Window("Sin título - Paint", "mspaint", 41, true, [Control(0, "Button", "Lápiz")]);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("appeared:pixeles", view, brought, out string? by), Is.True);
            Assert.That(by, Is.EqualTo("appeared:pixeles"));
            // An Edit counts: the form's field is what shows it open.
            Assert.That(ComputerUseSuccessCheck.Evaluate("appeared:horizontal", view, brought, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("appeared:pixeles", view, already, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("appeared:pixeles", view, failed, out _), Is.False);
            // What appeared and is gone again proves nothing on this look.
            Assert.That(ComputerUseSuccessCheck.Evaluate("appeared:pixeles", gone, brought, out _), Is.False);
            // The next sub-goal's control: brought up, and not on the sub-goal's first look.
            Assert.That(ComputerUseSuccessCheck.NextSubgoalBroughtUp("control:pixeles:selected", view, brought, "sin titulo - paint\nlapiz\n"),
                Is.EqualTo("appeared:pixeles"));
            Assert.That(ComputerUseSuccessCheck.NextSubgoalBroughtUp("control:pixeles:selected", view, brought, "sin titulo - paint\npixeles\n"),
                Is.Null);
            Assert.That(ComputerUseSuccessCheck.NextSubgoalBroughtUp("value:ancho=800", view, brought, null), Is.Null);
        });
    }

    // Review of cierre-de-subobjetivos (finding 5): appeared: is the control's whole name (a label's colon aside), never
    // a menu entry that only contains it; and a list's entries never push a form's field out of the names kept.
    [Test]
    public void AppearedIsTheWholeNameAndAListNeverHidesTheField()
    {
        JsonObject flip = Window("Sin título - Paint", "mspaint", 41, true,
            [Control(0, "MenuItem", "Voltear horizontal"), Control(1, "MenuItem", "Voltear vertical")]);
        var flipped = new JsonArray { new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["appeared"] = new JsonArray("voltear horizontal", "voltear vertical") } };

        JsonArray before = [Control(0, "Button", "Fuente")];
        JsonArray after = [Control(0, "Button", "Fuente")];
        for (int index = 1; index <= 40; index++)
        {
            after.Add(Control(index, "ListItem", $"Fuente {index}"));
        }

        after.Add(Control(41, "Edit", "Tamaño:"));
        var state = new JsonObject();
        var steps = new JsonArray();
        ComputerUseMission.MarkAppeared(state, steps, 0, Window("Documento1 - Word", "winword", 41, true, before));
        steps.Add(new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true });
        JsonObject dialog = Window("Fuente", "winword", 41, true, after);
        ComputerUseMission.MarkAppeared(state, steps, 0, dialog);

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("appeared:horizontal&appeared:vertical", flip, flipped, out _), Is.False);
            Assert.That(((JsonArray)steps[0]!["appeared"]!).Select(node => (string?)node), Does.Contain("tamano:"));
            Assert.That(ComputerUseSuccessCheck.Evaluate("appeared:tamano", dialog, steps, out _), Is.True);
        });
    }

    // Ronda 19b (r15b v3-34, v3-35): after app.open the mission tied itself to the application's first window, which
    // closed; every look then failed «mission_window_closed» (ten looks of 2 s until StartWait) and the turn said «la
    // ventana no se dejó leer». A scripted application whose first window (hwnd 100) gives way to another (hwnd 200):
    // «closesAgain» closes that one too, «alreadyRunning» says the opening reused a running application.
    private sealed record ClosingRun(Harness Harness, JsonObject Observed, int ClosedLooks, int UntiedLooksAfterClosing);

    private static bool Shows(ComputerUseStepRequest request, string name) =>
        request.View["controls"] is JsonArray controls && controls.OfType<JsonObject>().Any(control => (string?)control["name"] == name);

    private async Task<ClosingRun> RunOnAClosingWindowAsync(bool closesAgain, bool alreadyRunning)
    {
        bool open = false;
        int untiedLooks = 0;
        int closedLooks = 0;
        int untiedAfterClosing = 0;
        // The mind sees no window handle: each window names its one control after it.
        JsonObject Of(long hwnd) => InWindow(hwnd, Window("Notas rápidas", "notes", 12, true, [Control(0, "Edit", $"Nota {hwnd}")]));
        var harness = new Harness
        {
            Screen = look =>
            {
                if (!open)
                    return Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Document", "Texto")]);
                long[] windows = look["windows"] is JsonArray tied ? [.. tied.Select(node => (long)node!)] : [];
                if (windows.Length == 0)
                {
                    untiedAfterClosing += closedLooks > 0 ? 1 : 0;
                    return Of(++untiedLooks == 1 ? 100 : 200);
                }

                if (windows.Contains(100) || closesAgain)
                {
                    closedLooks++;
                    return new JsonObject { ["failWith"] = "mission_window_closed" };
                }

                return Of(200);
            },
        };
        harness.Mind = request => request.History.Count == 0
            ? Step("app.open", new JsonObject { ["appId"] = "Notas rápidas" })
            : Shows(request, "Nota 100") && alreadyRunning
                ? Step("input.visible.click", new JsonObject { ["label"] = "Nota 100" })
                : Step("none", new JsonObject());
        harness.Receipt = (operation, _) =>
        {
            open = true;
            var receipt = new JsonObject { ["processId"] = 12, ["surfaceChanged"] = true };
            if (operation == "app.open" && alreadyRunning)
                receipt["alreadyRunning"] = true;
            return receipt;
        };
        var arguments = new JsonObject { ["goal"] = "escribir una nota", ["application"] = "Notas rápidas", ["successCheck"] = "control:zzzz" };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en notas rápidas escribí una nota", arguments), arguments, CancellationToken.None);
        return new ClosingRun(harness, Observed(result), closedLooks, untiedAfterClosing);
    }

    [Test]
    public async Task AWindowThatClosedRightAfterTheOpeningIsTiedAgainOnceToTheApplicationsWindow()
    {
        ClosingRun run = await RunOnAClosingWindowAsync(closesAgain: false, alreadyRunning: false);

        Assert.Multiple(() =>
        {
            Assert.That(run.ClosedLooks, Is.EqualTo(1), "one closed look, never ten");
            Assert.That(run.UntiedLooksAfterClosing, Is.EqualTo(1), "one look of the application that names no window");
            Assert.That(run.Harness.Requests, Has.Count.EqualTo(2));
            Assert.That(Shows(run.Harness.Requests[^1], "Nota 200"), Is.True, "decided on the new window");
            Assert.That((string?)run.Observed["stoppedBy"], Is.Not.EqualTo("computer_use_view_unavailable"));
            Assert.That((string?)run.Observed["stoppedBy"], Is.Not.EqualTo("computer_use_window_closed"));
        });
    }

    // Counter-case: tied again once only; a second closing stops at once with its own cause, not «no se dejó leer».
    [Test]
    public async Task AWindowThatClosesAgainStopsTheMissionWithItsOwnCause()
    {
        ClosingRun run = await RunOnAClosingWindowAsync(closesAgain: true, alreadyRunning: false);

        Assert.Multiple(() =>
        {
            Assert.That((string?)run.Observed["stoppedBy"], Is.EqualTo("computer_use_window_closed"));
            Assert.That(run.ClosedLooks, Is.EqualTo(2), "the first closing ties it again, the second stops");
            Assert.That(run.UntiedLooksAfterClosing, Is.EqualTo(1));
            Assert.That(run.Harness.Looks, Has.Count.LessThanOrEqualTo(5), "no wait on a closed window until StartWait");
        });
    }

    // Counter-case: an application that was already running may show the person's own windows; its closed window is
    // never replaced by a look that names no window: the mission stops, its window closed.
    [Test]
    public async Task AClosedWindowOfAnApplicationAlreadyRunningIsNeverTiedAgain()
    {
        ClosingRun run = await RunOnAClosingWindowAsync(closesAgain: false, alreadyRunning: true);

        Assert.Multiple(() =>
        {
            Assert.That((string?)run.Observed["stoppedBy"], Is.EqualTo("computer_use_window_closed"));
            Assert.That(run.ClosedLooks, Is.EqualTo(1));
            Assert.That(run.UntiedLooksAfterClosing, Is.Zero);
        });
    }

    // Review of ronda 19b (finding 1): tied again with a look that names no window, the provider may read the person's
    // window of the same process the mission refused before, one titled like the application the person works in, or,
    // with none, the window in front. None of them is the mission's: it stops, its window closed, and the model never
    // sees them. «refused»: the person's window 300 came during the mission (refused while they typed in it) and is read
    // after the closing without fresh input; «person»: a window of the process the person types in; «front»: another
    // program's window in front.
    private async Task<(Harness Harness, JsonObject Observed, int UntiedLooksAfterOpening)> RunRetiedOnAWindowNotTheMissionsAsync(
        string after)
    {
        bool open = false;
        int untiedLooks = 0;
        JsonObject Of(long hwnd, string title = "Notas rápidas", string process = "notes", int processId = 12, bool requested = true) =>
            InWindow(hwnd, Window(title, process, processId, requested, [Control(0, "Edit", $"Nota {hwnd}")]));
        JsonObject AfterClosing()
        {
            JsonObject view = after switch
            {
                "refused" => Of(300),
                "person" => Of(400),
                _ => Of(500, "Bandeja de entrada", "mail", 50, requested: false),
            };
            if (after == "person")
                view["window"]!["personInputAgoMs"] = 40;
            return view;
        }

        var harness = new Harness
        {
            Screen = look =>
            {
                if (!open)
                    return Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Document", "Texto")]);
                if (look["windows"] is not JsonArray { Count: > 0 } windows)
                    return untiedLooks++ == 0 ? Of(100) : AfterClosing();
                // A mission tied to the window read after the closing reads it again (it is still open).
                if (windows.Any(node => (long?)node == (long?)AfterClosing()["window"]!["hwnd"]))
                    return AfterClosing();
                bool knowsTheirs = look["known"] is JsonArray known && known.Any(node => (long?)node == 300);
                if (after == "refused" && !knowsTheirs)
                {
                    JsonObject theirs = Of(300);
                    theirs["window"]!["born"] = true;
                    theirs["window"]!["personInputAgoMs"] = 40;
                    return theirs;
                }

                return new JsonObject { ["failWith"] = "mission_window_closed" };
            },
        };
        harness.Mind = request => request.History.Count == 0
            ? Step("app.open", new JsonObject { ["appId"] = "Notas rápidas" })
            : Step("input.text.type", new JsonObject { ["text"] = "hola" });
        harness.Receipt = (_, _) =>
        {
            open = true;
            return new JsonObject { ["processId"] = 12, ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "escribir una nota", ["application"] = "Notas rápidas", ["successCheck"] = "control:zzzz" };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en notas rápidas escribí una nota", arguments), arguments, CancellationToken.None);
        return (harness, Observed(result), untiedLooks);
    }

    [TestCase("refused")]
    [TestCase("person")]
    [TestCase("front")]
    public async Task AWindowTiedAgainIsNeverThePersonsNorTheOneInFront(string after)
    {
        (Harness harness, JsonObject observed, int untiedLooks) = await RunRetiedOnAWindowNotTheMissionsAsync(after);
        string[] theirs = ["Nota 300", "Nota 400", "Nota 500"];
        int looksAtStop = harness.Looks.Count;

        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_window_closed"));
            Assert.That(harness.Requests.Any(request => theirs.Any(name => Shows(request, name))), Is.False,
                "the model never sees the person's window nor the one in front");
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "app.open" }), "nothing done there");
            if (after == "front")
            {
                // Review 2 of ronda 21 (objective e): another program's window in front is no window of the application,
                // which may still be coming; it is looked for again, bounded by StartWait, and never shown meanwhile.
                int waits = (int)(ComputerUseMission.StartWait / ComputerUseMission.RetiePause);
                Assert.That(untiedLooks, Is.EqualTo(2 + waits), "the application's first look, then one a pause for StartWait");
                Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.RetiePause), Is.EqualTo(waits));
                Assert.That(looksAtStop, Is.LessThanOrEqualTo(6 + waits));
            }
            else
            {
                Assert.That(untiedLooks, Is.EqualTo(2),
                    "the application's first look and the one after the closing; no later look reads whatever is there instead");
                Assert.That(looksAtStop, Is.LessThanOrEqualTo(6));
            }
        });
    }

    // Review 2 of ronda 21 (objective e, v3-34): «Notas rápidas» opened cold shows a splash (hwnd 100) that closes; the
    // application's window (hwnd 200 of its process 12) comes a moment later, and meanwhile a look that names no window
    // reads another program's window in front (hwnd 500, mail, not requested). The front is never shown nor kept: the
    // window of the application is waited for, and the mission goes on in it. Counter-case: the person's window of the
    // same process (AWindowTiedAgainIsNeverThePersonsNorTheOneInFront, «refused» and «person») still stops at once.
    [TestCase(1)]
    [TestCase(2)]
    public async Task AWindowTiedAgainWaitsForTheApplicationsWindowPastTheOneInFront(int frontLooks)
    {
        bool open = false;
        int untiedLooks = 0;
        int frontSeen = 0;
        JsonObject Of(long hwnd) => InWindow(hwnd, Window("Notas rápidas", "notes", 12, true, [Control(0, "Edit", $"Nota {hwnd}")]));
        var harness = new Harness
        {
            Screen = look =>
            {
                if (!open)
                    return Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Document", "Texto")]);
                long[] windows = look["windows"] is JsonArray tied ? [.. tied.Select(node => (long)node!)] : [];
                if (windows.Length == 0)
                {
                    if (untiedLooks++ == 0)
                        return Of(100);
                    if (frontSeen++ < frontLooks)
                        return InWindow(500, Window("Bandeja de entrada", "mail", 50, false, [Control(0, "Edit", "Nota 500")]));
                    return Of(200);
                }

                return windows.Contains(100) ? new JsonObject { ["failWith"] = "mission_window_closed" } : Of(200);
            },
        };
        harness.Mind = request => request.History.Count == 0
            ? Step("app.open", new JsonObject { ["appId"] = "Notas rápidas" })
            : Step("none", new JsonObject());
        harness.Receipt = (_, _) =>
        {
            open = true;
            return new JsonObject { ["processId"] = 12, ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "escribir una nota", ["application"] = "Notas rápidas", ["successCheck"] = "control:zzzz" };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en notas rápidas escribí una nota", arguments), arguments, CancellationToken.None);
        JsonObject observed = Observed(result);

        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.Not.EqualTo("computer_use_window_closed"));
            Assert.That((string?)observed["stoppedBy"], Is.Not.EqualTo("computer_use_view_unavailable"));
            Assert.That(harness.Requests, Has.Count.EqualTo(2));
            Assert.That(Shows(harness.Requests[^1], "Nota 200"), Is.True, "decided on the application's window");
            Assert.That(harness.Requests.Any(request => Shows(request, "Nota 500")), Is.False, "the window in front is never shown");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.RetiePause), Is.EqualTo(frontLooks));
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "app.open" }));
        });
    }

    // Ronda 19b (r17 t2-c03): «abre configuracion…» with the person's Task Manager in front (raised, not the mission's
    // application) stopped before opening anything: «esa aplicación corre como administrador». The raised window of
    // another program leaves the opening to go on; the application's own raised window keeps the limit.
    private static JsonObject Raised(JsonObject view)
    {
        view["window"]!["elevated"] = true;
        return view;
    }

    private async Task<(Harness Harness, JsonObject Observed)> RunOverARaisedWindowAsync(
        bool raisedIsTheApplication, string decided)
    {
        bool open = false;
        var harness = new Harness
        {
            Screen = _ => raisedIsTheApplication
                ? Raised(Window("Configuración", "SystemSettings", 12, true, [Control(0, "ListItem", "Sistema")]))
                : open
                    ? Window("Configuración", "SystemSettings", 12, true, [Control(0, "ListItem", "Sistema")])
                    : Raised(Window("Administrador de tareas", "Taskmgr", 50, false, [Control(0, "Button", "Procesos")])),
        };
        harness.Mind = request => request.History.Count == 0
            ? Step(decided, decided == "app.open"
                ? new JsonObject { ["appId"] = "Configuración" }
                : new JsonObject { ["label"] = "Procesos" })
            : Step("none", new JsonObject());
        harness.Receipt = (_, _) =>
        {
            open = true;
            return new JsonObject { ["processId"] = 12, ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "ver la pantalla", ["application"] = "Configuración", ["successCheck"] = "control:zzzz" };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abre configuracion que quiero ver lo de la pantalla", arguments), arguments,
            CancellationToken.None);
        return (harness, Observed(result));
    }

    [Test]
    public async Task AnotherProgramsRaisedWindowInFrontLeavesTheApplicationToBeOpened()
    {
        (Harness harness, JsonObject observed) = await RunOverARaisedWindowAsync(raisedIsTheApplication: false, "app.open");

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "app.open" }));
            Assert.That((string?)observed["stoppedBy"], Does.Not.StartWith("computer_use_window_elevated"));
            Assert.That(harness.Requests, Has.Count.EqualTo(2), "decided again on the opened application");
            Assert.That((string?)harness.Requests[^1].View["window"]?["title"], Is.EqualTo("Configuración"));
        });
    }

    // Counter-case: on another program's raised window nothing but the opening is done, and its limit is not said of the
    // application: a click there stops with «the window in front was not the application's».
    [Test]
    public async Task OnAnotherProgramsRaisedWindowNoActIsDoneNorTheApplicationBlamed()
    {
        (Harness harness, JsonObject observed) = await RunOverARaisedWindowAsync(raisedIsTheApplication: false, "input.visible.click");

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Is.Empty);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_window_not_application"));
        });
    }

    // Counter-case: the mission's own application running as administrator keeps the honest limit, before any step.
    [Test]
    public async Task TheApplicationsOwnRaisedWindowKeepsTheElevatedLimit()
    {
        (Harness harness, JsonObject observed) = await RunOverARaisedWindowAsync(raisedIsTheApplication: true, "app.open");

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Is.Empty);
            Assert.That(harness.Requests, Is.Empty);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_window_elevated"));
        });
    }

    // r29 (pasada r27 v3-69, v3-20, v3-22, v3-72; bancos r27 y cd s06): the application of the request (named, or the
    // conversation's: «abre el monitor de recursos» → «ahora anda a la pestaña red») runs as administrator and shows no
    // window BAXY can find, and another window is in front: the person's browser, the simulated user's window, BAXY's
    // own. The mission opens the application, waits for its window and stops with the true cause; the window in front is
    // never read whole, shown to the mind, acted on nor named.
    [TestCase("hello - Búsqueda - Opera", "opera", false, true, "computer_use_window_elevated")]
    [TestCase("BAXY usuario simulado", "python", false, true, "computer_use_window_elevated")]
    [TestCase("BAXY", "Baxy.App", true, true, "computer_use_window_elevated")]
    // Counter-case: the opened application is not raised and still shows no window: said as an application that never
    // showed (estabilización D2, banco h1 s11/u1: before, «the window would not let itself be read»).
    [TestCase("hello - Búsqueda - Opera", "opera", false, false, "computer_use_app_not_shown")]
    public async Task AnApplicationOpenedThatShowsNoWindowStopsWithItsCauseAndNeverTakesTheWindowInFront(
        string frontTitle, string frontProcess, bool frontProtected, bool raised, string stop)
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject front = Window(frontTitle, frontProcess, 9, false,
                    [Control(0, "TabItem", "Red"), Control(1, "Button", "Account"), Control(2, "TabItem", "En directo")]);
                if (frontProtected)
                {
                    front["window"]!["protected"] = true;
                }

                if (raised)
                {
                    front["applicationElevated"] = true;
                }

                return front;
            },
            // Whatever it is shown after the opening, the mind would click the tab of the window it sees.
            Mind = request => request.History.Count == 0
                ? Step("app.open", new JsonObject { ["appId"] = "Monitor de recursos" })
                : Step("input.visible.click", new JsonObject { ["label"] = "Red", ["index"] = 0 }),
            Receipt = (_, _) => new JsonObject { ["processId"] = 77, ["alreadyRunning"] = true },
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a la pestaña red",
            ["application"] = "Monitor de recursos",
            ["successCheck"] = "control:red:selected|title:red",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Monitor de recursos, anda a la pestaña red", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "app.open" }), "no click, key or text anywhere");
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo(stop));
            Assert.That(harness.Requests.All(request => request.View["controls"]!.AsArray().Count == 0), Is.True,
                "the mind never saw the window in front");
            Assert.That(harness.Looks.All(look => (bool?)look["identityIfAbsent"] == true), Is.True,
                "the window in front was never read whole");
            Assert.That(observed["window"], Is.Null, "nothing of the window in front is told");
            Assert.That(observed["steps"]!.AsArray().Select(step => (string?)step!["windowTitle"]), Has.None.EqualTo(frontTitle));
        });
    }

    // The person's browser as the look of v3-69 read it (pasada r27, journal-caso.json: «hello - Búsqueda - Opera»,
    // process opera, behind; the controls the mission pressed there: «Account» twice, «En directo», «Pregunta al asistente»).
    private static JsonObject PersonsBrowserOfV369()
    {
        JsonObject view = Window("hello - Búsqueda - Opera", "opera", 9000, false,
        [
            Control(0, "Document", "Panel de contenido - Sitio Ejemplo", "readonly"),
            Control(1, "Button", "Mostrar menú"),
            Control(6, "Button", "Pregunta al asistente"),
            Control(8, "Button", "Account", "collapsed"),
            Control(20, "TabItem", "Vídeos", "selected"),
            Control(21, "TabItem", "En directo"),
            Control(36, "ComboBox", "Buscar", "collapsed", "los horarios del cercanias de madrid"),
        ], "Aproximadamente 220.000 resultados", "Adele - Hello (Official Music Video) - YouTube");
        view["window"]!["hwnd"] = 133102;
        view["window"]!["foreground"] = false;
        return view;
    }

    // r29, v3-69 whole (pasada r27): «abre el monitor de recursos» → «ahora anda a la pestaña red». The mind now frames the
    // follow-up in the conversation's application (test_cu_v2_seguimiento_en_la_app.py pins these very arguments); the
    // Monitor de recursos runs as administrator and the person's browser is the other window on the desktop. Whether the
    // provider finds the raised window (its look says «elevated») or not (its look says only who is in front, and after
    // the opening that the process is raised), the mission ends with the limit «runs as administrator»: no click, key
    // or text anywhere, the browser never read whole nor shown to the mind, nothing of it in what is told.
    [TestCase(true)]
    [TestCase(false)]
    public async Task TheFollowUpOfV369StopsOnTheRaisedApplicationAndNeverLooksAtThePersonsBrowser(bool raisedWindowFound)
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                if (raisedWindowFound)
                {
                    return Raised(Window("Monitor de recursos", "perfmon", 40436, true, [Control(0, "TabItem", "Red")]));
                }

                JsonObject browser = PersonsBrowserOfV369();
                browser["applicationElevated"] = true;
                return browser;
            },
            // What the mind decided on the browser in the live run, once the application is «open».
            Mind = request => request.History.Count == 0
                ? Step("app.open", new JsonObject { ["appId"] = "Monitor de recursos" })
                : Step("input.visible.click", new JsonObject { ["label"] = "Account", ["index"] = 8, ["manner"] = "open" }),
            Receipt = (_, _) => new JsonObject { ["processId"] = 40436, ["alreadyRunning"] = true },
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a la pestaña red",
            ["application"] = "Monitor de recursos",
            ["successCheck"] = "control:red:selected|title:red",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Monitor de recursos, anda a la pestaña red", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts.Where(act => act.Operation != "app.open"), Is.Empty, "no click, key or text anywhere");
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_window_elevated"));
            Assert.That(harness.Requests.Select(request => request.View["controls"]!.AsArray().Count), Is.All.Zero,
                "the mind never saw a control of the browser");
            Assert.That(raisedWindowFound || harness.Looks.All(look => (bool?)look["identityIfAbsent"] == true), Is.True,
                "the browser was never read whole");
            Assert.That((string?)observed["window"]?["process"], Is.Not.EqualTo("opera"));
            Assert.That((string?)observed["window"]?["title"], Is.Not.EqualTo("hello - Búsqueda - Opera"));
        });
    }

    // r29, review: the mission's own opening failed and left no process, and the look still says only who is in front
    // (tandas b2/c28u t4 t17: the window in front was read whole, 60 controls, and the mind typed there, refused): no
    // window of the mission to look at. It stops with the cause of the opening, the window in front never read whole.
    // Counter-case (u5, n6): an app.open that said false whose window does come goes on in it.
    [TestCase(false, "computer_use_step_failed")]
    [TestCase(true, null)]
    public async Task AFailedOpeningWithNoWindowStopsAndOneWhoseWindowComesGoesOn(bool windowComes, string? stop)
    {
        bool tried = false;
        var harness = new Harness
        {
            Screen = _ => tried && windowComes
                ? Window("Word", "WINWORD", 31, true, [Control(0, "ListItem", "Documento en blanco"), Control(1, "Button", "Abrir")])
                : PersonsBrowserOfV369(),
            Mind = request => request.History.Count == 0
                ? Step("app.open", new JsonObject { ["appId"] = "Word" })
                : Step("input.visible.click", new JsonObject { ["label"] = windowComes ? "Documento en blanco" : "Account", ["index"] = windowComes ? 0 : 8 }),
            Receipt = (operation, _) =>
            {
                if (operation == "app.open")
                {
                    tried = true;
                    return new JsonObject { ["failWith"] = "app_open_unverified" };
                }

                return new JsonObject { ["surfaceChanged"] = true };
            },
        };
        var arguments = new JsonObject { ["goal"] = "elegir documento en blanco", ["application"] = "Word", ["successCheck"] = "control:zzzz", ["budgetSteps"] = 3 };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Word elegí documento en blanco", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            if (windowComes)
            {
                Assert.That(harness.Acts.Select(act => act.Operation), Does.Contain("input.visible.click"), "the application's window is acted on");
                Assert.That((string?)observed["stoppedBy"], Is.Not.EqualTo("computer_use_step_failed"));
            }
            else
            {
                Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "app.open" }));
                Assert.That((string?)observed["stoppedBy"], Is.EqualTo(stop));
                Assert.That(harness.Looks.All(look => (bool?)look["identityIfAbsent"] == true), Is.True, "the window in front was never read whole");
                Assert.That(harness.Requests.Select(request => request.View["controls"]!.AsArray().Count), Is.All.Zero);
                Assert.That(observed["window"], Is.Null);
            }
        });
    }

    // r29, review 2: «escribí hola y andá a la pestaña insertar» as a first message was read whole in «navegador» and
    // the engine typed «hola» (and pressed Enter) in the person's browser, a field of a page holding the keyboard. The
    // mind no longer reads that chain (test_cu_v2_seguimiento_en_la_app.py); what it can still hand the engine is the
    // goal with no application (free_form_arguments: the goal and what it names, «insertar»). Over the person's browser
    // in front, whatever the mind decides there, no text and no key is delivered.
    [TestCase("input.text.type")]
    [TestCase("input.key.press")]
    [TestCase("input.visible.click")]
    public async Task AChainWithATabAndNoApplicationTypesNothingInThePersonsBrowser(string decided)
    {
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject browser = PersonsBrowserOfV369();
                browser["window"]!["foreground"] = true;
                browser["window"]!["focused"] = new JsonObject { ["kind"] = "Edit", ["name"] = "Escribe un mensaje", ["i"] = 5 };
                browser["controls"]!.AsArray().Add(Control(5, "Edit", "Escribe un mensaje", "focused"));
                return browser;
            },
            Mind = _ => decided switch
            {
                "input.text.type" => Step(decided, new JsonObject { ["text"] = "hola" }),
                "input.key.press" => Step(decided, new JsonObject { ["key"] = "enter" }),
                _ => Step(decided, new JsonObject { ["label"] = "Account", ["index"] = 8 }),
            },
        };
        var arguments = new JsonObject
        {
            ["goal"] = "escribí hola y andá a la pestaña insertar",
            ["referentLabels"] = new JsonArray("insertar"),
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("escribí hola y andá a la pestaña insertar", arguments), arguments,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Is.Empty, "nothing is typed, pressed or clicked in the person's browser");
            Assert.That((bool?)Observed(result)["reached"], Is.False);
        });
    }

    // Counter-case of r29: with no opening of its own, the window in front the provider did not resolve for the
    // application is still looked at whole when the mind decides anything but an opening
    // (AnythingButAnOpeningIsDecidedOnTheWindowLookedAtWhole), and an application that does show its window after the
    // opening goes on in it (ALookThatSaysOnlyWhoIsInFrontHoldsNoCheck).

    // Revision 3 of ronda 20b, end to end (v3-52 class): the first look is the application's main window; a click on
    // «Ajustes» opens the dialog (the receipt bears no title, as the provider's), a click on «Vídeo» only selects it
    // and the page beside it still shows General's «Idioma»; then Enter does nothing (its receipt rereads «Ajustes»).
    // The key is measured against the look it was decided on, not against the main window's first title: no arrival.
    [Test]
    public async Task AKeyThatDidNothingAfterTheClickThatOpenedTheDialogIsNoArrival()
    {
        const string Main = "OBS 31.0.0 - Perfil: Sin título - Escenas: Sin título";
        var harness = new Harness();
        harness.Screen = _ =>
        {
            int acts = harness.Acts.Count;
            if (acts == 0)
            {
                return Window(Main, "obs64", 70, true, [Control(0, "Button", "Ajustes"), Control(1, "Button", "Iniciar grabación")]);
            }

            return Window("Ajustes", "obs64", 70, true,
            [
                Control(0, "ListItem", "General", acts == 1 ? "selected" : string.Empty),
                Control(1, "ListItem", "Emisión"),
                Control(2, "ListItem", "Vídeo", acts == 1 ? string.Empty : "selected"),
                Control(3, "ComboBox", "Idioma", value: "Español"),
            ]);
        };
        harness.Mind = request => request.History.Count switch
        {
            0 => Step("input.visible.click", new JsonObject { ["label"] = "Ajustes" }),
            1 => Step("input.visible.click", new JsonObject { ["label"] = "Vídeo" }),
            2 => Step("input.key.press", new JsonObject { ["key"] = "enter" }),
            _ => new MindComputerUseStep("none", new JsonObject(), "no veo cómo seguir", "no_step_visible"),
        };
        harness.Receipt = (operation, arguments) => (operation, (string?)arguments["label"]) switch
        {
            ("input.visible.click", "Ajustes") => new JsonObject
            {
                ["surfaceChanged"] = true,
                ["method"] = "invoke",
                ["cascadeStage"] = "uia",
                ["name"] = "Ajustes",
                ["kind"] = "Button",
            },
            ("input.visible.click", _) => new JsonObject
            {
                ["surfaceChanged"] = false,
                ["method"] = "select",
                ["selected"] = true,
                ["cascadeStage"] = "uia",
                ["name"] = "Vídeo",
                ["kind"] = "ListItem",
            },
            _ => new JsonObject { ["surfaceChanged"] = false, ["windowTitle"] = "Ajustes" },
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a vídeo",
            ["application"] = "OBS",
            ["successCheck"] = "control:video:current",
            ["budgetSteps"] = 5,
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en obs andá a vídeo en ajustes", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.Not.True, observed.ToJsonString());
            Assert.That(harness.Acts.Select(act => act.Operation),
                Is.EqualTo(new[] { "input.visible.click", "input.visible.click", "input.key.press" }), "the scene was played");
        });
    }

    // Ronda 20b, palanca 6, review finding 1 (v3-40 b): a mission that opened Word's «Fuente» list and then stopped left
    // the list open in the person's window. The failed mission collapses what it opened, by the control's identity and
    // its ExpandCollapse, bound to the mission's window; nothing the person opened and no tree branch is touched.
    [Test]
    public async Task AFailedMissionCollapsesTheListItOpenedAndLeftOpen()
    {
        bool open = false;
        int asked = 0;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Window("Documento1 - Word", "WINWORD", 70, true,
                [
                    Control(2, "ComboBox", "Fuente", open ? "expanded" : "collapsed", "Aptos"),
                    Control(3, "ComboBox", "Tamaño de fuente", "expanded", "12"),
                    Control(4, "TreeItem", "Encabezados", "expanded"),
                    Control(9, "Document", "Documento1", "", "Notas de la reunión"),
                ]);
                view["window"]!["hwnd"] = 7070;
                return view;
            },
            Mind = _ => asked++ == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Fuente", ["index"] = 2, ["manner"] = "open" })
                : new MindComputerUseStep("none", new JsonObject(), "no veo cómo seguir", "no_step_visible"),
        };
        harness.Receipt = (_, arguments) =>
        {
            string? manner = (string?)arguments["manner"];
            open = manner == "open" || (open && manner != "collapse");
            return manner == "collapse"
                ? new JsonObject { ["closed"] = true, ["method"] = "collapse" }
                : new JsonObject { ["opened"] = true, ["method"] = "expand" };
        };
        var arguments = new JsonObject
        {
            ["goal"] = "insertar una tabla",
            ["application"] = "Word",
            ["successCheck"] = "title:tabla",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en word inserta una tabla", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        (string Operation, JsonObject Arguments)[] collapses = harness.Acts
            .Where(act => (string?)act.Arguments["manner"] == "collapse").ToArray();
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That(collapses, Has.Length.EqualTo(1), "only the list the mission opened");
            Assert.That((string?)collapses[0].Arguments["label"], Is.EqualTo("Fuente"));
            Assert.That((int?)collapses[0].Arguments["index"], Is.EqualTo(2));
            Assert.That((long?)collapses[0].Arguments["window"], Is.EqualTo(7070L), "bound to the mission's window");
            Assert.That(collapses[0].Operation, Is.EqualTo("input.visible.click"));
            Assert.That(open, Is.False);
            Assert.That(MindPlanBoundary.ArgumentsSatisfyExactSchema("input.visible.click", collapses[0].Arguments), Is.True);
        });
    }

    // Counter-cases: a list the mission did not open (or failed to open), a look of another window or of a protected
    // one, and a tree branch are never collapsed.
    [Test]
    public void OnlyTheListsTheMissionOpenedAreCollapsed()
    {
        JsonObject view = Window("Documento1 - Word", "WINWORD", 70, true,
        [
            Control(2, "ComboBox", "Fuente", "expanded"),
            Control(3, "ComboBox", "Tamaño de fuente", "expanded"),
            Control(4, "TreeItem", "Encabezados", "expanded"),
        ]);
        var steps = new JsonArray
        {
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Fuente", ["manner"] = "open", ["ok"] = true, ["kind"] = "ComboBox" },
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Encabezados", ["manner"] = "open", ["ok"] = true, ["kind"] = "TreeItem" },
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Tamaño de fuente", ["manner"] = "open", ["ok"] = false, ["kind"] = "ComboBox" },
        };
        JsonObject elsewhere = (JsonObject)view.DeepClone();
        elsewhere["onTheApplication"] = false;
        JsonObject guarded = (JsonObject)view.DeepClone();
        guarded["window"]!["protected"] = true;

        Assert.Multiple(() =>
        {
            JsonArray collapses = ComputerUseMission.ListsLeftOpen(steps, view);
            Assert.That(collapses.Select(node => (string?)node!["label"]), Is.EqualTo(new[] { "Fuente" }));
            Assert.That(ComputerUseMission.ListsLeftOpen(steps, elsewhere), Is.Empty);
            Assert.That(ComputerUseMission.ListsLeftOpen(steps, guarded), Is.Empty);
            Assert.That(ComputerUseMission.ListsLeftOpen(new JsonArray(), view), Is.Empty);
        });
    }

    // Review 2 of palanca 6, finding 3 (v3-40: «renombra la tab» lives in the tab's context menu): a popup born in the
    // mission has no «expanded» to read. The tab's context menu opened with manner «menu», and a split button's flyout
    // opened by its arrow with the pointer (the receipt's popupBorn), are closed after a failed mission by the collapse
    // of the control that opened them, which the worker sends as Escape to the popup's own window.
    [TestCase("TabItem", "Windows PowerShell", "menu")]
    [TestCase("SplitButton", "Nueva pestaña", null)]
    public async Task AFailedMissionClosesThePopupItOpened(string kind, string name, string? manner)
    {
        int asked = 0;
        var harness = new Harness
        {
            Screen = _ =>
            {
                JsonObject view = Window("Windows PowerShell", "WindowsTerminal", 70, true,
                [
                    Control(2, kind, name, kind == "TabItem" ? "selected" : ""),
                    Control(3, "Button", "Cerrar pestaña", ""),
                ]);
                view["window"]!["hwnd"] = 7171;
                return view;
            },
            Mind = _ => asked++ == 0
                ? Step("input.visible.click", manner is null
                    ? new JsonObject { ["label"] = name, ["index"] = 2 }
                    : new JsonObject { ["label"] = name, ["index"] = 2, ["manner"] = manner })
                : new MindComputerUseStep("none", new JsonObject(), "no veo cómo seguir", "no_step_visible"),
        };
        harness.Receipt = (_, arguments) => (string?)arguments["manner"] switch
        {
            "dismiss" => new JsonObject { ["closed"] = true, ["method"] = "escape" },
            "menu" => new JsonObject { ["opened"] = true, ["method"] = "contextmenu" },
            _ => new JsonObject { ["surfaceChanged"] = true, ["popupBorn"] = true },
        };
        var arguments = new JsonObject
        {
            ["goal"] = "renombrar la pestaña",
            ["application"] = "Terminal",
            ["successCheck"] = "title:consola",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en la terminal renombra la tab a consola", arguments), arguments,
            CancellationToken.None);

        // Review 3 (finding 1): the popup's close is «dismiss», never the control's ExpandCollapse.
        (string Operation, JsonObject Arguments)[] collapses = harness.Acts
            .Where(act => (string?)act.Arguments["manner"] == "dismiss").ToArray();
        Assert.Multiple(() =>
        {
            Assert.That((bool?)Observed(result)["reached"], Is.False);
            Assert.That(harness.Acts.Where(act => (string?)act.Arguments["manner"] == "collapse"), Is.Empty);
            Assert.That(collapses, Has.Length.EqualTo(1));
            Assert.That((string?)collapses[0].Arguments["label"], Is.EqualTo(name));
            Assert.That((long?)collapses[0].Arguments["window"], Is.EqualTo(7171L), "bound to the mission's window");
        });
    }

    // Counter-cases of finding 3: a click that opened no popup, a context menu that did not open, and a popup opener the
    // last look no longer shows are never closed.
    [Test]
    public void OnlyThePopupsTheMissionOpenedAreClosed()
    {
        JsonObject view = Window("Windows PowerShell", "WindowsTerminal", 70, true,
        [
            Control(2, "TabItem", "Windows PowerShell", "selected"),
            Control(3, "Button", "Cerrar pestaña", ""),
            Control(4, "SplitButton", "Nueva pestaña", ""),
        ]);
        var steps = new JsonArray
        {
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Cerrar pestaña", ["ok"] = true, ["surfaceChanged"] = true, ["kind"] = "Button" },
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Windows PowerShell", ["manner"] = "menu", ["ok"] = false, ["kind"] = "TabItem" },
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Nueva pestaña", ["ok"] = true, ["popupBorn"] = false, ["kind"] = "SplitButton" },
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Configuración", ["manner"] = "menu", ["ok"] = true, ["kind"] = "MenuItem" },
        };
        Assert.That(ComputerUseMission.ListsLeftOpen(steps, view), Is.Empty);
        steps.Add(new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Nueva pestaña", ["ok"] = true, ["popupBorn"] = true, ["kind"] = "SplitButton" });
        Assert.That(ComputerUseMission.ListsLeftOpen(steps, view).Select(node => (string?)node!["label"]),
            Is.EqualTo(new[] { "Nueva pestaña" }));
        Assert.That(ComputerUseMission.ListsLeftOpen(steps, view).Select(node => (string?)node!["manner"]),
            Is.EqualTo(new[] { "dismiss" }));
    }

    // Review 3 of palanca 6, finding 1: a right click on the tree item «Este equipo» the person had expanded in the
    // file browser's navigation pane, then a failed mission: its menu gets «dismiss» (Escape to the menu's own window),
    // never the collapse that would fold the person's branch and say closed with the menu still open.
    [Test]
    public void APopupOnATreeItemIsDismissedNeverCollapsed()
    {
        JsonObject view = Window("Este equipo", "explorer", 70, true,
        [
            Control(1, "Edit", "Buscar en Este equipo", ""),
            Control(3, "TreeItem", "Este equipo", "expanded"),
            Control(4, "TreeItem", "Red", "collapsed"),
        ]);
        var steps = new JsonArray
        {
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Este equipo", ["index"] = 3, ["manner"] = "menu", ["ok"] = true, ["kind"] = "TreeItem" },
        };

        JsonArray closes = ComputerUseMission.ListsLeftOpen(steps, view);
        Assert.Multiple(() =>
        {
            Assert.That(closes.Select(node => (string?)node!["manner"]), Is.EqualTo(new[] { "dismiss" }));
            Assert.That(closes.Select(node => (int?)node!["index"]), Is.EqualTo(new int?[] { 3 }));
        });
    }

    // Review 3 of palanca 6, finding 1 (variant): the right click went to the list item «Fotos» and a tree branch
    // «Fotos» is open earlier in the look; the step is paired by its kind (or, without one, by its index), so only the
    // list item is dismissed and the branch is never touched.
    [Test]
    public void APopupIsPairedWithItsOwnControlNotAnotherOfTheSameName()
    {
        JsonObject view = Window("Imágenes", "explorer", 70, true,
        [
            Control(2, "TreeItem", "Fotos", "expanded"),
            Control(7, "ListItem", "Fotos", "selected"),
        ]);
        var byKind = new JsonArray
        {
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Fotos", ["index"] = 7, ["manner"] = "menu", ["ok"] = true, ["kind"] = "ListItem" },
        };
        var byIndex = new JsonArray
        {
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Fotos", ["index"] = 7, ["manner"] = "menu", ["ok"] = true },
        };
        var opened = new JsonArray
        {
            new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Fotos", ["index"] = 7, ["manner"] = "open", ["ok"] = true, ["kind"] = "ListItem" },
        };

        Assert.Multiple(() =>
        {
            foreach (JsonArray steps in new[] { byKind, byIndex })
            {
                JsonArray closes = ComputerUseMission.ListsLeftOpen(steps, view);
                Assert.That(closes.Select(node => (int?)node!["index"]), Is.EqualTo(new int?[] { 7 }));
                Assert.That(closes.Select(node => (string?)node!["manner"]), Is.EqualTo(new[] { "dismiss" }));
            }

            // A list the mission opened is never paired with a branch of the same name, nor with a control of another kind.
            Assert.That(ComputerUseMission.ListsLeftOpen(opened, view), Is.Empty);
        });
    }

    // Ronda 21 (pasada r18 v3-63): after opening Servicios the first look read the window well (107 controls, 4 s), the
    // next ones were not answered in time (visible_controls_unavailable, 20 s each) and the good look was thrown away:
    // the turn said «la ventana de Servicios no se dejó leer». Scripted: one good look of the opened window, then every
    // read fails as unreadable (failFrom: the look from which they fail; before the opening the person's editor is read).
    private static Harness OpeningWhoseReadsStopAnswering(int failFrom, Func<ComputerUseStepRequest, MindComputerUseStep?> mind)
    {
        bool open = false;
        int looks = 0;
        var harness = new Harness
        {
            Screen = _ =>
            {
                if (!open)
                    return Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Document", "Texto")]);
                return ++looks >= failFrom
                    ? new JsonObject { ["failWith"] = "visible_controls_unavailable" }
                    : Window("Servicios", "mmc", 31, true, [
                        Control(0, "TreeItem", "Servicios (locales)", "selected"),
                        Control(1, "Text", "Cola de impresión"),
                        Control(2, "DataItem", "Cliente DHCP"),
                        Control(3, "Button", "Iniciar el servicio")]);
            },
            Mind = mind,
        };
        harness.Receipt = (_, _) =>
        {
            open = true;
            return new JsonObject { ["processId"] = 31, ["surfaceChanged"] = true };
        };
        return harness;
    }

    private static JsonObject ServicesArguments() => new()
    {
        ["goal"] = "ver si la cola de impresión está en ejecución",
        ["application"] = "Servicios",
        ["successCheck"] = "control:zzzz",
    };

    private static MindComputerUseStep? OpenThenCite(ComputerUseStepRequest request) => request.History.Count == 0
        ? Step("app.open", new JsonObject { ["appId"] = "Servicios" })
        : Step("done", new JsonObject { ["evidence"] = "Cola de impresión" });

    [Test]
    public async Task AGoodLookIsNotThrownAwayForAReadThatDidNotComeButNeverProvesAnything()
    {
        Harness harness = OpeningWhoseReadsStopAnswering(failFrom: 2, OpenThenCite);
        JsonObject arguments = ServicesArguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("fijate si la cola de impresión está en ejecución", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests, Has.Count.EqualTo(2), "the model decided on the good look kept");
            Assert.That(Shows(harness.Requests[^1], "Cola de impresión"), Is.True);
            Assert.That((bool?)observed["reached"], Is.False, "a kept look never proves done");
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_view_unavailable"),
                "the fresh look and its one read again failed: it could not verify");
            Assert.That(harness.Delays, Has.Some.EqualTo(ComputerUseMission.ViewRetryPause), "read once more after a pause");
        });
    }

    [Test]
    public async Task AFreshLookAfterAKeptOneIsWhatProvesTheCitation()
    {
        Harness harness = OpeningWhoseReadsStopAnswering(failFrom: 2, OpenThenCite);
        Func<JsonObject, JsonObject?> scripted = harness.Screen;
        // The worker answers again once the model decided on the kept look: the fresh look reads the window.
        harness.Screen = look =>
        {
            JsonObject? seen = scripted(look);
            if ((string?)seen?["failWith"] is not null && harness.Requests.Count >= 2)
                return Window("Servicios", "mmc", 31, true, [Control(0, "Text", "Cola de impresión"), Control(1, "Button", "Detener")]);
            return seen;
        };
        JsonObject arguments = ServicesArguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("fijate si la cola de impresión está en ejecución", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True, (string?)observed["stoppedBy"]);
            Assert.That(harness.Requests, Has.Count.EqualTo(3), "decided again on the fresh look before anything is said done");
            Assert.That(Shows(harness.Requests[^1], "Detener"), Is.True, "the citation held on the fresh look");
        });
    }

    // Counter-case: a window whose first look after the opening already failed (no good look: a hung window) still
    // stops at once as unreadable, with no read again.
    [Test]
    public async Task AWindowNeverReadStillStopsAsUnreadableWithoutReadingAgain()
    {
        Harness harness = OpeningWhoseReadsStopAnswering(failFrom: 1, OpenThenCite);
        JsonObject arguments = ServicesArguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("fijate si la cola de impresión está en ejecución", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_view_unavailable"));
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "nothing after the opening reached the model");
            Assert.That(harness.Delays, Has.None.EqualTo(ComputerUseMission.ViewRetryPause), "never read again");
        });
    }

    [Test]
    public void OnlyTheEnginesOpeningFirstInASubgoalNotAboutOpeningRestartsItsClock()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.RestartsSubgoalClock("app.open", "rule", true, 1, "ir a Registros de Windows > Sistema"), Is.True);
            // Counter-cases: a sub-goal whose goal is opening keeps the opening in its time; the model's own opening, a
            // failed one, or one after other steps is the sub-goal's work.
            Assert.That(ComputerUseMission.RestartsSubgoalClock("app.open", "rule", true, 1, "abrir el visor de eventos"), Is.False);
            Assert.That(ComputerUseMission.RestartsSubgoalClock("app.open", "model", true, 1, "ir a Sistema"), Is.False);
            Assert.That(ComputerUseMission.RestartsSubgoalClock("app.open", "rule", false, 1, "ir a Sistema"), Is.False);
            Assert.That(ComputerUseMission.RestartsSubgoalClock("app.open", "rule", true, 2, "ir a Sistema"), Is.False);
            Assert.That(ComputerUseMission.RestartsSubgoalClock("input.visible.click", "rule", true, 1, "ir a Sistema"), Is.False);
        });
    }

    // Review 1 of ronda 21 (finding 2): a kept look holds no final. The model saw the kept look of Servicios and said
    // there was no step («No veo la cola de impresión en la lista»): before the review the mission stopped on it with
    // computer_use_no_step_visible and quoted the kept look as the screen now. The window is looked at afresh; the
    // look and its one read again fail, and the mission says it could not read the window.
    private static MindComputerUseStep? OpenThenNoStep(ComputerUseStepRequest request) => request.History.Count == 0
        ? Step("app.open", new JsonObject { ["appId"] = "Servicios" })
        : new MindComputerUseStep("none", new JsonObject(), "No veo la cola de impresión en la lista", "no_step_visible");

    [Test]
    public async Task AFinalIsNeverSaidOnAKeptLook()
    {
        Harness harness = OpeningWhoseReadsStopAnswering(failFrom: 2, OpenThenNoStep);
        JsonObject arguments = ServicesArguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("fijate si la cola de impresión está en ejecución", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_view_unavailable"));
            Assert.That(observed["screen"], Is.Null, "the kept look is never quoted as the screen now");
            Assert.That(harness.Requests, Has.Count.EqualTo(2));
        });
    }

    // Counter-case: the fresh look reads the window, the model says again there is no step, and that is said on it.
    [Test]
    public async Task AFinalOnTheFreshLookAfterAKeptOneIsSaid()
    {
        Harness harness = OpeningWhoseReadsStopAnswering(failFrom: 2, OpenThenNoStep);
        Func<JsonObject, JsonObject?> scripted = harness.Screen;
        harness.Screen = look =>
        {
            JsonObject? seen = scripted(look);
            if ((string?)seen?["failWith"] is not null && harness.Requests.Count >= 2)
                return Window("Servicios", "mmc", 31, true, [
                    Control(0, "TreeItem", "Servicios (extendido)", "selected"), Control(1, "DataItem", "Cliente DHCP")]);
            return seen;
        };
        JsonObject arguments = ServicesArguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("fijate si la cola de impresión está en ejecución", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_no_step_visible"));
            Assert.That(harness.Requests, Has.Count.EqualTo(3), "decided again on the fresh look");
            Assert.That(observed["screen"]?.ToJsonString(), Does.Contain("Servicios (extendido)").And.Not.Contain("Servicios (locales)"),
                "the fresh look is the screen quoted");
        });
    }

    [Test]
    public void EveryFinalNeedsAFreshLookAndNoActDoes()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.EndsOnTheView("done"), Is.True);
            Assert.That(ComputerUseMission.EndsOnTheView("none"), Is.True);
            Assert.That(ComputerUseMission.EndsOnTheView("ask.person"), Is.True);
            Assert.That(ComputerUseMission.EndsOnTheView("input.visible.click"), Is.False);
            Assert.That(ComputerUseMission.EndsOnTheView("app.open"), Is.False);
        });
    }

    // Review 1 of ronda 21 (finding 1, v3-34): the opening's last good look was a splash or a loading view and the reads
    // after it failed; it is never handed on stale, and while it shows loading within StartWait it never reaches the
    // model: the mission says it could not read the window.
    private static Harness OpeningOnASplashWhoseReadsStop(JsonArray splash, Func<int, JsonObject?>? after = null)
    {
        bool open = false;
        int looks = 0;
        var harness = new Harness
        {
            Screen = _ =>
            {
                if (!open)
                    return Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Document", "Texto")]);
                looks++;
                if (looks == 1)
                    return Window("Notas rápidas", "notes", 12, true, (JsonArray)splash.DeepClone());
                return after?.Invoke(looks) ?? new JsonObject { ["failWith"] = "visible_controls_unavailable" };
            },
        };
        harness.Mind = request => request.History.Count == 0
            ? Step("app.open", new JsonObject { ["appId"] = "Notas rápidas" })
            : new MindComputerUseStep("none", new JsonObject(), "No veo dónde escribir", "no_step_visible");
        harness.Receipt = (_, _) =>
        {
            open = true;
            return new JsonObject { ["processId"] = 12, ["surfaceChanged"] = true };
        };
        return harness;
    }

    private static JsonObject NotesArguments() =>
        new() { ["goal"] = "escribir una nota", ["application"] = "Notas rápidas", ["successCheck"] = "control:zzzz" };

    private static JsonArray LoadingControls() =>
        [Control(0, "Button", "Minimizar"), Control(1, "Button", "Cerrar"), Control(2, "ProgressBar", "Cargando")];

    [TestCase("splash")]
    [TestCase("loading")]
    public async Task ASplashOrALoadingLookIsNeverHandedOnStale(string first)
    {
        JsonArray splash = first == "splash" ? [Control(0, "Image", "Notas rápidas")] : LoadingControls();
        Harness harness = OpeningOnASplashWhoseReadsStop(splash);
        JsonObject arguments = NotesArguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en notas rápidas escribí una nota", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_view_unavailable"));
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "nothing after the opening reached the model");
        });
    }

    // Counter-case: the loading view gives way to the application's interface within StartWait; the model decides on
    // the interface, never on the loading view.
    [Test]
    public async Task ALoadingLookWaitsForTheInterfaceWithinStartWait()
    {
        Harness harness = OpeningOnASplashWhoseReadsStop(LoadingControls(), looks => looks < 4
            ? Window("Notas rápidas", "notes", 12, true, LoadingControls())
            : Window("Notas rápidas", "notes", 12, true, [Control(0, "Edit", "Nota nueva"), Control(1, "Button", "Agregar")]));
        JsonObject arguments = NotesArguments();

        await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en notas rápidas escribí una nota", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Requests, Has.Count.GreaterThanOrEqualTo(2));
            Assert.That(Shows(harness.Requests[1], "Nota nueva"), Is.True, "decided on the interface");
            Assert.That(harness.Requests.Skip(1).Any(request => Shows(request, "Cargando")), Is.False);
        });
    }

    [Test]
    public void ALoadingBarThatStoodStillIsFurnitureAndTheOpeningGoesOn()
    {
        JsonObject view = Window("Explorador", "explorer", 5, true,
            [Control(0, "Button", "Atrás"), Control(1, "Button", "Adelante"), Control(2, "ProgressBar", "Cargando", "", "0")]);
        string tree = ComputerUseMission.OpeningTree(view);
        string? bars = ComputerUseMission.LoadingBarsSignature(view);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.LoadingWhileStarting(view, tree, null, bars, null, TimeSpan.FromSeconds(2)), Is.True,
                "first look: loading");
            Assert.That(ComputerUseMission.LoadingWhileStarting(view, tree, tree, bars, bars, TimeSpan.FromSeconds(4)), Is.False,
                "the same bar, standing still on the same tree: furniture");
            Assert.That(ComputerUseMission.LoadingWhileStarting(view, tree, null, bars, null, ComputerUseMission.StartWait), Is.False,
                "never past StartWait");
            Assert.That(ComputerUseMission.KeptWhileOpening(view), Is.False, "a loading view is never kept to be handed on");
        });
    }

    // Review 1 of ronda 21 (finding 3, v3-63): a look the worker cut at its own deadline (partial) holds no «none»: the
    // queue the model did not see may be in the part not walked. Counter-case: a gate the view writes is said on it.
    [TestCase(false)]
    [TestCase(true)]
    public async Task APartialLookHoldsNoAbsence(bool gate)
    {
        bool open = false;
        var harness = new Harness
        {
            Screen = _ =>
            {
                if (!open)
                    return Window("Notas - Bloc de notas", "Notepad", 9, false, [Control(0, "Document", "Texto")]);
                JsonObject view = Window("Servicios", "mmc", 31, true, [
                    Control(0, "TreeItem", "Servicios (locales)", "selected"),
                    Control(1, "Text", "Inicia sesión para continuar"),
                    Control(2, "DataItem", "Cliente DHCP"),
                    Control(3, "Button", "Iniciar el servicio")]);
                view["partial"] = true;
                return view;
            },
        };
        harness.Mind = request => request.History.Count == 0
            ? Step("app.open", new JsonObject { ["appId"] = "Servicios" })
            : gate
                ? new MindComputerUseStep("none",
                    new JsonObject { ["evidence"] = "Inicia sesión para continuar", ["gate"] = "account" }, "Pide iniciar sesión", "app_gate")
                : new MindComputerUseStep("none", new JsonObject(), "No veo la cola de impresión en la lista", "no_step_visible");
        harness.Receipt = (_, _) =>
        {
            open = true;
            return new JsonObject { ["processId"] = 31, ["surfaceChanged"] = true };
        };
        JsonObject arguments = ServicesArguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("fijate si la cola de impresión está en ejecución", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.That((string?)observed["stoppedBy"],
            Is.EqualTo(gate ? "computer_use_app_gate" : "computer_use_view_unavailable"));
    }

    // Ronda 23 (índices de vista y esquema, t-menu-2 r21): a rule's click the catalog's schema refused ended the mission
    // with «el paso elegido no era válido». Now it is never taken, kept as a failed step with the arguments refused, and
    // the model takes the next step with it in front.
    [Test]
    public async Task ARulesActTheSchemaRefusesIsHandedToTheModelWithItsCause()
    {
        bool saved = false;
        var harness = new Harness
        {
            Screen = _ => saved
                ? Window("App guardada", "app", 5, true, [Control(0, "Button", "Guardar"), Control(1, "Button", "Cerrar")])
                : Window("App", "app", 5, true, [Control(0, "Button", "Guardar"), Control(1, "Button", "Cerrar")]),
            Mind = request => request.History.Count == 0
                ? new MindComputerUseStep("input.visible.click",
                    new JsonObject { ["label"] = "Guardar", ["index"] = VisibleViewNumbering.HighestIndex + 1 }, string.Empty, Source: "rule")
                : Step("input.visible.click", new JsonObject { ["label"] = "Guardar", ["index"] = 0 }),
        };
        harness.Receipt = (_, _) =>
        {
            saved = true;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "guardar", ["application"] = "App", ["successCheck"] = "title:guardada" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("guarda", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        JsonArray steps = observed["steps"]!.AsArray();
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True, observed.ToJsonString());
            Assert.That(harness.Acts.Select(act => (int?)act.Arguments["index"]), Is.EqualTo(new int?[] { 0 }),
                "the refused click is never sent");
            Assert.That((bool?)steps[0]!["refused"], Is.True);
            Assert.That((bool?)steps[0]!["ok"], Is.False);
            Assert.That((string?)steps[0]!["error"], Is.EqualTo("arguments_invalid:index"));
            Assert.That((string?)steps[0]!["source"], Is.EqualTo("rule"));
            Assert.That((string?)harness.Requests[1].History[^1]!["error"], Is.EqualTo("arguments_invalid:index"),
                "the model sees the cause");
        });
    }

    // Counter-case: the model's own act the schema refuses still ends the mission as before.
    [Test]
    public async Task TheModelsOwnActTheSchemaRefusesStillEndsTheMission()
    {
        var harness = new Harness
        {
            Screen = _ => Window("App", "app", 5, true, [Control(0, "Button", "Guardar"), Control(1, "Button", "Cerrar")]),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Guardar", ["index"] = VisibleViewNumbering.HighestIndex + 1 }),
        };
        var arguments = new JsonObject { ["goal"] = "guardar", ["application"] = "App", ["successCheck"] = "title:guardada" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("guarda", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Acts, Is.Empty);
            Assert.That(harness.Requests, Has.Count.EqualTo(1));
            Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_step_arguments_invalid"));
        });
    }

    // Counter-cases of the refusal itself: once per sub-goal, from a rule only, the cause names the arguments refused,
    // and an act the schema takes is never refused.
    [Test]
    public void TheSchemaRefusalIsOncePerSubgoalAndOnlyForARule()
    {
        var past = new JsonObject { ["label"] = "Tamaño", ["index"] = VisibleViewNumbering.HighestIndex + 1, ["manner"] = "menu" };
        JsonObject? first = ComputerUseMission.SchemaRefusalForTheModel("input.visible.click", past, "rule", [], 3);

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.Not.Null);
            Assert.That((int?)first!["step"], Is.EqualTo(3));
            Assert.That((string?)first["label"], Is.EqualTo("Tamaño"));
            Assert.That((string?)first["manner"], Is.EqualTo("menu"));
            Assert.That((string?)first["error"], Is.EqualTo("arguments_invalid:index"));
            Assert.That((string?)first["source"], Is.EqualTo("rule"));
            Assert.That(ComputerUseMission.SchemaRefusalForTheModel("input.visible.click", past, "model", [], 3), Is.Null);
            Assert.That(ComputerUseMission.SchemaRefusalForTheModel("input.visible.click", past, null, [], 3), Is.Null);
            Assert.That(ComputerUseMission.SchemaRefusalForTheModel("input.visible.click", past, "rule", [first.DeepClone()], 4),
                Is.Null, "a second refusal in the sub-goal ends the mission");
            var taken = new JsonObject { ["label"] = "Tamaño", ["index"] = VisibleViewNumbering.HighestIndex };
            Assert.That(MindPlanBoundary.ArgumentsSatisfyExactSchema("input.visible.click", taken), Is.True);
            Assert.That(MindPlanBoundary.ArgumentsOutsideExactSchema("input.visible.click", taken), Is.Empty);
        });
    }
}
