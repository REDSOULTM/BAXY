using System.Text.Json;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class PeripheralNarrationTests
{
    [Test]
    public void VerifiedPeripheralListNamesObservedUsbDevicesWithoutOpaqueIds()
    {
        JsonElement result = JsonDocument.Parse("""
            {"version":1,"devices":[{"deviceId":"usb_private","kind":"usb","name":"USB Camera","status":"OK"}],"authority":"windows_print_wia_usb_inventory"}
            """).RootElement.Clone();

        string narration = OperationOutcomeNarration.For(
            "peripheral.list",
            OperationOutcome.Success(result));

        Assert.Multiple(() =>
        {
            Assert.That(narration, Is.EqualTo("Periféricos conectados: USB Camera."));
            Assert.That(narration, Does.Not.Contain("usb_private"));
        });
    }

    [Test]
    public void VerifiedMouseInventoryNamesOnlyObservedPointingDevices()
    {
        JsonElement result = JsonDocument.Parse("""
            {"version":1,"devices":[{"deviceId":"mouse_private","kind":"mouse","name":"ELAN1203 (Dispositivo HID I2C)","status":"OK"}],"requestedKind":"mouse","authority":"windows_print_wia_usb_hid_inventory"}
            """).RootElement.Clone();

        string narration = OperationOutcomeNarration.For(
            "peripheral.list",
            OperationOutcome.Success(result));

        Assert.Multiple(() =>
        {
            Assert.That(narration, Is.EqualTo(
                "Mouse y dispositivos apuntadores detectados: ELAN1203 (Dispositivo HID I2C)."));
            Assert.That(narration, Does.Not.Contain("mouse_private"));
        });
    }
}
