param(
    [string]$BuildRoot,
    [string]$EvidencePath,
    [switch]$AllowCloseVerifiedNotepadInQuiescentSession
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'path_safety.ps1')
. (Join-Path $PSScriptRoot 'build_layout.ps1')

# Keep the gate aligned with the public baxy.local.v1 message bound. The hello
# contains the complete authenticated schema catalog and legitimately grows
# beyond 64 KiB as capabilities are added.
$maximumJsonLineBytes = 1024 * 1024
$maximumStderrBytes = 2 * 1024
$messageTimeout = [TimeSpan]::FromSeconds(10)
$processExitTimeoutMilliseconds = 5000

if ($null -eq ('BaxyAppOpenGateNative' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Win32.SafeHandles;

public sealed class BaxyAppOpenGatePackageIdentity
{
    public BaxyAppOpenGatePackageIdentity(string familyName, string fullName)
    {
        FamilyName = familyName;
        FullName = fullName;
    }

    public string FamilyName { get; private set; }
    public string FullName { get; private set; }
}

public static class BaxyAppOpenGateNative
{
    private const uint WaitTimeout = 0x00000102;
    private const int MaximumPathCharacters = 32768;
    private const uint MaximumPackageIdentityCharacters = 4096;
    private const int ExtendedLimitInformation = 9;
    private const int ErrorSuccess = 0;
    private const int ErrorInsufficientBuffer = 122;
    private const int AppModelErrorNoPackage = 15700;
    private const uint InvalidFileAttributes = 0xFFFFFFFF;
    private const uint FileAttributeReparsePoint = 0x00000400;
    public const uint RequiredJobLimitFlags = 0x00002000 | 0x00000800;

    [StructLayout(LayoutKind.Sequential)]
    private struct JobObjectBasicLimitInformation
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
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
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }

    [DllImport(
        "kernel32.dll",
        EntryPoint = "CreateJobObjectW",
        CharSet = CharSet.Unicode,
        ExactSpelling = true,
        SetLastError = true)]
    private static extern SafeFileHandle CreateJobObjectW(
        IntPtr jobAttributes,
        string name);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetInformationJobObject(
        SafeFileHandle job,
        int informationClass,
        IntPtr information,
        uint length);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool QueryInformationJobObject(
        SafeFileHandle job,
        int informationClass,
        IntPtr information,
        uint length,
        IntPtr returnedLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool AssignProcessToJobObject(
        SafeFileHandle job,
        SafeProcessHandle process);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsProcessInJob(
        SafeProcessHandle process,
        SafeFileHandle job,
        [MarshalAs(UnmanagedType.Bool)] out bool result);

    [DllImport(
        "kernel32.dll",
        EntryPoint = "GetPackageFamilyName",
        CharSet = CharSet.Unicode,
        ExactSpelling = true)]
    private static extern int GetPackageFamilyName(
        SafeProcessHandle process,
        ref uint packageFamilyNameLength,
        StringBuilder packageFamilyName);

    [DllImport(
        "kernel32.dll",
        EntryPoint = "GetPackageFullName",
        CharSet = CharSet.Unicode,
        ExactSpelling = true)]
    private static extern int GetPackageFullName(
        SafeProcessHandle process,
        ref uint packageFullNameLength,
        StringBuilder packageFullName);

    [DllImport(
        "kernel32.dll",
        EntryPoint = "QueryFullProcessImageNameW",
        CharSet = CharSet.Unicode,
        ExactSpelling = true,
        SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool QueryFullProcessImageNameW(
        SafeProcessHandle process,
        uint flags,
        StringBuilder executablePath,
        ref uint size);

    [DllImport(
        "kernel32.dll",
        EntryPoint = "GetFileAttributesW",
        CharSet = CharSet.Unicode,
        ExactSpelling = true,
        SetLastError = true)]
    private static extern uint GetFileAttributesW(string path);

    [DllImport("kernel32.dll")]
    private static extern uint WaitForSingleObject(
        SafeProcessHandle handle,
        uint milliseconds);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindow(IntPtr window);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsWindowVisible(IntPtr window);

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(
        IntPtr window,
        out uint processId);

    public static bool IsProcessRunning(SafeProcessHandle handle)
    {
        return handle != null
            && !handle.IsInvalid
            && !handle.IsClosed
            && WaitForSingleObject(handle, 0) == WaitTimeout;
    }

    public static string QueryProcessPath(SafeProcessHandle handle)
    {
        if (handle == null || handle.IsInvalid || handle.IsClosed)
        {
            throw new InvalidOperationException("The process handle is not usable.");
        }

        StringBuilder path = new StringBuilder(MaximumPathCharacters);
        uint length = MaximumPathCharacters;
        if (!QueryFullProcessImageNameW(handle, 0, path, ref length)
            || length == 0
            || length >= MaximumPathCharacters)
        {
            throw new InvalidOperationException("Windows could not corroborate the executable path.");
        }

        return path.ToString();
    }

    public static BaxyAppOpenGatePackageIdentity QueryPackageIdentity(
        SafeProcessHandle handle)
    {
        if (handle == null || handle.IsInvalid || handle.IsClosed)
        {
            throw new InvalidOperationException("The process handle is not usable.");
        }

        string familyName = QueryPackageFamilyName(handle);
        string fullName = QueryPackageFullName(handle);
        if (familyName == null && fullName == null)
        {
            return null;
        }

        if (familyName == null || fullName == null)
        {
            throw new InvalidOperationException("Windows returned an incomplete package identity.");
        }

        return new BaxyAppOpenGatePackageIdentity(familyName, fullName);
    }

    public static bool PathChainHasNoReparsePoint(string path)
    {
        string fullPath = Path.GetFullPath(path);
        string root = Path.GetPathRoot(fullPath);
        if (String.IsNullOrEmpty(root))
        {
            throw new InvalidOperationException("The path has no absolute root.");
        }

        if (!VerifyPathComponent(root))
        {
            return false;
        }
        string current = root;
        string relative = fullPath.Substring(root.Length);
        foreach (string component in relative.Split(
            new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar },
            StringSplitOptions.RemoveEmptyEntries))
        {
            current = Path.Combine(current, component);
            if (!VerifyPathComponent(current))
            {
                return false;
            }
        }

        return true;
    }

    private static bool VerifyPathComponent(string path)
    {
        uint attributes = GetFileAttributesW(path);
        if (attributes == InvalidFileAttributes)
        {
            throw new InvalidOperationException(
                "Windows could not inspect a path component without traversal.");
        }

        return (attributes & FileAttributeReparsePoint) == 0;
    }

    private static string QueryPackageFamilyName(SafeProcessHandle handle)
    {
        uint length = 0;
        int result = GetPackageFamilyName(handle, ref length, null);
        if (result == AppModelErrorNoPackage)
        {
            return null;
        }

        if (result != ErrorInsufficientBuffer
            || length == 0
            || length > MaximumPackageIdentityCharacters)
        {
            throw new InvalidOperationException("Windows could not size the package family name.");
        }

        StringBuilder value = new StringBuilder(checked((int)length));
        result = GetPackageFamilyName(handle, ref length, value);
        if (result != ErrorSuccess || value.Length == 0)
        {
            throw new InvalidOperationException("Windows could not query the package family name.");
        }

        return value.ToString();
    }

    private static string QueryPackageFullName(SafeProcessHandle handle)
    {
        uint length = 0;
        int result = GetPackageFullName(handle, ref length, null);
        if (result == AppModelErrorNoPackage)
        {
            return null;
        }

        if (result != ErrorInsufficientBuffer
            || length == 0
            || length > MaximumPackageIdentityCharacters)
        {
            throw new InvalidOperationException("Windows could not size the package full name.");
        }

        StringBuilder value = new StringBuilder(checked((int)length));
        result = GetPackageFullName(handle, ref length, value);
        if (result != ErrorSuccess || value.Length == 0)
        {
            throw new InvalidOperationException("Windows could not query the package full name.");
        }

        return value.ToString();
    }

    public static SafeFileHandle CreateConfiguredJob()
    {
        SafeFileHandle job = CreateJobObjectW(IntPtr.Zero, null);
        if (job == null || job.IsInvalid)
        {
            if (job != null)
            {
                job.Dispose();
            }

            throw new InvalidOperationException("Windows could not create the core Job Object.");
        }

        int size = Marshal.SizeOf(typeof(JobObjectExtendedLimitInformation));
        IntPtr informationPointer = Marshal.AllocHGlobal(size);
        try
        {
            JobObjectExtendedLimitInformation information =
                new JobObjectExtendedLimitInformation();
            information.BasicLimitInformation.LimitFlags = RequiredJobLimitFlags;
            Marshal.StructureToPtr(information, informationPointer, false);
            if (!SetInformationJobObject(
                job,
                ExtendedLimitInformation,
                informationPointer,
                checked((uint)size)))
            {
                throw new InvalidOperationException("Windows rejected the required Job Object limits.");
            }
        }
        catch
        {
            job.Dispose();
            throw;
        }
        finally
        {
            Marshal.FreeHGlobal(informationPointer);
        }

        if (QueryJobLimitFlags(job) != RequiredJobLimitFlags)
        {
            job.Dispose();
            throw new InvalidOperationException("Job Object limits do not exactly match the gate policy.");
        }

        return job;
    }

    public static uint QueryJobLimitFlags(SafeFileHandle job)
    {
        if (job == null || job.IsInvalid || job.IsClosed)
        {
            throw new InvalidOperationException("The Job Object handle is not usable.");
        }

        int size = Marshal.SizeOf(typeof(JobObjectExtendedLimitInformation));
        IntPtr informationPointer = Marshal.AllocHGlobal(size);
        try
        {
            for (int index = 0; index < size; index++)
            {
                Marshal.WriteByte(informationPointer, index, 0);
            }

            if (!QueryInformationJobObject(
                job,
                ExtendedLimitInformation,
                informationPointer,
                checked((uint)size),
                IntPtr.Zero))
            {
                throw new InvalidOperationException("Windows could not query the Job Object limits.");
            }

            JobObjectExtendedLimitInformation information =
                (JobObjectExtendedLimitInformation)Marshal.PtrToStructure(
                    informationPointer,
                    typeof(JobObjectExtendedLimitInformation));
            return information.BasicLimitInformation.LimitFlags;
        }
        finally
        {
            Marshal.FreeHGlobal(informationPointer);
        }
    }

    public static void AssignProcessToConfiguredJob(
        SafeFileHandle job,
        SafeProcessHandle process)
    {
        if (QueryJobLimitFlags(job) != RequiredJobLimitFlags)
        {
            throw new InvalidOperationException("Refusing assignment to a Job Object with unexpected limits.");
        }

        if (process == null || process.IsInvalid || process.IsClosed)
        {
            throw new InvalidOperationException("The core process handle is not usable for Job assignment.");
        }

        if (!AssignProcessToJobObject(job, process))
        {
            throw new InvalidOperationException("Windows could not assign the core to its Job Object.");
        }
    }

    public static bool IsProcessAssignedToJob(
        SafeFileHandle job,
        SafeProcessHandle process)
    {
        bool result;
        if (!IsProcessInJob(process, job, out result))
        {
            throw new InvalidOperationException("Windows could not corroborate core Job assignment.");
        }

        return result;
    }
}

public sealed class BaxyAppOpenGateLineReader
{
    private static readonly UTF8Encoding StrictUtf8 = new UTF8Encoding(false, true);
    private readonly Stream stream;
    private readonly int maximumBytes;

    public BaxyAppOpenGateLineReader(Stream stream, int maximumBytes)
    {
        if (stream == null)
        {
            throw new ArgumentNullException("stream");
        }

        if (maximumBytes <= 0)
        {
            throw new ArgumentOutOfRangeException("maximumBytes");
        }

        this.stream = stream;
        this.maximumBytes = maximumBytes;
    }

    public async Task<string> ReadLineAsync(TimeSpan timeout)
    {
        if (timeout <= TimeSpan.Zero)
        {
            throw new ArgumentOutOfRangeException("timeout");
        }

        using (CancellationTokenSource cancellation = new CancellationTokenSource(timeout))
        using (MemoryStream line = new MemoryStream())
        {
            byte[] oneByte = new byte[1];
            while (true)
            {
                int read;
                try
                {
                    read = await stream.ReadAsync(
                        oneByte,
                        0,
                        oneByte.Length,
                        cancellation.Token).ConfigureAwait(false);
                }
                catch (OperationCanceledException exception)
                {
                    throw new TimeoutException("Timed out while reading a bounded protocol line.", exception);
                }

                if (read == 0)
                {
                    if (line.Length == 0)
                    {
                        return null;
                    }

                    throw new EndOfStreamException("The protocol stream ended before a line terminator.");
                }

                if (oneByte[0] == (byte)'\n')
                {
                    byte[] complete = line.ToArray();
                    int length = complete.Length;
                    if (length > 0 && complete[length - 1] == (byte)'\r')
                    {
                        length--;
                    }

                    return StrictUtf8.GetString(complete, 0, length);
                }

                if (line.Length >= maximumBytes)
                {
                    throw new InvalidDataException("A protocol line exceeded the configured byte limit.");
                }

                line.WriteByte(oneByte[0]);
            }
        }
    }
}

public sealed class BaxyAppOpenGateCaptureResult
{
    public BaxyAppOpenGateCaptureResult(string text, long observedBytes, bool exceeded)
    {
        Text = text;
        ObservedBytes = observedBytes;
        Exceeded = exceeded;
    }

    public string Text { get; private set; }
    public long ObservedBytes { get; private set; }
    public bool Exceeded { get; private set; }
}

public static class BaxyAppOpenGateIO
{
    public static async Task<BaxyAppOpenGateCaptureResult> DrainBoundedAsync(
        Stream stream,
        int maximumCapturedBytes,
        CancellationToken cancellationToken)
    {
        if (stream == null)
        {
            throw new ArgumentNullException("stream");
        }

        if (maximumCapturedBytes <= 0)
        {
            throw new ArgumentOutOfRangeException("maximumCapturedBytes");
        }

        byte[] buffer = new byte[4096];
        using (MemoryStream captured = new MemoryStream(maximumCapturedBytes))
        {
            long observedBytes = 0;
            int read;
            while ((read = await stream.ReadAsync(
                buffer,
                0,
                buffer.Length,
                cancellationToken).ConfigureAwait(false)) != 0)
            {
                observedBytes = checked(observedBytes + read);
                int remaining = maximumCapturedBytes - checked((int)captured.Length);
                if (remaining > 0)
                {
                    captured.Write(buffer, 0, Math.Min(remaining, read));
                }
            }

            string text = new UTF8Encoding(false, false).GetString(captured.ToArray());
            return new BaxyAppOpenGateCaptureResult(
                text,
                observedBytes,
                observedBytes > maximumCapturedBytes);
        }
    }
}
'@
}

function Assert-GateCondition {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not $Condition) { throw $Message }
}

function Publish-GateEvidence {
    param([Parameter(Mandatory = $true)]$Value)

    $json = $Value | ConvertTo-Json -Depth 8 -Compress
    $nextPath = $script:EvidencePath + '.next'
    [IO.File]::WriteAllText($nextPath, $json + [Environment]::NewLine, $script:Utf8NoBom)
    Move-Item -LiteralPath $nextPath -Destination $script:EvidencePath -Force
    return $json
}

function Test-GatePathChainHasNoReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        return [bool](Assert-ExistingPathChainHasNoReparsePoint -Path $Path)
    } catch {
        # Protected package directories can deny enumeration while still exposing
        # non-traversing file attributes. Check every absolute component with the
        # native API instead of skipping the reparse-point verifier.
        return [BaxyAppOpenGateNative]::PathChainHasNoReparsePoint($Path)
    }
}

function Test-StableProcessIdentity {
    param(
        [Parameter(Mandatory = $true)][Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)][string]$ExpectedPath,
        [Parameter(Mandatory = $true)][long]$ExpectedStartTicks
    )

    try {
        if (-not [BaxyAppOpenGateNative]::IsProcessRunning($Process.SafeHandle)) {
            return $false
        }

        $observedPath = [IO.Path]::GetFullPath(
            [BaxyAppOpenGateNative]::QueryProcessPath($Process.SafeHandle))
        $observedStartTicks = $Process.StartTime.ToUniversalTime().Ticks
        return [string]::Equals(
            $observedPath,
            $ExpectedPath,
            [StringComparison]::OrdinalIgnoreCase) -and
            $observedStartTicks -eq $ExpectedStartTicks -and
            [BaxyAppOpenGateNative]::IsProcessRunning($Process.SafeHandle)
    } catch {
        return $false
    }
}

function New-VerifiedNotepadIdentity {
    param(
        [Parameter(Mandatory = $true)][Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)][string]$System32Path,
        [Parameter(Mandatory = $true)][string]$ProgramFilesPath
    )

    if (-not [BaxyAppOpenGateNative]::IsProcessRunning($Process.SafeHandle)) {
        throw 'Notepad exited before its identity could be established.'
    }

    $observedPath = [IO.Path]::GetFullPath(
        [BaxyAppOpenGateNative]::QueryProcessPath($Process.SafeHandle))
    $startTicks = $Process.StartTime.ToUniversalTime().Ticks
    if ([string]::Equals(
            $observedPath,
            $System32Path,
            [StringComparison]::OrdinalIgnoreCase)) {
        if (-not (Test-GatePathChainHasNoReparsePoint -Path $observedPath)) {
            throw 'Canonical System32 Notepad disappeared during identity validation.'
        }
        if (-not [BaxyAppOpenGateNative]::IsProcessRunning($Process.SafeHandle)) {
            throw 'Canonical System32 Notepad exited during identity validation.'
        }

        return [pscustomobject]@{
            Kind = 'system32'
            ExecutablePath = $observedPath
            StartTicks = $startTicks
            PackageFamilyName = $null
            PackageFullName = $null
        }
    }

    $packageIdentity = [BaxyAppOpenGateNative]::QueryPackageIdentity($Process.SafeHandle)
    if ($null -eq $packageIdentity -or
        $packageIdentity.FamilyName -cne 'Microsoft.WindowsNotepad_8wekyb3d8bbwe' -or
        $packageIdentity.FullName -cnotmatch `
            '^Microsoft[.]WindowsNotepad_[0-9]+(?:[.][0-9]+){3}_(?:x64|x86|arm64)__8wekyb3d8bbwe$') {
        throw 'The returned process is neither exact System32 nor exact packaged Notepad.'
    }

    $expectedPackagePath = [IO.Path]::GetFullPath((Join-Path $ProgramFilesPath (
        'WindowsApps\{0}\Notepad\Notepad.exe' -f $packageIdentity.FullName)))
    Assert-StrictDescendantPath -Parent $ProgramFilesPath -Child $expectedPackagePath
    if (-not [string]::Equals(
            $observedPath,
            $expectedPackagePath,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Packaged Notepad executable path does not exactly match its full package name.'
    }
    if (-not (Test-GatePathChainHasNoReparsePoint -Path $observedPath)) {
        throw 'Packaged Notepad disappeared during identity validation.'
    }
    if (-not [BaxyAppOpenGateNative]::IsProcessRunning($Process.SafeHandle)) {
        throw 'Packaged Notepad exited during identity validation.'
    }

    return [pscustomobject]@{
        Kind = 'package'
        ExecutablePath = $observedPath
        StartTicks = $startTicks
        PackageFamilyName = $packageIdentity.FamilyName
        PackageFullName = $packageIdentity.FullName
    }
}

function Test-StableNotepadIdentity {
    param(
        [Parameter(Mandatory = $true)][Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)]$ExpectedIdentity
    )

    try {
        if (-not [BaxyAppOpenGateNative]::IsProcessRunning($Process.SafeHandle)) {
            return $false
        }

        $observedPath = [IO.Path]::GetFullPath(
            [BaxyAppOpenGateNative]::QueryProcessPath($Process.SafeHandle))
        if ($Process.StartTime.ToUniversalTime().Ticks -ne [long]$ExpectedIdentity.StartTicks -or
            -not [string]::Equals(
                $observedPath,
                [string]$ExpectedIdentity.ExecutablePath,
                [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-GatePathChainHasNoReparsePoint -Path $observedPath)) {
            return $false
        }

        if ($ExpectedIdentity.Kind -ceq 'package') {
            $observedPackage = [BaxyAppOpenGateNative]::QueryPackageIdentity($Process.SafeHandle)
            if ($null -eq $observedPackage -or
                $observedPackage.FamilyName -cne $ExpectedIdentity.PackageFamilyName -or
                $observedPackage.FullName -cne $ExpectedIdentity.PackageFullName) {
                return $false
            }
        } elseif ($ExpectedIdentity.Kind -cne 'system32') {
            return $false
        }

        return [BaxyAppOpenGateNative]::IsProcessRunning($Process.SafeHandle)
    } catch {
        return $false
    }
}

function Test-StableNotepadWindowIdentity {
    param(
        [Parameter(Mandatory = $true)][Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)]$ExpectedIdentity,
        [Parameter(Mandatory = $true)][IntPtr]$ExpectedWindow
    )

    if (-not (Test-StableNotepadIdentity `
            -Process $Process `
            -ExpectedIdentity $ExpectedIdentity)) {
        return $false
    }

    try {
        $windowOwnerPid = [uint32]0
        $null = [BaxyAppOpenGateNative]::GetWindowThreadProcessId(
            $ExpectedWindow,
            [ref]$windowOwnerPid)
        $Process.Refresh()
        return [BaxyAppOpenGateNative]::IsWindow($ExpectedWindow) -and
            [BaxyAppOpenGateNative]::IsWindowVisible($ExpectedWindow) -and
            $windowOwnerPid -eq [uint32]$Process.Id -and
            $Process.MainWindowHandle -eq $ExpectedWindow -and
            (Test-StableNotepadIdentity `
                -Process $Process `
                -ExpectedIdentity $ExpectedIdentity)
    } catch {
        return $false
    }
}

function Get-NotepadIdentityKey {
    param(
        [Parameter(Mandatory = $true)][Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)]$Identity
    )

    return '{0}|{1}|{2}|{3}|{4}|{5}' -f @(
        $Identity.Kind,
        $Identity.ExecutablePath,
        $Identity.PackageFamilyName,
        $Identity.PackageFullName,
        $Process.Id,
        $Identity.StartTicks)
}

function Get-CurrentNotepadIdentityKeys {
    param(
        [Parameter(Mandatory = $true)][string]$System32Path,
        [Parameter(Mandatory = $true)][string]$ProgramFilesPath
    )

    $keys = New-Object 'System.Collections.Generic.List[string]'
    $processes = @(Get-Process -Name 'notepad' -ErrorAction SilentlyContinue)
    foreach ($candidate in $processes) {
        try {
            $null = $candidate.SafeHandle
            try {
                $identity = New-VerifiedNotepadIdentity `
                    -Process $candidate `
                    -System32Path $System32Path `
                    -ProgramFilesPath $ProgramFilesPath
                $keys.Add((Get-NotepadIdentityKey -Process $candidate -Identity $identity))
            } catch {
                if ([BaxyAppOpenGateNative]::IsProcessRunning($candidate.SafeHandle)) {
                    throw
                }
            }
        } finally {
            $candidate.Dispose()
        }
    }

    return $keys.ToArray()
}

function Stop-ExactGateCore {
    param(
        [Parameter(Mandatory = $true)][Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)][string]$ExpectedPath,
        [Parameter(Mandatory = $true)][long]$ExpectedStartTicks
    )

    if (-not [BaxyAppOpenGateNative]::IsProcessRunning($Process.SafeHandle)) {
        return $true
    }

    try { $Process.StandardInput.BaseStream.Close() } catch { }
    if (-not $Process.WaitForExit($processExitTimeoutMilliseconds)) {
        if (-not (Test-StableProcessIdentity `
                -Process $Process `
                -ExpectedPath $ExpectedPath `
                -ExpectedStartTicks $ExpectedStartTicks)) {
            throw 'Refusing fallback termination because core identity changed.'
        }

        $Process.Kill()
        if (-not $Process.WaitForExit($processExitTimeoutMilliseconds)) {
            throw 'The exact product core did not exit after fallback termination.'
        }
    }

    return -not [BaxyAppOpenGateNative]::IsProcessRunning($Process.SafeHandle)
}

function Read-CoreJsonMessage {
    param(
        [Parameter(Mandatory = $true)][BaxyAppOpenGateLineReader]$Reader,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $readTask = $Reader.ReadLineAsync($messageTimeout)
    $line = $readTask.GetAwaiter().GetResult()
    if ($null -eq $line) { throw "Core exited before emitting $Label." }

    try {
        return $line | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "Core emitted invalid JSON for $Label."
    }
}

function Write-CoreJsonMessage {
    param(
        [Parameter(Mandatory = $true)][IO.Stream]$Stream,
        [Parameter(Mandatory = $true)]$Message
    )

    $json = $Message | ConvertTo-Json -Depth 6 -Compress
    if ($json.IndexOfAny(@([char]0x0A, [char]0x0D)) -ge 0) {
        throw 'A generated protocol request contains a line break.'
    }

    $encoding = New-Object Text.UTF8Encoding($false, $true)
    $payload = $encoding.GetBytes($json)
    if ($payload.Length -gt $maximumJsonLineBytes) {
        throw 'A generated protocol request exceeds the byte limit.'
    }

    $Stream.Write($payload, 0, $payload.Length)
    $Stream.WriteByte(0x0A)
    $Stream.Flush()
}

function Assert-ResponseEnvelope {
    param(
        [Parameter(Mandatory = $true)]$Response,
        [Parameter(Mandatory = $true)]$Request,
        [Parameter(Mandatory = $true)][bool]$ExpectedReplayed
    )

    Assert-GateCondition ($Response.type -is [string] -and $Response.type -ceq 'operation.response') `
        'Core did not emit an operation.response.'
    Assert-GateCondition ($Response.requestId -is [string] -and $Response.requestId -ceq $Request.requestId) `
        'Response requestId does not match the request.'
    Assert-GateCondition ($Response.missionId -is [string] -and $Response.missionId -ceq $Request.missionId) `
        'Response missionId does not match the request.'
    Assert-GateCondition ($Response.invocationId -is [string] -and $Response.invocationId -ceq $Request.invocationId) `
        'Response invocationId does not match the request.'
    Assert-GateCondition ($Response.status -is [string] -and $Response.status -ceq 'completed') `
        'app.open did not complete.'
    Assert-GateCondition ($Response.verified -is [bool] -and $Response.verified) `
        'app.open was not independently verified by the core.'
    Assert-GateCondition ($Response.replayed -is [bool] -and $Response.replayed -eq $ExpectedReplayed) `
        'Response replay state is incorrect.'
    Assert-GateCondition ($null -eq $Response.errorCode) `
        'A completed response unexpectedly contains an errorCode.'
    Assert-GateCondition ($null -ne $Response.result) `
        'A completed app.open response has no result.'
}

function Get-ExactProductProcessKeys {
    param([Parameter(Mandatory = $true)][string[]]$ExpectedPaths)

    $keys = New-Object 'System.Collections.Generic.List[string]'
    $processes = @(Get-Process -Name 'Baxy', 'baxy-core' -ErrorAction SilentlyContinue)
    foreach ($candidate in $processes) {
        try {
            $null = $candidate.SafeHandle
            if (-not [BaxyAppOpenGateNative]::IsProcessRunning($candidate.SafeHandle)) { continue }
            $candidatePath = [IO.Path]::GetFullPath(
                [BaxyAppOpenGateNative]::QueryProcessPath($candidate.SafeHandle))
            $matchesProduct = @($ExpectedPaths | Where-Object {
                [string]::Equals($_, $candidatePath, [StringComparison]::OrdinalIgnoreCase)
            }).Count -gt 0
            if ($matchesProduct) {
                $keys.Add("$candidatePath|$($candidate.Id)|$($candidate.StartTime.ToUniversalTime().Ticks)")
            }
        } finally {
            $candidate.Dispose()
        }
    }

    return $keys.ToArray()
}

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$artifactRoot = [IO.Path]::GetFullPath((Join-Path $root 'artifacts\product'))
$allowedBuildRoot = [IO.Path]::GetFullPath((Join-Path $artifactRoot 'build'))
$Utf8NoBom = New-Object Text.UTF8Encoding($false)
if ([string]::IsNullOrWhiteSpace($EvidencePath)) {
    $EvidencePath = Join-Path $artifactRoot 'app_open_gate.json'
}
$EvidencePath = [IO.Path]::GetFullPath($EvidencePath)
Assert-StrictDescendantPath -Parent $artifactRoot -Child $EvidencePath
if ([IO.Path]::GetExtension($EvidencePath) -cne '.json') {
    throw 'The app.open evidence path must be a JSON file under artifacts\product.'
}
$evidenceParent = [IO.Path]::GetDirectoryName($EvidencePath)
if (-not (Test-Path -LiteralPath $evidenceParent -PathType Container) -or
    -not (Assert-ExistingPathChainHasNoReparsePoint -Path $evidenceParent)) {
    throw 'The app.open evidence parent must be an existing safe directory.'
}
$localApplicationData = [Environment]::GetFolderPath(
    [Environment+SpecialFolder]::LocalApplicationData,
    [Environment+SpecialFolderOption]::DoNotVerify)
if ([string]::IsNullOrWhiteSpace($localApplicationData)) {
    throw 'Windows did not expose the private local application-data directory.'
}
$localApplicationData = [IO.Path]::GetFullPath($localApplicationData)
$allowedRuntimeRoot = [IO.Path]::GetFullPath(
    (Join-Path $localApplicationData 'BAXY'))
Assert-StrictDescendantPath -Parent $localApplicationData -Child $allowedRuntimeRoot
if ([string]::IsNullOrWhiteSpace($BuildRoot)) {
    $buildLayout = Get-BaxyBuildLayout -RepositoryRoot $root
    $BuildRoot = Join-Path $allowedBuildRoot (
        "local-$($buildLayout.RuntimeIdentifier)")
}

$BuildRoot = [IO.Path]::GetFullPath($BuildRoot)
Assert-StrictDescendantPath -Parent $allowedBuildRoot -Child $BuildRoot
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $artifactRoot
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowedBuildRoot
if (-not (Assert-ExistingPathChainHasNoReparsePoint -Path $BuildRoot)) {
    throw 'Product build root does not exist.'
}
Assert-TreeHasNoReparsePoint -Root $BuildRoot

$corePath = [IO.Path]::GetFullPath((Join-Path $BuildRoot 'app\core\baxy-core.exe'))
$appPath = [IO.Path]::GetFullPath((Join-Path $BuildRoot 'app\Baxy.exe'))
Assert-StrictDescendantPath -Parent $BuildRoot -Child $corePath
if (-not (Test-Path -LiteralPath $corePath -PathType Leaf)) {
    throw "Missing product core: $corePath"
}

$windowsDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::Windows)
if ([string]::IsNullOrWhiteSpace($windowsDirectory)) {
    throw 'Windows did not expose its canonical directory.'
}
$canonicalNotepadPath = [IO.Path]::GetFullPath(
    (Join-Path ([IO.Path]::GetFullPath((Join-Path $windowsDirectory 'System32'))) 'notepad.exe'))
if (-not (Test-Path -LiteralPath $canonicalNotepadPath -PathType Leaf)) {
    throw "Canonical Notepad is missing: $canonicalNotepadPath"
}
if (-not (Assert-ExistingPathChainHasNoReparsePoint -Path $canonicalNotepadPath)) {
    throw 'Canonical System32 Notepad disappeared during path validation.'
}
$programFilesPath = [Environment]::GetEnvironmentVariable('ProgramFiles', 'Process')
if ([string]::IsNullOrWhiteSpace($programFilesPath)) {
    throw 'Windows did not expose %ProgramFiles%.'
}
$programFilesPath = [IO.Path]::GetFullPath($programFilesPath)
if (-not (Assert-ExistingPathChainHasNoReparsePoint -Path $programFilesPath)) {
    throw '%ProgramFiles% does not exist.'
}

# The gate must never claim ownership of, focus, or close a preexisting Notepad.
$preexistingNotepad = @(Get-Process -Name 'notepad' -ErrorAction SilentlyContinue)
if ($preexistingNotepad.Count -gt 0) {
    $preexistingIds = @($preexistingNotepad | ForEach-Object { $_.Id })
    foreach ($candidate in $preexistingNotepad) { $candidate.Dispose() }
    Publish-GateEvidence ([ordered]@{
        status = 'skipped'
        reason = 'preexisting_notepad'
        preexisting_count = $preexistingIds.Count
        preexisting_process_ids = $preexistingIds
    })
    exit 2
}

$preexistingProduct = @(Get-Process -Name 'Baxy', 'baxy-core', 'Baxy.Setup' -ErrorAction SilentlyContinue)
if ($preexistingProduct.Count -gt 0) {
    $preexistingProductIds = @($preexistingProduct | ForEach-Object { $_.Id })
    foreach ($candidate in $preexistingProduct) { $candidate.Dispose() }
    Publish-GateEvidence ([ordered]@{
        status = 'skipped'
        reason = 'preexisting_baxy_process'
        preexisting_count = $preexistingProductIds.Count
        preexisting_process_ids = $preexistingProductIds
    })
    exit 2
}

$expectedProductPaths = @($appPath, $corePath)
$baselineProductKeys = New-Object 'System.Collections.Generic.HashSet[string]' `
    ([StringComparer]::OrdinalIgnoreCase)
foreach ($key in @(Get-ExactProductProcessKeys -ExpectedPaths $expectedProductPaths)) {
    $null = $baselineProductKeys.Add($key)
}

if (-not (Assert-ExistingPathChainHasNoReparsePoint -Path $allowedRuntimeRoot)) {
    New-Item -ItemType Directory -Path $allowedRuntimeRoot -Force | Out-Null
}
if (-not (Assert-ExistingPathChainHasNoReparsePoint -Path $allowedRuntimeRoot)) {
    throw 'Could not create a safe product runtime root.'
}

$dataRoot = [IO.Path]::GetFullPath((Join-Path $allowedRuntimeRoot 'app-open-gate'))
Assert-StrictDescendantPath -Parent $allowedRuntimeRoot -Child $dataRoot
if (Test-Path -LiteralPath $dataRoot) {
    throw 'The app.open gate data leaf must be absent before the clean-environment run.'
}

$dataRootOwned = $false
$coreProcess = $null
$coreJob = $null
$coreStartTicks = 0L
$corePid = 0
$jobLimitFlags = 0L
$jobClosed = $false
$stderrCancellation = $null
$stderrTask = $null
$stderrCapture = $null
$ownedNotepad = $null
$ownedNotepadIdentity = $null
$ownedNotepadWindow = [IntPtr]::Zero
$notepadOwnershipEstablished = $false
$notepadSurvivedJobClose = $false
$operationProcessId = 0
$operationWindowHandle = 0L
$coreProtocol = $null
$summary = $null
$primaryFailure = $null
$cleanupFailures = New-Object 'System.Collections.Generic.List[string]'
$notepadExited = $false
$coreExited = $false
$ownedProductProcessesAfterCleanup = -1

try {
    $null = [IO.Directory]::CreateDirectory($dataRoot)
    $dataRootOwned = $true
    if (-not (Assert-ExistingPathChainHasNoReparsePoint -Path $dataRoot)) {
        throw 'Could not create a safe app.open data root.'
    }

    $coreJob = [BaxyAppOpenGateNative]::CreateConfiguredJob()
    $jobLimitFlags = [long][BaxyAppOpenGateNative]::QueryJobLimitFlags($coreJob)
    Assert-GateCondition (
        $jobLimitFlags -eq [long][BaxyAppOpenGateNative]::RequiredJobLimitFlags) `
        'Job Object flags do not exactly match KILL_ON_JOB_CLOSE | BREAKAWAY_OK.'

    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $corePath
    $startInfo.WorkingDirectory = [IO.Path]::GetDirectoryName($corePath)
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.EnvironmentVariables['BAXY_DATA_DIR'] = $dataRoot
    $startInfo.EnvironmentVariables['DOTNET_NOLOGO'] = '1'

    $coreProcess = New-Object Diagnostics.Process
    $coreProcess.StartInfo = $startInfo
    # Windows PowerShell 5.1 derives redirected stdin from Console.InputEncoding.
    # Its default UTF-8 encoder emits a BOM before our first raw BaseStream write,
    # which makes an otherwise valid JSONL request fail as malformed_json.
    $previousConsoleInputEncoding = [Console]::InputEncoding
    $coreStarted = $false
    try {
        [Console]::InputEncoding = $Utf8NoBom
        $coreStarted = $coreProcess.Start()
    } finally {
        [Console]::InputEncoding = $previousConsoleInputEncoding
    }
    Assert-GateCondition -Condition $coreStarted `
        -Message 'The exact product core did not start.'
    $null = $coreProcess.SafeHandle
    $corePid = $coreProcess.Id
    $coreStartTicks = $coreProcess.StartTime.ToUniversalTime().Ticks
    $observedCorePath = [IO.Path]::GetFullPath(
        [BaxyAppOpenGateNative]::QueryProcessPath($coreProcess.SafeHandle))
    Assert-GateCondition ([string]::Equals(
            $observedCorePath,
            $corePath,
            [StringComparison]::OrdinalIgnoreCase)) `
        'The started core executable does not match the requested build.'
    Assert-GateCondition ([BaxyAppOpenGateNative]::IsProcessRunning($coreProcess.SafeHandle)) `
        'The product core exited during startup identity verification.'
    [BaxyAppOpenGateNative]::AssignProcessToConfiguredJob(
        $coreJob,
        $coreProcess.SafeHandle)
    Assert-GateCondition ([BaxyAppOpenGateNative]::IsProcessAssignedToJob(
            $coreJob,
            $coreProcess.SafeHandle)) `
        'Core is not assigned to the configured Job Object.'
    $jobLimitFlags = [long][BaxyAppOpenGateNative]::QueryJobLimitFlags($coreJob)
    Assert-GateCondition (
        $jobLimitFlags -eq [long][BaxyAppOpenGateNative]::RequiredJobLimitFlags) `
        'Assigned Job Object flags changed from the exact required policy.'

    $stderrCancellation = New-Object Threading.CancellationTokenSource
    $stderrTask = [BaxyAppOpenGateIO]::DrainBoundedAsync(
        $coreProcess.StandardError.BaseStream,
        $maximumStderrBytes,
        $stderrCancellation.Token)
    $reader = New-Object BaxyAppOpenGateLineReader(
        $coreProcess.StandardOutput.BaseStream,
        $maximumJsonLineBytes)

    $hello = Read-CoreJsonMessage -Reader $reader -Label 'hello'
    Assert-GateCondition ($hello.type -is [string] -and $hello.type -ceq 'hello') `
        'Core hello has an invalid type.'
    Assert-GateCondition ($hello.protocol -is [string] -and $hello.protocol -ceq 'baxy.local.v1') `
        'Core hello advertises an unexpected protocol.'
    Assert-GateCondition ($hello.pid -is [ValueType] -and [long]$hello.pid -eq $corePid) `
        'Core hello PID does not match the stable process.'
    $appOpenCapabilities = @($hello.capabilities | Where-Object {
        $_.name -is [string] -and $_.name -ceq 'app.open'
    })
    Assert-GateCondition ($appOpenCapabilities.Count -eq 1) `
        'Core does not advertise exactly one app.open capability.'
    Assert-GateCondition (
        $appOpenCapabilities[0].risk -is [string] -and
        $appOpenCapabilities[0].risk -ceq 'low_reversible') `
        'Core app.open capability has an unexpected risk classification.'
    Assert-GateCondition (Test-StableProcessIdentity `
            -Process $coreProcess `
            -ExpectedPath $corePath `
            -ExpectedStartTicks $coreStartTicks) `
        'Core identity changed after hello.'
    $coreProtocol = $hello.protocol

    $missionId = [Guid]::NewGuid().ToString('D')
    $invocationId = [Guid]::NewGuid().ToString('D')
    $firstRequest = [ordered]@{
        type = 'operation.request'
        requestId = [Guid]::NewGuid().ToString('D')
        missionId = $missionId
        invocationId = $invocationId
        operation = 'app.open'
        arguments = [ordered]@{ appId = 'windows.notepad' }
    }

    $launchNotBeforeUtc = [DateTime]::UtcNow
    Write-CoreJsonMessage -Stream $coreProcess.StandardInput.BaseStream -Message $firstRequest
    $firstResponse = Read-CoreJsonMessage -Reader $reader -Label 'first app.open response'
    Assert-ResponseEnvelope -Response $firstResponse -Request $firstRequest -ExpectedReplayed $false
    Assert-GateCondition (
        $firstResponse.result.appId -is [string] -and
        $firstResponse.result.appId -ceq 'windows.notepad') `
        'app.open returned an unexpected appId.'
    Assert-GateCondition (
        $firstResponse.result.alreadyRunning -is [bool] -and
        -not $firstResponse.result.alreadyRunning) `
        'The gate did not create a fresh Notepad instance.'
    Assert-GateCondition ($firstResponse.result.processId -is [ValueType]) `
        'app.open result has no numeric processId.'
    Assert-GateCondition ($firstResponse.result.windowHandle -is [ValueType]) `
        'app.open result has no numeric windowHandle.'
    $operationProcessId = [int]$firstResponse.result.processId
    $operationWindowHandle = [long]$firstResponse.result.windowHandle
    Assert-GateCondition ($operationProcessId -gt 0) `
        'app.open returned a non-positive processId.'
    Assert-GateCondition ($operationWindowHandle -gt 0) `
        'app.open returned a non-positive windowHandle.'

    $ownedNotepad = Get-Process -Id $operationProcessId -ErrorAction Stop
    $null = $ownedNotepad.SafeHandle
    Assert-GateCondition ([BaxyAppOpenGateNative]::IsProcessRunning($ownedNotepad.SafeHandle)) `
        'The returned Notepad process is not alive.'
    $ownedNotepadIdentity = New-VerifiedNotepadIdentity `
        -Process $ownedNotepad `
        -System32Path $canonicalNotepadPath `
        -ProgramFilesPath $programFilesPath
    $observedNotepadStartUtc = $ownedNotepad.StartTime.ToUniversalTime()
    Assert-GateCondition (
        $observedNotepadStartUtc -ge $launchNotBeforeUtc.AddSeconds(-2) -and
        $observedNotepadStartUtc -le [DateTime]::UtcNow.AddSeconds(1)) `
        'The returned Notepad process predates this gate invocation.'
    $notepadOwnershipEstablished = $true

    $ownedNotepadWindow = [IntPtr]$operationWindowHandle
    $windowVerified = $false
    $windowDeadline = [DateTime]::UtcNow.AddSeconds(5)
    do {
        if (-not (Test-StableNotepadIdentity `
                -Process $ownedNotepad `
                -ExpectedIdentity $ownedNotepadIdentity)) {
            break
        }

        $windowOwnerPid = [uint32]0
        $null = [BaxyAppOpenGateNative]::GetWindowThreadProcessId(
            $ownedNotepadWindow,
            [ref]$windowOwnerPid)
        $ownedNotepad.Refresh()
        $windowVerified = [BaxyAppOpenGateNative]::IsWindow($ownedNotepadWindow) -and
            [BaxyAppOpenGateNative]::IsWindowVisible($ownedNotepadWindow) -and
            $windowOwnerPid -eq [uint32]$operationProcessId -and
            $ownedNotepad.MainWindowHandle -eq $ownedNotepadWindow -and
            [BaxyAppOpenGateNative]::GetForegroundWindow() -eq $ownedNotepadWindow
        if (-not $windowVerified) { Start-Sleep -Milliseconds 50 }
    } until ($windowVerified -or [DateTime]::UtcNow -ge $windowDeadline)
    Assert-GateCondition $windowVerified `
        'The returned Notepad HWND is not visible, owned by the process, and foreground.'

    $ownedNotepadIdentityKey = Get-NotepadIdentityKey `
        -Process $ownedNotepad `
        -Identity $ownedNotepadIdentity
    $notepadKeysBeforeReplay = @(Get-CurrentNotepadIdentityKeys `
        -System32Path $canonicalNotepadPath `
        -ProgramFilesPath $programFilesPath)
    $notepadKeySetBeforeReplay = New-Object 'System.Collections.Generic.HashSet[string]' `
        ([StringComparer]::Ordinal)
    foreach ($key in $notepadKeysBeforeReplay) {
        $null = $notepadKeySetBeforeReplay.Add($key)
    }
    Assert-GateCondition ($notepadKeySetBeforeReplay.Contains($ownedNotepadIdentityKey)) `
        'The final Notepad identity is absent immediately before replay.'

    $replayRequest = [ordered]@{
        type = 'operation.request'
        requestId = [Guid]::NewGuid().ToString('D')
        missionId = $missionId
        invocationId = $invocationId
        operation = 'app.open'
        arguments = [ordered]@{ appId = 'windows.notepad' }
    }
    Assert-GateCondition ($replayRequest.requestId -cne $firstRequest.requestId) `
        'Replay requestId was not renewed.'
    Write-CoreJsonMessage -Stream $coreProcess.StandardInput.BaseStream -Message $replayRequest
    $replayResponse = Read-CoreJsonMessage -Reader $reader -Label 'replayed app.open response'
    Assert-ResponseEnvelope -Response $replayResponse -Request $replayRequest -ExpectedReplayed $true
    Assert-GateCondition ([int]$replayResponse.result.processId -eq $operationProcessId) `
        'Replay returned a different processId.'
    Assert-GateCondition ([long]$replayResponse.result.windowHandle -eq $operationWindowHandle) `
        'Replay returned a different windowHandle.'
    Assert-GateCondition (
        $replayResponse.result.alreadyRunning -is [bool] -and
        -not $replayResponse.result.alreadyRunning) `
        'Replay changed the stored alreadyRunning result.'
    Assert-GateCondition (
        $replayResponse.result.appId -is [string] -and
        $replayResponse.result.appId -ceq 'windows.notepad') `
        'Replay returned a different appId.'

    $notepadKeysAfterReplay = @(Get-CurrentNotepadIdentityKeys `
        -System32Path $canonicalNotepadPath `
        -ProgramFilesPath $programFilesPath)
    $newNotepadKeys = @($notepadKeysAfterReplay | Where-Object {
        -not $notepadKeySetBeforeReplay.Contains($_)
    })
    Assert-GateCondition ($newNotepadKeys.Count -eq 0) `
        'Replay created a new allowed Notepad process identity.'
    Assert-GateCondition ($notepadKeysAfterReplay -ccontains $ownedNotepadIdentityKey) `
        'Replay did not preserve the exact final Notepad identity.'
    Assert-GateCondition (Test-StableNotepadIdentity `
            -Process $ownedNotepad `
            -ExpectedIdentity $ownedNotepadIdentity) `
        'Replay did not preserve the stable final Notepad process handle.'

    Assert-GateCondition (Test-StableProcessIdentity `
            -Process $coreProcess `
            -ExpectedPath $corePath `
            -ExpectedStartTicks $coreStartTicks) `
        'Core identity changed during the gate.'
    Assert-GateCondition (Assert-ExistingPathChainHasNoReparsePoint -Path $dataRoot) `
        'The gate data root became unsafe during execution.'
    $jobLimitFlags = [long][BaxyAppOpenGateNative]::QueryJobLimitFlags($coreJob)
    Assert-GateCondition (
        $jobLimitFlags -eq [long][BaxyAppOpenGateNative]::RequiredJobLimitFlags) `
        'Job Object flags changed during app.open execution.'
    Assert-GateCondition ([BaxyAppOpenGateNative]::IsProcessAssignedToJob(
            $coreJob,
            $coreProcess.SafeHandle)) `
        'Core left the configured Job Object before shutdown.'

    $coreExited = Stop-ExactGateCore `
        -Process $coreProcess `
        -ExpectedPath $corePath `
        -ExpectedStartTicks $coreStartTicks
    Assert-GateCondition $coreExited 'The exact core did not stop before Job close.'
    $coreJob.Dispose()
    $jobClosed = $coreJob.IsClosed
    Assert-GateCondition $jobClosed 'The core Job Object handle did not close.'

    $survivalDeadline = [DateTime]::UtcNow.AddSeconds(3)
    do {
        $notepadSurvivedJobClose = Test-StableNotepadWindowIdentity `
            -Process $ownedNotepad `
            -ExpectedIdentity $ownedNotepadIdentity `
            -ExpectedWindow $ownedNotepadWindow
        if (-not $notepadSurvivedJobClose) { Start-Sleep -Milliseconds 50 }
    } until ($notepadSurvivedJobClose -or [DateTime]::UtcNow -ge $survivalDeadline)
    Assert-GateCondition $notepadSurvivedJobClose `
        'Notepad did not survive core shutdown and Job Object close with the same identity and HWND.'

    $summary = [ordered]@{
        status = 'passed'
        data_root = $dataRoot
        core = [ordered]@{
            pid = $corePid
            protocol = $coreProtocol
            app_open_capability = $true
            job_limit_flags = ('0x{0:X8}' -f $jobLimitFlags)
            job_closed = $jobClosed
        }
        operation = [ordered]@{
            verified = $true
            process_id = $operationProcessId
            window_handle = $operationWindowHandle
            identity_kind = $ownedNotepadIdentity.Kind
            canonical_path = $ownedNotepadIdentity.ExecutablePath
            package_family_name = $ownedNotepadIdentity.PackageFamilyName
            package_full_name = $ownedNotepadIdentity.PackageFullName
            visible_foreground_window = $true
            survived_core_job_close = $notepadSurvivedJobClose
        }
        replay = [ordered]@{
            replayed = $true
            request_id_changed = $true
            same_process = $true
            new_process_identities = 0
            observed_process_identities = $notepadKeysAfterReplay.Count
        }
    }
} catch {
    $primaryFailure = $_
} finally {
    if ($null -ne $coreProcess) {
        try {
            $coreExited = Stop-ExactGateCore `
                -Process $coreProcess `
                -ExpectedPath $corePath `
                -ExpectedStartTicks $coreStartTicks
            if (-not $coreExited) { throw 'The gate-owned core remains alive.' }
        } catch {
            $cleanupFailures.Add("core: $($_.Exception.Message)")
        }
    }

    if ($null -ne $coreJob) {
        try {
            if (-not $coreJob.IsClosed) { $coreJob.Dispose() }
            $jobClosed = $coreJob.IsClosed
            if (-not $jobClosed) { throw 'The core Job Object handle remains open.' }
        } catch {
            $cleanupFailures.Add("job: $($_.Exception.Message)")
        }
    }

    if ($null -ne $coreProcess -and -not $coreExited) {
        try {
            if ($coreProcess.WaitForExit($processExitTimeoutMilliseconds)) {
                $coreExited = -not [BaxyAppOpenGateNative]::IsProcessRunning(
                    $coreProcess.SafeHandle)
            }
            if (-not $coreExited) {
                throw 'Core remained alive after its KILL_ON_JOB_CLOSE owner closed.'
            }
        } catch {
            $cleanupFailures.Add("core_after_job: $($_.Exception.Message)")
        }
    }

    if ($null -ne $ownedNotepad) {
        try {
            if ($notepadOwnershipEstablished) {
                if (-not $jobClosed) {
                    throw 'Refusing to clean Notepad before the core Job Object is closed.'
                }

                $notepadIsRunning = [BaxyAppOpenGateNative]::IsProcessRunning(
                    $ownedNotepad.SafeHandle)
                if ($notepadIsRunning -and -not $notepadSurvivedJobClose) {
                    $notepadSurvivedJobClose = Test-StableNotepadWindowIdentity `
                        -Process $ownedNotepad `
                        -ExpectedIdentity $ownedNotepadIdentity `
                        -ExpectedWindow $ownedNotepadWindow
                }
                if (-not $notepadSurvivedJobClose) {
                    throw 'Notepad did not survive Job close with its original process and HWND.'
                }

                if ($AllowCloseVerifiedNotepadInQuiescentSession -and $notepadIsRunning) {
                    if (-not (Test-StableNotepadWindowIdentity `
                            -Process $ownedNotepad `
                            -ExpectedIdentity $ownedNotepadIdentity `
                            -ExpectedWindow $ownedNotepadWindow)) {
                        throw 'Refusing to close Notepad because its stable identity or HWND changed.'
                    }

                    $null = $ownedNotepad.CloseMainWindow()
                    if (-not $ownedNotepad.WaitForExit($processExitTimeoutMilliseconds)) {
                        throw 'Notepad did not accept a normal close; refusing forced termination.'
                    }
                }

                $notepadExited = -not [BaxyAppOpenGateNative]::IsProcessRunning(
                    $ownedNotepad.SafeHandle)
                if ($AllowCloseVerifiedNotepadInQuiescentSession -and -not $notepadExited) {
                    throw 'The verified Notepad remains alive after an explicitly requested close.'
                }
            }
        } catch {
            $cleanupFailures.Add("notepad: $($_.Exception.Message)")
        } finally {
            $ownedNotepad.Dispose()
        }
    }

    if ($null -ne $stderrTask) {
        $stderrDeadline = [DateTime]::UtcNow.AddSeconds(2)
        while (-not $stderrTask.IsCompleted -and [DateTime]::UtcNow -lt $stderrDeadline) {
            Start-Sleep -Milliseconds 25
        }
        if (-not $stderrTask.IsCompleted) {
            if ($null -ne $stderrCancellation) { $stderrCancellation.Cancel() }
            $cleanupFailures.Add('stderr: bounded drain did not finish after core exit.')
        } elseif ($stderrTask.IsFaulted) {
            $cleanupFailures.Add("stderr: $($stderrTask.Exception.GetBaseException().Message)")
        } elseif ($stderrTask.IsCanceled) {
            $cleanupFailures.Add('stderr: bounded drain was canceled.')
        } else {
            $stderrCapture = $stderrTask.GetAwaiter().GetResult()
            if ($stderrCapture.Exceeded) {
                $cleanupFailures.Add(
                    "stderr: core exceeded $maximumStderrBytes captured bytes.")
            }
        }
    }

    if ($null -ne $stderrCancellation) { $stderrCancellation.Dispose() }
    if ($null -ne $coreProcess) { $coreProcess.Dispose() }

    try {
        $postProductKeys = @(Get-ExactProductProcessKeys -ExpectedPaths $expectedProductPaths)
        $newProductKeys = @($postProductKeys | Where-Object {
            -not $baselineProductKeys.Contains($_)
        })
        $ownedProductProcessesAfterCleanup = $newProductKeys.Count
        if ($ownedProductProcessesAfterCleanup -ne 0) {
            throw 'A Baxy or baxy-core process created during the gate remains alive.'
        }
    } catch {
        $cleanupFailures.Add("product_processes: $($_.Exception.Message)")
    }

    if ($dataRootOwned) {
        try {
            Remove-TreeFailClosed -AllowedRoot $allowedRuntimeRoot -Target $dataRoot
            if (Test-Path -LiteralPath $dataRoot) {
                throw 'The gate-owned data leaf remains after cleanup.'
            }
        } catch {
            $cleanupFailures.Add("data_root: $($_.Exception.Message)")
        }
    }
}

if ($null -ne $primaryFailure -or $cleanupFailures.Count -gt 0) {
    $primaryMessage = if ($null -eq $primaryFailure) {
        $null
    } else {
        $primaryFailure.Exception.Message
    }
    Publish-GateEvidence ([ordered]@{
        status = 'failed'
        error = $primaryMessage
        cleanup_errors = $cleanupFailures.ToArray()
        core_exited = $coreExited
        job_closed = $jobClosed
        notepad_survived_job_close = $notepadSurvivedJobClose
        gate_notepad_exited = $notepadExited
        close_notepad_requested = [bool]$AllowCloseVerifiedNotepadInQuiescentSession
        owned_product_processes = $ownedProductProcessesAfterCleanup
        data_root_removed = $dataRootOwned -and -not (Test-Path -LiteralPath $dataRoot)
        stderr_bytes = if ($null -eq $stderrCapture) { $null } else { $stderrCapture.ObservedBytes }
    })
    throw 'The physical app.open gate failed; see its JSON result.'
}

$summary['cleanup'] = [ordered]@{
    gate_notepad_exited = $notepadExited
    close_notepad_requested = [bool]$AllowCloseVerifiedNotepadInQuiescentSession
    notepad_left_open_intentionally = `
        -not $AllowCloseVerifiedNotepadInQuiescentSession -and -not $notepadExited
    notepad_survived_job_close = $notepadSurvivedJobClose
    core_exited = $coreExited
    job_closed = $jobClosed
    owned_product_processes = $ownedProductProcessesAfterCleanup
    data_root_removed = $dataRootOwned -and -not (Test-Path -LiteralPath $dataRoot)
    stderr_bytes = if ($null -eq $stderrCapture) { 0 } else { $stderrCapture.ObservedBytes }
}
Publish-GateEvidence $summary
