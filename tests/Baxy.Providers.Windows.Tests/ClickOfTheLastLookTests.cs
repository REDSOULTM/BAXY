using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Contracts;
using NUnit.Framework;
using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.Tests;

// Cosecha 05-11 (uso real): with BAXY's own window in front, «PLATEA BAJA» with the index of the look at the browser and no
// window came back protected_window, and the model told «la ventana de Opera está protegida por BAXY». The catalog says a
// click with index acts in the window of the last look, and the adapter does: only the gate judged the window in front.
[TestFixture]
[NonParallelizable]
public sealed class ClickOfTheLastLookTests
{
    private const string View =
        "\"controls\":[{\"kind\":\"Button\",\"name\":\"Comprar\",\"id\":\"9.1\",\"state\":\"\",\"value\":null,"
        + "\"rect\":{\"x\":10,\"y\":10,\"w\":80,\"h\":24},\"repeated\":0}],\"controlCount\":1,\"focused\":null}";

    [Test]
    public void AClickWithTheLooksIndexIsJudgedOnThatLooksWindow()
    {
        (ExternalCapabilityReceipt receipt, IReadOnlyList<nint> judged, nint looked) =
            Click("""{"label":"Comprar","index":0}""", refuseFront: true);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("protected_window"));
            Assert.That(judged, Is.EqualTo(new[] { looked }));
        });
    }

    [Test]
    public void TheWindowOfTheLookIsRefusedWhenItIsTheProtectedOne()
    {
        (ExternalCapabilityReceipt receipt, _, _) = Click("""{"label":"Comprar","index":0}""", refuseFront: false, refuseLooked: true);

        Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
    }

    [Test]
    public void AClickWithNoIndexForALabelNoLookShowedIsStillJudgedOnTheWindowInFront()
    {
        (ExternalCapabilityReceipt receipt, IReadOnlyList<nint> judged, _) =
            Click("""{"label":"Otra cosa"}""", refuseFront: true);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(judged, Is.EqualTo(new nint[] { 0 }));
        });
    }

    [Test]
    public void AnIndexNoLookHandedOutIsStillJudgedOnTheWindowInFront()
    {
        (ExternalCapabilityReceipt receipt, IReadOnlyList<nint> judged, _) =
            Click("""{"label":"Comprar","index":40}""", refuseFront: true);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(judged, Is.EqualTo(new nint[] { 0 }));
        });
    }

    [Test]
    public void ALookWhoseWindowIsGoneIsNotJudgedOnThatWindow()
    {
        (ExternalCapabilityReceipt receipt, IReadOnlyList<nint> judged, _) =
            Click("""{"label":"Comprar","index":0}""", refuseFront: true, closeTheLookedWindow: true);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("protected_window"));
            Assert.That(judged, Is.EqualTo(new nint[] { 0 }));
        });
    }

    // Revisión ciega de C2025: the window looked at was closed, the index still resolves in that look, and the window in
    // front is another: nothing of that look may be pressed there.
    [Test]
    public void AnIndexOfAWindowThatClosedPressesNothingInTheWindowInFront()
    {
        nint window = CreateWindowEx(0x08000080, "STATIC", "BAXY look fixture", 0x90000000u, -31000, -31000, 400, 300, 0, 0, 0, 0);
        nint front = CreateWindowEx(0x08000080, "STATIC", "BAXY front fixture", 0x90000000u, -31000, -31000, 400, 300, 0, 0, 0, 0);
        Assert.That(window != 0 && front != 0, Is.True, $"CreateWindowEx failed: {Marshal.GetLastPInvokeError()}");
        try
        {
            string answer = "{\"ok\":true,\"error\":\"\",\"hwnd\":" + (long)window + ",\"window\":\"Tienda\"," + View;
            var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(answer);
            var adapter = new WindowsVisibleControlAdapter(worker, null, null, requestedWindow: (_, _) => ValueTask.FromResult(window))
            {
                WindowInFront = _ => ValueTask.FromResult(front),
            };
            _ = ComputerUseSpeedTests.Pumped(() => adapter.InvokeAsync(
                "input.visible.controls", JsonDocument.Parse("""{"application":"la tienda"}""").RootElement.Clone(),
                CancellationToken.None).AsTask());
            int looked = worker.Commands.Count;
            _ = DestroyWindow(window);

            ExternalCapabilityReceipt receipt = ComputerUseSpeedTests.Pumped(() => adapter.InvokeAsync(
                "input.visible.click", JsonDocument.Parse("""{"label":"Comprar","index":0}""").RootElement.Clone(),
                CancellationToken.None).AsTask());

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.False);
                Assert.That(worker.Commands.Skip(looked), Is.Empty, "nothing goes to the worker for that click");
                Assert.That(receipt.ErrorCode, Is.EqualTo("visible_control_identity_stale"));
                Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.Contain("has closed"));
            });
        }
        finally
        {
            _ = DestroyWindow(window);
            _ = DestroyWindow(front);
        }
    }

    [Test]
    public void AClickThatNamesItsWindowIsJudgedOnThatOne()
    {
        (ExternalCapabilityReceipt receipt, IReadOnlyList<nint> judged, _) =
            Click("""{"label":"Comprar","index":0,"window":424242}""", refuseFront: true);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("protected_window"));
            Assert.That(judged, Is.EqualTo(new nint[] { 424242 }));
        });
    }

    // The gate is told the arguments as the seams get them: the window of those arguments, 0 for «the one in front».
    private static (ExternalCapabilityReceipt Receipt, IReadOnlyList<nint> Judged, nint Looked) Click(
        string arguments, bool refuseFront, bool refuseLooked = false, bool closeTheLookedWindow = false)
    {
        nint window = CreateWindowEx(0x08000080, "STATIC", "BAXY look fixture", 0x90000000u, -31000, -31000, 400, 300, 0, 0, 0, 0);
        Assert.That(window != 0, Is.True, $"CreateWindowEx failed: {Marshal.GetLastPInvokeError()}");
        try
        {
            var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
                "{\"ok\":true,\"error\":\"\",\"hwnd\":" + (long)window + ",\"window\":\"Tienda\"," + View);
            var adapter = new WindowsVisibleControlAdapter(worker, null, null, requestedWindow: (_, _) => ValueTask.FromResult(window));
            _ = ComputerUseSpeedTests.Pumped(() => adapter.InvokeAsync(
                "input.visible.controls", JsonDocument.Parse("""{"application":"la tienda"}""").RootElement.Clone(),
                CancellationToken.None).AsTask());
            if (closeTheLookedWindow)
                _ = DestroyWindow(window);
            var judged = new List<nint>();
            using var provider = new WindowsExternalCapabilityProvider(
                [adapter],
                actRefused: (_, given) =>
                {
                    nint target = WindowsExternalCapabilityProvider.MissionWindow(given);
                    judged.Add(target);
                    return target == 0 ? refuseFront : refuseLooked && target == window;
                });
            ExternalCapabilityReceipt receipt = ComputerUseSpeedTests.Pumped(() => provider.InvokeAsync(
                "input.visible.click", JsonDocument.Parse(arguments).RootElement.Clone(), CancellationToken.None).AsTask());
            return (receipt, judged, window);
        }
        finally
        {
            _ = DestroyWindow(window);
        }
    }

    [DllImport("user32.dll", EntryPoint = "CreateWindowExW", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    private static extern nint CreateWindowEx(uint extendedStyle, string className, string title, uint style, int x, int y,
        int width, int height, nint parent, nint menu, nint instance, nint parameter);

    [DllImport("user32.dll", ExactSpelling = true)]
    private static extern bool DestroyWindow(nint window);
}
