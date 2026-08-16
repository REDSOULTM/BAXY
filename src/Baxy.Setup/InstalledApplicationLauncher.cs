using System.Collections;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Setup;

internal sealed record VerifiedInstalledApplication(
    string Version,
    string ApplicationName,
    string WorkingDirectory);

internal sealed record InstalledApplicationStartRequest(
    string ApplicationName,
    string WorkingDirectory,
    string? CommandLine,
    bool InheritHandles,
    uint CreationFlags,
    char[] EnvironmentBlock);

internal interface IInstalledApplicationPlatform
{
    uint CreateProcess(InstalledApplicationStartRequest request);
}

internal interface IInstalledApplicationEnvironment
{
    IReadOnlyList<KeyValuePair<string, string>> Capture();
}

internal sealed class InstalledApplicationLaunchException : Exception
{
    internal InstalledApplicationLaunchException(string message)
        : base(message)
    {
    }

    internal InstalledApplicationLaunchException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

internal sealed class InstalledApplicationLauncher
{
    internal const uint CreateUnicodeEnvironment = 0x00000400;
    internal const uint CreateBreakawayFromJob = 0x01000000;
    internal const uint RequiredCreationFlags = CreateBreakawayFromJob | CreateUnicodeEnvironment;

    private const string DataRootOverride = "BAXY_DATA_DIR";
    private const int MaximumEnvironmentBlockCharacters = 32_767;

    private readonly InstallationEngine _engine;
    private readonly IInstalledApplicationPlatform _platform;
    private readonly IInstalledApplicationEnvironment _environment;

    internal InstalledApplicationLauncher(InstallationEngine engine)
        : this(engine, new WindowsInstalledApplicationPlatform(), new ProcessEnvironmentSnapshot())
    {
    }

    internal InstalledApplicationLauncher(
        InstallationEngine engine,
        IInstalledApplicationPlatform platform,
        IInstalledApplicationEnvironment environment)
    {
        _engine = engine ?? throw new ArgumentNullException(nameof(engine));
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _environment = environment ?? throw new ArgumentNullException(nameof(environment));
    }

    internal uint Launch()
    {
        return _engine.UseVerifiedCurrentApplication(application =>
        {
            try
            {
                char[] environmentBlock = BuildEnvironmentBlock(_environment.Capture());
                InstalledApplicationStartRequest request = new(
                    application.ApplicationName,
                    application.WorkingDirectory,
                    CommandLine: null,
                    InheritHandles: false,
                    RequiredCreationFlags,
                    environmentBlock);

                uint processId = _platform.CreateProcess(request);
                if (processId == 0)
                {
                    throw new InstalledApplicationLaunchException(
                        "Windows returned an invalid BAXY process identity.");
                }

                return processId;
            }
            catch (InstalledApplicationLaunchException)
            {
                throw;
            }
            catch (Exception exception) when (
                exception is ArgumentException or IOException or InvalidOperationException or
                UnauthorizedAccessException or Win32Exception)
            {
                throw new InstalledApplicationLaunchException(
                    "Windows could not start the verified BAXY application.",
                    exception);
            }
        });
    }

    internal static char[] BuildEnvironmentBlock(
        IReadOnlyList<KeyValuePair<string, string>> snapshot)
    {
        if (snapshot is null)
        {
            throw new InstalledApplicationLaunchException(
                "Windows did not provide a process-environment snapshot.");
        }

        List<KeyValuePair<string, string>> filtered = new(snapshot.Count);
        HashSet<string> names = new(StringComparer.OrdinalIgnoreCase);
        foreach (KeyValuePair<string, string> pair in snapshot)
        {
            string? name = pair.Key;
            string? value = pair.Value;
            if (string.Equals(name, DataRootOverride, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (!IsValidEnvironmentName(name) || value is null || value.Contains('\0'))
            {
                throw new InstalledApplicationLaunchException(
                    "The inherited process environment is malformed.");
            }

            if (!names.Add(name!))
            {
                throw new InstalledApplicationLaunchException(
                    "The inherited process environment contains an ambiguous variable name.");
            }

            filtered.Add(new KeyValuePair<string, string>(name!, value));
        }

        filtered.Sort(static (left, right) =>
        {
            int insensitive = StringComparer.OrdinalIgnoreCase.Compare(left.Key, right.Key);
            return insensitive != 0
                ? insensitive
                : StringComparer.Ordinal.Compare(left.Key, right.Key);
        });

        long requiredCharacters = filtered.Count == 0 ? 2 : 1;
        foreach (KeyValuePair<string, string> pair in filtered)
        {
            requiredCharacters = checked(requiredCharacters + pair.Key.Length + pair.Value.Length + 2L);
        }

        if (requiredCharacters > MaximumEnvironmentBlockCharacters)
        {
            throw new InstalledApplicationLaunchException(
                "The inherited process environment exceeds the reviewed Windows limit.");
        }

        char[] block = new char[checked((int)requiredCharacters)];
        int offset = 0;
        foreach (KeyValuePair<string, string> pair in filtered)
        {
            pair.Key.AsSpan().CopyTo(block.AsSpan(offset));
            offset += pair.Key.Length;
            block[offset++] = '=';
            pair.Value.AsSpan().CopyTo(block.AsSpan(offset));
            offset += pair.Value.Length;
            block[offset++] = '\0';
        }

        return block;
    }

    private static bool IsValidEnvironmentName(string? name)
    {
        if (string.IsNullOrEmpty(name) || name.Contains('\0'))
        {
            return false;
        }

        if (name[0] != '=')
        {
            return !name.Contains('=');
        }

        return name.Length == 3 &&
            ((name[1] is >= 'A' and <= 'Z') || (name[1] is >= 'a' and <= 'z')) &&
            name[2] == ':';
    }
}

internal sealed class ProcessEnvironmentSnapshot : IInstalledApplicationEnvironment
{
    public IReadOnlyList<KeyValuePair<string, string>> Capture()
    {
        IDictionary variables = Environment.GetEnvironmentVariables();
        List<KeyValuePair<string, string>> snapshot = new(variables.Count);
        foreach (DictionaryEntry variable in variables)
        {
            if (variable.Key is not string name || variable.Value is not string value)
            {
                throw new InstalledApplicationLaunchException(
                    "Windows returned a malformed process-environment entry.");
            }

            snapshot.Add(new KeyValuePair<string, string>(name, value));
        }

        return snapshot;
    }
}

internal sealed partial class WindowsInstalledApplicationPlatform : IInstalledApplicationPlatform
{
    public uint CreateProcess(InstalledApplicationStartRequest request)
    {
        ValidateRequest(request);

        StartupInfo startupInfo = new()
        {
            Size = checked((uint)Marshal.SizeOf<StartupInfo>()),
        };

        GCHandle environmentHandle = GCHandle.Alloc(request.EnvironmentBlock, GCHandleType.Pinned);
        bool created;
        int error;
        ProcessInformation processInformation;
        try
        {
            created = CreateProcessW(
                request.ApplicationName,
                commandLine: 0,
                processAttributes: 0,
                threadAttributes: 0,
                request.InheritHandles,
                request.CreationFlags,
                environmentHandle.AddrOfPinnedObject(),
                request.WorkingDirectory,
                ref startupInfo,
                out processInformation);
            error = Marshal.GetLastPInvokeError();
        }
        finally
        {
            environmentHandle.Free();
        }

        if (!created)
        {
            throw new InstalledApplicationLaunchException(
                "CreateProcessW rejected the verified BAXY application.",
                new Win32Exception(error));
        }

        using SafeWaitHandle processHandle = new(processInformation.ProcessHandle, ownsHandle: true);
        using SafeWaitHandle threadHandle = new(processInformation.ThreadHandle, ownsHandle: true);
        if (processHandle.IsInvalid || threadHandle.IsInvalid || processInformation.ProcessId == 0)
        {
            throw new InstalledApplicationLaunchException(
                "CreateProcessW returned an invalid BAXY process result.");
        }

        return processInformation.ProcessId;
    }

    private static void ValidateRequest(InstalledApplicationStartRequest? request)
    {
        if (request is null ||
            !Path.IsPathFullyQualified(request.ApplicationName) ||
            !Path.IsPathFullyQualified(request.WorkingDirectory) ||
            request.CommandLine is not null ||
            request.InheritHandles ||
            request.CreationFlags != InstalledApplicationLauncher.RequiredCreationFlags ||
            request.EnvironmentBlock is not { Length: >= 2 } ||
            request.EnvironmentBlock[^1] != '\0' ||
            request.EnvironmentBlock[^2] != '\0' ||
            !string.Equals(
                Path.GetDirectoryName(request.ApplicationName),
                request.WorkingDirectory,
                StringComparison.OrdinalIgnoreCase))
        {
            throw new InstalledApplicationLaunchException(
                "The verified BAXY process-start contract is invalid.");
        }

        PathSafety.AssertExistingChainHasNoReparsePoint(request.WorkingDirectory);
        if (!Directory.Exists(request.WorkingDirectory))
        {
            throw new InstalledApplicationLaunchException(
                "The verified BAXY working directory disappeared before process creation.");
        }

        FileAttributes workingDirectoryAttributes = File.GetAttributes(request.WorkingDirectory);
        if ((workingDirectoryAttributes & FileAttributes.Directory) == 0 ||
            (workingDirectoryAttributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstalledApplicationLaunchException(
                "The verified BAXY working directory is unsafe.");
        }

        PathSafety.AssertRegularFile(request.ApplicationName);
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
