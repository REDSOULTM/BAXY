namespace Baxy.Providers.Windows.Applications;

public static class ApplicationIds
{
    public static bool IsValidRequest(string id)
    {
        if (string.IsNullOrWhiteSpace(id) || id.Length > 256)
        {
            return false;
        }

        foreach (char character in id)
        {
            if (char.IsControl(character)
                || character == '\uFFFD'
                || character is '\\' or '/' or ':' or ';' or '|' or '&' or '>' or '<' or '$')
            {
                return false;
            }
        }

        return true;
    }
}

public static class ApplicationOpenErrorCodes
{
    public const string InvalidApplication = "invalid_application";
    public const string ApplicationNotFound = "app_not_found";
    public const string ApplicationAmbiguous = "app_ambiguous";
    public const string InventoryFailed = "inventory_failed";
    public const string LaunchFailed = "launch_failed";
    // cu-v3-abrir-archivo: Windows does not list the application among the handlers («Abrir con») of that type of file.
    public const string FileNotAccepted = "app_file_not_accepted";
    // cu-v3-archivo-empaquetado: Windows lists the application for that type of file and the shell did not hand it the
    // file (its handler refused the invocation, or the file could not be made into what the shell hands).
    public const string FileActivationFailed = "app_file_activation_failed";
    public const string VerificationFailed = "verification_failed";
    // cu-v3-documento-nuevo: the person asked for a new document and the application's New command (Ctrl+N, sent only
    // to its window in front) showed no new window nor a new document in it; nothing is written anywhere.
    public const string NewDocumentNotCreated = "new_document_not_created";
    // Auditoría final V1: Windows gives the application no identity its windows can be told by (no package, no
    // executable behind its shortcut); nothing is launched nor said about its windows.
    public const string WindowIdentityUnavailable = "application_window_identity_unavailable";
}

// Foreground: the person asked for the application in front (or opened it outside a computer-use mission). Without
// it the application opens behind the person's window and is never handed the front (v3 point 0, arreglo 4).
// ForControl: the application is opened so that BAXY can read and press its window (v3 r5a M5): a program Windows would
// raise to administrator unasked is started with the person's own rights, and a raised window of it whose program opens
// again with those rights is not reused. cu-v3-elevacion: every opening carries it unless the person asked for
// administrator rights, which keeps the shell's path and the rights Windows gives it.
// FilePath (cu-v3-abrir-archivo): the full path of a file the application opens (file.open with an application): the
// shell hands it the file (package activation for files, or its executable with the path as argument), never a window
// of it that already runs, and never keys.
// NewDocument (cu-v3-documento-nuevo, uso real t4-c14 «pegame lo que copie en un bloc de notas nuevo» pasted into the
// person's note): the person asked for a new document. Auditoría D6: a new instance of the application is launched,
// never a window it already had, and the New command of that new window makes the document; the result is the new
// window (or that window showing the new document), never a window of the person's.
public record ApplicationOpenRequest(
    string ApplicationId,
    string InvocationId,
    bool Foreground = false,
    bool ForControl = false,
    string? FilePath = null,
    bool NewDocument = false);

public record ApplicationLaunchReceipt(
    string InvocationId,
    string ApplicationId,
    bool LaunchIssued,
    bool ReusedExisting,
    int? ProcessId,
    long? ProcessCreationTimeUtcTicks,
    string? ExecutablePath,
    string? PackageFamilyName,
    string? PackageFullName,
    long? WindowHandle,
    string? ErrorCode);

public record ApplicationOpenResult(
    bool Succeeded,
    bool Verified,
    string DisplayName,
    bool AlreadyRunning,
    int? ProcessId,
    long? WindowHandle,
    string? ErrorCode,
    ApplicationLaunchReceipt Receipt,
    bool WindowsActivation = false,
    // cu-v3-foco-segunda: the hand-back of a WindowsActivation was read back as held.
    bool FrontRestored = false,
    // cu-v3-documento-nuevo: the window is a new document the opening made and saw (ApplicationOpenRequest.NewDocument).
    bool NewDocument = false,
    // r20b palanca 4: asked in front while the person worked in another window, the window was raised above it without
    // the activation, and their keyboard stayed where it was.
    bool ShownWithoutFocus = false,
    // Auditoría D1: no installed application is called so; the closest installed names, none of them opened.
    IReadOnlyList<string>? Candidates = null);

public interface IApplicationOpenProvider
{
    ValueTask<ApplicationOpenResult> OpenAsync(
        ApplicationOpenRequest request,
        CancellationToken cancellationToken);

    /// <summary>
    /// Renew al máximo (guarda msconfig): read only, nothing launched. Whether the application this name resolves to is
    /// a tool that configures Windows itself, by the same rule no click acts on such a tool; false when it resolves to
    /// none or the provider cannot tell (the opening then fails or runs as always).
    /// </summary>
    ValueTask<bool> OpensSystemToolAsync(string applicationId, CancellationToken cancellationToken) =>
        ValueTask.FromResult(false);
}

// Candidates: not installed under that name, the installed names closest to it, as app.open says them (auditoría D1).
public sealed record ApplicationInstalledResult(
    string RequestedName,
    string? DisplayName,
    bool Installed,
    bool Verified,
    string? ErrorCode,
    string? InstalledVersion = null,
    IReadOnlyList<string>? Candidates = null);

public sealed record ApplicationWindowStatusResult(
    string RequestedName,
    string? DisplayName,
    bool Installed,
    bool HasVisibleWindow,
    int VisibleWindowCount,
    bool Verified,
    string? ErrorCode);

public interface IApplicationInventoryProvider
{
    ValueTask<ApplicationInstalledResult> IsInstalledAsync(
        string applicationName,
        CancellationToken cancellationToken);

    ValueTask<ApplicationWindowStatusResult> GetWindowStatusAsync(
        string applicationName,
        CancellationToken cancellationToken);
}

public sealed record InstalledApplicationCatalogSnapshot(
    bool Verified,
    bool Complete,
    IReadOnlyList<string> Names);

public interface IApplicationCatalogProvider
{
    ValueTask<InstalledApplicationCatalogSnapshot> GetCatalogSnapshotAsync(
        CancellationToken cancellationToken);
}
