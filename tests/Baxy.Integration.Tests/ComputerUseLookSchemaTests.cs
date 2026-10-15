using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// The look a mission asks for is validated by the kernel against the catalog's schema of
/// <c>input.visible.controls</c>. Live 2026-10-08 (17:57 on): the window a mission is tied to (ventana-misión) added
/// <c>windows</c> and <c>known</c> to every look after the first, the schema did not declare them, and the kernel
/// answered <c>invalid_arguments</c> to each one (2 964 refused looks in one evening, missions ended as
/// <c>computer_use_view_unavailable</c>). These tests build the arguments the mission really sends and check them
/// against the real catalog, never a copy of it.
/// </summary>
public sealed class ComputerUseLookSchemaTests
{
    private static readonly OperationArgumentsSchema LookSchema =
        ProductCatalog.GetRequired("input.visible.controls").ArgumentsSchema;

    [Test]
    public void TheLookOfATiedMissionPassesTheCatalogSchema()
    {
        JsonObject state = TiedState(otherWindows: 3);
        var arguments = new JsonObject
        {
            ["application"] = "Bloc de notas",
            ["includeText"] = true,
            ["limit"] = 60,
            ["processId"] = 4242,
        };

        ComputerUseMissionWindow.AddLookArguments(state, arguments);

        Assert.That(arguments["windows"], Is.Not.Null, "the tied mission names its window");
        Assert.That(arguments["known"], Is.Not.Null, "and the ones it knows are not its");
        Assert.That(Valid(arguments), Is.True, arguments.ToJsonString());
    }

    [Test]
    public void TheLookOfATiedMissionStaysValidWithManyWindowsOfTheProcess()
    {
        // A process that shows many windows (a browser, an office suite): the look still passes the schema.
        JsonObject state = TiedState(otherWindows: 300);
        var arguments = new JsonObject { ["application"] = "Bloc de notas", ["limit"] = 60 };

        ComputerUseMissionWindow.AddLookArguments(state, arguments);

        Assert.That(Valid(arguments), Is.True, arguments.ToJsonString());
    }

    [Test]
    public void TheSchemaStillRefusesAnUndeclaredArgument()
    {
        // Counter-case: declaring the mission's windows does not open the schema to anything else.
        var arguments = new JsonObject { ["application"] = "Bloc de notas", ["windowz"] = new JsonArray(1001) };

        Assert.That(Valid(arguments), Is.False);
    }

    private static JsonObject TiedState(int otherWindows)
    {
        var others = new JsonArray();
        for (int i = 0; i < otherWindows; i++)
            others.Add((long)(2000 + i));
        var state = new JsonObject { ["objective"] = "en el bloc de notas escribí hola" };
        var view = new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["hwnd"] = 1001L,
                ["root"] = 1001L,
                ["title"] = "Sin título - Bloc de notas",
                ["others"] = others,
            },
        };
        ComputerUseMissionWindow.Tie(state, "Bloc de notas", view, ofTheApplication: true, steps: new JsonArray());
        Assert.That(ComputerUseMissionWindow.Tied(state), Is.True, "the first look of the application ties the mission");
        return state;
    }

    private static bool Valid(JsonObject arguments)
    {
        using JsonDocument document = JsonDocument.Parse(arguments.ToJsonString());
        return OperationArgumentValidator.IsValid(document.RootElement, LookSchema);
    }
}
