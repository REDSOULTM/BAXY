using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo H2 (tandas redpc fin1/fin2): what the computer does not have is said as such. A typed operation that answers
/// one of a device's «absent» codes (data «computerUse.limits.devices») is told by the App's floor with that device's
/// cause, the same words as the mind's (tests/test_estab_h2_dispositivos.py); any other failure keeps its own floor.
/// </summary>
[TestFixture]
public sealed class EstabH2DispositivosTests
{
    // The situation of t1-c11 t1 (tandas_fin2_redpc t1 compose_audit), as it reached the writer (parsed, as the App
    // reads it).
    private static JsonObject Failed(string operation, string error, JsonObject attempted, bool uncertain = false) =>
        (JsonObject)JsonNode.Parse(Built(operation, error, attempted, uncertain).ToJsonString())!;

    private static JsonObject Built(string operation, string error, JsonObject attempted, bool uncertain) => new()
    {
        ["kind"] = "failure",
        ["polarity"] = "failure",
        ["cause"] = "mission_failed",
        ["stepCount"] = 0,
        ["steps"] = new JsonArray(),
        ["reason"] = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = operation,
            ["polarity"] = "failure",
            ["verified"] = false,
            ["succeeded"] = false,
            ["error"] = error,
            ["attempted"] = attempted,
            ["effectUncertain"] = uncertain ? true : null,
            ["cause"] = uncertain ? "external_effect_ambiguous" : null,
        },
    };

    [TestCase("bluetooth.radio.set", "bluetooth_radio_not_found", "Este equipo no tiene Bluetooth.", "This computer has no Bluetooth.")]
    [TestCase("wifi.radio.set", "wifi_radio_not_found", "Este equipo no tiene adaptador Wi-Fi.", "This computer has no Wi-Fi adapter.")]
    [TestCase("system.settings.set", "brightness_not_supported",
        "Este equipo no deja cambiar el brillo desde Windows (el monitor no lo expone).",
        "This computer doesn't let Windows change the brightness (the monitor doesn't expose it).")]
    public void AnAbsentDeviceIsSaidAsTheComputersLimit(string operation, string error, string spanish, string english)
    {
        JsonObject situation = Failed(operation, error, new JsonObject { ["state"] = true });
        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.FailureSentence(situation, english: false), Is.EqualTo(spanish));
            Assert.That(OperationFloor.FailureSentence(situation, english: true), Is.EqualTo(english));
        });
    }

    [Test]
    public void ABrightnessLeftUnconfirmedKeepsItsOwnFloor()
    {
        // Contracase (the notebook's monitor exposes its brightness): a set whose read after differs is no limit of the
        // computer; it stays the floor's «intenté…, pero no pude confirmar» (tandas t4-c04 before H2).
        JsonObject situation = Failed(
            "system.settings.set", "brightness_postread_failed",
            new JsonObject { ["setting"] = "brightness", ["value"] = 40 }, uncertain: true);
        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.FailureSentence(situation, english: false), Is.Null);
            Assert.That(OperationFloor.Final(situation, english: false), Does.StartWith("Intenté"));
        });
    }
}

/// <summary>Encargo H2: a device whose read needs arguments («readArguments» of the data) is read with them.</summary>
public sealed partial class ComputerUseLoopTests
{
    [Test]
    public async Task ABrightnessPlaceReadsTheMonitorWithItsSetting()
    {
        // «readArguments» of the data: the brightness's read needs its «setting»; an absent monitor stops the place.
        var harness = new Harness
        {
            Screen = _ => Window("Configuración", "SystemSettings", 60, true,
                [Control(0, "Text", "Pantalla")]),
            Receipt = (operation, _) => operation == "system.settings.status"
                ? new JsonObject { ["failWith"] = "brightness_not_supported" }
                : new JsonObject { ["surfaceChanged"] = true },
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a brillo",
            ["application"] = "Configuración",
            ["steps"] = new JsonArray { new JsonObject { ["goal"] = "ir a brillo", ["application"] = "Configuración", ["requires"] = "brightness" } },
        };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Configuración andá a brillo", arguments), arguments, CancellationToken.None);
        (string Operation, JsonObject Arguments) read = harness.Acts.Single();
        Assert.Multiple(() =>
        {
            Assert.That(read.Operation, Is.EqualTo("system.settings.status"));
            Assert.That((string?)read.Arguments["setting"], Is.EqualTo("brightness"));
            Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_limit_device"));
            Assert.That((string?)Observed(result)["absentDevice"], Is.EqualTo("brightness"));
        });
    }
}
