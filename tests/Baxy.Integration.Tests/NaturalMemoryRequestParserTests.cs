using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

public sealed class NaturalMemoryRequestParserTests
{
    [TestCase("What name have you saved in private memory?")]
    [TestCase("Which name have you stored in your local memory?")]
    [TestCase("What name do you have saved?")]
    [TestCase("What is my stored name?")]
    [TestCase("¿Qué nombre tienes guardado en tu memoria privada?")]
    [TestCase("¿Qué nombre has guardado en la memoria?")]
    [TestCase("¿Cuál es mi nombre guardado?")]
    [TestCase("¿Qué nombre tienes almacenado en la memoria local privada?")]
    public void StoredNameQuestionsReadTheExactPrivateName(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.recall"));
            Assert.That(result.Operation?.PrivateArguments["scope"]?.GetValue<string>(), Is.EqualTo("exact"));
            Assert.That(result.Operation?.PrivateArguments["selector"]?.GetValue<string>(), Is.EqualTo("name"));
        });
    }

    [TestCase("What name should you save in private memory?")]
    [TestCase("Do not read my saved name.")]
    [TestCase("What name has my coworker saved?")]
    [TestCase("What name have you saved and open Steam?")]
    [TestCase("Traduce: What name have you saved in private memory?")]
    [TestCase("¿Qué nombre tiene guardado mi hermano?")]
    [TestCase("¿Qué nombre guardarás en tu memoria?")]
    [TestCase("What name have you saved in the clipboard?")]
    [TestCase("What name have you saved if I ask next week?")]
    public void OtherNameLanguageDoesNotAuthorizeAStoredNameRead(string text)
    {
        Assert.That(NaturalMemoryRequestParser.Classify(text).Operation, Is.Null);
    }

    [TestCase("My name is Jordan. Remember my name.", "Jordan")]
    [TestCase("Me llamo Álvaro y quiero que guardes mi nombre.", "Álvaro")]
    [TestCase("My name is José Luis; save my name.", "José Luis")]
    [TestCase("Mi nombre es Zoë; recuerda mi nombre.", "Zoë")]
    [TestCase("Remember my name. My name is Morgan.", "Morgan")]
    public void DeclarationAndExplicitNameSaveBindTheSamePrivateDatum(string text, string name)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
        Assert.That(result.Operation!.Name, Is.EqualTo("memory.save"));
        Assert.That(result.Operation.PrivateArguments["selector"]!.GetValue<string>(), Is.EqualTo("name"));
        Assert.That(result.Operation.PrivateArguments["value"]!.GetValue<string>(), Is.EqualTo(name));
        Assert.That(result.Operation.PrivateArguments["sensitivity"]!.GetValue<string>(), Is.EqualTo("personal"));
        Assert.That(result.Operation.PrivateArguments["retention"]!.GetValue<string>(), Is.EqualTo("persistent"));
    }

    [TestCase("Me llamo Lina.")]
    [TestCase("Me llamo Lina y no quiero que guardes mi nombre.")]
    [TestCase("Si me llamo Lina, guarda mi nombre.")]
    [TestCase("Mi hermana se llama Lina. Recuerda mi nombre.")]
    [TestCase("My name is Jordan. Can you remember names?")]
    [TestCase("Me llamo Lina y abre Steam.")]
    public void ADeclarationAloneOrAnUnrelatedClauseDoesNotAuthorizeNamePersistence(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);
        Assert.That(result.Outcome, Is.Not.EqualTo(MemoryParseOutcome.Route));
        Assert.That(result.Operation, Is.Null);
    }

    [TestCase("Recuerda mi nombre")]
    [TestCase("Quiero que recuerdes mi nombre cuando te lo pregunte")]
    [TestCase("Remember my name when I ask again")]
    [TestCase("I want you to save my name")]
    [TestCase("I will tell you my name and I want you to remember it")]
    [TestCase("Tienes memoria, puedes guardar mi nombr?, quiero decirte mi nombre y quiero que lo recuerdes cuando te lo pregunte")]
    public void ExplicitSaveRequestCanAwaitItsNameWithoutCreatingAnOperation(string text)
    {
        MemoryParseResult parsed = NaturalMemoryRequestParser.Classify(text);
        Assert.Multiple(() =>
        {
            Assert.That(parsed.Outcome, Is.EqualTo(MemoryParseOutcome.Clarify));
            Assert.That(parsed.MissingSaveSubject, Is.EqualTo(MemorySaveSubject.Name));
            Assert.That(parsed.Operation, Is.Null);
            Assert.That(parsed.MustNotPersist, Is.True);
        });
    }

    [TestCase("¿Puedes recordar nombres?")]
    [TestCase("No quiero que recuerdes mi nombre")]
    [TestCase("Cuando abra Steam, recuerda mi nombre")]
    [TestCase("Mañana recuerda mi nombre")]
    [TestCase("me llamo Lina")]
    [TestCase("Remember my name is Lina")]
    public void OtherMemoryLanguageDoesNotCreateAMissingNameAuthority(string text)
    {
        Assert.That(NaturalMemoryRequestParser.Classify(text).MissingSaveSubject, Is.Null);
    }

    [TestCase("Borra el archivo C03-Prueba-Respuesta-20260906.txt del escritorio", false)]
    [TestCase("open Quarterly-customer-report-20260830-final.pdf", false)]
    [TestCase("move configuration-production-20260830-backup.json", false)]
    [TestCase("open sk_test_1234567890abcdefghijklmnop.txt", true)]
    [TestCase("remember gldt-0123456789abcdefghij", true)]
    [TestCase("save eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.signature1", true)]
    [TestCase("mi password es Quarterly-customer-report-20260830-final.pdf", true)]
    public void PublicProjectionDistinguishesDocumentNamesFromCredentialTokens(
        string text,
        bool expectedSensitive)
    {
        Assert.That(
            NaturalMemoryRequestParser.ContainsSensitiveMaterial(text),
            Is.EqualTo(expectedSensitive));
    }

    [Test]
    public void AmbiguousAudioDeviceRequestFlowsToTheMindPlanner()
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(
            "puedes cambiar el dispositivo");

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.NoRoute), result.ToString());
            Assert.That(result.MustNotClaimStandaloneRoute, Is.False, result.ToString());
        });
    }

    [TestCase("my favorite city is Lima")]
    [TestCase("i'm a developer")]
    [TestCase("me llamo Albeda")]
    public void ImplicitPersonalFactsRequireConsentBeforePersistence(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.AskToSave));
            Assert.That(result.Operation, Is.Null);
            Assert.That(result.MustNotPersist, Is.True);
        });
    }

    [TestCase("what do you know about me")]
    [TestCase("que tienes guardado sobre mi")]
    [TestCase("cosa ricordi di me")]
    public void HistoricalMemoryInspectionRoutesPrivately(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.recall"));
            Assert.That(
                result.Operation?.PrivateArguments["scope"]?.GetValue<string>(),
                Is.EqualTo("all"));
        });
    }

    [Test]
    public void ExplicitGenericFactUsesStablePrivateSelector()
    {
        MemoryParseResult first = NaturalMemoryRequestParser.Classify(
            "Recuerda que mi editor favorito es VS Code");
        MemoryParseResult second = NaturalMemoryRequestParser.Classify(
            "Recuerda que mi editor favorito es VS Code");

        Assert.Multiple(() =>
        {
            Assert.That(first.Operation?.Name, Is.EqualTo("memory.save"));
            Assert.That(
                first.Operation?.PrivateArguments["selector"]?.GetValue<string>(),
                Does.StartWith("historical_fact_"));
            Assert.That(
                second.Operation?.PrivateArguments["selector"]?.GetValue<string>(),
                Is.EqualTo(first.Operation?.PrivateArguments["selector"]?.GetValue<string>()));
        });
    }

    // The reminder boundary only takes tasks and due moments: a datum to keep
    // («recuerda que <dato>», «recordame que <preferencia>») is still a save.
    [TestCase("recuerda que mi hermana vive en Curicó")]
    [TestCase("recordame que prefiero el café sin azúcar")]
    [TestCase("remember that my sister lives in Lima")]
    public void DatumToKeepStaysAMemorySaveBesideTheReminderBoundary(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route), text);
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.save"), text);
        });
    }

    [Test]
    public void GenericPersonalTopicForgetRoutesPrivatelyAndRequiresConfirmation()
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(
            "olvidate de mi direccion vieja");

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.forget"));
            Assert.That(
                result.Operation?.PrivateArguments["scope"]?.GetValue<string>(),
                Is.EqualTo("topic"));
            Assert.That(
                result.Operation?.PrivateArguments["selector"]?.GetValue<string>(),
                Is.EqualTo("mi direccion vieja"));
            Assert.That(
                result.Operation?.PrivateArguments["confirmationRequired"]?.GetValue<bool>(),
                Is.True);
        });
    }

    [TestCase("olvida lo anterior")]
    [TestCase("olvida todo lo que sabes")]
    [TestCase("forget everything you know")]
    public void UnderspecifiedDestructiveForgetRequiresClarification(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Clarify));
            Assert.That(result.Operation, Is.Null);
            Assert.That(result.MustNotDelete, Is.True);
        });
    }

    // M111 (DEV-F v4d F-w10-t3): «that» saved in a note, a task or a list is that record, never BAXY's memory.
    [TestCase("save that in a note called router settings")]
    [TestCase("guarda eso en una nota que se llame claves del wifi")]
    [TestCase("guarda esto como nota")]
    [TestCase("save this to my notes please")]
    [TestCase("guarda eso en la lista de pendientes")]
    public void ThatSavedInARecordIsNotAMemorySave(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.NoRoute), result.ToString());
            Assert.That(result.Operation, Is.Null);
        });
    }

    [TestCase("remember that")]
    [TestCase("guarda eso para siempre")]
    public void ThatSavedWithNoRecordStillAsksWhatToRemember(string text)
    {
        Assert.That(NaturalMemoryRequestParser.Classify(text).Outcome, Is.EqualTo(MemoryParseOutcome.Clarify));
    }

    [TestCase("abrí el administrador de tareas")]
    [TestCase("ouvre le gestionnaire des tâches")]
    public void ApplicationAdministratorWordsDoNotBecomeAuthorityMemory(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.NoRoute));
            Assert.That(result.MustNotChangeAuthority, Is.False);
            Assert.That(result.Operation, Is.Null);
        });
    }

    [Test]
    public void AccentedSessionForgetRoutesPrivatelyWithoutDeletingPersistentMemory()
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(
            "olvidá lo anterior de esta conversación");

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.forget"));
            Assert.That(
                result.Operation?.PrivateArguments["scope"]?.GetValue<string>(),
                Is.EqualTo("session"));
            Assert.That(
                result.Operation?.PrivateArguments["mustNotDeletePersistent"]?.GetValue<bool>(),
                Is.True);
        });
    }

    [Test]
    public void ItalianPersistentLanguagePreferenceRoutesPrivately()
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(
            "parla in inglese da adesso in poi");

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.save"));
            Assert.That(
                result.Operation?.PrivateArguments["selector"]?.GetValue<string>(),
                Is.EqualTo("language"));
            Assert.That(
                result.Operation?.PrivateArguments["value"]?.GetValue<string>(),
                Is.EqualTo("en"));
        });
    }

    [TestCase(
        "RECUERDA   que my favorite color is verde!!!",
        "memory.save",
        "favorite_color",
        "verde")]
    [TestCase(
        "Remember that my name is Zoë.",
        "memory.save",
        "name",
        "Zoë")]
    [TestCase(
        "Recuerda durante esta sesión que mi proyecto se llama Ágora",
        "memory.save",
        "project_name",
        "Ágora")]
    [TestCase(
        "remember that I prefer short responses",
        "memory.save",
        "response_style",
        "short")]
    [TestCase(
        "recuerda que I prefer dark mode",
        "memory.save",
        "display_mode",
        "dark")]
    [TestCase(
        "WHAT'S MY FAVORITE COLOR?",
        "memory.recall",
        "favorite_color",
        null)]
    [TestCase(
        "forget my favorite color",
        "memory.forget",
        "favorite_color",
        null)]
    [TestCase(
        "Quel est mon nom, s'il vous plaît?",
        "memory.recall",
        "name",
        null)]
    [TestCase(
        "wie heiße ich",
        "memory.recall",
        "name",
        null)]
    [TestCase(
        "Erinnere dich an meinen Firmennamen",
        "memory.recall",
        "employer",
        null)]
    [TestCase(
        "Quien soy yo?",
        "memory.recall",
        "name",
        null)]
    [TestCase(
        "Was ist mein Name noch mal?",
        "memory.recall",
        "name",
        null)]
    [TestCase(
        "Was ist meine bevorzugte Einstellung?",
        "memory.recall",
        "preference",
        null)]
    public void RoutesBoundedSpanishEnglishAndSpanglishVariations(
        string text,
        string expectedOperation,
        string expectedSelector,
        string? expectedValue)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo(expectedOperation));
            Assert.That(
                operation?.PrivateArguments["selector"]?.GetValue<string>(),
                Is.EqualTo(expectedSelector));
            if (expectedValue is not null)
            {
                Assert.That(
                    operation?.PrivateArguments["value"]?.GetValue<string>(),
                    Is.EqualTo(expectedValue));
            }
        });
    }

    [TestCase("Desactiva la memoria privada.", false)]
    [TestCase("Deshabilita tu memoria personal local.", false)]
    [TestCase("Activa la memoria privada local de BAXY.", true)]
    [TestCase("Habilita tu memoria local.", true)]
    [TestCase("Disable your private local memory.", false)]
    [TestCase("Enable BAXY's personal memory.", true)]
    [TestCase("Turn the private memory off.", false)]
    [TestCase("Turn your local memory on.", true)]
    [TestCase("Baxy, please, disable your private memory.", false)]
    [TestCase("Baxy, por favor, activa tu memoria privada.", true)]
    [TestCase("disable memory", false)]
    [TestCase("habilita la memoria", true)]
    [TestCase("turn memory on", true)]
    [TestCase("turn memory off", false)]
    [TestCase("desactiva la memoria local de baxy", false)]
    [TestCase("enable baxy's private local memory", true)]
    public void ConfigurationRecognizesItsOwnQualifiedMemoryTarget(string text, bool enabled)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation?.Name, Is.EqualTo("memory.configure"));
            Assert.That(result.Operation?.PrivateArguments["enabled"]?.GetValue<bool>(), Is.EqualTo(enabled));
        });
    }

    [TestCase("No desactives la memoria privada.")]
    [TestCase("No desactiva la memoria privada.")]
    [TestCase("Do not disable your private memory.")]
    [TestCase("Never enable private memory.")]
    [TestCase("¿Qué significa desactiva la memoria privada?")]
    [TestCase("Explain how to disable private memory.")]
    [TestCase("Is your private memory enabled?")]
    [TestCase("Dime si la memoria privada está activa.")]
    [TestCase("If I asked you to disable memory, what would happen?")]
    [TestCase("Repite: desactiva la memoria privada.")]
    [TestCase("\"Disable your private memory\"")]
    [TestCase("Desactiva la memoria privada de Chrome.")]
    [TestCase("Disable Windows virtual memory.")]
    [TestCase("Desactiva la memoria RAM.")]
    [TestCase("Activa la memoria privada y abre Steam.")]
    [TestCase("Disable your memory and erase all my files.")]
    public void ConfigurationDoesNotTreatOtherMemoryMentionsAsConsent(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.That(result.Operation?.Name,
            Is.Not.EqualTo("memory.configure").And.Not.EqualTo("memory.enable").And.Not.EqualTo("memory.disable"));
    }

    [TestCase("activa la memoria", "memory.configure", "enabled", true)]
    [TestCase("enable memory", "memory.configure", "enabled", true)]
    [TestCase("desactiva la memoria", "memory.configure", "enabled", false)]
    [TestCase("disable memory", "memory.configure", "enabled", false)]
    public void RoutesExplicitMemoryConsentControls(
        string text,
        string expectedOperation,
        string property,
        bool expectedValue)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo(expectedOperation));
            Assert.That(
                operation?.PrivateArguments[property]?.GetValue<bool>(),
                Is.EqualTo(expectedValue));
        });
    }

    [TestCase("tienes memoria", "memory.status")]
    [TestCase("do you have memory", "memory.status")]
    [TestCase(
        "Hey, please, is your personal local-memory store working right now",
        "memory.status")]
    [TestCase(
        "Oye, please check whether tu personal local-memory store está working ahora",
        "memory.status")]
    [TestCase(
        "Baxy, escucha: Cuando puedas, comprueba si tus recuerdos privados de este PC están operativos",
        "memory.status")]
    [TestCase(
        "Baxy, listen: One quick request, please: check whether your private memories on this PC are operational",
        "memory.status")]
    [TestCase(
        "Cuando tengas un minuto, please check si tus private memories de este PC est\u00e1n operational",
        "memory.status")]
    [TestCase(
        "Oye, Baxy: cuando tengas un minuto, please check si tus private memories de este PC est\u00e1n operational.",
        "memory.status")]
    [TestCase(
        "Che, Baxy: porfa, when you have a minute, please check si tus private memories de este PC est\u00e1n operational.",
        "memory.status")]
    [TestCase(
        "Che, Baxy: one small request, porfa: est\u00e1 working ahora tu personal local-memory store.",
        "memory.status")]
    [TestCase("lista mi memoria", "memory.list")]
    [TestCase("list my memories", "memory.list")]
    [TestCase("exporta mi memoria", "memory.export")]
    [TestCase("export my memory", "memory.export")]
    public void RoutesExplicitInspectionAndRedactedExportControls(
        string text,
        string expectedOperation)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo(expectedOperation));
            Assert.That(operation?.PrivateArguments["version"]?.GetValue<int>(), Is.EqualTo(1));
            if (string.Equals(expectedOperation, "memory.export", StringComparison.Ordinal))
            {
                Assert.That(
                    operation?.PrivateArguments["includeSecrets"]?.GetValue<bool>(),
                    Is.False);
            }
        });
    }

    [TestCase("Dime cómo está la memoria local de Baxy")]
    [TestCase("Baxy, por favor: dime cómo está la memoria local de Baxy.")]
    [TestCase("Consulta el estado de tus recuerdos locales")]
    [TestCase("Baxy, por favor: consulta el estado de tus recuerdos locales.")]
    [TestCase("Show the status of Baxy's local memory")]
    [TestCase("Baxy, please: show the status of Baxy's local memory.")]
    [TestCase("Check whether local memory is enabled")]
    [TestCase("Baxy, please: check whether local memory is enabled.")]
    [TestCase("Checkea el estado de Baxy memory")]
    [TestCase("Baxy, porfa: checkea el estado de Baxy memory.")]
    [TestCase("Dime whether tu personal local-memory store está operational en este device")]
    [TestCase("Verifica si tus memorias privadas locales están activas ahora mismo")]
    [TestCase("Let me know the operational state of the personal memory Baxy keeps locally right now")]
    [TestCase("Aclárame whether la private memory guardada locally está working on este computer")]
    [TestCase("Te paso una indicación específica para el equipo: dime cómo está la memoria local de Baxy")]
    [TestCase("Here is a specific request for the PC: check whether local memory is enabled")]
    // The frame's word classes are completed from the language rather than
    // from the wordings a corpus used, and this border must match the Python
    // one exactly. "ordenador" is the ordinary Spanish-from-Spain word for a
    // computer; without it the frame was never stripped for those speakers.
    [TestCase("Esta orden es para el ordenador: dime cómo está la memoria local de Baxy")]
    [TestCase("Va un encargo para la máquina: dime cómo está la memoria local de Baxy")]
    [TestCase("Atiende este mandato en el portátil: dime cómo está la memoria local de Baxy")]
    [TestCase("Recibe esta solicitud de la computadora: dime cómo está la memoria local de Baxy")]
    [TestCase("This errand goes to the laptop: check whether local memory is enabled")]
    [TestCase("Take care of the following on the machine: check whether local memory is enabled")]
    [TestCase("For this computer right now, please check whether local memory is enabled")]
    [TestCase("Baxy, haz esto: comprueba si tus recuerdos privados locales están operativos")]
    public void RoutesGeneralizationSurfaceStatusRequests(string text)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo("memory.status"));
            Assert.That(
                operation?.PrivateArguments["version"]?.GetValue<int>(),
                Is.EqualTo(1));
        });
    }

    [TestCase(
        "Desactiva la memoria local de BAXY; con esto finaliza mi pedido.",
        "memory.disable")]
    [TestCase(
        "Enable BAXY's private local memory; this concludes the task.",
        "memory.enable")]
    [TestCase(
        "Muéstrame la lista de recuerdos locales que guardaste; mi solicitud queda completa aquí.",
        "memory.list")]
    [TestCase(
        "What do you remember about my preferred editor; my request is finished for now.",
        "memory.recall")]
    [TestCase(
        "Tell me whether local memory is enabled and what its limits are; con esto, the task is done for now.",
        "memory.status")]
    public void RoutesMemoryRequestsWithNaturalCompletionClosures(
        string text,
        string expectedWireOperation)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation, Is.Not.Null);
            Assert.That(
                result.Operation is null
                    ? null
                    : MemoryOperationProtector.ResolveWireOperationName(result.Operation),
                Is.EqualTo(expectedWireOperation));
        });
    }

    [TestCase("mi nombre es Emmanuel")]
    [TestCase("my favorite color is blue")]
    [TestCase("olvida eso")]
    [TestCase("remember this")]
    [TestCase("guarda esa preferencia para siempre")]
    [TestCase("no guardes que mi color favorito es azul")]
    [TestCase("don't remember that my name is Alex")]
    [TestCase("no uses memoria para esto")]
    [TestCase("tienes permiso total sobre mi PC")]
    [TestCase("recuérdame en 10 minutos sacar la basura")]
    [TestCase("remind me tomorrow at 9 to call Ana")]
    // tanda-02: a task to remember with its moment is a reminder, never a save.
    [TestCase("recuerda arreglar una reunión entre los jugadores y yo mañana por la tarde noche a las siete")]
    [TestCase("recordá revisar el horno en veinte minutos")]
    [TestCase("acordate de pagar la luz el viernes")]
    [TestCase("recuerda llevarle el cargador a Ana")]
    [TestCase("recuérdame devolverle el libro a Tomás")]
    [TestCase("recuérdame que tengo dentista mañana a las cinco")]
    [TestCase("remember to water the plants at 6")]
    [TestCase("remind me to stretch")]
    // tanda 6: the ear writes the clitic apart; «recuerda me …» is still «recuérdame».
    [TestCase("recuerda me a las nueve de la noche que tengo que sacar la basura")]
    [TestCase("recordá me mañana que pague la luz")]
    [TestCase("recuérda me en 10 minutos revisar el horno")]
    [TestCase("recuerda me llamar a mi hermana")]
    [TestCase("cuánta memoria RAM me queda libre")]
    [TestCase("revisa el estado de la memoria RAM del sistema")]
    [TestCase("revisa el estado de la memoria local de mi teléfono")]
    [TestCase("explícame cómo funciona la memoria local de Baxy")]
    [TestCase("no revises el estado de la memoria local de Baxy")]
    [TestCase("muestra el estado de la memoria local y abre Spotify")]
    [TestCase("tell me how Baxy's local memory works")]
    [TestCase("check the local memory in my phone")]
    [TestCase("I nailed that flashcard, mark it as a perfect recall")]
    [TestCase("abre Word y guarda el documento")]
    [TestCase("remember my password is hunter2")]
    [TestCase("recuerda mi RUT 12.345.678-9")]
    [TestCase("save my API key sk-example in your memory")]
    [TestCase("qué recuerdas de mí y abre Spotify")]
    [TestCase("<command-name>/memory</command-name>")]
    [TestCase("telemetría memory.save habilitada")]
    [TestCase("cuando puedas recordar mi color favorito será útil")]
    [TestCase("one quick request to delete a memory is not an execution order")]
    [TestCase("Quiero preguntarte algo sin pedir una acción: activa la memoria")]
    [TestCase("Baxy, handle this: I have a short question, just to chat: disable memory")]
    [TestCase("mira mis recuerdos de infancia con atención")]
    public void RejectsInferenceAnaphoraNegationSecretsRemindersHomonymsAndCompositions(
        string text)
    {
        bool parsed = NaturalMemoryRequestParser.TryParse(
            text,
            out MemoryRoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.False, text);
            Assert.That(operation, Is.Null, text);
        });
    }

    [Test]
    public void RejectsNullBlankControlMalformedUtf16AndOversizedInputWithoutThrowing()
    {
        string?[] malformed =
        [
            null,
            string.Empty,
            "   ",
            "recuerda que mi nombre es A\0lex",
            "recuerda que mi nombre es A\nlex",
            "remember my name is " + new string('\ud800', 1),
            "remember my name is " + new string('\udc00', 1),
            "remember my name is " + new string('a', 4097),
        ];

        foreach (string? text in malformed)
        {
            MemoryRoutedOperation? operation = null;
            bool parsed = true;
            Assert.DoesNotThrow(
                () => parsed = NaturalMemoryRequestParser.TryParse(text, out operation),
                text ?? "<null>");
            Assert.Multiple(() =>
            {
                Assert.That(parsed, Is.False, text);
                Assert.That(operation, Is.Null, text);
            });
        }
    }

    [Test]
    public void MemoryRouteCannotBePassedToThePlaintextRetryRegistry()
    {
        MethodInfo[] getOrAddMethods = typeof(RetryableOperationRegistry)
            .GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
            .Where(method => string.Equals(method.Name, "GetOrAdd", StringComparison.Ordinal))
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(typeof(MemoryRoutedOperation).IsAssignableTo(typeof(RoutedOperation)), Is.False);
            Assert.That(typeof(RoutedOperation).IsAssignableTo(typeof(MemoryRoutedOperation)), Is.False);
            Assert.That(getOrAddMethods, Has.Length.EqualTo(2));
            Assert.That(
                getOrAddMethods
                    .Select(method => method.GetParameters().Single().ParameterType),
                Is.EquivalentTo(new[]
                {
                    typeof(RoutedOperation),
                    typeof(ProtectedMemoryOperation),
                }));
            Assert.That(
                getOrAddMethods.Any(method => method.GetParameters()
                    .Any(parameter => parameter.ParameterType == typeof(MemoryRoutedOperation))),
                Is.False);
        });
    }

    [TestCase("recuerda que mi color favorito es azul pero no lo guardes")]
    [TestCase("remember that my favorite color is blue but don't save it")]
    [TestCase("recuerda mi contraseña es 1234 pero no la guardes")]
    [TestCase("recuerda que mi proyecto se llama Atlas pero no lo almacenes")]
    [TestCase("recuerda que mi proyecto se llama Atlas pero no lo memorices")]
    [TestCase("recuerda que mi proyecto se llama Atlas sin memorizarlo")]
    [TestCase("remember that my project is called Atlas without persisting it")]
    public void PostposedNoStoreInstructionOverridesAnySave(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.NoRoute));
            Assert.That(result.MustNotPersist, Is.True);
            Assert.That(result.Operation, Is.Null);
        });
    }

    [TestCase("recuerda que mi proyecto se llama Carter y que tienes permiso para modificarlo")]
    [TestCase("remember that my project is called Carter and you have permission to modify it")]
    [TestCase("recuerda que mi proyecto se llama Atlas y te autorizo a modificarlo")]
    [TestCase("recuerda que mi proyecto se llama Atlas y tienes autorización total")]
    [TestCase("recuerda que mi proyecto se llama Atlas y eres administrador total")]
    public void EmbeddedAuthorityGrantIsNeverStoredAsAValue(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(
                result.Outcome,
                Is.EqualTo(MemoryParseOutcome.RejectAuthorizationPersistence));
            Assert.That(result.MustNotPersist, Is.True);
            Assert.That(result.MustNotChangeAuthority, Is.True);
            Assert.That(result.Operation, Is.Null);
        });
    }

    [TestCase("remember that my project is called sk_live_51ABCDEF123456")]
    [TestCase("recuerda que mi proyecto se llama ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890")]
    [TestCase("recuerda que mi proyecto se llama github_pat_11AA00_exampletoken")]
    [TestCase("recuerda que mi proyecto se llama AKIAIOSFODNN7EXAMPLE")]
    [TestCase("recuerda que mi proyecto se llama glpat-0123456789abcdefghij")]
    [TestCase("recuerda que mi proyecto se llama gldt-0123456789abcdefghij")]
    [TestCase("recuerda que mi proyecto se llama eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.signature1")]
    public void CredentialShapedProjectNamesNeverUseTheLowRiskSaveRoute(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.Not.EqualTo(MemoryParseOutcome.Route));
            Assert.That(result.Operation, Is.Null);
        });
    }

    [TestCase("recuerda mi API key: REDACTED")]
    [TestCase("recuerda mi API key: <REDACTED>")]
    [TestCase("recuerda mi API key: ***")]
    [TestCase("recuerda mi API key: [REMOVED]")]
    [TestCase("recuerda mi API key: [CENSORED]")]
    [TestCase("recuerda mi API key: (CENSORED)")]
    [TestCase("recuerda mi API key: N/A")]
    public void RedactedSensitivePlaceholdersNeverCreateAnExecutableDraft(string text)
    {
        MemoryParseResult result = NaturalMemoryRequestParser.Classify(text);

        Assert.Multiple(() =>
        {
            Assert.That(result.Outcome, Is.EqualTo(MemoryParseOutcome.ConfirmSensitiveSave));
            Assert.That(result.MustNotPersist, Is.True);
            Assert.That(result.Operation, Is.Null);
        });
    }

    [Test]
    public void RoutedPrivateArgumentsAreImmutableSnapshots()
    {
        MemoryParseResult sensitive = NaturalMemoryRequestParser.Classify(
            "recuerda mi contraseña es 1234");
        MemoryParseResult forget = NaturalMemoryRequestParser.Classify(
            "borra mi color favorito");
        JsonObject sensitiveClone = sensitive.Operation!.PrivateArguments;
        JsonObject forgetClone = forget.Operation!.PrivateArguments;

        sensitiveClone["sensitivity"] = "normal";
        sensitiveClone["value"] = "changed";
        forgetClone["confirmationRequired"] = false;

        Assert.Multiple(() =>
        {
            Assert.That(
                sensitive.Operation.PrivateArguments["sensitivity"]?.GetValue<string>(),
                Is.EqualTo("secret"));
            Assert.That(
                sensitive.Operation.PrivateArguments["value"]?.GetValue<string>(),
                Is.EqualTo("1234"));
            Assert.That(
                forget.Operation.PrivateArguments["confirmationRequired"]?.GetValue<bool>(),
                Is.True);
        });
    }

    [Test]
    public void TypedMemoryResultsRedactPrivateArgumentsFromDiagnosticText()
    {
        const string canary = "sk-BAXY-PARSER-CANARY";
        var operation = new MemoryRoutedOperation(
            "memory.save",
            new JsonObject
            {
                ["version"] = 1,
                ["selector"] = "api_key",
                ["sensitivity"] = "secret",
                ["value"] = canary,
            });
        MemoryParseResult result = MemoryParseResult.ConfirmSensitiveSave(operation);

        Assert.Multiple(() =>
        {
            Assert.That(operation.ToString(), Does.Not.Contain(canary));
            Assert.That(operation.ToString(), Does.Contain("[REDACTED]"));
            Assert.That(result.ToString(), Does.Not.Contain(canary));
            Assert.That(result.ToString(), Does.Contain("[REDACTED]"));
        });
    }

    [Test]
    public void TypedMemoryResultFactoriesRejectMissingRoutesAndInvalidSensitiveDrafts()
    {
        var invalidSensitiveDraft = new MemoryRoutedOperation(
            "memory.recall",
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "all",
                ["selector"] = null,
            });
        var downgradedSecret = new MemoryRoutedOperation(
            "memory.save",
            new JsonObject
            {
                ["version"] = 1,
                ["selector"] = "api_key",
                ["value"] = "sk-BAXY-DIRECT-CANARY",
                ["kind"] = "fact",
                ["retention"] = "persistent",
                ["sensitivity"] = "normal",
                ["tags"] = new JsonArray(),
            });
        var unconfirmedForget = new MemoryRoutedOperation(
            "memory.forget",
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "all",
                ["selector"] = null,
                ["confirmationRequired"] = false,
            });

        Assert.Multiple(() =>
        {
            Assert.That(
                () => MemoryParseResult.Route(null!),
                Throws.TypeOf<ArgumentNullException>());
            Assert.That(
                () => MemoryParseResult.ConfirmSensitiveSave(invalidSensitiveDraft),
                Throws.TypeOf<ArgumentException>());
            Assert.That(
                () => MemoryParseResult.Route(downgradedSecret),
                Throws.TypeOf<ArgumentException>());
            Assert.That(
                () => MemoryParseResult.Route(unconfirmedForget),
                Throws.TypeOf<ArgumentException>());
        });
    }

}
