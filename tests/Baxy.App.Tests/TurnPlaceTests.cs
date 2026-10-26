using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The place this turn's app.open asked for (src/Baxy.App/TurnPlace.cs), which a look at that application's window
/// compares with the place in sight (ScreenViewProjection, aid asked_place). Práctica e2e E014.
/// </summary>
[TestFixture]
public sealed class TurnPlaceTests
{
    [Test]
    public void ACompletedAppOpenWithAPlaceIsTheTurnsAskedPlace()
    {
        var turn = new TurnPlace();

        turn.Ran("app.open", Open("Configuración", "sound"), "completed");

        Assert.That(turn.Asked, Is.EqualTo(("Configuración", "sound")));
    }

    // Nothing asked: an app.open with no place, one that did not complete, another operation.
    [TestCase("app.open", null, "completed")]
    [TestCase("app.open", "sound", "failed")]
    [TestCase("app.open", "sound", "needs_confirmation")]
    [TestCase("window.focus", "sound", "completed")]
    public void OtherwiseNothingIsAsked(string operation, string? place, string status)
    {
        var turn = new TurnPlace();

        turn.Ran(operation, Open("Configuración", place), status);

        Assert.That(turn.Asked, Is.Null);
    }

    // The last opening holds: a later app.open with no place asks none; a look in between changes nothing.
    [Test]
    public void TheLastOpeningHolds()
    {
        var turn = new TurnPlace();
        turn.Ran("app.open", Open("Steam", "library"), "completed");
        turn.Ran("input.visible.controls", new JsonObject { ["application"] = "Steam" }, "completed");
        (string, string)? kept = turn.Asked;

        turn.Ran("app.open", Open("Paint", null), "completed");

        Assert.Multiple(() =>
        {
            Assert.That(kept, Is.EqualTo(("Steam", "library")));
            Assert.That(turn.Asked, Is.Null);
        });
    }

    [Test]
    public void ANewTurnAsksNothing()
    {
        var turn = new TurnPlace();
        turn.Ran("app.open", Open("Configuración", "sound"), "completed");

        turn.NewTurn();

        Assert.That(turn.Asked, Is.Null);
    }

    private static JsonObject Open(string appId, string? place)
    {
        var call = new JsonObject { ["appId"] = appId };
        if (place is not null)
            call["place"] = place;
        return call;
    }
}
