using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// assistant.status (f6 estado) is read by the App from what its view shows; the engine holds none of it, so a call that
/// reaches it fails and says nothing in its place.
/// </summary>
[TestFixture]
public sealed class AssistantStatusHandlerTests
{
    [Test]
    public async Task TheEngineHoldsNoneOfBaxysOwnReadings()
    {
        var handler = new AssistantStatusHandler();

        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("r", "m", "i", JsonDocument.Parse("{\"scope\":\"model\"}").RootElement),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(handler.Definition.Name, Is.EqualTo("assistant.status"));
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(AssistantStatusHandler.ReadByTheApp));
            Assert.That(outcome.Result, Is.Null);
        });
    }
}
