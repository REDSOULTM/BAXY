using System.Text.Json;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>uso-129: which processes are one application, and what a force-kill of a helper says of the rest.</summary>
[TestFixture]
public sealed class ApplicationFamilyTests
{
    private static ApplicationProcess Node(int id, int parent, string name, long start, string? path) =>
        new(id, parent, name, start, path);

    private static Dictionary<int, ApplicationProcess> Running(params ApplicationProcess[] processes) =>
        processes.ToDictionary(static process => process.Id);

    private static readonly ApplicationProcess Shell = Node(1, 0, "explorer", 1, @"C:\Windows\explorer.exe");
    private static readonly ApplicationProcess Main = Node(10, 1, "bandeja", 5, @"C:\Prog\Bandeja\bandeja.exe");
    private static readonly ApplicationProcess Helper = Node(11, 10, "ayudante", 6, @"C:\Prog\Bandeja\bin\web\ayudante.exe");
    private static readonly ApplicationProcess Same = Node(12, 10, "bandeja", 6, @"C:\Prog\Bandeja\bandeja.exe");
    private static readonly ApplicationProcess Other = Node(13, 10, "visor", 6, @"C:\Prog\Visor\visor.exe");

    [Test]
    public void AHelperInTheApplicationsFolderHasItAsMain() =>
        Assert.That(ApplicationFamily.MainOf(Running(Shell, Main, Helper), 11)?.Id, Is.EqualTo(10));

    [Test]
    public void TheShellThatStartedItIsNeverItsMain() =>
        Assert.That(ApplicationFamily.MainOf(Running(Shell, Main), 10)?.Id, Is.EqualTo(10));

    [Test]
    public void AProgramAnApplicationStartedFromElsewhereIsItsOwnMain() =>
        Assert.That(ApplicationFamily.MainOf(Running(Shell, Main, Other), 13)?.Id, Is.EqualTo(13));

    [Test]
    public void AParentYoungerThanItsChildIsAnotherProcessThatReusedTheId()
    {
        ApplicationProcess reused = Node(10, 1, "bandeja", 9, @"C:\Prog\Bandeja\bandeja.exe");
        Assert.That(ApplicationFamily.MainOf(Running(Shell, reused, Helper), 11)?.Id, Is.EqualTo(11));
    }

    [Test]
    public void TheMembersAreItsDescendantsInItsFolderAndItsOwnExecutable() =>
        Assert.That(ApplicationFamily.Members(Running(Shell, Main, Helper, Same, Other), Main).Select(static p => p.Id),
            Is.EqualTo(new[] { 10, 11, 12 }));

    private sealed class HelperOfARunningApplication(WindowsProcessFamily family, bool mainAlive) : IWindowsProcessTerminationPlatform
    {
        private int _reads;
        private static readonly WindowsProcessIdentity Instance = new(11, 6);

        public IReadOnlyList<WindowsProcessIdentity> Snapshot(string processName) => _reads++ == 0 ? [Instance] : [];

        public WindowsProcessTermination Terminate(string processName, WindowsProcessIdentity identity) =>
            WindowsProcessTermination.Terminated;

        public WindowsProcessFamily Family(string processName, IReadOnlyList<WindowsProcessIdentity> instances) => family;

        public WindowsProcessFamily StillRunning(WindowsProcessFamily before) =>
            mainAlive ? before : WindowsProcessFamily.None;
    }

    // Uso real: «cierra los procesos en segundo plano» forced a helper and the application's main process stayed; the
    // receipt said only that the helper's instances were gone.
    [Test]
    public async Task ForcingAHelperWhoseApplicationStaysSaysSoAndTheCallThatReachesIt()
    {
        var adapter = new WindowsProcessTerminationAdapter(new HelperOfARunningApplication(new(Main, [Same]), mainAlive: true));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("system.process.terminate.named",
            JsonDocument.Parse("{\"name\":\"ayudante.exe\"}").RootElement, CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, "the named executable did end");
            Assert.That(result.GetProperty("mainStillRunning").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("mainProcessName").GetString(), Is.EqualTo("bandeja"));
            Assert.That(result.GetProperty("sameApplicationStillRunning")[0].GetString(), Is.EqualTo("bandeja"));
            Assert.That(result.GetProperty("next").GetString(),
                Does.StartWith("system_process_terminate_named {\"name\":\"bandeja\"}"));
        });
    }

    [Test]
    public async Task ForcingAnApplicationWhoseFamilyIsGoneAddsNothing()
    {
        var adapter = new WindowsProcessTerminationAdapter(new HelperOfARunningApplication(new(Main, [Same]), mainAlive: false));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("system.process.terminate.named",
            JsonDocument.Parse("{\"name\":\"ayudante\"}").RootElement, CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.TryGetProperty("mainStillRunning", out _), Is.False);
            Assert.That(result.TryGetProperty("next", out _), Is.False);
        });
    }
}
