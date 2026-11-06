using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// On the real desktop, opt-in only (Explicit and BAXY_PAGE_LIVE_CHECK=1): browser.page.read over local pages in an Edge of
/// the test's own, each with a temporary profile and scrolled by the address's fragment. Every window step is confined to
/// that Edge's process (<see cref="UserBrowserNamedTabLiveCheck.OwnWindows"/>); it is closed by its process id.
/// </summary>
[TestFixture]
[Explicit("Opens Edge windows of its own with local pages.")]
public sealed class UserBrowserPageOnScreenLiveCheck
{
    private const string EdgeExecutable = @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe";

    private static string Paragraphs(int count)
    {
        var page = new StringBuilder("<h1>Inicio de la pagina</h1>");
        for (int number = 1; number <= count; number++)
            page.Append("<p id=p").Append(number).Append(">Parrafo numero ").Append(number).Append(" con algo de texto para llenar la linea y que ocupe sitio.</p>");
        return page.Append("<h2 id=fin>Fin de la pagina</h2>").ToString();
    }

    private static string Results(int count)
    {
        var page = new StringBuilder("<h1>Resultados</h1>");
        for (int number = 1; number <= count; number++)
        {
            page.Append("<article id=r").Append(number).Append("><h3><a href=\"https://sitio").Append(number).Append(".test/\">Resultado ").Append(number)
                .Append("</a></h3><p>Lo que dice el resultado ").Append(number).Append(" y nada mas que eso.</p></article>");
        }
        return page.ToString();
    }

    [Test]
    public async Task AtItsTopALongPageIsReadAsEver()
    {
        JsonElement page = await ReadAsync(Paragraphs(400), string.Empty);
        Assert.Multiple(() =>
        {
            Assert.That(page.GetProperty("text").GetString(), Does.StartWith("Inicio de la pagina"));
            Assert.That(page.TryGetProperty("textStartsOnScreen", out _), Is.False);
        });
    }

    [Test]
    public async Task ScrolledDownItIsReadFromWhatIsOnScreen()
    {
        JsonElement page = await ReadAsync(Paragraphs(400), "#p232");
        string text = page.GetProperty("text").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(text[..200], Does.Contain("Parrafo numero 232"));
            Assert.That(text, Does.Not.Contain("Inicio de la pagina"));
            Assert.That(page.GetProperty("truncated").GetBoolean(), Is.True);
            Assert.That(page.GetProperty("textStartsOnScreen").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task AFixedHeaderDoesNotSendItBackToTheTop()
    {
        JsonElement page = await ReadAsync(
            "<header style=\"position:fixed;top:0;left:0;right:0;height:90px;background:#fff\">Cabecera fija</header>" + Paragraphs(400), "#p232");
        string text = page.GetProperty("text").GetString()!;
        Assert.That(text[..200], Does.Contain("Parrafo numero 23"));
        Assert.That(text, Does.Not.Contain("Inicio de la pagina"));
    }

    [Test]
    public async Task AFixedSideIndexLongerThanThePageStillLeavesThePageInTheText()
    {
        var index = new StringBuilder("<nav style=\"position:fixed;left:0;top:0;width:200px;height:100%;overflow:hidden;background:#fff\">");
        for (int entry = 1; entry <= 60; entry++)
            index.Append("<div>Entrada ").Append(entry).Append(" del indice lateral</div>");
        JsonElement page = await ReadAsync(index + "</nav><div style=\"margin-left:220px\">" + Paragraphs(400) + "</div>", "#p232");
        Assert.That(page.GetProperty("text").GetString(), Does.Contain("Parrafo numero 232"));
    }

    [Test]
    public async Task AtTheEndItReadsWhatIsOnScreen()
    {
        JsonElement page = await ReadAsync(Paragraphs(400), "#fin");
        Assert.That(page.GetProperty("text").GetString(), Does.Contain("Fin de la pagina"));
    }

    [Test]
    public async Task AHugePageStaysWithinItsLimit()
    {
        var watch = Stopwatch.StartNew();
        JsonElement page = await ReadAsync(Paragraphs(10_000), "#p7000");
        TestContext.Out.WriteLine($"{watch.ElapsedMilliseconds} ms");
        Assert.That(page.GetProperty("text").GetString()![..200], Does.Contain("Parrafo numero 7000"));
    }

    [Test]
    public async Task AColumnThatScrollsInsideIsReadAsEverAndSaysNothing()
    {
        JsonElement page = await ReadAsync(
            "<div id=c style=\"height:90vh;overflow:auto\">" + Paragraphs(400) + "</div>", "#p232");
        Assert.Multiple(() =>
        {
            Assert.That(page.GetProperty("text").GetString(), Does.StartWith("Inicio de la pagina"));
            Assert.That(page.TryGetProperty("textStartsOnScreen", out _), Is.False);
        });
    }

    [Test]
    public async Task AReadTellsHowToGoOnAndAfterScrollingItStartsFurtherDown()
    {
        (JsonElement first, JsonElement second) = await ReadTwiceAsync(Paragraphs(400));
        string again = second.GetProperty("text").GetString()!;
        TestContext.Out.WriteLine($"segunda len={again.Length} empieza «{again[..Math.Min(40, again.Length)]}»");
        Assert.Multiple(() =>
        {
            Assert.That(first.GetProperty("next").GetString(), Is.EqualTo(UserBrowserSurface.PageGoesOnBelow));
            Assert.That(second.GetProperty("textStartsOnScreen").GetBoolean(), Is.True);
            Assert.That(again, Does.Not.StartWith("Inicio de la pagina"));
        });
    }

    [Test]
    public async Task AScrolledPageThatFitsIsReadWhole()
    {
        JsonElement page = await ReadAsync(Paragraphs(40), "#p30");
        Assert.Multiple(() =>
        {
            Assert.That(page.GetProperty("text").GetString(), Does.Contain("Inicio de la pagina"));
            Assert.That(page.TryGetProperty("textStartsOnScreen", out _), Is.False);
        });
    }

    [Test]
    public async Task TheBlocksOfAScrolledListStartOnScreen()
    {
        JsonElement page = await ReadAsync(Results(300), "#r150");
        JsonElement[] blocks = [.. page.GetProperty("blocks").EnumerateArray()];
        string first = blocks[0].GetProperty("title").GetString()!;
        TestContext.Out.WriteLine(first + " .. " + blocks[^1].GetProperty("title").GetString());
        Assert.That(int.Parse(first.Split(' ')[1], System.Globalization.CultureInfo.InvariantCulture), Is.InRange(140, 160));
    }

    private static async Task<JsonElement> ReadAsync(string body, string fragment) =>
        (await OwnPageAsync(body, fragment, async (surface, _, browser) =>
            (await surface.ReadPageAsync("browser.page.read", browser, 6_000, CancellationToken.None), default(ExternalCapabilityReceipt)))).Item1;

    private static Task<(JsonElement, JsonElement)> ReadTwiceAsync(string body) =>
        OwnPageAsync(body, string.Empty, async (surface, platform, browser) =>
        {
            ExternalCapabilityReceipt first = await surface.ReadPageAsync("browser.page.read", browser, 6_000, CancellationToken.None);
            ExternalCapabilityReceipt down = await surface.ControlAsync(
                "browser.control", browser, "scroll_down", null, new ExternalEffectBoundary(), CancellationToken.None);
            Assert.That(down.Verified, Is.True, down.ErrorCode);
            await Task.Delay(500);
            return (first, await surface.ReadPageAsync("browser.page.read", browser, 6_000, CancellationToken.None));
        });

    private static async Task<(JsonElement, JsonElement)> OwnPageAsync(
        string body,
        string fragment,
        Func<UserBrowserSurface, UserBrowserNamedTabLiveCheck.OwnWindows, UserBrowserIdentity, Task<(ExternalCapabilityReceipt, ExternalCapabilityReceipt?)>> read)
    {
        if (Environment.GetEnvironmentVariable("BAXY_PAGE_LIVE_CHECK") != "1")
            Assert.Ignore("Set BAXY_PAGE_LIVE_CHECK=1 to run the live check.");
        string root = Path.Combine(Path.GetTempPath(), "baxy-page-live-" + Guid.NewGuid().ToString("N")[..8]);
        string profile = Path.Combine(root, "profile");
        Directory.CreateDirectory(profile);
        string file = Path.Combine(root, "pagina.html");
        string title = "Pagina " + Path.GetFileName(root);
        await File.WriteAllTextAsync(file, "<!doctype html><html><head><title>" + title + "</title></head><body>" + body + "</body></html>");
        using Process edge = Process.Start(new ProcessStartInfo(EdgeExecutable)
        {
            Arguments = "--user-data-dir=\"" + profile + "\" --no-first-run --no-default-browser-check --new-window \""
                + new Uri(file).AbsoluteUri + fragment + "\"",
            UseShellExecute = false,
        })!;
        try
        {
            var platform = new UserBrowserNamedTabLiveCheck.OwnWindows(new WindowsUserBrowserPlatform(), edge.Id);
            for (int attempt = 0; attempt < 40 && platform.Window == 0; attempt++)
            {
                await Task.Delay(500);
                if (platform.ListWindows("msedge") is [var window, ..] && window.Title.StartsWith(title, StringComparison.Ordinal))
                    platform.Window = window.Handle;
            }

            Assert.That(platform.Window, Is.Not.EqualTo((nint)0), "the test's own window");
            await Task.Delay(1_500);
            var browser = new UserBrowserIdentity("MSEdgeHTM", "edge", "Microsoft Edge", EdgeExecutable);
            (ExternalCapabilityReceipt one, ExternalCapabilityReceipt? two) = await read(new UserBrowserSurface(platform), platform, browser);
            Assert.That(one.Verified, Is.True, one.ErrorCode);
            JsonElement page = one.Result!.Value.Clone();
            JsonElement more = two?.Result is { } after ? after.Clone() : default;
            string text = page.GetProperty("text").GetString()!;
            TestContext.Out.WriteLine($"len={text.Length} empieza «{text[..Math.Min(50, text.Length)]}» from={(page.TryGetProperty("textStartsOnScreen", out _) ? "pantalla" : "inicio")}");
            return (page, more);
        }
        finally
        {
            if (!edge.HasExited)
                edge.Kill(entireProcessTree: true);
            await edge.WaitForExitAsync();
            for (int attempt = 0; attempt < 10 && Directory.Exists(root); attempt++)
            {
                try
                {
                    Directory.Delete(root, recursive: true);
                }
                catch (IOException)
                {
                    await Task.Delay(500);
                }
                catch (UnauthorizedAccessException)
                {
                    await Task.Delay(500);
                }
            }
        }
    }
}
