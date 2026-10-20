using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// The view the model reads of a look (src/Baxy.App/ScreenViewProjection.cs, linked here: the App has no test project):
/// it keeps what the reader returned. A control the worker found several times is listed once with the times it was
/// found (its «repeated» counts the copies after the first), and a line of text that repeats stays each time.
/// </summary>
[TestFixture]
public sealed class ScreenViewProjectionTests
{
    // The receipt as WindowsVisibleControlAdapter writes it: «repeated» only when the worker counted copies.
    private const string Look =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"WhatsApp\",\"process\":\"WhatsApp\",\"processId\":42,\"hwnd\":1234," +
        "\"foreground\":true,\"focused\":null}," +
        "\"controls\":[" +
        "{\"i\":1,\"kind\":\"Button\",\"name\":\"Enviar\",\"state\":\"\",\"value\":null}," +
        "{\"i\":2,\"kind\":\"ListItem\",\"name\":\"prueba\",\"state\":\"\",\"value\":null,\"repeated\":1}," +
        "{\"i\":3,\"kind\":\"Button\",\"name\":\"Responder\",\"state\":\"\",\"value\":null,\"repeated\":2}]," +
        "\"controlCount\":3," +
        "\"text\":{\"T\":[\"Abuela\"],\"C\":[\"ok\",\"prueba BAXY\",\"prueba BAXY\"],\"B\":[\"ok\"]}," +
        "\"textAuthority\":\"windows_media_ocr_lines\",\"authority\":\"uia\"}";

    [Test]
    public void AControlFoundSeveralTimesSaysTheTimesAndEveryRepeatedLineStays()
    {
        JsonObject projected = Project("{\"status\":\"completed\",\"observed\":{\"controlCount\":3}}");

        Assert.That((string?)projected["view"], Is.EqualTo(
            "Ventana «WhatsApp» (WhatsApp, window 1234), al frente\n" +
            "Controles:\n" +
            "[1] Button «Enviar»\n" +
            "[2] ListItem «prueba» ×2\n" +
            "[3] Button «Responder» ×3\n" +
            "Texto arriba: Abuela\n" +
            "Texto centro: ok | prueba BAXY | prueba BAXY\n" +
            "Texto abajo: ok"));
    }

    [Test]
    public void TheKernelsHeaderTravelsAndOnlyItsObservationBecomesTheView()
    {
        JsonObject projected = Project(
            "{\"status\":\"completed\",\"cause\":\"seen\",\"observed\":{\"controlCount\":3},\"observedLimit\":\"projected\"}");

        Assert.That(projected.Select(static fact => fact.Key), Is.EqualTo(new[] { "status", "cause", "view" }));
        Assert.That((string?)projected["status"], Is.EqualTo("completed"));
        Assert.That((string?)projected["cause"], Is.EqualTo("seen"));
    }

    // BAXY Renew cu (C11): a grid item says what the application calls it (Excel's «1» is the header of row 1).
    [Test]
    public void AGridItemSaysWhatTheApplicationCallsIt()
    {
        JsonObject projected = Project("{\"status\":\"completed\"}", Look.Replace(
            "{\"i\":1,\"kind\":\"Button\",\"name\":\"Enviar\",\"state\":\"\",\"value\":null}",
            "{\"i\":1,\"kind\":\"DataItem\",\"name\":\"1\",\"state\":\"\",\"value\":null,\"itemType\":\"Encabezado de fila\"}"));

        Assert.That((string?)projected["view"], Does.Contain("[1] DataItem «1» (tipo: Encabezado de fila)\n"));
    }

    private static JsonObject Project(string facts, string lookJson = Look)
    {
        using JsonDocument look = JsonDocument.Parse(lookJson);
        Assert.That(ScreenViewProjection.TryCreate(facts, look.RootElement, out string projected), Is.True);
        return JsonNode.Parse(projected) as JsonObject ?? throw new AssertionException("the view is not an object");
    }
}
