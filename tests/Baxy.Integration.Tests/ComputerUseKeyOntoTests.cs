using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Revisión de V (H1): Enter or space presses what has the keyboard, or, from a field, the result its list holds chosen.
/// Measured in bancoB_c24u c7: the search «Buscar» focused with «cotele» written and the result «Cotele!!!😎, Canal de
/// voz, Choche» selected; Enter there joins the channel, and the key went unmarked, so nobody was asked. The mission
/// marks the name the key lands on («onto») from the view the step was decided on, when it needs the person's word, and
/// RiskPolicy asks about it (RiskPolicyWorldActsTests.A_key_on_what_asks_asks_as_its_click_would).
/// </summary>
[TestFixture]
public sealed class ComputerUseKeyOntoTests
{
    private static JsonObject View(string focusedKind, string focusedName, params (string Kind, string Name, string State)[] controls)
    {
        var list = new JsonArray();
        int index = 0;
        foreach ((string kind, string name, string state) in controls)
            list.Add(new JsonObject { ["i"] = index++, ["kind"] = kind, ["name"] = name, ["state"] = state });
        return new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["title"] = "@Ron92 - Discord",
                ["focused"] = new JsonObject { ["kind"] = focusedKind, ["name"] = focusedName },
            },
            ["controls"] = list,
        };
    }

    private const string Channel = "Cotele!!!😎, Canal de voz, Choche";

    [Test]
    public void EnterInTheSearchLandsOnTheVoiceChannelItHoldsChosen()
    {
        JsonObject view = View("ComboBox", "Buscar", ("ComboBox", "Buscar", "expanded"), ("ListItem", Channel, "selected"));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.KeyLandsOnWhatAsks(view, "enter"), Is.EqualTo(Channel));
            Assert.That(ComputerUseMission.KeyLandsOnWhatAsks(view, "space"), Is.EqualTo(Channel));
            Assert.That(ComputerUseMission.KeyLandsOnWhatAsks(view, "tab"), Is.Null, "another key presses nothing");
        });
    }

    [Test]
    public void AFocusedControlThatAsksIsWhatTheKeyPresses()
    {
        JsonObject view = View("Hyperlink", "Cotele (canal de voz)", ("Hyperlink", "Cotele (canal de voz)", "focused"));
        Assert.That(ComputerUseMission.KeyLandsOnWhatAsks(view, "enter"), Is.EqualTo("Cotele (canal de voz)"));
    }

    // Contracases: a text channel chosen, a voice channel shown but not chosen, the keyboard off any field (the chosen
    // server of a side list is no result of what is being typed), and nothing chosen at all.
    [Test]
    public void WhatDoesNotAskOrIsNotUnderTheKeyIsNotMarked()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.KeyLandsOnWhatAsks(
                View("ComboBox", "Buscar", ("ListItem", "general (canal de texto)", "selected")), "enter"), Is.Null);
            Assert.That(ComputerUseMission.KeyLandsOnWhatAsks(
                View("ComboBox", "Buscar", ("ListItem", Channel, "")), "enter"), Is.Null);
            Assert.That(ComputerUseMission.KeyLandsOnWhatAsks(
                View("Button", "Silenciar", ("ListItem", Channel, "selected")), "enter"), Is.Null);
            Assert.That(ComputerUseMission.KeyLandsOnWhatAsks(View("Edit", "Mensaje @Ron92"), "enter"), Is.Null);
        });
    }
}
