using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 25 (G12, uso real 02-11: «ciérrate» → app.close of BAXY → app_running_in_background, «No pude cerrar BAXY»):
/// baxy.exit asks the running App to exit through the event its tray's «Salir» path already answers (the launcher's,
/// App.xaml.cs), so the conversation is kept and the icon removed. The App cannot be read closed before the reply, so
/// the result says the request was delivered, never that BAXY is closed.
/// </summary>
[TestFixture]
public sealed class BaxyExitHandlerTests
{
    [Test]
    public async Task TheRunningAppIsAskedToExitAndTheResultSaysDelivered()
    {
        string name = @"Local\BAXY.Tests.Exit." + Guid.NewGuid().ToString("N");
        using var exit = new EventWaitHandle(false, EventResetMode.AutoReset, name);

        using JsonDocument facts = JsonDocument.Parse(await Exit(name));
        JsonElement root = facts.RootElement;

        Assert.Multiple(() =>
        {
            Assert.That(root.GetProperty("status").GetString(), Is.EqualTo("completed"));
            Assert.That(root.GetProperty("verification").GetString(),
                Is.EqualTo(OperationVisibleFacts.VerificationDeliveredOnly));
            Assert.That(root.GetProperty("observed").GetProperty("exitRequested").GetBoolean(), Is.True);
            Assert.That(exit.WaitOne(0), Is.True);
        });
    }

    // No App listening (the engine alone, a bench): nothing is asked and nothing is said done.
    [Test]
    public async Task WithNoAppListeningNothingIsSaidDone()
    {
        using JsonDocument facts = JsonDocument.Parse(
            await Exit(@"Local\BAXY.Tests.Exit." + Guid.NewGuid().ToString("N")));

        Assert.Multiple(() =>
        {
            Assert.That(facts.RootElement.GetProperty("status").GetString(), Is.EqualTo("failed"));
            Assert.That(facts.RootElement.GetProperty("error").GetString(), Is.EqualTo("baxy_app_not_listening"));
        });
    }

    private static async Task<string> Exit(string eventName)
    {
        OperationOutcome outcome = await new BaxyExitHandler(eventName).ExecuteAsync(
            new OperationInvocation(
                "request", "mission", "invocation", JsonDocument.Parse("{}").RootElement.Clone()),
            CancellationToken.None);
        return OperationVisibleFacts.FromOutcome(BaxyExitHandler.Operation, outcome);
    }
}
