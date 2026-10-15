using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 22 «ventanas-y-recibos-sin-ajenos-ni-falsos» (pasada r18), the App's twin floor. t4-c19: a failed mission told
/// its only quiet read («Busqué las ventanas; hay 3: «Verification page | Example Platform - Opera»…») as done.
/// t4-c07 / t1-c13: «Creé la carpeta» over a folder that already existed (reachedState true).
/// </summary>
[TestFixture]
public sealed class CuR22VentanasYRecibosTests
{
    private static JsonObject Resolve() => new()
    {
        ["kind"] = "operation",
        ["operation"] = "window.resolve",
        ["polarity"] = "success",
        ["verified"] = true,
        ["succeeded"] = true,
        ["readOnly"] = true,
        ["observed"] = new JsonObject
        {
            ["windows"] = new JsonArray(
                new JsonObject { ["title"] = "Verification page | Example Platform - Opera", ["processName"] = "opera" },
                new JsonObject { ["title"] = "Imagen sobre imagen", ["processName"] = "opera" }),
            ["count"] = 2,
        },
    };

    private static JsonObject Mission(string cause, JsonObject? reason, params JsonObject[] steps)
    {
        var mission = new JsonObject
        {
            ["kind"] = cause == "mission_completed" ? "status" : "failure",
            ["polarity"] = cause == "mission_completed" ? "success" : "failure",
            ["cause"] = cause,
            ["stepCount"] = steps.Length,
            ["steps"] = new JsonArray(steps.Select(step => (JsonNode)JsonValue.Create(step.ToJsonString())!).ToArray()),
        };
        if (reason is not null)
            mission["reason"] = reason;
        return mission;
    }

    private static JsonObject SnapMissing() => new()
    {
        ["kind"] = "failure",
        ["polarity"] = "failure",
        ["cause"] = "step_data_missing",
        ["operation"] = "window.snap",
    };

    [Test]
    public void T4C19TheFailedMissionSaysTheEffectNotDoneNeverTheList()
    {
        string? final = OperationFloor.Final(Mission("mission_failed", SnapMissing(), Resolve()), english: false);
        Assert.That(final, Is.EqualTo("No pude colocar la ventana."));
    }

    [Test]
    public void ContracaseACompletedListingStillNamesTheWindows()
    {
        string? final = OperationFloor.Final(Mission("mission_completed", null, Resolve()), english: false);
        Assert.That(final, Does.Contain("Verification page"));
    }

    [Test]
    public void ContracaseADoneEffectAfterAReadIsStillTold()
    {
        var snap = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = "window.snap",
            ["polarity"] = "success",
            ["verified"] = true,
            ["succeeded"] = true,
            ["observed"] = new JsonObject { ["side"] = "left" },
        };
        string? final = OperationFloor.Final(Mission("mission_failed", SnapMissing(), Resolve(), snap), english: false);
        Assert.Multiple(() =>
        {
            Assert.That(final, Does.StartWith("Coloqué la ventana"));
            Assert.That(final, Does.Not.Contain("Verification"));
        });
    }

    private static JsonObject Directory(bool reached) => new()
    {
        ["kind"] = "operation",
        ["operation"] = "filesystem.create.directory",
        ["polarity"] = "success",
        ["verified"] = true,
        ["succeeded"] = true,
        ["observed"] = new JsonObject
        {
            ["name"] = "ramo calculo 2",
            ["kind"] = "directory",
            ["reachedState"] = reached,
            ["folder"] = "desktop",
        },
    };

    [Test]
    public void T4C07AFolderThatExistedIsSaidAsAlreadyThere() =>
        Assert.That(OperationFloor.Final(Directory(true), english: false),
            Is.EqualTo("La carpeta «ramo calculo 2» ya estaba en el Escritorio."));

    [Test]
    public void ContracaseANewFolderIsStillCreated() =>
        Assert.That(OperationFloor.Final(Directory(false), english: false), Is.EqualTo("Creé la carpeta «ramo calculo 2»."));

    // Ronda 22 revisión 2 (r18 t2-c18 «pon el Word y el Edge uno al lado del otro», t3-c15 «poné el word a la
    // izquierda…»): the draft was vetoed (missing_prior_open) and the floor said «Coloqué la ventana: a la
    // izquierda», naming no window. The snapped window is named from the receipt's «window» record; the side follows
    // the clause. The views are the real ones of tandas_r20/t2/compose_audit.jsonl.
    private static JsonObject Snap(string side, string title, string processName, bool? fitsInHalf = null)
    {
        var observed = new JsonObject
        {
            ["side"] = side,
            ["window"] = new JsonObject
            {
                ["windowId"] = "win_2e2a17656b7b80141f4c671a1b641f3b",
                ["processName"] = processName,
                ["title"] = title,
                ["state"] = "normal",
            },
        };
        if (fitsInHalf is bool fits)
            observed["fitsInHalf"] = fits;
        return new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = "window.snap",
            ["polarity"] = "success",
            ["verified"] = true,
            ["succeeded"] = true,
            ["readOnly"] = false,
            ["observed"] = observed,
        };
    }

    [Test]
    public void T2C18BothSnappedWindowsAreNamedWithTheirSide()
    {
        string? final = OperationFloor.Final(
            Mission(
                "mission_completed",
                null,
                Resolve(),
                Snap("left", "Documento1  -  Autorecuperado - Word", "WINWORD"),
                Snap("right", "Encontrar información sobre el dispositivo Windows | Microsoft Support", "msedge")),
            english: false);
        Assert.That(final, Is.EqualTo(
            "Coloqué la ventana «Documento1 - Autorecuperado - Word» a la izquierda y coloqué la ventana "
            + "«Encontrar información sobre el dispositivo Windows | Microsoft Support» a la derecha."));
    }

    [Test]
    public void T3C15ASingleSnapIsNamedAndItsSideHasNoLooseColon()
    {
        Assert.That(
            OperationFloor.Final(Snap("left", "Documento1 - Word", "WINWORD"), english: true),
            Is.EqualTo("I snapped the window «Documento1 - Word» on the left."));
    }

    [Test]
    public void ContracaseAFactThatIsNoPartOfTheClauseKeepsTheDetailSeparator()
    {
        string? final = OperationFloor.Final(Snap("left", "Documento1 - Word", "WINWORD", fitsInHalf: false), english: false);
        Assert.That(final, Is.EqualTo(
            "Coloqué la ventana «Documento1 - Word» a la izquierda: no cabe en media pantalla y ocupa un poco más."));
    }
}
