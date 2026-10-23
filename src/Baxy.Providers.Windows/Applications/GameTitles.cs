using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.Applications;

/// <summary>
/// BAXY Renew cu (C04): a game's page is asked for by the game's title, and its application's address takes the game's
/// catalog number (<see cref="Baxy.Kernel.Operations.ApplicationPlaces.GameCatalogOf"/>). The catalog's own source
/// turns the title into the number and the name of the game found (for Steam, its installed games and the store's public
/// title search, where only the title leaves); null when nothing bears the title.
/// </summary>
public interface IGameTitles
{
    ValueTask<GameTitle?> FindAsync(string catalog, string title, CancellationToken cancellationToken);
}

/// <summary>A game of a catalog: its number there and its name.</summary>
public sealed record GameTitle(string Number, string Name);

/// <summary>
/// Renew al máximo (auditoría de flujos): the catalog's title search got no answer (no network, a timeout, an error
/// status, a body not read): nothing is known of the title, never «no game bears it».
/// </summary>
public sealed class GameTitleSearchFailedException(Exception inner)
    : Exception("The game catalog's title search got no answer.", inner);

public sealed class CatalogGameTitles : IGameTitles
{
    public async ValueTask<GameTitle?> FindAsync(string catalog, string title, CancellationToken cancellationToken)
    {
        if (!string.Equals(catalog, SteamLocalAdapter.GameCatalog, StringComparison.Ordinal))
        {
            return null;
        }

        SteamStoreTitle? game = await SteamLocalAdapter.PageTitleAsync(title, cancellationToken).ConfigureAwait(false);
        return game is null ? null : new GameTitle(game.AppId, game.Name);
    }
}
