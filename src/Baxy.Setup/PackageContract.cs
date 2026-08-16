namespace Baxy.Setup;

internal static class PackageContract
{
    internal const string ManifestSchema = "baxy-product-build-v4";
    internal const int DataSchema = 1;
    internal const string Product = "BAXY";
    internal const string Runtime = "win-x64";
    internal const string TargetFramework = "net10.0-windows10.0.19041.0";
    internal const string Authenticity = "not_provided";
    internal const string Configuration = "Release";
    internal const string SourceProvenance = "git_head_snapshot";
    internal const string PointerSchema = "baxy-current-v2";
    internal const string VersionAttestationSchema = "baxy-installed-version-v2";
    internal const string TransactionSchema = "baxy-install-transaction-v2";
    internal const string InstallationIdentitySchema = "baxy-installation-v1";
    internal const string WindowsIntegrationSchema = "baxy-windows-integration-v1";
    internal const string WindowsIntegrationTransactionSchema =
        "baxy-windows-integration-transaction-v1";
    internal const string EmbeddedPackageResourceName = "Baxy.Setup.Payload.zip";
    internal const string EmbeddedPackageAttestationResourceName = "Baxy.Setup.Payload.attestation.json";
    internal const string EmbeddedPackageAttestationSchema = "baxy-setup-embedded-package-v2";
    internal const string EmbeddedVerificationEvidenceSchema = "baxy-setup-embedded-verification-v2";

    internal const long MaximumPackageBytes = 256L * 1024 * 1024;
    internal const long MaximumPayloadFileBytes = 128L * 1024 * 1024;
    internal const int MaximumManifestBytes = 256 * 1024;
    internal const int MaximumChecksumBytes = 64 * 1024;
    internal const int MaximumRelativePathLength = 240;
    internal const int MaximumVersionLength = 128;
    internal const int MaximumInstallationIdentityBytes = 4096;
    internal const int MaximumWindowsIntegrationBytes = 16 * 1024;
    internal const int MaximumWindowsIntegrationTransactionBytes = 48 * 1024;

    internal static readonly string[] DirectoryPaths =
    [
        "FieldUi",
        "FieldUi/assets",
        "FieldUiHost",
        "core",
        "runtimes",
        "runtimes/win-x64",
        "runtimes/win-x64/native",
        "tools",
        "tools/mpv",
        "tools/yt-dlp",
    ];

    internal static readonly string[] PayloadPaths =
    [
        "Baxy.exe",
        "D3DCompiler_47_cor3.dll",
        "DesktopClickVisible.ps1",
        "DesktopKeyPress.ps1",
        "DesktopSelectAll.ps1",
        "FieldUi/assets/index-CjozYCnU.css",
        "FieldUi/assets/index-D3QuhrLm.js",
        "FieldUi/index.html",
        "FieldUiHost/field-native-bridge.js",
        "KnownFileOpen.ps1",
        "KnownFolderOpen.ps1",
        "Microsoft.Web.WebView2.Core.xml",
        "Microsoft.Web.WebView2.WinForms.xml",
        "Microsoft.Web.WebView2.Wpf.xml",
        "PenImc_cor3.dll",
        "PresentationNative_cor3.dll",
        "SpotifyDesktopAutomation.ps1",
        "SpotifyMediaControl.ps1",
        "WebView2Loader.dll",
        "WindowsScheduledNotification.ps1",
        "core/DesktopClickVisible.ps1",
        "core/DesktopKeyPress.ps1",
        "core/DesktopSelectAll.ps1",
        "core/KnownFileOpen.ps1",
        "core/KnownFolderOpen.ps1",
        "core/SpotifyDesktopAutomation.ps1",
        "core/SpotifyMediaControl.ps1",
        "core/WindowsScheduledNotification.ps1",
        "core/baxy-core.exe",
        "runtimes/win-x64/native/WebView2Loader.dll",
        "tools/mpv/mpv.exe",
        "tools/mpv/vulkan-1.dll",
        "tools/yt-dlp/yt-dlp.exe",
        "vcruntime140_cor3.dll",
        "wpfgfx_cor3.dll",
    ];

    internal static readonly string[] ChecksumPaths =
    [
        "Baxy.exe",
        "D3DCompiler_47_cor3.dll",
        "DesktopClickVisible.ps1",
        "DesktopKeyPress.ps1",
        "DesktopSelectAll.ps1",
        "FieldUi/assets/index-CjozYCnU.css",
        "FieldUi/assets/index-D3QuhrLm.js",
        "FieldUi/index.html",
        "FieldUiHost/field-native-bridge.js",
        "KnownFileOpen.ps1",
        "KnownFolderOpen.ps1",
        "Microsoft.Web.WebView2.Core.xml",
        "Microsoft.Web.WebView2.WinForms.xml",
        "Microsoft.Web.WebView2.Wpf.xml",
        "PenImc_cor3.dll",
        "PresentationNative_cor3.dll",
        "SpotifyDesktopAutomation.ps1",
        "SpotifyMediaControl.ps1",
        "WebView2Loader.dll",
        "WindowsScheduledNotification.ps1",
        "build-manifest.json",
        "core/DesktopClickVisible.ps1",
        "core/DesktopKeyPress.ps1",
        "core/DesktopSelectAll.ps1",
        "core/KnownFileOpen.ps1",
        "core/KnownFolderOpen.ps1",
        "core/SpotifyDesktopAutomation.ps1",
        "core/SpotifyMediaControl.ps1",
        "core/WindowsScheduledNotification.ps1",
        "core/baxy-core.exe",
        "runtimes/win-x64/native/WebView2Loader.dll",
        "tools/mpv/mpv.exe",
        "tools/mpv/vulkan-1.dll",
        "tools/yt-dlp/yt-dlp.exe",
        "vcruntime140_cor3.dll",
        "wpfgfx_cor3.dll",
    ];

    internal static readonly string[] ZipPaths =
    [
        "Baxy.exe",
        "D3DCompiler_47_cor3.dll",
        "DesktopClickVisible.ps1",
        "DesktopKeyPress.ps1",
        "DesktopSelectAll.ps1",
        "FieldUi/assets/index-CjozYCnU.css",
        "FieldUi/assets/index-D3QuhrLm.js",
        "FieldUi/index.html",
        "FieldUiHost/field-native-bridge.js",
        "KnownFileOpen.ps1",
        "KnownFolderOpen.ps1",
        "Microsoft.Web.WebView2.Core.xml",
        "Microsoft.Web.WebView2.WinForms.xml",
        "Microsoft.Web.WebView2.Wpf.xml",
        "PenImc_cor3.dll",
        "PresentationNative_cor3.dll",
        "SHA256SUMS",
        "SpotifyDesktopAutomation.ps1",
        "SpotifyMediaControl.ps1",
        "WebView2Loader.dll",
        "WindowsScheduledNotification.ps1",
        "build-manifest.json",
        "core/DesktopClickVisible.ps1",
        "core/DesktopKeyPress.ps1",
        "core/DesktopSelectAll.ps1",
        "core/KnownFileOpen.ps1",
        "core/KnownFolderOpen.ps1",
        "core/SpotifyDesktopAutomation.ps1",
        "core/SpotifyMediaControl.ps1",
        "core/WindowsScheduledNotification.ps1",
        "core/baxy-core.exe",
        "runtimes/win-x64/native/WebView2Loader.dll",
        "tools/mpv/mpv.exe",
        "tools/mpv/vulkan-1.dll",
        "tools/yt-dlp/yt-dlp.exe",
        "vcruntime140_cor3.dll",
        "wpfgfx_cor3.dll",
    ];
}
