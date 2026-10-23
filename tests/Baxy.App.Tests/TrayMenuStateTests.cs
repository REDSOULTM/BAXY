using Baxy.App.Presentation;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>The tray menu's first line (TrayMenu.StateLabel): a start that failed is never shown as still starting.</summary>
[TestFixture]
public sealed class TrayMenuStateTests
{
    [TestCase(false, false, "Arrancando")]
    [TestCase(false, true, "No disponible")]
    [TestCase(true, true, "Activo · responde a «BAXY»")]
    public void TheMenuSaysWhetherBaxyIsStartingOrCouldNotStart(bool ready, bool failed, string said) =>
        Assert.That(TrayMenu.StateLabel(new TrayMenu.State(Listening: true, MicAvailable: true, Powered: true, ready, failed)),
            Is.EqualTo(said));
}
