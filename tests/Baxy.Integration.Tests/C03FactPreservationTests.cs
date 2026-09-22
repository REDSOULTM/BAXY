using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class C03FactPreservationTests
{
    [TestCase("dime hola Lina", "Hola Lina.", true)]
    [TestCase("decime hola José Luis", "Hola José Luis.", true)]
    [TestCase("tell me hello Jordan", "Hello Jordan.", true)]
    [TestCase("dime buenas noches Marisol", "Buenas noches Marisol.", true)]
    [TestCase("Dime qué causa los eclipses.", "Qué causa los eclipses.", false)]
    [TestCase("Dame la definición de gravedad.", "La definición de gravedad.", false)]
    [TestCase("dime hola Lina y explícame qué es la gravedad", "Hola Lina y explícame qué es la gravedad.", false)]
    [TestCase("dime hola Lina", "Listo, ya está.", false)]
    public async Task RequestedGreetingIsNotMistakenForAnInformationRequestEcho(
        string request, string reply, bool accepted)
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(request, reply) is null,
            Is.EqualTo(accepted));
        var draft = new UserMessageDraft(TurnVisibleFacts.Event("conversation"), "conversation", null);
        ModelMessageCompositionOutcome result = await ModelMessageComposer.ComposeAsync(
            draft, request, ModelMessageComposer.CreateFacts(draft),
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(new(reply)),
            cpuFallback: false, allowRecovery: false, CancellationToken.None);
        Assert.That(result.Text is not null, Is.EqualTo(accepted));
    }

    [TestCase("the person's name", "What’s your name again?", true)]
    [TestCase("the person's name", "What is your name?", true)]
    [TestCase("the note's content", "What should I remember?", true)]
    [TestCase(null, "What is your name?", false)]
    [TestCase("", "What is your name?", false)]
    [TestCase("the person's name", "I saved your name.", false)]
    public async Task RequiredInputSurvivesTheShellPublicationBoundary(
        string? missingValue, string reply, bool accepted)
    {
        var draft = new UserMessageDraft(TurnVisibleFacts.Clarification(
            "memory_save_needs_content", new JsonObject { ["missingValue"] = missingValue }),
            "clarification", null);
        ModelMessageCompositionOutcome result = await ModelMessageComposer.ComposeAsync(
            draft, "What can you do? Remember my name.", ModelMessageComposer.CreateFacts(draft),
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(new(reply)),
            cpuFallback: false, allowRecovery: false, CancellationToken.None);
        Assert.That(result.Text, accepted ? Is.EqualTo(reply) : Is.Null);
    }

    [TestCase("Quieres que lo confirmemos juntos?", false)]
    [TestCase("Soy BAXY. Tu nombre es Emmanuel. ¿Quieres que lo confirmemos juntos?", false)]
    [TestCase("Do you want me to explain that distinction?", false)]
    [TestCase("La ventana es un elemento de la interfaz. ¿Quieres que lo explique con un ejemplo?", false)]
    [TestCase("Steam is a game platform. Want me to explain that in more detail?", false)]
    [TestCase("¿Quieres que cierre la ventana?", true)]
    [TestCase("Want me to open Steam?", true)]
    [TestCase("¿Quieres que te muestre el estado del sistema del PC?", true)]
    [TestCase("¿Quieres que muestre el estado de la red?", true)]
    [TestCase("Do you want me to check whether an application is installed?", true)]
    public void ConversationalFollowUpIsNotAnOfferToOperateTheComputer(string reply, bool proposesAction)
    {
        Assert.That(UserMessagePolicy.ProposesUnsolicitedCatalogAction("Explícamelo.", reply),
            Is.EqualTo(proposesAction));
    }

    [Test]
    public void CorrectContextualIdentityCanReachThePersonWithAConversationalFollowUp()
    {
        const string request = "nono, te pregunte quien soy yo, no tu, dime quien eres tu y quien soy yo";
        const string answer = "Yo soy BAXY, tu compañero en el PC. Y tú te llamas Emmanuel, según lo que dijiste antes. ¿Quieres que lo confirmemos juntos? 😎";
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(request, answer, "es",
            "me llamo emmanuel, dime hola emmanuel"), Is.Null);
    }

    // Owner's test 2026-09-21 (turn 205) / ctx-dueno-04: the microphone already in
    // the requested state is a typed failure whose honest finals name the state.
    [TestCase("El micrófono ya no estaba activo, así que no se pudo silenciar.")]
    [TestCase("El micrófono ya estaba silenciado, así que no cambié nada.")]
    [TestCase("No pude silenciar el micrófono porque ya estaba silenciado.")]
    public void MicrophoneAlreadyMutedFailureCanReachThePerson(string reply)
    {
        string step = TurnVisibleFacts.Failure("mission_failed", new JsonObject
        {
            ["stepCount"] = 0,
            ["steps"] = new JsonArray(),
            ["reason"] = new JsonObject
            {
                ["kind"] = "operation",
                ["operation"] = "audio.microphone.mute",
                ["polarity"] = "failure",
                ["verified"] = false,
                ["succeeded"] = false,
                ["error"] = "microphone_already_muted",
            },
        });
        UserMessageDraft draft = UserMessagePolicy.Create(
            step, UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "silencia mi microfono"), Is.Null);
    }

    // ctx-dueno-04 (2026-09-22, «Dime algo»): the observed snippet says «volumen de
    // agua»; reporting it is not an invented volume level.
    [Test]
    public void VolumeWordCarriedByObservedSearchDataCanReachThePerson()
    {
        string facts = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = "web.search",
            ["polarity"] = "success",
            ["verified"] = true,
            ["succeeded"] = true,
            ["observed"] = new JsonObject
            {
                ["version"] = 1,
                ["query"] = "Tsunami",
                ["count"] = 1,
                ["results"] = new JsonArray(new JsonObject
                {
                    ["title"] = "Tsunami - Wikipedia",
                    ["url"] = "https://en.wikipedia.org/wiki/Tsunami",
                    ["snippet"] = "A tsunami is a series of waves caused by the displacement of a large volume of water.",
                }),
            },
        }.ToJsonString();
        UserMessageDraft draft = UserMessagePolicy.Create(facts, UserMessageEvent.Status);
        const string reply = "La curiosidad es sobre Tsunami. Un fragmento de Wikipedia (Tsunami - Wikipedia) dice que es una serie de olas causada por el desplazamiento de un volumen grande de agua.";
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "Dime algo"), Is.Null);
    }

    // MEME2053 «tienes alguna foto?»: the picture's subject is the declared missing field;
    // asking what the picture should show is the clarification, not an out-of-world question.
    [Test]
    public void ImageSubjectQuestionIsNotAnOutOfWorldQuestion()
    {
        string facts = new JsonObject
        {
            ["kind"] = "clarification",
            ["polarity"] = "pending",
            ["cause"] = "ambiguous_request",
            ["missingValue"] = "query",
        }.ToJsonString();
        UserMessageDraft draft = UserMessagePolicy.Create(facts, UserMessageEvent.Clarification);
        IReadOnlyList<string>? missing = UserMessagePolicy.DeclaredMissingFields(draft);
        const string reply = "¿De qué tipo de foto te refieres?";
        Assert.Multiple(() =>
        {
            Assert.That(missing, Is.EqualTo(new[] { "query" }));
            Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
                "tienes alguna foto?", reply, hasRequiredInput: true, missingFields: missing), Is.Null);
            Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
                "tienes alguna foto?", reply, hasRequiredInput: true), Is.EqualTo("out_of_world_question"));
        });
    }

    // PPTX2051: «the opening is not confirmed» states the failure in English.
    [Test]
    public void OpeningNotConfirmedIsAFailureStatement()
    {
        string created = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = "document.presentation.create",
            ["polarity"] = "success",
            ["verified"] = true,
            ["succeeded"] = true,
            ["observed"] = new JsonObject { ["version"] = 1, ["title"] = "Dogs", ["folder"] = "documents", ["name"] = "Dogs.pptx", ["slideCount"] = 5 },
        }.ToJsonString();
        string notOpened = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = "file.open",
            ["polarity"] = "failure",
            ["verified"] = false,
            ["succeeded"] = false,
            ["error"] = "file_open_not_verified",
        }.ToJsonString();
        string facts = MissionNarration.CreateFailureMessage([created], notOpened);
        UserMessageDraft draft = UserMessagePolicy.Create(facts, UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
        const string reply = "Dogs.pptx was created in Documents with 5 slides, but no window or process appeared, so the opening is not confirmed.";
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "make a presentation about dogs with 5 slides"), Is.Null);
    }

    // DOWNLOAD2047: the file just written and the source host are observed data, not codes.
    [Test]
    public void DownloadedFileNameIsObservedVocabulary()
    {
        string facts = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = "web.download",
            ["polarity"] = "success",
            ["verified"] = true,
            ["succeeded"] = true,
            ["observed"] = new JsonObject
            {
                ["version"] = 1,
                ["sourceUrl"] = "https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/250px-Wikipedia-logo-v2.svg.png",
                ["folder"] = "desktop",
                ["name"] = "250px-Wikipedia-logo-v2.svg.png",
                ["bytes"] = 59357,
                ["contentType"] = "image/png",
                ["authority"] = "downloaded_file_size_postread",
            },
        }.ToJsonString();
        UserMessageDraft draft = UserMessagePolicy.Create(facts, UserMessageEvent.Status);
        const string reply = "Descargué la imagen de portada de wikipedia.org y la guardé en el escritorio con el nombre 250px-Wikipedia-logo-v2.svg.png.";
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "descarga la imagen de portada de wikipedia.org y guardala en el escritorio"), Is.Null);
    }

    // Owner's test 2026-09-21 (turn 205): the verified unmute final.
    [TestCase("Tu micrófono está activo de nuevo.")]
    [TestCase("Activé el micrófono; ya no está silenciado.")]
    public void MicrophoneUnmuteSuccessCanReachThePerson(string reply)
    {
        string facts = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = "audio.microphone.mute",
            ["polarity"] = "success",
            ["verified"] = true,
            ["succeeded"] = true,
            ["observed"] = new JsonObject
            {
                ["version"] = 1,
                ["baselineMuted"] = true,
                ["muted"] = false,
                ["authority"] = "windows_core_audio_capture_endpoint_postread",
            },
        }.ToJsonString();
        UserMessageDraft draft = UserMessagePolicy.Create(facts, UserMessageEvent.Status);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "activa mi microfono"), Is.Null);
    }

    [Test]
    public void PriorFilenameRemainsHumanVocabularyInAConversationRecovery()
    {
        const string request = "Why couldn't you read that file?";
        const string reply = "The file \"c03-ausente.txt\" was not found in the sandbox.";
        const string prior = "Lee el archivo \"c03-ausente.txt\" del sandbox.";
        var draft = new UserMessageDraft(TurnVisibleFacts.Event("conversation"), "conversation", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, request), Is.EqualTo("internal_code"));
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, request, prior), Is.Null);
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(request, reply, "en", prior), Is.Null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply + " filesystem.read.text.", draft, request, prior),
            Is.EqualTo("internal_code"));
    }

    [Test]
    public void MissingVolumeLevelQuestionCanReachThePerson()
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
            "Pon el volumen.", "¿A qué nivel quieres que ponga el volumen?", "es", clarification: true), Is.Null);
    }

    [TestCase("¿Quieres que abra Steam?")]
    [TestCase("¿Quieres que vacíe la papelera?")]
    public void ClarificationDoesNotInviteAnUnrequestedFamily(string question)
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
            "Pon el volumen.", question, "es", clarification: true), Is.EqualTo("unsolicited_catalog"));
    }

    [Test]
    public void KnowledgeAnswerCanExplainAnEarlierFailure()
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
            "Why couldn't you read \"c03-invalid-utf8.txt\"?",
            "I couldn't read \"c03-invalid-utf8.txt\" because the file contains invalid UTF-8 characters, which caused the read operation to fail.",
            "en"), Is.Null);
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
            "Read the file.", "I couldn't read the file.", "en"), Is.EqualTo("looks_like_failure"));
    }

    [TestCase("The file contains invalid UTF-8 sequences, which cannot be properly read or processed.")]
    [TestCase("The document could not be read.")]
    [TestCase("The text can't be decoded.")]
    [TestCase("The file couldn't be opened.")]
    public void NegativeModalsReportFailureRegardlessOfSubject(string reply)
    {
        var draft = new UserMessageDraft(TurnVisibleFacts.Failure("invalid_utf8"), "error", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "Read the file."), Is.Null);
    }

    [TestCase("The file can be read.")]
    [TestCase("The document could be read.")]
    public void PositiveAbilityDoesNotExplainARealReadFailure(string reply)
    {
        var draft = new UserMessageDraft(TurnVisibleFacts.Failure("invalid_utf8"), "error", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "Read the file."),
            Is.EqualTo("reversed_result"));
    }

    [TestCase("No se encontró el archivo en el sandbox.")]
    [TestCase("No se encontraron archivos en el sandbox porque la búsqueda no devolvió coincidencias.")]
    [TestCase("No encontré el archivo porque la búsqueda no devolvió ningún resultado.")]
    [TestCase("No se pudo leer el archivo.")]
    public void SpanishNegativeResultsPreserveReadFailure(string reply)
    {
        var draft = new UserMessageDraft(TurnVisibleFacts.Failure("file_search_no_matches"), "error", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "Lee el archivo."), Is.Null);
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason("Lee el archivo.", reply, "es"),
            Is.EqualTo("looks_like_failure"));
    }

    [TestCase("c03-lectura.txt")]
    [TestCase("resumen_final.txt")]
    [TestCase("notas.edicion.md")]
    public void RequestedFileIdentifiersAreNotInternalCodeLeaks(string name)
    {
        string userText = $"Lee el archivo \"{name}\".";
        string reply = $"El contenido del archivo \"{name}\" es: \"El color es turquesa.\"";
        var draft = new UserMessageDraft(
            """{"kind":"operation","polarity":"success","verified":true}""", "status", null);
        Assert.Multiple(() =>
        {
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, userText), Is.Null);
            foreach (string code in new[] { "system.time", "request_failed" })
            {
                Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply + $" {code}.", draft, userText),
                    Is.EqualTo("internal_code"));
            }
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, $"Lee \"prefijo-{name}\"."),
                Is.EqualTo("internal_code"));
        });
    }

    [TestCase("No hay fallos registrados.")]
    [TestCase("No hay ningún fallo registrado.")]
    [TestCase("No hubo fallos en la comprobación.")]
    [TestCase("La comprobación terminó sin fallos.")]
    [TestCase("No se han detectado fallos.")]
    [TestCase("No se encontraron fallos.")]
    [TestCase("No se encontró ningún fallo.")]
    [TestCase("None of the checks failed.")]
    public void NegatedFailuresPreserveSuccessfulObservationPolarity(string reply)
    {
        var draft = new UserMessageDraft(
            """{"kind":"operation","operation":"system.status","polarity":"success","verified":true,"observed":{"failures":[]}}""",
            "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "Revisa la CPU"), Is.Null);
    }

    [TestCase("Hubo un fallo en la lectura.")]
    [TestCase("Se han detectado fallos.")]
    [TestCase("No hay fallos de audio, pero no pude leer la CPU.")]
    [TestCase("No se encontraron fallos de audio, pero no se pudo leer la CPU.")]
    [TestCase("No pude completar la lectura.")]
    [TestCase("The check failed.")]
    [TestCase("Some checks failed.")]
    [TestCase("None of the audio checks failed, but the CPU check failed.")]
    public void AssertedFailuresStillReverseSuccessfulObservations(string reply)
    {
        var draft = new UserMessageDraft(
            """{"kind":"operation","operation":"system.status","polarity":"success","verified":true,"observed":{"failures":[]}}""",
            "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "Revisa la CPU"),
            Is.EqualTo("reversed_result"));
    }

    [TestCase("No hay fallos registrados.")]
    [TestCase("No se han detectado fallos.")]
    [TestCase("None of the checks failed.")]
    public void DenyingFailuresCannotReplaceARealFailure(string reply)
    {
        var draft = new UserMessageDraft(TurnVisibleFacts.Failure("timeout"), "error", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "Revisa la CPU"),
            Is.EqualTo("reversed_result"));
    }

    [TestCase("www.google.com")]
    [TestCase("www.example.com")]
    [TestCase("https://docs.example.org")]
    public void DnsExplanationMayContainAPublicWebHost(string host)
    {
        string reply = $"DNS translates names such as {host} into IP addresses.";
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
            "What does DNS do?", reply, "en"), Is.Null);
    }

    [TestCase("system.time")]
    [TestCase("audio.status")]
    [TestCase("request_failed")]
    [TestCase("situation.greeting")]
    public void AWebHostDoesNotExemptOtherInternalCodes(string code)
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
            "What does DNS do?", $"www.example.com returned {code}.", "en"),
            Is.EqualTo("internal_code"));
    }

    [TestCase("La ventana \"Ventana C03 de prueba\" se cerró.")]
    [TestCase("El archivo «Archivo final» está guardado.")]
    [TestCase("The document 'Document draft' is open.")]
    public void AQuotedTargetIsNotAStutterAtTheBoundaryWithItsObjectNoun(string reply)
    {
        var draft = new UserMessageDraft("""{"kind":"operation","polarity":"success","verified":true}""", "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "confirmar"), Is.Null);
    }

    [TestCase("La ventana ventana se cerró.")]
    [TestCase("The document document is open.")]
    public void ARealStutterWithoutAQuotedTargetStillFails(string reply)
    {
        var draft = new UserMessageDraft("""{"kind":"operation","polarity":"success","verified":true}""", "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "confirmar"), Is.EqualTo("internal_code"));
    }

    [Test]
    public void WindowResultsExposeTheObservedTitleForDisambiguationAndNarration()
    {
        var candidate = new Baxy.Providers.Windows.Windows.WindowCandidate(
            "win_test", 42, "SharedHost", "normal", false, 1, 2, 300, 200,
            "Ventana de prueba");
        var result = Baxy.Core.Operations.WindowControlResultJson.Serialize(new[] { candidate });
        Assert.That(result.GetProperty("windows")[0].GetProperty("title").GetString(),
            Is.EqualTo("Ventana de prueba"));
        Assert.That(result.GetProperty("windows")[0].GetProperty("processName").GetString(),
            Is.EqualTo("SharedHost"));
    }

    [Test]
    public void MissionResultsRetainCatalogReadOnlySemanticsIncludingCancellation()
    {
        string read = """{"kind":"operation","operation":"window.resolve","observed":{"windows":[{"state":"maximized"}]}}""";
        string close = """{"kind":"operation","operation":"app.close","observed":{"windowClosed":true}}""";
        var completed = JsonNode.Parse(MissionNarration.CreateCompletionMessage(
            [read, close], "cierra la ventana de prueba"))!;
        var execution = new PendingMindPlanExecution("cierra la ventana de prueba",
            [new MindPlanStep("close", "app.close", "Cerrar la ventana de prueba.",
                [], "after_dependencies", new JsonObject { ["windowId"] = "unresolved" })]);
        execution.PendingOperation = PreparedOperation.Create("app.close",
            new JsonObject { ["windowId"] = "12345", ["processId"] = 678 });
        execution.CompletedMessages.Add(read);
        var cancelled = JsonNode.Parse(MissionNarration.CreateCancellationMessage(execution))!;
        Assert.Multiple(() =>
        {
            Assert.That((string?)completed["completedRequest"], Is.EqualTo(execution.Objective));
            Assert.That((bool?)JsonNode.Parse((string)completed["steps"]![0]!)!["readOnly"], Is.True);
            Assert.That((bool?)JsonNode.Parse((string)completed["steps"]![1]!)!["readOnly"], Is.False);
            Assert.That((bool?)JsonNode.Parse((string)cancelled["steps"]![0]!)!["readOnly"], Is.True);
            Assert.That((string?)cancelled["cause"], Is.EqualTo("remaining_steps_cancelled"));
            Assert.That((string?)cancelled["cancelledRequest"], Is.EqualTo(execution.Objective));
            Assert.That((string?)cancelled["cancelledAction"]?["operation"], Is.EqualTo("app.close"));
            Assert.That((string?)cancelled["cancelledAction"]?["arguments"]?["windowId"], Is.EqualTo("12345"));
            Assert.That(cancelled["pendingAction"], Is.Null);
        });
    }

    [Test]
    public void RecoveryConfirmationDescribesThePreparedActionRatherThanTheUngroundedPlan()
    {
        var execution = new PendingMindPlanExecution("cierra la ventana de prueba",
            [new MindPlanStep("close", "app.close", "Cerrar la ventana de prueba.",
                [], "after_dependencies", new JsonObject { ["windowId"] = "unresolved" })]);
        execution.PendingOperation = PreparedOperation.Create("app.close",
            new JsonObject { ["windowId"] = "12345", ["processId"] = 678 });

        var facts = JsonNode.Parse(MissionNarration.CreateConfirmationMessage(
            execution, "step_needs_confirmation", TurnVisibleFacts.ConfirmCancel))!;
        var recovery = JsonNode.Parse(MissionNarration.CreateRecoveryPrompt(execution))!;

        Assert.Multiple(() =>
        {
            Assert.That((string?)facts["pendingRequest"], Is.EqualTo(execution.Objective));
            Assert.That((string?)facts["pendingAction"]?["operation"], Is.EqualTo("app.close"));
            Assert.That((string?)facts["pendingAction"]?["arguments"]?["windowId"], Is.EqualTo("12345"));
            Assert.That((int?)facts["pendingAction"]?["arguments"]?["processId"], Is.EqualTo(678));
            Assert.That(JsonNode.DeepEquals(facts["pendingAction"], recovery["pendingAction"]), Is.True);
            Assert.That(facts.ToJsonString(), Does.Not.Contain(execution.PendingOperation.InvocationId));
        });
    }

    [TestCase("Explain encryption, pero en simple",
        "Encryption es como un código que transforma información en algo que solo se puede leer con una clave especial. Es como un mensaje que solo el destinatario puede entender.")]
    [TestCase("What is an SSID?", "An SSID is the network name that identifies a wireless network.")]
    [TestCase("Qué es una carpeta", "La carpeta agrupa archivos para mantenerlos organizados.")]
    [TestCase("responde en spanglish: qué es una copia de seguridad",
        "Una copia de seguridad es un backup de tus datos para recuperarlos si algo se pierde o se daña.")]
    public void ExplanatoryNounsAreNotRequestsForMachineParameters(string request, string reply)
    {
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(request, reply), Is.Null);
        var draft = new UserMessageDraft(
            """{"kind":"conversation","polarity":"success"}""", "conversation", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, request), Is.Null);
    }

    [TestCase("The time is 4:12 PM.", true)]
    [TestCase("The time is 04:12 p. m.", true)]
    [TestCase("Son las 16:12.", true)]
    [TestCase("Son las 16 y 12.", true)]
    [TestCase("Son las 4 y 12 PM.", true)]
    [TestCase("Son las 16 y 13.", false)]
    [TestCase("Son las 4 y 12 AM.", false)]
    [TestCase("Son las 16:12, o son las 16 y 13.", false)]
    [TestCase("Hay 16 y 12 archivos.", false)]
    [TestCase("The time is 4:12 AM.", false)]
    [TestCase("The time is 4:12.", false)]
    [TestCase("The time is 16:12 AM.", false)]
    [TestCase("The time is 16:12, or 4:12 AM.", false)]
    public void ClockEquivalencePreservesTheActualHalfOfTheDay(string reply, bool expected)
    {
        var draft = new UserMessageDraft(
            """{"kind":"status","polarity":"success","operation":"system.time","observed":{"utc":"2026-09-06T20:12:00Z","localUtcOffsetMinutes":-240}}""",
            "status", null);
        Assert.That(UserMessagePolicy.AcceptModelAuthoredResponse(reply, draft) is not null,
            Is.EqualTo(expected));
    }

    [Test]
    public async Task AFollowupCanNameTheUsersTopicWithoutExemptingOtherInternalTerms()
    {
        var draft = new UserMessageDraft("""{"kind":"conversation","polarity":"success"}""",
            "conversation", null);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft,
            priorRequests: ["explícame qué es un router"]);
        ModelMessageCompositionOutcome result = await ModelMessageComposer.ComposeAsync(draft,
            "¿para qué sirve?", facts,
            static (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(
                new("El router permite comunicar tu red con otras redes.")),
            cpuFallback: false, allowRecovery: false, CancellationToken.None);
        Assert.That(result.Text, Is.EqualTo("El router permite comunicar tu red con otras redes."));
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(
            "¿para qué sirve?", "El planner selecciona una tool.", "es",
            priorUserText: "explícame qué es un router"), Is.Not.Null);
    }
}
