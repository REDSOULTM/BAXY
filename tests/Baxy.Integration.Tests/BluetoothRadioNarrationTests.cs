using System.Text.Json;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class BluetoothRadioNarrationTests
{
    [TestCase(true, "Listo, Bluetooth está encendido y verificado.")]
    [TestCase(false, "Listo, Bluetooth está apagado y verificado.")]
    public void VerifiedBluetoothRadioStateIsNamed(bool state, string expected)
    {
        JsonElement result = JsonDocument.Parse(
            $$"""{"version":1,"state":{{state.ToString().ToLowerInvariant()}},"radioCount":1,"authority":"windows_radio_api_postread"}""")
            .RootElement.Clone();

        string narration = OperationOutcomeNarration.For(
            "bluetooth.radio.set",
            OperationOutcome.Success(result));

        Assert.That(narration, Is.EqualTo(expected));
    }
}
