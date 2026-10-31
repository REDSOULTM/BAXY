using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Banco ciego c3 (2026-10-31): 12 of the candidate's 16 looks that waited for a label waited the whole 24 s for one the
/// window never showed («Opciones», «Configuración», «Guardar como»), with the window still and the person hearing
/// nothing. A window whose controls stay the same look after look is not loading anything: the wait ends there. One
/// that still changes, or shows nothing yet, is waited on as before.
/// </summary>
[TestFixture]
public sealed class LabelWaitSettledTests
{
    [Test]
    public void AWindowThatShowsTheSameControlsLookAfterLookHasSettled()
    {
        var wait = new LabelWaitSettle();
        string[] names = ["Archivo", "Editar", "Ver", "Herramientas"];

        Assert.Multiple(() =>
        {
            Assert.That(wait.Look(names), Is.False);
            Assert.That(wait.Look(names), Is.False);
            Assert.That(wait.Look([.. names]), Is.True);
        });
    }

    [Test]
    public void AWindowThatStillChangesIsWaitedOn()
    {
        var wait = new LabelWaitSettle();

        Assert.Multiple(() =>
        {
            Assert.That(wait.Look(["Cargando"]), Is.False);
            Assert.That(wait.Look(["Cargando"]), Is.False);
            Assert.That(wait.Look(["Biblioteca", "Tienda"]), Is.False);
            Assert.That(wait.Look(["Biblioteca", "Tienda"]), Is.False);
            Assert.That(wait.Look(["Biblioteca", "Tienda", "Amigos"]), Is.False);
        });
    }

    [Test]
    public void AWindowThatShowsNothingYetIsNotSettled()
    {
        var wait = new LabelWaitSettle();

        Assert.Multiple(() =>
        {
            Assert.That(wait.Look([]), Is.False);
            Assert.That(wait.Look([]), Is.False);
            Assert.That(wait.Look([]), Is.False);
            Assert.That(wait.Look([]), Is.False);
        });
    }
}
