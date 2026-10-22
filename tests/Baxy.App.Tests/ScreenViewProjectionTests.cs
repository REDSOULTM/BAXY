using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The view the model reads of a look (src/Baxy.App/ScreenViewProjection.cs): what the reader marked as chosen is said
/// first, apart from the reading order.
/// </summary>
[TestFixture]
public sealed class ScreenViewProjectionTests
{
    // Sonda F019: Steam on its library, the store tab first in the reading order; the model said «quedó en la tienda».
    private const string Steam =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"Steam\",\"process\":\"steamwebhelper\",\"hwnd\":77,\"foreground\":true}," +
        "\"controls\":[" +
        "{\"i\":1,\"kind\":\"TabItem\",\"name\":\"Tienda\",\"state\":\"\",\"value\":null}," +
        "{\"i\":2,\"kind\":\"TabItem\",\"name\":\"Biblioteca\",\"state\":\"selected\",\"value\":null}," +
        "{\"i\":3,\"kind\":\"CheckBox\",\"name\":\"Sólo instalados\",\"state\":\"on focused\",\"value\":null}," +
        "{\"i\":4,\"kind\":\"Button\",\"name\":\"Menú\",\"state\":\"collapsed\",\"value\":null}]," +
        "\"controlCount\":4,\"textAuthority\":\"not_read\",\"authority\":\"uia\"}";

    [Test]
    public void WhatIsSelectedOrOnIsSaidBeforeTheControls()
    {
        string view = View(Steam);

        Assert.That(view, Does.StartWith(
            "Ventana «Steam» (steamwebhelper, window 77), al frente\n" +
            "Seleccionados o activados: [2] TabItem «Biblioteca» | [3] CheckBox «Sólo instalados»\n" +
            "Controles:\n" +
            "[1] TabItem «Tienda»\n" +
            "[2] TabItem «Biblioteca» (selected)\n"));
    }

    [Test]
    public void NothingChosenSaysNoLine()
    {
        string view = View(Steam.Replace("\"selected\"", "\"\"").Replace("\"on focused\"", "\"off\""));

        Assert.That(view, Does.Not.Contain("Seleccionados"));
    }

    private static string View(string lookJson)
    {
        using JsonDocument look = JsonDocument.Parse(lookJson);
        Assert.That(ScreenViewProjection.TryCreate("{\"status\":\"completed\"}", look.RootElement, out string projected), Is.True);
        return (string?)JsonNode.Parse(projected)?["view"] ?? throw new AssertionException("the projection has no view");
    }
}
