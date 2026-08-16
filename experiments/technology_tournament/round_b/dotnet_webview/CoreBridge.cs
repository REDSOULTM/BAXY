using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Tournament.RoundB.Dotnet;

internal sealed class CoreBridge : IAsyncDisposable
{
    private readonly Process _process;
    private readonly SafeFileHandle _job;
    private readonly SemaphoreSlim _turnLock = new(1, 1);

    private CoreBridge(Process process, SafeFileHandle job)
    {
        _process = process;
        _job = job;
    }

    public static CoreBridge Start()
    {
        var executable = Environment.GetEnvironmentVariable("BAXY_ROUND_B_CORE");
        if (string.IsNullOrWhiteSpace(executable))
        {
            executable = Path.Combine(AppContext.BaseDirectory, "core", "baxy-core.exe");
        }
        executable = Path.GetFullPath(executable);
        if (!File.Exists(executable))
        {
            throw new FileNotFoundException("No se encontró el core local empaquetado.", executable);
        }

        var root = Environment.GetEnvironmentVariable("BAXY_ROUND_B_DATA");
        if (string.IsNullOrWhiteSpace(root))
        {
            root = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "BAXY",
                "TournamentDotnet");
        }
        root = Path.GetFullPath(root);
        Directory.CreateDirectory(root);

        var start = new ProcessStartInfo
        {
            FileName = executable,
            Arguments = "--server",
            WorkingDirectory = Path.GetDirectoryName(executable)!,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardInputEncoding = new UTF8Encoding(false),
            StandardOutputEncoding = new UTF8Encoding(false),
            StandardErrorEncoding = new UTF8Encoding(false),
        };
        start.Environment["BAXY_TOURNAMENT_ROOT"] = root;
        start.Environment["BAXY_FIXED_WORKSPACE"] = Path.Combine(root, "workspace");
        var process = Process.Start(start) ?? throw new InvalidOperationException("El core local no pudo iniciarse.");
        try
        {
            var job = ProcessJob.CreateAndAssign(process);
            process.BeginErrorReadLine();
            return new CoreBridge(process, job);
        }
        catch
        {
            if (!process.HasExited) process.Kill(entireProcessTree: true);
            process.Dispose();
            throw;
        }
    }

    public async Task<string> SubmitAsync(string requestJson, CancellationToken cancellationToken)
    {
        using var requestDocument = JsonDocument.Parse(requestJson);
        var request = requestDocument.RootElement;
        var invocationId = request.GetProperty("invocation_id").GetString();
        var message = request.GetProperty("message").GetString();
        if (string.IsNullOrWhiteSpace(invocationId) || message is null)
        {
            throw new InvalidDataException("Petición de interfaz incompleta.");
        }
        var root = _process.StartInfo.Environment["BAXY_TOURNAMENT_ROOT"]!;
        var workspace = Path.Combine(root, "workspace");
        var wire = JsonSerializer.Serialize(new
        {
            invocation_id = invocationId,
            message,
            workspace,
        });

        await _turnLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_process.HasExited)
            {
                throw new InvalidOperationException("El core local terminó antes de responder.");
            }
            await _process.StandardInput.WriteLineAsync(wire.AsMemory(), cancellationToken).ConfigureAwait(false);
            await _process.StandardInput.FlushAsync(cancellationToken).ConfigureAwait(false);
            var output = await _process.StandardOutput.ReadLineAsync(cancellationToken).ConfigureAwait(false);
            if (string.IsNullOrWhiteSpace(output))
            {
                throw new InvalidDataException("El core local no devolvió un resultado.");
            }
            using var validation = JsonDocument.Parse(output);
            if (validation.RootElement.GetProperty("invocation_id").GetString() != invocationId)
            {
                throw new InvalidDataException("El core respondió para otra invocación.");
            }
            return output;
        }
        finally
        {
            _turnLock.Release();
        }
    }

    public async ValueTask DisposeAsync()
    {
        try
        {
            _process.StandardInput.Close();
            if (!_process.HasExited && !await WaitForExitAsync(_process, TimeSpan.FromSeconds(2)).ConfigureAwait(false))
            {
                _process.Kill(entireProcessTree: true);
                await _process.WaitForExitAsync().ConfigureAwait(false);
            }
        }
        catch (InvalidOperationException)
        {
            // The process already ended between the state check and cleanup.
        }
        finally
        {
            _turnLock.Dispose();
            _process.Dispose();
            _job.Dispose();
        }
    }

    private static async Task<bool> WaitForExitAsync(Process process, TimeSpan timeout)
    {
        using var cancellation = new CancellationTokenSource(timeout);
        try
        {
            await process.WaitForExitAsync(cancellation.Token).ConfigureAwait(false);
            return true;
        }
        catch (OperationCanceledException)
        {
            return false;
        }
    }

    private static class ProcessJob
    {
        private const uint KillOnJobClose = 0x00002000;
        private const int ExtendedLimitInformation = 9;

        public static SafeFileHandle CreateAndAssign(Process process)
        {
            var job = CreateJobObject(IntPtr.Zero, null);
            if (job.IsInvalid) throw new InvalidOperationException("No se pudo crear el propietario de procesos locales.");
            var information = new JobObjectExtendedLimitInformation
            {
                BasicLimitInformation = new JobObjectBasicLimitInformation { LimitFlags = KillOnJobClose },
            };
            var size = Marshal.SizeOf<JobObjectExtendedLimitInformation>();
            var pointer = Marshal.AllocHGlobal(size);
            try
            {
                Marshal.StructureToPtr(information, pointer, false);
                if (!SetInformationJobObject(job, ExtendedLimitInformation, pointer, (uint)size)
                    || !AssignProcessToJobObject(job, process.Handle))
                {
                    throw new InvalidOperationException("No se pudo vincular el core al ciclo de vida de BAXY.");
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

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern SafeFileHandle CreateJobObject(IntPtr jobAttributes, string? name);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetInformationJobObject(SafeFileHandle job, int informationClass, IntPtr information, uint length);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool AssignProcessToJobObject(SafeFileHandle job, IntPtr process);
    }
}
