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

    // Every file Baxy.App publishes from src/Baxy.FieldUi/dist but the reviewed index.html: the built assets, whose
    // names carry the build's content hashes, and the interface's images and clips. They come from the dist when this
    // project is built (Baxy.Setup.csproj, FieldUiAssets), so the contract names the files of the build it ships and
    // never a stale list.
    private static readonly string[] FieldUiDistPaths =
        [.. FieldUiAssets.Paths.Select(static path => path.Replace('\\', '/'))];

    internal static readonly string[] DirectoryPaths = Ordinal(
    [
        .. new[]
        {
            "FieldUi",
            "FieldUiHost",
            "core",
            "runtimes",
            "runtimes/win-x64",
            "runtimes/win-x64/native",
        }.Union(FieldUiDistPaths.SelectMany(AncestorDirectories), StringComparer.Ordinal),
    ]);

    // The reviewed payload but the Field UI's dist files (FieldUiDistPaths).
    private static readonly string[] ReviewedPayloadPaths =
    [
        "Baxy.exe",
        "D3DCompiler_47_cor3.dll",
        "DesktopKeyPress.ps1",
        "DesktopSelectAll.ps1",
        "DesktopUiaWorker.ps1",
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
        "WebView2Loader.dll",
        "core/DesktopKeyPress.ps1",
        "core/DesktopSelectAll.ps1",
        "core/DesktopUiaWorker.ps1",
        "core/KnownFileOpen.ps1",
        "core/KnownFolderOpen.ps1",
        "core/SpotifyDesktopAutomation.ps1",
        "core/baxy-core.exe",
        "runtimes/win-x64/native/WebView2Loader.dll",
        "vcruntime140_cor3.dll",
        "wpfgfx_cor3.dll",
    ];

    // Each list in ordinal order, the order the build writes the manifest, the checksums and the ZIP in.
    internal static readonly string[] PayloadPaths = Ordinal([.. ReviewedPayloadPaths, .. FieldUiDistPaths]);

    internal static readonly string[] ChecksumPaths = Ordinal([.. PayloadPaths, "build-manifest.json"]);

    internal static readonly string[] ZipPaths = Ordinal([.. ChecksumPaths, "SHA256SUMS"]);

    // The trees Setup walks follow this contract, whose Field UI assets grow with the build: an installed version is
    // its directories, its ZIP files and .baxy-version.json; a staging transaction adds package.zip and the version
    // directory. The margin only bounds the walk; the exact file and directory sets are checked after it.
    private const int TreeEntryMargin = 16;

    internal static int MaximumVersionTreeEntries => DirectoryPaths.Length + ZipPaths.Length + 1 + TreeEntryMargin;

    internal static int MaximumStagingTreeEntries => MaximumVersionTreeEntries + 2;

    // A version already installed answers to its own build manifest, not to this contract: an older or newer build
    // ships other Field UI files. These bounds only cap that manifest and the walk of its tree.
    internal const int MaximumInstalledPayloadFiles = 4096;

    internal const int MaximumInstalledVersionTreeEntries = 2 * MaximumInstalledPayloadFiles;

    private static IEnumerable<string> AncestorDirectories(string path)
    {
        for (int separator = path.LastIndexOf('/'); separator > 0; separator = path.LastIndexOf('/', separator - 1))
        {
            yield return path[..separator];
        }
    }

    private static string[] Ordinal(string[] paths)
    {
        Array.Sort(paths, StringComparer.Ordinal);
        return paths;
    }
}
