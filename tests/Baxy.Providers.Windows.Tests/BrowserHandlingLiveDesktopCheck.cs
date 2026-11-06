using System.Diagnostics;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso-111 (owner 04-11: BAXY handles the browser with any web: reads the page, presses, types, changes or closes tabs),
/// on the real desktop, opt-in only (Explicit, BAXY_NAVEGADOR_LIVE_CHECK=1, BAXY_NAVEGADOR_EXE the browser's executable,
/// BAXY_NAVEGADOR_SALIDA the file its log goes to): a browser of the test's own (a temporary profile, three local pages
/// with invented titles) handled through the product's real adapters. The page steps are confined to that browser's own
/// process (<see cref="UserBrowserNamedTabLiveCheck.OwnWindows"/>); the acts name its window, checked by title first. It is
/// closed by its exact process id and its profile deleted.
/// </summary>
[TestFixture]
[Explicit("Opens a browser window on the person's desktop and acts on it.")]
[Category("LiveDesktop")]
public sealed class BrowserHandlingLiveDesktopCheck
{
    private const string Board = "Pizarra BAXY 8Q";
    private const string Detail = "Detalle BAXY 8Q";
    private const string Bills = "Facturas BAXY 8Q";
    private const string Results = "Resultados BAXY 8Q";

    private static JsonElement Json(object arguments) =>
        JsonDocument.Parse(JsonSerializer.Serialize(arguments)).RootElement;

    [Test]
    public async Task ABrowsersPagesAreReadPressedTypedInAndItsTabsChangedAndClosed()
    {
        if (Environment.GetEnvironmentVariable("BAXY_NAVEGADOR_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_NAVEGADOR_LIVE_CHECK=1 is needed to touch the desktop.");
        string executable = Environment.GetEnvironmentVariable("BAXY_NAVEGADOR_EXE") ?? string.Empty;
        if (!File.Exists(executable))
            Assert.Ignore("No browser at " + executable);
        string log = Environment.GetEnvironmentVariable("BAXY_NAVEGADOR_SALIDA") ?? Path.GetTempFileName();
        void Say(string line)
        {
            File.AppendAllText(log, line + Environment.NewLine);
            TestContext.Out.WriteLine(line);
        }

        string root = Path.Combine(Path.GetTempPath(), "baxy-navegador-" + Guid.NewGuid().ToString("N")[..8]);
        string profile = Path.Combine(root, "perfil");
        Directory.CreateDirectory(profile);
        string Page(string name, string title, string body)
        {
            string path = Path.Combine(root, name + ".html");
            File.WriteAllText(path, $"<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\"><title>{title}</title></head><body>{body}</body></html>");
            return new Uri(path).AbsoluteUri;
        }

        string detail = Page("detalle", Detail, "<h1>Detalle</h1><p>Lo construyeron en 1888.</p>");
        string board = Page("pizarra", Board,
            "<h1>Pizarra</h1><p>Un dato: 1.204 visitantes.</p>"
            + $"<p><a href=\"{detail}\">Ver el detalle</a></p>"
            + "<label>Comentario <textarea id=\"c\" rows=\"3\" cols=\"40\"></textarea></label>"
            + "<p><button type=\"button\" onclick=\"document.getElementById('v').textContent='Enviado: '+document.getElementById('c').value\">Enviar</button></p>"
            + "<p id=\"v\">Sin enviar</p>");
        string resultList = Page("resultados", Results,
            "<h1>Resultados</h1>"
            + "<div><a href=\"https://uno.test/a\"><h2>Bus a Lima</h2><div>uno.test</div></a><div>El viaje dura 54 horas.</div></div>"
            + "<div><h2><a href=\"https://dos.test/b\">Vuelos a Lima</a></h2><div>El vuelo tarda 13 horas.</div></div>"
            + "<div><a href=\"https://tres.test/c\">Trenes a Lima</a><div>No hay trenes en esa ruta.</div></div>");
        string bills = Page("facturas", Bills, $"<h1>Facturas</h1><p>Ninguna pendiente.</p><p><a href=\"{resultList}\">Ver la lista</a></p>");
        var before = Process.GetProcesses().Select(static process =>
        {
            using (process)
                return process.Id;
        }).ToHashSet();
        var startInfo = new ProcessStartInfo(executable)
        {
            ArgumentList = { "--user-data-dir=" + profile, "--no-first-run", "--no-default-browser-check", "--disable-sync", "--new-window" },
            UseShellExecute = false,
        };
        if (string.Equals(Path.GetFileName(executable), "msedge.exe", StringComparison.OrdinalIgnoreCase))
            startInfo.ArgumentList.Add("--inprivate");
        startInfo.ArgumentList.Add(board);
        startInfo.ArgumentList.Add(bills);
        using Process browser = Process.Start(startInfo)!;
        var own = new List<int> { browser.Id };
        try
        {
            string processName = Path.GetFileNameWithoutExtension(executable);
            var identity = new UserBrowserIdentity("Prueba", processName == "msedge" ? "edge" : "chrome", "Navegador de prueba", executable);
            var real = new WindowsUserBrowserPlatform();
            nint window = 0;
            int owner = 0;
            for (int attempt = 0; attempt < 40 && window == 0; attempt++)
            {
                await Task.Delay(500);
                // A process that was not running before the test, on the page asked for (a launcher may hand over to another).
                foreach (UserBrowserWindow seen in real.ListWindows(processName))
                {
                    int process = VisibleControlSurface.WindowProcess(seen.Handle).ProcessId;
                    if (!before.Contains(process) && seen.Title.Contains(Board, StringComparison.Ordinal))
                    {
                        window = seen.Handle;
                        owner = process;
                        break;
                    }
                }
            }
            Assert.That(window, Is.Not.EqualTo((nint)0), "the test's own window, on the page asked for");
            own.Add(owner);
            var platform = new UserBrowserNamedTabLiveCheck.OwnWindows(real, owner);
            var surface = new UserBrowserSurface(platform);
            platform.Window = window;
            await Task.Delay(1500);
            using var uia = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            using var visible = new WindowsVisibleControlAdapter(uia);
            var typing = new WindowsDesktopInteractionAdapter(visible) { Scripts = uia };
            var results = new Dictionary<string, bool>();
            void Mark(string step, bool passed, ExternalCapabilityReceipt receipt)
            {
                results[step] = passed;
                // Only what is of the test's own pages: a failed look or click may name the person's other windows.
                string shown = receipt.Result?.GetRawText() ?? string.Empty;
                Say($"{step}: {(passed ? "BIEN" : "MAL")} verified={receipt.Verified} error={receipt.ErrorCode} "
                    + (shown.Contains("BAXY 8Q", StringComparison.Ordinal) && !shown.Contains("candidates", StringComparison.Ordinal)
                        && !shown.Contains("closest", StringComparison.Ordinal) && !shown.Contains("controls", StringComparison.Ordinal)
                        ? shown[..Math.Min(shown.Length, 700)] : string.Empty));
            }

            async ValueTask<ExternalCapabilityReceipt> ReadAsync() =>
                await surface.ReadPageAsync("browser.page.read", identity, 6_000, CancellationToken.None);
            static string Field(ExternalCapabilityReceipt receipt, string name) =>
                receipt.Result is { ValueKind: JsonValueKind.Object } result && result.TryGetProperty(name, out JsonElement value)
                    ? value.ToString() : string.Empty;
            void Own() => Assert.That(VisibleControlSurface.WindowTitle(window), Does.Contain("BAXY 8Q"), "still the test's own window");

            ExternalCapabilityReceipt page = await ReadAsync();
            Mark("leer la página", page.Verified && Field(page, "text").Contains("1.204", StringComparison.Ordinal), page);

            ExternalCapabilityReceipt look = await visible.InvokeAsync(
                "input.visible.controls", Json(new { application = Board, includeText = true }), CancellationToken.None);
            Mark("mirar la ventana por el nombre de la página", look.Verified, look);

            Own();
            ExternalCapabilityReceipt focusField = await visible.InvokeAsync(
                "input.visible.click", Json(new { label = "Comentario", window = (long)window }), CancellationToken.None);
            Mark("pulsar el campo", focusField.Verified, focusField);
            Own();
            ExternalCapabilityReceipt typed = await typing.InvokeAsync(
                "input.text.type", Json(new { text = "Hola mundo", window = (long)window }), CancellationToken.None);
            Mark("escribir en el campo y releerlo", typed.Verified && Field(typed, "readBack") == "True", typed);

            Own();
            ExternalCapabilityReceipt pressed = await visible.InvokeAsync(
                "input.visible.click", Json(new { label = "Enviar", window = (long)window }), CancellationToken.None);
            Mark("pulsar el botón", pressed.Verified, pressed);
            await Task.Delay(500);
            ExternalCapabilityReceipt sent = await ReadAsync();
            Mark("el botón hizo lo suyo y lo escrito llegó a la página",
                Field(sent, "text").Contains("Enviado: Hola mundo", StringComparison.Ordinal), sent);

            Own();
            ExternalCapabilityReceipt link = await visible.InvokeAsync(
                "input.visible.click", Json(new { label = "Ver el detalle", window = (long)window }), CancellationToken.None);
            Mark("pulsar un enlace", link.Verified, link);
            await Task.Delay(1000);
            ExternalCapabilityReceipt arrived = await ReadAsync();
            Mark("el enlace llevó a su página", Field(arrived, "title") == Detail, arrived);

            ExternalCapabilityReceipt tabs = await surface.ListTabsAsync("browser.tabs.list", identity, 20, CancellationToken.None);
            Mark("listar pestañas", tabs.Verified, tabs);
            ExternalCapabilityReceipt switched = await surface.ControlAsync(
                "browser.control", identity, "switch_tab", "facturas", new ExternalEffectBoundary(), CancellationToken.None);
            Mark("cambiar de pestaña", switched.Verified, switched);
            await Task.Delay(500);
            ExternalCapabilityReceipt other = await ReadAsync();
            Mark("la página leída es la de la otra pestaña", Field(other, "title") == Bills, other);
            Own();
            ExternalCapabilityReceipt toList = await visible.InvokeAsync(
                "input.visible.click", Json(new { label = "Ver la lista", window = (long)window }), CancellationToken.None);
            await Task.Delay(1000);
            ExternalCapabilityReceipt list = await ReadAsync();
            Mark("una lista de resultados llega en bloques",
                toList.Verified && list.Result?.TryGetProperty("blocks", out JsonElement blocks) == true && blocks.GetArrayLength() == 2
                && blocks[1].GetProperty("text").GetString() == "El vuelo tarda 13 horas.", list);
            ExternalCapabilityReceipt closed = await surface.ControlAsync(
                "browser.control", identity, "close", "detalle", new ExternalEffectBoundary(), CancellationToken.None);
            Mark("cerrar una pestaña nombrada", closed.Verified, closed);

            Say("RESUMEN " + executable + ": " + results.Count(static step => step.Value) + "/" + results.Count);
            Assert.That(results.Where(static step => !step.Value).Select(static step => step.Key), Is.Empty);
        }
        finally
        {
            foreach (int id in own.Where(id => !before.Contains(id)).Distinct())
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

            for (int attempt = 0; attempt < 10 && Directory.Exists(root); attempt++)
            {
                try
                {
                    Directory.Delete(root, recursive: true);
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
                {
                    await Task.Delay(500);
                }
            }
        }
    }
}
