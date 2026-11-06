using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Un juego fuera de la biblioteca de Steam. game.launch no depende de que el modelo siga la pista del recibo: si el
/// título no está en la biblioteca, la App busca en las aplicaciones instaladas y abre la que lo lleva, con un recibo que
/// dice qué abrió; varias, las dice sin abrir ninguna; ninguna, dice dónde miró sin afirmar que no está en el PC.
/// </summary>
[TestFixture]
public sealed class GameLaunchHandlerTests
{
    [Test]
    public async Task AGameTheLibraryHoldsGoesBySteamAndNothingElseIsLookedAt()
    {
        var look = new Looks(new ApplicationNameLook("Zarvok Launcher", [], []));
        var opened = new List<JsonElement>();

        OperationOutcome outcome = await Handler(
            new Steam(new ExternalCapabilityReceipt("game.launch", true, true, Json("""{"appId":"620"}"""), null)), look, opened)
            .ExecuteAsync(Invocation("""{"appId":"620","title":"Portal 2"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(look.Asked, Is.Empty);
            Assert.That(opened, Is.Empty);
        });
    }

    [TestCase("Zarvok Launcher")]
    [TestCase("Zarvok for Windows")]
    [TestCase("Zarvok")]
    public async Task ATitleOutsideTheLibraryOpensTheInstalledApplicationThatBearsItAndSaysWhich(string installed)
    {
        var look = new Looks(new ApplicationNameLook(installed, [], []));
        var opened = new List<JsonElement>();

        OperationOutcome outcome = await Handler(Outside("steam_installed_game_not_verified"), look, opened)
            .ExecuteAsync(Invocation("""{"appId":"12345","title":"Zarvok"}"""), CancellationToken.None);

        JsonElement result = outcome.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(look.Asked, Is.EqualTo(new[] { "Zarvok" }));
            Assert.That(opened, Has.Count.EqualTo(1));
            Assert.That(opened[0].GetProperty("appId").GetString(), Is.EqualTo(installed));
            Assert.That(opened[0].GetProperty("foreground").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("title").GetString(), Is.EqualTo("Zarvok"));
            Assert.That(result.GetProperty("displayName").GetString(), Is.EqualTo(installed));
            Assert.That(result.GetProperty("foundIn").GetString(), Is.EqualTo("start_menu"));
            Assert.That(result.GetProperty("next").GetString(),
                Does.Contain($"«{installed}»").And.Contain("not among the Steam games installed on this PC"));
        });
    }

    // What opened may be a launcher: the receipt says the application opened, never that the game runs.
    [Test]
    public async Task TheReceiptOfAnOpeningOutsideTheLibraryDoesNotSayTheGameRuns()
    {
        OperationOutcome outcome = await Handler(
            Outside("game_title_mismatch"), new Looks(new ApplicationNameLook("Zarvok Launcher", [], [])), [])
            .ExecuteAsync(Invocation("""{"appId":"620","title":"Zarvok"}"""), CancellationToken.None);

        Assert.That(outcome.Result!.Value.GetProperty("next").GetString(),
            Does.Contain("Whether the game itself is running was not read"));
    }

    [Test]
    public async Task SeveralApplicationsBearingTheTitleOpenNoneAndSayThemToAsk()
    {
        var opened = new List<JsonElement>();

        OperationOutcome outcome = await Handler(
            Outside("steam_installed_game_not_verified"),
            new Looks(new ApplicationNameLook(null, ["Tolvane Launcher", "Tolvane for Windows"], [])), opened)
            .ExecuteAsync(Invocation("""{"appId":"12345","title":"Tolvane"}"""), CancellationToken.None);

        JsonElement result = outcome.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(ApplicationOpenErrorCodes.ApplicationAmbiguous));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(opened, Is.Empty);
            Assert.That(result.GetProperty("candidates").EnumerateArray().Select(static name => name.GetString()),
                Is.EqualTo(new[] { "Tolvane Launcher", "Tolvane for Windows" }));
            Assert.That(result.GetProperty("next").GetString(), Does.Contain("ask").And.Contain("app_open"));
        });
    }

    // Ninguna: dice dónde miró, no afirma que no exista y no lleva a la tienda. La lista de Steam sigue en el recibo,
    // porque el título puede ser uno de esos juegos dicho de otra forma.
    [Test]
    public async Task NoApplicationBearingTheTitleSaysWhereItLookedAndNeverThatItIsNotThere()
    {
        var opened = new List<JsonElement>();

        OperationOutcome outcome = await Handler(
            Outside("game_title_mismatch"), new Looks(new ApplicationNameLook(null, [], ["Quorvanet"])), opened)
            .ExecuteAsync(Invocation("""{"appId":"620","title":"Quorvane"}"""), CancellationToken.None);

        JsonElement result = outcome.Result!.Value;
        string next = result.GetProperty("next").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(GameLaunchHandler.NotFound));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(opened, Is.Empty);
            Assert.That(result.GetProperty("lookedIn").EnumerateArray().Select(static place => place.GetString()),
                Is.EqualTo(new[] { "steam_installed_games", "start_menu" }));
            Assert.That(result.GetProperty("installedGames")[0].GetProperty("name").GetString(), Is.EqualTo("Portal 2"));
            Assert.That(result.GetProperty("nearNames")[0].GetString(), Is.EqualTo("Quorvanet"));
            Assert.That(next, Does.Contain("does not say it is not on this PC"));
            Assert.That(next, Does.Contain("store"));
        });
    }

    // Uso real 03-11 (G9): lo que Steam lista son sus juegos instalados, no la biblioteca de la cuenta. El recibo no dice
    // «no está en la biblioteca» y lleva lo que la caché de la biblioteca dice del título.
    [Test]
    public async Task AGameNotInstalledIsNeverSaidOutsideTheLibraryAndCarriesWhatTheCacheSays()
    {
        var steam = new Steam(new ExternalCapabilityReceipt("game.launch", false, false, Json("""
            {"version":1,"title":"Quorvane","installedGames":[{"appId":"620","name":"Portal 2"}],"outsideLibrary":true,
             "entitlement":{"appId":"700","owned":true,"installed":false,"state":"owned_not_installed"}}
            """), "steam_installed_game_not_verified"));

        OperationOutcome outcome = await Handler(steam, new Looks(new ApplicationNameLook(null, [], [])), [])
            .ExecuteAsync(Invocation("""{"title":"Quorvane"}"""), CancellationToken.None);

        JsonElement result = outcome.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(GameLaunchHandler.NotFound));
            Assert.That(result.GetProperty("entitlement").GetProperty("state").GetString(),
                Is.EqualTo("owned_not_installed"));
            Assert.That(result.GetProperty("lookedIn")[0].GetString(), Is.EqualTo("steam_installed_games"));
            Assert.That(result.GetProperty("next").GetString(),
                Does.Not.Contain("Steam library").And.Contain("game_install_named"));
        });
    }

    // Un catálogo que no se pudo leer no se cuenta como mirado.
    [Test]
    public async Task AStartMenuThatCouldNotBeReadIsNotSaidAsLookedIn()
    {
        OperationOutcome outcome = await Handler(Outside("steam_installed_game_not_verified"), new Looks(null), [])
            .ExecuteAsync(Invocation("""{"appId":"12345","title":"Quorvane"}"""), CancellationToken.None);

        Assert.That(outcome.Result!.Value.GetProperty("lookedIn").EnumerateArray().Select(static place => place.GetString()),
            Is.EqualTo(new[] { "steam_installed_games" }));
    }

    // Lo que el proveedor de Steam no marca como fuera de su biblioteca (el título es de un juego que tiene, otro fallo) no
    // sale de Steam.
    [TestCase("""{"version":1,"appId":"620","name":"Portal 2","title":"portal 2"}""", "steam_act_not_declared")]
    [TestCase("""{"version":1,"appId":"620"}""", "game_title_required")]
    public async Task AFailureThatIsNotATitleOutsideTheLibraryStaysSteams(string receipt, string code)
    {
        var look = new Looks(new ApplicationNameLook("Zarvok Launcher", [], []));
        var opened = new List<JsonElement>();

        OperationOutcome outcome = await Handler(
            new Steam(new ExternalCapabilityReceipt("game.launch", false, false, Json(receipt), code)), look, opened)
            .ExecuteAsync(Invocation("""{"appId":"620","title":"Portal 2"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(code));
            Assert.That(look.Asked, Is.Empty);
            Assert.That(opened, Is.Empty);
        });
    }

    // Lo que falla al abrir la aplicación encontrada lo dice la apertura, con su código y su duda sobre el efecto.
    [Test]
    public async Task AFailedOpeningOutsideTheLibraryKeepsItsOwnCode()
    {
        GameLaunchHandler handler = new(
            new ExternalCapabilityHandler("game.launch", Outside("steam_installed_game_not_verified")),
            new Looks(new ApplicationNameLook("Zarvok Launcher", [], [])),
            static (_, _) => ValueTask.FromResult(OperationOutcome.Failure("verification_failed", effectMayHaveOccurred: true)));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"12345","title":"Zarvok"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
        });
    }

    private static GameLaunchHandler Handler(
        IExternalCapabilityProvider steam, IApplicationOpenProvider apps, List<JsonElement> opened) =>
        new(new ExternalCapabilityHandler("game.launch", steam), apps, (invocation, _) =>
        {
            opened.Add(invocation.Arguments.Clone());
            string name = invocation.Arguments.GetProperty("appId").GetString()!;
            return ValueTask.FromResult(OperationOutcome.Success(
                Json($$"""{"appId":{{JsonSerializer.Serialize(name)}},"displayName":{{JsonSerializer.Serialize(name)}}}""")));
        });

    private static Steam Outside(string code) => new(new ExternalCapabilityReceipt("game.launch", false, false, Json("""
        {"version":1,"appId":"620","title":"T","installedGames":[{"appId":"620","name":"Portal 2"}],"outsideLibrary":true,"next":"old"}
        """), code));

    private static JsonElement Json(string text)
    {
        using JsonDocument document = JsonDocument.Parse(text);
        return document.RootElement.Clone();
    }

    private static OperationInvocation Invocation(string arguments) =>
        new("request", "mission", "invocation", Json(arguments));

    private sealed class Steam(ExternalCapabilityReceipt receipt) : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            ValueTask.FromResult(receipt);
    }

    private sealed class Looks(ApplicationNameLook? look) : IApplicationOpenProvider
    {
        internal List<string> Asked { get; } = [];

        public ValueTask<ApplicationOpenResult> OpenAsync(ApplicationOpenRequest request, CancellationToken cancellationToken) =>
            throw new InvalidOperationException("the handler opens through app.open");

        public ValueTask<ApplicationNameLook?> LookForAsync(string name, CancellationToken cancellationToken)
        {
            Asked.Add(name);
            return ValueTask.FromResult(look);
        }
    }
}
