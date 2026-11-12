using System.Buffers.Binary;
using System.IO.Compression;

namespace Baxy.Installer;

internal enum InstallPhase
{
    Downloading,
    Unpacking,
}

/// <summary>Where one installation lives. Beside <see cref="Root"/>, the staging and download folders share its drive.</summary>
internal sealed record InstallPaths(string Root)
{
    internal static InstallPaths ForThisUser { get; } = new(Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "Programs",
        "BAXY-App"));

    internal string Staging => Root + ".new";

    internal string Previous => Root + ".old";

    internal string Downloads => Root + ".download";

    internal string App => Path.Combine(Root, "app", "Baxy.exe");

    /// <summary>The folder has BAXY's app. Not this installer alone: a Downloads folder holds it too.</summary>
    internal bool HoldsBaxy => File.Exists(App);

    /// <summary>
    /// UNI1 (REV8 U4): the file that says a folder is BAXY's. The installer leaves it in the folders it makes beside the
    /// installation (its downloads and the one it unpacks into, which becomes the installation), so an uninstall deletes
    /// a folder beside it for being BAXY's, not for its name.
    /// </summary>
    internal const string MarkName = "BAXY-folder.mark";

    internal static void MarkAsBaxys(string folder)
    {
        Directory.CreateDirectory(folder);
        File.WriteAllText(Path.Combine(folder, MarkName), "BAXY");
    }

    /// <summary>
    /// UNI1 (REV8 U4): a folder beside the installation is BAXY's when its mark, its app or its uninstaller is in it, or
    /// when it is empty. One that only shares the name stays: a backup the person called «BAXY-App.old» is not BAXY's to
    /// delete. UPD1 (blind review): or when all it holds are the Windows components this installer downloads into its
    /// .download (Prerequisites.DownloadNames), which an installer up to 1.4.2 left there unmarked when one failed.
    /// </summary>
    internal static bool IsBaxys(string folder) =>
        File.Exists(Path.Combine(folder, MarkName))
        || new InstallPaths(folder).HoldsBaxy
        || File.Exists(Path.Combine(folder, WindowsIntegration.InstallerName))
        || Directory.EnumerateFileSystemEntries(folder).All(static entry =>
            File.Exists(entry) && Prerequisites.DownloadNames.Contains(Path.GetFileName(entry), StringComparer.OrdinalIgnoreCase))
        || HoldsOnlyReleaseParts(folder);

    /// <summary>
    /// REM1 (REV12 A-1): an installer before UNI1 (1.3.x) downloaded the parts of the release's zips into an unmarked
    /// .download and kept them when the download was cut. They are known by what they hold, whatever version: the first
    /// part of each zip begins with a zip entry («local file header signature 0x04034b50», then the entry's name at byte
    /// 30: PKWARE APPNOTE.TXT 4.3.7), and a release's first zip begins with app/Baxy.exe, the file every release holds
    /// (<see cref="Installation.RunAsync"/> checks it). The parts after the first are named after it (.000, .001…), and are
    /// downloaded in order, so the first is always there. The release's other zips (one per graphics card) are named after
    /// its first («baxy-1.3.1» and «baxy-1.3.1-nvidia»): a zip of anyone else's beside them is not (revisión ciega). Beside
    /// them, only the Windows components.
    /// </summary>
    private static bool HoldsOnlyReleaseParts(string folder)
    {
        try
        {
            List<string> names = [];
            foreach (string entry in Directory.EnumerateFileSystemEntries(folder))
            {
                if (!File.Exists(entry))
                {
                    return false;
                }

                names.Add(Path.GetFileName(entry));
            }

            HashSet<string> zips = new(StringComparer.OrdinalIgnoreCase);
            string? release = null;
            foreach (string first in names.Where(static name => name.EndsWith(".000", StringComparison.Ordinal)))
            {
                if (FirstZipEntry(Path.Combine(folder, first)) is { } entryName)
                {
                    zips.Add(first[..^4]);
                    if (entryName.Replace('\\', '/').Equals("app/Baxy.exe", StringComparison.OrdinalIgnoreCase))
                    {
                        release = Path.GetFileNameWithoutExtension(first[..^4]);
                    }
                }
            }

            return release is not null
                && zips.All(zip => zip.StartsWith(release, StringComparison.OrdinalIgnoreCase))
                && names.All(name =>
                Prerequisites.DownloadNames.Contains(name, StringComparer.OrdinalIgnoreCase)
                || (Path.GetExtension(name) is { Length: > 1 } number && number[1..].All(char.IsAsciiDigit)
                    && zips.Contains(Path.GetFileNameWithoutExtension(name))));
        }
        catch (Exception unreadable) when (unreadable is IOException or UnauthorizedAccessException)
        {
            Program.Log(unreadable.ToString());
            return false;
        }
    }

    /// <summary>
    /// The name of the first entry of the zip that <paramref name="part"/> begins; empty when the download was cut before
    /// that name (what there is matches the signature); null when it begins no zip.
    /// </summary>
    private static string? FirstZipEntry(string part)
    {
        ReadOnlySpan<byte> signature = [0x50, 0x4b, 0x03, 0x04];
        using FileStream file = new(part, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        Span<byte> header = stackalloc byte[30];
        int read = file.ReadAtLeast(header, header.Length, throwOnEndOfStream: false);
        int compared = Math.Min(read, signature.Length);
        if (!header[..compared].SequenceEqual(signature[..compared]))
        {
            return null;
        }

        if (read < header.Length)
        {
            return string.Empty;
        }

        byte[] name = new byte[BinaryPrimitives.ReadUInt16LittleEndian(header[26..])];
        int named = file.ReadAtLeast(name, name.Length, throwOnEndOfStream: false);
        return named < name.Length ? string.Empty : System.Text.Encoding.UTF8.GetString(name);
    }

    /// <summary>
    /// UPD1 (REV10 M4): an install or update deletes its .new, .old and .download, and writes into the last; the first of
    /// them that is there and is not BAXY's (<see cref="IsBaxys"/>, the uninstaller's own check) stops it before anything.
    /// </summary>
    internal void RefuseWhatIsNotBaxys()
    {
        if (new[] { Previous, Staging, Downloads }.FirstOrDefault(folder => Directory.Exists(folder) && !IsBaxys(folder)) is { } foreign)
        {
            throw new NotBaxysException(foreign);
        }
    }

    /// <summary>
    /// A folder and all in it, a link as a link, never what it points to (Microsoft Learn, Directory.Delete: «This method
    /// does not recurse through the reparse point»). UNI1 (REV8 U3): .NET's recursive delete still stops at a junction
    /// inside the tree («Access to the path is denied», measured) after deleting the rest, so each link goes on its own.
    /// Each folder's mark goes last, so one left half deleted is still known to be BAXY's.
    /// </summary>
    internal static void DeleteTree(string folder)
    {
        DirectoryInfo root = new(folder);
        if (root.LinkTarget is null)
        {
            foreach (DirectoryInfo inside in root.EnumerateDirectories())
            {
                DeleteTree(inside.FullName);
            }

            foreach (FileInfo file in root.EnumerateFiles().OrderBy(static file => file.Name == MarkName))
            {
                file.Delete();
            }
        }

        root.Delete();
    }

    /// <summary>
    /// A folder given with --dir: a full path, never a drive's root, that does not exist, is empty or already holds BAXY.
    /// The swap moves whatever was there away and deletes it, so a folder of the person's own is refused.
    /// </summary>
    internal static InstallPaths Chosen(string folder)
    {
        InstallPaths paths = Given(folder);
        string full = paths.Root;
        if (Directory.Exists(full) && Directory.EnumerateFileSystemEntries(full).Any() && !paths.HoldsBaxy)
        {
            throw new ArgumentException($"{full} has other files and BAXY would replace them: choose a new or empty folder");
        }

        // Its .new, .old and .download beside it are deleted too: they must be BAXY's.
        if (!paths.HoldsBaxy && new[] { paths.Staging, paths.Previous, paths.Downloads }.FirstOrDefault(Directory.Exists) is { } beside)
        {
            throw new ArgumentException($"{beside} is beside that folder and BAXY would delete it: choose another folder");
        }

        return paths;
    }

    /// <summary>A folder given with --dir: a full path, never a drive's root.</summary>
    private static InstallPaths Given(string folder)
    {
        if (!Path.IsPathFullyQualified(folder))
        {
            throw new ArgumentException($"--dir needs a full path, not «{folder}»");
        }

        string full = Path.TrimEndingDirectorySeparator(Path.GetFullPath(folder));
        return string.Equals(full, Path.TrimEndingDirectorySeparator(Path.GetPathRoot(full)!), StringComparison.OrdinalIgnoreCase)
            ? throw new ArgumentException($"--dir cannot be a whole drive ({full})")
            : new InstallPaths(full);
    }

    /// <summary>
    /// What an uninstall removes: the folder given; else the one this installer runs from, when it is an installation
    /// (the copy kept inside a BAXY opened by hand, REV8 U6); else the one «Installed apps» names; else the usual one.
    /// UNI1 (REV8 U2): whichever it is must be a BAXY. A folder that does not exist or holds none is refused before
    /// anything is touched, data included, so a mistyped --dir never ends in «uninstalled» with nothing uninstalled.
    /// </summary>
    /// <param name="running">This installer's exe (<see cref="Environment.ProcessPath"/>).</param>
    /// <param name="usual">The usual folder; tests give one of their own.</param>
    internal static InstallPaths ForUninstall(string? folder, WindowsPlaces places, string? running = null, InstallPaths? usual = null)
    {
        usual ??= ForThisUser;
        if (folder is not null)
        {
            InstallPaths chosen = Given(folder);
            return IsAnInstallation(chosen, places)
                ? chosen
                : throw new NothingToUninstallException(CommandLine.NothingToUninstall(CommandLine.Language, chosen.Root));
        }

        InstallPaths?[] candidates =
        [
            Path.GetDirectoryName(running) is { Length: > 0 } own ? new InstallPaths(own) : null,
            WindowsIntegration.RegisteredRoot(places) is { } registered ? new InstallPaths(registered) : null,
            usual,
        ];
        return candidates.FirstOrDefault(candidate => candidate is not null && IsAnInstallation(candidate, places))
            ?? throw new NothingToUninstallException(CommandLine.NothingToUninstall(CommandLine.Language, usual.Root));
    }

    /// <summary>
    /// BAXY's app is there; or its uninstaller is, in the folder «Installed apps» names or beside BAXY's mark: what an
    /// uninstall stopped halfway leaves (the folder emptied around the exe that waits), so it can be run again. A
    /// Downloads folder with the installer alone is neither.
    /// </summary>
    private static bool IsAnInstallation(InstallPaths candidate, WindowsPlaces places) =>
        candidate.HoldsBaxy
        || (File.Exists(Path.Combine(candidate.Root, WindowsIntegration.InstallerName))
            && (File.Exists(Path.Combine(candidate.Root, MarkName)) || WindowsIntegration.IsRegistered(candidate.Root, places)));
}

/// <summary>An uninstall pointed where there is no BAXY (<see cref="CommandLine.NotInstalled"/>).</summary>
internal sealed class NothingToUninstallException(string message) : ArgumentException(message);

internal sealed class InstallBlockedException(string message, Exception inner) : IOException(message, inner);

/// <summary>UPD1 (REV10 M4): a folder beside the installation has the name BAXY uses but is not BAXY's, and stays.</summary>
internal sealed class NotBaxysException(string folder)
    : IOException($"{folder} has the name of a folder BAXY uses beside the installation but is not BAXY's: it was left as it is")
{
    internal string Folder { get; } = folder;
}

/// <summary>Downloads the release, unpacks it beside the target and only then replaces what was there.</summary>
internal sealed class Installation(ReleaseManifest manifest, InstallPaths paths, PartFetcher fetcher, int moveAttempts = 5)
{
    private static readonly TimeSpan MoveRetry = TimeSpan.FromSeconds(2);
    private bool swapping;
    private bool replaced;

    internal long RequiredBytes => manifest.InstalledBytes + manifest.Archives.Sum(archive => archive.Bytes);

    /// <summary>A retry reuses the parts already downloaded and replaces the half-unpacked folder.</summary>
    internal long StillNeededBytes
    {
        get
        {
            long downloaded = manifest.Archives.SelectMany(archive => archive.Parts).Sum(part =>
            {
                FileInfo file = new(Path.Combine(paths.Downloads, part.File));
                return file.Exists ? Math.Min(file.Length, part.Bytes) : 0;
            });
            return Math.Max(0, RequiredBytes - downloaded - StagedBytes());
        }
    }

    /// <summary>The window waits for this before closing: a process ended here would leave BAXY only in Previous.</summary>
    internal bool IsSwapping => Volatile.Read(ref swapping);

    /// <summary>UPD1: the new BAXY is in place (the clean-up after it may still run).</summary>
    internal bool HasReplaced => Volatile.Read(ref replaced);

    private long StagedBytes()
    {
        try
        {
            return Directory.Exists(paths.Staging)
                ? new DirectoryInfo(paths.Staging).EnumerateFiles("*", SearchOption.AllDirectories).Sum(file => file.Length)
                : 0;
        }
        catch (Exception unreadable) when (unreadable is IOException or UnauthorizedAccessException)
        {
            Program.Log(unreadable.ToString());
            return 0;
        }
    }

    internal async Task RunAsync(Action<InstallPhase, long, long> progress, CancellationToken cancellation)
    {
        paths.RefuseWhatIsNotBaxys();
        BringBackAnInterruptedSwap();
        cancellation.ThrowIfCancellationRequested();
        RemoveIfPresent(paths.Staging);
        InstallPaths.MarkAsBaxys(paths.Downloads);
        IReadOnlyList<ReleaseArchive> archives = manifest.Archives;
        long total = archives.Sum(archive => archive.Bytes);
        long done = 0;
        Dictionary<ReleaseArchive, List<string>> downloaded = [];
        foreach (ReleaseArchive archive in archives)
        {
            List<string> files = [];
            foreach (ReleasePart part in archive.Parts)
            {
                files.Add(await fetcher.FetchAsync(
                    manifest.BaseUrl,
                    part,
                    paths.Downloads,
                    moved => progress(InstallPhase.Downloading, Interlocked.Add(ref done, moved), total),
                    cancellation).ConfigureAwait(false));
            }

            downloaded[archive] = files;
        }

        RemoveIfPresent(paths.Staging);
        InstallPaths.MarkAsBaxys(paths.Staging);
        long unpacked = 0;
        foreach (ReleaseArchive archive in archives)
        {
            using ConcatenatedStream stream = new(downloaded[archive]);
            using ZipArchive zip = new(stream, ZipArchiveMode.Read);
            foreach (ZipArchiveEntry entry in zip.Entries)
            {
                cancellation.ThrowIfCancellationRequested();
                await UnpackAsync(entry, paths.Staging, cancellation).ConfigureAwait(false);
                unpacked += entry.Length;
                progress(InstallPhase.Unpacking, unpacked, Math.Max(manifest.InstalledBytes, unpacked));
            }
        }

        if (!File.Exists(Path.Combine(paths.Staging, "app", "Baxy.exe")))
        {
            throw new InvalidDataException("the release does not contain app\\Baxy.exe");
        }

        Volatile.Write(ref swapping, true);
        try
        {
            Replace();
            Volatile.Write(ref replaced, true);
        }
        finally
        {
            Volatile.Write(ref swapping, false);
        }

        CleanUp(paths.Previous);
        CleanUp(paths.Downloads);
    }

    private static async Task UnpackAsync(ZipArchiveEntry entry, string root, CancellationToken cancellation)
    {
        string target = Path.GetFullPath(Path.Combine(root, entry.FullName));
        if (!target.StartsWith(Path.GetFullPath(root) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException($"{entry.FullName} is outside the installation");
        }

        if (entry.FullName.EndsWith('/'))
        {
            Directory.CreateDirectory(target);
            return;
        }

        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        using Stream source = entry.Open();
        await using FileStream file = new(target, FileMode.Create, FileAccess.Write, FileShare.None, 1 << 20, useAsync: true);
        await source.CopyToAsync(file, 1 << 20, cancellation).ConfigureAwait(false);
    }

    private void Replace()
    {
        try
        {
            RemoveIfPresent(paths.Previous);
            if (Directory.Exists(paths.Root))
            {
                MoveAllowingAScan(paths.Root, paths.Previous);
            }

            Directory.CreateDirectory(Path.GetDirectoryName(paths.Root)!);
            MoveAllowingAScan(paths.Staging, paths.Root);
        }
        catch (Exception failure) when (failure is IOException or UnauthorizedAccessException)
        {
            // BAXY is running from the old folder, or the swap stopped halfway: put back what was there. If even that
            // fails, the copy stays in Previous and the next run brings it back first.
            try
            {
                BringBackAnInterruptedSwap();
            }
            catch (Exception stuck) when (stuck is IOException or UnauthorizedAccessException)
            {
                Program.Log(stuck.ToString());
            }

            throw new InstallBlockedException(failure.Message, failure);
        }
    }

    private void BringBackAnInterruptedSwap()
    {
        if (!Directory.Exists(paths.Root) && Directory.Exists(paths.Previous))
        {
            Directory.Move(paths.Previous, paths.Root);
        }
    }

    /// <summary>An antivirus reading what was just unpacked holds the folder for a moment.</summary>
    private void MoveAllowingAScan(string source, string destination)
    {
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                Directory.Move(source, destination);
                return;
            }
            catch (Exception held) when (attempt < moveAttempts && held is IOException or UnauthorizedAccessException)
            {
                Thread.Sleep(MoveRetry);
            }
        }
    }

    /// <summary>The installation is already in place: what cannot be cleaned now does not undo it.</summary>
    private static void CleanUp(string directory)
    {
        try
        {
            RemoveIfPresent(directory);
        }
        catch (Exception left) when (left is IOException or UnauthorizedAccessException)
        {
            Program.Log(left.ToString());
        }
    }

    private static void RemoveIfPresent(string directory)
    {
        if (Directory.Exists(directory))
        {
            InstallPaths.DeleteTree(directory);
        }
    }
}
