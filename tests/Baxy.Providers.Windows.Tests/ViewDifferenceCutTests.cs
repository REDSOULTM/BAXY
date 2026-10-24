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
}
