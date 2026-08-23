using System.Text;
using System.Text.Json;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class NaturalNoteRequestParserTests
{
    [TestCase("abre Bloc de notas")]
    [TestCase("abre Notepad")]
    [TestCase("open Notepad")]
    [TestCase("open Bloc de notas")]
    [TestCase("ABRE NOTEPAD.")]
    [TestCase("Open bloc DE notas!")]
    [TestCase("  abre Notepad!  ")]
    [TestCase("abre el bloc de notas")]
    [TestCase("open the Notepad")]
    [TestCase("open up Notepad")]
    [TestCase("open Notepad please")]
    [TestCase("open Notepad por favor")]
    [TestCase("¿puedes abrir Notepad?")]
    [TestCase("¿podrías abrir el Bloc de notas por favor?")]
    [TestCase("can you open Notepad?")]
    [TestCase("could you please launch the Notepad?")]
    [TestCase("abre el coso de notas")]
    [TestCase("abre la app de notas")]
    public void RoutesOnlyAllowlistedNaturalNotepadCommands(string text)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo("app.open"));
            Assert.That(operation?.Arguments.Count, Is.EqualTo(1));
            Assert.That(
                operation?.Arguments["appId"]?.GetValue<string>(),
                Is.EqualTo("windows.notepad"));
        });
    }

    [TestCase("no abras Notepad")]
    [TestCase("don't open Notepad")]
    [TestCase("si puedes, abre Notepad")]
    [TestCase("if possible, open Notepad")]
    [TestCase("¿abriste Notepad?")]
    [TestCase("¿cómo abro Notepad?")]
    [TestCase("¿se puede abrir Notepad?")]
    [TestCase("is Notepad open?")]
    [TestCase("how do I open Notepad?")]
    [TestCase("could Notepad be opened?")]
    [TestCase("abre Notepad o Calculadora")]
    [TestCase("abre C:\\Windows\\System32\\notepad.exe")]
    [TestCase("open ./notepad.exe")]
    [TestCase("abre https://example.com")]
    [TestCase("open file://C:/Windows/notepad.exe")]
    [TestCase("abre Notepad archivo.txt")]
    [TestCase("open Notepad --help")]
    [TestCase("open the app")]
    [TestCase("ejecuta pytest")]
    [TestCase("abre el menú de contexto")]
    [TestCase("abre el canal de anuncios")]
    [TestCase("Start a background job for me")]
    [TestCase("abrí chrome chrome chrome chrome chrome chrome chrome chrome")]
    [TestCase("abre Notepad\0")]
    [TestCase("abre Notepad & calc")]
    [TestCase("open Notepad; calc")]
    [TestCase("open Notepad | calc")]
    [TestCase("open Notepad > salida.txt")]
    [TestCase("open Notepad $(calc)")]
    [TestCase("abre Notepad y abre Calculadora")]
    [TestCase("open Notepad\nopen Notepad")]
    [TestCase("abre Notepad. abre Notepad")]
    [TestCase("abre Notepad?")]
    [TestCase("abre Notepad!!")]
    public void RejectsUnsafeAmbiguousOrNonImperativeAppOpenText(string text)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.False);
            Assert.That(operation, Is.Null);
        });
    }

    [TestCase("abre Calculadora", "windows.calculator")]
    [TestCase("abre Steam", "Steam")]
    [TestCase("open Spotify", "Spotify")]
    [TestCase("launch Google Chrome", "Google Chrome")]
    [TestCase("ouvre Discord", "Discord")]
    [TestCase("öffne Word", "Word")]
    [TestCase("apri Steam", "Steam")]
    [TestCase("abra Spotify", "Spotify")]
    [TestCase("abre Discord si está instalado", "Discord")]
    [TestCase("abre Steam pero no maximices ni lances juegos", "Steam")]
    [TestCase("abrí Chrome Chrome Chrome", "Chrome")]
    public void RoutesExactInstalledApplicationNamesWithoutInventingPaths(
        string text,
        string expectedAppId)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo("app.open"));
            Assert.That(operation?.Arguments["appId"]?.GetValue<string>(), Is.EqualTo(expectedAppId));
        });
    }

    [Test]
    public void HistoricalTwoWindowRequestRemainsAPlannerMission()
    {
        bool parsed = NaturalNoteRequestParser.TryParse(
            "abre dos ventanas livianas lado a lado: Notepad y Calculadora",
            out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.False);
            Assert.That(operation, Is.Null);
        });
    }

    [Test]
    public void RoutesNaturalCreateToExactTypedOperation()
    {
        bool parsed = NaturalNoteRequestParser.TryParse(
            "Crea una nota llamada Compras con leche, pan y café",
            out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo("note.create"));
            Assert.That(operation?.Arguments["title"]?.GetValue<string>(), Is.EqualTo("Compras"));
            Assert.That(
                operation?.Arguments["content"]?.GetValue<string>(),
                Is.EqualTo("leche, pan y café"));
        });
    }

    [TestCase("Muéstrame mis notas", null)]
    [TestCase("lista mis notas activas", null)]
    [TestCase("muestra mis notas en la papelera", "trashed")]
    public void RoutesNaturalListsWithBoundedScope(string text, string? expectedScope)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.That(parsed, Is.True);
        Assert.That(operation?.Name, Is.EqualTo("note.list"));
        Assert.That(operation?.Arguments["scope"]?.GetValue<string>(), Is.EqualTo(expectedScope));
    }

    [Test]
    public void UnknownOrDangerousTextDoesNotBecomeAFreeFormOperation()
    {
        bool parsed = NaturalNoteRequestParser.TryParse(
            "Ejecuta este PowerShell y borra Documentos",
            out RoutedOperation? operation);

        Assert.That(parsed, Is.False);
        Assert.That(operation, Is.Null);
    }

    private static IEnumerable<TestCaseData> HistoricalStandaloneNoteCreateCases()
    {
        (string Text, string Content, int MessageRows)[] historicalRows =
        [
            ("anota comprar leche", "comprar leche", 4),
            ("anota llamar al dentista", "llamar al dentista", 1),
            ("anota que tengo que comprar pan", "tengo que comprar pan", 2),
            ("anota que tengo que llamar al medico manana", "tengo que llamar al medico manana", 2),
            ("Crea una nota : comprar pan", "comprar pan", 1),
            ("crea una nota que diga comprar pan", "comprar pan", 15),
            ("creá una nota que diga comprar pan", "comprar pan", 4),
            ("crea una nota que diga comprar pan y guardala", "comprar pan", 2),
            ("crea una nota: comprar pan", "comprar pan", 1),
            ("create a note saying buy milk", "buy milk", 2),
            ("create a note: buy milk", "buy milk", 1),
            ("tomá nota de que compre pan", "compre pan", 1),
            ("tomá nota: comprar leche", "comprar leche", 4),
        ];

        int messageRow = 0;
        foreach ((string text, string content, int count) in historicalRows)
        {
            for (int occurrence = 1; occurrence <= count; occurrence++)
            {
                messageRow++;
                yield return new TestCaseData(text, content)
                    .SetName($"HistoricalStandaloneNoteCreate_{messageRow:D2}");
            }
        }
    }

    [TestCaseSource(nameof(HistoricalStandaloneNoteCreateCases))]
    public void RoutesAllFortyHistoricalStandaloneNoteCreateRows(
        string text,
        string expectedContent)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo("note.create"));
            Assert.That(operation?.Arguments["content"]?.GetValue<string>(), Is.EqualTo(expectedContent));
            Assert.That(operation?.Arguments["title"]?.GetValue<string>(), Is.EqualTo(expectedContent));
        });
    }

    [TestCase(
        "Crea una nota llamada «Compras» con «leche, pan y café»",
        "Compras",
        "leche, pan y café")]
    [TestCase(
        "creá una nota llamada Ideas con probar el nuevo flujo y guárdala",
        "Ideas",
        "probar el nuevo flujo")]
    [TestCase(
        "create a note called \"Groceries\" with \"buy milk\" and save it",
        "Groceries",
        "buy milk")]
    [TestCase(
        "Create a note called Plan with call Ana",
        "Plan",
        "call Ana")]
    public void RoutesNamedSpanishAndEnglishNotesAndRemovesOuterQuotes(
        string text,
        string expectedTitle,
        string expectedContent)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo("note.create"));
            Assert.That(operation?.Arguments["title"]?.GetValue<string>(), Is.EqualTo(expectedTitle));
            Assert.That(operation?.Arguments["content"]?.GetValue<string>(), Is.EqualTo(expectedContent));
        });
    }

    [TestCase("show me my active notes", null)]
    [TestCase("list the active notes", null)]
    [TestCase("muestra my notes", null)]
    [TestCase("show me my trashed notes", "trashed")]
    [TestCase("list the deleted notes", "trashed")]
    [TestCase("lista mis notes in trash", "trashed")]
    public void RoutesSpanishEnglishAndSpanglishNoteLists(string text, string? expectedScope)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo("note.list"));
            Assert.That(operation?.Arguments["scope"]?.GetValue<string>(), Is.EqualTo(expectedScope));
        });
    }

    [TestCase("lee la nota Compras", "note.read", "Compras")]
    [TestCase("muéstrame la nota llamada «Ideas»", "note.read", "Ideas")]
    [TestCase("read the note called Groceries", "note.read", "Groceries")]
    [TestCase("show me the note \"Trip\"", "note.read", "Trip")]
    [TestCase("borra la nota Compras", "note.trash", "Compras")]
    [TestCase("elimina la nota llamada Ideas", "note.trash", "Ideas")]
    [TestCase("mueve la nota Compras a la papelera", "note.trash", "Compras")]
    [TestCase("mueve a la papelera la nota Compras", "note.trash", "Compras")]
    [TestCase("delete the note called Groceries", "note.trash", "Groceries")]
    [TestCase("trash the note Trip", "note.trash", "Trip")]
    [TestCase("send the note Trip to trash", "note.trash", "Trip")]
    [TestCase("send to the trash the note Trip", "note.trash", "Trip")]
    [TestCase("restaura la nota Compras de la papelera", "note.restore", "Compras")]
    [TestCase("recupera la nota llamada Ideas", "note.restore", "Ideas")]
    [TestCase("restore the note Groceries from the trash", "note.restore", "Groceries")]
    [TestCase("recover the note called Trip", "note.restore", "Trip")]
    public void RoutesFiniteTitleBasedLifecycleCommands(
        string text,
        string expectedOperation,
        string expectedTitle)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo(expectedOperation));
            Assert.That(operation?.Arguments.Count, Is.EqualTo(1));
            Assert.That(operation?.Arguments["title"]?.GetValue<string>(), Is.EqualTo(expectedTitle));
        });
    }

    [Test]
    public void QuickTitleIsCanonicalAndDoesNotSplitTheUtf8Boundary()
    {
        string decomposed = "cafe\u0301";
        bool canonicalParsed = NaturalNoteRequestParser.TryParse(
            $"anota {decomposed}",
            out RoutedOperation? canonicalOperation);
        string longContent = string.Concat(Enumerable.Repeat("🙂", 31));
        bool longParsed = NaturalNoteRequestParser.TryParse(
            $"create a note: {longContent}",
            out RoutedOperation? longOperation);
        string? canonicalTitle = canonicalOperation?.Arguments["title"]?.GetValue<string>();
        string? boundedTitle = longOperation?.Arguments["title"]?.GetValue<string>();

        Assert.Multiple(() =>
        {
            Assert.That(canonicalParsed, Is.True);
            Assert.That(canonicalTitle, Is.EqualTo("café"));
            Assert.That(canonicalTitle?.IsNormalized(NormalizationForm.FormC), Is.True);
            Assert.That(longParsed, Is.True);
            Assert.That(Encoding.UTF8.GetByteCount(boundedTitle!), Is.EqualTo(120));
            Assert.That(boundedTitle!.EnumerateRunes().Count(), Is.EqualTo(30));
            Assert.That(longOperation?.Arguments["content"]?.GetValue<string>(), Is.EqualTo(longContent));
        });
    }

    [TestCase("no anotes comprar leche")]
    [TestCase("don't create a note saying buy milk")]
    [TestCase("si puedes, anota comprar leche")]
    [TestCase("create a note: buy milk if possible")]
    [TestCase("borra todas las notas")]
    [TestCase("borra la nota todas las notas")]
    [TestCase("delete all notes")]
    [TestCase("delete the note all notes")]
    [TestCase("borra la nota Compras y la nota Ideas")]
    [TestCase("creá una nota con la lista del súper y ponéme un recordatorio para mañana a las 9")]
    [TestCase("crea una nota que diga comprar pan y recuérdame mañana")]
    [TestCase("make a note with my grocery list and set a reminder for tomorrow morning")]
    [TestCase("lee sandbox/carter_test/nota.txt")]
    [TestCase("lee la nota nota.txt")]
    [TestCase("read the note C:\\notes\\private.txt")]
    [TestCase("anota")]
    [TestCase("toma nota")]
    [TestCase("crea una nota:")]
    [TestCase("create a note saying")]
    [TestCase("restaura todas las notas")]
    [TestCase("mueve todas las notas a la papelera")]
    [TestCase("anota comprar leche\0")]
    [TestCase("read the note Compras\nthen delete it")]
    public void RejectsNegatedBulkConditionalComposedMalformedAndFilesystemNoise(string text)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.False);
            Assert.That(operation, Is.Null);
        });
    }

    [Test]
    public void RejectsIsolatedUtf16SurrogatesWithoutThrowing()
    {
        string[] malformed =
        [
            "anota " + new string('\ud800', 1),
            "read the note " + new string('\udc00', 1),
        ];

        foreach (string text in malformed)
        {
            RoutedOperation? operation = null;
            bool parsed = false;
            Assert.DoesNotThrow(() => parsed = NaturalNoteRequestParser.TryParse(text, out operation));
            Assert.Multiple(() =>
            {
                Assert.That(parsed, Is.False);
                Assert.That(operation, Is.Null);
            });
        }
    }

    [Test]
    public void RetryKeepsMissionAndInvocationUntilATerminalResponse()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-retry-tests", Guid.NewGuid().ToString("N"));
        string outboxPath = Path.Combine(root, "shell", "retry-outbox.v1.json");
        bool parsed = NaturalNoteRequestParser.TryParse(
            "Crea una nota llamada Compras con leche, pan y café",
            out RoutedOperation? routed);
        Assert.That(parsed, Is.True);
        Assert.That(routed, Is.Not.Null);
        try
        {
            var registry = new RetryableOperationRegistry(outboxPath);
            PreparedOperation first = registry.GetOrAdd(routed!);
            OperationRequest firstRequest = first.CreateRequest();
            PreparedOperation retry = registry.GetOrAdd(routed!);
            OperationRequest retryRequest = retry.CreateRequest();

            Assert.Multiple(() =>
            {
                Assert.That(retry, Is.SameAs(first));
                Assert.That(retryRequest.RequestId, Is.Not.EqualTo(firstRequest.RequestId));
                Assert.That(retryRequest.MissionId, Is.EqualTo(firstRequest.MissionId));
                Assert.That(retryRequest.InvocationId, Is.EqualTo(firstRequest.InvocationId));
                Assert.That(retryRequest.Operation, Is.EqualTo(firstRequest.Operation));
                Assert.That(
                    retryRequest.Arguments.GetRawText(),
                    Is.EqualTo(firstRequest.Arguments.GetRawText()));
            });

            registry.MarkResolved(first);
            PreparedOperation nextMission = registry.GetOrAdd(routed!);
            Assert.That(nextMission.InvocationId, Is.Not.EqualTo(first.InvocationId));
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Test]
    public void NormalProcessLaunchFailuresAreHandledAsUnavailableStartup()
    {
        Exception[] failures =
        [
            new System.ComponentModel.Win32Exception(),
            new UnauthorizedAccessException(),
            new BadImageFormatException(),
            new InvalidDataException(),
            new ArgumentException(),
        ];

        Assert.That(failures, Has.All.Matches<Exception>(MainWindowViewModel.IsExpectedStartupFailure));
    }

    [Test]
    public void HandshakeRequiresEveryOperationAdvertisedByTheComposer()
    {
        OperationDescriptor[] catalog = ProductCatalog.ToolDescriptors
            .Select(static descriptor => ProductCatalog.CreateToolDescriptor(
                new OperationDefinition(descriptor)))
            .ToArray();
        var complete = new ProtocolHello(
            ProtocolTypes.Hello,
            ProtocolVersion.Current,
            "1.0.0",
            42,
            catalog);
        ProtocolHello incomplete = complete with
        {
            Capabilities = catalog.Where(static capability =>
                capability.Name != "note.create").ToArray(),
        };
        ProtocolHello notesOnly = complete with
        {
            Capabilities = catalog.Where(static capability =>
                capability.Name.StartsWith("note.", StringComparison.Ordinal)).ToArray(),
        };
        ProtocolHello wrongAppRisk = WithRisk(
            complete,
            "app.open",
            OperationRisks.ReadOnly);
        ProtocolHello wrongCreateRisk = WithRisk(
            complete,
            "note.create",
            OperationRisks.WorkLoss);
        ProtocolHello wrongMemoryRisk = WithRisk(
            complete,
            "memory.enable",
            OperationRisks.LowReversible);
        ProtocolHello wrongMuteRisk = WithRisk(
            complete,
            "audio.mute",
            OperationRisks.ReadOnly);
        ProtocolHello wrongVolumeRisk = WithRisk(
            complete,
            "audio.volume",
            OperationRisks.ReadOnly);
        ProtocolHello wrongListRisk = WithRisk(
            complete,
            "note.list",
            OperationRisks.LowReversible);
        ProtocolHello wrongStatusRisk = WithRisk(
            complete,
            "system.status",
            OperationRisks.LowReversible);

        Assert.Multiple(() =>
        {
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(incomplete), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(notesOnly), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(complete), Is.True);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(wrongAppRisk), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(wrongCreateRisk), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(wrongMemoryRisk), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(wrongMuteRisk), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(wrongVolumeRisk), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(wrongListRisk), Is.False);
            Assert.That(CoreProcessClient.SupportsInteractiveOperations(wrongStatusRisk), Is.False);
        });
    }

    private static ProtocolHello WithRisk(
        ProtocolHello hello,
        string operationName,
        string risk) => hello with
        {
            Capabilities = hello.Capabilities
            .Select(capability => string.Equals(
                capability.Name,
                operationName,
                StringComparison.Ordinal)
                ? capability with { Risk = risk }
                : capability)
            .ToArray(),
        };

    [Test]
    public void ProjectsNoteListAsNaturalTextWithoutRawJson()
    {
        using JsonDocument resultDocument = JsonDocument.Parse(
            "{\"notes\":[{\"title\":\"Compras\"},{\"title\":\"Ideas\"}],\"count\":2,\"scope\":\"active\"}");
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Completed,
            "Encontré 2 notas.",
            true,
            false,
            resultDocument.RootElement.Clone(),
            null);

        OperationResponseProjection projection = OperationResponseProjection.Create(
            response,
            "note.list");

        Assert.That(projection.Message, Is.EqualTo("Encontré 2 notas."));
    }

    [Test]
    public void ProjectsAPartialNotePageWithoutClaimingItIsTheTotal()
    {
        using JsonDocument resultDocument = JsonDocument.Parse(
            "{\"notes\":[{\"title\":\"Compras\"},{\"title\":\"Ideas\"}],\"count\":2,\"totalCount\":9,\"scope\":\"active\",\"limit\":2,\"offset\":0,\"nextOffset\":2}");
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Completed,
            "Mostré 2 de 9 notas.",
            true,
            false,
            resultDocument.RootElement.Clone(),
            null);

        OperationResponseProjection projection = OperationResponseProjection.Create(response, "note.list");

        Assert.That(projection.Message, Is.EqualTo("Mostré 2 de 9 notas."));
    }
}
