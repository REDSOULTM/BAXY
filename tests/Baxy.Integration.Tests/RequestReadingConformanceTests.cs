using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// El shell y la mente leen el mismo saludo. Cuando cada lado tenía su propio
/// lexicón, «Good afternoon» salía español en Python e inglés en C# y el turno
/// se quedaba sin respuesta; este corpus compartido hace visible la divergencia
/// en las dos suites en vez de en una corrida de cien turnos.
/// </summary>
[TestFixture]
public sealed class RequestReadingConformanceTests
{
    [Test]
    public void SharedCorpusPinsTheGreetingReadingOnBothSidesOfTheBoundary()
    {
        string path = Path.Combine(
            FindRepositoryRoot(),
            "tests",
            "data",
            "request_reading_cases.json");
        using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
        JsonElement cases = document.RootElement.GetProperty("cases");
        Assert.That(cases.GetArrayLength(), Is.GreaterThan(50));

        Assert.Multiple(() =>
        {
            foreach (JsonElement entry in cases.EnumerateArray())
            {
                string text = entry.GetProperty("text").GetString()!;
                string greeting = entry.GetProperty("greeting").GetString()!;
                string ask = entry.GetProperty("ask").GetString()!;
                string? remainder = UserMessagePolicy.GreetingRemainder(text);

                switch (greeting)
                {
                    case "none":
                        Assert.That(remainder, Is.Null, text);
                        break;
                    case "only":
                        Assert.That(remainder, Is.Empty, text);
                        break;
                    default:
                        Assert.That(remainder, Is.Not.Null.And.Not.Empty, text);
                        Assert.That(
                            Fold(remainder!),
                            Is.EqualTo(Fold(ask)),
                            text);
                        break;
                }
            }
        });
    }

    [Test]
    public void AGreetingWithARequestIsNotRoutedAsAWelcome()
    {
        Assert.Multiple(() =>
        {
            Assert.That(UserMessagePolicy.IsGreetingRequest("Good afternoon"), Is.True);
            Assert.That(UserMessagePolicy.IsGreetingRequest("Hi again"), Is.True);
            Assert.That(UserMessagePolicy.IsGreetingRequest("hey, close Paint"), Is.False);
            Assert.That(UserMessagePolicy.IsGreetingRequest("Hey Steam"), Is.False);
            Assert.That(
                UserMessagePolicy.IsGreetingRequest("hey, what can you do"),
                Is.False);
            Assert.That(
                UserMessagePolicy.ConversationFallbackIntent("mañana a las 9"),
                Is.EqualTo("unknown"));
            Assert.That(
                UserMessagePolicy.ShouldNotResumePriorObjective("mañana a las 9"),
                Is.False);
            Assert.That(
                UserMessagePolicy.ShouldNotResumePriorObjective("Hi again"),
                Is.True);
        });
    }

    [Test]
    public void TheShellAcceptsTheAnswersTheMindAlreadyValidated()
    {
        // Borradores medidos en artifacts/comprobaciones/C03/panel-opus-4: la
        // mente los aceptaba y el shell los vetaba, y el turno se quedaba sin
        // respuesta con «retry_exhausted».
        Assert.Multiple(() =>
        {
            Assert.That(
                UserMessagePolicy.IsSafeConversationReply(
                    "what will you never do on this PC",
                    "I only do the work of this PC and nothing beyond it."),
                Is.True);
            Assert.That(
                UserMessagePolicy.IsSafeConversationReply(
                    "qué no haces, una frase",
                    "Solo hago lo que este PC es capaz de hacer, nada más."),
                Is.True);
            Assert.That(
                UserMessagePolicy.IsSafeConversationReply(
                    "hola, ¿qué puedes hacer en este PC?",
                    "Hola, puedo abrir y cerrar programas y leer la hora."),
                Is.True);
            // Las garantías se conservan.
            Assert.That(
                UserMessagePolicy.IsSafeConversationReply(
                    "what will you never do on this PC",
                    "I will never do anything unethical or harmful."),
                Is.False);
            Assert.That(
                UserMessagePolicy.IsSafeConversationReply(
                    "qué puedes hacer en este PC",
                    "Hola."),
                Is.False);
        });
    }

    [Test]
    public void AWorldErrandIsOutOfCatalogWhereverItGoes()
    {
        // panel-opus-11/060 contestó «I will send the parcel to Rhea»: la
        // lista de planetas no conocía Rhea, así que el pedido no se reconoció
        // como fuera de catálogo y se prometió un efecto que nadie autorizó.
        Assert.Multiple(() =>
        {
            foreach (string request in new[]
                     {
                         "send a parcel to Rhea",
                         "post a letter to Eris",
                         "manda una carta a Ganímedes",
                         "reserva una mesa en Titán",
                         "book a shuttle to Callisto",
                     })
            {
                Assert.That(
                    UserMessagePolicy.ConversationFallbackIntent(request),
                    Is.EqualTo("out_of_catalog"),
                    request);
            }

            // Lo que el catálogo sí sirve no se convierte en fuera de mundo.
            Assert.That(
                UserMessagePolicy.ConversationFallbackIntent("abre el Bloc de notas"),
                Is.Not.EqualTo("out_of_catalog"));
            Assert.That(
                UserMessagePolicy.ConversationFallbackIntent("qué hora es"),
                Is.Not.EqualTo("out_of_catalog"));
        });
    }

    private static string Fold(string value) =>
        string.Join(
            ' ',
            value
                .Normalize(System.Text.NormalizationForm.FormD)
                .Where(character =>
                    System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character)
                    != System.Globalization.UnicodeCategory.NonSpacingMark)
                .Aggregate(
                    new System.Text.StringBuilder(),
                    static (builder, character) =>
                        builder.Append(char.ToLowerInvariant(character)))
                .ToString()
                .Split(' ', StringSplitOptions.RemoveEmptyEntries))
            .Trim(' ', '.', ',', '!', '?', '¿', '¡');

    /// <summary>
    /// Un seguimiento elíptico deja su tema en el pedido anterior. Si el shell
    /// no lo envía, el compositor sólo ve «¿por qué importa?» y contesta en
    /// abstracto: la lectura del tema vive en la mente, pero el dato con el que
    /// lee tiene que cruzar la frontera.
    /// </summary>
    [Test]
    public void ConversationFactsCarryWhatThePersonAskedBefore()
    {
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Event("conversation"),
            UserMessageEvent.Conversation);
        System.Text.Json.Nodes.JsonObject facts = ModelMessageComposer.CreateFacts(
            draft,
            traceId: "t2",
            previousAnswer: null,
            priorRequests: ["explícame qué es la caché, una frase"]);

        Assert.That(facts["priorRequests"], Is.Not.Null);
        Assert.That(
            facts["priorRequests"]!.AsArray()[0]!.GetValue<string>(),
            Is.EqualTo("explícame qué es la caché, una frase"));
    }

    /// <summary>
    /// Un aviso de estado no es una conversación: no lleva el pedido anterior.
    /// </summary>
    [Test]
    public void StatusFactsDoNotCarryPreviousRequests()
    {
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Status("acting"),
            UserMessageEvent.Status);
        System.Text.Json.Nodes.JsonObject facts = ModelMessageComposer.CreateFacts(
            draft,
            traceId: "t2",
            previousAnswer: null,
            priorRequests: ["explícame qué es la caché, una frase"]);

        Assert.That(facts["priorRequests"], Is.Null);
    }

    /// <summary>
    /// La respuesta correcta a «qué haces en este PC» se rechazaba seis veces
    /// seguidas y el turno moría agotado (limites-18/006): el compositor la
    /// escribía bien y el veto del shell la tiraba.
    /// </summary>
    [Test]
    public void TheCatalogAnswerToACapabilityAskIsNotVetoed()
    {
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Event("conversation"),
            UserMessageEvent.Conversation);
        const string reply =
            "I can open and close apps, move and focus windows, read and set "
            + "the audio, and read the clock and PC state. There are other "
            + "things too.";

        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                reply,
                draft,
                "hi, what do you handle on this PC"),
            Is.Null);
        foreach (string variant in new[]
        {
            "I can open and close apps, move and focus windows, read and set "
                + "the audio, and read the clock and PC state, plus I take "
                + "notes and keep tasks. There are other things too.",
            "I can open and close apps, move and focus windows, read and set "
                + "the audio, and read the clock and PC state, and there are "
                + "other things too.",
            "I can open and close apps, move and focus windows, read and set "
                + "the audio, and keep track of the clock and PC state. There "
                + "are other things too.",
        })
        {
            Assert.That(
                UserMessagePolicy.ModelResponseRejectionReason(
                    variant,
                    draft,
                    "hi, what do you handle on this PC"),
                Is.Null,
                variant);
            Assert.That(
                UserMessagePolicy.ConversationReplyRejectionReason(
                    "hi, what do you handle on this PC",
                    variant,
                    "en"),
                Is.Null,
                variant);
        }
    }

    /// <summary>
    /// Si la mente lee «pregunta por lo que hago o por lo que no hago», el
    /// shell tiene que leer lo mismo: con su tabla más corta, la respuesta
    /// correcta del catálogo se vetaba como catálogo no solicitado. Esta
    /// comprobación hace que la divergencia salga aquí y no en una corrida.
    /// </summary>
    [Test]
    public void BothSidesAgreeOnAnAskAboutWhatTheProductDoes()
    {
        string path = Path.Combine(
            FindRepositoryRoot(),
            "tests",
            "data",
            "request_reading_cases.json");
        using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));

        Assert.Multiple(() =>
        {
            foreach (JsonElement entry in
                document.RootElement.GetProperty("cases").EnumerateArray())
            {
                string text = entry.GetProperty("text").GetString() ?? string.Empty;
                bool mindReads = false;
                foreach (JsonElement intent in
                    entry.GetProperty("intents").EnumerateArray())
                {
                    string name = intent.GetString() ?? string.Empty;
                    if (name is "capability" or "refuse")
                    {
                        mindReads = true;
                    }
                }

                if (mindReads)
                {
                    Assert.That(
                        UserMessagePolicy.IsSelfDescriptionQuestion(text),
                        Is.True,
                        text);
                }
            }
        });
    }

    /// <summary>
    /// Aceptar el encargo con las palabras del encargo es la respuesta, no un
    /// eco: «keep talking without launching anything» se contesta «I will keep
    /// talking without launching anything». El shell lo vetaba seis veces y el
    /// turno moría agotado (limites-22/009).
    /// </summary>
    [Test]
    public void AcceptingTheConstraintInThePersonsOwnWordsIsNotVetoed()
    {
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Event("conversation"),
            UserMessageEvent.Conversation);
        foreach ((string request, string reply) in new[]
        {
            ("keep talking without launching anything",
                "I will keep talking without launching anything."),
            ("keep chatting without opening apps",
                "I will keep chatting without opening any apps."),
            ("sigue charlando sin abrir programas",
                "No abriré programas, seguiré la conversación."),
        })
        {
            Assert.That(
                UserMessagePolicy.ModelResponseRejectionReason(reply, draft, request),
                Is.Null,
                reply);
        }
    }

    /// <summary>
    /// La exención es del pedido, no de la frase: las mismas palabras siguen
    /// siendo encargo copiado cuando la persona no las escribió. Sin este lado
    /// la regla anterior sólo sería una lista más corta.
    /// </summary>
    [Test]
    public void TheSameInstructionWordsAreStillVetoedWhenNobodyAskedForThem()
    {
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Event("conversation"),
            UserMessageEvent.Conversation);
        foreach ((string request, string reply) in new[]
        {
            ("what time is it", "I will keep talking without launching anything."),
            ("what is a router", "A router moves traffic, in one short sentence."),
            ("hello", "Name the pc network in this reply."),
            ("what can you do", "Stay in the conversation and do not introduce yourself."),
        })
        {
            Assert.That(
                UserMessagePolicy.ModelResponseRejectionReason(reply, draft, request),
                Is.EqualTo("internal_code"),
                reply);
        }
    }

    private static string FindRepositoryRoot()
    {
        DirectoryInfo? directory = new(TestContext.CurrentContext.TestDirectory);
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException("No se encontró la raíz versionada de BAXY.");
    }
}
