using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class Goal06VisibleVoiceTests
{
    [Test]
    public void NarrationEmitsStructuredFactsNotSpanishProse()
    {
        string success = ProductOperationNarrator.Instance.Narrate(
            "app.open",
            OperationOutcome.Success());
        string failure = ProductOperationNarrator.Instance.Narrate(
            "app.open",
            OperationOutcome.Failure("app_not_found"));

        Assert.Multiple(() =>
        {
            Assert.That(UserMessagePolicy.IsStructuredFacts(success), Is.True);
            Assert.That(UserMessagePolicy.IsStructuredFacts(failure), Is.True);
            Assert.That(success, Does.Contain("\"polarity\":\"success\""));
            Assert.That(failure, Does.Contain("\"polarity\":\"failure\""));
            Assert.That(success, Does.Not.Contain("Listo"));
            Assert.That(failure, Does.Not.Contain("No pude"));
        });
    }

    [Test]
    public async Task ComposerPublishesInjectedProseForVerifiedSuccessAndUglyPaths()
    {
        var cases = new (string User, string Intent, string Source, string Authored)[]
        {
            (
                "abre Spotify",
                "status",
                OperationVisibleFacts.FromOutcome("app.open", OperationOutcome.Success()),
                "Listo, Spotify está abierto y sonando."),
            (
                "abre Spotify",
                "error",
                TurnVisibleFacts.Failure("provider_down"),
                "No pude: Spotify no responde."),
            (
                "haz algo raro",
                "error",
                TurnVisibleFacts.Failure("out_of_catalog"),
                "No pude: eso no lo hago."),
            (
                "hello",
                "welcome",
                TurnVisibleFacts.Welcome(),
                "Hi."),
        };

        foreach ((string user, string intent, string source, string authored) in cases)
        {
            UserMessageEvent messageEvent = intent switch
            {
                "welcome" => UserMessageEvent.Welcome,
                "error" => UserMessageEvent.Error(UserMessageDiagnosticCodes.LocalService),
                _ => UserMessageEvent.Status,
            };
            UserMessageDraft draft = UserMessagePolicy.Create(source, messageEvent);
            JsonObject facts = ModelMessageComposer.CreateFacts(draft);
            ModelMessageCompositionOutcome outcome = await ModelMessageComposer.ComposeAsync(
                draft,
                user,
                facts,
                (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(
                    new MindComposedMessage(authored)),
                cpuFallback: false,
                allowRecovery: true,
                CancellationToken.None);

            Assert.That(outcome.Text, Is.EqualTo(authored), user);
            Assert.That(outcome.Text, Is.Not.EqualTo(source), user);
            Assert.That(
                outcome.Text,
                Does.Not.Contain("un momento").IgnoreCase,
                user);
            Assert.That(
                UserMessagePolicy.IsStructuredFacts(outcome.Text!),
                Is.False,
                user);
        }
    }

    [Test]
    public async Task VerifiedSystemTimeUsesUtcAndOffsetNotFabricatedLocalTime()
    {
        const string utc = "2026-09-03T06:57:52.1829160+00:00";
        const int offsetMinutes = -240;
        string source = OperationVisibleFacts.FromOutcome(
            "system.time",
            OperationOutcome.Success(
                JsonDocument.Parse(
                    """{"version":1,"utc":"2026-09-03T06:57:52.1829160+00:00","localUtcOffsetMinutes":-240}""")
                    .RootElement.Clone()));
        UserMessageDraft draft = UserMessagePolicy.Create(source, UserMessageEvent.Status);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        Assert.That(source, Does.Contain("\"utc\""));
        Assert.That(source, Does.Contain("localUtcOffsetMinutes"));
        Assert.That(source, Does.Not.Contain("localTime"));
        Assert.That(UserMessagePolicy.TryDerivedLocalClock(source, out string clock), Is.True);
        Assert.That(clock, Is.EqualTo("2:57"));

        ModelMessageCompositionOutcome accepted = await ModelMessageComposer.ComposeAsync(
            draft,
            "¿Qué hora es?",
            facts,
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(
                new MindComposedMessage("Listo, son las 2:57.")),
            cpuFallback: false,
            allowRecovery: true,
            CancellationToken.None);
        Assert.That(accepted.Text, Is.EqualTo("Listo, son las 2:57."));
        Assert.That(accepted.Failure, Is.Null);

        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: son las 2:57.",
                draft),
            Is.EqualTo("reversed_result"));
        ModelMessageCompositionOutcome inverted = await ModelMessageComposer.ComposeAsync(
            draft,
            "¿Qué hora es?",
            facts,
            (_, _, retryFacts, _, _) =>
            {
                Assert.That((string?)retryFacts["situation"], Is.EqualTo(source));
                return Task.FromResult<MindComposedMessage?>(
                    new MindComposedMessage("No pude: son las 2:57."));
            },
            cpuFallback: false,
            allowRecovery: true,
            CancellationToken.None);
        Assert.That(inverted.Text, Is.Null);
        Assert.That(inverted.Failure, Does.Contain("reversed_result"));
        Assert.That(inverted.UsedRecovery, Is.True);
        Assert.That(source, Does.Contain(utc));
        Assert.That(
            source,
            Does.Contain($"\"localUtcOffsetMinutes\":{offsetMinutes}"));
        UserMessageDraft audioOnly = UserMessagePolicy.Create(
            OperationVisibleFacts.FromOutcome(
                "audio.volume",
                OperationOutcome.Success(
                    JsonDocument.Parse("""{"level":100}""").RootElement.Clone())),
            UserMessageEvent.Status);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "La hora es 14:30 y el audio está activo con volumen al 100%.",
                audioOnly),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Can you read this computer's clock?",
                "Can you read this computer's clock?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Hola otra vez",
                "La hora actual es las 14:30."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "llama a un taxi en Marte",
                "Listo, el taxi fue llamado a las 21:45."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Dime qué sabes hacer",
                "Quieres que vme la Papelera de reciclaje?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "One sentence: define UTC.",
                "want me to system.time | read the current date"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "what do you do on this machine?",
                "¿Quieres que te comprobo si una aplicación está instalada?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "El mensaje es correcto es: Listo, REDPC\\usuario.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Welcome(),
                    UserMessageEvent.Welcome)),
            Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: la respuesta es unsafe.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Failure("model_invalid"),
                    UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted))),
            Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "llama a un taxi en Marte",
                "No puedo llamarar a un taxi en Marte."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "traduce 'good night' al español, nada más",
                "Buenos nochesos."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply("Hola", "Hola, ¿en qué puedo ayudarte?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Hola compañero",
                "¿Quieres que lea metadatos de una rutina exacta sin ejecutarla?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "cierra aquello",
                "¿Quieres que cierre la ventana?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ProposesUnsolicitedCatalogAction(
                "Have I got internet?",
                "Want me to check the active window?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ProposesUnsolicitedCatalogAction(
                "can you help me with this PC, porfa?",
                "¿Quieres que te muestre el estado del sistema del PC?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "online?",
                "¿Quieres que busque algo en la web?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Have I got internet?",
                "Want me to check if Wi-Fi is connected and get the opaque identity of the observed profile?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "¿hay red?",
                "¿Quieres que muestre el estado de la red?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Please, the time",
                "What time is it?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "what do you do on this machine?",
                "I am a language model designed to assist."),
            Is.False);
        Assert.That(
            UserMessagePolicy.StripLeadingPromptLabels("# ¿En qué puedo ayudarte hoy?"),
            Is.EqualTo("¿En qué puedo ayudarte hoy?"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "¿Quieres que te muestre el estado del sistema del PC?",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Welcome(),
                    UserMessageEvent.Welcome)),
            Is.EqualTo("unsolicited_catalog"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Hola, ¿en qué puedo ayudarte?",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Welcome(),
                    UserMessageEvent.Welcome)),
            Is.Null);
        Assert.That(
            UserMessagePolicy.ProposesUnsolicitedCatalogAction(
                "ábreme eso",
                "¿Quieres que mides el estado del sistema?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ProposesUnsolicitedCatalogAction(
                "cierra aquello",
                "¿Qué quieres que cierra?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "reserve a rocket to the moon",
                "What is the private directory path for restoring the latest ZIP backup?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "tú eres un él, no?",
                "El mensaje es: \"Listo, REDPC\\usuario\"."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply("¿sigues ahí?", ":"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "saluda a Saturno",
                "¿cuál es el nombre de la aplicación que se está utilizando para saludar a Saturno?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "what can you do eyes-free?",
                "I can interpret references following the established rules."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "El mensaje es: \"Listo, REDPC\\usuario\".",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Welcome(),
                    UserMessageEvent.Welcome)),
            Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "reserve a rocket to the moon",
                "what is the app id for the moon rocket reservation?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "ábreme eso",
                "¿cuál es la carpeta que deseas abrir?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply("¿sigues ahí?", "S"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "if you didn't confirm it, say that",
                "¿Qué hora te gustaría que fuera?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "ask Saturn for tea",
                "Can you ask Saturn for tea?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply("say hi to Saturn", "Hi, Saturn."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Have I got internet?",
                "No, no tienes internet."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: la respuesta no es útil.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Welcome(),
                    UserMessageEvent.Welcome)),
            Is.EqualTo("reversed_result"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("Hola otra vez"),
            Is.EqualTo("welcome"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("Who are you, in one line?"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent(
                "Explícame qué es un huso horario en una frase."),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("What can you do here"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("Hola, ¿qué puedes hacer?"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.IsGreetingRequest("Hola, ¿qué puedes hacer?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Hola, ¿qué puedes hacer?",
                "Buenos días"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Hola, ¿qué puedes hacer?",
                "Puedo abrir programas y decir la hora en este PC."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Explícame con calma qué puedes hacer en este PC y qué no haces, sin abrir nada.",
                "No tengo acceso a ningún dato adicional; solo sabía que debía responder en español con una frase."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("What will you refuse to do"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.IsCapabilityQuestion("What will you refuse to do"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I don't do that."),
            Is.True);
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent(
                "traduce 'hello' al español, nada más"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("just say hi"),
            Is.EqualTo("welcome"));
        Assert.That(UserMessagePolicy.IsGreetingRequest("Hey"), Is.True);
        Assert.That(UserMessagePolicy.IsGreetingRequest("just say hi"), Is.True);
        Assert.That(UserMessagePolicy.IsGreetingRequest("Hi there"), Is.True);
        // El idioma lo decide la mente y viaja con la respuesta; el shell no
        // lo vuelve a leer. Con «en» declarado, un saludo español se rechaza.
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Hi there",
                "Buenos días, compa.",
                "en"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Hi there",
                "Hi there",
                "en"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply("Hi there", "Hi there"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Buenos días, compa",
                "Buenos días, compa."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Good afternoon",
                "Good afternoon."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsContinueConstraintRequest(
                "keep going without opening apps"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "just say hi",
                "I cannot proceed with this request due to a failure in request analysis."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply("just say hi", "Hi"),
            Is.True);
        Assert.That(UserMessagePolicy.IsGreetingRequest("Hola, buenas"), Is.True);
        Assert.That(UserMessagePolicy.IsGreetingRequest("solo un hola"), Is.True);
        Assert.That(UserMessagePolicy.IsGreetingRequest("un saludo corto"), Is.True);
        Assert.That(UserMessagePolicy.IsGreetingRequest("good afternoon"), Is.True);
        Assert.That(
            UserMessagePolicy.IsSelfDescriptionQuestion("qué no haces, una frase"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSelfDescriptionQuestion(
                "qué no haces en este PC, sin abrir nada"),
            Is.True);
        Assert.That(UserMessagePolicy.IsGreetingRequest("abre Spotify"), Is.False);
        Assert.That(
            UserMessagePolicy.ShouldComposeAsConversationNotError("Hey"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ShouldComposeAsConversationNotError("just say hi"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ShouldComposeAsConversationNotError(
                "qué puedes hacer en este equipo"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ShouldComposeAsConversationNotError("abre Spotify"),
            Is.False);
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("cierra aquello"),
            Is.EqualTo("clarification"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("close that"),
            Is.EqualTo("clarification"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "close that",
                "I cannot complete that request."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "close that",
                "Which window or document should I close?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("ábreme eso"),
            Is.EqualTo("clarification"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("fabrica una hora"),
            Is.EqualTo("out_of_catalog"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("reserve a rocket to the moon"),
            Is.EqualTo("out_of_catalog"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("compra bitcoins ahora"),
            Is.EqualTo("out_of_catalog"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "compra bitcoins ahora",
                "¿cuál es el ID de confirmación y el precio esperado en céntimos para la compra de bitcoins?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Hola, ¿qué puedes hacer?",
                "No pude: no pude usar esa respuesta."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Explícame qué es un huso horario en una frase.",
                "Un huso horarioio es la diferencia que divide el mundo."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "hazlo ya",
                "¿a qué host enviar el eco ICMP?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "En una frase, qué es un huso horario",
                "¿Qué significa exactamente \"huso horario\" en este contexto?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("mail a postcard to Io"),
            Is.EqualTo("out_of_catalog"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("book a table on Europa"),
            Is.EqualTo("out_of_catalog"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("llama un taxi a Plutón"),
            Is.EqualTo("out_of_catalog"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Listo.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Status("acting"),
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "The volume was at level 3.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Welcome(),
                    UserMessageEvent.Welcome)),
            Is.Null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "The volume was at level 3.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Status("acting"),
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        const string clockFacts =
            """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"observed":{"utc":"2026-09-04T18:29:00+00:00","localUtcOffsetMinutes":-240}}""";
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "The app is open, and the time is 14:29.",
                UserMessagePolicy.Create(clockFacts, UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "reserve a cabin on Ganymede",
                "I cannot reserving a cabin on Ganymede."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "envía un paquete a Calisto",
                "¿Cuál es el nombre del destinatario del paquete?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("envía un paquete a Calisto"),
            Is.EqualTo("out_of_catalog"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent(
                "En una frase, qué es un huso horario"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "¿Qué significa exactamente \"UTC\" en este contexto?",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Clarification("ambiguous_request"),
                    UserMessageEvent.Clarification)),
            Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Listo, usuario.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Status("acting"),
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "hazlo",
                "No pude: la solicitud es unclear."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ShouldNotResumePriorObjective("cierra aquello"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ShouldNotResumePriorObjective("Hi again"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ShouldNotResumePriorObjective(
                "traduce 'hello' al español, nada más"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse?",
                "Will you refuse to disconnect the Wi-Fi?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "book a room on Triton",
                "No pude: el libro ya está reservado."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsIdentityQuestion("Who are you?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Why do we use time zones?",
                "The time zone is UTC-7."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "cierra aquello",
                "¿Quieres que minimice la ventana?"),
            Is.False);
        Assert.That(
            NaturalSystemStatusRequestParser.IsCurrentTimeRequest("dime la hora, porfa"),
            Is.True);
        Assert.That(
            NaturalSystemStatusRequestParser.IsCurrentTimeRequest("thanks — what time is it"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Listo, usuario.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Welcome(),
                    UserMessageEvent.Welcome)),
            Is.EqualTo("reversed_result"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "compra bitcoins ahora",
                "¿Estás refiriéndote a la compra de bitcoins en una plataforma específica?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: no pude usar esa respuesta.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Welcome(),
                    UserMessageEvent.Welcome)),
            Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.IsConnectivityStatusRequest("Have I got internet?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsConnectivityStatusRequest("¿hay red?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsConnectivityStatusRequest("are you connected?"),
            Is.True);
        Assert.That(
            NaturalSystemStatusRequestParser.IsClockAndAudioStatusRequest(
                "Dime la hora y el estado del audio."),
            Is.True);
        Assert.That(
            NaturalSystemStatusRequestParser.IsClockAndAudioStatusRequest("clock please"),
            Is.False);
        Assert.That(
            NaturalSystemStatusRequestParser.IsClockAndAudioStatusRequest(
                "Dime la hora y el volumen."),
            Is.True);
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent(
                "Dime la hora y el estado del audio."),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Dime la hora y el estado del audio.",
                "La hora y el estado del audio."),
            Is.False);
        string clockAudioMission = MissionNarration.CreateCompletionMessage(
        [
            """{"kind":"operation","operation":"system.time","polarity":"success","observed":{"utc":"2026-09-05T09:39:00+00:00","localUtcOffsetMinutes":-240}}""",
            """{"kind":"operation","operation":"audio.status","polarity":"success","observed":{"muted":false,"level":40}}""",
        ]);
        Assert.That(clockAudioMission, Does.Contain("\"muted\""));
        Assert.That(clockAudioMission, Does.Contain("\"level\":40"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "05:39",
                UserMessagePolicy.Create(clockAudioMission, UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Son las 05:39 y el volumen 40 no está silenciado.",
                UserMessagePolicy.Create(clockAudioMission, UserMessageEvent.Status)),
            Is.Null);
        string liveClockAudioMission = MissionNarration.CreateCompletionMessage(
        [
            """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"succeeded":true,"observed":{"utc":"2026-09-05T10:01:00+00:00","localUtcOffsetMinutes":-240}}""",
            """{"kind":"operation","operation":"audio.status","polarity":"success","verified":true,"succeeded":true,"observed":{"operation":"audio.status","targetId":"default-output","state":{"volumePercent":40,"muted":false}}}""",
        ]);
        Assert.That(liveClockAudioMission, Does.Contain("\"muted\""));
        Assert.That(liveClockAudioMission, Does.Contain("\"level\":40"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "06:01",
                UserMessagePolicy.Create(
                    liveClockAudioMission, UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Son las 06:01 y el volumen 40 no está silenciado.",
                UserMessagePolicy.Create(
                    liveClockAudioMission, UserMessageEvent.Status)),
            Is.Null);
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("are you connected?"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply("are you connected?", "Hello."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "are you connected?",
                "I am not connected."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply("are you connected?", "Hay red."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "are you connected?",
                "I am online."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "are you connected?",
                "Name the PC network, not yourself."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "are you connected?",
                "Please specify the PC network name."),
            Is.False);
        Assert.That(
            NaturalSystemStatusRequestParser.IsCurrentTimeRequest("clock please"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("clock please"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "keep going without opening apps",
                "Continue in one short sentence without opening apps."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsConnectivityStatusRequest("How is the neural net?"),
            Is.False);
        Assert.That(TurnVisibleFacts.Status("acting"), Does.Not.Contain("Sigo con"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Listo, Spotify está abierto.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Failure("out_of_catalog"),
                    UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted))),
            Is.EqualTo("reversed_result"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "En una frase, qué es un huso horario",
                "Hola, BAXY."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What are you able to do?",
                "I'm ready."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do?",
                "I will refuse to do anything that that, as it is not within my capabilities."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "cierra aquello",
                "¿Cuál es el objeto que te pide cierra?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "what do you do on this machine?",
                "I do not know what the user is referring to with \"this machine\"."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "define time zone in one sentence",
                "The time zone is Central European Time (CET)."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "One sentence: define UTC.",
                "UTC is the time standard other zones offset from."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsIdentityQuestion("introduce yourself briefly"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsCapabilityQuestion(
                "En qué me puedes echar una mano en este PC"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSelfDescriptionQuestion(
                "Explícame con calma qué puedes hacer en este PC y qué no haces, sin abrir nada."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Explícame con calma qué puedes hacer en este PC y qué no haces, sin abrir nada.",
                "En este PC abro programas, leo la hora y el audio. No abro nada ahora."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSelfDescriptionQuestion("Hola, ¿qué puedes hacer?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "what is a time zone, one line",
                "What is a time zone?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "cierra aquello",
                "Cierra por nombre de proceso?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What can you do here",
                "What is the specific task you need clarification on?"),
            Is.False);
        Assert.That(
            NaturalSystemStatusRequestParser.IsCurrentTimeRequest("la hora, otra vez"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("don't launch Steam"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.IsNegativeConstraintRequest("don't launch Steam"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsNegativeConstraintRequest("no abras el bloc de notas"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("keep going without apps"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent(
                "keep going without opening apps"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("don't launch Notepad"),
            Is.EqualTo("conversation"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "keep going without apps",
                "Eso no lo hago."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "keep going without opening apps",
                "I'll keep going without opening apps."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "traduce 'good morning' al español, nada más",
                "Buenos días."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "traduce 'good night' al español, nada más",
                "Buenas noches."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "traduce 'good morning' al español, nada más",
                "Hola, ¿en qué puedo ayudarte hoy?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "quién eres",
                "Soy By, un compañero que vive en el PC."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "descríbete en una frase",
                "Hola, el borrador anterior no sirve."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "De qué te ocupas en el PC",
                "Me ocupo de ayudar a los usuarios con sus preguntas."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude entender la solicitud.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Clarification("ambiguous_request"),
                    UserMessageEvent.Clarification)),
            Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Hecho ya ocurrido a las 15:19.",
                UserMessagePolicy.Create(
                    """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"observed":{"utc":"2026-09-04T19:19:00+00:00","localUtcOffsetMinutes":-240}}""",
                    UserMessageEvent.Status)),
            Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Who are you",
                "¿Quién te pregunta?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "online?",
                "Listo, 24 interfaces conectadas, 14 de ellas son ethernet."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Listo, el reloj de la sala marca 16:23.",
                UserMessagePolicy.Create(
                    """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"observed":{"utc":"2026-09-04T20:23:00+00:00","localUtcOffsetMinutes":-240}}""",
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "I've seen you at 03:46 and am here to help.",
                UserMessagePolicy.Create(
                    """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"observed":{"utc":"2026-09-05T07:46:00+00:00","localUtcOffsetMinutes":-240}}""",
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "I see the clock is 04:13 and I'm BAXY living on the PC.",
                UserMessagePolicy.Create(
                    """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"observed":{"utc":"2026-09-05T08:13:00+00:00","localUtcOffsetMinutes":-240}}""",
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "traduce 'hello' al español, nada más",
                "Hi."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "what is a time zone, one line",
                "I cannot provide a one-line explanation of what a time zone is."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "no abras Steam",
                "¿Qué tipo de información necesitas exactamente?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "envía un paquete a Calisto",
                "No puedo enviaritar el paquete a Calisto."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Por qué hay zonas horarias",
                "</think> Las zonas horarias existen por la rotación."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "ábreme eso",
                "¿Qué es UTC en una sola línea?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "continue without opening apps",
                "I cannot continue without opening apps."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "traduce 'hello' al español, nada más",
                "Hi, I'm BAXY."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "why do time zones exist",
                "Hi, I'm BAXY."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "define huso horario, una frase",
                "Huso horario definido, una frase."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "define huso horario, una frase",
                "Configuro el huso horario de forma centralizada."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "define huso horario, una frase",
                "Un huso horario es una región que comparte la misma hora civil."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "define UTC in one sentence",
                "I set the time zone to UTC."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "define UTC in one sentence",
                "UTC is the time standard other zones offset from."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "introduce yourself",
                "My name is Qwen, and I am here to help."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "quién eres tú",
                "Soyo."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "The app \"BAXY\" is open and the time is at level 17:03.",
                UserMessagePolicy.Create(
                    """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"observed":{"utc":"2026-09-04T21:03:00+00:00","localUtcOffsetMinutes":-240}}""",
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Listo, el mensaje fue enviado a las 16:58.",
                UserMessagePolicy.Create(
                    """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"observed":{"utc":"2026-09-04T20:58:00+00:00","localUtcOffsetMinutes":-240}}""",
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What can you do here",
                "Hello, I'm BAXY, your companion on the PC."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "why do time zones exist",
                "Hello, I'm here."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "BAXY is at 17:17.",
                UserMessagePolicy.Create(
                    """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"observed":{"utc":"2026-09-04T21:17:00+00:00","localUtcOffsetMinutes":-240}}""",
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "ask Saturn for tea",
                "No puedo pedir a Saturn teá."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I will refuse to engage in any activity that is illegal, unethical, or harmful."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "qué sabes hacer",
                "Sé responder preguntas sobre referencias semánticas en conversaciones e interpreto lo que quería decir el asistente."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Who are you",
                "No pude: la solicitud no estaba clara."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "clock now",
                "No pude: la solicitud no está clara."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I'm happy to help—just let me know what you need."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "no abras Steam",
                "No pude: la razón es que el borrador no cumple con los requisitos especificados."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "define UTC in one sentence",
                "Defino la zona horaria UTC en una frase."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: la solicitud no estaba clara.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Failure("out_of_catalog"),
                    UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted))),
            Is.EqualTo("internal_code"));
    }

    [Test]
    public void Cien29HoleClassesStayRejectedAndFaithfulAlternativesPass()
    {
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "no abras Steam",
                "No puedo abrir Steam."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "don't open Steam",
                "I cannot open Steam."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "no abras Steam",
                "No abro Steam."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "don't open Steam",
                "I don't do that."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "don't open Steam",
                "I will not open Steam."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "fabricate a clock time",
                "I cannot fabric a clock time."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "¿Tengo internet?",
                "Sí, tengo internet."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Have I got internet?",
                "I have internet."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "¿hay red?",
                "Hay red."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "qué puedes hacer en este equipo",
                "Soy un compañero que vive en el PC."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What can you do here",
                "I live on this PC and help with what you ask."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Who are you",
                "I am a companion that lives on the PC."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "qué puedes hacer en este equipo",
                "Soy BAXY, un compañero que vive en el PC."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "qué puedes hacer en este equipo",
                "Puedo ayudarte a gestionar tareas en este equipo."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "qué puedes hacer en este equipo",
                "¿Qué tipo de ayuda necesitas en el equipo?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "why do time zones exist",
                "It is EST."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "clock now",
                "No pude: la solicitud no está clara."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Who are you",
                "I'm happy to help—just let me know what you need."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Listo, tengo internet.",
                UserMessagePolicy.Create(
                    """{"kind":"operation","operation":"network.status","polarity":"success","verified":true}""",
                    UserMessageEvent.Status)),
            Is.EqualTo("wrong_actor"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: la solicitud no está clara.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Welcome(),
                    UserMessageEvent.Welcome)),
            Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.IsSelfDescriptionQuestion("qué puedes hacer en este equipo"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSelfDescriptionQuestion("what is UTC, one line"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I will refuse to do anything that violates safety policies, promotes harm, or shares private information."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I will not perform any action that violates ethical guidelines or legal requirements."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I don't do that."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I cannot refuse to do what was asked."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "The PC has a maximum RAM capacity of 64 GB."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I understand the situation and will respond in English as requested."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I understand the task and will respond in English as requested."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I am BAXY and I am present on the PC."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I am BAXY, and I see the situation is successful."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I have seen the previous draft and will proceed with the new instruction based on the current facts."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "The effect is closed."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I will not do harmful acts."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I will not do harmful things."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I will not steal."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "What will you refuse to do",
                "I will not book a room on Deimos."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "ask Saturn for tea",
                "I don't do that."),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "qué rechazas, una frase",
                "No puedo ayudar porque la solicitud no es clara."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "ask Jupiter for tea",
                "No puedo ayudar porque la solicitud es vaga."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "cierra aquello",
                "He cerrado el proceso actual."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "manda esto a Marte",
                "User wants to send a message to Mars."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "The PC is online and the current local time is 19:30.",
                UserMessagePolicy.Create(
                    """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"observed":{"utc":"2026-09-04T23:30:00+00:00","localUtcOffsetMinutes":-240}}""",
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "book a room on Deimos",
                "Listo, el cuarto de noche está reservado en Deimos hasta el lunes por la mañana."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "traduce 'hello' al español, nada más",
                "I see you're here and I'm ready to help."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "traduce 'hello' al español, nada más",
                "Hola"),
            Is.True);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Por qué hay zonas horarias",
                "No hay zonas horarias porque el sistema utiliza la hora local."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "qué rechazas, una frase",
                "No rechazo nada; soy BAXY y vivo en el PC."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "fabricate a clock time",
                "Hello."),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "I couldn't determine the current time as it varies depending on your local settings and system clock.",
                UserMessagePolicy.Create(
                    """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"observed":{"utc":"2026-09-05T00:07:00+00:00","localUtcOffsetMinutes":-240}}""",
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Hola, buenas",
                "La causa es que no puedo compilar porque el proceso no está disponible."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "book a room on Deimos",
                "No puedo hacer eso porque está fuera de lo que soy capaz de hacer. (Esta frase está en español como se requiere.)"),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "envía flores a Europa",
                "No puedo enviar flores a Europa porque el request no está claro."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "open that",
                "¿Quieres que abra esa carpeta y mostrar la ventana de Explorer?"),
            Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "BAXY está en el PC, el tiempo local es 20:29, y el documento tiene el título de nota.",
                UserMessagePolicy.Create(
                    """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"observed":{"utc":"2026-09-05T00:29:00+00:00","localUtcOffsetMinutes":-240}}""",
                    UserMessageEvent.Status)),
            Is.EqualTo("missing_literal_fact"));
    }

    [Test]
    public async Task WelcomeComposeRejectsCapabilityWithoutBaxy()
    {
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Welcome(),
            UserMessageEvent.Welcome);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        ModelMessageCompositionOutcome outcome = await ModelMessageComposer.ComposeAsync(
            draft,
            "Who are you",
            facts,
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(
                new MindComposedMessage("I am a companion that lives on the PC.")),
            cpuFallback: false,
            allowRecovery: false,
            CancellationToken.None);
        Assert.That(outcome.Text, Is.Null);
        Assert.That(outcome.Failure, Is.Not.Null);

        ModelMessageCompositionOutcome named = await ModelMessageComposer.ComposeAsync(
            draft,
            "qué puedes hacer",
            facts,
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(
                new MindComposedMessage("Soy un compañero que vive en el PC.")),
            cpuFallback: false,
            allowRecovery: false,
            CancellationToken.None);
        Assert.That(named.Text, Is.EqualTo("Soy un compañero que vive en el PC."));
    }

    [Test]
    public void ProgressStagesCarryNoVisibleProse()
    {
        foreach (string stage in FieldBridgeContract.ProgressStages)
        {
            Assert.That(FieldBridgeContract.Create(stage).Label, Is.Null, stage);
        }
    }

    [Test]
    public void PolicyRejectsInternalCodesAndSuccessOpenersOnFailure()
    {
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Failure("timeout"),
            UserMessageEvent.Error(UserMessageDiagnosticCodes.Timeout));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: provider_down",
                draft),
            Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Listo, Chrome no respondió.",
                draft),
            Is.EqualTo("reversed_result"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: se agotó el tiempo.",
                draft),
            Is.Null);
    }

    [Test]
    public void OutOfCatalogHonestRefuseIsNotAReversedResult()
    {
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Failure("out_of_catalog"),
            UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason("I don't do that.", draft),
            Is.Null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason("eso no lo hago.", draft),
            Is.Null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: eso no lo hago.",
                draft),
            Is.Null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Listo, Steam está abierto.",
                draft),
            Is.EqualTo("reversed_result"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Listo, Chrome no respondió.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Failure("timeout"),
                    UserMessageEvent.Error(UserMessageDiagnosticCodes.Timeout))),
            Is.EqualTo("reversed_result"));
    }

    [Test]
    public async Task OutOfCatalogRecoveryPublishesHonestRefuse()
    {
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Failure("out_of_catalog"),
            UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        int calls = 0;
        ModelMessageCompositionOutcome recovered = await ModelMessageComposer.ComposeAsync(
            draft,
            "book a table on Callisto",
            facts,
            (_, _, _, _, _) =>
            {
                calls++;
                return Task.FromResult<MindComposedMessage?>(
                    new MindComposedMessage(
                        calls == 1 ? "Listo, Steam está abierto." : "I don't do that."));
            },
            cpuFallback: false,
            allowRecovery: true,
            CancellationToken.None);
        Assert.That(recovered.Text, Is.EqualTo("I don't do that."));
        Assert.That(recovered.UsedRecovery, Is.True);
        Assert.That(recovered.Failure, Does.Contain("reversed_result"));

        ModelMessageCompositionOutcome firstTry = await ModelMessageComposer.ComposeAsync(
            draft,
            "book a table on Callisto",
            facts,
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(
                new MindComposedMessage("I don't do that.")),
            cpuFallback: false,
            allowRecovery: true,
            CancellationToken.None);
        Assert.That(firstTry.Text, Is.EqualTo("I don't do that."));
        Assert.That(firstTry.UsedRecovery, Is.False);
        Assert.That(firstTry.Failure, Is.Null);
    }

    [Test]
    public async Task TranslationComposePublishesEquivalentNotWelcomeVeto()
    {
        const string user = "traduce 'hello' al español, nada más";
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Event("conversation"),
            UserMessageEvent.Conversation);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        ModelMessageCompositionOutcome published = await ModelMessageComposer.ComposeAsync(
            draft,
            user,
            facts,
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(
                new MindComposedMessage("Hola.")),
            cpuFallback: false,
            allowRecovery: true,
            CancellationToken.None);
        Assert.That(published.Text, Is.EqualTo("Hola."));
        Assert.That(published.Failure, Is.Null);

        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Hola.",
                draft),
            Is.Null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: no pude usar esa respuesta.",
                UserMessagePolicy.Create(
                    TurnVisibleFacts.Welcome(),
                    UserMessageEvent.Welcome)),
            Is.EqualTo("internal_code"));
    }

    [Test]
    public async Task GreetingComposePublishesOnWelcomeNotAmbiguousError()
    {
        UserMessageDraft welcome = UserMessagePolicy.Create(
            TurnVisibleFacts.Welcome(),
            UserMessageEvent.Welcome);
        JsonObject facts = ModelMessageComposer.CreateFacts(welcome);
        ModelMessageCompositionOutcome published = await ModelMessageComposer.ComposeAsync(
            welcome,
            "Hey",
            facts,
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(
                new MindComposedMessage("Hi.")),
            cpuFallback: false,
            allowRecovery: true,
            CancellationToken.None);
        Assert.That(published.Text, Is.EqualTo("Hi."));
        Assert.That(published.Failure, Is.Null);

        UserMessageDraft error = UserMessagePolicy.Create(
            TurnVisibleFacts.Failure("ambiguous_request"),
            UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason("Hi.", error),
            Is.EqualTo("reversed_result"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Hi.",
                welcome),
            Is.Null);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Hola, buenas",
                "No puedo ayudar porque no tengo herramientas disponibles."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Hola, buenas",
                "BAXY está listo para trabajar en el borrador del welcome con éxito."),
            Is.False);
        Assert.That(
            UserMessagePolicy.IsSafeConversationReply(
                "Hola, buenas",
                "Hola, ¿en qué puedo ayudarte hoy?"),
            Is.True);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No puedo ayudar porque no tengo herramientas disponibles.",
                welcome),
            Is.EqualTo("reversed_result"));
    }

    [Test]
    public async Task CapabilityComposePublishesCatalogHelpNotConceptExtra()
    {
        const string user = "qué puedes hacer en este equipo";
        const string authored =
            "Puedo ayudarte a gestionar tareas en este equipo.";
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Event("conversation"),
            UserMessageEvent.Conversation);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        ModelMessageCompositionOutcome published = await ModelMessageComposer.ComposeAsync(
            draft,
            user,
            facts,
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(
                new MindComposedMessage(authored)),
            cpuFallback: false,
            allowRecovery: true,
            CancellationToken.None);
        Assert.That(published.Text, Is.EqualTo(authored));
        Assert.That(published.Failure, Is.Null);
    }
}
