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

        JsonElement facts = OperationOutcomeNarration.AssertFacts(
            "peripheral.list",
            OperationOutcome.Success(result));
        JsonElement device = facts.GetProperty("observed").GetProperty("devices")[0];

        Assert.Multiple(() =>
        {
            Assert.That(device.GetProperty("name").GetString(), Is.EqualTo("USB Camera"));
            Assert.That(device.TryGetProperty("deviceId", out _), Is.False);
            Assert.That(facts.GetRawText(), Does.Not.Contain("usb_private"));
        });
    }

    [Test]
    public void VerifiedMouseInventoryNamesOnlyObservedPointingDevices()
    {
        JsonElement result = JsonDocument.Parse("""
            {"version":1,"devices":[{"deviceId":"mouse_private","kind":"mouse","name":"ELAN1203 (Dispositivo HID I2C)","status":"OK"}],"requestedKind":"mouse","authority":"windows_print_wia_usb_hid_inventory"}
            """).RootElement.Clone();

        JsonElement facts = OperationOutcomeNarration.AssertFacts(
            "peripheral.list",
            OperationOutcome.Success(result));
        JsonElement observed = facts.GetProperty("observed");
        JsonElement device = observed.GetProperty("devices")[0];

        Assert.Multiple(() =>
        {
            Assert.That(
                device.GetProperty("name").GetString(),
                Is.EqualTo("ELAN1203 (Dispositivo HID I2C)"));
            Assert.That(observed.GetProperty("requestedKind").GetString(), Is.EqualTo("mouse"));
            Assert.That(device.TryGetProperty("deviceId", out _), Is.False);
            Assert.That(facts.GetRawText(), Does.Not.Contain("mouse_private"));
        });
    }
}
