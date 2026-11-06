using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Security.Cryptography.X509Certificates;
using Microsoft.Web.WebView2.Core;

namespace Baxy.App;

/// <summary>
/// The window draws in Microsoft's WebView2, and some Windows do not have it. Steam and itch.io run no installer of
/// BAXY's, so the App installs it: Microsoft's Evergreen Bootstrapper from Microsoft's address, for this person only (no
/// administrator), and it runs only with a valid Microsoft signature
/// (https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution).
/// </summary>
internal static class WebView2Runtime
{
    private const string BootstrapperAddress = "https://go.microsoft.com/fwlink/p/?LinkId=2124703";
    private const string BootstrapperName = "MicrosoftEdgeWebview2Setup.exe";
    private static readonly Guid GenericVerify = new("00AAC56B-CD44-11D0-8CC2-00C04FC295EE");

    internal static bool IsInstalled()
    {
        try
        {
            return !string.IsNullOrEmpty(CoreWebView2Environment.GetAvailableBrowserVersionString());
        }
        catch (WebView2RuntimeNotFoundException)
        {
            return false;
        }
    }

    internal static async Task InstallAsync(CancellationToken cancellation)
    {
        using HttpClient http = new();
        string directory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "BAXY",
            "webview2-setup");
        await InstallAsync(http, directory, RunAsync, IsInstalled, cancellation).ConfigureAwait(false);
    }

    /// <summary>A failure is an InvalidOperationException, the start failure the window already shows.</summary>
    internal static async Task InstallAsync(
        HttpClient http,
        string directory,
        Func<string, CancellationToken, Task<int>> run,
        Func<bool> isInstalled,
        CancellationToken cancellation)
    {
        Directory.CreateDirectory(directory);
        string path = Path.Combine(directory, BootstrapperName);
        try
        {
            await DownloadAsync(http, path, cancellation).ConfigureAwait(false);
            if (!IsSignedByMicrosoft(path))
            {
                throw new InvalidOperationException($"{BootstrapperName} does not carry a valid Microsoft signature.");
            }

            int exitCode = await run(path, cancellation).ConfigureAwait(false);
            if (!isInstalled())
            {
                throw new InvalidOperationException(
                    $"{BootstrapperName} ended with code {exitCode} and WebView2 is still not installed.");
            }
        }
        finally
        {
            File.Delete(path);
        }
    }

    private static async Task DownloadAsync(HttpClient http, string path, CancellationToken cancellation)
    {
        try
        {
            using HttpResponseMessage response = await http
                .GetAsync(BootstrapperAddress, HttpCompletionOption.ResponseHeadersRead, cancellation)
                .ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            await using FileStream file = new(path, FileMode.Create, FileAccess.Write, FileShare.None);
            await response.Content.CopyToAsync(file, cancellation).ConfigureAwait(false);
        }
        catch (HttpRequestException failure)
        {
            throw new InvalidOperationException($"{BootstrapperName} could not be downloaded: {failure.Message}", failure);
        }
    }

    private static async Task<int> RunAsync(string path, CancellationToken cancellation)
    {
        using Process process = Process.Start(new ProcessStartInfo(path, "/silent /install") { UseShellExecute = true })
            ?? throw new InvalidOperationException($"{BootstrapperName} did not start.");
        await process.WaitForExitAsync(cancellation).ConfigureAwait(false);
        return process.ExitCode;
    }

    private static bool IsSignedByMicrosoft(string path)
    {
        nint name = Marshal.StringToHGlobalUni(path);
        GCHandle file = GCHandle.Alloc(
            new FileInfoData { Size = (uint)Marshal.SizeOf<FileInfoData>(), Path = name },
            GCHandleType.Pinned);
        try
        {
            TrustData trust = new()
            {
                Size = (uint)Marshal.SizeOf<TrustData>(),
                UiChoice = 2,
                UnionChoice = 1,
                File = file.AddrOfPinnedObject(),
            };
            Guid action = GenericVerify;
            if (WinVerifyTrust(0, ref action, ref trust) != 0)
            {
                return false;
            }
        }
        finally
        {
            file.Free();
            Marshal.FreeHGlobal(name);
        }

#pragma warning disable SYSLIB0057 // The one API that reads a file's signer; WinVerifyTrust already validated the signature.
        using X509Certificate signer = X509Certificate.CreateFromSignedFile(path);
#pragma warning restore SYSLIB0057
        return signer.Subject.Contains("O=Microsoft Corporation", StringComparison.Ordinal);
    }

    [DllImport("wintrust.dll")]
    private static extern int WinVerifyTrust(nint window, ref Guid action, ref TrustData data);

    [StructLayout(LayoutKind.Sequential)]
    private struct FileInfoData
    {
        internal uint Size;
        internal nint Path;
        internal nint Handle;
        internal nint KnownSubject;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct TrustData
    {
        internal uint Size;
        internal nint PolicyCallbackData;
        internal nint SipClientData;
        internal uint UiChoice;
        internal uint RevocationChecks;
        internal uint UnionChoice;
        internal nint File;
        internal uint StateAction;
        internal nint StateData;
        internal nint UrlReference;
        internal uint ProviderFlags;
        internal uint UiContext;
        internal nint SignatureSettings;
    }
}
