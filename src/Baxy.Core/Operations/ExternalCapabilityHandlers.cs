using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.Windows;

namespace Baxy.Core.Operations;

internal static class ExternalCapabilityHandlers
{
    private static readonly string[] Operations =
    [
        "bluetooth.device.list",
        "bluetooth.device.pair",
        "bluetooth.radio.set",
        "bluetooth.radio.status",
        "backup.known.create",
        "backup.known.list",
        "backup.known.restore.latest",
        "backup.known.verify.latest",
        "browser.control",
        "browser.navigate",
        "browser.navigate.named",
        "browser.page.read",
        "browser.tabs.list",
        "calculator.expression.evaluate",
        "calendar.event.create",
        "calendar.event.list",
        "client.channel.locate",
        "client.microphone.set",
        "clipboard.copy",
        "clipboard.paste",
        "display.mode.set",
        "display.status",
        "desktop.wallpaper.set",
        "file.compress",
        "file.edit",
        "file.find",
        "file.open",
        "file.read",
        "software.python.package.status",
        "software.python.status",
        "storage.removable.list",
        "document.presentation.create",
        "email.latest.read",
        "email.send",
        "email.latest.reply",
        "game.catalog.list",
        "game.entitlement.named",
        "game.installed.named",
        "game.install.cancel",
        "game.install.cancel.active",
        "game.install.named",
        "game.install.status",
        "game.launch",
        "game.uninstall.named",
        "input.key.press",
        "input.keyboard.layout",
        "input.keyboard.open",
        "input.keyboard.status",
        "input.pointer.control",
        "input.scroll",
        "input.select.all",
        "input.text.type",
        "input.visible.click",
        "input.visible.controls",
        "media.control",
        "media.seek.relative",
        "media.play.exact",
        "media.play.query",
        "media.play.youtube",
        "media.status",
        "message.draft",
        "message.send",
        "message.send.test",
        "office.document.create",
        "office.document.read",
        "office.format.apply",
        "ocr.read",
        "package.install",
        "package.uninstall",
        "shell.command.run",
        "peripheral.list",
        "peripheral.print",
        "peripheral.scan",
        "streaming.navigate",
        "streaming.play.named",
        "system.application.crash.diagnose",
        "system.power",
        "system.process.terminate.named",
        "system.recyclebin.empty",
        "system.settings.adjust",
        "system.settings.status",
        "system.settings.set",
        "vision.describe",
        "web.search",
        "web.fetch",
        "schedule.alarms",
        "filesystem.explorer.count",
        "filesystem.file.open.latest",
        "filesystem.folder.open",
        "filesystem.known.duplicates",
        "filesystem.known.trash.named",
        "filesystem.sandbox.diff.named",
        "filesystem.sandbox.move.named",
        "weather.current",
        "web.download",
        "wifi.connect",
        "wifi.connect.named",
        "wifi.disconnect",
        "wifi.ensure.connected",
        "wifi.profile.list",
        "wifi.radio.set",
        "wifi.radio.status",
        "wifi.scan",
        "wifi.status",
    ];

    /// <param name="keyWindows">The window a key press lands on (K-2 refinada); null (the test seams) reads none, and
    /// every Enter or space that declares neither target nor onto keeps asking in normal mode.</param>
    public static IOperationHandler[] Create(
        IExternalCapabilityProvider provider,
        string? dataRoot = null,
        IKeyWindowReader? keyWindows = null) =>
        Operations.Select(operation =>
        {
            var external = new ExternalCapabilityHandler(operation, provider);
            return operation switch
            {
                BaxySettingHandler.Operation => new BaxySettingHandler(external, dataRoot),
                KeyPressHandler.Operation when keyWindows is not null => new KeyPressHandler(external, keyWindows),
                _ => (IOperationHandler)external,
            };
        }).ToArray();
}

/// <summary>
/// Al máximo, K-2 refinada (2026-10-22): Enter or space that declares neither where the keyboard is (target) nor what it
/// lands on (onto) asks in normal mode (RiskPolicy.PressesUndeclared), because message.draft leaves a message written in
/// a chat and that Enter would send it. Asking for every such Enter also asked for each one in a search box or an
/// address bar. Before the person is asked, this preflight reads the window the key would reach (the window argument,
/// or the one the provider sends a key with no window to): neither a messaging client nor a console lowers the press
/// to a reversible act and it goes without asking; one that is, or one that cannot be read, keeps the question. The
/// windows are told by the providers' data (<see cref="IKeyWindowReader"/>).
/// </summary>
internal sealed class KeyPressHandler(ExternalCapabilityHandler keys, IKeyWindowReader windows)
    : IOperationHandler, IInvocationPreflight
{
    internal const string Operation = "input.key.press";

    public OperationDefinition Definition => keys.Definition;

    public async ValueTask<InvocationPreflightResult> PreflightAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        InvocationPreflightResult found = await keys.PreflightAsync(arguments, cancellationToken).ConfigureAwait(false);
        // Renew al máximo (guarda diálogo destructivo): a risk the provider raised is never lowered here.
        if (found.Failure is not null
            || found.Risk is not null
            || !RiskPolicy.PressesUndeclared(Operation, arguments)
            || !TryWindow(arguments, out long? window))
        {
            return found;
        }

        KeyWindowKind kind;
        try
        {
            kind = windows.KindOf(window);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return found;
        }

        return kind == KeyWindowKind.Ordinary ? InvocationPreflightResult.Lowered(OperationRisk.Reversible) : found;
    }

    public bool MayRaise(JsonElement arguments) => keys.MayRaise(arguments);

    public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken) =>
        keys.ExecuteAsync(invocation, cancellationToken);

    // No window (absent or null): the key goes where the provider sends it. A positive whole number: that window.
    // Anything else cannot be placed.
    private static bool TryWindow(JsonElement arguments, out long? window)
    {
        window = null;
        if (!arguments.TryGetProperty("window", out JsonElement named) || named.ValueKind == JsonValueKind.Null)
        {
            return true;
        }

        if (named.ValueKind == JsonValueKind.Number && named.TryGetInt64(out long handle) && handle > 0)
        {
            window = handle;
            return true;
        }

        return false;
    }
}

/// <summary>
/// Estabilización U: BAXY's own settings ride on <c>system.settings.set</c> and live in the profile, in the same
/// stores the App reads (<see cref="PresentationModeStore"/>) and the engine reads (<see cref="ConfirmationModeStore"/>).
/// The accessible mode is switched both ways and verified by reading the file back. Bypass is only switched off here:
/// switching it on is a conscious gesture in BAXY's own interface (identity, «Peligro y confirmación»), so from the chat
/// it is refused with its cause and nothing changes. Every Windows setting goes on to the Windows provider.
/// </summary>
internal sealed class BaxySettingHandler(IOperationHandler windows, string? dataRoot) : IOperationHandler
{
    internal const string Operation = "system.settings.set";
    internal const string AccessibleMode = "accessible_mode";
    internal const string ConfirmationBypass = "confirmation_bypass";

    public OperationDefinition Definition => windows.Definition;

    public ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        JsonElement arguments = invocation.Arguments;
        string? setting = arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("setting", out JsonElement named)
            && named.ValueKind == JsonValueKind.String
                ? named.GetString()
                : null;
        if (setting is not (AccessibleMode or ConfirmationBypass))
        {
            return windows.ExecuteAsync(invocation, cancellationToken);
        }

        int value = arguments.TryGetProperty("value", out JsonElement asked) && asked.TryGetInt32(out int number)
            ? number
            : -1;
        if (value is not (0 or 1))
        {
            return ValueTask.FromResult(OperationOutcome.Failure("baxy_setting_value_invalid"));
        }

        if (string.IsNullOrWhiteSpace(dataRoot))
        {
            return ValueTask.FromResult(OperationOutcome.Failure("baxy_setting_unavailable"));
        }

        bool on = value == 1;
        if (setting == ConfirmationBypass && on)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("confirmation_bypass_interface_only"));
        }

        // Revisión 2026-10-22 (C-3): a file that cannot be read (another program holds it locked) is not «off»: taking it
        // so answered «already off», done, while the file still said on.
        if (!TryReadOn(setting, out bool before))
        {
            return ValueTask.FromResult(OperationOutcome.Failure("baxy_setting_unreadable"));
        }

        try
        {
            if (before != on)
            {
                if (setting == AccessibleMode)
                    PresentationModeStore.WriteAccessible(dataRoot, on);
                else
                    ConfirmationModeStore.Write(dataRoot, ConfirmationMode.Normal);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "baxy_setting_write_failed", effectMayHaveOccurred: true, causeCode: "external_effect_ambiguous"));
        }

        if (!TryReadOn(setting, out bool after) || after != on)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "baxy_setting_postread_failed", effectMayHaveOccurred: before != on));
        }

        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("setting", setting);
            writer.WriteNumber("value", value);
            writer.WriteBoolean("changed", before != on);
            if (setting == AccessibleMode && ModelAids.On(ModelAids.AccessibleScope))
            {
                // pc-ayudas: what the mode changes (SettingsPanel's «Modo accesible») and the modes the interface shows
                // as not ready yet (Rail's PROFILES), so a reply never promises more than the switch did.
                writer.WriteString("scope", "BAXY's own window only: larger text, more contrast, wider buttons");
                writer.WriteString("notAvailableYet", "a blind (screen reader) mode and a hands-free mobility mode");
            }
            writer.WriteString("authority", "baxy_profile_setting_postread");
            writer.WriteEndObject();
        }

        using JsonDocument result = JsonDocument.Parse(buffer.ToArray());
        return ValueTask.FromResult(OperationOutcome.Success(result.RootElement.Clone()));
    }

    // Whether the setting's file could be read, and whether it says on.
    private bool TryReadOn(string setting, out bool on)
    {
        if (setting == AccessibleMode)
        {
            return PresentationModeStore.TryReadAccessible(dataRoot, out on);
        }

        bool read = ConfirmationModeStore.TryRead(dataRoot, out ConfirmationMode mode);
        on = mode == ConfirmationMode.Bypass;
        return read;
    }
}

internal sealed class ExternalCapabilityHandler(
    string operation,
    IExternalCapabilityProvider provider) : IOperationHandler, IInvocationPreflight
{
    private readonly IExternalCapabilityProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(operation);

    // Al máximo, flujos: what the provider reads of the call's target before the person is asked (a name that is not
    // there, or is there several times, with its candidates): that failure answers without a yes. A provider that
    // cannot tell, or fails to read, leaves the call to ask and to run as always.
    public async ValueTask<InvocationPreflightResult> PreflightAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        ExternalCapabilityReceipt? found;
        try
        {
            found = await _provider.PreflightAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception)
        {
            return InvocationPreflightResult.Proceed;
        }

        // Renew al máximo (guarda diálogo destructivo): a call the provider found needs the person's yes (the «Sí» under
        // «¿Quieres reemplazarlo?») asks, bound to it, as what cannot be undone.
        if (found is { NeedsConfirmation: true, Verified: false, EffectObserved: false, EffectMayHaveOccurred: false }
            && string.Equals(found.Operation, operation, StringComparison.Ordinal))
        {
            return InvocationPreflightResult.Raised(OperationRisk.Irreversible);
        }

        return found is { Verified: false, EffectObserved: false, EffectMayHaveOccurred: false }
            && string.Equals(found.Operation, operation, StringComparison.Ordinal)
            && !string.IsNullOrWhiteSpace(found.ErrorCode)
                ? InvocationPreflightResult.Fails(OperationOutcome.Failure(found.ErrorCode, result: found.Result))
                : InvocationPreflightResult.Proceed;
    }

    // Renew al máximo (guarda diálogo destructivo): only a call the provider says may need a yes is read when its
    // declared risk goes without asking; a provider that fails to say keeps it as declared.
    public bool MayRaise(JsonElement arguments)
    {
        try
        {
            return _provider.PreflightMayRaise(operation, arguments);
        }
        catch (Exception exception) when (exception is InvalidOperationException or ArgumentException
            or JsonException or KeyNotFoundException or ObjectDisposedException)
        {
            return false;
        }
    }

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        ExternalCapabilityReceipt receipt;
        try
        {
            receipt = await _provider.InvokeAsync(
                operation, invocation.Arguments, cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception)
        {
            bool effectMayHaveOccurred = Definition.ProductDescriptor!.RequiresObservedEffect;
            return OperationOutcome.Failure(
                "external_provider_failed",
                effectMayHaveOccurred: effectMayHaveOccurred,
                causeCode: effectMayHaveOccurred
                    ? "external_effect_ambiguous"
                    : "external_provider_exception");
        }
        if (!string.Equals(receipt.Operation, operation, StringComparison.Ordinal)
            || !receipt.Verified
            || receipt.Result is null
            || receipt.ErrorCode is not null)
        {
            bool effectMayHaveOccurred =
                receipt.EffectObserved || receipt.EffectMayHaveOccurred;
            // What a failing provider still observed (how many tabs it closed
            // before stopping) travels with the failure, never as success.
            // BAXY Renew cu (C14): an empty code from a provider is no code; journaled as «» it kept the engine from
            // starting again on that profile (the journal's read-back refused the entry).
            return OperationOutcome.Failure(
                string.IsNullOrWhiteSpace(receipt.ErrorCode) ? "external_verification_failed" : receipt.ErrorCode,
                result: receipt.Verified ? null : receipt.Result,
                effectMayHaveOccurred: effectMayHaveOccurred,
                causeCode: effectMayHaveOccurred ? "external_effect_ambiguous" : null);
        }

        // v3 r6 lectores (t2-r4 c15): a switch whose verified post-read already showed the requested state is done;
        // with neither an observed effect nor that verified state the request is not done.
        if (Definition.ProductDescriptor!.RequiresObservedEffect && !receipt.EffectObserved
            && !(receipt.StateAlreadyReached && !receipt.EffectMayHaveOccurred))
        {
            // Auditoría del Core (w8): the provider's verified post-read is what it saw after the call; it travels with
            // the failure, marked effectObserved:false, never as success (status, code and uncertainty unchanged).
            return OperationOutcome.Failure(
                "external_verification_failed",
                result: Unobserved(receipt.Result.Value),
                effectMayHaveOccurred: receipt.EffectMayHaveOccurred,
                causeCode: receipt.EffectMayHaveOccurred
                    ? "external_effect_ambiguous"
                    : "external_effect_unobserved");
        }

        return OperationOutcome.Success(receipt.StateAlreadyReached
            ? Unchanged(receipt.Result.Value)
            : receipt.Result.Value);
    }

    // Ronda B: the state already reached travels to the model as changed:false in the result (a disconnection that
    // was already done reads apart from one that happened); a result that says changed itself keeps its own.
    private static JsonElement Unchanged(JsonElement result) => WithFact(result, "changed");

    // The verified post-read of a call whose effect was not observed: effectObserved:false beside its own properties (a
    // result that says it itself keeps its own).
    private static JsonElement Unobserved(JsonElement result) => WithFact(result, "effectObserved");

    private static JsonElement WithFact(JsonElement result, string name)
    {
        if (result.ValueKind != JsonValueKind.Object || result.TryGetProperty(name, out _))
        {
            return result;
        }

        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            foreach (JsonProperty property in result.EnumerateObject())
            {
                property.WriteTo(writer);
            }

            writer.WriteBoolean(name, false);
            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.ToArray());
        return document.RootElement.Clone();
    }
}
