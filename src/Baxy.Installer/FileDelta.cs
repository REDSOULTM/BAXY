using System.IO.Compression;
using System.Net;
using System.Net.Http.Headers;
using System.Runtime.InteropServices;
using System.Security.Cryptography;

namespace Baxy.Installer;

/// <summary>What an installation over a BAXY already there takes of one archive: the files to download alone, and those
/// the folder already has with the release's size and SHA-256.</summary>
internal sealed record ArchivePlan(ReleaseArchive Archive, IReadOnlyList<ReleaseFile> Kept, IReadOnlyList<ReleaseFile> Needed)
{
    /// <summary>What is downloaded of the archive: each needed file once, as it is in the zip.</summary>
    internal long NeededBytes => Needed.DistinctBy(static file => file.Sha256).Sum(static file => file.Packed);
}

/// <summary>The server answered a Range request with the whole file, or with another range: the parts are taken whole.</summary>
internal sealed class RangeRefusedException(string message) : Exception(message);

/// <summary>
/// AUT1 (orden del dueño, 13-11-2026): an update downloads only what differs. The installed files are compared with
/// files.json by size and SHA-256 (a model of several GB that did not change is read, never downloaded), the way Steam's
/// clients take «only the new or modified portions» (partner.steamgames.com/doc/sdk/uploading) and Squirrel picks deltas
/// or the full package «by calculating which one requires less total downloading» (Squirrel.Windows, docs/using/
/// update-process.md); both read 2026-11-13. Measured on the packages of 1.5.1 and 1.5.2: 15 of 4,935 files differ, 94.0 MB
/// in the zips of 5,211.8 MB.
/// </summary>
internal static partial class FileDelta
{
    private const int Readers = 4;

    /// <summary>
    /// The archives of <paramref name="manifest"/> that are taken file by file, each with its plan. One is taken whole (and
    /// is not here) when the folder holds no BAXY, when files.json does not list it, or when what differs is more than half
    /// of it: then the parts, whole and resumable, are less work than their files one by one.
    /// </summary>
    internal static async Task<Dictionary<ReleaseArchive, ArchivePlan>> PlanAsync(
        ReleaseManifest manifest, FileManifest? files, InstallPaths paths, CancellationToken cancellation)
    {
        Dictionary<ReleaseArchive, ArchivePlan> plans = [];
        if (files is null || !paths.HoldsBaxy)
        {
            return plans;
        }

        HashSet<string> seen = new(StringComparer.OrdinalIgnoreCase);
        foreach (ReleaseArchive archive in manifest.Archives)
        {
            // A path two archives carry (the licenses of the NVIDIA part) lands on the same bytes: the first one counts.
            ReleaseFile[] listed = [.. files.Files.Where(file => file.Archive == archive.Name && seen.Add(file.Path))];
            // A file said to lie beyond the archive's bytes: files.json is not this archive's, and it is taken whole.
            if (listed.Length == 0 || listed.Any(file => file.Offset + file.Packed > archive.Bytes))
            {
                continue;
            }

            bool[] installed = new bool[listed.Length];
            await Parallel.ForEachAsync(
                Enumerable.Range(0, listed.Length),
                new ParallelOptions { MaxDegreeOfParallelism = Readers, CancellationToken = cancellation },
                async (index, stop) => installed[index] = await IsInstalledAsync(paths.Root, listed[index], stop).ConfigureAwait(false))
                .ConfigureAwait(false);
            ArchivePlan plan = new(
                archive,
                [.. listed.Where((_, index) => installed[index])],
                [.. listed.Where((_, index) => !installed[index])]);
            if (plan.NeededBytes <= archive.Bytes / 2)
            {
                plans[archive] = plan;
            }
        }

        return plans;
    }

    /// <summary>
    /// Where <paramref name="file"/> goes under <paramref name="root"/>. Its path was checked when files.json was read;
    /// what Windows makes of it is checked here too, as each zip entry's is (Installation.UnpackAsync), so that nothing
    /// is ever placed outside the folder, whoever built the manifest.
    /// </summary>
    internal static string InRoot(string root, ReleaseFile file)
    {
        string inside = Path.GetFullPath(root) + Path.DirectorySeparatorChar;
        string full = Path.GetFullPath(Path.Combine(root, file.Path.Replace('/', Path.DirectorySeparatorChar)));
        return full.StartsWith(inside, StringComparison.OrdinalIgnoreCase)
            ? full
            : throw new InvalidDataException($"{file.Path} is outside the installation");
    }

    /// <summary>
    /// <paramref name="source"/> also under the name <paramref name="target"/>, without a second copy on disk: a hard link
    /// («all hard links to a file must be on the same volume», and only on NTFS: Microsoft Learn, CreateHardLinkW, read
    /// 2026-11-13), else a copy. A linked file is never written again: the old folder still names the same bytes.
    /// </summary>
    internal static void Place(string source, string target)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        if (!File.Exists(target) && !CreateHardLinkW(target, source, 0))
        {
            File.Copy(source, target);
        }
    }

    private static Task<bool> IsInstalledAsync(string root, ReleaseFile file, CancellationToken cancellation) =>
        IsAsync(InRoot(root, file), file, cancellation);

    /// <summary>Whether what is at <paramref name="path"/> is <paramref name="file"/>, by its size and SHA-256.</summary>
    internal static async Task<bool> IsAsync(string path, ReleaseFile file, CancellationToken cancellation)
    {
        try
        {
            FileInfo found = new(path);
            if (!found.Exists || found.Length != file.Bytes)
            {
                return false;
            }

            await using FileStream content = new(path, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20, useAsync: true);
            return Convert.ToHexStringLower(await SHA256.HashDataAsync(content, cancellation).ConfigureAwait(false)) == file.Sha256;
        }
        catch (Exception unreadable) when (unreadable is IOException or UnauthorizedAccessException)
        {
            // What cannot be read is downloaded.
            return false;
        }
    }

    [LibraryImport("kernel32.dll", StringMarshalling = StringMarshalling.Utf16, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool CreateHardLinkW(string link, string existing, nint security);
}

/// <summary>
/// Downloads files of the release one by one, each from its own bytes of the parts with a Range request («a client can
/// alter the semantics of GET to be a range request», answered 206 Partial Content: RFC 9110 §14.2 and §15.3.7), and
/// keeps each only with the size and SHA-256 of files.json, under that hash as its name. Neighbours in the zip come in
/// one request. What a cut connection left is not downloaded again: the files already kept stay, and the one that was
/// arriving goes on from its last byte. GitHub's release assets answer ranges (measured 2026-11-13: 206 with Content-Range
/// from release-assets.githubusercontent.com); a server that does not is told apart (<see cref="RangeRefusedException"/>)
/// and the parts are then taken whole.
/// </summary>
/// <param name="gap">Files this near in the zip come in one request: reading past what lies between them costs less
/// than asking again (a request to a release asset is two, with its redirection).</param>
/// <param name="gate">The window's «Pause»: while it is closed nothing more is downloaded, as with the parts (PartFetcher).</param>
internal sealed class RangeFetcher(
    HttpClient http, TimeSpan? stallLimit = null, TimeSpan? retryDelay = null, long gap = 256 << 10, Func<PauseGate>? gate = null)
{
    /// <summary>The folder, inside the installation's downloads, where the files are kept until they are placed.</summary>
    internal const string StoreName = "files";

    private const int AttemptsWithoutProgress = 8;
    private const int DamagedAttempts = 3;

    private static readonly TimeSpan LongestWait = TimeSpan.FromSeconds(60);
    private readonly TimeSpan stallLimit = stallLimit ?? PartFetcher.StallLimit;
    private readonly TimeSpan retryDelay = retryDelay ?? TimeSpan.FromSeconds(3);
    private long received;

    /// <summary>Every byte the server sent for these files: theirs, and what lies between neighbours asked together.</summary>
    internal long ReceivedBytes => Interlocked.Read(ref received);

    /// <summary>Where a file with that SHA-256 is kept in <paramref name="store"/> once it is whole and checked.</summary>
    internal static string Kept(string store, ReleaseFile file) => Path.Combine(store, file.Sha256);

    /// <param name="moved">Called with each change in the bytes of these files here (negative when one starts over).</param>
    internal async Task FetchAsync(
        string baseUrl,
        ReleaseArchive archive,
        IReadOnlyList<ReleaseFile> needed,
        string store,
        Action<long> moved,
        CancellationToken cancellation)
    {
        Directory.CreateDirectory(store);
        ReleaseFile[] wanted = [.. needed.DistinctBy(static file => file.Sha256).OrderBy(static file => file.Offset)];
        // What an earlier try left of each file, whole or in part, is here already.
        moved(wanted.Sum(file => File.Exists(Kept(store, file)) ? file.Packed : Resumed(store, file)));
        int attempt = 1;
        int damaged = 0;
        while (true)
        {
            long arrived = 0;
            void Moved(long bytes)
            {
                arrived += Math.Max(bytes, 0);
                moved(bytes);
            }

            try
            {
                ReleaseFile[] missing = [.. wanted.Where(file => !File.Exists(Kept(store, file)))];
                if (missing.Length == 0)
                {
                    return;
                }

                foreach (List<ReleaseFile> run in Runs(missing, store))
                {
                    await FetchRunAsync(baseUrl, archive, run, store, Moved, cancellation).ConfigureAwait(false);
                }
            }
            catch (Exception failure) when (
                !cancellation.IsCancellationRequested &&
                !IsFinal(failure) &&
                failure is HttpRequestException or IOException or InvalidDataException or OperationCanceledException)
            {
                attempt = arrived > 0 && failure is not InvalidDataException ? 1 : attempt + 1;
                if (failure is InvalidDataException ? ++damaged >= DamagedAttempts : attempt > AttemptsWithoutProgress)
                {
                    throw;
                }

                TimeSpan wait = retryDelay * Math.Pow(2, attempt - 1);
                await Task.Delay(wait < LongestWait ? wait : LongestWait, cancellation).ConfigureAwait(false);
            }
        }
    }

    private static bool IsFinal(Exception failure) =>
        Failures.IsDiskFull(failure) || failure is HttpRequestException { StatusCode: { } status } && Failures.IsRefusal(status);

    private static string Partial(string store, ReleaseFile file) => Kept(store, file) + ".part";

    // The bytes of a file, as they are in the zip, that an earlier try left here: the download goes on after them.
    private static long Resumed(string store, ReleaseFile file)
    {
        FileInfo partial = new(Partial(store, file));
        if (partial.Exists && partial.Length > file.Packed)
        {
            partial.Delete();
            return 0;
        }

        return partial.Exists ? partial.Length : 0;
    }

    // A file that goes on from the bytes it has here begins a request of its own, at its next byte.
    private IEnumerable<List<ReleaseFile>> Runs(IReadOnlyList<ReleaseFile> missing, string store)
    {
        List<ReleaseFile> run = [];
        foreach (ReleaseFile file in missing)
        {
            if (run.Count > 0 && (file.Offset - (run[^1].Offset + run[^1].Packed) > gap || Resumed(store, file) > 0))
            {
                yield return run;
                run = [];
            }

            run.Add(file);
        }

        if (run.Count > 0)
        {
            yield return run;
        }
    }

    private async Task FetchRunAsync(
        string baseUrl, ReleaseArchive archive, List<ReleaseFile> run, string store, Action<long> moved, CancellationToken cancellation)
    {
        long from = run[0].Offset + Resumed(store, run[0]);
        await using ArchiveRange source = new(
            http, baseUrl, archive, from, run[^1].Offset + run[^1].Packed, stallLimit, read => Interlocked.Add(ref received, read), cancellation);
        byte[] buffer = new byte[1 << 20];
        long at = from;
        foreach (ReleaseFile file in run)
        {
            long resumed = at > file.Offset ? at - file.Offset : 0;
            for (long skip = file.Offset + resumed - at; skip > 0;)
            {
                int read = await source.ReadAsync(buffer.AsMemory(0, (int)Math.Min(buffer.Length, skip)), cancellation).ConfigureAwait(false);
                skip -= read > 0 ? read : throw new HttpRequestException($"{archive.Name}: ended before {file.Path}");
            }

            await PackedAsync(source, file, store, resumed, buffer, moved, cancellation).ConfigureAwait(false);
            at = file.Offset + file.Packed;
            try
            {
                await FinishAsync(file, store, buffer, cancellation).ConfigureAwait(false);
            }
            catch (InvalidDataException)
            {
                // Nothing of it stays: what was counted of it is taken back.
                moved(-file.Packed);
                throw;
            }
        }
    }

    // The file's bytes as they are in the zip, after the ones already here, into its «.part»: a cut leaves them there.
    private async Task PackedAsync(
        Stream source, ReleaseFile file, string store, long resumed, byte[] buffer, Action<long> tell, CancellationToken cancellation)
    {
        await using FileStream target = new(
            Partial(store, file), resumed > 0 ? FileMode.Append : FileMode.Create, FileAccess.Write, FileShare.None, 1 << 16, useAsync: true);
        for (long left = file.Packed - resumed; left > 0;)
        {
            if (gate is not null)
            {
                await gate().WaitAsync(cancellation).ConfigureAwait(false);
            }

            int read = await source.ReadAsync(buffer.AsMemory(0, (int)Math.Min(buffer.Length, left)), cancellation).ConfigureAwait(false);
            if (read == 0)
            {
                throw new HttpRequestException($"{file.Path}: the download ended early");
            }

            await target.WriteAsync(buffer.AsMemory(0, read), cancellation).ConfigureAwait(false);
            left -= read;
            tell(read);
        }
    }

    // Every byte of the file is here: it is unpacked if the zip deflated it, and kept, under its hash, only when it has
    // the size and SHA-256 of files.json. One that has not is deleted whole, and never more of it is unpacked than the
    // release says it has, whatever the bytes unpack to.
    private static async Task FinishAsync(ReleaseFile file, string store, byte[] buffer, CancellationToken cancellation)
    {
        string partial = Partial(store, file);
        string unpacking = Kept(store, file) + ".tmp";
        try
        {
            using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            long written = 0;
            await using (FileStream packed = new(partial, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20, useAsync: true))
            {
                await using FileStream? target = file.Method == ReleaseFile.Stored
                    ? null
                    : new FileStream(unpacking, FileMode.Create, FileAccess.Write, FileShare.None, 1 << 16, useAsync: true);
                await using Stream content = target is null ? packed : new DeflateStream(packed, CompressionMode.Decompress, leaveOpen: true);
                for (int read; (read = await content.ReadAsync(buffer, cancellation).ConfigureAwait(false)) > 0;)
                {
                    written += read;
                    if (written > file.Bytes)
                    {
                        throw new InvalidDataException($"{file.Path} is longer than the release says");
                    }

                    hash.AppendData(buffer, 0, read);
                    if (target is not null)
                    {
                        await target.WriteAsync(buffer.AsMemory(0, read), cancellation).ConfigureAwait(false);
                    }
                }
            }

            if (written != file.Bytes || Convert.ToHexStringLower(hash.GetHashAndReset()) != file.Sha256)
            {
                throw new InvalidDataException($"{file.Path} does not have the expected hash");
            }

            if (file.Method == ReleaseFile.Stored)
            {
                File.Move(partial, Kept(store, file), overwrite: true);
            }
            else
            {
                File.Move(unpacking, Kept(store, file), overwrite: true);
                File.Delete(partial);
            }
        }
        catch (InvalidDataException)
        {
            File.Delete(unpacking);
            File.Delete(partial);
            throw;
        }
        catch
        {
            // The disk filled up, the update was cancelled: the bytes downloaded stay for the next try.
            File.Delete(unpacking);
            throw;
        }
    }

    /// <summary>
    /// The bytes [from, to) of an archive, taken as the one zip its parts make, read in order: one Range request to each
    /// part they fall in. Each answer must be 206 for the range asked (RFC 9110 §15.3.7), or 200 when a whole part was.
    /// </summary>
    private sealed class ArchiveRange(
        HttpClient http,
        string baseUrl,
        ReleaseArchive archive,
        long from,
        long to,
        TimeSpan stallLimit,
        Action<int> received,
        CancellationToken cancellation)
        : Stream
    {
        private long position = from;
        private long segmentLeft;
        private HttpResponseMessage? response;
        private Stream? body;

        public override bool CanRead => true;

        public override bool CanSeek => false;

        public override bool CanWrite => false;

        public override long Length => throw new NotSupportedException();

        public override long Position
        {
            get => throw new NotSupportedException();
            set => throw new NotSupportedException();
        }

        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            if (position >= to || buffer.Length == 0)
            {
                return 0;
            }

            if (body is null)
            {
                await OpenAsync().ConfigureAwait(false);
            }

            using CancellationTokenSource stalled = CancellationTokenSource.CreateLinkedTokenSource(cancellation, cancellationToken);
            stalled.CancelAfter(stallLimit);
            int read;
            try
            {
                read = await body!.ReadAsync(buffer[..(int)Math.Min(buffer.Length, segmentLeft)], stalled.Token).ConfigureAwait(false);
            }
            catch (IOException dropped)
            {
                throw new HttpRequestException(dropped.Message, dropped);
            }

            if (read == 0)
            {
                throw new HttpRequestException($"{archive.Name}: the download ended early");
            }

            received(read);
            position += read;
            segmentLeft -= read;
            if (segmentLeft == 0)
            {
                Close(ref response, ref body);
            }

            return read;
        }

        public override Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken) =>
            ReadAsync(buffer.AsMemory(offset, count), cancellationToken).AsTask();

        private async Task OpenAsync()
        {
            long start = 0;
            ReleasePart part = archive.Parts[0];
            foreach (ReleasePart next in archive.Parts)
            {
                part = next;
                if (position < start + next.Bytes)
                {
                    break;
                }

                start += next.Bytes;
            }

            long first = position - start;
            long last = Math.Min(to - start, part.Bytes) - 1;
            if (first < 0 || first >= part.Bytes || last < first)
            {
                throw new InvalidDataException($"{archive.Name} has no byte {position}");
            }

            using HttpRequestMessage request = new(HttpMethod.Get, baseUrl + part.File);
            request.Headers.Range = new RangeHeaderValue(first, last);
            using CancellationTokenSource answering = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            answering.CancelAfter(stallLimit);
            HttpResponseMessage answer = await http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, answering.Token)
                .ConfigureAwait(false);
            try
            {
                bool whole = first == 0 && last == part.Bytes - 1;
                if (answer.StatusCode == HttpStatusCode.PartialContent
                    ? answer.Content.Headers.ContentRange is not { From: { } begins } || begins != first
                    : answer.StatusCode == HttpStatusCode.OK && !whole)
                {
                    throw new RangeRefusedException($"{baseUrl}{part.File} did not answer the range {first}-{last}");
                }

                if (answer.StatusCode is not (HttpStatusCode.PartialContent or HttpStatusCode.OK))
                {
                    throw new HttpRequestException($"{baseUrl}{part.File}: {(int)answer.StatusCode}", null, answer.StatusCode);
                }

                body = await answer.Content.ReadAsStreamAsync(cancellation).ConfigureAwait(false);
                response = answer;
                segmentLeft = last - first + 1;
            }
            catch
            {
                answer.Dispose();
                throw;
            }
        }

        private static void Close(ref HttpResponseMessage? response, ref Stream? body)
        {
            body?.Dispose();
            response?.Dispose();
            body = null;
            response = null;
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                Close(ref response, ref body);
            }

            base.Dispose(disposing);
        }

        public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();

        public override void Flush()
        {
        }

        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();

        public override void SetLength(long value) => throw new NotSupportedException();

        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }
}
