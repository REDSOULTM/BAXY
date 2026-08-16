using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.Marshalling;

namespace Baxy.Setup;

internal sealed record ShellLinkSpecification(
    string TargetPath,
    string WorkingDirectory,
    string Description,
    string Arguments,
    string IconPath,
    int IconIndex,
    int ShowCommand = 1);

internal static partial class WindowsShellLink
{
    private const int SOk = 0;
    private const int SFalse = 1;
    private const int MaxPathCharacters = 260;
    private const int MaximumInformationTipCharacters = 1024;
    private const uint CoInitApartmentThreaded = 0x2;
    private const uint ClassContextInProcessServer = 0x1;
    private const uint StorageModeRead = 0x0;
    private const uint ShellLinkGetPathRaw = 0x4;
    private const uint MoveFileWriteThrough = 0x8;

    private static readonly Guid ShellLinkClassId = new("00021401-0000-0000-C000-000000000046");
    private static readonly Guid ShellLinkInterfaceId = new("000214F9-0000-0000-C000-000000000046");
    private static readonly StrategyBasedComWrappers ComWrappers = new();

    internal static void WriteNewVerified(string linkPath, ShellLinkSpecification specification)
    {
        string destination = ValidateLinkDestination(linkPath, mustExist: false);
        ValidatedShellLinkSpecification validated = ValidateSpecification(specification);
        ExecuteInInitializedSta(() => WriteNewVerifiedCore(destination, validated, temporaryPath: null));
    }

    internal static void WriteNewVerifiedFromJournal(
        string linkPath,
        string temporaryPath,
        ShellLinkSpecification specification)
    {
        string destination = ValidateLinkDestination(linkPath, mustExist: false);
        string temporary = ValidateJournalTemporaryPath(destination, temporaryPath, mustBeNew: true);
        ValidatedShellLinkSpecification validated = ValidateSpecification(specification);
        ExecuteInInitializedSta(() => WriteNewVerifiedCore(destination, validated, temporary));
    }

    internal static void PromoteVerifiedJournalTemporary(
        string linkPath,
        string temporaryPath,
        ShellLinkSpecification specification)
    {
        string destination = ValidateLinkDestination(linkPath, mustExist: false);
        string temporary = ValidateJournalTemporaryPath(destination, temporaryPath, mustBeNew: false);
        ValidatedShellLinkSpecification validated = ValidateSpecification(specification);
        ExecuteInInitializedSta(() =>
        {
            ReadAndVerifyCore(temporary, validated);
            MoveNewLinkWriteThrough(temporary, destination);
            ReadAndVerifyCore(destination, validated);
        });
    }

    internal static void ReadAndVerify(string linkPath, ShellLinkSpecification specification)
    {
        string source = ValidateLinkDestination(linkPath, mustExist: true);
        ValidatedShellLinkSpecification validated = ValidateSpecification(specification);
        ExecuteInInitializedSta(() => ReadAndVerifyCore(source, validated));
    }

    internal static void ReadAndVerifyAfterInstallationMove(
        string linkPath,
        ShellLinkSpecification specification)
    {
        string source = ValidateLinkDestination(linkPath, mustExist: true);
        ValidatedShellLinkSpecification validated =
            ValidateSpecificationAfterInstallationMove(specification);
        ExecuteInInitializedSta(() => ReadAndVerifyCore(source, validated));
    }

    private static void WriteNewVerifiedCore(
        string destination,
        ValidatedShellLinkSpecification specification,
        string? temporaryPath)
    {
        if (File.Exists(destination) || Directory.Exists(destination))
        {
            throw new InstallationSafetyException("Refusing to overwrite an existing shell-link path.");
        }

        string parent = Path.GetDirectoryName(destination)!;
        string temporary = temporaryPath ?? CreateTemporarySiblingPath(parent);
        bool temporaryCreated = false;
        bool promoted = false;
        try
        {
            // Reserve the unpredictable name with CreateNew. Denying delete sharing keeps the
            // directory entry stable while ShellLink persists and a fresh COM instance reloads it.
            using (FileStream reservation = new(
                       temporary,
                       FileMode.CreateNew,
                       FileAccess.ReadWrite,
                       FileShare.ReadWrite))
            {
                temporaryCreated = true;
                CreateAndSave(temporary, specification);
                reservation.Flush(flushToDisk: true);
                PathSafety.AssertRegularFile(temporary);
                ReadAndVerifyCore(temporary, specification);
            }

            MoveNewLinkWriteThrough(temporary, destination);
            promoted = true;
        }
        finally
        {
            if (!promoted && temporaryCreated)
            {
                DeleteKnownTemporaryFailClosed(temporary);
            }
        }
    }

    private static unsafe void CreateAndSave(string path, ValidatedShellLinkSpecification specification)
    {
        ComObject instance = CreateShellLinkInstance();
        try
        {
            IShellLinkW shellLink = (IShellLinkW)(object)instance;
            IPersistFile persistFile = (IPersistFile)(object)instance;
            fixed (char* target = specification.TargetPath)
            fixed (char* workingDirectory = specification.WorkingDirectory)
            fixed (char* description = specification.Description)
            fixed (char* arguments = specification.Arguments)
            fixed (char* iconPath = specification.IconPath)
            fixed (char* persistedPath = path)
            {
                RequireSOk(shellLink.SetPath((nint)target), "IShellLinkW.SetPath");
                RequireSOk(
                    shellLink.SetWorkingDirectory((nint)workingDirectory),
                    "IShellLinkW.SetWorkingDirectory");
                RequireSOk(shellLink.SetDescription((nint)description), "IShellLinkW.SetDescription");
                RequireSOk(shellLink.SetArguments((nint)arguments), "IShellLinkW.SetArguments");
                RequireSOk(
                    shellLink.SetIconLocation((nint)iconPath, specification.IconIndex),
                    "IShellLinkW.SetIconLocation");
                RequireSOk(shellLink.SetShowCmd(specification.ShowCommand), "IShellLinkW.SetShowCmd");
                RequireSOk(persistFile.Save((nint)persistedPath, remember: 1), "IPersistFile.Save");
            }
        }
        finally
        {
            instance.FinalRelease();
        }
    }

    private static unsafe void ReadAndVerifyCore(
        string path,
        ValidatedShellLinkSpecification specification)
    {
        PathSafety.AssertRegularFile(path);
        ComObject instance = CreateShellLinkInstance();
        try
        {
            IShellLinkW shellLink = (IShellLinkW)(object)instance;
            IPersistFile persistFile = (IPersistFile)(object)instance;
            fixed (char* persistedPath = path)
            {
                RequireSOk(persistFile.Load((nint)persistedPath, StorageModeRead), "IPersistFile.Load");
            }

            Span<char> pathBuffer = stackalloc char[MaxPathCharacters];
            pathBuffer.Clear();
            string target;
            fixed (char* buffer = pathBuffer)
            {
                RequireSOk(
                    shellLink.GetPath(buffer, pathBuffer.Length, 0, ShellLinkGetPathRaw),
                    "IShellLinkW.GetPath");
                target = ReadNullTerminated(pathBuffer, "target path");
            }

            Span<char> workingDirectoryBuffer = stackalloc char[MaxPathCharacters];
            workingDirectoryBuffer.Clear();
            string workingDirectory;
            fixed (char* buffer = workingDirectoryBuffer)
            {
                RequireSOk(
                    shellLink.GetWorkingDirectory(buffer, workingDirectoryBuffer.Length),
                    "IShellLinkW.GetWorkingDirectory");
                workingDirectory = ReadNullTerminated(workingDirectoryBuffer, "working directory");
            }

            Span<char> descriptionBuffer = stackalloc char[MaximumInformationTipCharacters];
            descriptionBuffer.Clear();
            string description;
            fixed (char* buffer = descriptionBuffer)
            {
                RequireSOk(
                    shellLink.GetDescription(buffer, descriptionBuffer.Length),
                    "IShellLinkW.GetDescription");
                description = ReadNullTerminated(descriptionBuffer, "description");
            }

            Span<char> argumentsBuffer = stackalloc char[MaximumInformationTipCharacters];
            argumentsBuffer.Clear();
            string arguments;
            fixed (char* buffer = argumentsBuffer)
            {
                RequireSOk(
                    shellLink.GetArguments(buffer, argumentsBuffer.Length),
                    "IShellLinkW.GetArguments");
                arguments = ReadNullTerminated(argumentsBuffer, "arguments");
            }

            Span<char> iconPathBuffer = stackalloc char[MaxPathCharacters];
            iconPathBuffer.Clear();
            string iconPath;
            int iconIndex;
            fixed (char* buffer = iconPathBuffer)
            {
                RequireSOk(
                    shellLink.GetIconLocation(buffer, iconPathBuffer.Length, out iconIndex),
                    "IShellLinkW.GetIconLocation");
                iconPath = ReadNullTerminated(iconPathBuffer, "icon path");
            }

            RequireSOk(shellLink.GetShowCmd(out int showCommand), "IShellLinkW.GetShowCmd");
            RequireExact("target path", specification.TargetPath, target);
            RequireExact("working directory", specification.WorkingDirectory, workingDirectory);
            RequireExact("description", specification.Description, description);
            RequireExact("arguments", specification.Arguments, arguments);
            RequireExact("icon path", specification.IconPath, iconPath);
            if (iconIndex != specification.IconIndex)
            {
                throw new InstallationSafetyException("The shell-link icon index does not match its owned specification.");
            }

            if (showCommand != specification.ShowCommand)
            {
                throw new InstallationSafetyException("The shell-link show command does not match its owned specification.");
            }
        }
        finally
        {
            instance.FinalRelease();
        }
    }

    private static ComObject CreateShellLinkInstance()
    {
        Guid classId = ShellLinkClassId;
        Guid interfaceId = ShellLinkInterfaceId;
        RequireSOk(
            CoCreateInstance(
                ref classId,
                0,
                ClassContextInProcessServer,
                ref interfaceId,
                out nint nativeInstance),
            "CoCreateInstance(CLSID_ShellLink)");
        if (nativeInstance == 0)
        {
            throw new InstallationSafetyException("ShellLink activation returned a null COM interface.");
        }

        object wrapper;
        try
        {
            wrapper = ComWrappers.GetOrCreateObjectForComInstance(
                nativeInstance,
                CreateObjectFlags.UniqueInstance);
        }
        finally
        {
            ReleaseNativeComReference(nativeInstance);
        }

        return wrapper as ComObject ??
            throw new InstallationSafetyException("ShellLink activation did not produce a source-generated COM wrapper.");
    }

    private static unsafe void ReleaseNativeComReference(nint instance)
    {
        nint* virtualMethodTable = *(nint**)instance;
        delegate* unmanaged[Stdcall]<nint, uint> release =
            (delegate* unmanaged[Stdcall]<nint, uint>)virtualMethodTable[2];
        _ = release(instance);
    }

    private static void ExecuteInInitializedSta(Action action)
    {
        if (!OperatingSystem.IsWindows())
        {
            throw new PlatformNotSupportedException("Windows shell links require Windows.");
        }

        if (Thread.CurrentThread.GetApartmentState() != ApartmentState.STA)
        {
            throw new InstallationSafetyException("Windows shell-link operations require an explicit STA thread.");
        }

        int result = CoInitializeEx(0, CoInitApartmentThreaded);
        // SetApartmentState(STA) causes the CLR to initialize COM before managed code runs,
        // so the required explicit balancing call normally returns S_FALSE. COM requires an
        // additional CoUninitialize for both S_OK and S_FALSE; every shell/persist operation
        // below still requires the stronger, exact S_OK contract.
        if (result is not SOk and not SFalse)
        {
            throw new InstallationSafetyException(
                $"CoInitializeEx(COINIT_APARTMENTTHREADED) failed with HRESULT 0x{result:X8}.");
        }

        try
        {
            action();
        }
        finally
        {
            CoUninitialize();
        }
    }

    private static ValidatedShellLinkSpecification ValidateSpecification(ShellLinkSpecification specification)
    {
        ArgumentNullException.ThrowIfNull(specification);
        string target = ValidateExistingRegularFile(specification.TargetPath, "target path");
        string workingDirectory = ValidateExistingDirectory(specification.WorkingDirectory, "working directory");
        string icon = ValidateExistingRegularFile(specification.IconPath, "icon path");
        ValidateText(specification.Description, nameof(specification.Description), MaximumInformationTipCharacters);
        ValidateText(specification.Arguments, nameof(specification.Arguments), MaximumInformationTipCharacters);
        return new ValidatedShellLinkSpecification(
            target,
            workingDirectory,
            specification.Description,
            specification.Arguments,
            icon,
            specification.IconIndex,
            specification.ShowCommand);
    }

    private static ValidatedShellLinkSpecification ValidateSpecificationAfterInstallationMove(
        ShellLinkSpecification specification)
    {
        ArgumentNullException.ThrowIfNull(specification);
        string installationRoot = ValidateCanonicalAbsolutePath(
            specification.WorkingDirectory,
            "working directory");
        string validatedRoot = PathSafety.ValidateInstallationRoot(installationRoot);
        if (!string.Equals(installationRoot, validatedRoot, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The historical shell-link working directory is not a canonical installation root.");
        }

        string target = ValidateCanonicalAbsolutePath(specification.TargetPath, "target path");
        string icon = ValidateCanonicalAbsolutePath(specification.IconPath, "icon path");
        string expectedStableHost = Path.Combine(installationRoot, "Baxy.Setup.exe");
        if (!string.Equals(target, expectedStableHost, StringComparison.Ordinal) ||
            !string.Equals(icon, expectedStableHost, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "A historical BAXY shell link must target and use the exact stable setup host under its installation root.");
        }

        ValidateOptionalRegularDirectory(installationRoot, "working directory");
        ValidateOptionalRegularFile(target, "target and icon path");
        ValidateText(specification.Description, nameof(specification.Description), MaximumInformationTipCharacters);
        ValidateText(specification.Arguments, nameof(specification.Arguments), MaximumInformationTipCharacters);
        return new ValidatedShellLinkSpecification(
            target,
            installationRoot,
            specification.Description,
            specification.Arguments,
            icon,
            specification.IconIndex,
            specification.ShowCommand);
    }

    private static string ValidateLinkDestination(string path, bool mustExist)
    {
        string fullPath = ValidateAbsolutePath(path, "shell-link path", MaxPathCharacters);
        if (!string.Equals(Path.GetExtension(fullPath), ".lnk", StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException("A Windows shell-link path must use the .lnk extension.");
        }

        string? parent = Path.GetDirectoryName(fullPath);
        if (string.IsNullOrEmpty(parent))
        {
            throw new InstallationSafetyException("A Windows shell link must have an existing parent directory.");
        }

        _ = ValidateExistingDirectory(parent, "shell-link parent directory");
        bool exists = File.Exists(fullPath) || Directory.Exists(fullPath);
        if (mustExist)
        {
            if (!File.Exists(fullPath))
            {
                throw new InstallationSafetyException("The expected Windows shell link is missing or is not a file.");
            }

            PathSafety.AssertRegularFile(fullPath);
        }
        else if (exists)
        {
            throw new InstallationSafetyException("Refusing to overwrite an existing shell-link path.");
        }

        return fullPath;
    }

    private static string ValidateExistingRegularFile(string path, string field)
    {
        string fullPath = ValidateAbsolutePath(path, field, MaxPathCharacters);
        if (!File.Exists(fullPath))
        {
            throw new InstallationSafetyException($"The shell-link {field} must be an existing regular file.");
        }

        PathSafety.AssertRegularFile(fullPath);
        return fullPath;
    }

    private static string ValidateExistingDirectory(string path, string field)
    {
        string fullPath = ValidateAbsolutePath(path, field, MaxPathCharacters);
        PathSafety.AssertExistingChainHasNoReparsePoint(fullPath);
        if (!Directory.Exists(fullPath))
        {
            throw new InstallationSafetyException($"The shell-link {field} must be an existing directory.");
        }

        FileAttributes attributes = File.GetAttributes(fullPath);
        if ((attributes & FileAttributes.Directory) == 0 ||
            (attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstallationSafetyException($"The shell-link {field} is unsafe.");
        }

        return fullPath;
    }

    private static void ValidateOptionalRegularFile(string path, string field)
    {
        PathSafety.AssertExistingChainHasNoReparsePoint(path);
        if (File.Exists(path))
        {
            PathSafety.AssertRegularFile(path);
            return;
        }

        if (Directory.Exists(path))
        {
            throw new InstallationSafetyException(
                $"The historical shell-link {field} is not a regular file.");
        }
    }

    private static void ValidateOptionalRegularDirectory(string path, string field)
    {
        PathSafety.AssertExistingChainHasNoReparsePoint(path);
        if (Directory.Exists(path))
        {
            PathSafety.AssertRegularDirectory(path);
            return;
        }

        if (File.Exists(path))
        {
            throw new InstallationSafetyException(
                $"The historical shell-link {field} is not a regular directory.");
        }
    }

    private static string ValidateCanonicalAbsolutePath(string path, string field)
    {
        string fullPath = ValidateAbsolutePath(path, field, MaxPathCharacters);
        string canonical = fullPath.TrimEnd(
            Path.DirectorySeparatorChar,
            Path.AltDirectorySeparatorChar);
        if (!string.Equals(path, canonical, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                $"The historical shell-link {field} must use its exact canonical absolute path.");
        }

        return canonical;
    }

    private static string ValidateAbsolutePath(string path, string field, int bufferCharacters)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        if (!Path.IsPathFullyQualified(path))
        {
            throw new InstallationSafetyException($"The shell-link {field} must be an absolute path.");
        }

        if (path.Contains('\0'))
        {
            throw new InstallationSafetyException($"The shell-link {field} contains a null character.");
        }

        string fullPath = Path.GetFullPath(path);
        if (fullPath.Length >= bufferCharacters)
        {
            throw new InstallationSafetyException(
                $"The shell-link {field} exceeds the reviewed {bufferCharacters - 1}-character contract.");
        }

        return fullPath;
    }

    private static void ValidateText(string value, string field, int bufferCharacters)
    {
        ArgumentNullException.ThrowIfNull(value);
        if (value.Contains('\0'))
        {
            throw new InstallationSafetyException($"The shell-link {field} contains a null character.");
        }

        if (value.Length >= bufferCharacters)
        {
            throw new InstallationSafetyException(
                $"The shell-link {field} exceeds the reviewed {bufferCharacters - 1}-character contract.");
        }
    }

    private static string ValidateJournalTemporaryPath(
        string destination,
        string temporaryPath,
        bool mustBeNew)
    {
        string temporary = ValidateAbsolutePath(
            temporaryPath,
            "journaled shell-link temporary path",
            MaxPathCharacters);
        string destinationParent = Path.GetDirectoryName(destination)!;
        string? temporaryParent = Path.GetDirectoryName(temporary);
        if (!string.Equals(destinationParent, temporaryParent, StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException(
                "A journaled shell-link temporary must be a sibling of its destination.");
        }

        string leaf = Path.GetFileName(temporary);
        const string prefix = ".baxy-";
        const string suffix = ".lnk";
        string identifier = leaf.StartsWith(prefix, StringComparison.Ordinal) &&
            leaf.EndsWith(suffix, StringComparison.Ordinal)
            ? leaf[prefix.Length..^suffix.Length]
            : string.Empty;
        if (!Guid.TryParseExact(identifier, "N", out Guid parsed) ||
            !string.Equals(identifier, parsed.ToString("N"), StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "A journaled shell-link temporary must use exact .baxy-<lowercase-guid-N>.lnk form.");
        }

        bool exists = File.Exists(temporary) || Directory.Exists(temporary);
        if (mustBeNew && exists)
        {
            throw new InstallationSafetyException(
                "Refusing to overwrite an existing journaled shell-link temporary path.");
        }

        if (!mustBeNew && !File.Exists(temporary))
        {
            throw new InstallationSafetyException(
                "The expected journaled shell-link temporary is missing or is not a file.");
        }

        return temporary;
    }

    private static void MoveNewLinkWriteThrough(string source, string destination)
    {
        if (!MoveFileEx(source, destination, MoveFileWriteThrough))
        {
            throw new InstallationSafetyException(
                "Windows could not durably publish the verified shell link without overwrite.",
                new Win32Exception(Marshal.GetLastPInvokeError()));
        }
    }

    private static string CreateTemporarySiblingPath(string parent)
    {
        for (int attempt = 0; attempt < 8; attempt++)
        {
            string candidate = Path.Combine(parent, $".baxy-{Guid.NewGuid():N}.lnk");
            if (candidate.Length >= MaxPathCharacters)
            {
                throw new InstallationSafetyException("The shell-link parent is too long for a safe temporary sibling.");
            }

            if (!File.Exists(candidate) && !Directory.Exists(candidate))
            {
                return candidate;
            }
        }

        throw new InstallationSafetyException("Unable to allocate a new shell-link temporary sibling name.");
    }

    private static void DeleteKnownTemporaryFailClosed(string temporary)
    {
        if (!File.Exists(temporary))
        {
            return;
        }

        PathSafety.AssertRegularFile(temporary);
        File.Delete(temporary);
    }

    private static string ReadNullTerminated(ReadOnlySpan<char> buffer, string field)
    {
        int terminator = buffer.IndexOf('\0');
        if (terminator < 0)
        {
            throw new InstallationSafetyException($"The shell-link {field} exceeded its reviewed COM buffer.");
        }

        return new string(buffer[..terminator]);
    }

    private static void RequireExact(string field, string expected, string actual)
    {
        if (!string.Equals(expected, actual, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException($"The shell-link {field} does not match its owned specification.");
        }
    }

    private static void RequireSOk(int result, string operation)
    {
        if (result != SOk)
        {
            throw new InstallationSafetyException(
                $"{operation} returned non-canonical HRESULT 0x{result:X8}.");
        }
    }

    [LibraryImport("ole32.dll")]
    private static partial int CoInitializeEx(nint reserved, uint coInit);

    [LibraryImport("ole32.dll")]
    private static partial void CoUninitialize();

    [LibraryImport("ole32.dll")]
    private static partial int CoCreateInstance(
        ref Guid classId,
        nint outer,
        uint classContext,
        ref Guid interfaceId,
        out nint instance);

    [LibraryImport(
        "kernel32.dll",
        EntryPoint = "MoveFileExW",
        SetLastError = true,
        StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool MoveFileEx(
        string existingFileName,
        string newFileName,
        uint flags);

    private sealed record ValidatedShellLinkSpecification(
        string TargetPath,
        string WorkingDirectory,
        string Description,
        string Arguments,
        string IconPath,
        int IconIndex,
        int ShowCommand);
}

[GeneratedComInterface(
    Options = ComInterfaceOptions.ComObjectWrapper,
    StringMarshalling = StringMarshalling.Utf16)]
[Guid("000214F9-0000-0000-C000-000000000046")]
internal unsafe partial interface IShellLinkW
{
    [PreserveSig]
    int GetPath(char* file, int maximumCharacters, nint findData, uint flags);

    [PreserveSig]
    int GetIDList(out nint itemIdList);

    [PreserveSig]
    int SetIDList(nint itemIdList);

    [PreserveSig]
    int GetDescription(char* description, int maximumCharacters);

    [PreserveSig]
    int SetDescription(nint description);

    [PreserveSig]
    int GetWorkingDirectory(char* directory, int maximumCharacters);

    [PreserveSig]
    int SetWorkingDirectory(nint directory);

    [PreserveSig]
    int GetArguments(char* arguments, int maximumCharacters);

    [PreserveSig]
    int SetArguments(nint arguments);

    [PreserveSig]
    int GetHotkey(out ushort hotkey);

    [PreserveSig]
    int SetHotkey(ushort hotkey);

    [PreserveSig]
    int GetShowCmd(out int showCommand);

    [PreserveSig]
    int SetShowCmd(int showCommand);

    [PreserveSig]
    int GetIconLocation(char* iconPath, int maximumCharacters, out int iconIndex);

    [PreserveSig]
    int SetIconLocation(nint iconPath, int iconIndex);

    [PreserveSig]
    int SetRelativePath(nint relativePath, uint reserved);

    [PreserveSig]
    int Resolve(nint ownerWindow, uint flags);

    [PreserveSig]
    int SetPath(nint file);
}

[GeneratedComInterface(
    Options = ComInterfaceOptions.ComObjectWrapper,
    StringMarshalling = StringMarshalling.Utf16)]
[Guid("0000010C-0000-0000-C000-000000000046")]
internal partial interface IPersist
{
    [PreserveSig]
    int GetClassID(out Guid classId);
}

[GeneratedComInterface(
    Options = ComInterfaceOptions.ComObjectWrapper,
    StringMarshalling = StringMarshalling.Utf16)]
[Guid("0000010B-0000-0000-C000-000000000046")]
internal partial interface IPersistFile : IPersist
{
    [PreserveSig]
    int IsDirty();

    [PreserveSig]
    int Load(nint fileName, uint mode);

    [PreserveSig]
    int Save(nint fileName, int remember);

    [PreserveSig]
    int SaveCompleted(nint fileName);

    [PreserveSig]
    int GetCurFile(out nint fileName);
}
