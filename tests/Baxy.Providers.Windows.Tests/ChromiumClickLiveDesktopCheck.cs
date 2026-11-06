using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real 03-11 (encargo 54): a click in a Chromium/CEF window whose entry opened its page was said uncertain. Measured
/// on the desktop with a browser of the test's own (a temporary profile, a local page): a list of entries, each pressed
/// opens its page in the same window after <c>delay</c> ms (the list stays, as a launcher's library does, or goes, as a
/// grid of tiles does), with the window's title unchanged. With <c>hover</c>, the person's pointer is told to have passed
/// over the window while the click is read (a double of the detector: on a desktop whose cursor another program holds,
/// such as a shared keyboard and mouse, no pass can be made), so the image proves nothing and the window's tree, read
/// again, must. The click must end verified, by what changed in the window. Never runs in a suite: Explicit and
/// BAXY_CU_CLIC_CHROMIUM_LIVE_CHECK=1; BAXY_CU_CLIC_CHROMIUM_BROWSER names the browser's executable (Edge by default).
/// It acts only on the window it opened, checked by its process and title, and closes every process of its own by id.
/// </summary>
[TestFixture]
[Explicit("Opens a browser window on the person's desktop and clicks in it.")]
[Category("LiveDesktop")]
public sealed class ChromiumClickLiveDesktopCheck
{
    private const string PageTitle = "Estante BAXY 54";
    private const string Entry = "Planeta Ambar";

    [TestCase("button", 0, true, false)]
    [TestCase("div", 900, true, false)]
    [TestCase("link", 900, false, false)]
    [TestCase("button", 0, true, true)]
    [TestCase("div", 900, true, true)]
    [TestCase("link", 900, false, true)]
    public async Task AnEntryThatOpensItsPageInAChromiumWindowIsAVerifiedClick(string kind, int delay, bool keep, bool hover)
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_CLIC_CHROMIUM_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_CU_CLIC_CHROMIUM_LIVE_CHECK=1 is needed to touch the desktop.");
        string browser = Environment.GetEnvironmentVariable("BAXY_CU_CLIC_CHROMIUM_BROWSER") is { Length: > 0 } named
            ? named
            : @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe";
        if (!File.Exists(browser))
            Assert.Ignore("No browser at " + browser);
        string folder = Path.Combine(Path.GetTempPath(), "baxy-clic-chromium-" + Guid.NewGuid().ToString("N")[..8]);
        string profile = Path.Combine(folder, "perfil");
        Directory.CreateDirectory(profile);
        string page = Path.Combine(folder, "estante.html");
        await File.WriteAllTextAsync(page, Page(kind, delay, keep));
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
            if (string.Equals(Path.GetFileName(browser), "msedge.exe", StringComparison.OrdinalIgnoreCase))
                start.ArgumentList.Add("--inprivate");
            start.ArgumentList.Add(new Uri(page).AbsoluteUri);
            using var started = Process.Start(start);
            own.Add(started?.Id ?? 0);
            (nint window, uint drawn) = await OwnWindowAsync(before);
            own.Add(unchecked((int)drawn));
            Assert.That(window, Is.Not.EqualTo((nint)0), "the test's own browser window, of a process it started");
            await Task.Delay(1500);

            using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using var visible = new WindowsVisibleControlAdapter(uia)
            {
                PersonTouchOf = hover ? (_, _) => PersonTouch.PointerPassed : (_, _) => PersonTouch.None,
            };
            ExternalCapabilityReceipt view = default!;
            for (int attempt = 0; attempt < 10; attempt++)
            {
                // The first look of a just opened Chromium window may see no page yet (accessibility turns on with it).
                view = await visible.InvokeAsync(
                    "input.visible.controls",
                    JsonDocument.Parse(JsonSerializer.Serialize(new { application = PageTitle, includeText = false })).RootElement,
                    CancellationToken.None);
                if (view.ErrorCode is null && visible.NamesSeen(window).Contains(Entry))
                    break;
                await Task.Delay(1000);
            }

            TestContext.Out.WriteLine($"mirada: verified={view.Verified} error={view.ErrorCode} nombres={visible.NamesSeen(window).Count}");
            Assert.That(VisibleControlSurface.WindowTitle(window), Does.StartWith(PageTitle + " - "), "still the test's own window");
            var watch = Stopwatch.StartNew();
            ExternalCapabilityReceipt clicked = await visible.InvokeAsync(
                "input.visible.click",
                JsonDocument.Parse(JsonSerializer.Serialize(new { label = Entry, window = (long)window })).RootElement,
                CancellationToken.None);
            TestContext.Out.WriteLine(
                $"clic {kind}/{delay}/{(keep ? "queda" : "se va")}/{(hover ? "mano" : "sin mano")}: verified={clicked.Verified} "
                + $"error={clicked.ErrorCode} ms={watch.ElapsedMilliseconds} result={clicked.Result?.GetRawText()}");
            await Task.Delay(Math.Max(0, delay + 300 - (int)watch.ElapsedMilliseconds));
            string shown = VisibleControlSurface.WindowTitle(window);
            Assert.Multiple(() =>
            {
                Assert.That(view.ErrorCode, Is.Null, "the page is viewed");
                Assert.That(clicked.ErrorCode, Is.Null, "the click that opened its page is not uncertain");
                Assert.That(clicked.Verified, Is.True);
                Assert.That(shown, Does.StartWith(PageTitle + " - "), "the title did not change: the page proved it");
                if (hover)
                    Assert.That(clicked.Result?.TryGetProperty("pointerOver", out _), Is.True, "proved by the tree read again");
            });
        }
        finally
        {
            CloseOwn(own, before);
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

    // A list of entries; pressing one shows «Cargando…» and, after delay ms, its page (its name as the heading, a play
    // button), the list kept or removed. The title never changes.
    private static string Page(string kind, int delay, bool keep)
    {
        string[] entries = [Entry, "Ciudad Coral", "Rio Plateado"];
        string Item(string name) => kind switch
        {
            "button" => $"<li><button type=\"button\" onclick=\"abrir('{name}')\">{name}</button></li>",
            "link" => $"<li><a href=\"#\" onclick=\"abrir('{name}');return false\">{name}</a></li>",
            _ => $"<li><div class=\"fila\" onclick=\"abrir('{name}')\">{name}</div></li>",
        };
        return $$"""
            <!doctype html>
            <html lang="es"><head><meta charset="utf-8"><title>{{PageTitle}}</title>
            <style>.fila{cursor:pointer;padding:4px}nav{float:left;width:30%}main{margin-left:32%}</style></head>
            <body>
            <nav id="lista"><ul>{{string.Concat(entries.Select(Item))}}</ul></nav>
            <main id="ficha"><h1>Inicio</h1><p>Elige una entrada.</p></main>
            <script>
            function abrir(n){
              document.getElementById('ficha').innerHTML='<p>Cargando...</p>';
              setTimeout(function(){
                {{(keep ? string.Empty : "var l=document.getElementById('lista'); l.parentNode.removeChild(l);")}}
                document.getElementById('ficha').innerHTML='<h1>'+n+'</h1><p>Ultima vez: ayer</p><button type="button">Jugar</button>';
              }, {{delay}});
            }
            </script>
            </body></html>
            """;
    }

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
}
