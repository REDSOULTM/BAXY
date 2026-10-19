using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// FT/proveedores goal (E2) on the real desktop: a text typed with no window into a blank Word document in front is read
/// back by UI Automation (Word's «_WwG» document has no Win32 edit control, so before the fix it was always
/// input_text_not_read_back), and the document holds it. Never runs in a suite: Explicit and BAXY_WORD_READBACK_LIVE=1,
/// only while no one uses the desktop; the Word it starts is closed without saving.
/// </summary>
[TestFixture]
[Explicit("Opens Word on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class WordReadBackLiveDesktopCheck
{
    [Test]
    public async Task ATextTypedIntoABlankWordDocumentIsReadBack()
    {
        if (Environment.GetEnvironmentVariable("BAXY_WORD_READBACK_LIVE") != "1")
            Assert.Ignore("BAXY_WORD_READBACK_LIVE=1 is needed to touch the desktop.");
        const string text = "hola desde baxy";
        Type? progId = Type.GetTypeFromProgID("Word.Application");
        Assert.That(progId, Is.Not.Null, "Word is not installed");
        dynamic word = Activator.CreateInstance(progId!)!;
        try
        {
            word.Visible = true;
            dynamic document = word.Documents.Add();
            word.Activate();
            await Task.Delay(3000);
            dynamic shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell")!)!;
            shell.AppActivate((string)word.ActiveWindow.Caption);
            await Task.Delay(1500);
            _ = GetWindowThreadProcessId(GetForegroundWindow(), out uint front);
            using Process inFront = Process.GetProcessById((int)front);
            Assert.That(inFront.ProcessName, Is.EqualTo("WINWORD"), "Word must be in front for this check");

            using var uia = new UiaWorkerHost();
            var visible = new WindowsVisibleControlAdapter(uia);
            var adapter = new WindowsDesktopInteractionAdapter(visible);
            using JsonDocument arguments = JsonDocument.Parse($$"""{"text":"{{text}}"}""");
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "input.text.type", arguments.RootElement, CancellationToken.None);
            await Task.Delay(500);
            string held = (string)document.Content.Text;
            TestContext.Out.WriteLine($"verified={receipt.Verified} error={receipt.ErrorCode} result={receipt.Result}");
            TestContext.Out.WriteLine($"document={held.Trim()}");
            Assert.Multiple(() =>
            {
                // Word's AutoCorrect puts a capital on the sentence's first letter (as the provider compares it).
                Assert.That(held, Does.Contain(text[1..]), "the text is in the document");
                Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
                Assert.That(receipt.Result?.GetProperty("readBack").GetBoolean(), Is.True);
                Assert.That(receipt.Result?.GetRawText(), Does.Contain("uia"), "read back by UI Automation");
            });
        }
        finally
        {
            int[] before = [.. Process.GetProcessesByName("WINWORD").Select(static process => process.Id)];
            try
            {
                word.Quit(0);
            }
            catch (Exception exception) when (exception is COMException
                or Microsoft.CSharp.RuntimeBinder.RuntimeBinderException)
            {
            }

            await Task.Delay(2000);
            // A Word that did not close is ended by its process id (this check started it; nothing is saved).
            foreach (Process left in Process.GetProcessesByName("WINWORD").Where(process => before.Contains(process.Id)))
                using (left)
                    left.Kill();
        }
    }

    // FT/proveedores goal (E2, review): two documents are one WINWORD process; the caret of the one in front is not read
    // for the other's window.
    [Test]
    public async Task TheCaretOfAnotherDocumentOfTheSameWordIsNotRead()
    {
        if (Environment.GetEnvironmentVariable("BAXY_WORD_READBACK_LIVE") != "1")
            Assert.Ignore("BAXY_WORD_READBACK_LIVE=1 is needed to touch the desktop.");
        Type? progId = Type.GetTypeFromProgID("Word.Application");
        Assert.That(progId, Is.Not.Null, "Word is not installed");
        dynamic word = Activator.CreateInstance(progId!)!;
        try
        {
            word.Visible = true;
            dynamic first = word.Documents.Add();
            nint behind = (nint)(int)first.ActiveWindow.Hwnd;
            dynamic second = word.Documents.Add();
            second.Content.Text = "segundo documento";
            second.Activate();
            await Task.Delay(3000);
            nint front = (nint)(int)second.ActiveWindow.Hwnd;
            dynamic shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell")!)!;
            shell.AppActivate((string)second.ActiveWindow.Caption);
            await Task.Delay(1500);
            _ = GetWindowThreadProcessId(front, out uint process);

            using var uia = new UiaWorkerHost();
            var visible = new WindowsVisibleControlAdapter(uia);
            using JsonDocument? other = await visible.CaretTextAsync(behind, (int)process, 8192, CancellationToken.None);
            using JsonDocument? own = await visible.CaretTextAsync(front, (int)process, 8192, CancellationToken.None);
            TestContext.Out.WriteLine($"behind={other?.RootElement.GetRawText()} front={own?.RootElement.GetRawText()}");
            Assert.Multiple(() =>
            {
                Assert.That(GetForegroundWindow(), Is.EqualTo(front), "the second document must be in front");
                Assert.That(other?.RootElement.GetProperty("ok").GetBoolean(), Is.False);
                Assert.That(other?.RootElement.GetProperty("error").GetString(), Is.EqualTo("caret_window_mismatch"));
                Assert.That(own?.RootElement.GetProperty("ok").GetBoolean(), Is.True);
                Assert.That(own?.RootElement.GetProperty("text").GetString(), Does.Contain("segundo documento"));
            });
        }
        finally
        {
            int[] before = [.. Process.GetProcessesByName("WINWORD").Select(static process => process.Id)];
            try
            {
                word.Quit(0);
            }
            catch (Exception exception) when (exception is COMException
                or Microsoft.CSharp.RuntimeBinder.RuntimeBinderException)
            {
            }

            await Task.Delay(2000);
            foreach (Process left in Process.GetProcessesByName("WINWORD").Where(process => before.Contains(process.Id)))
                using (left)
                    left.Kill();
        }
    }

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(nint window, out uint processId);
}
