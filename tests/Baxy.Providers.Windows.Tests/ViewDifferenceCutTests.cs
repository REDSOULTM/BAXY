using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (w8): the difference between the view before an act and the one after it (ViewDifference, a pure
/// function: no window is read) when a view was cut at its cap. A click that adds controls to a crowded window pushes
/// others past the cap, and those were said «gone»; with nothing listed changed, the window was said «same».
/// </summary>
[TestFixture]
public sealed class ViewDifferenceCutTests
{
    private static List<WindowsVisibleControlAdapter.ViewControl> Rows(int from, int count) =>
        [.. Enumerable.Range(from, count).Select(static i =>
            new WindowsVisibleControlAdapter.ViewControl { Index = i, Id = "1." + i, Kind = "ListItem", Name = "Fila " + i })];

    [Test]
    public void ACutViewSaysNoControlGoneAndNoWindowTheSame()
    {
        List<WindowsVisibleControlAdapter.ViewControl> before = Rows(0, 5);
        List<WindowsVisibleControlAdapter.ViewControl> after = Rows(0, 3);

        JsonElement cut = WindowsVisibleControlAdapter.ViewDifference(before, "Lista", after, [], "Lista", cut: true);
        JsonElement whole = WindowsVisibleControlAdapter.ViewDifference(before, "Lista", after, [], "Lista");
        JsonElement cutSame = WindowsVisibleControlAdapter.ViewDifference(before, "Lista", before, [], "Lista", cut: true);

        Assert.Multiple(() =>
        {
            Assert.That(cut.TryGetProperty("gone", out _), Is.False, "pushed past the cap, never gone");
            Assert.That(cut.GetProperty("cut").GetBoolean(), Is.True);
            Assert.That(whole.GetProperty("gone").GetArrayLength(), Is.EqualTo(2), "a whole view still says gone");
            Assert.That(cutSame.TryGetProperty("same", out _), Is.False);
            Assert.That(cutSame.GetProperty("sameListed").GetBoolean(), Is.True);
        });
    }

    // Holdout v5 V5E029 (s1): a click on the mode's label only took the focus ring off the display, and the difference
    // said «changed: [38] Text «Se muestra 0»», with nothing of what changed. It says the state as it was and as it is,
    // and that the focus is the only difference.
    [Test]
    public void ADifferenceOfTheFocusAloneSaysSoAndWhatChanged()
    {
        WindowsVisibleControlAdapter.ViewControl Display(string state) =>
            new() { Index = 38, Id = "1.38", Kind = "Text", Name = "Se muestra 0", State = state };
        WindowsVisibleControlAdapter.ViewControl Bold(string state) =>
            new() { Index = 39, Id = "1.39", Kind = "CheckBox", Name = "Negrita", State = state };

        JsonElement focus = WindowsVisibleControlAdapter.ViewDifference(
            [Display("focused"), Bold("off")], "Calculadora", [Display(""), Bold("off focused")], [], "Calculadora");
        JsonElement toggled = WindowsVisibleControlAdapter.ViewDifference(
            [Display("focused"), Bold("off")], "Calculadora", [Display(""), Bold("on focused")], [], "Calculadora");
        JsonElement cut = WindowsVisibleControlAdapter.ViewDifference(
            [Display("focused")], "Calculadora", [Display("")], [], "Calculadora", cut: true);

        Assert.Multiple(() =>
        {
            Assert.That(focus.GetProperty("focusOnly").GetBoolean(), Is.True);
            Assert.That(focus.GetProperty("changed").EnumerateArray().Select(entry => entry.GetString()), Is.EqualTo(new[]
            {
                "[38] Text «Se muestra 0» focused → (none)", "[39] CheckBox «Negrita» off → off focused",
            }));
            Assert.That(toggled.TryGetProperty("focusOnly", out _), Is.False, "a state beside the focus changed");
            Assert.That(cut.TryGetProperty("focusOnly", out _), Is.False, "what a cut view did not list is not known");
        });
    }
}
