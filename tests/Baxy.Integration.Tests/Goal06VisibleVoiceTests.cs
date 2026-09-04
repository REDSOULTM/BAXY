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
                "Hola, estoy listo."),
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
            Is.EqualTo("welcome"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent(
                "Explícame qué es un huso horario en una frase."),
            Is.EqualTo("clarification"));
        Assert.That(
            UserMessagePolicy.ConversationFallbackIntent("cierra aquello"),
            Is.EqualTo("clarification"));
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
}
