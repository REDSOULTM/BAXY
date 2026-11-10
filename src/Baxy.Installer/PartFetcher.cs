using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;

namespace Baxy.Installer;

internal sealed record ReleasePart(string File, long Bytes, string Sha256);

/// <summary>
/// Downloads one release part, resuming what a cut connection left, and keeps it only with its manifest hash. The App links
/// this file (Baxy.App.csproj) for the tuned model the person asks for (TunedModel): one pinned address into a «.part».
/// </summary>
internal sealed class PartFetcher(
    HttpClient http,
    TimeSpan? stallLimit = null,
    TimeSpan? retryDelay = null,
    Func<PauseGate>? gate = null)
{
    private const int AttemptsWithoutProgress = 8;
    private const int DamagedAttempts = 3;
    private static readonly TimeSpan LongestWait = TimeSpan.FromSeconds(60);

    /// <summary>How long a server may send nothing, an answer or more bytes, before it is given up on.</summary>
    internal static readonly TimeSpan StallLimit = TimeSpan.FromSeconds(60);

    private readonly TimeSpan stallLimit = stallLimit ?? StallLimit;
    private readonly TimeSpan retryDelay = retryDelay ?? TimeSpan.FromSeconds(3);

    /// <param name="moved">Called with each change in the bytes of this part on disk (negative when it starts over).</param>
    internal Task<string> FetchAsync(
        string baseUrl,
        ReleasePart part,
        string directory,
        Action<long> moved,
        CancellationToken cancellation) =>
        FetchAsync(baseUrl + part.File, Path.Combine(directory, part.File), part, moved, cancellation);

    /// <summary>The part at <paramref name="address"/>, downloaded into <paramref name="path"/>.</summary>
    internal async Task<string> FetchAsync(
        string address,
        string path,
        ReleasePart part,
        Action<long> moved,
        CancellationToken cancellation)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        long told = 0;
        void Tell(long onDisk)
        {
            moved(onDisk - told);
            told = onDisk;
        }

        int attempt = 1;
        int damaged = 0;
        while (true)
        {
            long before = File.Exists(path) ? new FileInfo(path).Length : 0;
            try
            {
                long onDisk = before;
                if (onDisk > part.Bytes)
                {
                    File.Delete(path);
                    onDisk = 0;
                }

                Tell(onDisk);
                if (onDisk < part.Bytes)
                {
                    await DownloadAsync(address, path, onDisk, Tell, cancellation).ConfigureAwait(false);
                }

                if (await HashAsync(path, cancellation).ConfigureAwait(false) == part.Sha256)
                {
                    return path;
                }

                File.Delete(path);
                Tell(0);
                throw new InvalidDataException($"{part.File} does not have the expected hash");
            }
            catch (Exception failure) when (
                !cancellation.IsCancellationRequested &&
                !IsFinal(failure) &&
                failure is HttpRequestException or IOException or InvalidDataException or OperationCanceledException)
            {
                bool advanced = File.Exists(path) && new FileInfo(path).Length > before;
                attempt = advanced ? 1 : attempt + 1;
                if (failure is InvalidDataException ? ++damaged >= DamagedAttempts : attempt > AttemptsWithoutProgress)
                {
                    throw;
                }

                TimeSpan wait = retryDelay * Math.Pow(2, attempt - 1);
                await Task.Delay(wait < LongestWait ? wait : LongestWait, cancellation).ConfigureAwait(false);
            }
        }
    }

    /// <summary>Waiting does not free a full disk or publish an asset the server says is not there.</summary>
    private static bool IsFinal(Exception failure) =>
        Failures.IsDiskFull(failure) || failure is HttpRequestException { StatusCode: { } status } && Failures.IsRefusal(status);

    private async Task DownloadAsync(
        string address,
        string path,
        long onDisk,
        Action<long> tell,
        CancellationToken cancellation)
    {
        using HttpRequestMessage request = new(HttpMethod.Get, address);
        if (onDisk > 0)
        {
            request.Headers.Range = new RangeHeaderValue(onDisk, null);
        }

        using CancellationTokenSource answering = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
        answering.CancelAfter(stallLimit);
        using HttpResponseMessage response = await http
            .SendAsync(request, HttpCompletionOption.ResponseHeadersRead, answering.Token)
            .ConfigureAwait(false);
        if (response.StatusCode == HttpStatusCode.OK)
        {
            onDisk = 0;
        }
        else if (response.StatusCode != HttpStatusCode.PartialContent)
        {
            throw new HttpRequestException($"{address}: {(int)response.StatusCode}", null, response.StatusCode);
        }

        await using Stream source = await response.Content.ReadAsStreamAsync(cancellation).ConfigureAwait(false);
        await using FileStream target = new(
            path,
            onDisk > 0 ? FileMode.Append : FileMode.Create,
            FileAccess.Write,
            FileShare.None,
            bufferSize: 1 << 16,
            useAsync: true);
        byte[] buffer = new byte[1 << 20];
        while (true)
        {
            if (gate is not null)
            {
                await gate().WaitAsync(cancellation).ConfigureAwait(false);
            }

            using CancellationTokenSource stalled = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            stalled.CancelAfter(stallLimit);
            int read;
            try
            {
                read = await source.ReadAsync(buffer, stalled.Token).ConfigureAwait(false);
            }
            catch (IOException dropped)
            {
                throw new HttpRequestException(dropped.Message, dropped);
            }

            if (read == 0)
            {
                return;
            }

            await target.WriteAsync(buffer.AsMemory(0, read), cancellation).ConfigureAwait(false);
            onDisk += read;
            tell(onDisk);
        }
    }

    private static async Task<string> HashAsync(string path, CancellationToken cancellation)
    {
        await using FileStream file = new(path, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20, useAsync: true);
        return Convert.ToHexStringLower(await SHA256.HashDataAsync(file, cancellation).ConfigureAwait(false));
    }
}
