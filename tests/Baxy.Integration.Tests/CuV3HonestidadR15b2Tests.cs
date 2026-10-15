using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Pasada r15b2, v3-22 t3 «¿cuáles tienen impacto alto?»: the decider looked at the Task Manager with
/// input.visible.controls; the window runs as administrator and the read listed only its frame (no text). The mind now
/// tells that limit from its floor data («No pude hacerlo en «Administrador de tareas»: esa aplicación corre como
/// administrador…») instead of a drafted definition; the App's twin publishes it over that successful read, while a
/// failure told over a read that did see the window is still a reversed result.
/// </summary>
[TestFixture]
public sealed class CuV3HonestidadR15b2Tests
{
    // compose_audit.jsonl of v2-v3-22, turn 3 (trimmed rectangles of the frame panes).
    private const string ElevatedRead =
        """{"kind":"operation","operation":"input.visible.controls","polarity":"success","verified":true,"succeeded":true,"observed":{"version":2,"ok":true,"error":"","window":{"title":"Administrador de tareas","process":"Taskmgr","requested":true,"root":13766422,"others":[],"foreground":true,"elevated":true,"focused":{"kind":"Pane","name":"TaskManagerMain","nameSource":"","i":3}},"controls":[{"i":0,"kind":"Pane","name":"DesktopWindowXamlSource","state":"","zone":"C"},{"i":1,"kind":"Pane","name":"Filter Control Glass Window","state":"","zone":"T"},{"i":2,"kind":"Pane","name":"Glass Window","state":"","zone":"TR"},{"i":3,"kind":"Pane","name":"TaskManagerMain","state":"focused","zone":"C"},{"i":4,"kind":"TitleBar","name":"Administrador de tareas","state":"","zone":"TL"}],"controlCount":5,"clientProviders":true,"authority":"windows_uia_snapshot_ocr_zones"}}""";

    private const string Told =
        "No pude hacerlo en «Administrador de tareas»: esa aplicación corre como administrador y Windows no deja que otra aplicación la controle.";

    [Test]
    public void V3_22_TheLimitOfAnElevatedWindowIsPublishedOverItsRead()
    {
        var draft = new UserMessageDraft(ElevatedRead, "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(Told, draft, "¿cuáles tienen impacto alto?"), Is.Null);
    }

    [Test]
    public void ContracaseAFailureToldOverAWindowThatWasReadIsStillReversed()
    {
        string read = ElevatedRead.Replace("\"elevated\":true,", "", StringComparison.Ordinal)
            .Replace("\"controlCount\":5,", "\"controlCount\":5,\"text\":{\"C\":[\"Steam\",\"Alto\"]},", StringComparison.Ordinal);
        var draft = new UserMessageDraft(read, "status", null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude leer la lista del Administrador de tareas.", draft, "¿cuáles tienen impacto alto?"),
            Is.EqualTo("reversed_result"));
    }
}
