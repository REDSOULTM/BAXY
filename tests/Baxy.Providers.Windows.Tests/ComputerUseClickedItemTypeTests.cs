using System.Reflection;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C11): a click by the index of the last look says what the pressed item is (its «itemType», «Encabezado
/// de columna»). Only when that index's control is the one pressed: an index whose control the label does not name, or
/// an index of a look of another window, leaves the label to its cascade, and what the cascade pressed is not that
/// control. Every effect goes to fakes: no window is touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseClickedItemTypeTests
{
    private const nint Window = 4660;

    private const string NotFound =
        "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_not_found\"," +
        "\"name\":\"\",\"controlIdentity\":\"\",\"absentOrDisabled\":false}";

    [TestCase("""{"label":"Aceptar","index":3,"window":4660}""", TestName = "AnIndexTheLabelDoesNotNameGivesNoItemType")]
    [TestCase("""{"label":"A","index":3,"window":9999}""", TestName = "AnIndexOfAnotherWindowsLookGivesNoItemType")]
    public async Task TheItemTypeIsOnlyOfTheIndexsControlWhenItWasThePressedOne(string click)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFound);
        var adapter = new WindowsVisibleControlAdapter(worker, new HittingLocator(), null);
        RememberView(adapter,
        [
            new WindowsVisibleControlAdapter.ViewControl
            {
                Index = 3, Id = "1.3", Kind = "DataItem", Name = "A", State = "", ItemType = "Encabezado de columna",
            },
        ]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", JsonDocument.Parse(click).RootElement.Clone(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, "the label was pressed by its cascade");
            Assert.That(receipt.Result?.GetProperty("cascadeStage").GetString(), Is.EqualTo("ocr"));
            Assert.That(receipt.Result?.TryGetProperty("itemType", out _), Is.False,
                "the item type of a control that was not pressed");
        });
    }

    // Contracase: the index's control, named by the label, on the look's own window, says its item type.
    [Test]
    public async Task TheIndexsOwnControlPressedSaysItsItemType()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"A\"," +
            "\"controlIdentity\":\"1.3\",\"absentOrDisabled\":false,\"selected\":true}");
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, capture: Capture);
        RememberView(adapter,
        [
            new WindowsVisibleControlAdapter.ViewControl
            {
                Index = 3, Id = "1.3", Kind = "DataItem", Name = "A", State = "", ItemType = "Encabezado de columna",
            },
        ]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", JsonDocument.Parse("""{"label":"A","index":3,"window":4660}""").RootElement.Clone(),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("itemType").GetString(), Is.EqualTo("Encabezado de columna"));
        });
    }

    private static void RememberView(
        WindowsVisibleControlAdapter adapter, IReadOnlyList<WindowsVisibleControlAdapter.ViewControl> controls)
    {
        FieldInfo field = typeof(WindowsVisibleControlAdapter).GetField(
            "_lastView", BindingFlags.NonPublic | BindingFlags.Instance)!;
        object view = Activator.CreateInstance(
            field.FieldType, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance, null,
            [Window, controls], null)!;
        field.SetValue(adapter, view);
    }

    private sealed class HittingLocator : IVisibleControlLocator
    {
        public string Stage => "ocr";

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation, string label, CancellationToken cancellationToken)
        {
            JsonElement result = JsonDocument.Parse(
                "{\"version\":1,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"" + label + "\"," +
                "\"controlIdentity\":\"ocr.1\",\"absentOrDisabled\":false,\"selected\":false," +
                "\"surfaceChanged\":true,\"cascadeStage\":\"ocr\",\"authority\":\"ocr_locate_click_postread\"}")
                .RootElement.Clone();
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(
                new ExternalCapabilityReceipt(operation, true, true, result, null));
        }
    }
}
