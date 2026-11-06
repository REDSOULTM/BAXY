using System.Buffers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.Clipboard;
using Baxy.Providers.Windows.Capture;
using Baxy.Providers.Windows.Filesystem;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Memory;
using Baxy.Providers.Windows.Network;
using Baxy.Providers.Windows.Notes;
using Baxy.Providers.Windows.SystemStatus;
using Baxy.Providers.Windows.Tasks;
using Baxy.Providers.Windows.Windows;
using Baxy.Security.Windows;

namespace Baxy.Core;

internal static class Program
{
    private const int MaximumLineBytes = 1024 * 1024;
    private static readonly long StartedAt = System.Diagnostics.Stopwatch.GetTimestamp();
    private static readonly SemaphoreSlim OutputLock = new(1, 1);

    public static async Task<int> Main()
    {
        // Reading the field sets it by now: the class has no static constructor, so its static fields may be initialized
        // as late as their first read, and the hello's catalog wait counts from the start of Main (auditoría D-K13).
        _ = StartedAt;
        ChildProcessHandles.KeepOutputFromChildren();
        Console.InputEncoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true);
        Console.OutputEncoding = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);

        string dataRoot;
        try
        {
            dataRoot = ResolveDataRoot();
        }
        catch (Exception exception) when (exception is ArgumentException or IOException)
        {
            Console.Error.WriteLine("BAXY core could not validate its private data directory.");
            return 64;
        }

        using var singleInstance = new Semaphore(
            initialCount: 1,
            maximumCount: 1,
            CreateMutexName(dataRoot));
        if (!singleInstance.WaitOne(0))
        {
            Console.Error.WriteLine("BAXY core is already running for this local data profile.");
            return 73;
        }

        using var shutdown = new CancellationTokenSource();
        Console.CancelKeyPress += (_, eventArgs) =>
        {
            eventArgs.Cancel = true;
            shutdown.Cancel();
        };

        try
        {
            return await RunAsync(dataRoot, shutdown.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (shutdown.IsCancellationRequested)
        {
            return 0;
        }
        catch (Exception exception) when (UnreadableProfile.Is(exception))
        {
            // Uso 85: the profile's state, not a crash; the App stops relaunching and asks the person.
            int exitCode = UnreadableProfile.ExitCode(WindowsProtectedPayload.CurrentUserProtectionWorks);
            Console.Error.WriteLine(exitCode == CoreExitCodes.ProfileUnreadable
                ? $"BAXY core stopped: its local data profile cannot be read or authenticated by this Windows account ({exception.GetType().Name}): {exception.Message}"
                : $"BAXY core stopped safely: Windows data protection does not work in this session ({exception.GetType().Name}): {exception.Message}");
            return exitCode;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine($"BAXY core stopped safely ({exception.GetType().Name}): {exception.Message}");
            return UnreadableProfile.StoppedSafely;
        }
        finally
        {
            singleInstance.Release();
        }
    }

    private static async Task<int> RunAsync(string dataRoot, CancellationToken cancellationToken)
    {
        var noteStore = new LocalNoteStore(Path.Combine(dataRoot, "notes-store"));
        var taskStore = new LocalTaskStore(Path.Combine(dataRoot, "tasks-store"));
        var clipboardProvider = new WindowsClipboardProvider();
        var screenshotProvider = new WindowsScreenshotProvider(Path.Combine(dataRoot, "captures"));
        var filesystemProvider = new LocalFilesystemProvider(
            Path.Combine(dataRoot, "filesystem-sandbox"));
        using var externalCapabilityProvider = new WindowsExternalCapabilityProvider(dataRoot);
        // Computer use: the first view of a mission pays neither the UI Automation worker's start nor its first look.
        externalCapabilityProvider.Prewarm();
        _ = Task.Run(ChildProcessHandles.ReapOrphanedCompilers, CancellationToken.None);
        var installedApplicationProvider = new WindowsInstalledApplicationOpenProvider();
        // A look by an application's installed name finds its window as window.resolve does (ajuste c3).
        externalCapabilityProvider.ResolveApplicationsWith(installedApplicationProvider);
        // The catalog read (a cold PowerShell at sign-in) starts now, beside the
        // journal check, instead of after it; the hello waits for it only
        // within its own budget (CoreStartupBudget).
        var keptCatalog = new KeptApplicationCatalog(Path.Combine(dataRoot, KeptApplicationCatalog.FileName));
        Task<InstalledApplicationCatalogSnapshot> catalogRead = ReadAndKeepCatalogAsync(
            installedApplicationProvider, keptCatalog, cancellationToken);
        var audioControlProvider = new WindowsAudioControlProvider(
            Path.Combine(dataRoot, "audio", "control-state"));
        var systemStatusProvider = new WindowsSystemStatusProvider();
        var processStatusProvider = new WindowsProcessStatusProvider();
        var timeStatusProvider = new WindowsTimeStatusProvider();
        using var placeTimeZoneResolver = new OpenMeteoPlaceTimeZoneResolver();
        var gpuStatusProvider = new WindowsGpuStatusProvider();
        var windowControlProvider = new WindowsWindowControlProvider(installedApplicationProvider);
        var privatePayload = new WindowsProtectedPayload(
            Path.Combine(dataRoot, "security", "private-payload.v1.key"));
        var memoryStore = new LocalMemoryStore(
            Path.Combine(dataRoot, "memory-store"),
            privatePayload);
        var memoryCodec = new BoundProtectedJsonCodec(privatePayload);
        var memoryExportWriter = new LocalMemoryExportWriter();
        var networkStatusProvider = new WindowsNetworkStatusProvider();
        var networkDiagnosticProvider = new WindowsNetworkDiagnosticProvider();
        var networkIpProvider = new WindowsNetworkIpProvider();
        var networkPortProvider = new WindowsNetworkPortProvider();
        var identityProvider = new WindowsIdentityProvider();
        var appOpenHandler = new AppOpenHandler(installedApplicationProvider,windowIdFor: windowControlProvider.IssueFor);
        IOperationHandler[] handlers =
        [
            new AppInstalledHandler(installedApplicationProvider),
            new ApplicationWindowStatusHandler(installedApplicationProvider),
            appOpenHandler,
            new AppRestartHandler(windowControlProvider, appOpenHandler.ExecuteAsync),
            new AssistantStatusHandler(),
            new BaxyExitHandler(),
            new GameLaunchHandler(
                new ExternalCapabilityHandler("game.launch", externalCapabilityProvider),
                installedApplicationProvider,
                appOpenHandler.ExecuteAsync),
            new GameStoreHandler("game.store.page", "game", "title", appOpenHandler.ExecuteAsync),
            new CalculatorOpeningHandler(
                new ExternalCapabilityHandler("calculator.expression.evaluate", externalCapabilityProvider),
                appOpenHandler.ExecuteAsync),
            new PasteIntoNewDocumentHandler(
                new ExternalCapabilityHandler("clipboard.paste", externalCapabilityProvider), appOpenHandler.ExecuteAsync,
                OfficeNewDocumentPaste.TryAsync, appOpenHandler,
                new PasteDestinations(installedApplicationProvider).ResolveAsync),
            new GameStoreHandler("game.store.search", "results", "query", appOpenHandler.ExecuteAsync),
            new ExternalCapabilityHandler("audio.app.volume.adjust", externalCapabilityProvider),
            new ExternalCapabilityHandler("audio.app.volume.set", externalCapabilityProvider),
            new ExternalCapabilityHandler("audio.microphone.mute", externalCapabilityProvider),
            new ExternalCapabilityHandler("audio.microphone.status", externalCapabilityProvider),
            new AudioMuteHandler(audioControlProvider),
            new AudioStatusHandler(audioControlProvider),
            new AudioVolumeHandler(audioControlProvider),
            new ExternalCapabilityHandler("audio.volume.adjust", externalCapabilityProvider),
            .. ClipboardHandlers.Create(clipboardProvider),
            new ScreenshotCaptureHandler(
                screenshotProvider, "capture.active.window", activeWindow: true),
            new ScreenshotCaptureHandler(screenshotProvider),
            .. ConversationHandlers.Create(),
            .. FilesystemHandlers.Create(filesystemProvider),
            .. ExternalCapabilityHandlers.Create(externalCapabilityProvider, dataRoot, new KeyWindowReader()),
            new OwnSettingsHandler(dataRoot),
            .. MemoryHandlers.Create(
                memoryStore,
                memoryCodec,
                exportWriter: memoryExportWriter),
            new DnsStatusHandler(networkDiagnosticProvider),
            new NetworkPingHandler(networkDiagnosticProvider),
            new NetworkIpHandler(networkIpProvider),
            new NetworkPortHandler(networkPortProvider),
            new NetworkStatusHandler(networkStatusProvider),
            new CreateNoteHandler(noteStore),
            new ListNotesHandler(noteStore, taskStore),
            new ReadNoteHandler(noteStore),
            new RestoreNoteHandler(noteStore),
            new SearchNotesHandler(noteStore),
            new TrashNoteHandler(noteStore),
            new UpdateNoteHandler(noteStore),
            new SystemIdentityHandler(identityProvider),
            new SystemStatusHandler(systemStatusProvider, gpuStatusProvider),
            new ProcessListHandler(processStatusProvider),
            new TimeStatusHandler(timeStatusProvider, placeTimeZoneResolver),
            .. TaskHandlers.Create(taskStore, noteStore),
            .. WindowControlHandlers.Create(windowControlProvider),
        ];
        var registry = new OperationRegistry(handlers);
        ProductCatalog.ValidateAgainst(registry);
        // The journal check re-authenticates the live segment record by record
        // (seconds on a grown journal under load). It runs beside the catalog read
        // and the hello waits for it only within its budget (HelloJournalWait); no
        // request is read, let alone executed, until the journal is open and valid,
        // and a journal that fails validation still stops the core (UnreadableProfile).
        Task<FileInvocationJournal> journalOpen = Task.Run(
            async () => await OpenJournalAsync(
                    dataRoot,
                    privatePayload,
                    cancellationToken)
                .ConfigureAwait(false),
            cancellationToken);
        await using Stream input = Console.OpenStandardInput();
        await using Stream output = Console.OpenStandardOutput();
        var lineReader = new BoundedLineReader(input, MaximumLineBytes);

        try
        {
            await HelloJournalWait.WithinAsync(
                    journalOpen,
                    System.Diagnostics.Stopwatch.GetElapsedTime(StartedAt),
                    cancellationToken)
                .ConfigureAwait(false);
            ApplicationCatalogSnapshot? sent = await WriteHelloAsync(
                    output,
                    registry,
                    catalogRead,
                    keptCatalog,
                    externalCapabilityProvider,
                    cancellationToken)
                .ConfigureAwait(false);
            _ = SendLateCatalogAsync(output, catalogRead, sent, cancellationToken);
        }
        catch
        {
            await DiscardJournalAsync(journalOpen).ConfigureAwait(false);
            throw;
        }

        await using FileInvocationJournal journal = await journalOpen.ConfigureAwait(false);
        using var engine = new MissionEngine(
            registry,
            journal,
            new MissionEngineOptions
            {
                PrivateEnvelopeAuthenticator = new MemoryEnvelopeAuthenticator(
                    memoryCodec,
                    memoryExportWriter),
                ConfirmationMode = () => ConfirmationModeStore.Read(dataRoot),
            });

        while (!cancellationToken.IsCancellationRequested)
        {
            ProtocolLine? received = await lineReader.ReadAsync(cancellationToken).ConfigureAwait(false);
            if (received is null)
            {
                return 0;
            }

            if (received.Value.TooLarge || received.Value.Utf8 is not { Length: > 0 } utf8Line)
            {
                await WriteProtocolErrorAsync(
                    output,
                    "invalid_message_size",
                    "La solicitud está vacía o excede el tamaño permitido.",
                    cancellationToken).ConfigureAwait(false);
                continue;
            }

            OperationRequest request;
            try
            {
                request = ProtocolJson.DeserializeRequest(utf8Line);
            }
            catch (JsonException)
            {
                await WriteProtocolErrorAsync(
                    output,
                    "malformed_json",
                    "La solicitud no tiene un JSON válido para BAXY.",
                    cancellationToken).ConfigureAwait(false);
                continue;
            }

            OperationResponse response = await CoreRequest.ExecuteAsync(engine, request, Console.Error, cancellationToken)
                .ConfigureAwait(false);
            await WriteMessageAsync(
                output,
                CoreRequest.ToLine(request, response, MaximumLineBytes, Console.Error),
                cancellationToken).ConfigureAwait(false);
        }

        return 0;
    }

    private static async ValueTask<ApplicationCatalogSnapshot?> WriteHelloAsync(
        Stream output,
        OperationRegistry registry,
        Task<InstalledApplicationCatalogSnapshot> catalogRead,
        KeptApplicationCatalog keptCatalog,
        WindowsExternalCapabilityProvider externalCapabilityProvider,
        CancellationToken cancellationToken)
    {
        ProtocolHello hello = await CreateHelloAsync(
            registry,
            catalogRead,
            keptCatalog,
            externalCapabilityProvider,
            cancellationToken).ConfigureAwait(false);
        byte[] helloMessage = ProtocolJson.SerializeToUtf8Bytes(hello);
        if (helloMessage.Length > MaximumLineBytes)
        {
            hello = hello with
            {
                ApplicationCatalog = new ApplicationCatalogSnapshot(
                    ApplicationCatalogContract.CurrentVersion,
                    Verified: false,
                    Complete: false,
                    Array.Empty<string>()),
                GameCatalog = new GameCatalogSnapshot(
                    GameCatalogContract.CurrentVersion,
                    Verified: false,
                    Complete: false,
                    Array.Empty<GameCatalogEntry>()),
            };
            helloMessage = ProtocolJson.SerializeToUtf8Bytes(hello);
        }

        if (helloMessage.Length > MaximumLineBytes)
        {
            throw new InvalidDataException("The core hello exceeds the protocol line limit.");
        }

        await WriteMessageAsync(
            output,
            helloMessage,
            cancellationToken).ConfigureAwait(false);
        return hello.ApplicationCatalog;
    }

    // Ajuste c3 (humos del 31-10): a verified read is kept for the next start, whose read may be late.
    private static async Task<InstalledApplicationCatalogSnapshot> ReadAndKeepCatalogAsync(
        WindowsInstalledApplicationOpenProvider provider,
        KeptApplicationCatalog keptCatalog,
        CancellationToken cancellationToken)
    {
        InstalledApplicationCatalogSnapshot read = await provider.GetCatalogSnapshotAsync(cancellationToken)
            .ConfigureAwait(false);
        keptCatalog.Keep(read);
        return read;
    }

    // Ajuste c3 (humos del 31-10): a read that ends after the hello, saying other names than the hello did, goes to the
    // App at once (catalog.applications), so the mind is not left the whole session without the list. A failed read
    // or write sends nothing and is said on stderr; requests are answered as before.
    private static async Task SendLateCatalogAsync(
        Stream output,
        Task<InstalledApplicationCatalogSnapshot> catalogRead,
        ApplicationCatalogSnapshot? sent,
        CancellationToken cancellationToken)
    {
        try
        {
            InstalledApplicationCatalogSnapshot live = await catalogRead.ConfigureAwait(false);
            InstalledApplicationCatalogSnapshot? update = HelloCatalogWait.LateUpdate(
                sent is null ? new(false, false, []) : new(sent.Verified, sent.Complete, sent.Names), live);
            if (update is null)
            {
                return;
            }

            await WriteMessageAsync(
                output,
                ProtocolJson.SerializeToUtf8Bytes(new ApplicationCatalogUpdate(
                    ProtocolTypes.ApplicationCatalogUpdate,
                    new ApplicationCatalogSnapshot(
                        ApplicationCatalogContract.CurrentVersion, true, update.Complete, [.. update.Names]))),
                cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            Console.Error.WriteLine("BAXY core ended before sending the installed applications read late.");
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine($"BAXY core could not send the installed applications read late: {exception.GetType().Name}");
        }
    }

    /// <summary>
    /// Closes a journal whose open was still running when the start failed, so its
    /// file handle and key never outlive the core's own failure.
    /// </summary>
    private static async ValueTask DiscardJournalAsync(Task<FileInvocationJournal> journalOpen)
    {
        try
        {
            await (await journalOpen.ConfigureAwait(false)).DisposeAsync().ConfigureAwait(false);
        }
        catch (Exception)
        {
            // The start already failed; that failure is the one reported.
        }
    }

    private static async ValueTask<FileInvocationJournal> OpenJournalAsync(
        string dataRoot,
        IProtectedPayload privatePayload,
        CancellationToken cancellationToken)
    {
        string journalPath = Path.Combine(dataRoot, "journal", "missions.jsonl");
        string anchorPath = string.Concat(journalPath, ".anchor");
        string authenticationKeyPath = Path.Combine(
            dataRoot,
            "security",
            "journal-hmac.v2.key");
        LegacyJournalMigrationResult migration = LegacyJournalMigration.PreserveUnkeyedV1(
            journalPath,
            anchorPath,
            authenticationKeyPath);
        var keyStore = new WindowsJournalAuthenticationKeyStore(
            authenticationKeyPath,
            privatePayload);
        bool emptyJournal = File.Exists(journalPath)
            && new FileInfo(journalPath).Length == 0;
        bool allowCreateKey = !File.Exists(anchorPath)
            && (migration.Migrated || !File.Exists(journalPath) || emptyJournal);
        byte[] key = keyStore.LoadOrCreate(allowCreateKey);
        JournalHmacAuthenticator? authenticator = null;
        try
        {
            authenticator = new JournalHmacAuthenticator(key);
            FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
                    journalPath,
                    authenticator,
                    static diagnostic => Console.Error.WriteLine($"BAXY core: {diagnostic}"),
                    cancellationToken)
                .ConfigureAwait(false);
            authenticator = null;
            try
            {
                // Auditoría del núcleo 2026-10-23: what an earlier start left begun ends, authenticated, as abandoned
                // (its effect possibly standing), so it is never run again and holds no reservation.
                int abandoned = await journal.AbandonInterruptedAsync(cancellationToken).ConfigureAwait(false);
                if (abandoned > 0)
                {
                    Console.Error.WriteLine(
                        $"BAXY core: {abandoned} invocations an earlier start left begun ended as abandoned.");
                }
            }
            catch
            {
                await journal.DisposeAsync().ConfigureAwait(false);
                throw;
            }

            return journal;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(key);
            authenticator?.Dispose();
        }
    }

    private static async ValueTask<ProtocolHello> CreateHelloAsync(
        OperationRegistry registry,
        Task<InstalledApplicationCatalogSnapshot> applicationCatalogRead,
        KeptApplicationCatalog keptCatalog,
        WindowsExternalCapabilityProvider externalCapabilityProvider,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(applicationCatalogRead);
        ArgumentNullException.ThrowIfNull(externalCapabilityProvider);
        ProductCatalog.ValidateAgainst(registry);
        OperationDescriptor[] capabilities = registry.ToolDescriptors.ToArray();
        Version? version = typeof(Program).Assembly.GetName().Version;
        string coreVersion = version is null
            ? "0.1.0"
            : $"{version.Major}.{version.Minor}.{Math.Max(0, version.Build)}";
        ApplicationCatalogSnapshot applicationCatalog;
        try
        {
            InstalledApplicationCatalogSnapshot providerSnapshot =
                await HelloCatalogWait.WithinAsync(
                    applicationCatalogRead,
                    System.Diagnostics.Stopwatch.GetElapsedTime(StartedAt),
                    keptCatalog.Load,
                    cancellationToken).ConfigureAwait(false);
            applicationCatalog = new ApplicationCatalogSnapshot(
                ApplicationCatalogContract.CurrentVersion,
                providerSnapshot.Verified,
                providerSnapshot.Complete,
                providerSnapshot.Names.ToArray());
            ContractValidator.Validate(applicationCatalog);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception)
        {
            applicationCatalog = new ApplicationCatalogSnapshot(
                ApplicationCatalogContract.CurrentVersion,
                Verified: false,
                Complete: false,
                Array.Empty<string>());
        }

        GameCatalogSnapshot gameCatalog;
        try
        {
            InstalledGameCatalogSnapshot providerSnapshot =
                externalCapabilityProvider.GetInstalledGameCatalogSnapshot();
            gameCatalog = new GameCatalogSnapshot(
                GameCatalogContract.CurrentVersion,
                providerSnapshot.Verified,
                providerSnapshot.Complete,
                providerSnapshot.Entries
                    .Select(static entry => new GameCatalogEntry(
                        entry.Provider,
                        entry.AppId,
                        entry.Name))
                    .ToArray());
            ContractValidator.Validate(gameCatalog);
        }
        catch (Exception)
        {
            gameCatalog = new GameCatalogSnapshot(
                GameCatalogContract.CurrentVersion,
                Verified: false,
                Complete: false,
                Array.Empty<GameCatalogEntry>());
        }

        return new ProtocolHello(
            ProtocolTypes.Hello,
            ProtocolVersion.Current,
            coreVersion,
            Environment.ProcessId,
            capabilities,
            applicationCatalog,
            gameCatalog);
    }

    private static async ValueTask WriteProtocolErrorAsync(
        Stream output,
        string errorCode,
        string message,
        CancellationToken cancellationToken)
    {
        var error = new ProtocolError(ProtocolTypes.ProtocolError, errorCode, message);
        await WriteMessageAsync(
            output,
            ProtocolJson.SerializeToUtf8Bytes(error),
            cancellationToken).ConfigureAwait(false);
    }

    internal static async ValueTask WriteMessageAsync(
        Stream output,
        ReadOnlyMemory<byte> message,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(output);
        cancellationToken.ThrowIfCancellationRequested();

        ArrayPool<byte> pool = ArrayPool<byte>.Shared;
        int wireLength = checked(message.Length + 1);
        byte[] wire = pool.Rent(wireLength);
        // Ajuste c3: a late catalog (SendLateCatalogAsync) is written beside the responses; one line at a time.
        await OutputLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            message.Span.CopyTo(wire);
            wire[message.Length] = (byte)'\n';
            await output.WriteAsync(
                wire.AsMemory(0, wireLength),
                cancellationToken).ConfigureAwait(false);
            await output.FlushAsync(cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            OutputLock.Release();
            CryptographicOperations.ZeroMemory(wire.AsSpan(0, wireLength));
            pool.Return(wire);
        }
    }

    private static string ResolveDataRoot()
    {
        string? configured = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        string root = string.IsNullOrWhiteSpace(configured)
            ? Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "BAXY",
                "1")
            : configured;
        return WindowsPrivateStorage.PreparePrivateDataRoot(root);
    }

    private static string CreateMutexName(string dataRoot)
    {
        byte[] digest = SHA256.HashData(Encoding.UTF8.GetBytes(dataRoot.ToUpperInvariant()));
        return $"Local\\BAXY.Core.{Convert.ToHexString(digest.AsSpan(0, 12))}";
    }

    internal readonly record struct ProtocolLine(byte[]? Utf8, bool TooLarge);

    internal sealed class BoundedLineReader
    {
        private readonly Stream _input;
        private readonly int _maximumLineBytes;
        private readonly byte[] _buffer = new byte[8192];
        private int _bufferOffset;
        private int _bufferCount;

        public BoundedLineReader(Stream input, int maximumLineBytes)
        {
            _input = input ?? throw new ArgumentNullException(nameof(input));
            ArgumentOutOfRangeException.ThrowIfNegativeOrZero(maximumLineBytes);
            _maximumLineBytes = maximumLineBytes;
        }

        public async ValueTask<ProtocolLine?> ReadAsync(CancellationToken cancellationToken)
        {
            MemoryStream? payload = null;
            bool tooLarge = false;
            bool sawData = false;

            try
            {
                while (true)
                {
                    if (_bufferCount == 0)
                    {
                        _bufferOffset = 0;
                        _bufferCount = await _input.ReadAsync(_buffer, cancellationToken)
                            .ConfigureAwait(false);
                        if (_bufferCount == 0)
                        {
                            return sawData ? CreateResult(payload, tooLarge) : null;
                        }
                    }

                    ReadOnlySpan<byte> available = _buffer.AsSpan(_bufferOffset, _bufferCount);
                    int newlineIndex = available.IndexOf((byte)'\n');
                    int bytesBeforeNewline = newlineIndex >= 0 ? newlineIndex : available.Length;
                    if (newlineIndex >= 0 && payload is null)
                    {
                        int fastPathConsumed = bytesBeforeNewline + 1;
                        _bufferOffset += fastPathConsumed;
                        _bufferCount -= fastPathConsumed;
                        return CreateResult(available[..bytesBeforeNewline]);
                    }

                    if (bytesBeforeNewline > 0)
                    {
                        sawData = true;
                        if (!tooLarge)
                        {
                            payload ??= new MemoryStream(
                                capacity: (int)Math.Min(
                                    _maximumLineBytes + 1L,
                                    _buffer.Length));
                            long remaining = _maximumLineBytes + 1L - payload.Length;
                            if (bytesBeforeNewline <= remaining)
                            {
                                payload.Write(available[..bytesBeforeNewline]);
                            }
                            else
                            {
                                tooLarge = true;
                            }
                        }
                    }

                    int consumed = bytesBeforeNewline + (newlineIndex >= 0 ? 1 : 0);
                    _bufferOffset += consumed;
                    _bufferCount -= consumed;
                    if (newlineIndex >= 0)
                    {
                        return CreateResult(payload, tooLarge);
                    }
                }
            }
            finally
            {
                payload?.Dispose();
            }
        }

        private ProtocolLine CreateResult(MemoryStream? payload, bool tooLarge)
        {
            if (tooLarge)
            {
                return new ProtocolLine(null, TooLarge: true);
            }

            byte[] bytes = payload?.ToArray() ?? [];
            if (bytes.Length > 0 && bytes[^1] == (byte)'\r')
            {
                Array.Resize(ref bytes, bytes.Length - 1);
            }

            return bytes.Length <= _maximumLineBytes
                ? new ProtocolLine(bytes, TooLarge: false)
                : new ProtocolLine(null, TooLarge: true);
        }

        private ProtocolLine CreateResult(ReadOnlySpan<byte> payload)
        {
            if (payload.Length > 0 && payload[^1] == (byte)'\r')
            {
                payload = payload[..^1];
            }

            return payload.Length <= _maximumLineBytes
                ? new ProtocolLine(payload.ToArray(), TooLarge: false)
                : new ProtocolLine(null, TooLarge: true);
        }
    }
}
