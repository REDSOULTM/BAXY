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
    /// A folder given with --dir: a full path, never a drive's root, that does not exist, is empty or already holds BAXY.
    /// The swap moves whatever was there away and deletes it, so a folder of the person's own is refused.
    /// </summary>
    internal static InstallPaths Chosen(string folder)
    {
        if (!Path.IsPathFullyQualified(folder))
        {
            throw new ArgumentException($"--dir needs a full path, not «{folder}»");
        }

        string full = Path.TrimEndingDirectorySeparator(Path.GetFullPath(folder));
        if (string.Equals(full, Path.TrimEndingDirectorySeparator(Path.GetPathRoot(full)!), StringComparison.OrdinalIgnoreCase))
        {
            throw new ArgumentException($"--dir cannot be a whole drive ({full})");
        }

        InstallPaths paths = new(full);
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

    /// <summary>What an uninstall removes: the folder given, else the one «Installed apps» names, else the usual one.</summary>
    internal static InstallPaths ForUninstall(string? folder, WindowsPlaces places)
    {
        if (folder is not null)
        {
            InstallPaths chosen = Chosen(folder);
            return Directory.Exists(chosen.Root) && !chosen.HoldsBaxy
                ? throw new ArgumentException($"{chosen.Root} does not hold BAXY: nothing to uninstall there")
                : chosen;
        }

        return WindowsIntegration.RegisteredRoot(places) is { } registered && new InstallPaths(registered) is { HoldsBaxy: true } found
            ? found
            : ForThisUser;
    }
}

internal sealed class InstallBlockedException(string message, Exception inner) : IOException(message, inner);

/// <summary>Downloads the release, unpacks it beside the target and only then replaces what was there.</summary>
internal sealed class Installation(ReleaseManifest manifest, InstallPaths paths, PartFetcher fetcher, int moveAttempts = 5)
{
    private static readonly TimeSpan MoveRetry = TimeSpan.FromSeconds(2);
    private bool swapping;

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
        BringBackAnInterruptedSwap();
        cancellation.ThrowIfCancellationRequested();
        RemoveIfPresent(paths.Staging);
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
        Directory.CreateDirectory(paths.Staging);
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
            Directory.Delete(directory, recursive: true);
        }
    }
}
