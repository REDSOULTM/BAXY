using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// INS2 (MIN1): BAXY with no model of its own took the 4 GB PC's RAM in 9-17 s, before any breakdown could be shown, and
/// said «Listo» with no mind. Before anything starts, a PC with less RAM than BAXY takes even with a model by API is told
/// so with its figures; the machines that work today are not asked anything.
/// </summary>
[TestFixture]
public sealed class StartupRamTests
{
    [TestCase(4096L, true, TestName = "HP 15, 4 GB")]
    [TestCase(6144L, false, TestName = "6 GB: justo, no se frena")]
    [TestCase(8192L, false, TestName = "8 GB")]
    [TestCase(16384L, false, TestName = "Notebook y Radeon, 16 GB")]
    [TestCase(32768L, false, TestName = "Este PC, 32 GB")]
    [TestCase(null, false, TestName = "RAM sin leer")]
    public void Only_a_pc_where_baxy_does_not_fit_even_by_api_is_asked(long? installedMib, bool asked) =>
        Assert.That(StartupRam.TooLittle(installedMib), Is.EqualTo(asked));

    [TestCase(false, "4 GB", "0,4", "6 GB", "API", "¿Abrirme igual?")]
    [TestCase(true, "4 GB", "0.4", "6 GB", "API", "Open me anyway?")]
    public void The_question_says_the_pc_figures_what_it_needs_and_that_another_model_does_not_help(
        bool english, string installed, string free, string need, string api, string question)
    {
        string said = StartupRam.Said(english, 4096, 454);

        Assert.That(said, Does.Contain(installed).And.Contain(free).And.Contain(need).And.Contain(api).And.EndWith(question));
        Assert.That(said, Does.Not.Contain(english ? "Settings" : "Ajustes"));
    }

    [Test]
    public void The_app_and_the_installer_hold_back_at_one_figure() =>
        Assert.That(BaxyRamNeed.ByApiMib, Is.EqualTo(4096 + 777 + 1222));
}
