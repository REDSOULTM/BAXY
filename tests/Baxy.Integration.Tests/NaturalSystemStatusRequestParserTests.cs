using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class NaturalSystemStatusRequestParserTests
{
    [TestCase("Dime la hora, please, en spanglish", true)]
    [TestCase("Tell me the time in Spanish.", true)]
    [TestCase("Dime la hora en inglés", true)]
    [TestCase("What time is it in spanglish?", true)]
    [TestCase("Explica qué es un reloj en spanglish", false)]
    [TestCase("Translate what time is it to Spanish", false)]
    [TestCase("Tell me the time in London", false)]
    public void ResponseLanguageDoesNotReplaceTheClockRequest(string text, bool expected)
    {
        Assert.That(NaturalSystemStatusRequestParser.IsCurrentTimeRequest(text), Is.EqualTo(expected));
    }

    [TestCase("qué hora es")]
    [TestCase("¿Qué hora es ahora?")]
    [TestCase("dime la hora actual")]
    [TestCase("what time is it?")]
    [TestCase("what's the time right now")]
    [TestCase("dame la hora")]
    [TestCase("Dime la hora exacta")]
    [TestCase("what is today's date")]
    [TestCase("cual es la fecha de hoy")]
    [TestCase("¿Me dices la hora?")]
    [TestCase("Could you tell me the time?")]
    [TestCase("the time, please")]
    [TestCase("hora ahora")]
    [TestCase("local time?")]
    [TestCase("time check")]
    [TestCase("dime la hora y no inventes")]
    [TestCase("Can you read this computer's clock?")]
    [TestCase("what time is it ahora")]
    [TestCase("what does the clock say")]
    [TestCase("qué marca el reloj")]
    [TestCase("tell the time in English")]
    [TestCase("otra vez la hora")]
    [TestCase("thanks, what time is it")]
    [TestCase("gracias, ¿qué hora es?")]
    [TestCase("finish with the local clock")]
    [TestCase("termina con la hora local")]
    [TestCase("local clock time?")]
    [TestCase("now the time, please")]
    [TestCase("hola, what time is it")]
    [TestCase("the time, don't guess")]
    [TestCase("a tiny clock fact")]
    [TestCase("según el reloj, qué día es")]
    [TestCase("dime la hora, porfa")]
    [TestCase("la hora ya")]
    [TestCase("otra vez, la hora")]
    [TestCase("now the clock, please")]
    [TestCase("según el reloj, qué hora marca")]
    [TestCase("thanks — what time is it")]
    [TestCase("clock now")]
    [TestCase("hora local, please")]
    public void ExplicitLocalTimeQueriesRouteDirectly(string text)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo("system.time"));
            Assert.That(operation?.Arguments, Is.Empty);
        });
    }

    [TestCase("por qué existen los husos horarios")]
    [TestCase("what is a time zone")]
    [TestCase("inventa una hora")]
    [TestCase("make up a time")]
    // LANG1909 (ecc19b60a; H0260/H0347): la hora pedida en otro idioma ya no se contesta en
    // español por el atajo; se pide repetir, como cualquier pedido fuera de es/en.
    [TestCase("Mi puoi dire che ore sono?")]
    [TestCase("wie spät ist es")]
    public void TimeZoneEssaysAndInventedClockAsksAreNotCurrentTimeReads(string text)
    {
        Assert.That(NaturalSystemStatusRequestParser.IsCurrentTimeRequest(text), Is.False);
        Assert.That(
            NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation),
            Is.False);
        Assert.That(operation, Is.Null);
    }

    [TestCase("¿Cómo está mi PC?", "summary")]
    [TestCase("what is my computer status?", "summary")]
    [TestCase("how está mi pc status", "summary")]
    [TestCase("revisa RAM y CPU", "cpu_memory")]
    [TestCase("Dime que versión de Windows tengo y cuanta RAM tiene este PC.", "os_memory")]
    [TestCase("current CPU usage", "cpu")]
    [TestCase("cuánta RAM tengo", "memory")]
    [TestCase("how much disk space is left", "disk")]
    [TestCase("¿Cuánto espacio libre tengo en C?", "disk")]
    [TestCase("¿Cuánto espacio libre tengo en el disco C?", "disk")]
    [TestCase("la batería está cargando?", "battery")]
    [TestCase("estado de la batería", "battery")]
    [TestCase("niveau de batterie", "battery")]
    [TestCase("quanto spazio libero ho sul disco", "disk")]
    [TestCase("qué tan cargado está el procesador", "cpu")]
    [TestCase("cuánta memoria me queda libre", "memory")]
    [TestCase("qué versión de Windows tengo", "os")]
    [TestCase("Dime mi GPU", "gpu_identity")]
    [TestCase("Dime que GPU tengo y cuanta VRAM tiene.", "gpu_identity")]
    [TestCase("que GPU tengo", "gpu_identity")]
    [TestCase("Dime qué GPU tengo", "gpu_identity")]
    [TestCase("que gpu tiene este pc?", "gpu_identity")]
    [TestCase("Cuanta vram tengo?", "gpu_identity")]
    [TestCase("show VRAM", "gpu_usage")]
    [TestCase("muestra mi VRAM", "gpu_usage")]
    [TestCase("GPU usage", "gpu_usage")]
    [TestCase("uso de GPU", "gpu_usage")]
    [TestCase("muestra uso de GPU con nvidia-smi", "gpu_usage")]
    [TestCase("qué tan llena está la GPU", "gpu_usage")]
    [TestCase("revisa VRAM", "gpu_usage")]
    [TestCase("revisa nvidia-smi", "gpu_usage")]
    [TestCase("verifica GPU con nvidia-smi sin estresar PC", "gpu_usage")]
    public void ExplicitLocalStatusQueriesRouteToTheirBoundedScope(
        string text,
        string expectedScope)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(operation?.Name, Is.EqualTo("system.status"));
            Assert.That(
                operation?.Arguments["scope"]?.GetValue<string>(),
                Is.EqualTo(expectedScope));
            Assert.That(operation?.Arguments, Has.Count.EqualTo(1));
        });
    }

    [TestCase("regarde les processus", "name")]
    [TestCase("lista procesos", "name")]
    [TestCase("List all running processes please", "name")]
    [TestCase("lista procesos por CPU", "cpu")]
    [TestCase("muestra los procesos por RAM", "memory")]
    public void ExplicitProcessInventoryIsBoundedAndReadOnly(
        string text,
        string expectedSort)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True, text);
            Assert.That(operation?.Name, Is.EqualTo("system.process.list"), text);
            Assert.That(operation?.Arguments["sort"]?.GetValue<string>(), Is.EqualTo(expectedSort));
            Assert.That(operation?.Arguments["limit"]?.GetValue<int>(), Is.EqualTo(10));
            Assert.That(operation?.Arguments, Has.Count.EqualTo(2));
        });
    }

    [TestCase("qué es una CPU")]
    [TestCase("cuánto vale esa CPU?")]
    [TestCase("lista los procesos que más RAM consumen")]
    [TestCase("show time, IP and RAM")]
    [TestCase("cuánta RAM usa Parakeet?")]
    [TestCase("muestra la fecha actual y el uso de RAM")]
    [TestCase("no muestres el uso de CPU")]
    [TestCase("si puedes, revisa RAM y CPU")]
    [TestCase("revisa RAM y CPU y abre Notepad")]
    [TestCase("qué es una GPU")]
    [TestCase("precios actuales GPU")]
    [TestCase("si VRAM está alta, evita abrir apps pesadas")]
    [TestCase("monitoreo de GPU")]
    [TestCase("por qué mi GPU no se usa")]
    [TestCase("qué está usando VRAM ahora?")]
    [TestCase("verifica GPU mientras Carter responde")]
    [TestCase("que GPU tengo y cuanta VRAM tiene")]
    [TestCase("muestra VRAM")]
    [TestCase("qué es la hora UTC")]
    [TestCase("qué hora es en Tokio mañana")]
    [TestCase("dime la hora y abre Notepad")]
    [TestCase("talk, and also give the time")]
    public void KnowledgeProcessConditionalAndCompositeQueriesFailClosed(string text)
    {
        bool parsed = NaturalNoteRequestParser.TryParse(text, out RoutedOperation? operation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.False, text);
            Assert.That(operation, Is.Null, text);
        });
    }

    [Test]
    public void MalformedUtf16FailsClosedWithoutThrowing()
    {
        string malformed = string.Concat("cuánta RAM tengo", '\uD800');
        RoutedOperation? operation = null;
        bool parsed = true;

        Assert.DoesNotThrow(() =>
            parsed = NaturalNoteRequestParser.TryParse(malformed, out operation));
        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.False);
            Assert.That(operation, Is.Null);
        });
    }
}
