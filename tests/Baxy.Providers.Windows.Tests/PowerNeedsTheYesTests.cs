using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo L3: «apágalo» about an open application went to system.power shutdown, and on the owner's PC (Bypass, System
/// One off) nothing stood between that misreading and Windows. The Core's real handler and the real adapter on a platform
/// that shuts nothing down: in normal mode what ends the person's session reaches Windows only with their yes. Bypass asks
/// nothing (orden del dueño, 2026-11-07, REV7: «Bypass es literalmente un modo sin permisos»).
/// </summary>
[TestFixture]
public sealed class PowerNeedsTheYesTests
{
    [TestCase("shutdown")]
    [TestCase("restart")]
    [TestCase("signout")]
    public async Task InNormalModeWhatEndsTheSessionReachesWindowsOnlyWithTheYes(string action)
    {
        using var place = new Place();
        var platform = new Platform();
        await using FileInvocationJournal journal = await place.Journal();
        using MissionEngine engine = Engine(platform, journal, ConfirmationMode.Normal);
        OperationRequest request = Power(action);

        OperationResponse asked = await engine.ExecuteAsync(request, CancellationToken.None);
        string? beforeTheYes = platform.Requested;
        OperationResponse confirmed = await engine.ExecuteAsync(
            request with { ConfirmationToken = asked.Result!.Value.GetProperty("token").GetString() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(asked.ErrorCode, Is.EqualTo(ConfirmationChallengeContract.RequiredErrorCode));
            Assert.That(beforeTheYes, Is.Null);
            Assert.That(confirmed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(platform.Requested, Is.EqualTo(action));
        });
    }

    [TestCase(ConfirmationMode.Normal, "lock")]
    [TestCase(ConfirmationMode.Bypass, "lock")]
    [TestCase(ConfirmationMode.Normal, "sleep")]
    [TestCase(ConfirmationMode.Bypass, "sleep")]
    [TestCase(ConfirmationMode.Bypass, "shutdown")]
    [TestCase(ConfirmationMode.Bypass, "restart")]
    [TestCase(ConfirmationMode.Bypass, "signout")]
    public async Task WhatKeepsItAllOpenOrRunsInBypassGoesDirectly(ConfirmationMode mode, string action)
    {
        using var place = new Place();
        var platform = new Platform();
        await using FileInvocationJournal journal = await place.Journal();
        using MissionEngine engine = Engine(platform, journal, mode);

        OperationResponse response = await engine.ExecuteAsync(Power(action), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(platform.Requested, Is.EqualTo(action));
        });
    }

    private static MissionEngine Engine(Platform platform, FileInvocationJournal journal, ConfirmationMode mode) => new(
        new OperationRegistry(ExternalCapabilityHandlers.Create(new Provider(new WindowsPowerTransitionAdapter(platform)))
            .Where(static handler => handler.Definition.Name == "system.power")),
        journal,
        new MissionEngineOptions { ConfirmationMode = () => mode });

    private static OperationRequest Power(string action) => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "system.power",
        JsonSerializer.SerializeToElement(new { action }));

    private sealed class Provider(WindowsPowerTransitionAdapter adapter) : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            adapter.InvokeAsync(operation, arguments, cancellationToken);
    }

    private sealed class Platform : IWindowsPowerTransitionPlatform
    {
        internal string? Requested { get; private set; }

        public WindowsPowerTransitionResult Request(string action)
        {
            Requested = action;
            return new WindowsPowerTransitionResult(true, "fake_platform_acceptance", false);
        }
    }

    private sealed class Place : IDisposable
    {
        private readonly string _root = Directory.CreateTempSubdirectory("baxy-power-yes-").FullName;

        internal Task<FileInvocationJournal> Journal() => FileInvocationJournal.OpenAsync(
            Path.Combine(_root, "journal.jsonl"), new JournalHmacAuthenticator(new byte[32])).AsTask();

        public void Dispose() => Directory.Delete(_root, recursive: true);
    }
}
