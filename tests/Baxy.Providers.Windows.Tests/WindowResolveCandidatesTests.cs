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

    private static ValueTask<OperationOutcome> Resolve(string code) =>
        new WindowResolveHandler(new FailingWindows(code), () => Desktop, () => ("Opera GX", "opera")).ExecuteAsync(
            new OperationInvocation("r", "m", "i", JsonDocument.Parse("{\"applicationName\":\"Microsoft Word\"}").RootElement),
            CancellationToken.None);

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
            throw new AssertionException("not used");

        public ValueTask<WindowActionResult> ExecuteAsync(
            string windowId, WindowControlAction action, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");

        public ValueTask<WindowActionResult> SetBoundsAsync(
            string windowId, int? x, int? y, int? width, int? height, CancellationToken cancellationToken) =>
            throw new AssertionException("not used");
    }
}
