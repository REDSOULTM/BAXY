using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;

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
        "software.python.package.status",
        "software.python.status",
        "storage.removable.list",
        "document.pdf.read",
        "email.latest.read",
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
        "game.purchase.commit",
        "game.purchase.prepare",
        "input.key.press",
        "input.keyboard.layout",
        "input.keyboard.open",
        "input.keyboard.status",
        "input.pointer.control",
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
        "notification.cancel.at",
        "notification.cancel.latest",
        "notification.diagnose",
        "notification.list",
        "notification.schedule",
        "office.document.create",
        "office.document.read",
        "ocr.read",
        "package.install.commit",
        "package.install.prepare",
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
        "filesystem.file.open.latest",
        "filesystem.folder.open",
        "filesystem.known.duplicates",
        "filesystem.known.list",
        "filesystem.known.search",
        "filesystem.known.trash.named",
        "filesystem.path.ensure.absent",
        "filesystem.sandbox.append.named",
        "filesystem.sandbox.diff.named",
        "filesystem.sandbox.move.named",
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

    public static IOperationHandler[] Create(IExternalCapabilityProvider provider) =>
        Operations.Select(operation => (IOperationHandler)new ExternalCapabilityHandler(
            operation, provider)).ToArray();
}

internal sealed class ExternalCapabilityHandler(
    string operation,
    IExternalCapabilityProvider provider) : IOperationHandler
{
    private readonly IExternalCapabilityProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(operation);

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
            return OperationOutcome.Failure(
                receipt.ErrorCode ?? "external_verification_failed",
                effectMayHaveOccurred: effectMayHaveOccurred,
                causeCode: effectMayHaveOccurred ? "external_effect_ambiguous" : null);
        }

        if (Definition.ProductDescriptor!.RequiresObservedEffect && !receipt.EffectObserved)
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
