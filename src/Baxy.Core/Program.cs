using System.Buffers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.Clipboard;
using Baxy.Providers.Windows.Capture;
using Baxy.Providers.Windows.Filesystem;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Memory;
using Baxy.Providers.Windows.Network;
using Baxy.Providers.Windows.Notes;
using Baxy.Providers.Windows.Routines;
using Baxy.Providers.Windows.SystemStatus;
using Baxy.Providers.Windows.Tasks;
using Baxy.Providers.Windows.Windows;
using Baxy.Security.Windows;

namespace Baxy.Core;

internal static class Program
{
    private const int MaximumLineBytes = 1024 * 1024;

    public static async Task<int> Main()
    {
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
        catch (JournalIntegrityException)
        {
            Console.Error.WriteLine("BAXY core stopped because its mission journal failed integrity validation.");
            return 74;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine($"BAXY core stopped safely ({exception.GetType().Name}).");
            return 70;
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
        var reminderStore = new LocalTaskStore(Path.Combine(dataRoot, "reminders-store"));
        var routineStore = new LocalRoutineStore(Path.Combine(dataRoot, "routines-store"));
        var clipboardProvider = new WindowsClipboardProvider();
        var screenshotProvider = new WindowsScreenshotProvider(Path.Combine(dataRoot, "captures"));
        var filesystemProvider = new LocalFilesystemProvider(
            Path.Combine(dataRoot, "filesystem-sandbox"));
        using var externalCapabilityProvider = new WindowsExternalCapabilityProvider(dataRoot);
        var installedApplicationProvider = new WindowsInstalledApplicationOpenProvider();
        var routedApplicationOpenProvider = new ApplicationOpenProviderRouter(
            new WindowsCalculatorOpenProvider(),
            installedApplicationProvider);
        var audioControlProvider = new WindowsAudioControlProvider(
            Path.Combine(dataRoot, "audio", "control-state"));
        var systemStatusProvider = new WindowsSystemStatusProvider();
        var processStatusProvider = new WindowsProcessStatusProvider();
        var timeStatusProvider = new WindowsTimeStatusProvider();
        var gpuStatusProvider = new WindowsGpuStatusProvider();
        var windowControlProvider = new WindowsWindowControlProvider();
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
        IOperationHandler[] handlers =
        [
            new AppStatusHandler(),
            new AppInstalledHandler(installedApplicationProvider),
            new ApplicationWindowStatusHandler(installedApplicationProvider),
            new AppOpenHandler(routedApplicationOpenProvider),
            new ExternalCapabilityHandler("audio.microphone.mute", externalCapabilityProvider),
            new AudioMuteHandler(audioControlProvider),
            new AudioStatusHandler(audioControlProvider),
            new AudioVolumeHandler(audioControlProvider),
            new ExternalCapabilityHandler("audio.volume.adjust", externalCapabilityProvider),
            .. ClipboardHandlers.Create(clipboardProvider),
            new ScreenshotCaptureHandler(
                screenshotProvider, "capture.active.window", activeWindow: true),
            new ScreenshotCaptureHandler(screenshotProvider),
            .. FilesystemHandlers.Create(filesystemProvider),
            .. ExternalCapabilityHandlers.Create(externalCapabilityProvider),
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
            new ListNotesHandler(noteStore),
            new ReadNoteHandler(noteStore),
            new RestoreNoteHandler(noteStore),
            new SearchNotesHandler(noteStore),
            new TrashNoteHandler(noteStore),
            new UpdateNoteHandler(noteStore),
            new SystemIdentityHandler(identityProvider),
            new SystemStatusHandler(systemStatusProvider, gpuStatusProvider),
            new ProcessListHandler(processStatusProvider),
            new TimeStatusHandler(timeStatusProvider),
            .. ReminderHandlers.Create(reminderStore),
            .. RoutineHandlers.Create(routineStore),
            .. TaskHandlers.Create(taskStore),
            .. WindowControlHandlers.Create(windowControlProvider),
        ];
        var registry = new OperationRegistry(handlers);
        ProductCatalog.ValidateAgainst(registry);
        await using FileInvocationJournal journal = await OpenJournalAsync(
            dataRoot,
            privatePayload,
            cancellationToken).ConfigureAwait(false);
        using var engine = new MissionEngine(
            registry,
            journal,
            new MemoryEnvelopeAuthenticator(memoryCodec, memoryExportWriter),
            ProductOperationNarrator.Instance);
        await using Stream input = Console.OpenStandardInput();
        await using Stream output = Console.OpenStandardOutput();
        var lineReader = new BoundedLineReader(input, MaximumLineBytes);

        ProtocolHello hello = await CreateHelloAsync(
            registry,
            installedApplicationProvider,
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

            OperationResponse response = await engine.ExecuteAsync(request, cancellationToken)
                .ConfigureAwait(false);
            await WriteMessageAsync(
                output,
                ProtocolJson.SerializeBoundedToUtf8Bytes(response, MaximumLineBytes),
                cancellationToken).ConfigureAwait(false);
        }

        return 0;
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
                    cancellationToken)
                .ConfigureAwait(false);
            authenticator = null;
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
        WindowsInstalledApplicationOpenProvider applicationCatalogProvider,
        WindowsExternalCapabilityProvider externalCapabilityProvider,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(applicationCatalogProvider);
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
                await applicationCatalogProvider
                    .GetCatalogSnapshotAsync(cancellationToken)
                    .ConfigureAwait(false);
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

    internal static ValueTask WriteMessageAsync(
        Stream output,
        ReadOnlyMemory<byte> message,
        CancellationToken cancellationToken) =>
        WriteMessageAsync(
            output,
            message,
            ArrayPool<byte>.Shared,
            cancellationToken);

    internal static async ValueTask WriteMessageAsync(
        Stream output,
        ReadOnlyMemory<byte> message,
        ArrayPool<byte> pool,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(output);
        ArgumentNullException.ThrowIfNull(pool);
        cancellationToken.ThrowIfCancellationRequested();

        int wireLength = checked(message.Length + 1);
        byte[] wire = pool.Rent(wireLength);
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
