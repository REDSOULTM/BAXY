using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>The view model's start of the mind (MainWindowViewModel.InitializeMindAsync) against the fake mind.</summary>
[TestFixture]
public sealed class MindStartTests
{
    [Test]
    public async Task TwoStartsAtOnceLeaveOneMindRunning()
    {
        using var fake = new FakeMind();
        // The model takes a moment to load: the second start (a relaunch, the engine's recovery) comes meanwhile.
        fake.Script(new JsonObject { ["delay"] = new JsonObject { ["catalog.configure"] = 1.0 } });
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            await Task.WhenAll(ViewModelHarness.StartMindAsync(viewModel), ViewModelHarness.StartMindAsync(viewModel));

            Assert.That(viewModel.IsMindReady, Is.True);
            Assert.That(viewModel.MindProcessId, Is.Not.Null);
            Assert.That(fake.LiveProcesses, Is.EqualTo(new[] { viewModel.MindProcessId!.Value }),
                "a mind process runs that the App no longer holds");
        }

        Assert.That(await ViewModelHarness.UntilAsync(() => fake.LiveProcesses.Count == 0), Is.True);
    }
}
