using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;

namespace Baxy.Core.Operations;

/// <summary>
/// Ajuste c5 (un juego con su propio lanzador o de la tienda de Windows): la lista que game.launch enseña es la biblioteca
/// de Steam, y su recibo pedía al modelo un app_open que a veces no llegaba, o que no encontraba «X» porque en el menú
/// Inicio es «X Launcher». Con un título fuera de esa biblioteca, la App misma mira las aplicaciones instaladas: abre la
/// única que lleva el título, por app.open, y dice cuál; varias, las dice para preguntar; ninguna, dice dónde miró, sin
/// afirmar que no esté en el PC. Un juego de la biblioteca sigue yendo por Steam, y cualquier otro fallo de Steam es de Steam.
/// </summary>
internal sealed class GameLaunchHandler(
    ExternalCapabilityHandler steam,
    IApplicationOpenProvider applications,
    Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> open)
    : IOperationHandler, IInvocationPreflight
{
    internal const string NotFound = "game_not_installed_in_steam_or_start_menu";

    public OperationDefinition Definition => steam.Definition;

    public ValueTask<InvocationPreflightResult> PreflightAsync(JsonElement arguments, CancellationToken cancellationToken) =>
        steam.PreflightAsync(arguments, cancellationToken);

    public bool MayRaise(JsonElement arguments) => steam.MayRaise(arguments);

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        OperationOutcome inSteam = await steam.ExecuteAsync(invocation, cancellationToken).ConfigureAwait(false);
        if (inSteam.Succeeded
            || inSteam.Result is not { ValueKind: JsonValueKind.Object } refused
            || !refused.TryGetProperty("outsideLibrary", out JsonElement outside) || !outside.GetBoolean()
            || invocation.Arguments.GetProperty("title").GetString() is not { } title)
        {
            return inSteam;
        }

        ApplicationNameLook? look = await applications.LookForAsync(title, cancellationToken).ConfigureAwait(false);
        if (look?.Name is { } name)
        {
            OperationOutcome opened = await open(
                new OperationInvocation(
                    invocation.RequestId,
                    invocation.MissionId,
                    invocation.InvocationId + ":open",
                    JsonSerializer.SerializeToElement(
                        new OpenApplicationArguments(name, Foreground: true, ForControl: true),
                        CoreJsonContext.Default.OpenApplicationArguments)),
                cancellationToken).ConfigureAwait(false);
            return opened.Succeeded ? opened with { Result = Told(opened.Result, title, name) } : opened;
        }

        if (look is { Several.Count: > 0 })
        {
            return OperationOutcome.Failure(
                ApplicationOpenErrorCodes.ApplicationAmbiguous,
                result: Facts(writer =>
                {
                    writer.WriteString("title", title);
                    WriteNames(writer, "candidates", look.Several);
                    writer.WriteString(
                        "next",
                        $"«{title}» is not among the Steam games installed on this PC and several installed applications bear "
                            + "it; nothing was "
                            + "opened: ask the person which one, and app_open with that name opens it");
                }));
        }

        return OperationOutcome.Failure(
            NotFound,
            result: Facts(writer =>
            {
                writer.WriteString("title", title);
                WriteNames(writer, "lookedIn",
                    look is null ? ["steam_installed_games"] : ["steam_installed_games", "start_menu"]);
                if (look is { Near.Count: > 0 })
                    WriteNames(writer, "nearNames", look.Near);
                if (refused.TryGetProperty("installedGames", out JsonElement games))
                {
                    writer.WritePropertyName("installedGames");
                    games.WriteTo(writer);
                }

                // Uso real 03-11 (G9): what the account's library cache says of the title, read by Steam's adapter.
                if (refused.TryGetProperty("entitlement", out JsonElement entitlement))
                {
                    writer.WritePropertyName("entitlement");
                    entitlement.WriteTo(writer);
                }

                writer.WriteString(
                    "next",
                    $"nothing was opened: «{title}» is neither among the Steam games installed on this PC nor among the "
                        + (look is null ? "games read, and the Start menu could not be read" : "Start menu's applications")
                        + ", which does not say it is not on this PC (installed without a Start entry, or under another "
                        + "name, it is not seen; game_installed_named looks in Epic) nor that the person does not own it "
                        + "(entitlement, when present, is what Steam's library cache says; game_install_named installs a "
                        + "game the account owns). Say where it was looked for; the store is for buying a game, not for "
                        + "opening this one");
            }));
    }

    // The opening's own receipt with what the person asked for, where it was found and what it does not say.
    private static JsonElement Told(JsonElement? receipt, string title, string name) => Facts(writer =>
    {
        if (receipt is { ValueKind: JsonValueKind.Object } opened)
        {
            foreach (JsonProperty property in opened.EnumerateObject())
            {
                if (property.Name is not ("title" or "foundIn" or "next" or "version"))
                    property.WriteTo(writer);
            }
        }

        writer.WriteString("title", title);
        writer.WriteString("foundIn", "start_menu");
        writer.WriteString(
            "next",
            $"«{title}» is not among the Steam games installed on this PC; the installed application «{name}» was opened "
                + "for it. Whether the game "
                + "itself is running was not read: if this is its launcher, starting it is one step more");
    });

    private static void WriteNames(Utf8JsonWriter writer, string property, IReadOnlyList<string> names)
    {
        writer.WriteStartArray(property);
        foreach (string name in names)
            writer.WriteStringValue(name);
        writer.WriteEndArray();
    }

    private static JsonElement Facts(Action<Utf8JsonWriter> write)
    {
        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            write(writer);
            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.ToArray());
        return document.RootElement.Clone();
    }
}
