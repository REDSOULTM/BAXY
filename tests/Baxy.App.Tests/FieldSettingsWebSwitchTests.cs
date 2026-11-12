using System.IO;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// PRV1 (revisión de privacidad 2026-11-09, PRIV-07): «Búsqueda web» switched off refused the web search and the pages
/// BAXY reads or downloads, and nothing else: the video BAXY picks from a search of its own and the game's title it
/// looks up in the store's public search went out all the same, under a switch whose text says «sale la búsqueda».
/// The switch covers every call by which BAXY itself asks a service for what the person asked (FieldSettings.AsksTheWeb).
/// </summary>
[TestFixture]
public sealed class FieldSettingsWebSwitchTests
{
    // The calls the catalog says go out that are not BAXY asking the web for what the person asked, each with why
    // «Búsqueda web» leaves it alone. A call that goes out and is in neither list fails here: it has to be decided.
    private static readonly Dictionary<string, string> NotASearchOfBaxysOwn = new(StringComparer.Ordinal)
    {
        ["baxy.update"] = "BAXY's own update, asked for by name, with its own switch for the notice",
        ["browser.navigate"] = "a page opened in the person's browser",
        ["browser.navigate.named"] = "a page opened in a browser the person named",
        ["game.store.search"] = "the store's own search, opened in the person's game client",
        ["media.play.exact"] = "played in the person's own music session",
        ["media.play.query"] = "played in the person's own music session",
        ["network.ping"] = "an echo to a host: no search (NetworkEgress weighs its host)",
        ["peripheral.print"] = "a printer, maybe on the person's network",
        ["shell.command.run"] = "the person's command",
        ["streaming.navigate"] = "a page of the person's own streaming session",
        ["streaming.play.named"] = "played in the person's own streaming session",
        ["weather.current"] = "has its own switch, «Clima»",
    };

    private string _root = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-field-settings-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(_root, recursive: true);

    [TestCase("web.search", "{\"query\":\"pan amasado\"}")]
    [TestCase("web.fetch", "{\"url\":\"https://ejemplo.example/\"}")]
    [TestCase("web.download", "{\"url\":\"https://ejemplo.example/a.pdf\"}")]
    [TestCase("media.play.youtube", "{\"query\":\"lofi\"}")]
    [TestCase("game.store.page", "{\"title\":\"Aventura de prueba\"}")]
    [TestCase("game.install.named", "{\"title\":\"Aventura de prueba\"}")]
    public void WithTheSwitchOffNoCallByWhichBaxyAsksTheWebRuns(string operation, string arguments)
    {
        var settings = new FieldSettings(_root);
        JsonObject given = (JsonObject)JsonNode.Parse(arguments)!;

        Assert.That(settings.Refusal(operation, given), Is.Null, "refused with the switch on");

        settings.ApplyGeneral(new JsonObject { ["web"] = false });

        Assert.That(settings.Refusal(operation, given), Is.EqualTo("web_disabled_by_owner"));
    }

    [TestCase("browser.navigate", "{\"url\":\"https://ejemplo.example/\"}")]
    [TestCase("media.play.query", "{\"provider\":\"spotify\",\"query\":\"lofi\"}")]
    [TestCase("weather.current", "{}")]
    [TestCase("network.ping", "{\"host\":\"192.168.1.1\"}")]
    public void WhatThePersonsOwnProgramsOpenOrAnotherSwitchRulesIsLeftAlone(string operation, string arguments)
    {
        var settings = new FieldSettings(_root);
        settings.ApplyGeneral(new JsonObject { ["web"] = false });

        Assert.That(settings.Refusal(operation, (JsonObject)JsonNode.Parse(arguments)!), Is.Null);
    }

    // SIS1 (REV10 F3): a call the catalog does not mark as going out can still go out by an argument. app.open of a
    // place that takes a game, with a game's title, looks the title up in its catalog's public search (AppOpenHandler,
    // SteamLocalAdapter.PageTitleAsync). Every such route the data declare (an application, a place whose slot is a
    // game, a catalog with a title search) is refused with the switch off; a catalog number is no search.
    [Test]
    public void EveryPlaceWhoseValueTheDataLookUpInAPublicSearchIsCoveredByTheSwitch()
    {
        (string App, string Place)[] routes = [.. ApplicationPlaces.PlaceNames
            .SelectMany(static place => ApplicationPlaces.ApplicationsWith(place).Select(app => (app, place)))
            .Where(static route => ApplicationPlaces.GameCatalogOf(route.app, route.place) is { } catalog
                && ApplicationPlaces.TitleSearchOf(catalog, "Aventura de prueba") is not null)];
        var settings = new FieldSettings(_root);
        JsonObject Call((string App, string Place) route, string value) =>
            new() { ["appId"] = route.App, ["place"] = route.Place, ["placeValue"] = value };

        Assert.That(routes, Is.Not.Empty, "the data declare no title search: this test reads nothing");
        Assert.That(routes.Select(route => settings.Refusal("app.open", Call(route, "Aventura de prueba"))),
            Has.All.Null, "refused with the switch on");

        settings.ApplyGeneral(new JsonObject { ["web"] = false });

        Assert.Multiple(() =>
        {
            foreach ((string App, string Place) route in routes)
            {
                Assert.That(settings.Refusal("app.open", Call(route, "Aventura de prueba")),
                    Is.EqualTo("web_disabled_by_owner"), $"{route.App} {route.Place} with a title");
                Assert.That(settings.Refusal("app.open", Call(route, "413150")), Is.Null,
                    $"{route.App} {route.Place} with its catalog number: no search");
                Assert.That(settings.Refusal("app.open", new JsonObject { ["appId"] = route.App }), Is.Null,
                    $"{route.App} opened alone");
            }
        });
    }

    [Test]
    public void EveryCallTheCatalogSaysGoesOutIsCoveredByTheSwitchOrNamedWithItsReason()
    {
        string[] goingOut = [.. ProductCatalog.ToolDescriptors
            .Where(static descriptor => descriptor.Effects.Any(static effect => effect.Kind == OperationEffects.Network))
            .Select(static descriptor => descriptor.Name)];

        Assert.Multiple(() =>
        {
            Assert.That(goingOut.Where(static name => !FieldSettings.AsksTheWeb.Contains(name)
                && !NotASearchOfBaxysOwn.ContainsKey(name)), Is.Empty, "a call that goes out and nobody decided");
            Assert.That(FieldSettings.AsksTheWeb.Where(NotASearchOfBaxysOwn.ContainsKey), Is.Empty);
            Assert.That(FieldSettings.AsksTheWeb.Where(static name => !ProductCatalog.TryGet(name, out _)), Is.Empty,
                "a call the switch names is not in the catalog");
        });
    }
}
