using System.Text.Json;
using Baxy.Kernel.Operations;

namespace Baxy.Core.Operations;

/// <summary>
/// BAXY Renew cu (C04 variant, C05): the game store's own places as operations of their own. game.store.search opens the
/// store's search with what is searched (the place «results» of the game catalog's application) and game.store.page a
/// game's page by its title (the place «game», which its catalog resolves). Both are app.open with that place, in front;
/// nothing else. The model reached neither through app.open's place: it listed what is installed, asked which game, or
/// clicked through the store, in the live cases; an operation named for the act is what it chooses.
/// </summary>
internal sealed class GameStoreHandler(
    string operation,
    string place,
    string argument,
    Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> open)
    : IOperationHandler
{
    private const string Catalog = "steam";

    private readonly Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> _open =
        open ?? throw new ArgumentNullException(nameof(open));

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(operation);

    public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        if (invocation.Arguments.ValueKind != JsonValueKind.Object
            || !invocation.Arguments.TryGetProperty(argument, out JsonElement given)
            || given.ValueKind != JsonValueKind.String
            || given.GetString() is not { Length: > 0 } value
            || ApplicationPlaces.ApplicationOfCatalog(Catalog) is not { } application)
        {
            return ValueTask.FromResult(OperationOutcome.InvalidArguments(Definition, invocation.Arguments));
        }

        return _open(
            new OperationInvocation(
                invocation.RequestId,
                invocation.MissionId,
                invocation.InvocationId + ":open",
                JsonSerializer.SerializeToElement(
                    // What was asked is the person's words, never a catalog number: a title of digits alone
                    // («1942») is still searched as a title.
                    new OpenApplicationArguments(
                        application, Foreground: true, ForControl: true, Place: place, PlaceValue: value,
                        PlaceValueAsSaid: true),
                    CoreJsonContext.Default.OpenApplicationArguments)),
            cancellationToken);
    }
}
