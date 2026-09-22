using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.Kernel.Planning;

public sealed record MissionPlanStepProposal(
    string Id,
    string Operation,
    string Purpose,
    IReadOnlyList<string> DependsOn,
    string ArgumentsMode,
    JsonElement? Arguments);

public sealed record MissionPlanProposal(
    int Version,
    string Objective,
    IReadOnlyList<MissionPlanStepProposal> Steps);

public sealed class MissionPlanValidationException : Exception
{
    public MissionPlanValidationException(string message)
        : base(message)
    {
    }
}

/// <summary>
/// Valida propuestas del sidecar sin confiar en texto, riesgo ni autoridad del modelo.
/// La policy y el verifier siguen ejecutándose por operación en MissionEngine.
/// </summary>
public static class MissionPlanValidator
{
    public const int MaximumSteps = 16;
    public const int MaximumObjectiveUtf8Bytes = 16_384;
    public const int MaximumPurposeUtf8Bytes = 2_048;

    public static void Validate(MissionPlanProposal proposal)
    {
        ArgumentNullException.ThrowIfNull(proposal);
        if (proposal.Version != 1)
        {
            throw new MissionPlanValidationException("The plan version is not supported.");
        }

        ValidateText(
            proposal.Objective,
            MaximumObjectiveUtf8Bytes,
            "The plan objective is invalid.");
        if (proposal.Steps is null
            || proposal.Steps.Count is < 1 or > MaximumSteps
            || proposal.Steps.Any(static step => step is null))
        {
            throw new MissionPlanValidationException("The plan step count is invalid.");
        }

        var seen = new HashSet<string>(StringComparer.Ordinal);
        var precedingOperations = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (MissionPlanStepProposal step in proposal.Steps)
        {
            if (!IsStepId(step.Id) || !seen.Add(step.Id))
            {
                throw new MissionPlanValidationException("Plan step IDs must be unique and canonical.");
            }

            if (!ProductCatalog.TryGet(step.Operation, out ProductOperationDescriptor? descriptor)
                || descriptor.ToolExposure != ToolExposure.Public
                || descriptor.Risk == OperationRisks.ForbiddenDestructive
                || step.Operation.StartsWith("memory.", StringComparison.Ordinal))
            {
                throw new MissionPlanValidationException(
                    "A plan step references an operation outside the public planning boundary.");
            }

            ValidateText(
                step.Purpose,
                MaximumPurposeUtf8Bytes,
                "A plan step purpose is invalid.");
            if (step.DependsOn is null
                || step.DependsOn.Count >= MaximumSteps
                || step.DependsOn.Distinct(StringComparer.Ordinal).Count()
                    != step.DependsOn.Count
                || step.DependsOn.Any(dependency => !seen.Contains(dependency)))
            {
                throw new MissionPlanValidationException(
                    "A plan step may depend only on unique preceding steps.");
            }

            string[] requiredPredecessors = RequiredPredecessorOperations(
                step.Operation);
            if (requiredPredecessors.Length > 0
                && !step.DependsOn.Any(dependency =>
                    precedingOperations.TryGetValue(
                        dependency,
                        out string? producerOperation)
                    && requiredPredecessors.Contains(
                        producerOperation,
                        StringComparer.Ordinal)))
            {
                throw new MissionPlanValidationException(
                    "A dependency-bound operation lacks its required verified producer.");
            }

            if (step.ArgumentsMode == "after_dependencies")
            {
                string[] permittedProducers = DependencyProducerOperations(
                    step.Operation);
                if (permittedProducers.Length == 0
                    || !step.DependsOn.Any(dependency =>
                        precedingOperations.TryGetValue(
                            dependency,
                            out string? producerOperation)
                        && permittedProducers.Contains(
                            producerOperation,
                            StringComparer.Ordinal)))
                {
                    throw new MissionPlanValidationException(
                        "Deferred grounding lacks a permitted producer family.");
                }
            }

            switch (step.ArgumentsMode)
            {
                case "literal" when step.Arguments is { } arguments:
                    if (!OperationArgumentValidator.IsValid(arguments, descriptor.ArgumentsSchema))
                    {
                        throw new MissionPlanValidationException(
                            "Literal plan arguments do not satisfy the operation schema.");
                    }

                    break;
                case "after_dependencies" when step.Arguments is null
                    && step.DependsOn.Count > 0:
                    break;
                default:
                    throw new MissionPlanValidationException(
                        "The plan argument materialization mode is invalid.");
            }

            precedingOperations.Add(step.Id, step.Operation);
        }
    }

    /// <summary>
    /// Returns the closed set of producer operations that can authorize a
    /// dependency-bound consumer. An empty set means the operation has no
    /// mandatory producer family at the plan boundary.
    /// </summary>
    public static string[] RequiredPredecessorOperations(string operation) =>
        operation switch
        {
            "app.close" => ["window.resolve", "window.active"],
            "bluetooth.device.pair" => ["bluetooth.device.list"],
            "filesystem.read.text" => ["filesystem.search", "filesystem.list"],
            "game.install.commit" => ["game.install.prepare"],
            "game.purchase.commit" => ["game.purchase.prepare"],
            "message.send" => ["message.recipient.resolve"],
            "notification.dismiss" => ["notification.list.due"],
            "ocr.read" => ["capture.screenshot", "capture.active.window"],
            "package.install.commit" => ["package.install.prepare"],
            "peripheral.print" or "peripheral.scan" => ["peripheral.list"],
            "reminder.delete" => ["reminder.resolve.exact"],
            "vision.describe" => ["capture.screenshot"],
            "window.focus" or "window.maximize" or "window.minimize"
                or "window.move" or "window.resize" or "window.restore"
                or "window.snap" =>
                ["window.resolve", "window.active"],
            "wifi.connect" => ["wifi.profile.list"],
            _ => [],
        };

    /// <summary>
    /// Returns every producer family whose verified result may ground the
    /// operation. Conditional relations apply only when the consumer uses
    /// deferred arguments; direct literal identities remain valid.
    /// </summary>
    public static string[] DependencyProducerOperations(string operation)
    {
        string[] required = RequiredPredecessorOperations(operation);
        if (required.Length > 0)
        {
            return required;
        }

        return operation switch
        {
            "browser.navigate" or "browser.navigate.named" => ["web.search"],
            "note.read" => ["note.create"],
            "office.document.read" => ["office.document.create"],
            // FILES1705 «crea un archivo de texto con los 5 procesos que más
            // memoria usan»: the file's text is projected from the verified
            // process listing, so the write may defer its arguments to it.
            "filesystem.write.text" => ["system.process.list"],
            // MEME2053 «Tienes algun meme?»: the picture the image search
            // downloads is the file the viewer opens; its name exists only in
            // the verified download, so the open defers its arguments to it.
            "file.open" => ["web.download"],
            _ => [],
        };
    }

    /// <summary>
    /// Returns the argument fields that must be copied from verified producer
    /// observations before a dependency-bound consumer can execute.
    /// </summary>
    public static string[] DependencyAuthorityFields(string operation) =>
        operation switch
        {
            "app.close" or "window.focus" or "window.maximize"
                or "window.minimize" or "window.move" or "window.resize"
                or "window.restore" or "window.snap" => ["windowId"],
            "bluetooth.device.pair" or "peripheral.print"
                or "peripheral.scan" => ["deviceId"],
            "browser.navigate" or "browser.navigate.named" => ["url"],
            "filesystem.read.text" => ["resourceId"],
            "game.install.commit" or "game.purchase.commit"
                or "package.install.commit" => ["confirmationId"],
            "message.send" => ["recipientId"],
            "note.read" => ["noteId"],
            "notification.dismiss" or "reminder.delete" => ["reminderId"],
            "ocr.read" or "vision.describe" => ["captureId"],
            "office.document.read" => ["documentId"],
            "wifi.connect" => ["profileId"],
            "file.open" => ["folder", "name"],
            _ => [],
        };

    private static bool IsStepId(string? value)
    {
        if (string.IsNullOrEmpty(value)
            || value.Length > 32
            || value[0] is < 'a' or > 'z')
        {
            return false;
        }

        return value.All(static character => character is >= 'a' and <= 'z'
            or >= '0' and <= '9'
            or '_');
    }

    private static void ValidateText(string? value, int maximumUtf8Bytes, string error)
    {
        if (string.IsNullOrWhiteSpace(value)
            || System.Text.Encoding.UTF8.GetByteCount(value) > maximumUtf8Bytes
            || value.Any(IsUnsafeTextCharacter))
        {
            throw new MissionPlanValidationException(error);
        }
    }

    private static bool IsUnsafeTextCharacter(char character) =>
        char.IsControl(character) && character is not ('\r' or '\n' or '\t')
        || char.IsSurrogate(character)
        || character is '\u061c'
            or '\u200b'
            or '\u200c'
            or '\u200d'
            or '\u200e'
            or '\u200f'
            or '\u202a'
            or '\u202b'
            or '\u202c'
            or '\u202d'
            or '\u202e'
            or '\u2060'
            or '\u2066'
            or '\u2067'
            or '\u2068'
            or '\u2069'
            or '\ufeff';
}
