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
    Func<long, string, CancellationToken, ValueTask<long>>? settle = null,
    TimeProvider? time = null)
    : IOperationHandler, IInvocationPreflight
{
    // BAXY Renew cu (C03 en frío): how long an application started behind its sign-in may take to show its window.
    internal static readonly TimeSpan SignInBudget = TimeSpan.FromSeconds(30);
    private readonly Func<long, string, CancellationToken, ValueTask<long>> _settle =
        settle ?? ((window, name, token) => ApplicationWindowSettle.WaitSettledAsync(window, name, SignInBudget, token));
    private readonly IApplicationOpenProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));
    private readonly LaunchProvenance _provenance = provenance ?? LaunchProvenance.Shared;
    private readonly IApplicationPlaceOpener _places = places ?? new ShellApplicationPlaceOpener();
    private readonly Func<long, OpenedWindowFront> _frontOf = frontOf ?? OpenedWindowFront.Read;
    private readonly IGameTitles _games = games ?? new CatalogGameTitles();
    // The clock the moment before the opening is read on (LaunchedByThisOpening compares it with the process's own).
    private readonly TimeProvider _time = time ?? TimeProvider.System;

    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("app.open");

    // Renew al máximo (guarda msconfig): E014 «abre la configuración de sonido» opened «Configuración del sistema»
    // (msconfig) elevated without asking, the window where the incidente del 2026-10-15 disabled 256 services. An
    // opening whose name resolves to a tool that configures Windows itself (the provider's rule, the one no click acts
    // on) is this invocation's own risk: it asks in normal mode, bound to it. Read only; any other opening goes straight.
    public bool MayRaise(JsonElement arguments) => true;

    public async ValueTask<InvocationPreflightResult> PreflightAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string? appId = arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("appId", out JsonElement named)
            && named.ValueKind == JsonValueKind.String
                ? named.GetString()
                : null;
        // E014 (int3 s1): a place its application does not have is refused by the opening itself, launching nothing;
        // asking the person first («¿Abro la Configuración del sistema en la sección de sonido?») asked for nothing.
        if (appId is not null
            && arguments.TryGetProperty("place", out JsonElement place) && place.ValueKind == JsonValueKind.String
            && !ApplicationPlaces.PlacesOf(appId).Any(declared => declared.Place == place.GetString()))
        {
            return InvocationPreflightResult.Proceed;
        }

        // Revisión del núcleo (q-core): a value with no place, or one its place does not take, is refused by the opening
        // the same way (place_value_not_taken, nothing launched); a game's title is looked up first, so it still asks.
        string? placeName = arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("place", out JsonElement placed) && placed.ValueKind == JsonValueKind.String
                ? placed.GetString()
                : null;
        string? placeValue = arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("placeValue", out JsonElement valued) && valued.ValueKind == JsonValueKind.String
                ? valued.GetString()
                : null;
        if (appId is not null && placeValue is not null
            && ApplicationPlaces.GameCatalogOf(appId, placeName) is null
            && ApplicationPlaces.Address(appId, placeName, placeValue) is null)
        {
            return InvocationPreflightResult.Proceed;
        }

        return appId is not null && ApplicationIds.IsValidOpening(appId)
            && await _provider.OpensSystemToolAsync(appId, cancellationToken).ConfigureAwait(false)
                ? InvocationPreflightResult.Raised(OperationRisk.Irreversible)
                : InvocationPreflightResult.Proceed;
    }

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
            return OperationOutcome.InvalidArguments(Definition, invocation.Arguments);
        }

        if (!ApplicationIds.IsValidOpening(arguments.AppId))
        {
            return OperationOutcome.Failure("invalid_application");
        }

        // Estabilización, encargo C: a place is opened only by the address its application's data declare
        // (ApplicationPlaces); a place, a value or an application the data do not declare opens nothing.
        string? placeAddress = null;
        string? placeValue = arguments.PlaceValue;
        GameTitle? game = null;
        // BAXY Renew cu (C04): a game's page asked for by the game's title, as the person says it; its catalog turns it
        // into the number the address takes, and the game found is named back with the opening. A value of digits
        // alone is already that number, except a title said as such (game.store.page: «1942» is a game's name).
        if (ApplicationPlaces.GameCatalogOf(arguments.AppId, arguments.Place) is { } catalog
            && !string.IsNullOrWhiteSpace(placeValue)
            && (arguments.PlaceValueAsSaid == true || !placeValue.All(char.IsAsciiDigit)))
        {
            bool searchFailed = false;
            try
            {
                game = await _games.FindAsync(catalog, placeValue, cancellationToken).ConfigureAwait(false);
            }
            catch (GameTitleSearchFailedException)
            {
                // Renew al máximo (auditoría de flujos): no answer (no network) is not a title nothing bears.
                searchFailed = true;
            }

            if (game is null)
            {
                return OperationOutcome.Failure(
                    searchFailed ? "game_title_search_failed" : "game_title_not_found",
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
                // Said with what was asked (BAXY Renew, notebook). BAXY Renew cu (C04 variant): a place the application
                // has, refused for its value (a game's name given to its library), is told apart, with what each place
                // takes. Revisión 2026-10-22 (B-APP-3): a value given with no place is a value not taken too, never a
                // place of another application.
                bool placeOfApplication = arguments.Place is null || ApplicationPlaces.PlacesOf(arguments.AppId)
                    .Any(declared => declared.Place == arguments.Place);
                // Renew al máximo (E014): after the fact that nothing opened (int3 s1 told «Abrí Configuración» from a
                // hint that began with «opens it»). Ajuste c4 (banco ciego c3, causa 4: C3-051, C3-052, C3-089,
                // C3-092): a place of another application says how the one asked for opens, never another one (the
                // opening that reached the place's application opened it instead, and the one asked for never opened);
                // the application the person's words name is SaidApplication's, which knows them. Encargo 34 (rule of
                // encargos 20 and 28): the call that opens it comes first, with its argument written, and what this one
                // did not open at the end; its places, when it has some, between them.
                string itself = $"{WireNames.Call("app.open", new() { ["appId"] = arguments.AppId })} opens "
                    + $"{arguments.AppId} itself";
                string notOf = $"this call opened nothing: {arguments.Place} is not a place of {arguments.AppId}";
                string? places = !ModelAids.On(ModelAids.AppPlaces) ? null
                    : placeOfApplication
                        ? PlacesNext($"nothing was opened. {arguments.AppId} opens straight at a place of its own",
                            arguments.AppId)
                        : (PlacesNext($"{itself}; it also opens straight at a place of its own", arguments.AppId) ?? itself)
                            + "; " + notOf;
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
                        {
                            WritePlaces(writer, arguments.AppId);
                            WriteNames(writer, "placeIn", ApplicationPlaces.ApplicationsWith(arguments.Place));
                        }

                        if (places is not null) writer.WriteString("next", places);
                    }));
            }
        }

        // v3 r22 revisión: the moment before the opening. A process created before it was not launched by this
        // opening, whatever the provider's reuse flag says (a process already running with no visible window, a
        // window that appears inside a process the person was already using), and never counts as BAXY's.
        // v3 r22 revisión 2: the person's own input into what this opening launches is watched from before it.
        _provenance.PrepareLaunch();
        long openingStartedTicks = _time.GetUtcNow().UtcTicks;
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
            // Banco de uso 2026-11-03 (U33): a place of an application that is not on the PC whose data declare its
            // page on the web says that page (with the game found), and what opens it; nothing was opened.
            if (errorCode == "app_not_found" && placeAddress is not null
                && ApplicationPlaces.WebAddress(arguments.AppId, arguments.Place, placeValue) is { } web)
            {
                return OperationOutcome.Failure(errorCode, result: Facts(writer =>
                {
                    writer.WriteString("appId", arguments.AppId);
                    writer.WriteString("place", arguments.Place);
                    writer.WriteString("placeWebUrl", web);
                    if (game is not null)
                    {
                        writer.WriteStartObject("placeGame");
                        writer.WriteString("number", game.Number);
                        writer.WriteString("name", game.Name);
                        writer.WriteEndObject();
                    }

                    WriteNames(writer, "candidates", providerResult.Candidates);
                    // Encargo 28 (U33): the call first, with the page's address; told after «nothing was opened», the
                    // model dictated the address 2 and 3 times of 10 (WireNames.Call).
                    writer.WriteString("next", $"{WireNames.Call("browser.navigate", new() { ["url"] = web })} opens "
                        + $"this place's page on the web in the person's browser; this call opened nothing: "
                        + $"{arguments.AppId} is not installed on this PC");
                }));
            }

            return OperationOutcome.Failure(
                errorCode,
                result: ModelAids.On(ModelAids.OpenRecovery)
                    ? Facts(writer => WriteRecovery(writer, errorCode, arguments.AppId, providerResult, invocation.Arguments))
                    : providerResult.EmptyFrame || providerResult.ExitedWithError is not null
                        ? Facts(writer =>
                        {
                            WriteNames(writer, "candidates", providerResult.Candidates);
                            if (providerResult.EmptyFrame)
                                writer.WriteBoolean("emptyFrame", true);
                            if (providerResult.ExitedWithError is { } exited)
                                writer.WriteString("exitedWithError", exited);
                        })
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
                    if (providerResult.WindowHandle is long window and not 0)
                        writer.WriteNumber("window", window);
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
            && await _settle(openedWindow, providerResult.DisplayName, cancellationToken).ConfigureAwait(false)
                is long settled and not 0)
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
                : place is null && ModelAids.On(ModelAids.AppPlaces)
                    ? ItsRead(arguments.AppId)
                : null,
            FrontChanged: place?.FrontChanged == true,
            PlaceGame: game is null ? null : new PlacedGame(game.Number, game.Name),
            WindowId: windowIdFor?.Invoke((nint)openedWindow),
            Window: openedWindow,
            ProcessName: front.Process,
            Foreground: front.Held,
            ForegroundHeldBy: front.HolderTitle is { } title ? new WindowName(title, front.HolderProcess ?? string.Empty) : null,
            PlaceWindowChanged: place?.WindowChanged);
        JsonElement serialized = JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.OpenApplicationResult);
        return OperationOutcome.Success(serialized);
    }

    // Encargo 80: the read the application's data declare, its call first (the rule of encargos 20 and 28). Without it
    // «abre Configuración y dime si el modo es claro u oscuro» walked its pages and told a theme's name as the mode, even
    // with the read in the catalog (live, 2 of 6); with it 6 of 6, in two calls.
    // Uso real 04-11: the places an opening could have gone to (BAXY Renew cu, C04) were listed in the result of one that
    // asked for none, and one of them was told as where it opened. The tool's description lists them, the mind says them
    // with the next turn, and a click that fails after it says them again (the mind's app_places_next).
    private static string? ItsRead(string appId) =>
        ApplicationPlaces.ReadOf(appId) is { } read
            ? $"{WireNames.Call(read.Operation, read.Arguments)} reads {read.Tells}"
            : null;

    // P2.15: «lead» starts the sentence, so a refusal says first that nothing opened.
    private static string? PlacesNext(string lead, string appId)
    {
        IReadOnlyList<(string Place, string? Takes)> places = ApplicationPlaces.PlacesOf(appId);
        return places.Count == 0 ? null
            : $"{lead}, by app_open with place: "
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
        Utf8JsonWriter writer, string errorCode, string appId, ApplicationOpenResult opening, JsonElement asked)
    {
        WriteNames(writer, "candidates", opening.Candidates);
        ApplicationLaunchReceipt receipt = opening.Receipt;
        writer.WriteBoolean("launchIssued", receipt.LaunchIssued);
        if (receipt.ReusedExisting)
            writer.WriteBoolean("alreadyRunning", true);
        // Renew al máximo (velocidad): what the opening saw instead of a window of it: its frame, empty.
        if (opening.EmptyFrame)
            writer.WriteBoolean("emptyFrame", true);
        // uso-108 C12: why no window came, only when a process of the launch died of it.
        if (opening.ExitedWithError is { } exited)
            writer.WriteString("exitedWithError", exited);
        string name = string.IsNullOrWhiteSpace(opening.DisplayName) ? appId : opening.DisplayName;
        // Encargo 34 (rule of encargos 20 and 28): the look comes first, as the call with its argument written, and what
        // this opening saw at the end.
        string status = WireNames.Call("window.application.status", new() { ["name"] = name });
        string look = $"{status} tells whether a window of {name} shows now, before saying it opened or not";
        string? next = errorCode switch
        {
            "verification_failed" when opening.EmptyFrame =>
                $"Windows shows a window frame of {name} with nothing of {name} inside it (its program does not draw "
                    + "there); no window of it was verified",
            // Auditoría de falsedades: «was started» read as «se abrió»; what the receipt knows is that the launch was
            // issued (LaunchIssued), not that the application started.
            "verification_failed" or "inventory_failed" when receipt.LaunchIssued =>
                $"{look}; a launch of {name} was issued and no window of it was verified",
            "verification_failed" or "inventory_failed" when receipt.ReusedExisting =>
                $"{look}; {name} was already running and no window of it was verified",
            "verification_failed" => $"{look}; no window of {name} was verified",
            // Encargo 18 (banco de uso, U08/U14/U15): two installed applications of one name, and the model asked the
            // same name again until its calls ran out. Each candidate, as said, is an appId the opening takes.
            "app_ambiguous" when opening.Candidates is { Count: > 1 } =>
                $"nothing was opened: more than one installed application answers to {appId}; {WireNames.Of("app.open")} "
                    + "with appId set to one of candidates, written exactly as it is there, opens that one",
            // Banco de entorno del NB (R17: «Opera GX» said, «Navegador Opera GX» installed, two of three runs gave up
            // here): the one installed name that holds the name asked leads, as the call with the model's own other
            // arguments (encargo 28: a next that leads with the call is followed); nothing was opened by it.
            "app_not_found" when opening.NameHolder is { } holder && ModelAids.On(ModelAids.NameHolderNext) =>
                $"{WireNames.Call("app.open", WithAppId(asked, holder))} opens {holder}, the one installed application "
                    + $"whose name holds «{appId}» whole; this call opened nothing: no installed application is named "
                    + $"exactly {appId}",
            "launch_failed" when !receipt.LaunchIssued =>
                $"{status} tells whether {name} is open already; the launch of {name} was not issued (Windows did not "
                    + "take it)",
            // Encargo 98: its New command is another one in some languages: what showed instead of the document.
            "new_document_not_created" when opening.DialogOpened is { } met =>
                $"no new document was made: {name} showed «{met.Title}», "
                    + (met.Closed ? "which was closed again" : "which is still open"),
            _ => null,
        };
        if (opening.DialogOpened is { } dialog)
        {
            writer.WriteStartObject("dialogOpened");
            writer.WriteString("title", dialog.Title);
            writer.WriteBoolean("closed", dialog.Closed);
            writer.WriteEndObject();
        }

        if (next is not null)
            writer.WriteString("next", next);
    }

    // The call as the model wrote it, with appId set to the installed name (its other arguments as they were).
    private static System.Text.Json.Nodes.JsonObject WithAppId(JsonElement asked, string appId)
    {
        System.Text.Json.Nodes.JsonObject call =
            System.Text.Json.Nodes.JsonNode.Parse(asked.GetRawText()) as System.Text.Json.Nodes.JsonObject ?? [];
        call["appId"] = appId;
        return call;
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
