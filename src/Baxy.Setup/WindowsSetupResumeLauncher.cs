using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Setup;

internal sealed record WindowsSetupResumeStartRequest(
    string ApplicationName,
    string WorkingDirectory,
    string CommandLine,
    char[] EnvironmentBlock,
    uint CreationFlags,
    bool InheritHandles);

internal interface IWindowsSetupResumeProcessPlatform
{
    uint CreateProcess(WindowsSetupResumeStartRequest request);
}

internal sealed class WindowsSetupResumeLauncher
{
    internal const uint CreateUnicodeEnvironment = 0x00000400;
    private const int MaximumCommandLineCharacters = 32_767;

    private readonly CanonicalWindowsPaths _paths;
    private readonly IWindowsSetupResumeProcessPlatform _platform;
    private readonly IInstalledApplicationEnvironment _environment;

    internal WindowsSetupResumeLauncher(CanonicalWindowsPaths paths)
        : this(
            paths,
            new WindowsSetupResumeProcessPlatform(),
            new ProcessEnvironmentSnapshot())
    {
    }

    internal WindowsSetupResumeLauncher(
        CanonicalWindowsPaths paths,
        IWindowsSetupResumeProcessPlatform platform,
        IInstalledApplicationEnvironment environment)
    {
        _paths = paths ?? throw new ArgumentNullException(nameof(paths));
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _environment = environment ?? throw new ArgumentNullException(nameof(environment));
    }

    internal uint Launch(
        WindowsProductLifecycleResumeRequirement requirement,
        WindowsProductLifecycleOperation operation)
    {
        ArgumentNullException.ThrowIfNull(requirement);
        string application = ValidateRequirement(requirement, operation);
        string commandLine = BuildCanonicalCommandLine(application, operation);
        char[] environmentBlock;
        try
        {
            environmentBlock = InstalledApplicationLauncher.BuildEnvironmentBlock(
                _environment.Capture());
        }
        catch (Exception exception) when (
            exception is InstalledApplicationLaunchException or ArgumentException or
                InvalidOperationException)
        {
            throw new InstallationSafetyException(
                "Windows returned an invalid Setup-resume environment.",
                exception);
        }

        StableSetupHostManager.VerifyExact(application, requirement.TargetSetupIdentity);
        using FileStream lockStream = OpenLockedRead(application);
        StableSetupHostManager.VerifyExact(application, requirement.TargetSetupIdentity);
        WindowsSetupResumeStartRequest request = new(
            application,
            _paths.InstallationRoot,
            commandLine,
            environmentBlock,
            CreateUnicodeEnvironment,
            InheritHandles: false);
        uint processId = _platform.CreateProcess(request);
        if (processId == 0)
        {
            throw new InstallationSafetyException(
                "CreateProcessW returned no Setup-resume process identity.");
        }

        StableSetupHostManager.VerifyExact(application, requirement.TargetSetupIdentity);
        return processId;
    }

    internal static string BuildCanonicalCommandLine(
        string applicationPath,
        WindowsProductLifecycleOperation operation)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(applicationPath);
        if (!Path.IsPathFullyQualified(applicationPath) ||
            applicationPath.Contains('"') || applicationPath.Contains('\0'))
        {
            throw new InstallationSafetyException(
                "The Setup-resume application path is not canonical command-line text.");
        }

        string suffix = operation switch
        {
            WindowsProductLifecycleOperation.InstallOrUpdate => string.Empty,
            WindowsProductLifecycleOperation.Rollback => " --rollback",
            _ => throw new InstallationSafetyException(
                "Only install/update or rollback may relaunch a target Setup host."),
        };
        string commandLine = $"\"{applicationPath}\"{suffix}";
        if (commandLine.Length >= MaximumCommandLineCharacters)
        {
            throw new InstallationSafetyException(
                "The Setup-resume command line exceeds the reviewed Windows limit.");
        }

        return commandLine;
    }

    private string ValidateRequirement(
        WindowsProductLifecycleResumeRequirement requirement,
        WindowsProductLifecycleOperation operation)
    {
        if (!Guid.TryParseExact(requirement.TransactionId, "N", out Guid transactionId) ||
            transactionId == Guid.Empty ||
            !string.Equals(
                requirement.TransactionId,
                transactionId.ToString("N"),
                StringComparison.Ordinal) ||
            requirement.VerifiedTargetSetupPath is not string candidate ||
            requirement.TargetSetupIdentity is null)
        {
            throw new InstallationSafetyException(
                "The lifecycle did not provide an exact resumable Setup target.");
        }

        string application = Path.GetFullPath(candidate);
        string next = Path.Combine(_paths.InstallationRoot, "Baxy.Setup.next.exe");
        bool allowed = string.Equals(
                application,
                _paths.StableSetupHost,
                StringComparison.Ordinal) ||
            string.Equals(application, next, StringComparison.Ordinal);
        if (!allowed || !string.Equals(candidate, application, StringComparison.Ordinal) ||
            !string.Equals(
                Path.GetDirectoryName(application),
                _paths.InstallationRoot,
                StringComparison.Ordinal) ||
            operation == WindowsProductLifecycleOperation.Reconcile)
        {
            throw new InstallationSafetyException(
                "The lifecycle resume target escaped the exact stable/next Setup paths.");
        }

        return application;
    }

    private static FileStream OpenLockedRead(string path)
    {
        try
        {
            return new FileStream(
                path,
                FileMode.Open,
                FileAccess.Read,
                FileShare.Read,
                bufferSize: 1,
                FileOptions.SequentialScan);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            throw new InstallationSafetyException(
                "The verified target Setup host could not be locked for relaunch.",
                exception);
        }
    }
}

internal sealed partial class WindowsSetupResumeProcessPlatform
    : IWindowsSetupResumeProcessPlatform
{
    public uint CreateProcess(WindowsSetupResumeStartRequest request)
    {
        ValidateRequest(request);
        char[] commandLine = [.. request.CommandLine, '\0'];
        GCHandle commandPin = GCHandle.Alloc(commandLine, GCHandleType.Pinned);
        GCHandle environmentPin = GCHandle.Alloc(request.EnvironmentBlock, GCHandleType.Pinned);
        try
        {
            StartupInfo startup = new()
            {
                Size = checked((uint)Marshal.SizeOf<StartupInfo>()),
            };
            bool created = CreateProcessW(
                request.ApplicationName,
                commandPin.AddrOfPinnedObject(),
                processAttributes: 0,
                threadAttributes: 0,
                request.InheritHandles,
                request.CreationFlags,
                environmentPin.AddrOfPinnedObject(),
                request.WorkingDirectory,
                ref startup,
                out ProcessInformation processInformation);
            int error = Marshal.GetLastPInvokeError();
            if (!created)
            {
                throw new InstallationSafetyException(
                    "CreateProcessW rejected the verified target Setup host.",
                    new Win32Exception(error));
            }

            using SafeWaitHandle process = new(
                processInformation.ProcessHandle,
                ownsHandle: true);
            using SafeWaitHandle thread = new(
                processInformation.ThreadHandle,
                ownsHandle: true);
            if (process.IsInvalid || thread.IsInvalid || processInformation.ProcessId == 0)
            {
                throw new InstallationSafetyException(
                    "CreateProcessW returned an invalid Setup-resume process result.");
            }

            return processInformation.ProcessId;
        }
        finally
        {
            environmentPin.Free();
            commandPin.Free();
        }
    }

    private static void ValidateRequest(WindowsSetupResumeStartRequest? request)
    {
        if (request is null ||
            !Path.IsPathFullyQualified(request.ApplicationName) ||
            !Path.IsPathFullyQualified(request.WorkingDirectory) ||
            !string.Equals(
                Path.GetDirectoryName(request.ApplicationName),
                request.WorkingDirectory,
                StringComparison.Ordinal) ||
            (request.CommandLine != $"\"{request.ApplicationName}\"" &&
             request.CommandLine != $"\"{request.ApplicationName}\" --rollback") ||
            request.EnvironmentBlock is not { Length: >= 2 } ||
            request.EnvironmentBlock[^1] != '\0' ||
            request.EnvironmentBlock[^2] != '\0' ||
            request.CreationFlags != WindowsSetupResumeLauncher.CreateUnicodeEnvironment ||
            request.InheritHandles)
        {
            throw new InstallationSafetyException(
                "The Setup-resume CreateProcessW request is not canonical.");
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct StartupInfo
    {
        internal uint Size;
        internal nint Reserved;
        internal nint Desktop;
        internal nint Title;
        internal uint X;
        internal uint Y;
        internal uint XSize;
        internal uint YSize;
        internal uint XCountChars;
        internal uint YCountChars;
        internal uint FillAttribute;
        internal uint Flags;
        internal ushort ShowWindow;
        internal ushort Reserved2Size;
        internal nint Reserved2;
        internal nint StandardInput;
        internal nint StandardOutput;
        internal nint StandardError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ProcessInformation
    {
        internal nint ProcessHandle;
        internal nint ThreadHandle;
        internal uint ProcessId;
        internal uint ThreadId;
    }

    [LibraryImport(
        "kernel32.dll",
        EntryPoint = "CreateProcessW",
        SetLastError = true,
        StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool CreateProcessW(
        string applicationName,
        nint commandLine,
        nint processAttributes,
        nint threadAttributes,
        [MarshalAs(UnmanagedType.Bool)] bool inheritHandles,
        uint creationFlags,
        nint environment,
        string currentDirectory,
        ref StartupInfo startupInfo,
        out ProcessInformation processInformation);
}
