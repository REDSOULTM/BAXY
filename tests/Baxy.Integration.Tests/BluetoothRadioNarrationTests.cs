using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class BluetoothRadioNarrationTests
{
    [TestCase(true)]
    [TestCase(false)]
    public void VerifiedBluetoothRadioStateIsNamed(bool state)
    {
        JsonElement result = JsonDocument.Parse(
            $$"""{"version":1,"state":{{state.ToString().ToLowerInvariant()}},"radioCount":1,"authority":"windows_radio_api_postread"}""")
            .RootElement.Clone();

        string narration = OperationOutcomeNarration.For(
            "bluetooth.radio.set",
            OperationOutcome.Success(result));
        var facts = OperationOutcomeNarration.Facts(
            "bluetooth.radio.set",
            OperationOutcome.Success(result));

        Assert.That(facts["polarity"]?.GetValue<string>(), Is.EqualTo("success"));
        Assert.That(narration, Does.Contain($"\"state\":{state.ToString().ToLowerInvariant()}"));
    }
}
