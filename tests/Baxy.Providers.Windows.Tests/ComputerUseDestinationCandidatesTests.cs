using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Revision 1 of ronda 21 (B4, B5), destino por contenido: the provider's listing of the desktop's windows for a mission
/// with no application. Scripted worker and a desktop named by the test: no window is read, nothing is clicked.
/// </summary>
[TestFixture]
public sealed class ComputerUseDestinationCandidatesTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private const string Signature =
        """{"ok":true,"error":"","hwnd":0,"controls":[{"kind":"Text","name":"Imagen"},{"kind":"Button","name":"Girar"}],"selection":false,"complete":true}""";

    private static VisibleControlSurface.DestinationWindow Desk(long hwnd, string process, bool cloaked = false, long? personAgo = null) =>
        new((nint)hwnd, 100 + (int)hwnd, process, process + " " + hwnd.ToString(System.Globalization.CultureInfo.InvariantCulture), personAgo, cloaked);

    private static WindowsVisibleControlAdapter Adapter(
        ComputerUsePerceptionTests.ScriptedUiaWorker worker, IReadOnlyList<VisibleControlSurface.DestinationWindow> desktop,
        nint front = 0, Func<long>? clock = null) =>
        new(worker, null, null)
        {
            DestinationDesktop = () => (desktop, front),
            DestinationClockMs = clock ?? (static () => 0L),
        };

    private static JsonElement[] Windows(ExternalCapabilityReceipt receipt) =>
        [.. receipt.Result!.Value.GetProperty("candidateWindows").EnumerateArray()];

    // The look's only gate to the listing (WindowsVisibleControlAdapter.ListAsync calls nothing else): a look with a
    // window, a process or an application of its own reads that, as always.
    [Test]
    public void CandidatesAreAskedOnlyByALookWithNoWindowProcessNorApplication()
    {
        JsonElement asked = Json("""{"candidates":true}""");

        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleControlAdapter.AsksForCandidates(asked, 0, 0, null), Is.True);
            Assert.That(WindowsVisibleControlAdapter.AsksForCandidates(asked, 1, 0, null), Is.False, "the mission's windows");
            Assert.That(WindowsVisibleControlAdapter.AsksForCandidates(asked, 0, 4242, null), Is.False, "the mission's process");
            Assert.That(WindowsVisibleControlAdapter.AsksForCandidates(asked, 0, 0, "Paint"), Is.False, "an application");
            Assert.That(WindowsVisibleControlAdapter.AsksForCandidates(Json("""{"limit":60}"""), 0, 0, null), Is.False);
        });
    }

    [Test]
    public async Task ProtectedWindowsAreMarkedAndNeverReadAndCloakedOnesAreLeftOut()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(Signature);
        WindowsVisibleControlAdapter adapter = Adapter(
            worker, [Desk(1, "Code", personAgo: 300), Desk(2, "mspaint", cloaked: true), Desk(3, "mspaint")], front: 1);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"candidates":true,"limit":60}"""), CancellationToken.None);

        JsonElement[] windows = Windows(receipt);
        Assert.Multiple(() =>
        {
            Assert.That(windows.Select(window => window.GetProperty("hwnd").GetInt64()), Is.EqualTo(new long[] { 1, 3 }));
            Assert.That(windows[0].GetProperty("protected").GetBoolean(), Is.True);
            Assert.That(windows[0].GetProperty("controls").GetArrayLength(), Is.Zero);
            Assert.That(windows[0].GetProperty("foreground").GetBoolean(), Is.True);
            Assert.That(windows[0].GetProperty("personInputAgoMs").GetInt64(), Is.EqualTo(300));
            Assert.That(windows[1].TryGetProperty("protected", out _), Is.False);
            Assert.That(windows[1].GetProperty("controls").GetArrayLength(), Is.EqualTo(2));
            Assert.That(worker.Commands, Has.Count.EqualTo(1), "one signature, of the window that is not protected");
            Assert.That(worker.Commands[0], Does.Contain("\"cmd\":\"signature\"").And.Contain("\"hwnd\":3"));
            Assert.That(worker.Commands.Any(command => command.Contains("\"cmd\":\"view\"", StringComparison.Ordinal)), Is.False,
                "the full view (and the worker's last view) is left alone");
        });
    }

    [Test]
    public async Task TheListingRunsUnderOneBudgetAndAWindowNotReadInTimeGoesOutUnread()
    {
        // Each signature takes 1,5 s on the test's clock: the first three are read (the third with what is left), the
        // fourth is not asked for and goes out unread; a failed answer is unread too.
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(Signature);
        WindowsVisibleControlAdapter adapter = Adapter(
            worker, [Desk(1, "mspaint"), Desk(2, "WINWORD"), Desk(3, "Notepad"), Desk(4, "explorer")],
            clock: () => worker.Commands.Count * 1500L);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"candidates":true}"""), CancellationToken.None);

        JsonElement[] windows = Windows(receipt);
        Assert.Multiple(() =>
        {
            Assert.That(worker.Commands, Has.Count.EqualTo(3));
            Assert.That(worker.Commands[0], Does.Contain($"\"budgetMs\":{WindowsVisibleControlAdapter.DestinationWindowBudgetMs}"));
            Assert.That(worker.Commands[2], Does.Contain("\"budgetMs\":1000"));
            Assert.That(windows.Select(window => window.TryGetProperty("unread", out JsonElement unread) && unread.GetBoolean()),
                Is.EqualTo(new[] { false, false, false, true }));
            Assert.That(windows[3].GetProperty("controls").GetArrayLength(), Is.Zero);
        });

        var silent = new ComputerUsePerceptionTests.ScriptedUiaWorker();
        ExternalCapabilityReceipt failed = await Adapter(silent, [Desk(1, "mspaint")]).InvokeAsync(
            "input.visible.controls", Json("""{"candidates":true}"""), CancellationToken.None);
        Assert.That(Windows(failed)[0].GetProperty("unread").GetBoolean(), Is.True);

        // A walk the window's budget cut before any control came is unread; one cut after some came is what it read.
        var cut = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            """{"ok":true,"error":"","hwnd":1,"controls":[],"selection":false,"complete":false}""",
            """{"ok":true,"error":"","hwnd":2,"controls":[{"kind":"Text","name":"Imagen"}],"selection":false,"complete":false}""");
        JsonElement[] partial = Windows(await Adapter(cut, [Desk(1, "mspaint"), Desk(2, "mspaint")]).InvokeAsync(
            "input.visible.controls", Json("""{"candidates":true}"""), CancellationToken.None));
        Assert.That(partial[0].GetProperty("unread").GetBoolean(), Is.True);
        Assert.That(partial[1].TryGetProperty("unread", out _), Is.False);
    }

    [Test]
    public void TheWorkersSignatureIsTheCheapReadAndLeavesTheLastViewAlone()
    {
        // B4: the signature never re-reads the client, the HMENU or the disabled controls, never replaces the view a
        // click or a scroll of the mission resolves against, and stops at its budget.
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string script = File.ReadAllText(worker);
        int start = script.IndexOf("function Do-Signature(", StringComparison.Ordinal);
        Assert.That(start, Is.GreaterThan(0));
        int end = script.IndexOf("\n}", start, StringComparison.Ordinal);
        string body = script[start..end];

        Assert.Multiple(() =>
        {
            foreach (string costly in new[] { "LastView", "Get-ClientReread", "Get-DisabledShown", "MenuEntries", "Get-ShownDescendants" })
                Assert.That(body, Does.Not.Contain(costly));
            Assert.That(body, Does.Contain("budget").And.Contain("Test-TextSelected"));
            Assert.That(script, Does.Contain("elseif($cmd -eq 'signature'){ Send-Line (Do-Signature $request) }"));
        });
    }

    // Revision 1 of ronda 24 (B1): a control the signature read inside a Document goes out marked «content», a frame's
    // control goes out unmarked; the worker's walk carries the mark from a Document down to everything under it.
    [Test]
    public async Task AControlInsideADocumentGoesOutAsContent()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            """{"ok":true,"error":"","hwnd":7,"controls":[{"kind":"Button","name":"Atrás"},{"kind":"Document","name":"Video"},{"kind":"Button","name":"Guardar","content":true}],"selection":false,"complete":true}""");
        WindowsVisibleControlAdapter adapter = Adapter(worker, [Desk(7, "browser")]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"candidates":true}"""), CancellationToken.None);

        JsonElement[] controls = [.. Windows(receipt)[0].GetProperty("controls").EnumerateArray()];
        string path = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(path), "the worker script is copied next to the tests");
        string script = File.ReadAllText(path);
        int start = script.IndexOf("function Do-Signature(", StringComparison.Ordinal);
        string body = script[start..script.IndexOf("\n}", start, StringComparison.Ordinal)];
        Assert.Multiple(() =>
        {
            Assert.That(controls[0].TryGetProperty("content", out _), Is.False);
            Assert.That(controls[1].TryGetProperty("content", out _), Is.False);
            Assert.That(controls[2].GetProperty("content").GetBoolean(), Is.True);
            Assert.That(body, Does.Contain("content=$true").And.Contain("$kind -eq 'Document'"));
        });
    }

    [Test]
    public async Task TheSelectionIsTheOneTheWorkerRead()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            """{"ok":true,"error":"","hwnd":5,"controls":[{"kind":"Document","name":"Informe"}],"selection":true,"complete":true}""",
            """{"ok":true,"error":"","hwnd":6,"controls":[{"kind":"Edit","name":"Barra de direcciones"}],"selection":false,"complete":true}""");
        WindowsVisibleControlAdapter adapter = Adapter(worker, [Desk(5, "WINWORD"), Desk(6, "msedge")]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"candidates":true}"""), CancellationToken.None);

        JsonElement[] windows = Windows(receipt);
        Assert.Multiple(() =>
        {
            Assert.That(windows[0].GetProperty("selection").GetBoolean(), Is.True);
            Assert.That(windows[1].TryGetProperty("selection", out _), Is.False);
        });
    }
}
