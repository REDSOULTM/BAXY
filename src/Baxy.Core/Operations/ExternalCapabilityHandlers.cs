using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using Baxy.Providers.Windows.External;
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
        "clipboard.copy",
        "clipboard.paste",
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
        "game.install.commit",
        "game.install.named",
        "game.install.prepare",
        "game.install.status",
        "game.launch",
        "game.uninstall.named",
        "game.purchase.commit",
        "game.purchase.prepare",
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
        "message.recipient.resolve",
        "message.send",
        "message.send.test",
        "office.document.create",
        "office.document.read",
        "ocr.read",
        "package.install.commit",
        "package.install.prepare",
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
        "filesystem.path.ensure.absent",
        "filesystem.sandbox.diff.named",
        "filesystem.sandbox.move.named",
        "weather.current",
        "web.news.headlines",
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

    public static IOperationHandler[] Create(IExternalCapabilityProvider provider, string? dataRoot = null) =>
        Operations.Select(operation =>
        {
            IOperationHandler handler = new ExternalCapabilityHandler(operation, provider);
            return operation == BaxySettingHandler.Operation
                ? new BaxySettingHandler(handler, dataRoot)
                : handler;
        }).ToArray();
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

        bool before = setting == AccessibleMode
            ? PresentationModeStore.ReadAccessible(dataRoot)
            : ConfirmationModeStore.Read(dataRoot) == ConfirmationMode.Bypass;
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

        bool after = setting == AccessibleMode
            ? PresentationModeStore.ReadAccessible(dataRoot)
            : ConfirmationModeStore.Read(dataRoot) == ConfirmationMode.Bypass;
        if (after != on)
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
            writer.WriteString("authority", "baxy_profile_setting_postread");
            writer.WriteEndObject();
        }

        using JsonDocument result = JsonDocument.Parse(buffer.ToArray());
        return ValueTask.FromResult(OperationOutcome.Success(result.RootElement.Clone()));
    }
}

internal sealed class ExternalCapabilityHandler(
    string operation,
    IExternalCapabilityProvider provider,
    LaunchProvenance? provenance = null) : IOperationHandler
{
    // v3 r22 uso real: the operations that only point at or move through what a window shows (a click on a control,
    // a scroll, the list of visible controls) put nothing into it. Every other operation that is not read-only may
    // have written into some window, and which one is not always known, so it marks every process BAXY launched as
    // written (LaunchProvenance, fail-closed): their windows ask again before closing.
    // v3 r22 revisión: a pointing operation may still carry text it types into what it opens (a click's «search» is
    // typed into the box the click opened, SearchBurst.TypeAsync); with any such argument present and not empty it
    // writes as well. Each typed argument is checked against the real catalog (AppCloseLaunchProvenanceTests).
    private static readonly Dictionary<string, string[]> PointingOperations = new(StringComparer.Ordinal)
    {
        ["input.visible.click"] = ["search"],
        ["input.scroll"] = [],
        ["input.visible.controls"] = [],
    };

    internal static IReadOnlyDictionary<string, string[]> PointingOperationsTypedArguments => PointingOperations;

    private readonly IExternalCapabilityProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));
    private readonly LaunchProvenance _provenance = provenance ?? LaunchProvenance.Shared;
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(operation);

    internal static bool MayWriteIntoAWindow(OperationDefinition definition, JsonElement arguments)
    {
        if (definition.Risk == OperationRisk.ReadOnly)
        {
            return false;
        }

        if (!PointingOperations.TryGetValue(definition.Name, out string[]? typed))
        {
            return true;
        }

        if (typed.Length == 0)
        {
            return false;
        }

        if (arguments.ValueKind != JsonValueKind.Object)
        {
            return true;
        }

        foreach (string name in typed)
        {
            if (arguments.TryGetProperty(name, out JsonElement value)
                && value.ValueKind != JsonValueKind.Null
                && (value.ValueKind != JsonValueKind.String || value.GetString()!.Length > 0))
            {
                return true;
            }
        }

        return false;
    }

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        if (MayWriteIntoAWindow(Definition, invocation.Arguments))
        {
            _provenance.NoteWritten();
        }

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
            return OperationOutcome.Failure(
                receipt.ErrorCode ?? "external_verification_failed",
                result: receipt.Verified ? null : receipt.Result,
                effectMayHaveOccurred: effectMayHaveOccurred,
                causeCode: effectMayHaveOccurred ? "external_effect_ambiguous" : null);
        }

        // v3 r6 lectores (t2-r4 c15): a switch whose verified post-read already showed the requested state is done with
        // changed:false; with neither an observed effect nor that verified state the request is not done.
        if (Definition.ProductDescriptor!.RequiresObservedEffect && !receipt.EffectObserved
            && !(receipt.StateAlreadyReached && !receipt.EffectMayHaveOccurred))
        {
            return OperationOutcome.Failure(
                "external_verification_failed",
                effectMayHaveOccurred: receipt.EffectMayHaveOccurred,
                causeCode: receipt.EffectMayHaveOccurred
                    ? "external_effect_ambiguous"
                    : "external_effect_unobserved");
        }

        return OperationOutcome.Success(receipt.Result.Value);
    }
}
