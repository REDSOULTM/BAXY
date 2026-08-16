using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class AppOpenHandlerTests
{
    [Test]
    public void DefinitionIsLowRiskAndReversible()
    {
        var handler = new AppOpenHandler(new StubProvider(Success()));

        Assert.Multiple(() =>
        {
            Assert.That(handler.Definition.Name, Is.EqualTo("app.open"));
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.Reversible));
        });
    }

    [Test]
    public async Task DurableInvocationIdentityCrossesTheProviderBoundary()
    {
        OperationInvocation invocation = Invocation("{\"appId\":\"windows.notepad\"}");
        var provider = new StubProvider(Success(invocation.InvocationId));
        var handler = new AppOpenHandler(provider);

        _ = await handler.ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(provider.LastRequest?.ApplicationId, Is.EqualTo(ApplicationIds.Notepad));
            Assert.That(provider.LastRequest?.InvocationId, Is.EqualTo(invocation.InvocationId));
        });
    }

    [TestCase(false, "Listo, abrí Bloc de notas.")]
    [TestCase(true, "Listo, enfoqué Bloc de notas.")]
    public async Task VerifiedResultIsTheOnlySuccess(bool alreadyRunning, string expectedMessage)
    {
        OperationInvocation invocation = Invocation("{\"appId\":\"windows.notepad\"}");
        var handler = new AppOpenHandler(new StubProvider(Success(
            invocation.InvocationId,
            alreadyRunning)));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(Message(outcome), Is.EqualTo(expectedMessage));
            Assert.That(outcome.Result?.GetProperty("appId").GetString(), Is.EqualTo(ApplicationIds.Notepad));
            Assert.That(outcome.Result?.GetProperty("processId").GetInt32(), Is.EqualTo(4242));
            Assert.That(outcome.Result?.GetProperty("windowHandle").GetInt64(), Is.EqualTo(73));
        });
    }

    [Test]
    public async Task VerifierMayDiscoverWindowAfterDurableReceiptWasWritten()
    {
        OperationInvocation invocation = Invocation("{\"appId\":\"windows.notepad\"}");
        ApplicationOpenResult valid = Success(invocation.InvocationId);
        var handler = new AppOpenHandler(new StubProvider(
            valid with { Receipt = valid.Receipt with { WindowHandle = null } }));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.That(outcome.Succeeded, Is.True);
    }

    [TestCase("top_error")]
    [TestCase("receipt_error")]
    [TestCase("missing_receipt")]
    [TestCase("invocation")]
    [TestCase("application")]
    [TestCase("process")]
    [TestCase("creation_time")]
    [TestCase("path")]
    [TestCase("window")]
    [TestCase("flags_both")]
    [TestCase("flags_neither")]
    [TestCase("already_running")]
    [TestCase("package_pair")]
    public async Task ContradictoryVerifiedEvidenceFailsClosed(string defect)
    {
        OperationInvocation invocation = Invocation("{\"appId\":\"windows.notepad\"}");
        ApplicationOpenResult valid = Success(invocation.InvocationId);
        ApplicationOpenResult contradicted = defect switch
        {
            "top_error" => valid with { ErrorCode = "verification_failed" },
            "receipt_error" => valid with
            {
                Receipt = valid.Receipt with { ErrorCode = "verification_failed" },
            },
            "missing_receipt" => valid with { Receipt = null! },
            "invocation" => valid with
            {
                Receipt = valid.Receipt with { InvocationId = Guid.NewGuid().ToString("D") },
            },
            "application" => valid with
            {
                Receipt = valid.Receipt with { ApplicationId = "windows.calculator" },
            },
            "process" => valid with { Receipt = valid.Receipt with { ProcessId = 4243 } },
            "creation_time" => valid with
            {
                Receipt = valid.Receipt with { ProcessCreationTimeUtcTicks = 0 },
            },
            "path" => valid with { Receipt = valid.Receipt with { ExecutablePath = null } },
            "window" => valid with { Receipt = valid.Receipt with { WindowHandle = 74 } },
            "flags_both" => valid with
            {
                Receipt = valid.Receipt with { LaunchIssued = true, ReusedExisting = true },
            },
            "flags_neither" => valid with
            {
                Receipt = valid.Receipt with { LaunchIssued = false, ReusedExisting = false },
            },
            "already_running" => valid with { AlreadyRunning = true },
            "package_pair" => valid with
            {
                Receipt = valid.Receipt with
                {
                    PackageFamilyName = "Microsoft.WindowsNotepad_8wekyb3d8bbwe",
                },
            },
            _ => throw new AssertionException($"Unknown contradiction: {defect}"),
        };
        var handler = new AppOpenHandler(new StubProvider(contradicted));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(Message(outcome), Does.Contain("puede haber quedado abierto"));
            Assert.That(Message(outcome), Does.Not.StartWith("Listo"));
        });
    }

    [TestCase("app_not_found")]
    [TestCase("invalid_application")]
    [TestCase("invalid_invocation")]
    [TestCase("app_not_found")]
    [TestCase("inventory_failed")]
    [TestCase("launch_failed")]
    [TestCase("state_capacity_reached")]
    [TestCase("state_corrupt")]
    [TestCase("state_unavailable")]
    [TestCase("verification_failed")]
    public async Task ExpectedProviderFailureRemainsHonest(string errorCode)
    {
        var providerResult = new ApplicationOpenResult(
            Succeeded: false,
            Verified: false,
            "Bloc de notas",
            AlreadyRunning: false,
            ProcessId: null,
            WindowHandle: null,
            errorCode,
            Receipt(errorCode: errorCode));
        var handler = new AppOpenHandler(new StubProvider(providerResult));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"appId\":\"windows.notepad\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.Verified, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(errorCode));
            Assert.That(Message(outcome), Does.Not.StartWith("Listo"));
        });
    }

    [Test]
    public async Task LauncherSuccessWithoutIndependentVerificationNeverClaimsSuccess()
    {
        var providerResult = new ApplicationOpenResult(
            Succeeded: true,
            Verified: false,
            "Bloc de notas",
            AlreadyRunning: false,
            ProcessId: 4242,
            WindowHandle: 73,
            ErrorCode: null,
            Receipt(launchIssued: true, processId: 4242, windowHandle: 73));
        var handler = new AppOpenHandler(new StubProvider(providerResult));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"appId\":\"windows.notepad\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(Message(outcome), Does.Not.StartWith("Listo"));
        });
    }

    [TestCase("inventory_failed")]
    [TestCase("state_capacity_reached")]
    [TestCase("state_corrupt")]
    [TestCase("state_unavailable")]
    [TestCase("verification_failed")]
    public async Task PartialEffectIsDisclosedInsteadOfReportedAsNoEffect(string errorCode)
    {
        var providerResult = new ApplicationOpenResult(
            Succeeded: true,
            Verified: false,
            "Bloc de notas",
            AlreadyRunning: false,
            ProcessId: 4242,
            WindowHandle: 73,
            errorCode,
            Receipt(
                launchIssued: true,
                processId: 4242,
                windowHandle: 73,
                errorCode: errorCode));
        var handler = new AppOpenHandler(new StubProvider(providerResult));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"appId\":\"windows.notepad\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(errorCode));
            Assert.That(Message(outcome), Does.Contain("puede haber quedado abierto"));
            Assert.That(Message(outcome), Does.Not.StartWith("Listo"));
            if (string.Equals(errorCode, "inventory_failed", StringComparison.Ordinal))
            {
                Assert.That(Message(outcome), Does.Contain("pudo haber comenzado"));
            }
        });
    }

    [TestCase("{}")]
    [TestCase("{\"appId\":\"windows.notepad\",\"arguments\":\"unsafe\"}")]
    [TestCase("{\"AppId\":\"windows.notepad\"}")]
    public async Task InvalidContractNeverCallsProvider(string json)
    {
        var provider = new StubProvider(Success());
        var handler = new AppOpenHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(json), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(provider.CallCount, Is.Zero);
        });
    }

    [TestCase("C:\\Windows\\System32\\notepad.exe")]
    [TestCase("")]
    public async Task NonAllowlistedApplicationIdNeverReachesProvider(string appId)
    {
        var provider = new StubProvider(Success());
        var handler = new AppOpenHandler(provider);
        string json = JsonSerializer.Serialize(new { appId });

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation(json), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_application"));
            Assert.That(provider.CallCount, Is.Zero);
        });
    }

    [Test]
    public async Task CalculatorAllowlistAcceptsOnlyConsistentVerifiedEvidence()
    {
        OperationInvocation invocation = Invocation("{\"appId\":\"windows.calculator\"}");
        var receipt = new ApplicationLaunchReceipt(
            invocation.InvocationId, ApplicationIds.Calculator, true, false, 5151,
            DateTime.UtcNow.Ticks, @"C:\Windows\System32\calc.exe", null, null, 81, null);
        var provider = new StubProvider(new ApplicationOpenResult(
            true, true, "Calculadora", false, 5151, 81, null, receipt));
        var handler = new AppOpenHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("appId").GetString(),
                Is.EqualTo(ApplicationIds.Calculator));
            Assert.That(outcome.Result.Value.GetProperty("displayName").GetString(),
                Is.EqualTo("Calculadora"));
        });
    }

    [Test]
    public async Task InstalledApplicationAcceptsOnlyProviderVerifiedIdentityAndWindow()
    {
        OperationInvocation invocation = Invocation("{\"appId\":\"Steam\"}");
        var receipt = new ApplicationLaunchReceipt(
            invocation.InvocationId, "Steam", true, false, 6161,
            DateTime.UtcNow.Ticks, @"C:\Program Files (x86)\Steam\steam.exe",
            null, null, 91, null);
        var provider = new StubProvider(new ApplicationOpenResult(
            true, true, "Steam", false, 6161, 91, null, receipt));
        var handler = new AppOpenHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(Message(outcome), Is.EqualTo("Listo, abrí Steam."));
            Assert.That(outcome.Result!.Value.GetProperty("appId").GetString(), Is.EqualTo("Steam"));
        });
    }

    [Test]
    public async Task UnexpectedProviderFailureLeavesInvocationIncomplete()
    {
        using var journal = new InMemoryInvocationJournal();
        var provider = new StubProvider(new IOException("simulated provider failure"));
        using var engine = new MissionEngine(
            new OperationRegistry([new AppOpenHandler(provider)]),
            journal);
        OperationRequest request = Request();

        Assert.That(
            async () => await engine.ExecuteAsync(request, CancellationToken.None),
            Throws.TypeOf<IOException>());

        string? started = await journal.FindStartedFingerprintAsync(
            request.InvocationId,
            CancellationToken.None);
        CompletedInvocation? completed = await journal.FindCompletedAsync(
            request.InvocationId,
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(started, Is.EqualTo(RequestFingerprint.Compute(request)));
            Assert.That(completed, Is.Null);
        });
    }

    private static OperationInvocation Invocation(string json) => new(
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        JsonDocument.Parse(json).RootElement.Clone());

    private static OperationRequest Request() => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "app.open",
        JsonDocument.Parse("{\"appId\":\"windows.notepad\"}").RootElement.Clone());

    private static ApplicationOpenResult Success(
        string? invocationId = null,
        bool alreadyRunning = false) => new(
        Succeeded: true,
        Verified: true,
        "Bloc de notas",
        alreadyRunning,
        ProcessId: 4242,
        WindowHandle: 73,
        ErrorCode: null,
        Receipt(
            launchIssued: !alreadyRunning,
            reusedExisting: alreadyRunning,
            processId: 4242,
            windowHandle: 73,
            invocationId: invocationId));

    private static ApplicationLaunchReceipt Receipt(
        bool launchIssued = false,
        bool reusedExisting = false,
        int? processId = null,
        long? windowHandle = null,
        string? errorCode = null,
        string? invocationId = null) =>
        new(
            invocationId ?? Guid.NewGuid().ToString("D"),
            ApplicationIds.Notepad,
            launchIssued,
            reusedExisting,
            processId,
            processId.HasValue ? DateTime.UtcNow.Ticks : null,
            processId.HasValue ? @"C:\Windows\System32\notepad.exe" : null,
            PackageFamilyName: null,
            PackageFullName: null,
            windowHandle,
            errorCode);

    private static string Message(OperationOutcome outcome) =>
        OperationOutcomeNarration.For("app.open", outcome);

    private sealed class StubProvider : IApplicationOpenProvider
    {
        private readonly ApplicationOpenResult? _result;
        private readonly Exception? _exception;

        public StubProvider(ApplicationOpenResult result)
        {
            _result = result;
        }

        public StubProvider(Exception exception)
        {
            _exception = exception;
        }

        public int CallCount { get; private set; }

        public ApplicationOpenRequest? LastRequest { get; private set; }

        public ValueTask<ApplicationOpenResult> OpenAsync(
            ApplicationOpenRequest request,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            CallCount++;
            LastRequest = request;
            if (_exception is not null)
            {
                throw _exception;
            }

            return ValueTask.FromResult(_result!);
        }
    }
}
