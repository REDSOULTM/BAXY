using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The rail's «Alarmas» counter (FieldProductChannel surfaces «triggers»). VIVO3 C1: «0» before any alarm, «—» with three
/// set by chat: a schedule.alarms of the chat dropped the count to be read again «when the view asks», and only the
/// triggers panel asked, so the surfaces the view polls kept null until it was opened.
/// </summary>
[TestFixture]
public sealed class TriggerCountTests
{
    [Test]
    public async Task AnAlarmSetByChatIsCountedAgainWhenTheViewAsksForTheSurfaces()
    {
        int listed = 0;
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            view.Channel.ListTriggers = (_, _) => Task.FromResult<OperationResponse?>(Listed(listed));
            (_, JsonObject first) = await view.SendAsync("GET", "/triggers");
            Assert.That((int?)first["count"], Is.EqualTo(0));

            listed = 3;
            const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
            object loop = typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
            var host = (NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!;
            host.StepCompleted!(new NativeTurnStep("schedule.alarms", new JsonObject { ["action"] = "create" },
                OperationStatuses.Completed, true, null, 12, "{}", "c1", Sent: true));

            (_, JsonObject surfaces) = await view.SendAsync("GET", "/surfaces");

            Assert.That((int?)surfaces["triggers"], Is.EqualTo(3));
        }
    }

    [Test]
    public async Task ACountThatCannotBeReadStaysUnknown()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            view.Channel.ListTriggers = (_, _) => Task.FromResult<OperationResponse?>(null);

            (_, JsonObject surfaces) = await view.SendAsync("GET", "/surfaces");

            Assert.That(surfaces["triggers"], Is.Null);
        }
    }

    private static OperationResponse Listed(int count) => new(
        ProtocolTypes.OperationResponse, "r", "m", "i", OperationStatuses.Completed, "listed", true, false,
        JsonDocument.Parse("{\"count\":" + count + ",\"notifications\":[]}").RootElement.Clone(), null);
}
