using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Falsos éxitos de la pasada v3 ronda 7 (2026-10-08), la parte del App. v3-43: «luego a opciones de energía y dime qué
/// plan está activo» llegó con la página aún «Cargando 0»; el borrador honrado «No pude ver qué plan de energía está activo
/// porque la pantalla estaba cargando» murió como reversed_result y el turno cayó en «Lo hice en la aplicación «Panel de
/// control»», un hecho sin respuesta. Contracasos: negar la llegada sigue invirtiendo el resultado, y una misión sin
/// pregunta no admite «no pude ver».
/// </summary>
[TestFixture]
public sealed class CuV3FalsosR7Tests
{
    private static string Mission(string goal) => new JsonObject
    {
        ["kind"] = "operation",
        ["operation"] = "mission.computer.use",
        ["polarity"] = "success",
        ["verified"] = true,
        ["succeeded"] = true,
        ["observed"] = new JsonObject
        {
            ["goal"] = goal,
            ["application"] = "Panel de control",
            ["reached"] = true,
            ["successCheck"] = "stepDone:input.visible.click:opciones de energia",
            ["stepCount"] = 3,
            ["screen"] = new JsonObject
            {
                ["title"] = "Opciones de energía",
                ["values"] = new JsonArray(new JsonObject { ["name"] = "Cargando", ["value"] = "0" }),
            },
        },
    }.ToJsonString();

    private const string Asked = "hacer clic en opciones de energia; y responder: dime qué plan de energía está activo";
    private const string Request = "luego a opciones de energía y dime qué plan está activo";

    private static string? Rejection(string reply, string goal) =>
        UserMessagePolicy.ModelResponseRejectionReason(reply, new UserMessageDraft(Mission(goal), "status", null), Request);

    [Test]
    public void V3_43_TheUnreadAnswerOfAReachedPlaceIsNoReversedResult()
    {
        Assert.Multiple(() =>
        {
            Assert.That(
                Rejection("No pude ver qué plan de energía está activo porque la pantalla estaba cargando.", Asked),
                Is.Null);
            Assert.That(
                Rejection("Llegué a Opciones de energía, pero no pude leer qué plan está activo: seguía cargando.", Asked),
                Is.Null);
        });
    }

    [Test]
    public void V3_43_DenyingTheArrivalOrNoQuestionStillReverses()
    {
        Assert.Multiple(() =>
        {
            Assert.That(Rejection("No pude llegar a Opciones de energía.", Asked), Is.EqualTo("reversed_result"));
            Assert.That(
                Rejection("No pude ver qué plan de energía está activo porque la pantalla estaba cargando.",
                    "hacer clic en opciones de energia"),
                Is.EqualTo("reversed_result"));
        });
    }
}
