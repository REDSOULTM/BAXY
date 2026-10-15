using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Goal v3, point 0, fix 1, measured on the desktop: which windows take a text or a key delivered without the
/// keyboard and without the front (a WinForms form of its own never activated, Windows 11 Notepad and the Settings
/// search box behind a window of its own). Never runs in a suite: it is Explicit and also needs
/// BAXY_CU_TEXT_LIVE_CHECK=1. Run it only with the live turn (scripts/cu_live/turno.sh tomar: its agent lock first,
/// then no live.lock); it opens its own windows, never touches one it did not open (Notepad and Settings are skipped
/// when already running) and closes each by its exact process id. It prints one table row per delivery.
/// </summary>
[TestFixture]
[Explicit("Opens windows on the person's desktop.")]
[Category("LiveDesktop")]
public sealed partial class TextDeliveryLiveDesktopCheck
{
    private const string FormScript = """
        param([string]$Title,[switch]$Activate)
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -ReferencedAssemblies System.Windows.Forms -TypeDefinition @'
        public class BaxyQuietForm : System.Windows.Forms.Form {
          public bool Quiet = true;
          protected override bool ShowWithoutActivation { get { return Quiet; } }
        }
        '@
        $f=New-Object BaxyQuietForm
        $f.Quiet=-not $Activate
        $f.Text=$Title; $f.Width=440; $f.Height=260; $f.StartPosition='Manual'; $f.Left=60; $f.Top=60
        $box=New-Object System.Windows.Forms.TextBox; $box.Left=10; $box.Top=10; $box.Width=400
        $rich=New-Object System.Windows.Forms.RichTextBox; $rich.Left=10; $rich.Top=40; $rich.Width=400; $rich.Height=80
        $ok=New-Object System.Windows.Forms.Button; $ok.Text='Aceptar'; $ok.Left=10; $ok.Top=130
        $ok.Add_Click({ $f.Text=$f.Text+' aceptado' })
        $f.AcceptButton=$ok
        $f.Controls.AddRange(@($box,$rich,$ok))
        $f.ActiveControl=$box
        [System.Windows.Forms.Application]::Run($f)
        """;

    private readonly List<string> _rows = [];

    [Test]
    public async Task WhatEachWindowTakesWithoutTheFront()
    {
        if (Environment.GetEnvironmentVariable("BAXY_CU_TEXT_LIVE_CHECK") != "1")
            Assert.Ignore("BAXY_CU_TEXT_LIVE_CHECK=1 is needed to touch the desktop.");
        string script = Path.Combine(Path.GetTempPath(), "baxy-text-live-" + Guid.NewGuid().ToString("N") + ".ps1");
        await File.WriteAllTextAsync(script, FormScript, new UTF8Encoding(false));
        var opened = new List<Process>();
        try
        {
            await QuietFormAsync(script, opened);
            await NotepadAsync(script, opened);
            await SettingsAsync(script, opened);
        }
        finally
        {
            foreach (Process process in opened)
            {
                try
                {
                    if (!process.HasExited)
                        process.Kill();
                }
                catch (InvalidOperationException)
                {
                }

                process.Dispose();
            }

            File.Delete(script);
            TestContext.Out.WriteLine("| ventana | campo (clase) | camino | entregado | llegó | frente intacto | cursor intacto |");
            TestContext.Out.WriteLine("|---|---|---|---|---|---|---|");
            foreach (string row in _rows)
                TestContext.Out.WriteLine(row);
        }
    }

    // A form of its own that never took the front: its TextBox and RichTextBox, then Enter on the TextBox (its
    // AcceptButton renames the form: the key arrived) and Tab.
    private async Task QuietFormAsync(string script, List<Process> opened)
    {
        string title = "BAXY prueba texto " + Guid.NewGuid().ToString("N")[..6];
        Process form = StartForm(script, title, activate: false);
        opened.Add(form);
        nint window = await WaitWindowAsync(() => FindTopLevel(form.Id, title));
        var messages = new WindowsFieldMessages();
        var delivery = new WindowsTextDelivery(messages);
        nint edit = Children(window).FirstOrDefault(child => ClassOf(child).Contains(".EDIT.", StringComparison.OrdinalIgnoreCase));
        nint rich = Children(window).FirstOrDefault(child => ClassOf(child).Contains("RichEdit", StringComparison.OrdinalIgnoreCase));
        _rows.Add($"| WinForms sin activar | foco del hilo: {Describe(messages.FocusOf(window))} | — | — | — | — | — |");
        await TypeRowAsync("WinForms sin activar", delivery, window, edit, "hola mañana a las 5");
        await TypeRowAsync("WinForms sin activar", delivery, window, rich, "lista: pan, leche");
        await KeyRowAsync("WinForms sin activar", delivery, window, edit, "enter", 0x0D,
            () => WindowText(window).EndsWith("aceptado", StringComparison.Ordinal));
        int caret = messages.Selection(rich)?.Start ?? -1;
        await KeyRowAsync("WinForms sin activar", delivery, window, rich, "arrow_left", 0x25,
            () => messages.Selection(rich)?.Start == caret - 1);
    }

    // Windows 11 Notepad, opened here and then covered by an activated form of its own: the person's window in front.
    private async Task NotepadAsync(string script, List<Process> opened)
    {
        if (Process.GetProcessesByName("Notepad").Length > 0)
        {
            _rows.Add("| Bloc de notas | — | omitido: ya había uno abierto (no es nuestro) | — | — | — | — |");
            return;
        }

        DateTime launched = DateTime.Now;
        using (Process.Start(new ProcessStartInfo("notepad.exe") { UseShellExecute = true }))
        {
        }

        nint window = await WaitWindowAsync(() => Process.GetProcessesByName("Notepad")
            .Where(process => StartedSince(process, launched))
            .SelectMany(process => TopLevels(process.Id))
            .FirstOrDefault(hwnd => ClassOf(hwnd) == "Notepad"));
        _ = GetWindowThreadProcessId(window, out uint notepadId);
        opened.Add(Process.GetProcessById((int)notepadId));
        nint edit = await WaitWindowAsync(() => Children(window).FirstOrDefault(child => ClassOf(child).StartsWith("RichEdit", StringComparison.OrdinalIgnoreCase)));
        Process cover = StartForm(script, "BAXY tapa " + Guid.NewGuid().ToString("N")[..6], activate: true);
        opened.Add(cover);
        await Task.Delay(1500);
        var messages = new WindowsFieldMessages();
        var delivery = new WindowsTextDelivery(messages);
        _rows.Add($"| Bloc de notas de fondo | foco del hilo: {Describe(messages.FocusOf(window))} | — | — | — | — | —|");
        await TypeRowAsync("Bloc de notas de fondo", delivery, window, edit, "Querido Ron: mañana a las 5");
        int before = messages.TextLength(edit);
        await KeyRowAsync("Bloc de notas de fondo", delivery, window, edit, "enter", 0x0D, () => messages.TextLength(edit) > before);
        // What was written goes away before the window is closed: Notepad keeps unsaved tabs for its next start.
        nint empty = Marshal.StringToHGlobalUni(string.Empty);
        try
        {
            _ = SendMessageTimeoutW(edit, 0x000C, 0, empty, 2, 2000, out _);
        }
        finally
        {
            Marshal.FreeHGlobal(empty);
        }
    }

    // The Settings search box (XAML, no window of its own): only UI Automation's SetValue reaches it.
    private async Task SettingsAsync(string script, List<Process> opened)
    {
        if (Process.GetProcessesByName("SystemSettings").Length > 0)
        {
            _rows.Add("| Configuración | — | omitido: ya estaba abierta (no es nuestra) | — | — | — | — |");
            return;
        }

        DateTime launched = DateTime.Now;
        using (Process.Start(new ProcessStartInfo("ms-settings:") { UseShellExecute = true }))
        {
        }

        Process settings = null!;
        nint frame = await WaitWindowAsync(() =>
        {
            Process? running = Process.GetProcessesByName("SystemSettings").FirstOrDefault(process => StartedSince(process, launched));
            if (running is null)
                return 0;
            settings = running;
            return AllTopLevels().FirstOrDefault(hwnd => ClassOf(hwnd) == "ApplicationFrameWindow"
                && Children(hwnd).Any(child => ProcessOf(child) == running.Id));
        });
        opened.Add(settings);
        Process cover = StartForm(script, "BAXY tapa " + Guid.NewGuid().ToString("N")[..6], activate: true);
        opened.Add(cover);
        await Task.Delay(2500);
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        using var host = new UiaWorkerHost(worker);
        string? search = null;
        for (int attempt = 0; attempt < 10 && search is null; attempt++)
        {
            using JsonDocument? view = await host.SendAsync(
                $$"""{"cmd":"view","hwnd":{{frame}},"limit":60}""", TimeSpan.FromSeconds(20), CancellationToken.None);
            if (view?.RootElement.TryGetProperty("controls", out JsonElement controls) == true)
            {
                search = controls.EnumerateArray()
                    .Where(control => control.GetProperty("kind").GetString() == "Edit")
                    .Select(control => control.GetProperty("id").GetString())
                    .FirstOrDefault(id => !string.IsNullOrEmpty(id));
            }

            if (search is null)
                await Task.Delay(1000);
        }

        if (search is null)
        {
            _rows.Add("| Configuración de fondo | — | sin campo Edit en la vista | — | — | — | — |");
            return;
        }

        // The cover must hold the front before the measure: Settings may still be activating after its launch.
        for (int attempt = 0; attempt < 20 && ProcessOf(GetForegroundWindow()) != cover.Id; attempt++)
            await Task.Delay(250);
        nint front = GetForegroundWindow();
        _ = GetCursorPos(out Point cursor);
        using JsonDocument? answer = await host.SendAsync(
            JsonSerializer.Serialize(new { cmd = "field", hwnd = (long)frame, controlId = search, text = "mouse" }),
            TimeSpan.FromSeconds(20), CancellationToken.None);
        _ = GetCursorPos(out Point after);
        string method = answer?.RootElement.TryGetProperty("method", out JsonElement m) == true ? m.GetString() ?? "" : "sin respuesta";
        bool delivered = answer?.RootElement.TryGetProperty("delivered", out JsonElement d) == true && d.GetBoolean();
        string fieldClass = answer?.RootElement.TryGetProperty("className", out JsonElement c) == true ? c.GetString() ?? "" : "";
        await Task.Delay(800);
        nint frontAfter = GetForegroundWindow();
        string fronts = frontAfter == front
            ? Yes(true)
            : $"no ({Describe(front)} pid {ProcessOf(front)} → {Describe(frontAfter)} pid {ProcessOf(frontAfter)}; tapa pid {cover.Id}, Configuración pid {settings.Id})";
        _rows.Add($"| Configuración de fondo | buscador ({fieldClass}) | {(method.Length > 0 ? method : "ninguno")} | {Yes(delivered)} | {Yes(delivered)} (valor releído) | {fronts} | {Yes(cursor.Equals(after))} |");
    }

    private async Task TypeRowAsync(string place, WindowsTextDelivery delivery, nint window, nint field, string text)
    {
        if (field == 0)
        {
            _rows.Add($"| {place} | sin campo | — | — | — | — | — |");
            return;
        }

        nint front = GetForegroundWindow();
        _ = GetCursorPos(out Point cursor);
        FieldDelivery? result = await delivery.TypeAsync(delivery.Messages.Identity(window), field, text, CancellationToken.None);
        _ = GetCursorPos(out Point after);
        string? content = delivery.Messages.Text(field, delivery.Messages.TextLength(field));
        bool arrived = content?.Contains(text, StringComparison.Ordinal) == true;
        _rows.Add($"| {place} | {ClassOf(field)} | {result?.Method ?? "ninguno (teclado)"} | {Yes(result?.Delivered == true)} | {Yes(arrived)} | {Yes(GetForegroundWindow() == front)} | {Yes(cursor.Equals(after))} |");
    }

    private async Task KeyRowAsync(
        string place, WindowsTextDelivery delivery, nint window, nint field, string key, ushort virtualKey, Func<bool> arrived)
    {
        if (field == 0)
            return;
        nint front = GetForegroundWindow();
        _ = GetCursorPos(out Point cursor);
        FieldDelivery? result = delivery.Press(delivery.Messages.Identity(window), field, key, virtualKey);
        await Task.Delay(400);
        _ = GetCursorPos(out Point after);
        _rows.Add($"| {place} | tecla {key} → {ClassOf(field)} | {result?.Method ?? "ninguno (teclado)"} | {Yes(result?.Delivered == true)} | {Yes(arrived())} | {Yes(GetForegroundWindow() == front)} | {Yes(cursor.Equals(after))} |");
    }

    private static string Yes(bool value) => value ? "sí" : "no";

    private static string Describe(nint hwnd) => hwnd == 0 ? "ninguno" : ClassOf(hwnd);

    private static bool StartedSince(Process process, DateTime since)
    {
        try
        {
            return process.StartTime >= since.AddSeconds(-2);
        }
        catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            return false;
        }
    }

    private static Process StartForm(string script, string title, bool activate)
    {
        var start = new ProcessStartInfo("powershell.exe")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        foreach (string argument in new[] { "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-File", script, "-Title", title })
            start.ArgumentList.Add(argument);
        if (activate)
            start.ArgumentList.Add("-Activate");
        return Process.Start(start) ?? throw new InvalidOperationException("powershell did not start");
    }

    private static async Task<nint> WaitWindowAsync(Func<nint> find)
    {
        for (int attempt = 0; attempt < 60; attempt++)
        {
            nint found = find();
            if (found != 0)
                return found;
            await Task.Delay(250);
        }

        throw new AssertionException("the window did not appear");
    }

    private static nint FindTopLevel(int processId, string title) =>
        TopLevels(processId).FirstOrDefault(hwnd => WindowText(hwnd) == title);

    private static IEnumerable<nint> TopLevels(int processId) =>
        AllTopLevels().Where(hwnd => ProcessOf(hwnd) == processId);

    private static List<nint> AllTopLevels()
    {
        var found = new List<nint>();
        _ = EnumWindows((hwnd, _) =>
        {
            if (IsWindowVisible(hwnd))
                found.Add(hwnd);
            return true;
        }, 0);
        return found;
    }

    private static List<nint> Children(nint parent)
    {
        var found = new List<nint>();
        _ = EnumChildWindows(parent, (hwnd, _) =>
        {
            found.Add(hwnd);
            return true;
        }, 0);
        return found;
    }

    private static int ProcessOf(nint hwnd)
    {
        _ = GetWindowThreadProcessId(hwnd, out uint processId);
        return (int)processId;
    }

    private static string ClassOf(nint hwnd) => new WindowsFieldMessages().ClassName(hwnd);

    private static string WindowText(nint hwnd)
    {
        char[] text = new char[512];
        int length = GetWindowTextW(hwnd, text, text.Length);
        return length <= 0 ? string.Empty : new string(text, 0, length);
    }

    private delegate bool EnumProc(nint hwnd, nint parameter);

    [StructLayout(LayoutKind.Sequential)]
    private struct Point
    {
        public int X;
        public int Y;
    }

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern bool GetCursorPos(out Point point);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumProc callback, nint parameter);

    [DllImport("user32.dll")]
    private static extern bool EnumChildWindows(nint parent, EnumProc callback, nint parameter);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(nint hwnd);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint hwnd, out uint processId);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowTextW(nint hwnd, [Out] char[] text, int count);

    [DllImport("user32.dll")]
    private static extern nint SendMessageTimeoutW(
        nint hwnd, uint message, nint wParam, nint lParam, uint flags, uint timeout, out nint result);
}
