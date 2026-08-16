namespace Baxy.Setup;

internal sealed record CanonicalWindowsPaths(
    string InstallationRoot,
    string StableSetupHost,
    string VersionsRoot,
    string CurrentPointer,
    string DataRoot,
    string StartMenuDirectory,
    string StartMenuShortcut)
{
    internal static CanonicalWindowsPaths Resolve()
    {
        return FromKnownFoldersCore(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.Programs),
            inspectDataRoot: true);
    }

    internal static CanonicalWindowsPaths ResolveForUninstall()
    {
        return FromKnownFoldersCore(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            Environment.GetFolderPath(Environment.SpecialFolder.Programs),
            inspectDataRoot: false);
    }

    internal static CanonicalWindowsPaths FromKnownFolders(
        string localAppData,
        string programsFolder) =>
        FromKnownFoldersCore(localAppData, programsFolder, inspectDataRoot: true);

    internal static CanonicalWindowsPaths FromKnownFoldersForUninstall(
        string localAppData,
        string programsFolder) =>
        FromKnownFoldersCore(localAppData, programsFolder, inspectDataRoot: false);

    private static CanonicalWindowsPaths FromKnownFoldersCore(
        string localAppData,
        string programsFolder,
        bool inspectDataRoot)
    {
        string localAppDataFull = ValidateKnownFolder(localAppData, "LocalApplicationData");
        string programsFolderFull = ValidateKnownFolder(programsFolder, "Programs");

        string installationRoot = GetStrictDescendant(localAppDataFull, "Programs", "BAXY");
        string stableSetupHost = GetStrictDescendant(installationRoot, "Baxy.Setup.exe");
        string versionsRoot = GetStrictDescendant(installationRoot, "versions");
        string currentPointer = GetStrictDescendant(installationRoot, "current");
        string dataRoot = GetStrictDescendant(localAppDataFull, "BAXY");
        string startMenuDirectory = GetStrictDescendant(programsFolderFull, "BAXY");
        string startMenuShortcut = GetStrictDescendant(startMenuDirectory, "BAXY.lnk");

        List<string> paths =
        [
            installationRoot,
            stableSetupHost,
            versionsRoot,
            currentPointer,
            startMenuDirectory,
            startMenuShortcut,
        ];
        if (inspectDataRoot)
        {
            paths.Add(dataRoot);
        }

        foreach (string path in paths)
        {
            PathSafety.AssertExistingChainHasNoReparsePoint(path);
        }

        return new CanonicalWindowsPaths(
            installationRoot,
            stableSetupHost,
            versionsRoot,
            currentPointer,
            dataRoot,
            startMenuDirectory,
            startMenuShortcut);
    }

    private static string ValidateKnownFolder(string path, string name)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        if (!Path.IsPathFullyQualified(path))
        {
            throw new InstallationSafetyException($"Windows did not provide an absolute {name} path.");
        }

        string fullPath = Path.TrimEndingDirectorySeparator(Path.GetFullPath(path));
        PathSafety.AssertExistingChainHasNoReparsePoint(fullPath);
        return fullPath;
    }

    private static string GetStrictDescendant(string root, params string[] segments)
    {
        string candidate = Path.GetFullPath(Path.Combine([root, .. segments]));
        string prefix = Path.EndsInDirectorySeparator(root) ? root : root + Path.DirectorySeparatorChar;
        if (!candidate.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException("A canonical Windows path escaped its owned root.");
        }

        return candidate;
    }
}
