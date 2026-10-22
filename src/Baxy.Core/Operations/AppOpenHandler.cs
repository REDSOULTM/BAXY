using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.Windows;

namespace Baxy.Core.Operations;

internal sealed class AppOpenHandler(
    IApplicationOpenProvider provider,
    LaunchProvenance? provenance = null,
    IApplicationPlaceOpener? places = null,
    Func<nint, string?>? windowIdFor = null,
    Func<long, OpenedWindowFront>? frontOf = null,
    IGameTitles? games = null,
    Func<long, string, CancellationToken, long>? settle = null)
    : IOperationHandler
{
    // BAXY Renew cu (C03 en frío): how long an application started behind its sign-in may take to show its window.
    internal static readonly TimeSpan SignInBudget = TimeSpan.FromSeconds(30);
    private readonly Func<long, string, CancellationToken, long> _settle =
        settle ?? ((window, name, token) => ApplicationWindowSettle.WaitSettled(window, name, SignInBudget, token));
    private readonly IApplicationOpenProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));
    private readonly LaunchProvenance _provenance = provenance ?? LaunchProvenance.Shared;
    private readonly IApplicationPlaceOpener _places = places ?? new ShellApplicationPlaceOpener();
    private readonly Func<long, OpenedWindowFront> _frontOf = frontOf ?? OpenedWindowFront.Read;
    private readonly IGameTitles _games = games ?? new CatalogGameTitles();

    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("app.open");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        OpenApplicationArguments arguments;
        try
        {
            arguments = JsonSerializer.Deserialize(
                invocation.Arguments,
                CoreJsonContext.Default.OpenApplicationArguments)
                ?? throw new JsonException("Arguments cannot be null.");
        }
        catch (JsonException)
        {
            return OperationOutcome.Failure("invalid_arguments");
        }

        if (!ApplicationIds.IsValidRequest(arguments.AppId))
        {
            return OperationOutcome.Failure("invalid_application");
        }

        // Estabilización, encargo C: a place is opened only by the address its application's data declare
        // (ApplicationPlaces); a place, a value or an application the data do not declare opens nothing.
        string? placeAddress = null;
        string? placeValue = arguments.PlaceValue;
        GameTitle? game = null;
        // BAXY Renew cu (C04): a game's page asked for by the game's title, as the person says it; its catalog turns it
        // into the number the address takes, and the game found is named back with the opening.
        if (ApplicationPlaces.GameCatalogOf(arguments.AppId, arguments.Place) is { } catalog
            && !string.IsNullOrWhiteSpace(placeValue) && !placeValue.All(char.IsAsciiDigit))
        {
            game = await _games.FindAsync(catalog, placeValue, cancellationToken).ConfigureAwait(false);
            if (game is null)
            {
                return OperationOutcome.Failure(
                    "game_title_not_found",
                    result: Facts(writer =>
                    {
                        writer.WriteString("appId", arguments.AppId);
                        writer.WriteString("place", arguments.Place);
                        writer.WriteString("title", placeValue);
                    }));
            }

            placeValue = game.Number;
        }

        if (arguments.Place is not null || placeValue is not null)
        {
            placeAddress = ApplicationPlaces.Address(arguments.AppId, arguments.Place, placeValue);
            if (placeAddress is null)
            {
                // Said with what was asked (BAXY Renew, notebook) and the applications that do have that place, so
                // the next opening can name the right one. BAXY Renew cu (C04 variant): a place the application has,
                // refused for its value (a game's name given to its library), is told apart, with what each place takes.
                // Revisión 2026-10-22 (B-APP-3): a value given with no place is a value not taken too, never a place of
                // another application.
                bool placeOfApplication = arguments.Place is null || ApplicationPlaces.PlacesOf(arguments.AppId)
                    .Any(declared => declared.Place == arguments.Place);
                string? places = ModelAids.On(ModelAids.AppPlaces) ? PlacesNext(arguments.AppId, arguments.AppId) : null;
                return OperationOutcome.Failure(
                    placeOfApplication ? "place_value_not_taken" : "place_not_of_application",
                    result: Facts(writer =>
                    {
                        writer.WriteString("appId", arguments.AppId);
                        if (arguments.Place is not null) writer.WriteString("place", arguments.Place);
                        if (placeOfApplication && arguments.PlaceValue is not null)
                            writer.WriteString("placeValue", arguments.PlaceValue);
                        // The places of its application and what each takes, as a fact whether the aids are on or off.
                        if (placeOfApplication)
                            WritePlaces(writer, arguments.AppId);
                        WriteNames(writer, "placeIn", ApplicationPlaces.ApplicationsWith(arguments.Place));
                        if (places is not null) writer.WriteString("next", places);
                    }));
            }
        }

        // v3 r22 revisión: the moment before the opening. A process created before it was not launched by this
        // opening, whatever the provider's reuse flag says (a process already running with no visible window, a
        // window that appears inside a process the person was already using), and never counts as BAXY's.
        // v3 r22 revisión 2: the person's own input into what this opening launches is watched from before it.
        _provenance.PrepareLaunch();
        long openingStartedTicks = DateTime.UtcNow.Ticks;
        ApplicationOpenResult providerResult = await _provider.OpenAsync(
            new ApplicationOpenRequest(
                arguments.AppId,
                invocation.InvocationId,
                arguments.Foreground == true,
                arguments.ForControl == true,
                NewDocument: arguments.NewDocument == true),
            cancellationToken).ConfigureAwait(false);

        if (!providerResult.Succeeded || !providerResult.Verified)
        {
            string errorCode = NormalizeErrorCode(providerResult.ErrorCode, providerResult.Verified);
            return OperationOutcome.Failure(
                errorCode,
                result: ModelAids.On(ModelAids.OpenRecovery)
                    ? Facts(writer => WriteRecovery(writer, errorCode, arguments.AppId, providerResult))
                    : Names("candidates", providerResult.Candidates),
                effectMayHaveOccurred: providerResult.Succeeded);
        }

        // cu-v3-documento-nuevo: a new document asked for is told done only when the opening saw it made.
        if (!HasConsistentSuccessEvidence(invocation, arguments, providerResult)
            || (arguments.NewDocument == true && !providerResult.NewDocument))
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }

        // v3 r22 uso real (t3-c18): a process this verified opening launched (not one already running) is noted with
        // its creation time and the window the opening verified; its window closes without asking while BAXY has
        // not written into any window (WindowsWindowControlProvider.HoldsNoDocument).
        if (!providerResult.AlreadyRunning
            && LaunchedByThisOpening(providerResult.Receipt.ProcessCreationTimeUtcTicks, openingStartedTicks))
        {
            _provenance.NoteLaunched(
                providerResult.ProcessId.GetValueOrDefault(),
                providerResult.Receipt.ProcessCreationTimeUtcTicks.GetValueOrDefault(),
                providerResult.WindowHandle.GetValueOrDefault());
        }

        // The application is open and verified; its place's address goes to the handler it registered. Only the
        // handing over is reported (placeRequested): whether the place arrived is for a look at the window to say.
        PlaceOpening? place = placeAddress is null ? null
            : _places.Open(placeAddress, arguments.Foreground == true, providerResult.WindowHandle.GetValueOrDefault());
        if (place is { Opened: false })
        {
            // Round A: the application is open and verified; what failed is handing its place over (it said
            // launch_failed, a launch that had in fact worked). Revisión 2026-10-22 (C-4): said with the application it
            // opened and the window id the window operations take, so the failure is never told as «not opened».
            return OperationOutcome.Failure(
                "place_not_opened",
                result: Facts(writer =>
                {
                    writer.WriteString("appId", arguments.AppId);
                    writer.WriteString("displayName", providerResult.DisplayName);
                    writer.WriteBoolean("opened", true);
                    if (windowIdFor?.Invoke((nint)providerResult.WindowHandle.GetValueOrDefault()) is { } windowId)
                        writer.WriteString("windowId", windowId);
                    if (arguments.Place is not null) writer.WriteString("place", arguments.Place);
                }),
                effectMayHaveOccurred: true);
        }

        // BAXY Renew cu (C03 en frío): started by this opening behind its own sign-in, the place handed during it was
        // lost (the look showed «Iniciando sesión» and then the store); once its window settles the place goes again,
        // and the receipt names that window.
        // Renew al máximo (auditoría de flujos): only a process this opening started is behind its sign-in; one already
        // running (Steam in the notification area, showing a window new to the opening) waited 30 s for nothing.
        long openedWindow = providerResult.WindowHandle.GetValueOrDefault();
        if (place is not null && !providerResult.AlreadyRunning
            && LaunchedByThisOpening(providerResult.Receipt.ProcessCreationTimeUtcTicks, openingStartedTicks)
            && ApplicationPlaces.StartsBehindSignIn(arguments.AppId)
            && _settle(openedWindow, providerResult.DisplayName, cancellationToken) is long settled and not 0)
        {
            openedWindow = settled;
            place = _places.Open(placeAddress!, arguments.Foreground == true, settled) is { Opened: true } again
                ? again with { FrontRestored = place.FrontRestored || again.FrontRestored }
                : place;
        }

        // BAXY Renew (notebook), F004: whether the window this opening verified holds the front as it answers (after
        // its place too), and the window that holds it when it does not; with the program that window is named by.
        // Read once; nothing is done about it.
        OpenedWindowFront front = _frontOf(openedWindow);
        var result = new OpenApplicationResult(
            arguments.AppId,
            providerResult.DisplayName,
            providerResult.AlreadyRunning,
            providerResult.ProcessId.GetValueOrDefault(),
            openedWindow,
            providerResult.WindowsActivation,
            (providerResult.WindowsActivation && providerResult.FrontRestored) || place?.FrontRestored == true,
            providerResult.NewDocument,
            providerResult.ShownWithoutFocus,
            PlaceRequested: place is not null,
            EffectReadBack: place is null ? null : false,
            // Renew al máximo (6.2): a window that did not change after the address is said with the aid's sentence.
            Next: place is not null && ModelAids.On(ModelAids.PlaceUnverified)
                ? $"{providerResult.DisplayName} was asked to show its {arguments.Place ?? "place"}"
                    + (game is null ? string.Empty : $" of {game.Name}")
                    + (place.WindowChanged == false
                        ? $"; its window did not change within {ShellApplicationPlaceOpener.PlaceArrival.TotalSeconds:0} s"
                        : string.Empty)
                    + "; whether it shows now "
                    + "was not checked: input_visible_controls can look before saying so"
                : place is null && ModelAids.On(ModelAids.AppPlaces) ? PlacesNext(providerResult.DisplayName, arguments.AppId)
                : null,
            FrontChanged: place?.FrontChanged == true,
            PlaceGame: game is null ? null : new PlacedGame(game.Number, game.Name),
            WindowId: windowIdFor?.Invoke((nint)openedWindow),
            ProcessName: front.Process,
            Foreground: front.Held,
            ForegroundHeldBy: front.HolderTitle is { } title ? new WindowName(title, front.HolderProcess ?? string.Empty) : null,
            PlaceWindowChanged: place?.WindowChanged);
        JsonElement serialized = JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.OpenApplicationResult);
        return OperationOutcome.Success(serialized);
    }

    // BAXY Renew cu (C04): opened with no place, an application that has places of its own says which, and what each
    // takes (the model clicked through Steam's store for a game's page that app_open opens by the game's name).
    private static string? PlacesNext(string displayName, string appId)
    {
        IReadOnlyList<(string Place, string? Takes)> places = ApplicationPlaces.PlacesOf(appId);
        return places.Count == 0 ? null
            : $"{displayName} also opens straight at a place of its own, by app_open with place: "
                + string.Join(", ", places.Select(place => place.Takes switch
                {
                    "game" => $"{place.Place} (placeValue: the game's name)",
                    "query" => $"{place.Place} (placeValue: what to search)",
                    _ => place.Place,
                }));
    }

    // Renew al máximo (6.3, aid open_recovery): a failed opening says what its provider's receipt knows (whether the
    // launch was issued, and an instance reused) and, where no window was verified after it or Windows did not take the
    // launch, which tool can look before the person is told (specific and actionable errors: Anthropic, «Writing
    // effective tools for agents»; recovery from a tool's error, Fission-GRPO, doi.org/10.48550/arXiv.2601.15625).
    // Facts only: nothing here says the application opened or not.
    private static void WriteRecovery(
        Utf8JsonWriter writer, string errorCode, string appId, ApplicationOpenResult opening)
    {
        WriteNames(writer, "candidates", opening.Candidates);
        ApplicationLaunchReceipt receipt = opening.Receipt;
        writer.WriteBoolean("launchIssued", receipt.LaunchIssued);
        if (receipt.ReusedExisting)
            writer.WriteBoolean("alreadyRunning", true);
        string name = string.IsNullOrWhiteSpace(opening.DisplayName) ? appId : opening.DisplayName;
        const string look = "window_application_status can tell whether one shows now, before saying it opened or not";
        string? next = errorCode switch
        {
            "verification_failed" or "inventory_failed" when receipt.LaunchIssued =>
                $"{name} was started and no window of it was verified; {look}",
            "verification_failed" or "inventory_failed" when receipt.ReusedExisting =>
                $"{name} was already running and no window of it was verified; {look}",
            "verification_failed" => $"no window of {name} was verified; {look}",
            "launch_failed" when !receipt.LaunchIssued =>
                $"the launch of {name} was not issued (Windows did not take it); window_application_status can tell "
                    + "whether it is open already",
            _ => null,
        };
        if (next is not null)
            writer.WriteString("next", next);
    }

    // Auditoría D1: the installed names closest to one that matched none (or the applications that have a place),
    // said with the failure (nothing was opened).
    private static JsonElement? Names(string property, IReadOnlyList<string>? names) =>
        names is { Count: > 0 } ? Facts(writer => WriteNames(writer, property, names)) : null;

    private static void WritePlaces(Utf8JsonWriter writer, string appId)
    {
        writer.WriteStartArray("places");
        foreach ((string place, string? takes) in ApplicationPlaces.PlacesOf(appId))
        {
            writer.WriteStartObject();
            writer.WriteString("place", place);
            if (takes is not null) writer.WriteString("takes", takes);
            writer.WriteEndObject();
        }
        writer.WriteEndArray();
    }

    private static void WriteNames(Utf8JsonWriter writer, string property, IReadOnlyList<string>? names)
    {
        if (names is not { Count: > 0 })
            return;
        writer.WriteStartArray(property);
        foreach (string name in names)
            writer.WriteStringValue(name);
        writer.WriteEndArray();
    }

    private static JsonElement Facts(Action<Utf8JsonWriter> write)
    {
        var buffer = new System.Buffers.ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            write(writer);
            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }

    // A process creation time is stamped by the kernel's system clock, which advances in ticks of up to 15.6 ms and
    // so may read a little behind DateTime.UtcNow (precise); a process created after the mark may carry a stamp up to
    // one clock tick earlier. Anything older was already running before the opening began.
    private static readonly long CreationClockGranularityTicks = TimeSpan.FromMilliseconds(16).Ticks;

    internal static bool LaunchedByThisOpening(long? processCreationTimeUtcTicks, long openingStartedTicks) =>
        processCreationTimeUtcTicks is long created
        && created >= openingStartedTicks - CreationClockGranularityTicks;

    private static bool HasConsistentSuccessEvidence(
        OperationInvocation invocation,
        OpenApplicationArguments arguments,
        ApplicationOpenResult result)
    {
        ApplicationLaunchReceipt? receipt = result.Receipt;
        bool hasPackageFamily = !string.IsNullOrWhiteSpace(receipt?.PackageFamilyName);
        bool hasPackageFullName = !string.IsNullOrWhiteSpace(receipt?.PackageFullName);

        return result.ErrorCode is null
            && !string.IsNullOrWhiteSpace(result.DisplayName)
            && result.DisplayName.Length <= 256
            && result.ProcessId is > 0
            && result.WindowHandle is > 0
            && receipt is not null
            && receipt.ErrorCode is null
            && string.Equals(
                receipt.InvocationId,
                invocation.InvocationId,
                StringComparison.Ordinal)
            && string.Equals(receipt.ApplicationId, arguments.AppId, StringComparison.Ordinal)
            && receipt.ProcessId == result.ProcessId
            && receipt.ProcessCreationTimeUtcTicks is > 0
            && receipt.ProcessCreationTimeUtcTicks <= DateTime.MaxValue.Ticks
            && !string.IsNullOrWhiteSpace(receipt.ExecutablePath)
            && Path.IsPathFullyQualified(receipt.ExecutablePath)
            && (receipt.WindowHandle is null || receipt.WindowHandle == result.WindowHandle)
            && receipt.LaunchIssued != receipt.ReusedExisting
            && result.AlreadyRunning == receipt.ReusedExisting
            && hasPackageFamily == hasPackageFullName;
    }

    private static string NormalizeErrorCode(string? errorCode, bool verified)
    {
        if (!verified && string.IsNullOrWhiteSpace(errorCode))
        {
            return "verification_failed";
        }

        return errorCode switch
        {
            "app_not_found" => "app_not_found",
            "app_ambiguous" => "app_ambiguous",
            "invalid_application" => "invalid_application",
            "inventory_failed" => "inventory_failed",
            "launch_failed" => "launch_failed",
            "application_window_identity_unavailable" => "application_window_identity_unavailable",
            "verification_failed" => "verification_failed",
            "new_document_not_created" => "new_document_not_created",
            _ => "application_open_failed",
        };
    }

}
