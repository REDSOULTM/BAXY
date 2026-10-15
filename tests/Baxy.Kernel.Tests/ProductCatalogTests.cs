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
    // retiraron en BAXY Renew (RenewAgentRetirements).
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
        "notification.list",
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
    // encuesta pedía y el catálogo no tenía (document.text.read se retiró en BAXY Renew).
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
        "web.news.headlines",
    ];


    // Motor de computer use (plan post-goal Fase 4, D21; CONTRATO_VISTA_ACCION.md):
    // el desplazamiento verificado por superficie y la misión general del shell (el arrastre de v3 se retiró en la
    // estabilización L: arrastrar es un límite declarado).
    internal static readonly string[] ComputerUseAdditions =
    [
        "input.scroll",
        "mission.computer.use",
    ];

    // BAXY Renew, herramientas de agente (2026-10-15): leer una página pública como texto, y editar, buscar, leer y
    // escribir archivos con cuatro operaciones que sustituyen a las seis de RenewAgentRetirements.
    internal static readonly string[] RenewAgentAdditions =
    [
        "file.edit",
        "file.find",
        "file.read",
        "file.write",
        "web.fetch",
    ];

    internal static readonly string[] RenewAgentRetirements =
    [
        "document.pdf.read",
        "document.text.read",
        "filesystem.known.list",
        "filesystem.known.search",
        "filesystem.sandbox.append.named",
        "filesystem.write.text",
    ];

    internal const int ExpectedDescriptors = 170 + 21 + 14 + 2 + 5 - 6;

    internal const int ExpectedTools = ExpectedDescriptors - 1;

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

    // Ronda 23: the cause a refused act is handed back with names the arguments the schema refuses, and none for
    // arguments it takes (counter-case).
    [Test]
    public void TheInvalidArgumentsAreNamedAndNoneForValidOnes()
    {
        OperationArgumentsSchema schema = ProductCatalog.GetRequired("input.visible.click").ArgumentsSchema;
        using JsonDocument wrong = JsonDocument.Parse("{\"index\":71,\"manner\":\"triple\",\"labelz\":\"x\"}");
        using JsonDocument right = JsonDocument.Parse("{\"index\":70,\"label\":\"Tamaño\",\"manner\":\"menu\"}");

        Assert.Multiple(() =>
        {
            Assert.That(OperationArgumentValidator.InvalidArguments(wrong.RootElement, schema),
                Is.EqualTo(new[] { "index", "manner", "labelz", "label" }));
            Assert.That(OperationArgumentValidator.InvalidArguments(right.RootElement, schema), Is.Empty);
            Assert.That(OperationArgumentValidator.IsValid(right.RootElement, schema), Is.True);
        });
    }

    // Computer use, chained missions (shared contract «steps»): up to ten ordered sub-goals (goal v3 point 2: long tasks;
    // the mind's MAX_STEPS was 8 only because this limit was), each a closed object with its goal, application and
    // success check; the whole mission up to thirty steps.
    [TestCase("""{"goal":"abre Steam"}""", true)]
    [TestCase("""{"goal":"abre Steam","budgetSteps":30}""", true)]
    [TestCase("""{"goal":"abre Steam","budgetSteps":31}""", false)]
    [TestCase("""{"goal":"abre Steam","steps":null}""", true)]
    [TestCase("""{"goal":"en esta ventana guardá","frontWindow":true}""", true)]
    [TestCase("""{"goal":"en esta ventana guardá","frontWindow":"si"}""", false)]
    [TestCase("""{"goal":"a y b","application":null,"successCheck":null,"steps":[{"goal":"a","application":"Steam","successCheck":"text:a"},{"goal":"b","application":null,"successCheck":null}]}""", true)]
    [TestCase("""{"goal":"a","steps":[{"goal":"a"}]}""", true)]
    [TestCase("""{"goal":"a","steps":[]}""", false)]
    [TestCase("""{"goal":"a","steps":[{"goal":" "}]}""", false)]
    [TestCase("""{"goal":"a","steps":[{"application":"Steam"}]}""", false)]
    [TestCase("""{"goal":"a","steps":[{"goal":"a","budgetSteps":3}]}""", false)]
    [TestCase("""{"goal":"a","steps":[{"goal":"a","application":7}]}""", false)]
    [TestCase("""{"goal":"a","steps":["a"]}""", false)]
    [TestCase("""{"goal":"a","steps":[{"goal":"1"},{"goal":"2"},{"goal":"3"},{"goal":"4"},{"goal":"5"},{"goal":"6"},{"goal":"7"},{"goal":"8"},{"goal":"9"},{"goal":"10"}]}""", true)]
    [TestCase("""{"goal":"a","steps":[{"goal":"1"},{"goal":"2"},{"goal":"3"},{"goal":"4"},{"goal":"5"},{"goal":"6"},{"goal":"7"},{"goal":"8"},{"goal":"9"},{"goal":"10"},{"goal":"11"}]}""", false)]
    // Ronda 20b, revisión 2: a sub-goal of a form carries the check of the whole form (formCheck), a string or null.
    [TestCase("""{"goal":"a","steps":[{"goal":"poner alto en 500","formCheck":"value:ancho=500&value:alto=500"}]}""", true)]
    [TestCase("""{"goal":"a","steps":[{"goal":"hacer clic en aceptar","formCheck":null}]}""", true)]
    [TestCase("""{"goal":"a","steps":[{"goal":"a","formCheck":7}]}""", false)]
    public void AComputerUseMissionMayChainOrderedSubgoals(string json, bool expected)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("mission.computer.use");
        using JsonDocument arguments = JsonDocument.Parse(json);

        Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, descriptor.ArgumentsSchema), Is.EqualTo(expected));
    }

    [Test]
    public void ASubgoalLongerThanItsContractIsRejected()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("mission.computer.use");
        string goal = new('x', 513);
        string application = new('y', 129);
        using JsonDocument longGoal = JsonDocument.Parse($$"""{"goal":"a","steps":[{"goal":"{{goal}}"}]}""");
        using JsonDocument longApplication = JsonDocument.Parse($$"""{"goal":"a","steps":[{"goal":"a","application":"{{application}}"}]}""");

        Assert.Multiple(() =>
        {
            Assert.That(OperationArgumentValidator.IsValid(longGoal.RootElement, descriptor.ArgumentsSchema), Is.False);
            Assert.That(OperationArgumentValidator.IsValid(longApplication.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public void TheSubgoalSchemaIsPublishedAsAClosedObjectInsideTheArray()
    {
        OperationDescriptor tool = ProductCatalog.CreateToolDescriptor(ProductCatalog.CreateDefinition("mission.computer.use"));
        JsonElement steps = tool.ArgumentsSchema.GetProperty("properties").GetProperty("steps");
        JsonElement items = steps.GetProperty("items");

        Assert.Multiple(() =>
        {
            Assert.That(steps.GetProperty("maxItems").GetInt32(), Is.EqualTo(10));
            Assert.That(steps.GetProperty("minItems").GetInt32(), Is.EqualTo(1));
            Assert.That(items.GetProperty("type").GetString(), Is.EqualTo("object"));
            Assert.That(items.GetProperty("additionalProperties").GetBoolean(), Is.False);
            Assert.That(items.GetProperty("required").EnumerateArray().Select(name => name.GetString()), Is.EqualTo(new[] { "goal" }));
            // Estabilización L: «limit» (the declared limit the sub-goal is) and «requires» (the device its place needs).
            Assert.That(
                items.GetProperty("properties").EnumerateObject().Select(property => property.Name),
                Is.EqualTo(new[] { "application", "formCheck", "goal", "limit", "requires", "successCheck" }));
        });
    }

    [Test]
    public void ObjectItemsCannotNestArrays()
    {
        var nested = new OperationArgumentsSchema(
            [new OperationArgumentProperty("tags", OperationJsonType.Array, itemTypes: OperationJsonType.String)],
            []);
        Assert.Throws<ArgumentException>(() => _ = new OperationArgumentProperty(
            "steps", OperationJsonType.Array, itemSchema: nested));
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

    // Goal v3 point 2: a scroll may name the element to bring into view (label), a text the field it sets (field) and
    // whether it replaces its value (replace), a click what it writes over (consequence, only «overwrite»).
    [TestCase("input.scroll", """{"amount":3,"direction":"down","label":"Omega","window":4660}""", true)]
    [TestCase("input.scroll", """{"amount":3,"direction":"down","label":null}""", true)]
    [TestCase("input.scroll", """{"amount":3,"direction":"down","label":5}""", false)]
    [TestCase("input.text.type", """{"text":"800","field":"Ancho","replace":true,"window":4660}""", true)]
    [TestCase("input.text.type", """{"text":"800","replace":"yes"}""", false)]
    // Ronda 19 (r17 t2-c13): the country the person's speech marks goes with the place as a declared hint.
    [TestCase("weather.current", """{"location":"Valencia","dialectCountry":"ES"}""", true)]
    [TestCase("weather.current", """{"location":"Valencia","dialectCountry":null}""", true)]
    [TestCase("weather.current", """{"location":"Curicó"}""", true)]
    [TestCase("weather.current", """{"location":"Valencia","dialectCountry":"España"}""", false)]
    [TestCase("weather.current", """{"location":"Valencia","dialectCountry":"FR"}""", false)]
    // Review of combos-galerias (finding 1): the entry of a list chosen by pattern, as the mind sends it.
    [TestCase("input.text.type", """{"text":"Wingdings","field":"Fuente","replace":true,"entry":true,"window":4660}""", true)]
    [TestCase("input.text.type", """{"text":"Wingdings","entry":null}""", true)]
    [TestCase("input.text.type", """{"text":"Wingdings","entry":"yes"}""", false)]
    [TestCase("input.visible.click", """{"label":"Sí","consequence":"overwrite"}""", true)]
    [TestCase("input.visible.click", """{"label":"Sí","consequence":"delete"}""", false)]
    [TestCase("input.key.press", """{"key":"shift_f10"}""", true)]
    [TestCase("input.key.press", """{"key":"ctrl_shift_s"}""", true)]
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
    // Ronda 26: the mission's first look asks only who is in front when the application named has no window.
    [TestCase("input.visible.controls", """{"limit":60,"application":"Calculadora","identityIfAbsent":true}""", true)]
    [TestCase("input.visible.controls", """{"limit":60,"identityIfAbsent":null}""", true)]
    [TestCase("input.visible.controls", """{"limit":60,"identityIfAbsent":"si"}""", false)]
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
        ProductOperationDescriptor[] descriptors = ProductCatalog.Descriptors.ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(descriptors, Has.Length.EqualTo(ExpectedDescriptors));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.Name),
                Is.SupersetOf(C03CatalogAdditions));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.Name),
                Is.SupersetOf(Reopen1993CatalogAdditions).And.SupersetOf(ComputerUseAdditions)
                    .And.SupersetOf(RenewAgentAdditions));
            Assert.That(
                descriptors.Select(static descriptor => descriptor.Name),
                Has.None.AnyOf(RenewAgentRetirements));
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
                descriptor.ArgumentsSchema.AdditionalProperties is false), Is.True);
            Assert.That(descriptors.All(static descriptor =>
                !string.IsNullOrWhiteSpace(descriptor.VerifierContractId)), Is.True);
            Assert.That(
                ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name),
                Is.EqualTo(descriptors
                    .Where(static descriptor => descriptor.Name != "app.status")
                    .Select(static descriptor => descriptor.Name)));
            Assert.That(ProductCatalog.ToolDescriptors, Has.Count.EqualTo(ExpectedTools));
            Assert.That(
                ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name),
                Does.Not.Contain("app.status"));
            Assert.That(
                ProductCatalog.GetRequired("app.status").ToolExposure,
                Is.EqualTo(ToolExposure.Internal));
        });
    }

    [Test]
    public void PublicToolProjectionCarriesTheExactSchemaRiskVerifierAndDescription()
    {
        OperationDescriptor[] tools = ProductCatalog.ToolDescriptors
            .Select(static descriptor => ProductCatalog.CreateToolDescriptor(
                new OperationDefinition(descriptor)))
            .ToArray();

        Assert.That(tools, Has.Length.EqualTo(ExpectedTools));
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
            });
        }

        Assert.That(
            () => ProductCatalog.CreateToolDescriptor(ProductCatalog.CreateDefinition("app.status")),
            Throws.ArgumentException);
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
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
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

    [Test]
    public void AudioStatusIsPublicReadOnlyAndAcceptsOnlyEmptyArguments()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("audio.status");
        using JsonDocument empty = JsonDocument.Parse("{}");
        using JsonDocument extra = JsonDocument.Parse("{\"scope\":\"output\"}");

        Assert.Multiple(() =>
        {
            Assert.That(descriptor.Risk, Is.EqualTo(OperationRisks.ReadOnly));
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
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
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
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
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
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
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
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
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
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
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
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
            Assert.That(descriptor.ToolExposure, Is.EqualTo(ToolExposure.Public));
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
        foreach (ProductOperationDescriptor descriptor in ProductCatalog.Descriptors)
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
        var exact = new OperationRegistry(ProductCatalog.Descriptors.Select(
            static descriptor => (IOperationHandler)new StubHandler(
                ProductCatalog.CreateDefinition(descriptor.Name))));
        IOperationHandler[] altered = ProductCatalog.Descriptors.Select(
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
            Assert.That(exact.ToolDefinitions, Has.Count.EqualTo(ExpectedTools));
            Assert.That(exact.ToolDescriptors, Has.Count.EqualTo(ExpectedTools));
            Assert.That(
                exact.ToolDefinitions.Select(static definition => definition.Name),
                Is.EqualTo(ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name)));
            Assert.That(
                exact.ToolDescriptors.Select(static descriptor => descriptor.Name),
                Is.EqualTo(ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name)));
            Assert.That(
                exact.ToolDefinitions.Select(static definition => definition.Name),
                Does.Not.Contain("app.status"));
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
