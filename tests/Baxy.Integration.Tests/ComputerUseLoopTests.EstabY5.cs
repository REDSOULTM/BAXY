using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización y5 (banco h1, «andá a Descargas y después a Imágenes»): «Imágenes» of Explorer's navigation tree was
/// seen and pressed, it stayed chosen and the folder stayed «Downloads»; the mind said so (click_without_effect) and the
/// stop said «no vi en la pantalla un control con el que seguir». The stop is the pressed control that left the window
/// where it was; a «none» with no cause of its own is still the screen without a step.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private static JsonObject ExplorerAtDownloads() => Window("Downloads - Explorador de archivos", "explorer", 51508, true,
        [Control(0, "TreeItem", "Downloads"), Control(1, "TreeItem", "Imágenes"), Control(2, "ListItem", "Intelectra_Galactico_Agil_18s")]);

    [TestCase("click_without_effect", "computer_use_click_without_effect")]
    [TestCase("", "computer_use_no_step_visible")]
    public async Task APressedControlThatLeftTheWindowWhereItWasIsTheStopNotAMissingControl(string code, string stoppedBy)
    {
        var harness = new Harness
        {
            Screen = _ => ExplorerAtDownloads(),
            Mind = _ => new MindComputerUseStep("none", new JsonObject(), "el clic en «Imágenes» no tuvo efecto", code),
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a imagenes",
            ["application"] = "Explorador de archivos",
            ["successCheck"] = "control:imagenes:current|title:imagenes",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en el Explorador de archivos andá a Imágenes", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(result.Response!.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo(stoppedBy));
            Assert.That((JsonObject)OperationFloor.ComputerUseData["causes"]!, Does.ContainKey(stoppedBy), "the floor says it");
        });
    }
}
