using System.IO;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Uso 85 (notebook, Steam session): a profile the core could not read stopped it at every start and the App relaunched
/// core and mind for ever, killing the model mid-load, with nothing said to the person. A core that says the profile is
/// unreadable ends the start for good and the interface asks; any piece that fails the same way again and again becomes
/// a breakdown shown as such; and a new profile never deletes the old one.
/// </summary>
[TestFixture]
public sealed class EngineBreakdownTests
{
    [Test]
    public void ACoreThatEndedSayingTheProfileIsUnreadableIsTerminal()
    {
        Assert.Multiple(() =>
        {
            Assert.That(CoreProcessClient.StartFailure(CoreExitCodes.ProfileUnreadable),
                Is.TypeOf<CoreProfileUnreadableException>());
            Assert.That(CoreProcessClient.StartFailure(70), Is.Null, "any other stop is retried");
            Assert.That(CoreProcessClient.StartFailure(null), Is.Null);
        });
    }

    [Test]
    public async Task AnUnreadableProfileIsShownAndNothingIsRelaunched()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            TimeSpan? retry = viewModel.CoreStartFailed(new CoreProfileUnreadableException(), DateTimeOffset.UtcNow);
            (int status, JsonObject agent) = await view.SendAsync("GET", "/agent/status");

            Assert.Multiple(() =>
            {
                Assert.That(retry, Is.Null, "no relaunch");
                Assert.That(status, Is.EqualTo(200));
                Assert.That((string?)agent["failure"], Is.EqualTo(MainWindowViewModel.ProfileUnreadable));
            });
        }
    }

    [Test]
    public async Task TheSameStartFailureAgainAndAgainBecomesABreakdown()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        {
            DateTimeOffset at = DateTimeOffset.UtcNow;
            var failure = new IOException("El motor local terminó durante el saludo de protocolo.");
            var waits = new List<TimeSpan?>();
            for (int n = 0; n < StartupRetries.IdenticalLimit; n++)
            {
                waits.Add(viewModel.CoreStartFailed(failure, at.AddSeconds(n)));
                if (n < StartupRetries.IdenticalLimit - 1)
                {
                    Assert.That(viewModel.Failure, Is.EqualTo("retry_without_close"));
                }
            }

            Assert.Multiple(() =>
            {
                Assert.That(waits.Take(4), Is.EqualTo(new TimeSpan?[]
                {
                    TimeSpan.FromSeconds(10), TimeSpan.FromSeconds(20), TimeSpan.FromSeconds(40), TimeSpan.FromSeconds(60),
                }));
                Assert.That(waits[^1], Is.Null, "the fifth identical failure relaunches nothing");
                Assert.That(viewModel.Failure, Is.EqualTo(MainWindowViewModel.EngineUnavailable));
            });
        }
    }

    [Test]
    public void RelaunchesWaitLongerEachTimeAndEnd()
    {
        var retries = new StartupRetries();
        DateTimeOffset at = DateTimeOffset.UtcNow;
        var waits = new List<TimeSpan?>();
        for (int n = 0; n < StartupRetries.Limit; n++)
        {
            // Causes that change every time still end at the limit.
            waits.Add(retries.Failed("causa " + n, at));
        }

        Assert.Multiple(() =>
        {
            Assert.That(waits[0], Is.EqualTo(TimeSpan.FromSeconds(10)));
            Assert.That(waits[3], Is.EqualTo(TimeSpan.FromSeconds(60)));
            Assert.That(waits[^2], Is.EqualTo(TimeSpan.FromSeconds(60)));
            Assert.That(waits[^1], Is.Null);
        });
    }

    [Test]
    public void APieceThatStayedUpStartsCountingAgainAndOneThatFellAtOnceDoesNot()
    {
        DateTimeOffset at = DateTimeOffset.UtcNow;
        var stayed = new StartupRetries();
        var fell = new StartupRetries();
        for (int n = 0; n < StartupRetries.IdenticalLimit - 1; n++)
        {
            _ = stayed.Failed("mente_salio", at);
            _ = fell.Failed("mente_salio", at);
        }

        stayed.Up(at);
        fell.Up(at);

        Assert.Multiple(() =>
        {
            Assert.That(stayed.Failed("mente_salio", at + StartupRetries.Stable), Is.EqualTo(TimeSpan.FromSeconds(10)));
            Assert.That(fell.Failed("mente_salio", at + TimeSpan.FromSeconds(30)), Is.Null,
                "up for half a minute each time is the same failure again");
        });
    }

    [Test]
    public async Task WithNoBreakdownOrUnreadableProfileTheAnswersChangeNothing()
    {
        using var fake = new FakeMind();
        Directory.CreateDirectory(fake.DataRoot);
        string marker = Path.Combine(fake.DataRoot, "confirmation-mode");
        await File.WriteAllTextAsync(marker, "normal");
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            (int fresh, JsonObject freshBody) = await view.SendAsync("POST", "/profile/fresh");
            (int retry, JsonObject retryBody) = await view.SendAsync("POST", "/engine/retry");

            Assert.Multiple(() =>
            {
                Assert.That(fresh, Is.EqualTo(409));
                Assert.That((string?)freshBody["error"], Is.EqualTo("profile_not_unreadable"));
                Assert.That(retry, Is.EqualTo(409));
                Assert.That((string?)retryBody["error"], Is.EqualTo("nothing_to_retry"));
                Assert.That(File.Exists(marker), Is.True, "the profile stays where it was");
            });
        }
    }

    [Test]
    public void AProfileSetAsideIsRenamedWithTheDateAndKeptWhole()
    {
        string parent = Path.Combine(Path.GetTempPath(), $"baxy-apartar-{Guid.NewGuid():N}");
        string root = Path.Combine(parent, "1");
        try
        {
            Directory.CreateDirectory(Path.Combine(root, "memory-store"));
            File.WriteAllText(Path.Combine(root, "memory-store", "current.bin"), "lo de la persona");
            var at = new DateTimeOffset(2026, 11, 4, 15, 30, 12, TimeSpan.FromHours(-3));

            string first = ProfileSetAside.SetAside(root, at);
            Directory.CreateDirectory(root);  // the new profile, set aside in turn within the same second
            string second = ProfileSetAside.SetAside(root, at);

            Assert.Multiple(() =>
            {
                Assert.That(Path.GetFileName(first), Is.EqualTo("1.respaldo-2026-11-04-153012"));
                Assert.That(Path.GetFileName(second), Is.EqualTo("1.respaldo-2026-11-04-153012-2"));
                Assert.That(Directory.Exists(root), Is.False);
                Assert.That(File.ReadAllText(Path.Combine(first, "memory-store", "current.bin")),
                    Is.EqualTo("lo de la persona"));
            });
        }
        finally
        {
            if (Directory.Exists(parent))
            {
                Directory.Delete(parent, recursive: true);
            }
        }
    }

    [Test]
    public void AFolderSomethingHoldsIsNotSetAsideAndStaysWhole()
    {
        string parent = Path.Combine(Path.GetTempPath(), $"baxy-apartar-{Guid.NewGuid():N}");
        string root = Path.Combine(parent, "1");
        try
        {
            Directory.CreateDirectory(root);
            string held = Path.Combine(root, "abierto.txt");
            using (new FileStream(held, FileMode.Create, FileAccess.ReadWrite, FileShare.None))
            {
                Assert.That(() => ProfileSetAside.SetAside(root, DateTimeOffset.Now), Throws.InstanceOf<IOException>());
            }

            Assert.That(File.Exists(held), Is.True);
            Assert.That(Directory.GetDirectories(parent), Has.Length.EqualTo(1), "nothing was moved");
        }
        finally
        {
            if (Directory.Exists(parent))
            {
                Directory.Delete(parent, recursive: true);
            }
        }
    }
}
