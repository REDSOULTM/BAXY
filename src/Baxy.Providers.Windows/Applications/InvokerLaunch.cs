using System.Collections;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.Applications;

/// <summary>
/// v3 r5a M5 (v3-22, 23, 65, 66, 67, 69, 72): an application BAXY opened through the shell came up as administrator
/// by itself, and a window that runs above BAXY can be neither read nor pressed (VisibleControlSurface.RunsAboveUs).
/// The cause is in the executable's own manifest: «highestAvailable», or «autoElevate», asks Windows to raise the
/// program whenever the person is an administrator, without anyone asking for it. A program that can run with the
/// person's ordinary rights is then started the way the person starts it from a plain console: the shortcut's target
/// and arguments, through CreateProcess, with the compatibility layer «RunAsInvoker». The rule is the manifest's,
/// never a list of programs. A manifest that says «requireAdministrator» cannot run without the rights and keeps the
/// shell's path (Windows asks the person, as before).
/// Measured live 2026-10-08 (r5a): the management consoles (a «.msc» document started by its associated host) open
/// with the person's rights and a full accessible tree. A program that raises itself from its own code (it starts
/// again elevated after reading its token) still ends elevated: the window is then an honest limit, as before.
/// </summary>
internal static partial class InvokerLaunch
{
    internal const string CompatibilityLayerVariable = "__COMPAT_LAYER";
    internal const string RunAsInvoker = "RunAsInvoker";

    internal sealed record ManifestElevation(string? Level, bool AutoElevate)
    {
        // Raised by Windows although nobody asked: «highestAvailable», or «autoElevate» on a program that does not
        // require the rights. «requireAdministrator» is a program that cannot run without them.
        public bool RaisesUnasked =>
            !string.Equals(Level, "requireAdministrator", StringComparison.OrdinalIgnoreCase)
            && (string.Equals(Level, "highestAvailable", StringComparison.OrdinalIgnoreCase) || AutoElevate);

        // Review of M5: started with the person's rights, it stays with them. Measured live (r5a, 2026-10-08): the
        // consoles («highestAvailable» alone) opened unraised and readable; a program marked «autoElevate» raised
        // itself again from its own code (the Task Manager, «asInvoker» with «autoElevate»; the performance monitor
        // behind the Resource Monitor, «highestAvailable» with «autoElevate»). Only the first is offered to reopen.
        public bool ReopensUnraised =>
            string.Equals(Level, "highestAvailable", StringComparison.OrdinalIgnoreCase) && !AutoElevate;
    }

    /// <summary>
    /// Whether the elevated window of <paramref name="processId"/> would open again with the person's rights if BAXY
    /// reopened it (ManifestElevation.ReopensUnraised over the process's executable); false when it cannot be read.
    /// </summary>
    internal static bool WindowReopensUnraised(int processId) =>
        processId > 0
        && WindowsInstalledApplicationPlatform.ExecutableImagePath(processId) is { Length: > 0 } executable
        && ParseManifest(ReadManifest(executable)).ReopensUnraised;

    internal sealed record LaunchPlan(string Executable, string Arguments, string WorkingDirectory);

    internal static ManifestElevation ParseManifest(string? manifest)
    {
        if (string.IsNullOrWhiteSpace(manifest))
            return new ManifestElevation(null, false);
        Match level = LevelPattern().Match(manifest);
        Match autoElevate = AutoElevatePattern().Match(manifest);
        return new ManifestElevation(
            level.Success ? level.Groups["level"].Value : null,
            autoElevate.Success && string.Equals(autoElevate.Groups["value"].Value, "true", StringComparison.OrdinalIgnoreCase));
    }

    /// <summary>
    /// What to start for a shortcut's target: an executable is itself; a document (a console file) is started by the
    /// command its type is associated with, «%1» being the document and «%*» the shortcut's arguments.
    /// </summary>
    internal static (string Executable, string Arguments)? ResolveCommand(
        string target,
        string? arguments,
        Func<string, string?> associatedCommand)
    {
        if (string.IsNullOrWhiteSpace(target) || !Path.IsPathRooted(target))
            return null;
        string shortcutArguments = arguments?.Trim() ?? string.Empty;
        string extension = Path.GetExtension(target);
        if (string.Equals(extension, ".exe", StringComparison.OrdinalIgnoreCase))
            return (target, shortcutArguments);
        if (string.IsNullOrEmpty(extension))
            return null;
        string? template = associatedCommand(extension);
        if (string.IsNullOrWhiteSpace(template))
            return null;
        template = Environment.ExpandEnvironmentVariables(template.Trim());
        string executable;
        string rest;
        if (template.StartsWith('"'))
        {
            int close = template.IndexOf('"', 1);
            if (close < 0)
                return null;
            executable = template[1..close];
            rest = template[(close + 1)..];
        }
        else
        {
            int space = template.IndexOf(' ');
            executable = space < 0 ? template : template[..space];
            rest = space < 0 ? string.Empty : template[space..];
        }

        if (!string.Equals(Path.GetExtension(executable), ".exe", StringComparison.OrdinalIgnoreCase)
            || !Path.IsPathRooted(executable))
        {
            return null;
        }

        bool tookDocument = rest.Contains("%1", StringComparison.Ordinal) || rest.Contains("%L", StringComparison.OrdinalIgnoreCase);
        string expanded = rest
            .Replace("%1", target, StringComparison.Ordinal)
            .Replace("%L", target, StringComparison.OrdinalIgnoreCase)
            .Replace("%*", shortcutArguments, StringComparison.Ordinal)
            .Trim();
        if (!tookDocument)
            expanded = ($"\"{target}\" {expanded}").Trim();
        return (executable, expanded);
    }

    /// <summary>
    /// The plan for a classic shortcut whose program Windows would raise unasked; null keeps the shell's path.
    /// </summary>
    internal static LaunchPlan? Plan(
        InstalledApplicationEntry entry,
        Func<string, bool> exists,
        Func<string, string?> associatedCommand,
        Func<string, string?> readManifest)
    {
        // A packaged application («…!App») never runs as administrator and is activated by its manager.
        if (entry.AppUserModelId.Contains('!', StringComparison.Ordinal)
            || string.IsNullOrWhiteSpace(entry.TargetPath)
            || !exists(entry.TargetPath))
        {
            return null;
        }

        (string Executable, string Arguments)? command = ResolveCommand(entry.TargetPath, entry.TargetArguments, associatedCommand);
        if (command is null || !exists(command.Value.Executable))
            return null;
        if (!ParseManifest(readManifest(command.Value.Executable)).RaisesUnasked)
            return null;
        string directory = Path.GetDirectoryName(command.Value.Executable) ?? Environment.SystemDirectory;
        return new LaunchPlan(command.Value.Executable, command.Value.Arguments, directory);
    }

    // Review of M5: BAXY's core runs inside the App's kill-on-close job, and a program it starts directly would die with
    // BAXY (or with a restart of the core) and inherit the core's inheritable handles, among them its stdio pipes. Like
    // WindowsApplicationLauncher, the program leaves the job and inherits nothing; its environment is the core's plus
    // the compatibility layer.
    internal const uint CreateBreakawayFromJob = 0x01000000;
    internal const uint CreateUnicodeEnvironment = 0x00000400;

    internal sealed record StartRequest(
        string Executable,
        string CommandLine,
        string WorkingDirectory,
        uint CreationFlags,
        bool InheritHandles,
        string EnvironmentBlock);

    // Pasada r15b v3-57: a page BAXY opens for the person in its own CDP browser is the person's window, like an
    // application it opens; started from the core it stayed in the kill-on-close job and vanished when BAXY closed
    // (6 s after «He abierto una nueva pestaña en Edge…» nothing was left). It leaves the job the same way, with the
    // core's environment as it is (no compatibility layer: the browser is not being kept from raising itself).
    internal static StartRequest PrepareOutsideBaxy(LaunchPlan plan, IDictionary environment) =>
        Prepare(plan, environment) with { EnvironmentBlock = BuildEnvironment(environment, compatibilityLayer: false) };

    internal static int StartOutsideBaxy(LaunchPlan plan) =>
        Create(PrepareOutsideBaxy(plan, Environment.GetEnvironmentVariables()));

    internal static StartRequest Prepare(LaunchPlan plan, IDictionary environment)
    {
        string commandLine = "\"" + plan.Executable + "\"" + (plan.Arguments.Length > 0 ? " " + plan.Arguments : string.Empty);
        return new StartRequest(
            plan.Executable,
            commandLine,
            plan.WorkingDirectory,
            CreateBreakawayFromJob | CreateUnicodeEnvironment,
            InheritHandles: false,
            BuildEnvironment(environment, compatibilityLayer: true));
    }

    private static string BuildEnvironment(IDictionary environment, bool compatibilityLayer)
    {
        var variables = new SortedDictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (DictionaryEntry variable in environment)
        {
            if (variable.Key is string name && name.Length > 0 && !name.Contains('\0') && !name.Contains('=')
                && (variable.Value as string ?? string.Empty) is var value && !value.Contains('\0'))
            {
                variables[name] = value;
            }
        }

        if (compatibilityLayer)
            variables[CompatibilityLayerVariable] = RunAsInvoker;
        return string.Concat(variables.Select(static pair => pair.Key + "=" + pair.Value + "\0")) + "\0";
    }

    internal static bool Start(LaunchPlan plan) => Create(Prepare(plan, Environment.GetEnvironmentVariables())) > 0;

    // The started process's id, 0 when it could not be started.
    private static unsafe int Create(StartRequest request)
    {
        var startup = new StartupInfo { Size = (uint)sizeof(StartupInfo) };
        char[] commandLine = (request.CommandLine + "\0").ToCharArray();
        fixed (char* environment = request.EnvironmentBlock)
        fixed (char* line = commandLine)
        {
            if (!CreateProcess(
                    request.Executable,
                    line,
                    0,
                    0,
                    request.InheritHandles,
                    request.CreationFlags,
                    environment,
                    request.WorkingDirectory,
                    ref startup,
                    out ProcessInformation information))
            {
                return 0;
            }

            CloseHandle(information.Process);
            CloseHandle(information.Thread);
            return (int)information.ProcessId;
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct StartupInfo
    {
        public uint Size;
        public nint Reserved;
        public nint Desktop;
        public nint Title;
        public uint X;
        public uint Y;
        public uint XSize;
        public uint YSize;
        public uint XCountChars;
        public uint YCountChars;
        public uint FillAttribute;
        public uint Flags;
        public ushort ShowWindow;
        public ushort Reserved2Size;
        public nint Reserved2;
        public nint StdInput;
        public nint StdOutput;
        public nint StdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ProcessInformation
    {
        public nint Process;
        public nint Thread;
        public uint ProcessId;
        public uint ThreadId;
    }

    [LibraryImport("kernel32.dll", EntryPoint = "CreateProcessW", StringMarshalling = StringMarshalling.Utf16, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static unsafe partial bool CreateProcess(
        string applicationName,
        char* commandLine,
        nint processAttributes,
        nint threadAttributes,
        [MarshalAs(UnmanagedType.Bool)] bool inheritHandles,
        uint creationFlags,
        char* environment,
        string currentDirectory,
        ref StartupInfo startupInfo,
        out ProcessInformation processInformation);

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool CloseHandle(nint handle);

    internal static string? AssociatedCommand(string extension)
    {
        const int AssocStrCommand = 1;
        const int AssocFNoTruncate = 0x20;
        uint length = 0;
        AssocQueryString(AssocFNoTruncate, AssocStrCommand, extension, "open", null, ref length);
        if (length == 0 || length > 4096)
            return null;
        char[] buffer = new char[length];
        int result = AssocQueryString(AssocFNoTruncate, AssocStrCommand, extension, "open", buffer, ref length);
        return result == 0 && length > 0 ? new string(buffer, 0, (int)length - 1) : null;
    }

    /// <summary>The executable's application manifest (resource type 24), as text; null when it has none.</summary>
    internal static string? ReadManifest(string executable)
    {
        const uint LoadLibraryAsDatafile = 0x2;
        const uint LoadLibraryAsImageResource = 0x20;
        nint module = LoadLibraryEx(executable, 0, LoadLibraryAsDatafile | LoadLibraryAsImageResource);
        if (module == 0)
            return null;
        try
        {
            foreach (int id in new[] { 1, 2, 3 })
            {
                nint resource = FindResource(module, id, 24);
                if (resource == 0)
                    continue;
                nint data = LockResource(LoadResource(module, resource));
                int size = (int)SizeofResource(module, resource);
                if (data == 0 || size <= 0)
                    continue;
                byte[] bytes = new byte[size];
                Marshal.Copy(data, bytes, 0, size);
                return System.Text.Encoding.UTF8.GetString(bytes);
            }

            return null;
        }
        finally
        {
            FreeLibrary(module);
        }
    }

    [GeneratedRegex(@"requestedExecutionLevel[^>]*?\blevel\s*=\s*[""'](?<level>[A-Za-z]+)[""']", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex LevelPattern();

    [GeneratedRegex(@"<(?:\w+:)?autoElevate[^>]*>\s*(?<value>[A-Za-z]+)\s*<", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex AutoElevatePattern();

    [LibraryImport("shlwapi.dll", EntryPoint = "AssocQueryStringW", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int AssocQueryString(int flags, int str, string assoc, string? extra, [Out] char[]? output, ref uint length);

    [LibraryImport("kernel32.dll", EntryPoint = "LoadLibraryExW", StringMarshalling = StringMarshalling.Utf16, SetLastError = true)]
    private static partial nint LoadLibraryEx(string path, nint file, uint flags);

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool FreeLibrary(nint module);

    [LibraryImport("kernel32.dll", EntryPoint = "FindResourceW")]
    private static partial nint FindResource(nint module, nint name, nint type);

    [LibraryImport("kernel32.dll")]
    private static partial nint LoadResource(nint module, nint resource);

    [LibraryImport("kernel32.dll")]
    private static partial nint LockResource(nint data);

    [LibraryImport("kernel32.dll")]
    private static partial uint SizeofResource(nint module, nint resource);
}
