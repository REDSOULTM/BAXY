using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M113 (DEV-F v4d w14-t1 «open Obsidian porfa…»): the Start catalog read found the application absent, the mind
/// composed «No se pudo abrir Obsidian porque no aparece en el catálogo de inicio de Windows.» and the shell refused it
/// as reversed_result, so the turn ended with no final. The absence read is told in the ways people tell it; an
/// opening or a separate failure stays refused. The phrasings are our own.
/// </summary>
[TestFixture]
public sealed class M113AusenciaContadaTests
{
    private const string Absent =
        """{"kind":"operation","operation":"app.installed","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"requestedName":"Krita","installed":false,"authority":"windows_start_catalog_snapshot"}}""";

    [TestCase("No se pudo abrir Krita porque no aparece en el catálogo de inicio de Windows.")]
    [TestCase("No puedo abrir Krita porque no está instalada en este equipo.")]
    [TestCase("No puedo abrir Krita porque la aplicación no figura en el catálogo de inicio de Windows.")]
    [TestCase("Krita no está instalada en este equipo.")]
    [TestCase("I couldn't open Krita because it isn't installed on this PC.")]
    [TestCase("I can't open Krita because it doesn't appear in the Windows Start catalog.")]
    [TestCase("Krita is not installed on this computer.")]
    public void TheAbsenceReadIsPublished(string reply)
    {
        var draft = new UserMessageDraft(Absent, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "abre Krita"), Is.Null);
    }

    [TestCase("Abrí Krita, pero no aparece en el catálogo de inicio de Windows.")]
    [TestCase("No se pudo abrir Krita porque el disco está lleno.")]
    [TestCase("I tried to open Krita but it failed.")]
    public void AnOpeningOrAnotherFailureIsStillRefused(string reply)
    {
        var draft = new UserMessageDraft(Absent, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "abre Krita"), Is.EqualTo("reversed_result"));
    }
}
