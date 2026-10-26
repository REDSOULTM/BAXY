using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class ProductCatalogTests
{
    // C03 (2026-09-12 … 2026-09-20) creció el catálogo de 170 a 191 descriptores con estas 21
    // operaciones, cada una sellada por su tanda; la cifra se re-pina aquí junto a la lista nominal
    // (plan post-goal 2026-09-20, Fase 1 grupo B). document.pdf.read y filesystem.known.list se
    // retiraron en BAXY Renew (RenewRetired).
    internal static readonly string[] C03CatalogAdditions =
    [
        "audio.app.volume.adjust",
        "audio.app.volume.set",
        "bluetooth.radio.status",
        "calculator.expression.evaluate",
        "client.channel.locate",
        "display.status",
        "game.entitlement.named",
        "input.visible.controls",
        "message.draft",
        "message.send.test",
        "software.python.package.status",
        "software.python.status",
        "storage.removable.list",
        "wifi.radio.set",
        "wifi.radio.status",
        "wifi.scan",
        "window.close.all",
        "window.minimize.all",
        "window.snap",
    ];

    // Auditoría semántica 2026-09-20 (REOPEN1993): herramientas tipadas que la
    // encuesta pedía y el catálogo no tenía (document.text.read y web.news.headlines se retiraron en BAXY Renew).
    internal static readonly string[] Reopen1993CatalogAdditions =
    [
        "desktop.wallpaper.set",
        "document.presentation.create",
        "email.send",
        "file.compress",
        "filesystem.explorer.count",
        "file.open",
        "game.uninstall.named",
        "package.uninstall",
        "shell.command.run",
        "weather.current",
        "web.download",
    ];


    // Motor de computer use (plan post-goal Fase 4, D21; CONTRATO_VISTA_ACCION.md): el desplazamiento verificado
    // por superficie (el arrastre de v3 se retiró en la estabilización L; la misión general del shell, en BAXY Renew).
    internal static readonly string[] ComputerUseAdditions =
    [
        "input.scroll",
    ];

    // BAXY Renew, herramientas de agente (2026-10-15): leer una página pública como texto; editar, buscar, leer y
    // escribir archivos con cuatro operaciones; una sola para lo que suena después (alarmas y recordatorios); y una
    // sola para instalar un programa, que resuelve, instala y verifica tras el sí.
    internal static readonly string[] RenewAgentAdditions =
    [
        "file.edit",
        "file.find",
        "file.read",
        "file.write",
        "web.fetch",
        "schedule.alarms",
        "package.install",
    ];

    // Auditoría de los pedidos reales (2026-10-17): reiniciar una aplicación (la única operación que decía «restart»
    // era system.power, que va sin el sí) y cambiar la frecuencia o la resolución del monitor (sólo a un modo que su
    // controlador lista, releído y revertido si no coincide).
    internal static readonly string[] RenewRealesAdditions =
    [
        "app.restart",
        "display.mode.set",
    ];

    // Lo que esas operaciones sustituyen, retirado en el mismo cambio: las seis de archivos y las doce de avisos
    // (reminder.* sólo guardaba un registro que nadie hacía sonar), y las siete de rutinas, que nada ejecutaba. Y la
    // misión de pantalla, que el bucle nativo ya no aloja (auditoría K3), y app.status, que nadie invocaba (D-K9). Y la
    // pareja preparar/confirmar de winget, que package.install sustituye. Y el paso interno que mandaba una ruta a una
    // papelera privada sin vuelta, que nada invocaba. Auditoría final (2026-10-15): los nueve pasos internos que nada
    // enviaba (hash, papelera privada, preparar/confirmar de Steam y su compra, resolver destinatario o tarea),
    // message.send y filesystem.trash.restore, que sólo servían a dos de ellos, y los titulares del día, que leían el
    // mismo canal que web.search con source=news.
    internal static readonly string[] RenewRetired =
    [
        "app.status",
        "mission.computer.use",
        "notification.cancel.at",
        "notification.cancel.latest",
        "notification.diagnose",
        "notification.dismiss",
        "notification.list",
        "notification.list.due",
        "notification.schedule",
        "reminder.create",
        "reminder.delete",
        "reminder.list",
        "reminder.resolve.exact",
        "reminder.restore",
        "document.pdf.read",
        "document.text.read",
        "filesystem.known.list",
        "filesystem.known.search",
        "filesystem.sandbox.append.named",
        "filesystem.write.text",
        "routine.delete",
        "routine.list",
        "routine.phrase.create",
        "routine.read",
        "routine.resolve.exact",
        "routine.restore",
        "routine.set.enabled",
        "package.install.commit",
        "package.install.prepare",
        "filesystem.path.ensure.absent",
        "web.news.headlines",
        "filesystem.hash",
        "filesystem.trash.commit",
        "filesystem.trash.prepare",
        "filesystem.trash.restore",
        "game.install.commit",
        "game.install.prepare",
        "game.purchase.commit",
        "game.purchase.prepare",
        "message.recipient.resolve",
        "task.resolve.exact",
    ];

    // Uso real 2026-10-21 (decisión del dueño: «si le pido que mande un mensaje, lo tiene que mandar»): message.send
    // vuelve, ya no como el paso interno retirado sino como el envío verificado al destinatario nombrado, con el sí en
    // modo normal.
    internal static readonly string[] UsoRealAdditions =
    [
        "message.send",
    ];

    // Every operation of the catalog is offered to the model as a tool.
    // BAXY Renew uso real: + 1, message.send. BAXY Renew cu (C04 variante, C05): + 2, game.store.page y game.store.search;
    // (C14) + 1, client.microphone.set; (C18) + 1, clipboard.paste.into; (C10, C11, notebook) + 1, office.format.apply.
    // pc-f6-sesiones (APLAZADOS f4-accesibilidad): + 4, las conversaciones por voz (ConversationAdditions).
    internal const int ExpectedDescriptors = 170 + 21 + 14 + 2 + 7 - 30 - 12 + 2 + 1 + 2 + 1 + 1 + 1 + 4;

    // pc-f6-sesiones (APLAZADOS f4-accesibilidad, 2026-10-25): empezar, listar, abrir y renombrar una conversación
    // estaba sólo en la vista; la App las ejecuta con sus propias sesiones (FieldProductChannel) y ninguna pide el sí.
    internal static readonly string[] ConversationAdditions =
    [
        "conversation.list",
        "conversation.new",
        "conversation.open",
        "conversation.rename",
    ];

    [TestCase("{\"process\":\"*\"}", true)]
    [TestCase("{\"process\":\"*\",\"limit\":50,\"offset\":50}", true)]
    [TestCase("{\"process\":\"*\",\"byTitle\":true}", true)]
    [TestCase("{\"process\":\"editor.exe\",\"offset\":0}", true)]
    // CLOSE1060 (b7d005955): the flat v3 schema types both selectors and requires
    // neither; WindowResolveHandler enforces «exactly one» before any OS read.
    [TestCase("{}", true)]
    [TestCase("{\"process\":\"\"}", false)]
    [TestCase("{\"process\":\" \"}", false)]
    [TestCase("{\"process\":\"*\",\"offset\":-1}", false)]
    [TestCase("{\"process\":\"*\",\"offset\":0.5}", false)]
    [TestCase("{\"process\":\"*\",\"limit\":51}", false)]
    [TestCase("{\"process\":\"*\",\"limit\":0}", false)]
    [TestCase("{\"all\":true}", false)]
    public void WindowInventoryRemainsAReadOnlyBoundedOperationWithAnExplicitSelector(string json, bool expected)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("window.resolve");
        using JsonDocument arguments = JsonDocument.Parse(json);

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.ReadOnly));
            Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, descriptor.ArgumentsSchema), Is.EqualTo(expected));
            // v2 → v3: CLOSE1060 (b7d005955) añadió el selector applicationName a window.resolve.
            Assert.That(descriptor.VerifierContractId, Is.EqualTo("window.resolve.identity.inventory.v3"));
        });
    }

    // Ronda 22 (uso real r18 t2-c16, t3-c11, t4-c09 «…y guárdala en el escritorio»): a capture takes the known folder
    // it is also saved to, optional (without it the capture stays private), and nothing outside the enum.
    [TestCase("capture.screenshot", "{}", true)]
    [TestCase("capture.screenshot", """{"folder":"desktop"}""", true)]
    [TestCase("capture.screenshot", """{"folder":"pictures"}""", true)]
    [TestCase("capture.screenshot", """{"folder":"documents"}""", true)]
    [TestCase("capture.screenshot", """{"folder":"downloads"}""", true)]
    [TestCase("capture.active.window", "{}", true)]
    [TestCase("capture.active.window", """{"folder":"desktop"}""", true)]
    [TestCase("capture.screenshot", """{"folder":"all_known"}""", false)]
    [TestCase("capture.screenshot", """{"folder":"C:\\Users"}""", false)]
    [TestCase("capture.screenshot", """{"folder":null}""", false)]
    [TestCase("capture.screenshot", """{"path":"C:\\Users"}""", false)]
    [TestCase("capture.active.window", """{"folder":"projects"}""", false)]
    public void ACaptureTakesAnOptionalKnownFolderToBeSavedTo(string operation, string json, bool expected)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired(operation);
        using JsonDocument arguments = JsonDocument.Parse(json);

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.PrivacySensitive));
            Assert.That(descriptor.ArgumentsSchema.Required, Is.Empty);
            Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, descriptor.ArgumentsSchema), Is.EqualTo(expected));
        });
    }

    // Renew al máximo (F001, F016): a launch carries the game the person asked for, so the provider can refuse an appId
    // that is another game before anything starts.
    [TestCase("{\"appId\":\"252950\"}", false)]
    [TestCase("{\"appId\":\"252950\",\"title\":\"Rocket League\"}", true)]
    public void AGameLaunchCarriesTheTitleThePersonAskedFor(string json, bool expected)
    {
        using JsonDocument arguments = JsonDocument.Parse(json);
        OperationArgumentsSchema schema = ProductCatalog.GetRequired("game.launch").ArgumentsSchema;
        Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, schema), Is.EqualTo(expected));
    }

    // Ronda 23 (índices de vista y esquema, t-menu-2 r21): a look numbers up to its cap, the goal's reserved room and
    // the body; the acts on a control of the look take all of it and nothing past it, and the look's own limit is the cap.
    [TestCase("input.visible.click", "index", "\"label\":\"Tamaño\"")]
    [TestCase("input.scroll", "index", "\"amount\":1,\"direction\":\"down\"")]
    [TestCase("input.text.type", "index", "\"text\":\"hola\"")]
    public void ActsOnAControlOfTheLookTakeEveryIndexTheLookNumbers(string operation, string argument, string rest)
    {
        OperationArgumentsSchema schema = ProductCatalog.GetRequired(operation).ArgumentsSchema;

        Assert.Multiple(() =>
        {
            Assert.That(VisibleViewNumbering.HighestIndex, Is.EqualTo(70));
            foreach ((int index, bool expected) in new[] { (0, true), (59, true), (60, true), (VisibleViewNumbering.HighestIndex, true), (VisibleViewNumbering.HighestIndex + 1, false), (-1, false) })
            {
                using JsonDocument arguments = JsonDocument.Parse($"{{\"{argument}\":{index},{rest}}}");
                Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, schema), Is.EqualTo(expected), $"{argument}={index}");
            }

            OperationArgumentsSchema look = ProductCatalog.GetRequired("input.visible.controls").ArgumentsSchema;
            using JsonDocument atCap = JsonDocument.Parse($"{{\"limit\":{VisibleViewNumbering.Cap}}}");
            using JsonDocument pastCap = JsonDocument.Parse($"{{\"limit\":{VisibleViewNumbering.Cap + 1}}}");
            Assert.That(OperationArgumentValidator.IsValid(atCap.RootElement, look), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(pastCap.RootElement, look), Is.False);
        });
    }

    // The cause a refused call is handed back with names each argument the schema refuses and what it takes, and none
    // for arguments it takes (counter-case).
    [Test]
    public void TheInvalidArgumentsAreNamedWithWhatTheyTakeAndNoneForValidOnes()
    {
        OperationArgumentsSchema schema = ProductCatalog.GetRequired("input.visible.click").ArgumentsSchema;
        using JsonDocument wrong = JsonDocument.Parse("{\"index\":71,\"manner\":\"triple\",\"labelz\":\"x\"}");
        using JsonDocument right = JsonDocument.Parse("{\"index\":70,\"label\":\"Tamaño\",\"manner\":\"menu\"}");

        Assert.Multiple(() =>
        {
            IReadOnlyList<ArgumentProblem> problems = OperationArgumentValidator.Problems(wrong.RootElement, schema);
            Assert.That(problems.Select(static problem => problem.Name),
                Is.EqualTo(new[] { "index", "manner", "labelz", "label" }));
            Assert.That(problems[0].Problem, Does.StartWith("expected an integer").And.Contain(" from "));
            Assert.That(problems[1].Problem, Is.EqualTo("expected one of the allowed values or null"));
            Assert.That(problems[1].Allowed, Is.EqualTo(new[] { "double", "menu", "open" }));
            Assert.That(problems[2].Problem, Is.EqualTo("not an argument of this tool"));
            Assert.That(problems[2].Nearest, Is.EqualTo("label"));
            Assert.That(problems[2].Accepted, Is.EqualTo(schema.Properties.Select(static property => property.Name)));
            Assert.That(problems[3].Problem, Is.EqualTo("required and missing"));
            Assert.That(OperationArgumentValidator.Problems(right.RootElement, schema), Is.Empty);
            Assert.That(OperationArgumentValidator.IsValid(right.RootElement, schema), Is.True);
        });
    }

    // P5.3: an argument the tool does not take is answered with the ones it takes and, when one is close enough to be
    // the one meant, that one; never one far off, one as near as another, nor one already given.
    [TestCase("app.close", "{\"app_id\":\"Paint\"}", "appId")]
    [TestCase("app.close", "{\"window\":\"w1\"}", "windowId")]
    [TestCase("app.close", "{\"windowid\":\"w1\"}", "windowId")]
    [TestCase("audio.volume", "{\"level\":5,\"levle\":5}", null)]
    [TestCase("audio.volume", "{\"volume\":50}", null)]
    [TestCase("app.close", "{\"process\":\"paint\"}", null)]
    public void AnArgumentTheToolDoesNotTakeSaysWhichItTakesAndTheNearest(
        string operation, string arguments, string? nearest)
    {
        OperationArgumentsSchema schema = ProductCatalog.GetRequired(operation).ArgumentsSchema;
        using JsonDocument given = JsonDocument.Parse(arguments);

        ArgumentProblem unknown = OperationArgumentValidator.Problems(given.RootElement, schema)
            .Single(static problem => problem.Problem == "not an argument of this tool");

        Assert.Multiple(() =>
        {
            Assert.That(unknown.Nearest, Is.EqualTo(nearest));
            Assert.That(unknown.Accepted, Is.EqualTo(schema.Properties.Select(static property => property.Name)));
            Assert.That(unknown.Allowed, Is.Null);
        });
    }

    // P5.3: a value outside an argument's values is answered with the nearest of them and, when they are few, all of
    // them; a value of another type gets no nearest.
    [TestCase("{\"scope\":\"cpu memory\"}", "cpu_memory")]
    [TestCase("{\"scope\":\"Batery\"}", "battery")]
    [TestCase("{\"scope\":\"batt\"}", "battery")]
    [TestCase("{\"scope\":\"gpu\"}", null)]
    [TestCase("{\"scope\":\"weather\"}", null)]
    [TestCase("{\"scope\":7}", null)]
    public void AValueOutsideTheEnumSaysTheNearestAndTheFewAllowed(string arguments, string? nearest)
    {
        OperationArgumentsSchema schema = ProductCatalog.GetRequired("system.status").ArgumentsSchema;
        using JsonDocument given = JsonDocument.Parse(arguments);

        ArgumentProblem problem = OperationArgumentValidator.Problems(given.RootElement, schema).Single();

        Assert.Multiple(() =>
        {
            Assert.That(problem.Name, Is.EqualTo("scope"));
            Assert.That(problem.Problem, Is.EqualTo("expected one of the allowed values"));
            Assert.That(problem.Nearest, Is.EqualTo(nearest));
            Assert.That(problem.Allowed, Is.EqualTo(schema.Properties.Single().AllowedValues));
            Assert.That(problem.Allowed, Has.Count.LessThanOrEqualTo(OperationArgumentValidator.AllowedShown));
            Assert.That(problem.Accepted, Is.Null);
        });
    }

    // P5.3 counter-case: past twelve values the list is left to the tool's own schema; the nearest still goes back.
    [TestCase("Page Down", "page_down")]
    [TestCase("ctrl+c", "ctrl_c")]
    [TestCase("ctrl", null)]
    public void ManyAllowedValuesAreNotListedButTheNearestIs(string key, string? nearest)
    {
        OperationArgumentsSchema schema = ProductCatalog.GetRequired("input.key.press").ArgumentsSchema;
        using JsonDocument given = JsonDocument.Parse(JsonSerializer.Serialize(new { key }));

        ArgumentProblem problem = OperationArgumentValidator.Problems(given.RootElement, schema)
            .Single(static candidate => candidate.Name == "key");

        Assert.Multiple(() =>
        {
            Assert.That(schema.Properties.Single(static property => property.Name == "key").AllowedValues,
                Has.Count.GreaterThan(OperationArgumentValidator.AllowedShown));
            Assert.That(problem.Problem, Is.EqualTo("expected one of the allowed values"));
            Assert.That(problem.Allowed, Is.Null);
            Assert.That(problem.Nearest, Is.EqualTo(nearest));
        });
    }

    // P5.3: the model reads those fields as data beside the argument and its problem, and only those it has.
    [Test]
    public void TheCorrectingFieldsReachTheModelAsStructuredData()
    {
        string message = OperationVisibleFacts.FromStatus(
            "app.close",
            OperationStatuses.Failed,
            "invalid_arguments",
            [
                new ArgumentProblem("windowid", "not an argument of this tool")
                {
                    Accepted = ["appId", "windowId"],
                    Nearest = "windowId",
                },
                new ArgumentProblem("scope", "expected one of the allowed values") { Allowed = ["cpu", "disk"] },
                new ArgumentProblem("level", "required and missing"),
            ]);

        using JsonDocument facts = JsonDocument.Parse(message);
        JsonElement problems = facts.RootElement.GetProperty("argumentProblems");
        Assert.Multiple(() =>
        {
            Assert.That(problems[0].GetProperty("nearest").GetString(), Is.EqualTo("windowId"));
            Assert.That(problems[0].GetProperty("accepted").EnumerateArray().Select(static name => name.GetString()),
                Is.EqualTo(new[] { "appId", "windowId" }));
            Assert.That(problems[0].TryGetProperty("allowed", out _), Is.False);
            Assert.That(problems[1].GetProperty("allowed").EnumerateArray().Select(static value => value.GetString()),
                Is.EqualTo(new[] { "cpu", "disk" }));
            Assert.That(problems[1].TryGetProperty("nearest", out _), Is.False);
            Assert.That(problems[2].EnumerateObject().Select(static field => field.Name),
                Is.EqualTo(new[] { "argument", "problem" }));
        });
    }

    // input.scroll may name the control of the last view to scroll (a list, a conversation) instead of the window.
    [TestCase("""{"amount":3,"direction":"down"}""", true)]
    [TestCase("""{"amount":3,"direction":"down","index":0}""", true)]
    [TestCase("""{"amount":3,"direction":"up","index":59}""", true)]
    [TestCase("""{"amount":3,"direction":"up","index":null}""", true)]
    // Ronda 23 (t-menu-2): the look numbers past its cap (the goal's reserved room, the body); 60 is one of its
    // controls now and the first index past the look is VisibleViewNumbering.HighestIndex + 1 (71).
    [TestCase("""{"amount":3,"direction":"up","index":60}""", true)]
    [TestCase("""{"amount":3,"direction":"up","index":70}""", true)]
    [TestCase("""{"amount":3,"direction":"up","index":71}""", false)]
    [TestCase("""{"amount":3,"direction":"up","index":-1}""", false)]
    [TestCase("""{"amount":3,"direction":"up","index":"2"}""", false)]
    public void ScrollMayTargetOneControlOfTheView(string json, bool expected)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("input.scroll");
        using JsonDocument arguments = JsonDocument.Parse(json);

        Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, descriptor.ArgumentsSchema), Is.EqualTo(expected));
    }

    // Goal v3 point 2: a scroll may name the element to bring into view (label), a text whether it replaces the value of
    // the field it sets (replace), a click what it writes over (consequence, only «overwrite»). Auditoría final 2, fila
    // 12: a field named by its label (field) was resolved only by the retired mission and is no argument.
    [TestCase("input.scroll", """{"amount":3,"direction":"down","label":"Omega","window":4660}""", true)]
    [TestCase("input.scroll", """{"amount":3,"direction":"down","label":null}""", true)]
    [TestCase("input.scroll", """{"amount":3,"direction":"down","label":5}""", false)]
    [TestCase("input.text.type", """{"text":"800","index":2,"replace":true,"window":4660}""", true)]
    [TestCase("input.text.type", """{"text":"800","field":"Ancho","index":2,"window":4660}""", false)]
    [TestCase("input.text.type", """{"text":"800","replace":"yes"}""", false)]
    // Práctica V5E061 («cámbialo, era el miércoles, no el martes»): the one part of the text to change, as it is there.
    [TestCase("input.text.type", """{"text":"miércoles","replacing":"martes","window":4660}""", true)]
    [TestCase("input.text.type", """{"text":"miércoles","replacing":null}""", true)]
    [TestCase("input.text.type", """{"text":"miércoles","replacing":" "}""", false)]
    [TestCase("input.text.type", """{"text":"miércoles","replacing":3}""", false)]
    // Ronda 19 (r17 t2-c13): the country the person's speech marks goes with the place as a declared hint.
    [TestCase("weather.current", """{"location":"Valencia","dialectCountry":"ES"}""", true)]
    [TestCase("weather.current", """{"location":"Valencia","dialectCountry":null}""", true)]
    [TestCase("weather.current", """{"location":"Curicó"}""", true)]
    [TestCase("weather.current", """{"location":"Valencia","dialectCountry":"España"}""", false)]
    [TestCase("weather.current", """{"location":"Valencia","dialectCountry":"FR"}""", false)]
    // Review of combos-galerias (finding 1): the entry of a list chosen by pattern, as the mind sends it.
    [TestCase("input.text.type", """{"text":"Wingdings","index":3,"replace":true,"entry":true,"window":4660}""", true)]
    [TestCase("input.text.type", """{"text":"Wingdings","entry":null}""", true)]
    [TestCase("input.text.type", """{"text":"Wingdings","entry":"yes"}""", false)]
    [TestCase("input.visible.click", """{"label":"Sí","consequence":"overwrite"}""", true)]
    [TestCase("input.visible.click", """{"label":"Sí","consequence":"delete"}""", false)]
    [TestCase("input.key.press", """{"key":"shift_f10"}""", true)]
    [TestCase("input.key.press", """{"key":"ctrl_shift_s"}""", true)]
    [TestCase("input.key.press", """{"key":"ctrl_end"}""", true)]
    [TestCase("input.key.press", """{"key":"ctrl_home"}""", true)]
    [TestCase("input.key.press", """{"key":"alt_f4"}""", false)]
    [TestCase("input.key.press", """{"key":"enter","consequence":"overwrite"}""", true)]
    [TestCase("input.key.press", """{"key":"enter","consequence":"delete"}""", false)]
    // Ronda 21 (vista ordenada por objetivo): the goal's words go with the mission's look, bounded; a word that is not
    // text, an empty word or more than the bound is refused.
    [TestCase("input.visible.controls", """{"limit":60,"wanted":["aplicacion","application"]}""", true)]
    [TestCase("input.visible.controls", """{"limit":60,"wanted":null}""", true)]
    [TestCase("input.visible.controls", """{"limit":60}""", true)]
    [TestCase("input.visible.controls", """{"limit":60,"wanted":[" "]}""", false)]
    [TestCase("input.visible.controls", """{"limit":60,"wanted":[3]}""", false)]
    [TestCase("input.visible.controls", """{"limit":60,"wanted":"aplicacion"}""", false)]
    [TestCase("input.visible.controls", """{"wanted":["a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y"]}""", false)]
    // Auditoría K9: what only the retired mission sent to its look is no argument; a look may name the windows it
    // reads by the number an earlier look gave, and ask for the newest entries of a conversation.
    [TestCase("input.visible.controls", """{"limit":60,"application":"Calculadora","identityIfAbsent":true}""", false)]
    [TestCase("input.visible.controls", """{"limit":60,"candidates":true}""", false)]
    [TestCase("input.visible.controls", """{"limit":60,"known":[4660]}""", false)]
    [TestCase("input.visible.controls", """{"limit":60,"processId":4242}""", false)]
    [TestCase("input.visible.controls", """{"limit":60,"starting":true}""", false)]
    [TestCase("input.visible.controls", """{"limit":60,"tail":true}""", true)]
    [TestCase("input.visible.controls", """{"limit":60,"windows":[4660]}""", false)]
    public void TheTypesOfTaskOfV3AreArgumentsOfThePrimitives(string operation, string json, bool expected)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired(operation);
        using JsonDocument arguments = JsonDocument.Parse(json);

        Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, descriptor.ArgumentsSchema), Is.EqualTo(expected));
    }

    [TestCase("{\"applicationName\":\"Calculadora\"}", true)]
    [TestCase("{\"applicationName\":\" \"}", false)]
    public void WindowInventoryAcceptsTheApplicationNameSelectorOfV3(string json, bool expected)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("window.resolve");
        using JsonDocument arguments = JsonDocument.Parse(json);

        Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, descriptor.ArgumentsSchema), Is.EqualTo(expected));
    }

    [Test]
    public void CatalogHasStableUniqueCompleteToolDescriptors()
    {
        ProductOperationDescriptor[] descriptors = ProductCatalog.ToolDescriptors.ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(descriptors, Has.Length.EqualTo(ExpectedDescriptors));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.Name),
                Is.SupersetOf(C03CatalogAdditions));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.Name),
                Is.SupersetOf(Reopen1993CatalogAdditions).And.SupersetOf(ComputerUseAdditions)
                    .And.SupersetOf(RenewAgentAdditions).And.SupersetOf(RenewRealesAdditions)
                    .And.SupersetOf(UsoRealAdditions).And.SupersetOf(ConversationAdditions));
            Assert.That(descriptors.Select(static descriptor => descriptor.Name),
                Has.None.AnyOf(RenewRetired));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.Name),
                Is.EqualTo(descriptors.Select(static descriptor => descriptor.Name)
                    .Order(StringComparer.Ordinal)));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.Name).Distinct(StringComparer.Ordinal),
                Is.EquivalentTo(descriptors.Select(static descriptor => descriptor.Name)));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.VerifierContractId)
                    .Distinct(StringComparer.Ordinal).Count(),
                Is.EqualTo(descriptors.Length));
            Assert.That(descriptors.All(static descriptor =>
                OperationRisks.IsKnown(descriptor.Risk)), Is.True);
            Assert.That(descriptors.All(static descriptor =>
                !string.IsNullOrWhiteSpace(descriptor.VerifierContractId)), Is.True);
        });
    }

    // Al máximo, flujos (audit of the daily flows, finding 2): the operations whose provider may take longer than an
    // ordinary call say how long (the provider's own budget), and the App waits that long before its margin runs out.
    [Test]
    public void OnlyTheOperationsWhoseProviderTakesLongDeclareTheirBudget()
    {
        var expected = new Dictionary<string, TimeSpan>(StringComparer.Ordinal)
        {
            ["file.read"] = TimeSpan.FromSeconds(90),
            ["media.play.exact"] = TimeSpan.FromSeconds(85),
            ["media.play.query"] = TimeSpan.FromSeconds(85),
            ["message.send.test"] = TimeSpan.FromSeconds(90),
            ["ocr.read"] = TimeSpan.FromSeconds(90),
            ["system.status"] = TimeSpan.FromSeconds(90),
            ["vision.describe"] = TimeSpan.FromSeconds(90),
        };

        Assert.That(
            ProductCatalog.ToolDescriptors.Where(static d => d.Budget is not null)
                .ToDictionary(static d => d.Name, static d => d.Budget!.Value, StringComparer.Ordinal),
            Is.EquivalentTo(expected));
    }

    [Test]
    public void PublicToolProjectionCarriesTheExactSchemaRiskVerifierAndDescription()
    {
        OperationDescriptor[] tools = ProductCatalog.ToolDescriptors
            .Select(static descriptor => ProductCatalog.CreateToolDescriptor(
                new OperationDefinition(descriptor)))
            .ToArray();

        Assert.That(tools, Has.Length.EqualTo(ExpectedDescriptors));
        for (int index = 0; index < tools.Length; index++)
        {
            ProductOperationDescriptor product = ProductCatalog.ToolDescriptors[index];
            OperationDescriptor tool = tools[index];
            Assert.Multiple(() =>
            {
                Assert.That(tool.Name, Is.EqualTo(product.Name));
                Assert.That(
                    tool.ArgumentsSchema.GetRawText(),
                    Is.EqualTo(product.ArgumentsSchema.CanonicalJson),
                    product.Name);
                Assert.That(tool.Risk, Is.EqualTo(product.Risk), product.Name);
                Assert.That(
                    tool.VerifierContractId,
                    Is.EqualTo(product.VerifierContractId),
                    product.Name);
                Assert.That(tool.Description, Is.EqualTo(product.Description), product.Name);
                Assert.That(tool.Effects ?? [], Is.EqualTo(product.EffectKinds), product.Name);
            });
        }

        Assert.That(
            () => ProductCatalog.CreateToolDescriptor(
                new OperationDefinition("note.create", OperationRisk.Reversible, "Not from the catalog.")),
            Throws.ArgumentException);
    }

    // Al máximo, B-APP-10 (00_IDENTIDAD: cero listas de apps, nada de código que nombre una app): app.open decía
    // «También acepta windows.calculator», un alias con proveedor propio junto al camino genérico del catálogo Inicio.
    // Ninguna descripción ofrece un identificador con puntos que no sea el nombre de una operación del catálogo.
    [Test]
    public void NoDescriptionOffersAnIdentifierThatIsNotAnOperation()
    {
        HashSet<string> operations = [.. ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name)];
        string[] aliases = [.. ProductCatalog.ToolDescriptors
            .SelectMany(static descriptor => System.Text.RegularExpressions.Regex
                .Matches(descriptor.Description, @"(?<![\w/\\])[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+(?!\w)")
                .Select(match => (descriptor.Name, Identifier: match.Value)))
            .Where(found => !operations.Contains(found.Identifier))
            .Select(static found => $"{found.Name}: {found.Identifier}")];

        Assert.That(aliases, Is.Empty);
    }

    // Al máximo 5.1: a conditional effect holds only with the arguments that make it happen.
    [TestCase("app.open", "{\"appId\":\"Spotify\"}", false)]
    [TestCase("app.open", "{\"appId\":\"Spotify\",\"foreground\":true}", true)]
    [TestCase("system.settings.set", "{\"setting\":\"airplane_mode\",\"value\":1}", false)]
    [TestCase("system.settings.set", "{\"setting\":\"do_not_disturb\",\"value\":1}", true)]
    [TestCase("input.key.press", "{}", true)]
    [TestCase("window.minimize", "{}", false)]
    public void AWindowEffectIsReadWithTheCallsArguments(string operation, string arguments, bool expected)
    {
        using JsonDocument given = JsonDocument.Parse(arguments);
        Assert.That(ProductCatalog.GetRequired(operation).Has(OperationEffects.WindowInput, given.RootElement),
            Is.EqualTo(expected));
    }

    // Auditoría del núcleo 2026-10-23: what the model wrote that a search or an address takes out of the PC is the
    // network effect (OperationEffects.Network: «a query, an address, a host, a place, a title»), which the App's brake
    // on remembered values (NetworkEgress) reads; these went out unasked in normal mode without it.
    [TestCase("media.play.query", "{\"provider\":\"spotify\",\"query\":\"x\"}")]
    [TestCase("media.play.exact", "{\"provider\":\"spotify\",\"title\":\"x\"}")]
    [TestCase("media.play.youtube", "{\"query\":\"x\"}")]
    [TestCase("streaming.play.named", "{\"service\":\"netflix\",\"title\":\"x\"}")]
    [TestCase("streaming.navigate", "{\"service\":\"netflix\",\"resourceUri\":\"https://www.netflix.com/title/1\"}")]
    [TestCase("game.store.search", "{\"query\":\"x\"}")]
    [TestCase("game.store.page", "{\"title\":\"x\"}")]
    public void WhatASearchOrAnAddressTakesOutOfThePcIsTheNetworkEffect(string operation, string arguments)
    {
        using JsonDocument given = JsonDocument.Parse(arguments);
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired(operation);
        Assert.Multiple(() =>
        {
            Assert.That(OperationArgumentValidator.IsValid(given.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(descriptor.Has(OperationEffects.Network, given.RootElement), Is.True);
            Assert.That(RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(descriptor.Risk), ConfirmationMode.Normal,
                operation, given.RootElement), Is.EqualTo(PolicyDecision.Allow));
        });
    }

    [Test]
    public void HistoricalCdpInspectionCapabilitiesArePrivateBoundedAndReadOnlyInEffect()
    {
        ProductOperationDescriptor page = ProductCatalog.GetRequired("browser.page.read");
        ProductOperationDescriptor tabs = ProductCatalog.GetRequired("browser.tabs.list");

        Assert.Multiple(() =>
        {
            Assert.That(page.Risk, Is.EqualTo(OperationRisks.PrivacySensitive));
            Assert.That(tabs.Risk, Is.EqualTo(OperationRisks.PrivacySensitive));
            Assert.That(page.VerifierContractId,
                Is.EqualTo("browser.page.read.cdp.dom.snapshot.v1"));
            Assert.That(tabs.VerifierContractId,
                Is.EqualTo("browser.tabs.list.cdp.targets.snapshot.v1"));
            Assert.That(page.ArgumentsSchema.CanonicalJson,
                Does.Contain("\"maximumCharacters\""));
            Assert.That(tabs.ArgumentsSchema.CanonicalJson, Does.Contain("\"limit\""));
        });
    }

    // BAXY Renew agent tools (2026-10-15): the four file operations take their typed arguments and nothing else.
    // Reading and finding change nothing; writing and editing are reversible (what they replace goes to the Recycle
    // Bin first), so Normal runs every one of them without asking.
    [TestCase("file.find", """{"folder":"desktop"}""", true)]
    [TestCase("file.find", """{"folder":"all_known","query":"*.pdf","order":"recent","limit":5}""", true)]
    [TestCase("file.find", """{"folder":"documents","content":"reunión","subdirectory":"trabajo"}""", true)]
    [TestCase("file.find", """{"folder":"pictures"}""", false)]
    [TestCase("file.find", """{"query":"informe"}""", false)]
    [TestCase("file.read", """{"fileName":"informe.pdf","folder":"all_known","offset":4000,"maximumCharacters":4000}""", true)]
    [TestCase("file.read", """{"fileName":"notas/ideas.md","folder":"desktop"}""", true)]
    [TestCase("file.read", """{"fileName":"notas.txt","folder":"desktop","offset":-1}""", false)]
    [TestCase("file.read", """{"fileName":"notas.txt","folder":"desktop","maximumCharacters":100}""", false)]
    [TestCase("file.write", """{"relativePath":"hola.txt","text":"hola","folder":"desktop"}""", true)]
    [TestCase("file.write", """{"relativePath":"lista.txt","text":"pan","append":true}""", true)]
    [TestCase("file.write", """{"relativePath":"hola.txt","text":"hola","folder":"all_known"}""", false)]
    [TestCase("file.edit", """{"fileName":"notas.txt","folder":"desktop","oldText":"lunes","newText":"martes"}""", true)]
    [TestCase("file.edit", """{"fileName":"notas.txt","folder":"desktop","oldText":"2024","newText":"","replaceAll":true}""", true)]
    [TestCase("file.edit", """{"fileName":"notas.txt","folder":"desktop","oldText":"lunes"}""", false)]
    public void TheFileOperationsTakeTypedArgumentsAndNeverAskInNormalMode(string operation, string json, bool expected)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired(operation);
        using JsonDocument arguments = JsonDocument.Parse(json);

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(operation is "file.find" or "file.read"
                ? OperationRisks.ReadOnly : OperationRisks.LowReversible));
            Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, descriptor.ArgumentsSchema),
                Is.EqualTo(expected));
            if (expected)
            {
                Assert.That(
                    RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(descriptor.Risk), ConfirmationMode.Normal,
                        descriptor.Name, arguments.RootElement),
                    Is.EqualTo(PolicyDecision.Allow));
            }
        });
    }

    [TestCase("conversation.list", OperationRisks.ReadOnly, "{}", "{\"conversation\":\"ayer\"}")]
    [TestCase("conversation.new", OperationRisks.LowReversible, "{}", "{\"title\":\"Viaje\"}")]
    [TestCase("conversation.open", OperationRisks.LowReversible, "{\"conversation\":\"Viaje\"}", "{}")]
    [TestCase("conversation.rename", OperationRisks.LowReversible, "{\"title\":\"Viaje\"}", "{\"title\":\" \"}")]
    [TestCase("conversation.rename", OperationRisks.LowReversible,
        "{\"conversation\":\"ab12cd34ef56\",\"title\":\"Viaje\"}", "{\"conversation\":\"ab12cd34ef56\"}")]
    public void TheConversationsAreToolsThatNeverAskForTheYes(string name, string risk, string valid, string invalid)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired(name);
        using JsonDocument accepted = JsonDocument.Parse(valid);
        using JsonDocument refused = JsonDocument.Parse(invalid);

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(risk));
            Assert.That(OperationArgumentValidator.IsValid(accepted.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(refused.RootElement, descriptor.ArgumentsSchema), Is.False);
            foreach (ConfirmationMode mode in Enum.GetValues<ConfirmationMode>())
            {
                Assert.That(RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(descriptor.Risk), mode, name,
                    accepted.RootElement), Is.EqualTo(PolicyDecision.Allow), $"{name} {mode}");
            }
        });
    }

    [Test]
    public void AudioStatusIsPublicReadOnlyAndAcceptsOnlyEmptyArguments()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("audio.status");
        using JsonDocument empty = JsonDocument.Parse("{}");
        using JsonDocument extra = JsonDocument.Parse("{\"scope\":\"output\"}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.ReadOnly));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("audio.status.endpoint.read.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                empty.RootElement,
                descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement,
                descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void MediaStatusIsPublicReadOnlyAndAcceptsOnlyEmptyArguments()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("media.status");
        using JsonDocument empty = JsonDocument.Parse("{}");
        using JsonDocument extra = JsonDocument.Parse("{\"provider\":\"spotify\"}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.ReadOnly));
            Assert.That(descriptor.VerifierContractId, Is.EqualTo("media.status.smtc.read.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                empty.RootElement,
                descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement,
                descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void KeyPressIsPublicBoundedAndRejectsUnsafeCombinations()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("input.key.press");
        using JsonDocument escape = JsonDocument.Parse("{\"key\":\"escape\"}");
        using JsonDocument altF4 = JsonDocument.Parse("{\"key\":\"alt+f4\"}");
        using JsonDocument extra = JsonDocument.Parse("{\"key\":\"escape\",\"repeat\":2}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.LowReversible));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("input.key.press.win32.sendinput.accepted.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                escape.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                altF4.RootElement, descriptor.ArgumentsSchema), Is.False);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void ClipboardPasteIsPrivacySensitiveClosedAndUsesFocusedClipboardVerifier()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("clipboard.paste");
        using JsonDocument empty = JsonDocument.Parse("{}");
        using JsonDocument extra = JsonDocument.Parse("{\"text\":\"secret\"}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.PrivacySensitive));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("clipboard.paste.win32.clipboard.foreground.sendinput.accepted.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                empty.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void ClipboardCopyIsPrivacySensitiveAndRequiresClipboardSequencePostread()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("clipboard.copy");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.PrivacySensitive));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("clipboard.copy.win32.foreground.sendinput.sequence.postread.v1"));
        });
    }

    // Decisión del dueño 2026-09-13 (DECISIONES_DUENO_2026-09-13.md §6, NETWORK1201, 0fed0df6c): la IP
    // propia se lee a pedido sin confirmación; el riesgo pasó de privacy_sensitive a read_only.
    [Test]
    public void NetworkIpListIsReadOnlyClosedAndDoubleReadVerified()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("network.ip.list");
        using JsonDocument empty = JsonDocument.Parse("{}");
        using JsonDocument extra = JsonDocument.Parse("{\"scope\":\"public\"}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.ReadOnly));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("network.ip.list.windows.unicast.secondread.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                empty.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void WifiStatusIsReadOnlyClosedAndDoubleReadVerified()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("wifi.status");
        using JsonDocument empty = JsonDocument.Parse("{}");
        using JsonDocument extra = JsonDocument.Parse("{\"includeSsid\":true}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.ReadOnly));
            Assert.That(
                RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(descriptor.Risk), operation: descriptor.Name),
                Is.EqualTo(PolicyDecision.Allow));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("wifi.status.netsh.wlan.secondread.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                empty.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                extra.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void PowerTransitionsAllowSessionSignoutWithoutConfirmation()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("system.power");
        using JsonDocument signout = JsonDocument.Parse("{\"action\":\"signout\"}");
        using JsonDocument shutdown = JsonDocument.Parse("{\"action\":\"shutdown\"}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.WorkLoss));
            Assert.That(
                RiskPolicy.Evaluate(
                    ProductCatalog.ToPolicyRisk(descriptor.Risk),
                    operation: descriptor.Name),
                Is.EqualTo(PolicyDecision.Allow));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("system.power.windows.transition.receipt.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                signout.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                shutdown.RootElement, descriptor.ArgumentsSchema), Is.True);
        });
    }

    [Test]
    public void WorkLossChallengesInNormalModeAndBypassSkipsIt()
    {
        ProductOperationDescriptor recycle = ProductCatalog.GetRequired("system.recyclebin.empty");
        ProductOperationDescriptor close = ProductCatalog.GetRequired("app.close");
        ProductOperationDescriptor overwrite = ProductCatalog.GetRequired("memory.forget");

        Assert.Multiple(() =>
        {
            Assert.That(recycle.Risk, Is.EqualTo(OperationRisks.WorkLoss));
            Assert.That(close.Risk, Is.EqualTo(OperationRisks.WorkLoss));
            Assert.That(overwrite.Risk, Is.EqualTo(OperationRisks.WorkLoss));
            Assert.That(
                RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(recycle.Risk)),
                Is.EqualTo(PolicyDecision.RequireConfirmation));
            Assert.That(
                RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(close.Risk)),
                Is.EqualTo(PolicyDecision.RequireConfirmation));
            Assert.That(
                RiskPolicy.Evaluate(
                    ProductCatalog.ToPolicyRisk(recycle.Risk),
                    ConfirmationMode.Bypass),
                Is.EqualTo(PolicyDecision.Allow));
        });
    }

    [Test]
    public void MediaSeekIsPublicReversibleAndBoundsTheRelativeDelta()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("media.seek.relative");
        using JsonDocument valid = JsonDocument.Parse("{\"seconds\":-15}");
        using JsonDocument zero = JsonDocument.Parse("{\"seconds\":0}");
        using JsonDocument excessive = JsonDocument.Parse("{\"seconds\":3601}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.LowReversible));
            Assert.That(descriptor.VerifierContractId,
                Is.EqualTo("media.seek.relative.smtc.timeline.postread.v1"));
            Assert.That(OperationArgumentValidator.IsValid(
                valid.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                zero.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(
                excessive.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void EverySchemaIsClosedCanonicalAndSelfDescribing()
    {
        foreach (ProductOperationDescriptor descriptor in ProductCatalog.ToolDescriptors)
        {
            OperationArgumentsSchema schema = descriptor.ArgumentsSchema;
            using JsonDocument document = JsonDocument.Parse(schema.CanonicalJson);
            JsonElement root = document.RootElement;

            Assert.Multiple(() =>
            {
                Assert.That(root.GetProperty("type").GetString(), Is.EqualTo("object"), descriptor.Name);
                Assert.That(root.GetProperty("additionalProperties").GetBoolean(), Is.False, descriptor.Name);
                Assert.That(root.GetProperty("properties").EnumerateObject()
                    .Select(static property => property.Name),
                    Is.EqualTo(schema.Properties.Select(static property => property.Name)),
                    descriptor.Name);
                Assert.That(root.GetProperty("required").EnumerateArray()
                    .Select(static item => item.GetString()),
                    Is.EqualTo(schema.Required),
                    descriptor.Name);
                Assert.That(root.GetRawText(), Is.EqualTo(schema.CanonicalJson), descriptor.Name);
            });
        }
    }

    [TestCase("{\"level\":0}", true)]
    [TestCase("{\"level\":100}", true)]
    [TestCase("{\"level\":-1}", false)]
    [TestCase("{\"level\":101}", false)]
    [TestCase("{\"level\":1.0}", false)]
    [TestCase("{\"level\":\"50\"}", false)]
    [TestCase("{\"level\":50,\"extra\":true}", false)]
    [TestCase("{}", false)]
    public void ValidatorRejectsExtraWrongTypeMissingAndOutOfRangeArguments(
        string json,
        bool expected)
    {
        using JsonDocument document = JsonDocument.Parse(json);

        bool valid = OperationArgumentValidator.IsValid(
            document.RootElement,
            ProductCatalog.GetRequired("audio.volume").ArgumentsSchema);

        Assert.That(valid, Is.EqualTo(expected));
    }

    [Test]
    public void RegistryAndCatalogAreOneToOneByExactDescriptorIdentity()
    {
        var exact = new OperationRegistry(ProductCatalog.ToolDescriptors.Select(
            static descriptor => (IOperationHandler)new StubHandler(
                ProductCatalog.CreateDefinition(descriptor.Name))));
        IOperationHandler[] altered = ProductCatalog.ToolDescriptors.Select(
                static descriptor => (IOperationHandler)new StubHandler(
                    ProductCatalog.CreateDefinition(descriptor.Name)))
            .ToArray();
        altered[0] = new StubHandler(new OperationDefinition(
            altered[0].Definition.Name,
            altered[0].Definition.Risk,
            altered[0].Definition.Description));
        var nonCatalogRegistry = new OperationRegistry(altered);

        Assert.Multiple(() =>
        {
            Assert.That(() => ProductCatalog.ValidateAgainst(exact), Throws.Nothing);
            Assert.That(
                () => ProductCatalog.ValidateAgainst(nonCatalogRegistry),
                Throws.InvalidOperationException);
            Assert.That(exact.Definitions.All(static definition =>
                definition.ProductDescriptor is not null), Is.True);
            Assert.That(exact.Definitions, Has.Count.EqualTo(ExpectedDescriptors));
            Assert.That(exact.ToolDescriptors, Has.Count.EqualTo(ExpectedDescriptors));
            Assert.That(
                exact.ToolDescriptors.Select(static descriptor => descriptor.Name),
                Is.EqualTo(ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name)));
        });
    }

    [Test]
    public void NullableEnumHasMatchingCanonicalSchemaAndRuntimeValidation()
    {
        OperationArgumentsSchema schema = ProductCatalog.GetRequired("note.list").ArgumentsSchema;
        using JsonDocument supplied = JsonDocument.Parse("{\"scope\":null}");
        using JsonDocument canonical = JsonDocument.Parse(schema.CanonicalJson);
        JsonElement scope = canonical.RootElement
            .GetProperty("properties")
            .GetProperty("scope");

        Assert.Multiple(() =>
        {
            Assert.That(OperationArgumentValidator.IsValid(supplied.RootElement, schema), Is.True);
            Assert.That(scope.GetProperty("type").EnumerateArray()
                .Select(static value => value.GetString()),
                Is.EqualTo(new string?[] { "null", "string" }));
            Assert.That(scope.GetProperty("enum").EnumerateArray().First().ValueKind,
                Is.EqualTo(JsonValueKind.Null));
        });
    }

    [Test]
    public void CatalogAssemblyHasNoParserPlannerOrModelRuntimeDependency()
    {
        string[] references = typeof(ProductCatalog).Assembly
            .GetReferencedAssemblies()
            .Select(static assembly => assembly.Name ?? string.Empty)
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(references, Does.Not.Contain("Baxy.App"));
            Assert.That(references, Does.Not.Contain("Baxy.Core"));
            Assert.That(references.Any(static reference =>
                reference.Contains("Parser", StringComparison.OrdinalIgnoreCase)
                || reference.Contains("Planner", StringComparison.OrdinalIgnoreCase)
                || reference.Contains("ModelRuntime", StringComparison.OrdinalIgnoreCase)),
                Is.False);
        });
    }

    private sealed class StubHandler(OperationDefinition definition) : IOperationHandler
    {
        public OperationDefinition Definition { get; } = definition;

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(OperationOutcome.Success(
                JsonDocument.Parse("{}").RootElement.Clone()));
        }
    }
}
