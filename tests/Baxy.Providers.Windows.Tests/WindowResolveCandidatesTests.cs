using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C13): a window.resolve by an application name that matched nothing («Microsoft Word» is no installed
/// name; the browser guessed was not the one open) went back with only its code, and the reply said the application was
/// not open. With the aid window_candidates it carries the desktop's windows, by process and title, as a look that names
/// no window does (fake windows: nothing real is read).
/// </summary>
[TestFixture]
public sealed class WindowResolveCandidatesTests
{
    private static readonly (string, string)[] Desktop = [("WINWORD", "informe - Word"), ("opera", "Gmail - Opera")];

    [TestCase("app_not_found")]
    [TestCase("window_not_found")]
    public async Task AnApplicationNameThatMatchedNothingListsTheVisibleWindows(string code)
    {
        using IDisposable setting = ModelAids.Use("all");
        OperationOutcome outcome = await Resolve(code);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(code));
            JsonElement result = outcome.Result!.Value;
            Assert.That(result.GetProperty("candidateCount").GetInt32(), Is.EqualTo(2));
            Assert.That(result.GetProperty("candidates")[0].GetProperty("process").GetString(), Is.EqualTo("WINWORD"));
            Assert.That(result.GetProperty("candidates")[1].GetProperty("title").GetString(), Is.EqualTo("Gmail - Opera"));
            Assert.That(result.GetProperty("personBrowser").GetProperty("process").GetString(), Is.EqualTo("opera"));
            Assert.That(result.GetProperty("next").GetString(), Does.Contain("by its process")
                .And.Contain("the person's web browser is Opera GX (process opera)"));
        });
    }

    // P2.15: app_not_found is a name no installed application bears, so no window was looked for by it; «no window was
    // found under that name» read as «it is not open». Only window_not_found says no window was found.
    [TestCase("app_not_found", "no installed application bears that name")]
    [TestCase("window_not_found", "no window was found under that name")]
    public async Task ItsWayOutSaysWhatTheNameMatched(string code, string lead)
    {
        using IDisposable setting = ModelAids.Use("all");
        string next = (await Resolve(code)).Result!.Value.GetProperty("next").GetString()!;

        Assert.That(next, Does.StartWith(lead));
    }

    // Contracases: with the aids off, and for another failure, the code goes back alone, as before.
    [TestCase("none", "app_not_found")]
    [TestCase("all", "verification_failed")]
    public async Task OtherwiseTheCodeGoesBackAlone(string aids, string code)
    {
        using IDisposable setting = ModelAids.Use(aids);
        OperationOutcome outcome = await Resolve(code);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(code));
            Assert.That(outcome.Result, Is.Null);
        });
    }

    // Al máximo, flujos (P252, 22 of 27 runs: «pon esta ventana a la izquierda» → window.resolve {}): with no selector
    // the refusal says, as a fact, that the person's window in front (BAXY's own left out) is window_active's; with
    // both selectors, or with the aid off, the code goes back alone. Nothing is read.
    [TestCase("all", "{}", true)]
    [TestCase("all", "{\"limit\":5}", true)]
    [TestCase("all", "{\"applicationName\":\"Word\",\"process\":\"WINWORD\"}", false)]
    [TestCase("none", "{}", false)]
    public async Task NoSelectorSaysThePersonsWindowInFrontIsWindowActives(string aids, string json, bool told)
    {
        using IDisposable setting = ModelAids.Use(aids);

        OperationOutcome outcome = await new WindowResolveHandler(
                new FailingWindows("not_read"), () => Desktop, () => ("Opera GX", "opera"))
            .ExecuteAsync(new OperationInvocation("r", "m", "i", JsonDocument.Parse(json).RootElement), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(WindowControlErrorCodes.InvalidSelector));
            Assert.That(outcome.Result?.GetProperty("next").GetString(),
                told ? Does.Contain("window_active") : Is.Null);
        });
    }

    // Encargo L3 («Cierra Nubarra del todo, que se queda pegada ahí al lado del reloj»): an application in the notification
    // area has no window, so window_not_found and the desktop's windows left the model resolving again 4 times of 5, and
    // it never reached app_close, the one call that asks it to quit. It says so, and which call closes it, and only if
    // that is what the person asked: unconditional, «maximiza» closed it in 2 of 21 controls.
    [Test]
    public async Task AnApplicationRunningWithoutAWindowSaysSoAndWhichCallClosesIt()
    {
        using IDisposable setting = ModelAids.Use("all");

        OperationOutcome outcome = await new WindowResolveHandler(
                new FailingWindows(WindowControlErrorCodes.WindowNotFound) { Background = [4242, 4243] },
                () => Desktop, () => null)
            .ExecuteAsync(
                new OperationInvocation("r", "m", "i", JsonDocument.Parse("{\"applicationName\":\"Nubarra\"}").RootElement),
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(WindowControlErrorCodes.WindowNotFound));
            Assert.That(outcome.Result?.GetProperty("runningWithoutWindow").GetBoolean(), Is.True);
            Assert.That(outcome.Result?.GetProperty("backgroundProcesses").GetInt32(), Is.EqualTo(2));
            Assert.That(outcome.Result?.GetProperty("candidateCount").GetInt32(), Is.EqualTo(2));
            Assert.That(outcome.Result?.GetProperty("next").GetString(), Is.EqualTo(
                "it has no window open but it is running in the background: if the person asked to close it, "
                + "app_close {\"appId\":\"Nubarra\"}; if they asked for its window, it has none; these are the other "
                + "windows open on the desktop (top first)"));
        });
    }

    [Test]
    public async Task AnApplicationNotRunningKeepsTheReceiptItHad()
    {
        using IDisposable setting = ModelAids.Use("all");

        OperationOutcome outcome = await Resolve(WindowControlErrorCodes.WindowNotFound);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Result?.TryGetProperty("runningWithoutWindow", out _), Is.False);
            Assert.That(outcome.Result?.GetProperty("next").GetString(), Does.StartWith("no window was found under that name"));
        });
    }

    private static ValueTask<OperationOutcome> Resolve(string code) =>
        new WindowResolveHandler(new FailingWindows(code), () => Desktop, () => ("Opera GX", "opera")).ExecuteAsync(
            new OperationInvocation("r", "m", "i", JsonDocument.Parse("{\"applicationName\":\"Microsoft Word\"}").RootElement),
            CancellationToken.None);

    // Encargo 94 (held-out: «Pégalo en la ventana que se llama Cuaderno Faro»): a name no installed application bears
    // answered «no window was looked for by it» with a window of that very title in its own list, and the model hunted for
    // it by process until it gave up, or resolved it and pasted into the one in front. The window of that exact title is
    // the answer; not in front, it says which paste reaches it (the call written, as the rule of encargos 20, 28 and 34).
    [Test]
    public async Task AWindowOfThatExactTitleIsTheAnswerAndSaysWhichPasteReachesIt()
    {
        using IDisposable setting = ModelAids.Use("all");
        WindowCandidate window = new("win_7", 7, "cuaderno", "normal", false, 0, 0, 600, 300, "Cuaderno Lumbre");
        var windows = new FailingWindows("app_not_found") { Titled = [window] };

        OperationOutcome outcome = await new WindowResolveHandler(windows, () => Desktop, () => ("Opera GX", "opera")).ExecuteAsync(
            new OperationInvocation("r", "m", "i", JsonDocument.Parse("""{"applicationName":"Cuaderno Lumbre"}""").RootElement),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            JsonElement result = outcome.Result!.Value;
            Assert.That(result.GetProperty("windows")[0].GetProperty("windowId").GetString(), Is.EqualTo("win_7"));
            Assert.That(result.GetProperty("next").GetString(), Does.Contain(
                """clipboard_paste_into {"appId":"Cuaderno Lumbre"} pastes into this window""").And.Contain("the window in front"));
        });
    }

    // Contracase: in front, a plain paste reaches it: nothing to say.
    [Test]
    public async Task AWindowOfThatTitleInFrontSaysNothingMore()
    {
        using IDisposable setting = ModelAids.Use("all");
        WindowCandidate window = new("win_7", 7, "cuaderno", "normal", true, 0, 0, 600, 300, "Cuaderno Lumbre");
        var windows = new FailingWindows("app_not_found") { Titled = [window] };

        OperationOutcome outcome = await new WindowResolveHandler(windows, () => Desktop, () => ("Opera GX", "opera")).ExecuteAsync(
            new OperationInvocation("r", "m", "i", JsonDocument.Parse("""{"applicationName":"Cuaderno Lumbre"}""").RootElement),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out _), Is.False);
        });
    }

    // BAXY Renew cu (C13 en el PC): a browser resolved by name that is not the person's own says which theirs is; the
    // person's own, or a window that is no browser, goes back as it was.
    [Test]
    public void ABrowserThatIsNotThePersonsOwnSaysWhichTheirsIs()
    {
        using JsonDocument found = JsonDocument.Parse("""{"version":1,"windows":[]}""");
        WindowCandidate chrome = new("win_1", 1, "chrome", "maximized", false, 0, 0, 1366, 768, "YouTube");
        WindowCandidate opera = new("win_2", 2, "opera", "maximized", false, 0, 0, 1366, 768, "Correo");
        WindowCandidate word = new("win_3", 3, "WINWORD", "normal", false, 0, 0, 800, 600, "Documento1");
        (string, string) own = ("Opera GX", "opera");

        JsonElement other = WindowResolveHandler.WithPersonBrowser(found.RootElement, [chrome], own);

        Assert.Multiple(() =>
        {
            Assert.That(other.GetProperty("personBrowser").GetProperty("name").GetString(), Is.EqualTo("Opera GX"));
            Assert.That(other.GetProperty("next").GetString(), Does.Contain("windows of chrome"));
            Assert.That(WindowResolveHandler.WithPersonBrowser(found.RootElement, [opera], own)
                .TryGetProperty("personBrowser", out _), Is.False);
            Assert.That(WindowResolveHandler.WithPersonBrowser(found.RootElement, [word], own)
                .TryGetProperty("personBrowser", out _), Is.False);
            Assert.That(WindowResolveHandler.WithPersonBrowser(found.RootElement, [chrome], null)
                .TryGetProperty("personBrowser", out _), Is.False);
        });
    }

    private sealed class FailingWindows(string code) : IWindowControlProvider
    {
        internal IReadOnlyList<WindowCandidate> Titled { get; init; } = [];

        internal IReadOnlyList<int> Background { get; init; } = [];

        public ValueTask<IReadOnlyList<int>> BackgroundProcessesAsync(string applicationName, CancellationToken cancellationToken) =>
            ValueTask.FromResult(Background);

        public ValueTask<WindowResolveResult> ResolveApplicationAsync(
            string applicationName, int limit, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new WindowResolveResult(false, false, [], code));

        public ValueTask<WindowMinimizeAllResult> MinimizeAllAsync(CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowCloseResult> CloseAsync(string windowId, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowResolveResult> ResolveForegroundAsync(CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowResolveResult> ResolveAsync(
            string processName, int limit, CancellationToken cancellationToken, bool byTitle = false, int offset = 0) =>
            !byTitle ? throw new AssertionException("not used")
                : ValueTask.FromResult(Titled.Count > 0
                    ? new WindowResolveResult(true, true, Titled, null)
                    : new WindowResolveResult(false, false, [], WindowControlErrorCodes.WindowNotFound));

        public ValueTask<WindowActionResult> ExecuteAsync(
            string windowId, WindowControlAction action, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowActionResult> SetBoundsAsync(
            string windowId, int? x, int? y, int? width, int? height, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");
    }
}
