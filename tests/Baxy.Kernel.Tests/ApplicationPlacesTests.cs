using System.Text.Json;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// Estabilización, encargo C: the places of an application with an address of their own are one data file
/// (src/baxy_mind/data/app_places.v1.json), read here and held to the file's own examples. The kernel takes a place only by a name the data declare (app.open's schema) and composes its
/// address only from the application's own entry; nothing else is ever opened.
/// </summary>
[TestFixture]
public sealed class ApplicationPlacesTests
{
    private static JsonDocument Data()
    {
        using Stream stream = typeof(ApplicationPlaces).Assembly.GetManifestResourceStream("Baxy.Kernel.AppPlaces.json")!;
        return JsonDocument.Parse(stream);
    }

    [Test]
    public void EveryExampleOfTheDataComposesItsAddress()
    {
        using JsonDocument data = Data();
        JsonElement[] examples = [.. data.RootElement.GetProperty("examples").EnumerateArray()];
        Assert.That(examples, Is.Not.Empty);
        Assert.Multiple(() =>
        {
            foreach (JsonElement example in examples)
            {
                string? value = example.TryGetProperty("value", out JsonElement said) ? said.GetString() : null;
                Assert.That(
                    ApplicationPlaces.Address(
                        example.GetProperty("application").GetString(), example.GetProperty("place").GetString(), value),
                    Is.EqualTo(example.GetProperty("address").GetString()),
                    example.GetProperty("goal").GetString());
            }
        });
    }

    [TestCase("steam", "library", null, "steam://open/games")]
    [TestCase("Spotify", "results", "Los Bunkers", "spotify:search:Los%20Bunkers")]
    // A place of another application, a place undeclared, a slot left empty or filled where there is none, a game that is
    // no number, a text with control characters: no address.
    [TestCase("Steam", "home", null, null)]
    // A place the data name without an address (Spotify's «Tu biblioteca», measured: no protocol reaches it).
    [TestCase("Spotify", "library", null, null)]
    [TestCase("Paint", "library", null, null)]
    [TestCase("Steam", "results", null, null)]
    [TestCase("Steam", "library", "x", null)]
    [TestCase("Steam", "game", "cuphead", null)]
    [TestCase("Steam", "results", "a\nb", null)]
    public void OnlyWhatTheDataDeclareHasAnAddress(string application, string place, string? value, string? address) =>
        Assert.That(ApplicationPlaces.Address(application, place, value), Is.EqualTo(address));

    [Test]
    public void ASearchedTextIsEscapedIntoItsSlotAndNeverLeavesIt()
    {
        string? address = ApplicationPlaces.Address("Steam", "results", "x&appid=1/../?#");
        Assert.That(address, Does.StartWith("steam://openurl/https://store.steampowered.com/search/?term=x%26appid%3D1%2F.."));
    }

    // The kernel itself refuses an address whose scheme its application does not declare, or with an unknown slot: the
    // data are refused whole, never half read.
    [TestCase("""{"applications":{"A":{"schemes":["a"],"places":{"p":{"address":"b://x"}}}}}""")]
    [TestCase("""{"applications":{"A":{"schemes":["a"],"places":{"p":{"address":"a://{other}"}}}}}""")]
    [TestCase("""{"applications":{"A":{"schemes":["a"],"places":{"p":{"address":"a://{query}/{game}"}}}}}""")]
    public void DataWithAnUndeclaredSchemeOrSlotIsRefused(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        Assert.Throws<InvalidDataException>(() => ApplicationPlaces.Read(document));
    }

    // app.open takes a place only by a name the data declare: anything else is invalid arguments for the kernel, in
    // every confirmation mode (the schema is checked before the policy).
    [TestCase("""{"appId":"Steam"}""", true)]
    [TestCase("""{"appId":"Steam","place":"library"}""", true)]
    [TestCase("""{"appId":"Steam","place":"results","placeValue":"Cuphead"}""", true)]
    [TestCase("""{"appId":"Steam","place":"steam://open/console"}""", false)]
    [TestCase("""{"appId":"Steam","place":"console"}""", false)]
    [TestCase("""{"appId":"Steam","place":"library","placeValue":" "}""", false)]
    public void AppOpenTakesOnlyADeclaredPlace(string json, bool valid)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("app.open");
        using JsonDocument arguments = JsonDocument.Parse(json);
        Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, descriptor.ArgumentsSchema), Is.EqualTo(valid));
    }

    // Encargo imp-steam: a game catalog's acts are its application's own addresses with the game's number, and the
    // names of the control of its own dialog that confirms them; nothing that is not a catalog number fills the slot.
    [TestCase("steam", "install", "40800", "steam://install/40800", "Instalar|Install")]
    [TestCase("steam", "uninstall", "40800", "steam://uninstall/40800", "Desinstalar|Uninstall")]
    [TestCase("steam", "launch", "268910", "steam://rungameid/268910", "Jugar|Play")]
    [TestCase("steam", "install", "super meat boy", null, null)]
    [TestCase("steam", "install", "40800/../console", null, null)]
    [TestCase("steam", "console", "40800", null, null)]
    [TestCase("epic", "install", "40800", null, null)]
    public void AGameActIsTheDataAddressWithItsConfirmingNames(
        string catalog, string act, string game, string? address, string? confirm)
    {
        ApplicationPlaces.GameAct? declared = ApplicationPlaces.GameActOf(catalog, act, game);
        Assert.Multiple(() =>
        {
            Assert.That(declared?.Address, Is.EqualTo(address));
            Assert.That(declared is null ? null : string.Join('|', declared.Confirm), Is.EqualTo(confirm));
        });
    }

    // The store's title search sends the title alone, escaped into its slot; a blank or control-character title sends nothing.
    [Test]
    public void ATitleSearchSendsTheTitleAloneEscaped()
    {
        ApplicationPlaces.TitleSearch? search = ApplicationPlaces.TitleSearchOf("steam", " Super Meat Boy&cc=XX ");
        Assert.Multiple(() =>
        {
            Assert.That(search?.Address, Does.StartWith("https://store.steampowered.com/api/storesearch/?term=Super%20Meat%20Boy%26cc%3DXX&"));
            Assert.That((search?.List, search?.Id, search?.Name), Is.EqualTo(("items", "id", "name")));
            Assert.That(ApplicationPlaces.TitleSearchOf("steam", " "), Is.Null);
            Assert.That(ApplicationPlaces.TitleSearchOf("steam", "a\u0007b"), Is.Null);
            Assert.That(ApplicationPlaces.TitleSearchOf("spotify", "Los Bunkers"), Is.Null);
        });
    }

    // An act with a scheme its application does not declare or without the game's slot, a confirming name left blank, an
    // act or a title search of an application with no game catalog, a title search that is not https: refused whole.
    [TestCase("""{"applications":{"A":{"schemes":["a"],"gameCatalog":"a","places":{},"acts":{"x":{"address":"b://{game}"}}}}}""")]
    [TestCase("""{"applications":{"A":{"schemes":["a"],"gameCatalog":"a","places":{},"acts":{"x":{"address":"a://run"}}}}}""")]
    [TestCase("""{"applications":{"A":{"schemes":["a"],"gameCatalog":"a","places":{},"acts":{"x":{"address":"a://{game}","confirm":[" "]}}}}}""")]
    [TestCase("""{"applications":{"A":{"schemes":["a"],"places":{},"acts":{"x":{"address":"a://{game}"}}}}}""")]
    [TestCase("""{"applications":{"A":{"schemes":["a"],"gameCatalog":"a","places":{},"titles":{"address":"http://s/?q={title}","list":"l","id":"i","name":"n"}}}}""")]
    [TestCase("""{"applications":{"A":{"schemes":["a"],"gameCatalog":"a","places":{},"titles":{"address":"https://s/?q=x","list":"l","id":"i","name":"n"}}}}""")]
    public void DataWithAWrongActOrTitleSearchIsRefused(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        Assert.Throws<InvalidDataException>(() => ApplicationPlaces.Read(document));
    }

    // No act is a place app.open takes: the dialog of an install or an uninstall opens only by its typed operation.
    [TestCase("""{"appId":"Steam","place":"install","placeValue":"40800"}""")]
    [TestCase("""{"appId":"Steam","place":"uninstall","placeValue":"40800"}""")]
    [TestCase("""{"appId":"Steam","place":"launch","placeValue":"40800"}""")]
    public void NoActIsAPlaceOfAppOpen(string json)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("app.open");
        using JsonDocument arguments = JsonDocument.Parse(json);
        Assert.That(OperationArgumentValidator.IsValid(arguments.RootElement, descriptor.ArgumentsSchema), Is.False);
    }

    [Test]
    public void ThePlaceNamesAreTheDataOnesSortedAndDistinct()
    {
        using JsonDocument data = Data();
        string[] declared =
        [
            .. data.RootElement.GetProperty("applications").EnumerateObject()
                .SelectMany(application => application.Value.GetProperty("places").EnumerateObject()
                    .Where(place => place.Value.TryGetProperty("address", out _)).Select(place => place.Name))
                .Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal),
        ];
        Assert.That(ApplicationPlaces.PlaceNames, Is.EqualTo(declared));
    }
}
