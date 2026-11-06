using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real 03-11 (G8, «en el traductor de Google escribe hola» en Opera): a field of a web page open in a Chromium
/// browser, measured on the desktop with a browser of the test's own (a temporary profile, a local page with a single
/// line field and a text area that has the focus, as the translator's has). The page is found by its own name (the
/// title's first part, before « - <browser>»), its fields are viewed, and a text typed by the keyboard into the focused
/// text area is read back there. Never runs in a suite: Explicit and BAXY_CU_CAMPO_WEB_LIVE_CHECK=1;
/// BAXY_CU_CAMPO_WEB_BROWSER names the browser's executable (Edge by default). It acts only on the window it opened,
/// checked by its process and title before every act, and closes every process of its own profile by its id.
/// </summary>
[TestFixture]
[Explicit("Opens a browser window on the person's desktop and types into it.")]
[Category("LiveDesktop")]
public sealed class WebFieldLiveDesktopCheck
{
    private const string PageTitle = "Pizarra BAXY 7Q";

    [Test]
    public async Task AWebPageIsFoundByItsNameAndWhatIsTypedInItsFieldIsReadBack()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_CAMPO_WEB_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_CU_CAMPO_WEB_LIVE_CHECK=1 is needed to touch the desktop.");
        string browser = Environment.GetEnvironmentVariable("BAXY_CU_CAMPO_WEB_BROWSER") is { Length: > 0 } named
            ? named
            : @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe";
        if (!File.Exists(browser))
            Assert.Ignore("No browser at " + browser);
        string folder = Path.Combine(Path.GetTempPath(), "baxy-campo-web-" + Guid.NewGuid().ToString("N")[..8]);
        string profile = Path.Combine(folder, "perfil");
        Directory.CreateDirectory(profile);
        string page = Path.Combine(folder, "pizarra.html");
        await File.WriteAllTextAsync(page, $$"""
            <!doctype html>
            <html lang="es"><head><meta charset="utf-8"><title>{{PageTitle}}</title></head>
            <body><h1>Pizarra</h1>
            <label>Asunto <input id="asunto" type="text"></label><br>
            <label for="texto">Texto de origen</label><br>
            <textarea id="texto" rows="5" cols="50" autofocus></textarea>
            </body></html>
            """);
        // Every process already running is the person's (their own browser among them): never taken as the test's.
        var before = Process.GetProcesses().Select(static process =>
        {
            using (process)
                return process.Id;
        }).ToHashSet();
        var own = new List<int>();
        try
        {
            var start = new ProcessStartInfo(browser)
            {
                ArgumentList = { "--user-data-dir=" + profile, "--no-first-run", "--no-default-browser-check", "--new-window" },
                UseShellExecute = false,
            };
            // Edge signs a new profile in with the Windows account and shows its sync dialog over the page; InPrivate
            // never signs in.
            if (string.Equals(Path.GetFileName(browser), "msedge.exe", StringComparison.OrdinalIgnoreCase))
                start.ArgumentList.Add("--inprivate");
            start.ArgumentList.Add(new Uri(page).AbsoluteUri);
            using var started = Process.Start(start);
            own.Add(started?.Id ?? 0);
            (nint window, uint drawn) = await OwnWindowAsync(before);
            own.Add(unchecked((int)drawn));
            Assert.That(window, Is.Not.EqualTo((nint)0), "the test's own browser window, of a process it started");
            string title = VisibleControlSurface.WindowTitle(window);
            TestContext.Out.WriteLine($"ventana {window} «{title}»");
            await Task.Delay(1500);

            nint found = await VisibleControlSurface.ResolveTitledWindowAsync(PageTitle, CancellationToken.None);
            TestContext.Out.WriteLine($"por su nombre: {found}");

            using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using var visible = new WindowsVisibleControlAdapter(uia);
            var typing = new WindowsDesktopInteractionAdapter(visible) { Scripts = uia };

            // First the text, with no look before it: the browser's accessibility tree is still off (the hardest case;
            // a look first would have turned it on). The product's act fronts the window it names (checked before every
            // key) and gives the front back.
            Assert.That(VisibleControlSurface.WindowTitle(window), Does.StartWith(PageTitle + " - "), "still the test's own window");
            ExternalCapabilityReceipt typed = await typing.InvokeAsync(
                "input.text.type",
                JsonDocument.Parse(JsonSerializer.Serialize(new { text = "Hola mundo", window = (long)window })).RootElement,
                CancellationToken.None);
            bool readBack = typed.Result is { ValueKind: JsonValueKind.Object } typedResult
                && typedResult.TryGetProperty("readBack", out JsonElement read) && read.ValueKind == JsonValueKind.True;
            TestContext.Out.WriteLine($"escrito: verified={typed.Verified} error={typed.ErrorCode} readBack={readBack}");

            ExternalCapabilityReceipt view = await visible.InvokeAsync(
                "input.visible.controls",
                JsonDocument.Parse(JsonSerializer.Serialize(new { application = PageTitle, includeText = true })).RootElement,
                CancellationToken.None);
            // Only what the look says of the focused field is written (a failed look lists the person's windows).
            string focused = view.Result is { ValueKind: JsonValueKind.Object } seen
                && seen.TryGetProperty("window", out JsonElement viewed) && viewed.TryGetProperty("focused", out JsonElement field)
                    ? field.GetRawText()
                    : "-";
            TestContext.Out.WriteLine($"mirada: verified={view.Verified} error={view.ErrorCode} foco={focused}");

            Assert.Multiple(() =>
            {
                Assert.That(found, Is.EqualTo(window), "the page is found by its own name");
                Assert.That(view.ErrorCode, Is.Null, "its fields are viewed");
                Assert.That(typed.ErrorCode, Is.Null);
                Assert.That(typed.Verified, Is.True);
                Assert.That(readBack, Is.True, "the text typed is read back in the focused text area");
            });
        }
        finally
        {
            CloseOwn(own, before);
            // The temporary profile goes with the browser (a browser may have signed it in and synchronized into it).
            for (int attempt = 0; attempt < 10 && Directory.Exists(folder); attempt++)
            {
                try
                {
                    Directory.Delete(folder, recursive: true);
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
                {
                    await Task.Delay(500);
                }
            }
        }
    }

    // The visible top-level window titled by the test's own page (a name no other window has), of a process that was
    // not running before the test (never the person's browser, even if it took the page), and its process.
    private static async Task<(nint Window, uint Process)> OwnWindowAsync(HashSet<int> before)
    {
        for (int attempt = 0; attempt < 60; attempt++)
        {
            nint chosen = 0;
            uint owner = 0;
            EnumWindows((window, ignored) =>
            {
                if (!IsWindowVisible(window)
                    || !VisibleControlSurface.WindowTitle(window).StartsWith(PageTitle + " - ", StringComparison.Ordinal))
                    return true;
                _ = GetWindowThreadProcessId(window, out uint process);
                if (before.Contains(unchecked((int)process)))
                    return true;
                owner = process;
                chosen = window;
                return false;
            }, 0);
            if (chosen != 0)
                return (chosen, owner);
            await Task.Delay(500);
        }

        return (0, 0);
    }

    // The browser the test started and the process that drew its page, each with its helpers, by id; never one that was
    // running before the test.
    private static void CloseOwn(IEnumerable<int> processes, HashSet<int> before)
    {
        foreach (int id in processes.Where(id => id > 0 && !before.Contains(id)).Distinct())
        {
            try
            {
                using Process process = Process.GetProcessById(id);
                process.Kill(entireProcessTree: true);
            }
            catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
                or System.ComponentModel.Win32Exception)
            {
            }
        }
    }

    private delegate bool EnumWindowsProc(nint window, nint parameter);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumWindows(EnumWindowsProc callback, nint parameter);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowVisible(nint window);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint process);

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();
}
