using System.IO;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// MOD1 D5 (ABIERTOS_VIVO D5, 2026-11-09): a change of context makes BAXY's own model read its instructions and tools whole
/// again (746-754 s on an RX 7600 on Vulkan) and nothing said so before. The App keeps what this PC took the last time it
/// read them whole, from the mind's own progress lines, and Settings → Model → Context says it before the change.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class PrefixReadTests
{
    private string _root = "";

    [SetUp]
    public void SetUp() => _root = Directory.CreateTempSubdirectory("baxy-prefix-").FullName;

    [TearDown]
    public void TearDown() => Directory.Delete(_root, recursive: true);

    private static TimeSpan Seconds(double seconds) => TimeSpan.FromSeconds(seconds);

    [Test]
    public void AWholeReadIsKeptWithWhatItTookAndIsStillKnownAfterARestart()
    {
        var read = new PrefixRead(_root);
        Assert.That(read.Last(), Is.Null, "nothing was read on this PC yet");

        read.Begin();
        read.Saw(1024, 49086, Seconds(100));
        read.Saw(24000, 49086, Seconds(400));
        read.Saw(49086, 49086, Seconds(840));
        read.Ended(ownModel: true);

        // 48,062 tokens in 740 s: the 49,086 of the prefix take 756 s at that pace
        Assert.That(read.Last(), Is.EqualTo((49086, 756)));
        Assert.That(new PrefixRead(_root).Last(), Is.EqualTo((49086, 756)), "kept on disk: most starts restore the prefix and read nothing");
        Assert.That(new PrefixRead(_root).Json()?.ToJsonString(), Is.EqualTo("""{"tokens":49086,"seconds":756}"""));
    }

    [Test]
    public void AStartThatReadNothingOrOnlyItsEndLeavesTheLastWholeReadAsItWas()
    {
        var read = new PrefixRead(_root);
        read.Begin();
        read.Saw(2048, 49086, Seconds(0));
        read.Saw(49086, 49086, Seconds(18));
        read.Ended(ownModel: true);
        (int Tokens, int Seconds)? whole = read.Last();
        Assert.That(whole, Is.EqualTo((49086, 19)));

        // the prefix restored from its kept state: no line at all
        read.Begin();
        read.Ended(ownModel: true);
        Assert.That(read.Last(), Is.EqualTo(whole));

        // or one line that says it is all there
        read.Begin();
        read.Saw(49086, 49086, Seconds(50));
        read.Ended(ownModel: true);
        Assert.That(read.Last(), Is.EqualTo(whole));

        // read only from where it differed (the last 2,000 tokens): not a measure of the whole
        read.Begin();
        read.Saw(47086, 49086, Seconds(60));
        read.Saw(49086, 49086, Seconds(61));
        read.Ended(ownModel: true);
        Assert.That(read.Last(), Is.EqualTo(whole));
    }

    [Test]
    public void AStartThatFailedOrAnotherModelsIsNotThisPcsReadOfBaxysOwnModel()
    {
        var read = new PrefixRead(_root);
        read.Begin();
        read.Saw(1024, 49086, Seconds(0));
        read.Saw(49086, 49086, Seconds(300));
        read.Ended(ownModel: false);
        Assert.That(read.Last(), Is.Null);

        // what an ended start saw does not count for the next one
        read.Begin();
        read.Saw(49086, 49086, Seconds(900));
        read.Ended(ownModel: true);
        Assert.That(read.Last(), Is.Null);

        // nor what a start that never ended saw (it failed while reading): the next one restored its prefix, and its one line
        // beside the failed start's first would look like a whole read
        read.Begin();
        read.Saw(1024, 49086, Seconds(1000));
        read.Saw(30000, 49086, Seconds(1400));
        read.Begin();
        read.Saw(49086, 49086, Seconds(2000));
        read.Ended(ownModel: true);
        Assert.That(read.Last(), Is.Null);
    }

    [Test]
    public void AFileThatIsNotAMeasureIsNoMeasure()
    {
        File.WriteAllText(Path.Combine(_root, PrefixRead.FileName), """{"tokens":0,"seconds":"mucho"}""");
        Assert.That(new PrefixRead(_root).Last(), Is.Null);
        File.WriteAllText(Path.Combine(_root, PrefixRead.FileName), "no es json");
        Assert.That(new PrefixRead(_root).Last(), Is.Null);
    }

    // The App's own path: the mind's progress lines of a start reach the measure, and the view reads it where it reads the
    // context (GET /settings/local-context). The fake mind reads its «prefix» of 4 tokens in 4 lines, 0.4 s apart.
    [Test]
    public async Task TheViewReadsWhatTheLastWholeReadTookOnceAMindCameUpReadingIt()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["progress"] = new JsonObject { ["catalog.configure"] = new JsonObject { ["every"] = 0.4, ["count"] = 4 } },
        });
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            (int status, JsonObject before) = await view.SendAsync("GET", "/settings/local-context");
            Assert.That((status, before["lastRead"]), Is.EqualTo((200, (JsonNode?)null)), "no read measured yet");

            await ViewModelHarness.StartMindAsync(viewModel);
            Assert.That(viewModel.IsMindReady, Is.True);

            (_, JsonObject after) = await view.SendAsync("GET", "/settings/local-context");
            Assert.Multiple(() =>
            {
                Assert.That((int?)after["lastRead"]?["tokens"], Is.EqualTo(4));
                // 3 tokens in about 1.2 s: the 4 take 2 s, rounded up (less if a busy PC read the lines late and together, or more)
                Assert.That((int?)after["lastRead"]?["seconds"], Is.InRange(1, 10));
            });

            // a later start that reads nothing (its prefix restored) keeps that measure
            fake.Script(new JsonObject());
            await ViewModelHarness.StopMindForRestartAsync(viewModel);
            await ViewModelHarness.StartMindAsync(viewModel);
            (_, JsonObject kept) = await view.SendAsync("GET", "/settings/local-context");
            Assert.That(kept["lastRead"]?.ToJsonString(), Is.EqualTo(after["lastRead"]!.ToJsonString()));
        }
    }
}
