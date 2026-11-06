using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real 02-11 (encargo 2, A) on the real desktop, in a spreadsheet: a value typed by the product's adapter into a
/// cell whose edit is open (left by typing, here sent to the sheet's window as characters, never by the keyboard) is not
/// told verified, and nothing is written into it; the edit, confirmed afterwards, keeps what was being edited. A cell
/// that holds text and is not the active one says so when it is not reached. Never runs in a suite: Explicit,
/// BAXY_CELLS_LIVE=1 and BAXY_CELLS_BOOK (a blank workbook in a temporary folder of the caller's); the spreadsheet it
/// opens is ended by its process id, nothing saved. It needs no front: every write goes by UI Automation or messages.
/// </summary>
[TestFixture]
[Explicit("Opens a spreadsheet on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class SpreadsheetCellsLiveDesktopCheck
{
    private const string Spreadsheet = @"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE";
    private const uint Char = 0x0102;
    private const uint KeyDown = 0x0100;
    private const uint KeyUp = 0x0101;

    [Test]
    public async Task ACellWhoseEditIsOpenIsNotToldVerified()
    {
        string? book = Environment.GetEnvironmentVariable("BAXY_CELLS_BOOK");
        if (Environment.GetEnvironmentVariable("BAXY_CELLS_LIVE") != "1" || book is null || !File.Exists(book))
            Assert.Ignore("BAXY_CELLS_LIVE=1 and BAXY_CELLS_BOOK are needed to touch the desktop.");
        using Process opened = Process.Start(new ProcessStartInfo(Spreadsheet) { ArgumentList = { "/x", book! } })!;
        try
        {
            string title = Path.GetFileNameWithoutExtension(book!);
            for (int wait = 0; wait < 80 && !(opened.MainWindowHandle != 0 && opened.MainWindowTitle.Contains(title)); wait++)
            {
                await Task.Delay(500);
                opened.Refresh();
            }

            nint window = opened.MainWindowHandle;
            Assert.That(window, Is.Not.EqualTo((nint)0), "the spreadsheet's window");
            await Task.Delay(3000);
            nint sheet = ChildOfClass(window, "EXCEL7");
            Assert.That(sheet, Is.Not.EqualTo((nint)0), "the sheet's window");
            using var uia = new UiaWorkerHost();
            var visible = new WindowsVisibleControlAdapter(uia);
            var adapter = new WindowsDesktopInteractionAdapter(visible);

            async Task<Dictionary<string, (int Index, string Value)>> LookAsync(string tag)
            {
                using JsonDocument arguments = JsonDocument.Parse("""{"application":"Excel","limit":60}""");
                ExternalCapabilityReceipt look = await visible.InvokeAsync("input.visible.controls", arguments.RootElement,
                    CancellationToken.None);
                var cells = new Dictionary<string, (int, string)>(StringComparer.Ordinal);
                if (look.Result is { } result && result.TryGetProperty("controls", out JsonElement controls))
                {
                    foreach (JsonElement control in controls.EnumerateArray())
                    {
                        string kind = control.TryGetProperty("kind", out JsonElement typed) ? typed.GetString() ?? "" : "";
                        if (kind is not ("DataItem" or "Edit"))
                            continue;
                        string name = control.GetProperty("name").GetString() ?? "";
                        string value = control.TryGetProperty("value", out JsonElement held) ? held.ToString() : "";
                        cells[name] = (control.GetProperty("i").GetInt32(), value);
                    }
                }

                TestContext.Out.WriteLine($"look {tag}: error={look.ErrorCode} " + string.Join(" | ", cells
                    .Where(cell => cell.Key is "A1" or "B1" or "Editar celda")
                    .Select(cell => $"{cell.Key}#{cell.Value.Item1}=«{cell.Value.Item2}»")));
                return cells;
            }

            async Task<ExternalCapabilityReceipt> TypeAsync(string text, string cell)
            {
                Dictionary<string, (int Index, string Value)> cells = await LookAsync("before " + text);
                Assert.That(cells.ContainsKey(cell), Is.True, $"no {cell} in the look");
                using JsonDocument arguments = JsonDocument.Parse(
                    $$"""{"text":"{{text}}","window":{{window}},"index":{{cells[cell].Index}}}""");
                ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("input.text.type", arguments.RootElement,
                    CancellationToken.None);
                TestContext.Out.WriteLine(
                    $"type «{text}» at {cell} -> verified={receipt.Verified} error={receipt.ErrorCode} result={receipt.Result}");
                return receipt;
            }

            ExternalCapabilityReceipt first = await TypeAsync("alfa", "A1");
            // An edit opened in the active cell A1 and left open, as typing into it leaves it.
            foreach (char character in "beta")
                _ = PostMessage(sheet, Char, character, 1);
            await Task.Delay(800);
            ExternalCapabilityReceipt intoOpenEdit = await TypeAsync("gamma", "A1");
            _ = PostMessage(sheet, KeyDown, 0x0D, 0x001C0001);
            _ = PostMessage(sheet, KeyUp, 0x0D, unchecked((nint)0xC01C0001));
            await Task.Delay(800);
            string confirmed = (await LookAsync("after Enter")).GetValueOrDefault("A1").Value ?? "";
            ExternalCapabilityReceipt other = await TypeAsync("delta", "B1");
            ExternalCapabilityReceipt notActive = await TypeAsync("epsilon", "A1");
            string end = (await LookAsync("end")).GetValueOrDefault("A1").Value ?? "";

            Assert.Multiple(() =>
            {
                Assert.That(first.Verified, Is.True, "an empty cell takes its value");
                Assert.That(confirmed, Is.EqualTo("beta"), "the edit confirmed keeps what was being edited");
                Assert.That(intoOpenEdit.Verified, Is.False, $"«gamma» told verified while A1 ended «{confirmed}»");
                Assert.That(intoOpenEdit.ErrorCode, Is.EqualTo("input_edit_not_confirmed"));
                Assert.That(intoOpenEdit.EffectMayHaveOccurred, Is.False);
                Assert.That(intoOpenEdit.Result?.GetProperty("editPending").GetBoolean(), Is.True);
                Assert.That(other.Verified, Is.True, "another empty cell takes its value (and becomes the active one)");
                Assert.That(notActive.ErrorCode, Is.EqualTo("input_field_not_reachable"));
                Assert.That(notActive.Result?.GetProperty("fieldHasText").GetBoolean(), Is.True);
                Assert.That(notActive.Result?.GetProperty("textSelected").GetBoolean(), Is.False);
                Assert.That(end, Is.EqualTo("beta"), "nothing was written into A1 after its edit");
            });
        }
        finally
        {
            if (!opened.HasExited)
                opened.Kill();
        }
    }

    private static nint ChildOfClass(nint parent, string className)
    {
        nint found = 0;
        _ = EnumChildWindows(parent, (child, _) =>
        {
            char[] name = new char[64];
            int length = GetClassName(child, name, name.Length);
            if (new string(name, 0, Math.Max(length, 0)) != className)
                return true;
            found = child;
            return false;
        }, 0);
        return found;
    }

    private delegate bool ChildProcedure(nint child, nint parameter);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumChildWindows(nint parent, ChildProcedure procedure, nint parameter);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassName(nint window, [Out] char[] name, int capacity);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool PostMessage(nint window, uint message, nint wParam, nint lParam);
}
