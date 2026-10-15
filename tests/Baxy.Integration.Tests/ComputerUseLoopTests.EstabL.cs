using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo L de estabilización (límite de partida «lo que depende de hardware que el equipo no tiene», live n5): a place
/// that needs a device (steps[].requires, marked by the mind) is read from the computer before its first look and stops
/// with <c>computer_use_limit_device</c> when the device is absent, after the sub-goals before it; a present device lets
/// it be tried as before. H7 of the review: only a single step the mind marked keeps a single goal's budget; any other
/// «steps» is a chain, however many. The floor says the stop (tests/test_estab_l_limites.py).
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private static JsonObject SettingsAt(string page) => Window("Configuración", "SystemSettings", 60, true,
        [Control(0, "Text", page), Control(1, "ListItem", "Red e Internet"), Control(2, "ListItem", "Wi-Fi"),
         Control(3, "ListItem", "Modo avión")]);

    private static JsonObject N5Arguments() => new()
    {
        ["goal"] = "ir a red e internet; luego ir a wi-fi",
        ["steps"] = new JsonArray
        {
            new JsonObject { ["goal"] = "ir a red e internet", ["application"] = "Configuración",
                ["successCheck"] = "stepDone:input.visible.click:red e internet" },
            new JsonObject { ["goal"] = "ir a wi-fi", ["application"] = "Configuración",
                ["successCheck"] = "stepDone:input.visible.click:wi-fi", ["requires"] = "wifi" },
        },
    };

    private static Harness RadioHarness(bool present) => new()
    {
        Screen = _ => SettingsAt("Red e Internet"),
        Mind = request => Step("input.visible.click",
            new JsonObject { ["label"] = request.Subgoal == 0 ? "Red e Internet" : "Wi-Fi" }),
        Receipt = (operation, _) => operation == "wifi.radio.status"
            ? present ? new JsonObject { ["state"] = true } : new JsonObject { ["failWith"] = "wifi_radio_not_found" }
            : new JsonObject { ["surfaceChanged"] = true },
    };

    [Test]
    public async Task APlaceThatNeedsAnAbsentDeviceStopsBeforeItsFirstLook()
    {
        // n5 on a computer with no Wi-Fi adapter: the radio read answers that there is none.
        Harness harness = RadioHarness(present: false);
        JsonObject arguments = N5Arguments();
        Assert.That(MindPlanBoundary.ArgumentsSatisfyExactSchema(ComputerUseMission.OperationName, arguments), Is.True,
            "the catalog declares the mark");

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Configuración andá a Red e Internet y después a Wi-Fi", arguments),
            arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_limit_device"));
            Assert.That((string?)observed["absentDevice"], Is.EqualTo("wifi"));
            Assert.That((bool?)observed["subgoals"]![0]!["reached"], Is.True);
            Assert.That(harness.Acts.Select(act => act.Operation),
                Is.EqualTo(new[] { "input.visible.click", "wifi.radio.status" }), "the device is read once, nothing pressed after");
            Assert.That(harness.Requests.Select(request => request.Subgoal), Is.All.EqualTo(0));
        });
    }

    [Test]
    public async Task APresentDeviceLetsItsPlaceBeTried()
    {
        // Contracase: the same request on a computer whose radio answers (redpc: «WiFi=On»).
        Harness harness = RadioHarness(present: true);
        JsonObject arguments = N5Arguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Configuración andá a Red e Internet y después a Wi-Fi", arguments),
            arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(observed["stoppedBy"], Is.Null);
            Assert.That(harness.Acts.Count(act => act.Operation == "wifi.radio.status"), Is.EqualTo(1));
        });
    }

    [Test]
    public async Task OnlyTheOneStepTheMindMarkedKeepsASingleGoalsBudget()
    {
        // H7: «en Configuración andá a Wi-Fi» marked as needing the radio comes as one step and is no chain (no
        // «subgoals», the single goal's time); an unmarked «steps» of one item, which the model may send, stays a chain.
        Harness marked = RadioHarness(present: false);
        var single = new JsonObject
        {
            ["goal"] = "ir a wi-fi",
            ["application"] = "Configuración",
            ["steps"] = new JsonArray { new JsonObject { ["goal"] = "ir a wi-fi", ["application"] = "Configuración", ["requires"] = "wifi" } },
        };
        ComputerUseMission.Result stopped = await ComputerUseMission.RunAsync(
            marked.Context(_root), Execution("en Configuración andá a Wi-Fi", single), single, CancellationToken.None);

        Harness unmarked = RadioHarness(present: true);
        var oneStepChain = new JsonObject
        {
            ["goal"] = "ir a red e internet",
            ["steps"] = new JsonArray { new JsonObject { ["goal"] = "ir a red e internet", ["application"] = "Configuración",
                ["successCheck"] = "stepDone:input.visible.click:red e internet" } },
        };
        ComputerUseMission.Result chained = await ComputerUseMission.RunAsync(
            unmarked.Context(_root), Execution("andá a Red e Internet", oneStepChain), oneStepChain, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((string?)Observed(stopped)["stoppedBy"], Is.EqualTo("computer_use_limit_device"));
            Assert.That(Observed(stopped)["subgoals"], Is.Null, "the marked single goal is no chain");
            Assert.That(Observed(chained)["subgoals"], Is.Not.Null, "an unmarked one-step «steps» is still a chain");
        });
    }

    [Test]
    public void EveryDeviceHasItsCauseAndAReadOnlyRead()
    {
        var causes = (JsonObject)OperationFloor.ComputerUseData["causes"]!;
        var devices = (JsonObject)OperationFloor.ComputerUseData["limits"]!["devices"]!;
        Assert.Multiple(() =>
        {
            Assert.That(causes[ComputerUseMission.DeviceStop], Is.Not.Null);
            foreach ((string device, JsonNode? entry) in devices)
            {
                Assert.That(ProductCatalog.GetRequired((string)entry!["read"]!).Risk, Is.EqualTo(OperationRisks.ReadOnly), device);
                Assert.That((JsonArray)entry["absent"]!, Is.Not.Empty, device);
            }
        });
    }
}
