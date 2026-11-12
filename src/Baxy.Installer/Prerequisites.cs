using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography.X509Certificates;
using Microsoft.Win32;

namespace Baxy.Installer;

/// <summary>
/// What Windows itself must have and BAXY's folder cannot carry: the WebView2 runtime of the interface and the Visual C++
/// runtime of llama-server. Each comes from Microsoft's own address and runs only with a valid Microsoft signature.
/// </summary>
internal static partial class Prerequisites
{
    private const string WebView2Client = @"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";
    private const string WebView2Address = "https://go.microsoft.com/fwlink/p/?LinkId=2124703";
    private const string VisualCppAddress = "https://aka.ms/vs/17/release/vc_redist.x64.exe";
    private const string VisualCppKey = @"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64";
    private const int RestartRequired = 3010;
    private const int NewerAlreadyInstalled = 1638;
    private static readonly Guid GenericVerify = new("00AAC56B-CD44-11D0-8CC2-00C04FC295EE");

    internal static bool IsMicrosoftSubject(string subject) =>
        subject.Split(", ").Contains("O=Microsoft Corporation", StringComparer.Ordinal);

    internal static bool HasWebView2()
    {
        return Version(Registry.LocalMachine, @"SOFTWARE\WOW6432Node\" + WebView2Client) ||
            Version(Registry.LocalMachine, @"SOFTWARE\" + WebView2Client) ||
            Version(Registry.CurrentUser, @"Software\" + WebView2Client);

        static bool Version(RegistryKey root, string name)
        {
            using RegistryKey? key = root.OpenSubKey(name);
            return key?.GetValue("pv") is string version && version.Length > 0 && version != "0.0.0.0";
        }
    }

    internal static bool HasVisualCpp()
    {
        using RegistryKey? key = Registry.LocalMachine.OpenSubKey(VisualCppKey);
        return key?.GetValue("Installed") is int and 1;
    }

    /// <summary>The files this downloads into BAXY's .download folder, and deletes after running them.</summary>
    internal static readonly string[] DownloadNames = [WebView2Setup, VisualCppSetup];

    private const string WebView2Setup = "webview2-setup.exe";
    private const string VisualCppSetup = "vc_redist.x64.exe";

    /// <summary>Installs what is missing. The Visual C++ runtime asks for the administrator's permission itself.</summary>
    internal static async Task InstallMissingAsync(HttpClient http, string directory, CancellationToken cancellation)
    {
        if (!HasWebView2())
        {
            await RunAsync(http, WebView2Address, directory, WebView2Setup, "/silent /install", cancellation)
                .ConfigureAwait(false);
        }

        if (!HasVisualCpp())
        {
            await RunAsync(http, VisualCppAddress, directory, VisualCppSetup, "/install /quiet /norestart", cancellation)
                .ConfigureAwait(false);
        }
    }

    private static async Task RunAsync(
        HttpClient http,
        string address,
        string directory,
        string name,
        string arguments,
        CancellationToken cancellation)
    {
        // UPD1 (REV10 M4): it is BAXY's .download folder, and a component left half downloaded must not make it look foreign.
        InstallPaths.MarkAsBaxys(directory);
        string path = Path.Combine(directory, name);
        await DownloadAsync(http, address, path, PartFetcher.StallLimit, cancellation).ConfigureAwait(false);

        if (!IsSignedByMicrosoft(path))
        {
            File.Delete(path);
            throw new InvalidDataException($"{name} does not carry a valid Microsoft signature");
        }

        Process process;
        try
        {
            process = Process.Start(new ProcessStartInfo(path, arguments)
            {
                UseShellExecute = true,
                WorkingDirectory = Environment.SystemDirectory,
            })
                ?? throw new PrerequisiteException($"{name} did not start");
        }
        catch (Win32Exception refused)
        {
            throw new PrerequisiteException($"{name} did not start: {refused.Message}", refused);
        }

        using (process)
        {
            await process.WaitForExitAsync(cancellation).ConfigureAwait(false);
            File.Delete(path);
            if (process.ExitCode is not (0 or RestartRequired or NewerAlreadyInstalled))
            {
                throw new PrerequisiteException($"{name} ended with code {process.ExitCode}");
            }
        }
    }

    /// <summary>
    /// Downloads <paramref name="address"/> to <paramref name="path"/>. The client never times out by itself (the parts
    /// are gigabytes), so the limit is on silence, as <see cref="PartFetcher"/>'s: a server that sends nothing for
    /// <paramref name="stallLimit"/>, an answer or more bytes, is given up on as a network failure the person or the
    /// script can retry, where the window and --quiet used to wait for ever (INS-6).
    /// </summary>
    internal static async Task DownloadAsync(
        HttpClient http,
        string address,
        string path,
        TimeSpan stallLimit,
        CancellationToken cancellation)
    {
        try
        {
            using CancellationTokenSource answering = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
            answering.CancelAfter(stallLimit);
            using HttpResponseMessage response = await http
                .GetAsync(address, HttpCompletionOption.ResponseHeadersRead, answering.Token)
                .ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            await using Stream source = await response.Content.ReadAsStreamAsync(cancellation).ConfigureAwait(false);
            await using FileStream file = new(path, FileMode.Create, FileAccess.Write, FileShare.None);
            byte[] buffer = new byte[1 << 16];
            while (true)
            {
                using CancellationTokenSource stalled = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
                stalled.CancelAfter(stallLimit);
                int read = await source.ReadAsync(buffer, stalled.Token).ConfigureAwait(false);
                if (read == 0)
                {
                    return;
                }

                await file.WriteAsync(buffer.AsMemory(0, read), cancellation).ConfigureAwait(false);
            }
        }
        catch (OperationCanceledException silent) when (!cancellation.IsCancellationRequested)
        {
            throw new HttpRequestException($"{address} sent nothing for {stallLimit.TotalSeconds:0.#} s", silent);
        }
    }

    private static unsafe bool IsSignedByMicrosoft(string path)
    {
        fixed (char* file = path)
        {
            FileInfoData fileInfo = new() { Size = (uint)sizeof(FileInfoData), Path = file };
            TrustData trust = new()
            {
                Size = (uint)sizeof(TrustData),
                UiChoice = 2,
                RevocationChecks = 0,
                UnionChoice = 1,
                File = &fileInfo,
                StateAction = 0,
            };
            Guid action = GenericVerify;
            if (WinVerifyTrust(0, ref action, &trust) != 0)
            {
                return false;
            }
        }

#pragma warning disable SYSLIB0057 // The one API that reads a file's signer; WinVerifyTrust already validated the signature.
        using X509Certificate signer = X509Certificate.CreateFromSignedFile(path);
#pragma warning restore SYSLIB0057
        return IsMicrosoftSubject(signer.Subject);
    }

    [LibraryImport("wintrust.dll")]
    private static unsafe partial int WinVerifyTrust(nint window, ref Guid action, TrustData* data);

    [StructLayout(LayoutKind.Sequential)]
    private unsafe struct FileInfoData
    {
        internal uint Size;
        internal char* Path;
        internal nint Handle;
        internal nint KnownSubject;
    }

    [StructLayout(LayoutKind.Sequential)]
    private unsafe struct TrustData
    {
        internal uint Size;
        internal nint PolicyCallbackData;
        internal nint SipClientData;
        internal uint UiChoice;
        internal uint RevocationChecks;
        internal uint UnionChoice;
        internal FileInfoData* File;
        internal uint StateAction;
        internal nint StateData;
        internal nint UrlReference;
        internal uint ProviderFlags;
        internal uint UiContext;
        internal nint SignatureSettings;
    }
}
