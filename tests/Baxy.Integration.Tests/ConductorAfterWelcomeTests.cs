using System.IO;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 28: the harness can send the first turn of a case after the welcome is composed and published
/// (CU_TRAS_BIENVENIDA=1 → -AfterWelcome → --after-welcome). Measurement only: off by default, conductor mode only.
/// </summary>
[TestFixture]
public sealed class ConductorAfterWelcomeTests
{
    [Test]
    public void TheConductorWaitsForTheWelcomeOnlyWhenAsked()
    {
        ProductConductorHost.ConductorArguments plain = ProductConductorHost.ConductorArguments.Parse(
            ["--conductor", "--profile=C:\\perfil", "--timeout-ms=5000"]);
        ProductConductorHost.ConductorArguments asked = ProductConductorHost.ConductorArguments.Parse(
            ["--conductor", "--profile=C:\\perfil", ProductConductorHost.AfterWelcomeArgument, "--timeout-ms=5000"]);

        Assert.Multiple(() =>
        {
            Assert.That(plain.AfterWelcome, Is.False, "the cold figure is the default");
            Assert.That(asked.AfterWelcome, Is.True);
            Assert.That(asked.Timeout, Is.EqualTo(plain.Timeout), "the flag takes no value from its neighbours");
        });
    }

    [Test]
    public async Task TheFirstTurnWaitsUntilTheWelcomeIsPublished()
    {
        int looks = 0;
        var waits = new List<TimeSpan>();

        bool settled = await ProductConductorHost.WelcomeSettledAsync(
            () => ++looks > 3,
            TimeSpan.FromSeconds(30),
            (step, _) =>
            {
                waits.Add(step);
                return Task.CompletedTask;
            },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(settled, Is.True);
            Assert.That(waits, Has.Count.EqualTo(3), "it waited while the welcome was still being composed");
            Assert.That(waits, Has.All.EqualTo(TimeSpan.FromMilliseconds(50)));
        });
    }

    [Test]
    public async Task AWelcomeAlreadyPublishedCostsNoWaitAndOneThatNeverComesStopsAtTheLimit()
    {
        int waitsWhenSettled = 0;
        bool already = await ProductConductorHost.WelcomeSettledAsync(
            static () => true,
            TimeSpan.FromSeconds(30),
            (_, _) =>
            {
                waitsWhenSettled++;
                return Task.CompletedTask;
            },
            CancellationToken.None);

        int waitsWhenNever = 0;
        bool never = await ProductConductorHost.WelcomeSettledAsync(
            static () => false,
            TimeSpan.FromSeconds(1),
            (_, _) =>
            {
                waitsWhenNever++;
                return Task.CompletedTask;
            },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(already, Is.True);
            Assert.That(waitsWhenSettled, Is.Zero);
            Assert.That(never, Is.False, "the turn is sent anyway and the run says the welcome did not settle");
            Assert.That(waitsWhenNever, Is.EqualTo(20), "1 s of 50 ms looks");
        });
    }

    // One name per layer, tied here: the harness variable, the launcher switch and the conductor argument.
    [Test]
    public void TheHarnessOptionReachesTheConductorAndIsOffByDefault()
    {
        string harness = File.ReadAllText(RepositoryPath("scripts", "cu_live", "cu_live.sh"));
        string launcher = File.ReadAllText(RepositoryPath("scripts", "run_baxy_conductor.ps1"));
        string readme = File.ReadAllText(RepositoryPath("scripts", "cu_live", "README.md"));

        Assert.Multiple(() =>
        {
            Assert.That(harness, Does.Contain("[ \"${CU_TRAS_BIENVENIDA:-0}\" = 1 ] && TRAS=\"-AfterWelcome\""));
            Assert.That(launcher, Does.Contain("[switch]$AfterWelcome"));
            Assert.That(launcher, Does.Contain($"$argumentList.Add(\"{ProductConductorHost.AfterWelcomeArgument}\")"));
            Assert.That(readme, Does.Contain("CU_TRAS_BIENVENIDA"));
            Assert.That(readme, Does.Contain(ProductConductorHost.AfterWelcomeArgument));
        });
    }

    private static string RepositoryPath(params string[] parts)
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
        {
            directory = directory.Parent;
        }

        Assert.That(directory, Is.Not.Null, "repository root not found");
        return Path.Combine([directory!.FullName, .. parts]);
    }
}
