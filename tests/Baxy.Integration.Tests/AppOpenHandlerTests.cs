using System.Text.Json;
using System.Text.Json.Nodes;
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

    // v3 point 0 (arreglo 4): only «foreground» true asks the provider for the front; absent or false, the application
    // opens behind the person's window. A front Windows gave by itself and handed back is said in the result.
    [TestCase("{\"appId\":\"windows.notepad\"}", false)]
    [TestCase("{\"appId\":\"windows.notepad\",\"foreground\":false}", false)]
    [TestCase("{\"appId\":\"windows.notepad\",\"foreground\":true}", true)]
    public async Task TheForegroundIsAskedOnlyWhenTheArgumentsSaySo(string arguments, bool asked)
    {
        OperationInvocation invocation = Invocation(arguments);
        var provider = new StubProvider(Success(invocation.InvocationId) with { WindowsActivation = !asked });
        var handler = new AppOpenHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Verified, Is.True);
            Assert.That(provider.LastRequest?.Foreground, Is.EqualTo(asked));
            Assert.That(outcome.Result?.TryGetProperty("windowsActivation", out JsonElement activation) == true
                && activation.GetBoolean(), Is.EqualTo(!asked), "said only when it happened");
        });
    }

    // cu-v3-foco-segunda: the result says whether the hand-back of a Windows activation held; a refused one is an
    // activation without «frontRestored», and nothing is said of a front nobody took.
    [TestCase(true, true, true)]
    [TestCase(true, false, false)]
    [TestCase(false, true, false)]
    public async Task TheResultSaysWhetherTheFrontWentBack(bool activation, bool restored, bool said)
    {
        OperationInvocation invocation = Invocation("{\"appId\":\"windows.notepad\"}");
        var provider = new StubProvider(Success(invocation.InvocationId) with
        {
            WindowsActivation = activation,
            FrontRestored = restored,
        });

        OperationOutcome outcome = await new AppOpenHandler(provider).ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Verified, Is.True);
            Assert.That(outcome.Result?.TryGetProperty("frontRestored", out JsonElement back) == true && back.GetBoolean(),
                Is.EqualTo(said));
        });
    }

    // r20b palanca 4 (v3-40, v3-43): an opening asked in front while the person worked in another window says it was
    // shown above without their keyboard («shownWithoutFocus»); one that took the front says nothing of it.
    [TestCase(true)]
    [TestCase(false)]
    public async Task TheResultSaysAWindowShownWithoutTakingTheKeyboard(bool shown)
    {
        OperationInvocation invocation = Invocation("{\"appId\":\"windows.notepad\",\"foreground\":true}");
        var provider = new StubProvider(Success(invocation.InvocationId) with { ShownWithoutFocus = shown });

        OperationOutcome outcome = await new AppOpenHandler(provider).ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Verified, Is.True);
            Assert.That(outcome.Result?.TryGetProperty("shownWithoutFocus", out JsonElement said) == true && said.GetBoolean(),
                Is.EqualTo(shown));
        });
    }

    // v3 r5a M5 review: only an opening for a computer-use mission («forControl») asks the provider for the person's
    // rights; an ordinary «abre X» keeps the shell's path (a console opened to administer the PC keeps its rights).
    [TestCase("{\"appId\":\"windows.notepad\"}", false)]
    [TestCase("{\"appId\":\"windows.notepad\",\"forControl\":false}", false)]
    [TestCase("{\"appId\":\"windows.notepad\",\"forControl\":true}", true)]
    public async Task TheOpeningIsForControlOnlyWhenTheArgumentsSaySo(string arguments, bool forControl)
    {
        OperationInvocation invocation = Invocation(arguments);
        var provider = new StubProvider(Success(invocation.InvocationId));
        var handler = new AppOpenHandler(provider);

        _ = await handler.ExecuteAsync(invocation, CancellationToken.None);

        Assert.That(provider.LastRequest?.ForControl, Is.EqualTo(forControl));
    }

    // cu-v3-documento-nuevo (uso real t4-c14): «newDocument» reaches the provider, the result says the document was
    // made, and an opening that asked for one and reports none (the person's window as it was) is no success.
    [TestCase("{\"appId\":\"windows.notepad\"}", false, false, true)]
    [TestCase("{\"appId\":\"windows.notepad\",\"newDocument\":true}", true, true, true)]
    [TestCase("{\"appId\":\"windows.notepad\",\"newDocument\":true}", true, false, false)]
    public async Task ANewDocumentAskedForIsSuccessOnlyWhenTheProviderMadeIt(
        string arguments, bool asked, bool made, bool succeeded)
    {
        OperationInvocation invocation = Invocation(arguments);
        var provider = new StubProvider(Success(invocation.InvocationId, alreadyRunning: true) with { NewDocument = made });

        OperationOutcome outcome = await new AppOpenHandler(provider).ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(provider.LastRequest?.NewDocument, Is.EqualTo(asked));
            Assert.That(outcome.Succeeded, Is.EqualTo(succeeded));
            Assert.That(outcome.Result?.TryGetProperty("newDocument", out JsonElement said) == true && said.GetBoolean(),
                Is.EqualTo(succeeded && made));
        });
    }

    // Estabilización, encargo C: a place of the application its data declare (app_places.v1.json) is opened by the
    // address the kernel composes, once the application is open and verified; the result says so. A place, a value or
    // an application the data do not declare opens nothing at all, and a hand-over Windows refused is no success.
    [Test]
    public async Task ADeclaredPlaceIsOpenedByItsAddressAfterTheApplication()
    {
        OperationInvocation invocation = Invocation("{\"appId\":\"Steam\",\"place\":\"results\",\"placeValue\":\"Cuphead\"}");
        var provider = new StubProvider(SuccessOf("Steam", invocation.InvocationId));
        var places = new StubPlaces(opens: true);

        OperationOutcome outcome = await new AppOpenHandler(provider, places: places).ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(provider.CallCount, Is.EqualTo(1));
            Assert.That(places.Opened, Is.EqualTo(new[] { "steam://openurl/https://store.steampowered.com/search/?term=Cuphead" }));
            Assert.That(outcome.Result?.GetProperty("placeOpened").GetBoolean(), Is.True);
        });
    }

    [TestCase("{\"appId\":\"Steam\",\"place\":\"home\"}")]
    [TestCase("{\"appId\":\"windows.notepad\",\"place\":\"library\"}")]
    [TestCase("{\"appId\":\"Steam\",\"place\":\"game\",\"placeValue\":\"cuphead\"}")]
    [TestCase("{\"appId\":\"Steam\",\"placeValue\":\"Cuphead\"}")]
    public async Task APlaceTheDataDoNotDeclareOpensNothing(string arguments)
    {
        OperationInvocation invocation = Invocation(arguments);
        var provider = new StubProvider(SuccessOf("Steam", invocation.InvocationId));
        var places = new StubPlaces(opens: true);

        OperationOutcome outcome = await new AppOpenHandler(provider, places: places).ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(provider.CallCount, Is.Zero);
            Assert.That(places.Opened, Is.Empty);
        });
    }

    [Test]
    public async Task APlaceWindowsDidNotTakeIsNoSuccessAndAnOpeningWithoutPlaceOpensNone()
    {
        OperationInvocation placed = Invocation("{\"appId\":\"Steam\",\"place\":\"library\"}");
        var refused = new StubPlaces(opens: false);
        OperationOutcome failed = await new AppOpenHandler(new StubProvider(SuccessOf("Steam", placed.InvocationId)), places: refused)
            .ExecuteAsync(placed, CancellationToken.None);

        OperationInvocation bare = Invocation("{\"appId\":\"Steam\"}");
        var unused = new StubPlaces(opens: true);
        OperationOutcome opened = await new AppOpenHandler(new StubProvider(SuccessOf("Steam", bare.InvocationId)), places: unused)
            .ExecuteAsync(bare, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(failed.Succeeded, Is.False);
            Assert.That(failed.ErrorCode, Is.EqualTo("launch_failed"));
            Assert.That(failed.EffectMayHaveOccurred, Is.True);
            Assert.That(opened.Succeeded, Is.True);
            Assert.That(unused.Opened, Is.Empty);
            Assert.That(opened.Result?.TryGetProperty("placeOpened", out _), Is.False);
        });
    }

    private static ApplicationOpenResult SuccessOf(string appId, string invocationId)
    {
        ApplicationOpenResult notepad = Success(invocationId, alreadyRunning: true);
        return notepad with { DisplayName = appId, Receipt = notepad.Receipt with { ApplicationId = appId } };
    }

    // Review H2: the handler's raised window goes back behind the person's unless the front was asked for, and the
    // receipt says the front changed and whether it is back.
    [TestCase("{\"appId\":\"Steam\",\"place\":\"library\"}", false)]
    [TestCase("{\"appId\":\"Steam\",\"place\":\"library\",\"foreground\":true}", true)]
    public async Task TheFrontTheAddressTookGoesBackAndTheReceiptSaysSo(string arguments, bool asked)
    {
        OperationInvocation invocation = Invocation(arguments);
        var places = new StubPlaces(opens: true, front: !asked);

        OperationOutcome outcome = await new AppOpenHandler(new StubProvider(SuccessOf("Steam", invocation.InvocationId)), places: places)
            .ExecuteAsync(invocation, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(places.KeptFront, Is.EqualTo(new[] { asked }));
            Assert.That(places.Window, Is.EqualTo(73));
            Assert.That(outcome.Result?.TryGetProperty("frontChanged", out JsonElement changed) == true && changed.GetBoolean(), Is.EqualTo(!asked));
            Assert.That(outcome.Result?.TryGetProperty("frontRestored", out JsonElement back) == true && back.GetBoolean(), Is.EqualTo(!asked));
        });
    }

    private sealed class StubPlaces(bool opens, bool front = false) : IApplicationPlaceOpener
    {
        public List<string> Opened { get; } = [];

        public List<bool> KeptFront { get; } = [];

        public long Window { get; private set; }

        public PlaceOpening Open(string address, bool keepFront, long applicationWindow)
        {
            KeptFront.Add(keepFront);
            Window = applicationWindow;
            if (opens)
            {
                Opened.Add(address);
            }

            return new PlaceOpening(opens, FrontChanged: opens && front && !keepFront, FrontRestored: opens && front && !keepFront);
        }
    }

    [TestCase(false)]
    [TestCase(true)]
    public async Task VerifiedResultIsTheOnlySuccess(bool alreadyRunning)
    {
        OperationInvocation invocation = Invocation("{\"appId\":\"windows.notepad\"}");
        var handler = new AppOpenHandler(new StubProvider(Success(
            invocation.InvocationId,
            alreadyRunning)));

        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);
        JsonObject facts = Facts(outcome);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(facts["polarity"]?.GetValue<string>(), Is.EqualTo("success"));
            Assert.That(facts["operation"]?.GetValue<string>(), Is.EqualTo("app.open"));
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
            Assert.That(Facts(outcome)["effectUncertain"]?.GetValue<bool>(), Is.True);
            Assert.That(Facts(outcome)["polarity"]?.GetValue<string>(), Is.EqualTo("failure"));
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
    [TestCase("new_document_not_created")]
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
            Assert.That(Facts(outcome)["effectUncertain"]?.GetValue<bool>(), Is.True);
            Assert.That(Facts(outcome)["error"]?.GetValue<string>(), Is.EqualTo(errorCode));
            Assert.That(Message(outcome), Does.Not.StartWith("Listo"));
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
            Assert.That(Facts(outcome)["polarity"]?.GetValue<string>(), Is.EqualTo("success"));
            Assert.That(Facts(outcome)["operation"]?.GetValue<string>(), Is.EqualTo("app.open"));
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

    private static JsonObject Facts(OperationOutcome outcome) =>
        OperationOutcomeNarration.Facts("app.open", outcome);

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
