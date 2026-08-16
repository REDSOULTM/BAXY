using System.Buffers;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace Baxy.App;

internal sealed class LocalJsonlSidecarDefinition
{
    internal LocalJsonlSidecarDefinition(
        string name,
        string executablePath,
        string workingDirectory,
        IReadOnlyList<string>? arguments = null,
        IReadOnlyDictionary<string, string>? environment = null,
        bool drainStandardError = true)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(name);
        ArgumentException.ThrowIfNullOrWhiteSpace(executablePath);
        ArgumentException.ThrowIfNullOrWhiteSpace(workingDirectory);

        string executable = Path.GetFullPath(executablePath);
        string directory = Path.GetFullPath(workingDirectory);
        if (!Path.IsPathFullyQualified(executable)
            || !Path.IsPathFullyQualified(directory)
            || !File.Exists(executable)
            || !Directory.Exists(directory))
        {
            throw new ArgumentException("El sidecar local debe usar rutas absolutas existentes.");
        }

        Name = name;
        ExecutablePath = executable;
        WorkingDirectory = directory;
        Arguments = Array.AsReadOnly(arguments?.ToArray() ?? []);
        Environment = new Dictionary<string, string>(
            environment ?? new Dictionary<string, string>(),
            StringComparer.Ordinal);
        DrainStandardError = drainStandardError;
    }

    internal string Name { get; }

    internal string ExecutablePath { get; }

    internal string WorkingDirectory { get; }

    internal IReadOnlyList<string> Arguments { get; }

    internal IReadOnlyDictionary<string, string> Environment { get; }

    internal bool DrainStandardError { get; }
}

internal sealed class LocalJsonlSidecarProcess : IAsyncDisposable
{
    private const int StandardErrorBufferBytes = 8 * 1024;
    private readonly Process _process;
    private readonly CancellationTokenSource _standardErrorPumpCancellation = new();
    private readonly Task _standardErrorPump;
    private SafeFileHandle? _job;
    private long _standardErrorBytesObserved;
    private int _stopped;

    private LocalJsonlSidecarProcess(
        LocalJsonlSidecarDefinition definition,
        Process process,
        SafeFileHandle job)
    {
        Definition = definition;
        _process = process;
        _job = job;
        _standardErrorPump = definition.DrainStandardError
            ? PumpStandardErrorAsync(
                process.StandardError.BaseStream,
                _standardErrorPumpCancellation.Token)
            : Task.CompletedTask;
    }

    internal LocalJsonlSidecarDefinition Definition { get; }

    internal Process Process => _process;

    internal long StandardErrorBytesObserved =>
        Interlocked.Read(ref _standardErrorBytesObserved);

    internal bool IsStandardErrorPumpCompleted => _standardErrorPump.IsCompleted;

    internal ValueTask WriteUtf8LineAsync(
        ReadOnlyMemory<byte> utf8Line,
        CancellationToken cancellationToken) =>
        WriteUtf8LineAsync(
            _process.StandardInput.BaseStream,
            utf8Line,
            cancellationToken);

    internal static async ValueTask WriteUtf8LineAsync(
        Stream output,
        ReadOnlyMemory<byte> utf8Line,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(output);
        cancellationToken.ThrowIfCancellationRequested();

        int wireLength = checked(utf8Line.Length + 1);
        byte[] wire = ArrayPool<byte>.Shared.Rent(wireLength);
        try
        {
            utf8Line.Span.CopyTo(wire);
            wire[utf8Line.Length] = (byte)'\n';
            await output.WriteAsync(
                wire.AsMemory(0, wireLength),
                cancellationToken).ConfigureAwait(false);
            await output.FlushAsync(cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(wire.AsSpan(0, wireLength));
            ArrayPool<byte>.Shared.Return(wire);
        }
    }

    internal static LocalJsonlSidecarProcess Start(LocalJsonlSidecarDefinition definition)
    {
        ArgumentNullException.ThrowIfNull(definition);
        var startInfo = new ProcessStartInfo
        {
            FileName = definition.ExecutablePath,
            WorkingDirectory = definition.WorkingDirectory,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardInputEncoding = StrictUtf8,
            StandardOutputEncoding = StrictUtf8,
            StandardErrorEncoding = StrictUtf8,
        };
        foreach (string argument in definition.Arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }

        foreach ((string key, string value) in definition.Environment)
        {
            startInfo.Environment[key] = value;
        }

        var process = new Process
        {
            StartInfo = startInfo,
            EnableRaisingEvents = true,
        };
        SafeFileHandle? job = null;
        try
        {
            if (!process.Start())
            {
                throw new InvalidOperationException(
                    $"No se pudo iniciar el sidecar local '{definition.Name}'.");
            }

            job = WindowsKillOnCloseJob.CreateAndAssign(process);
            var sidecar = new LocalJsonlSidecarProcess(definition, process, job);
            job = null;
            return sidecar;
        }
        catch
        {
            job?.Dispose();
            TryTerminate(process);
            process.Dispose();
            throw;
        }
    }

    internal async Task StopAsync()
    {
        if (Interlocked.Exchange(ref _stopped, 1) != 0)
        {
            return;
        }

        try
        {
            if (!TryHasExited(_process))
            {
                try
                {
                    _process.StandardInput.Close();
                }
                catch (Exception exception) when (exception is InvalidOperationException or IOException)
                {
                }

                _ = await TryWaitForExitAsync(_process, TimeSpan.FromSeconds(2))
                    .ConfigureAwait(false);
            }

            if (!TryHasExited(_process))
            {
                _job?.Dispose();
                _job = null;
                _ = await TryWaitForExitAsync(_process, TimeSpan.FromSeconds(2))
                    .ConfigureAwait(false);
            }

            if (!TryHasExited(_process))
            {
                TryTerminate(_process);
                _ = await TryWaitForExitAsync(_process, TimeSpan.FromSeconds(2))
                    .ConfigureAwait(false);
            }
        }
        finally
        {
            _job?.Dispose();
            _job = null;
            _standardErrorPumpCancellation.Cancel();
            await ObserveStandardErrorPumpAsync().ConfigureAwait(false);
            _standardErrorPumpCancellation.Dispose();
        }
    }

    public async ValueTask DisposeAsync()
    {
        await StopAsync().ConfigureAwait(false);
        _process.Dispose();
    }

    private static UTF8Encoding StrictUtf8 { get; } =
        new(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true);

    private async Task PumpStandardErrorAsync(
        Stream standardError,
        CancellationToken cancellationToken)
    {
        byte[] buffer = ArrayPool<byte>.Shared.Rent(StandardErrorBufferBytes);
        try
        {
            while (true)
            {
                int read = await standardError.ReadAsync(
                    buffer.AsMemory(0, StandardErrorBufferBytes),
                    cancellationToken).ConfigureAwait(false);
                if (read == 0)
                {
                    return;
                }

                Interlocked.Add(ref _standardErrorBytesObserved, read);
                CryptographicOperations.ZeroMemory(buffer.AsSpan(0, read));
            }
        }
        catch (Exception exception) when (
            exception is OperationCanceledException
                or IOException
                or InvalidOperationException
                or NotSupportedException)
        {
            // stderr is diagnostic-only. Draining it must never surface traces
            // or make the JSONL protocol unavailable during shutdown.
        }
        finally
        {
            CryptographicOperations.ZeroMemory(buffer);
            ArrayPool<byte>.Shared.Return(buffer);
        }
    }

    private async Task ObserveStandardErrorPumpAsync()
    {
        _ = await ReapPumpWithinAsync(
            _standardErrorPump,
            () =>
            {
                try
                {
                    _process.StandardError.Close();
                }
                catch (Exception exception) when (
                    exception is InvalidOperationException or IOException)
                {
                }
            },
            TimeSpan.FromSeconds(2)).ConfigureAwait(false);
    }

    internal static async Task<bool> ReapPumpWithinAsync(
        Task pump,
        Action close,
        TimeSpan stageTimeout)
    {
        ArgumentNullException.ThrowIfNull(pump);
        ArgumentNullException.ThrowIfNull(close);
        ArgumentOutOfRangeException.ThrowIfLessThanOrEqual(
            stageTimeout,
            TimeSpan.Zero);
        if (await TryObservePumpWithinAsync(pump, stageTimeout).ConfigureAwait(false))
        {
            return true;
        }

        close();
        if (await TryObservePumpWithinAsync(pump, stageTimeout).ConfigureAwait(false))
        {
            return true;
        }

        _ = pump.ContinueWith(
            static completed =>
            {
                _ = completed.Exception;
            },
            CancellationToken.None,
            TaskContinuationOptions.OnlyOnFaulted
                | TaskContinuationOptions.ExecuteSynchronously,
            TaskScheduler.Default);
        return false;
    }

    private static async Task<bool> TryObservePumpWithinAsync(
        Task pump,
        TimeSpan timeout)
    {
        try
        {
            await pump.WaitAsync(timeout).ConfigureAwait(false);
            return true;
        }
        catch (TimeoutException)
        {
            return false;
        }
        catch (Exception)
        {
            // A diagnostic-only pump failure is observed but never escalated
            // through the JSONL sidecar lifecycle.
            return true;
        }
    }

    private static bool TryHasExited(Process process)
    {
        try
        {
            return process.HasExited;
        }
        catch (Exception exception) when (
            exception is InvalidOperationException or Win32Exception or NotSupportedException)
        {
            return false;
        }
    }

    private static async Task<bool> TryWaitForExitAsync(Process process, TimeSpan timeout)
    {
        using var cancellation = new CancellationTokenSource(timeout);
        try
        {
            await process.WaitForExitAsync(cancellation.Token).ConfigureAwait(false);
            return true;
        }
        catch (Exception exception) when (
            exception is OperationCanceledException
                or InvalidOperationException
                or Win32Exception
                or NotSupportedException)
        {
            return false;
        }
    }

    private static void TryTerminate(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch (Exception exception) when (
            exception is InvalidOperationException or Win32Exception or NotSupportedException)
        {
        }
    }
}

internal static class WindowsKillOnCloseJob
{
    private const uint BreakawayOk = 0x00000800;
    private const uint KillOnJobClose = 0x00002000;
    private const int ExtendedLimitInformation = 9;

    internal static SafeFileHandle CreateAndAssign(Process process)
    {
        ArgumentNullException.ThrowIfNull(process);
        SafeFileHandle job = NativeMethods.CreateJobObject(IntPtr.Zero, null);
        if (job.IsInvalid)
        {
            throw new InvalidOperationException("No se pudo crear el Job Object del sidecar local.");
        }

        var information = new JobObjectExtendedLimitInformation
        {
            BasicLimitInformation = new JobObjectBasicLimitInformation
            {
                // Trusted application launches may explicitly break away. Every
                // sidecar process itself remains owned by this kill-on-close job.
                LimitFlags = KillOnJobClose | BreakawayOk,
            },
        };
        int size = Marshal.SizeOf<JobObjectExtendedLimitInformation>();
        IntPtr pointer = Marshal.AllocHGlobal(size);
        try
        {
            Marshal.StructureToPtr(information, pointer, fDeleteOld: false);
            if (!NativeMethods.SetInformationJobObject(
                    job,
                    ExtendedLimitInformation,
                    pointer,
                    checked((uint)size))
                || !NativeMethods.AssignProcessToJobObject(job, process.Handle))
            {
                throw new InvalidOperationException(
                    "No se pudo vincular el sidecar local al ciclo de vida de BAXY.");
            }

            return job;
        }
        catch
        {
            job.Dispose();
            throw;
        }
        finally
        {
            Marshal.FreeHGlobal(pointer);
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct JobObjectBasicLimitInformation
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public nuint MinimumWorkingSetSize;
        public nuint MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public nuint Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct IoCounters
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct JobObjectExtendedLimitInformation
    {
        public JobObjectBasicLimitInformation BasicLimitInformation;
        public IoCounters IoInfo;
        public nuint ProcessMemoryLimit;
        public nuint JobMemoryLimit;
        public nuint PeakProcessMemoryUsed;
        public nuint PeakJobMemoryUsed;
    }

    private static partial class NativeMethods
    {
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern SafeFileHandle CreateJobObject(IntPtr jobAttributes, string? name);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool SetInformationJobObject(
            SafeFileHandle job,
            int informationClass,
            IntPtr information,
            uint length);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static extern bool AssignProcessToJobObject(SafeFileHandle job, IntPtr process);
    }
}
