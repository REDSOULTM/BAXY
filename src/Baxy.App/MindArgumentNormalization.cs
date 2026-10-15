using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;

namespace Baxy.App;

/// <summary>
/// Decide si una operación necesita que el modelo extraiga argumentos y lleva
/// los que extrajo a su forma canónica. Es el borde común de los planes directos
/// y los compuestos: ambos entran por aquí para recibir la misma identidad.
/// </summary>
internal static class MindArgumentNormalization
{
    internal static bool RequiresExtraction(ProductOperationDescriptor descriptor)
    {
        ArgumentNullException.ThrowIfNull(descriptor);
        return descriptor.ArgumentsSchema.Properties.Count > 0;
    }

    /// <summary>
    /// The arguments in canonical form. An opening outside a computer-use mission (<paramref name="beforeComputerUse"/>
    /// false) is one the person asked to see: it comes to the front («foreground»), the owner's rule for a bare «abre
    /// X» (v3 point 0, arreglo 4). An opening the plan makes for a computer-use mission stays behind the person's
    /// window unless the mind asked for the front; an explicit «foreground» is never changed. The same rule by who asked
    /// holds for a file opened with an application (file.open, molestia-ayudantes: «abre paisaje.jpg en Fotos» opened
    /// it behind the person's window, and BAXY said «abrí…» of a file they could not see).
    /// cu-v3-elevacion (r9 v3-23, v3-65): every opening starts the application with the person's own rights
    /// («forControl», v3 r5a M5), so a console a turn opens is one the next turn can read and press; only a request
    /// that asks for administrator rights (<see cref="OperationFloor.AdministratorAsked"/>) keeps the shell's path and
    /// the rights Windows gives it. Review of cu-v3-elevacion (finding 2): «forControl» is the App's to decide from the
    /// request alone, never the extractor's: a «forControl» the model wrote is replaced (false on a bare «abre
    /// servicios» would raise the console unasked; true on «como administrador» would ignore what the person said).
    /// Estabilización, encargo C: a place of the application (<c>place</c>, <c>placeValue</c>) is opened only by a
    /// computer-use mission, whose check then reads the window for the arrival; an opening outside one never carries it.
    /// </summary>
    internal static JsonObject Normalize(
        string operationName,
        string objective,
        JsonObject extractedArguments,
        bool beforeComputerUse = false)
    {
        JsonObject canonical = NormalizeIdentity(operationName, objective, extractedArguments);
        bool appOpen = string.Equals(operationName, "app.open", StringComparison.Ordinal);
        if (!appOpen && !string.Equals(operationName, "file.open", StringComparison.Ordinal))
        {
            return canonical;
        }

        bool withPersonRights = !OperationFloor.AdministratorAsked(objective);
        bool rightsAsDecided = !appOpen || (withPersonRights
            ? (bool?)canonical[ComputerUseMission.ForControlArgument] == true
            : !canonical.ContainsKey(ComputerUseMission.ForControlArgument));
        bool shown = !beforeComputerUse && !canonical.ContainsKey("foreground");
        bool placed = appOpen && (canonical.ContainsKey(ComputerUseMission.PlaceArgument)
            || canonical.ContainsKey(ComputerUseMission.PlaceValueArgument));
        if (rightsAsDecided && !shown && !placed)
        {
            return canonical;
        }

        JsonObject normalized = ReferenceEquals(canonical, extractedArguments)
            ? extractedArguments.DeepClone().AsObject()
            : canonical;
        if (appOpen && withPersonRights)
        {
            normalized[ComputerUseMission.ForControlArgument] = true;
        }
        else if (appOpen)
        {
            normalized.Remove(ComputerUseMission.ForControlArgument);
        }

        if (shown)
        {
            normalized["foreground"] = true;
        }

        normalized.Remove(ComputerUseMission.PlaceArgument);
        normalized.Remove(ComputerUseMission.PlaceValueArgument);

        return normalized;
    }

    private static JsonObject NormalizeIdentity(
        string operationName,
        string objective,
        JsonObject extractedArguments)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operationName);
        ArgumentException.ThrowIfNullOrWhiteSpace(objective);
        ArgumentNullException.ThrowIfNull(extractedArguments);
        if (string.Equals(operationName, "app.open", StringComparison.Ordinal)
            && extractedArguments["appId"] is JsonValue value
            && value.TryGetValue(out string? extractedAppId)
            && !string.IsNullOrWhiteSpace(extractedAppId)
            && NaturalApplicationRequestParser.TryNormalizeKnownAlias(
                extractedAppId,
                out string canonicalAppId))
        {
            // The model may preserve a natural alias such as "notepad".
            // Normalize at the common execution boundary so both direct and
            // compound plans receive the same canonical identity.
            JsonObject normalized = extractedArguments.DeepClone().AsObject();
            normalized["appId"] = canonicalAppId;
            return normalized;
        }

        return extractedArguments;
    }
}
