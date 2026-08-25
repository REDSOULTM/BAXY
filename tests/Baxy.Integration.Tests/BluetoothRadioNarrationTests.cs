using System.Text.Json;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class BluetoothRadioNarrationTests
{
    [TestCase(true)]
    [TestCase(false)]
    public void VerifiedBluetoothRadioStateReachesTheComposerAsFacts(bool state)
    {
        JsonElement result = JsonDocument.Parse(
            $$"""{"version":1,"state":{{state.ToString().ToLowerInvariant()}},"radioCount":1,"authority":"windows_radio_api_postread"}""")
            .RootElement.Clone();

        JsonElement facts = OperationOutcomeNarration.AssertFacts(
            "bluetooth.radio.set",
            OperationOutcome.Success(result));

        Assert.That(
            facts.GetProperty("observed").GetProperty("state").GetBoolean(),
            Is.EqualTo(state));
    }
}
