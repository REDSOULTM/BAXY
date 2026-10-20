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
        JsonElement? hint = WindowsVisibleControlAdapter.CollapsedHint(
        [
            Control(29, "MenuItem", "Portapapeles", "collapsed"),
            Control(30, "MenuItem", "Fuente", "collapsed"),
            Control(31, "Button", "Guardar", ""),
            Control(41, "ComboBox", "Cuadro de nombres", "collapsed"),
            Control(60, "DataItem", "A", "collapsed"),
        ]);

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
        Assert.That(WindowsVisibleControlAdapter.CollapsedHint([Control(0, "Button", "Aceptar", "")]), Is.Null);
    }
}
