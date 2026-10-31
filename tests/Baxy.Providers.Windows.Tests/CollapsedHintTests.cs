using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C11): Excel in a normal window folds the Font group into a collapsed «Fuente» entry and a click on
/// «Negrita» by its label found nothing. The refusal lists the collapsed entries of the last look, by index and name.
/// </summary>
[TestFixture]
public sealed class CollapsedHintTests
{
    private static WindowsVisibleControlAdapter.ViewControl Control(int index, string kind, string name, string state) =>
        new() { Index = index, Kind = kind, Name = name, State = state };

    [Test]
    public void TheCollapsedEntriesOfTheLastLookAreListed()
    {
        JsonElement? hint = WindowsVisibleControlAdapter.NotFoundHint(
        [
            Control(29, "MenuItem", "Portapapeles", "collapsed"),
            Control(30, "MenuItem", "Fuente", "collapsed"),
            Control(31, "Button", "Guardar", ""),
            Control(41, "ComboBox", "Cuadro de nombres", "collapsed"),
            Control(60, "DataItem", "A", "collapsed"),
        ], "Negrita", collapsed: true, closest: true);

        Assert.Multiple(() =>
        {
            Assert.That(hint!.Value.GetProperty("collapsed").EnumerateArray().Select(entry => entry.GetString()),
                Is.EqualTo(new[] { "[29] MenuItem «Portapapeles»", "[30] MenuItem «Fuente»", "[41] ComboBox «Cuadro de nombres»" }));
            Assert.That(hint.Value.GetProperty("next").GetString(), Does.Contain("manner open"));
        });
    }

    // Contracase: a look with nothing collapsed adds nothing (the refusal reads as before).
    [Test]
    public void ALookWithNothingCollapsedAddsNothing()
    {
        Assert.That(WindowsVisibleControlAdapter.NotFoundHint([Control(0, "Button", "Aceptar", "")], "Negrita", true, true),
            Is.Null);
    }

    // Ajuste c3 (E011, séptima vuelta): on a «Guardar como», «prueba c3 guardado.txt» clicked as if it were a button. Nothing
    // is pressed, and the refusal names the controls of the last look closest to the label, by index.
    [Test]
    public void TheControlsClosestToALabelNoControlHasAreListedByIndex()
    {
        WindowsVisibleControlAdapter.ViewControl[] look =
        [
            Control(11, "TreeItem", "Escritorio", "selected"),
            Control(14, "ListItem", "prueba c3.txt", ""),
            Control(16, "ListItem", "carta", ""),
            Control(30, "Edit", "Nombre de archivo:", ""),
            Control(37, "Button", "Guardar", ""),
        ];

        JsonElement? hint = WindowsVisibleControlAdapter.NotFoundHint(look, "prueba c3 guardado.txt", true, true);
        JsonElement? none = WindowsVisibleControlAdapter.NotFoundHint(look, "Editar", true, true);
        JsonElement? off = WindowsVisibleControlAdapter.NotFoundHint(look, "prueba c3 guardado.txt", true, false);

        Assert.Multiple(() =>
        {
            Assert.That(hint!.Value.GetProperty("closest").EnumerateArray().Select(entry => entry.GetString()),
                Is.EqualTo(new[] { "[14] ListItem «prueba c3.txt»" }));
            Assert.That(hint.Value.TryGetProperty("collapsed", out _), Is.False);
            Assert.That(hint.Value.GetProperty("next").GetString(), Does.Contain("closest"));
            Assert.That(none, Is.Null, "nothing alike: the refusal reads as before");
            Assert.That(off, Is.Null, "the aid off");
        });
    }
}
