using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// uso-90: signing in to an account of the person's waits for their «sí» (src/Baxy.App/AccountFlow.cs). The looks are
/// those of banco diag-9dea, U06 c1-g10 (runs\diag-9dea-c1-g10-e2e\events.jsonl), as the reader returned them: the
/// YouTube page with its «Sign in» link, then Google's identifier page, where the model pressed «Sign in» and «Next»
/// unasked.
/// </summary>
[TestFixture]
public sealed class AccountFlowTests
{
    private const long Window = 262206;

    // The look before the first click (its controls as the view listed them; the ones this reads, verbatim).
    private static readonly JsonElement YouTubePage = Look(
        (6, "Edit", "Address and search bar", "https://www.youtube.com/watch?v=v8F6yJt1ULo", "collapsed"),
        (14, "Document", "Easy Homemade Bread | Crispy Crust and Fluffy Crumb - YouTube",
            "https://www.youtube.com/watch?v=v8F6yJt1ULo", "readonly"),
        (17, "ComboBox", "Search", null, "expanded"),
        (18, "Button", "Search", null, ""),
        (21, "Hyperlink", "Sign in",
            "https://accounts.google.com/ServiceLogin?service=youtube&uilel=3&passive=true&continue=https%3A%2F%2Fwww.youtube.com%2Fs",
            "readonly"),
        (23, "Hyperlink", "Learn more",
            "https://support.google.com/youtube/answer/3037019#zippy=%2Ccheck-that-youre-signed-into-youtube", "readonly"),
        (35, "Button", "Close tab", null, ""));

    // The look after it: the identifier page, «Email or phone» focused, «Next» below.
    private static readonly JsonElement IdentifierPage = Look(
        (6, "Edit", "Address and search bar",
            "https://accounts.google.com/v3/signin/identifier?continue=https://www.youtube.com/signin?action_handle_signin%3Dtrue%26a",
            "collapsed"),
        (13, "Document", "YouTube",
            "https://accounts.google.com/v3/signin/identifier?continue=https://www.youtube.com/signin?action_handle_signin%3Dtrue%26a",
            "readonly"),
        (14, "Edit", "Email or phone", null, "focused"),
        (17, "Button", "Next", null, ""),
        (18, "Button", "Create account", null, "collapsed"));

    [Test]
    public void TheSignInLinkOfU06WaitsForTheYesAndSaysWhy()
    {
        var flow = new AccountFlow();
        flow.Saw("input.visible.controls", Args("""{"application":"msedge","includeText":true}"""),
            OperationStatuses.Completed, YouTubePage);

        (string Cause, JsonObject Facts)? held = flow.Holds("input.visible.click",
            Args("""{"label":"Sign in","index":21,"window":262206}"""));

        Assert.That(held, Is.Not.Null);
        Assert.Multiple(() =>
        {
            Assert.That(held!.Value.Cause, Is.EqualTo(AccountFlow.Cause));
            Assert.That((bool?)held.Value.Facts["enters"], Is.True);
            Assert.That((string?)held.Value.Facts["page"], Is.EqualTo("accounts.google.com/ServiceLogin"));
        });
    }

    [Test]
    public void NextOnTheIdentifierPageOfU06WaitsForTheYes()
    {
        var flow = new AccountFlow();
        flow.Saw("input.visible.controls", Args("""{"application":"msedge"}"""), OperationStatuses.Completed,
            IdentifierPage);

        (string Cause, JsonObject Facts)? held = flow.Holds("input.visible.click",
            Args("""{"label":"Next","index":17,"window":262206}"""));

        Assert.That(held?.Cause, Is.EqualTo(AccountFlow.Cause));
        Assert.That((bool?)held?.Facts["enters"], Is.False);
        // Typing into it, or Enter there, goes on with it too.
        Assert.That(flow.Holds("input.text.type", Args("""{"index":14,"text":"ana@example.com"}"""))?.Cause,
            Is.EqualTo(AccountFlow.Cause));
        Assert.That(flow.Holds("input.key.press", Args("""{"key":"enter","window":262206}"""))?.Cause,
            Is.EqualTo(AccountFlow.Cause));
    }

    [Test]
    public void AfterASignInLinkRanItsWindowIsOnTheSignInPage()
    {
        var flow = new AccountFlow();
        JsonObject signIn = Args("""{"label":"Sign in","index":21,"window":262206}""");
        flow.Saw("input.visible.controls", Args("{}"), OperationStatuses.Completed, YouTubePage);
        flow.Saw("input.visible.click", signIn, OperationStatuses.Completed, null);

        Assert.That(flow.Holds("input.visible.click", Args("""{"label":"Next","window":262206}"""))?.Cause,
            Is.EqualTo(AccountFlow.Cause));
    }

    [TestCase("""{"label":"Search","index":18,"window":262206}""")]
    [TestCase("""{"label":"Learn more","index":23,"window":262206}""")]
    [TestCase("""{"label":"Close tab","window":262206}""")]
    public void OtherClicksOnAPageWithASignInLinkGo(string arguments)
    {
        var flow = new AccountFlow();
        flow.Saw("input.visible.controls", Args("{}"), OperationStatuses.Completed, YouTubePage);

        Assert.That(flow.Holds("input.visible.click", Args(arguments)), Is.Null);
    }

    [Test]
    public void APasswordFieldMakesAnyPageASignInPage()
    {
        var flow = new AccountFlow();
        flow.Saw("input.visible.controls", Args("{}"), OperationStatuses.Completed, Look(
            (2, "Document", "Foro de prueba", "https://foro.ejemplo.test/entrar", "readonly"),
            (5, "Edit", "Contraseña", null, "password"),
            (6, "Button", "Entrar", null, "")));

        (string Cause, JsonObject Facts)? held = flow.Holds("input.visible.click", Args("""{"label":"Entrar"}"""));
        Assert.That(held?.Cause, Is.EqualTo(AccountFlow.Cause));
        Assert.That((bool?)held?.Facts["passwordField"], Is.True);
    }

    [Test]
    public void NothingIsHeldWithNoLookOfThatWindowOrAfterANewSession()
    {
        var flow = new AccountFlow();
        Assert.That(flow.Holds("input.visible.click", Args("""{"label":"Next","window":262206}""")), Is.Null);

        flow.Saw("input.visible.controls", Args("{}"), OperationStatuses.Completed, IdentifierPage);
        Assert.That(flow.Holds("input.visible.click", Args("""{"label":"Next","window":1}""")), Is.Null);
        // A look that failed reads nothing.
        var other = new AccountFlow();
        other.Saw("input.visible.controls", Args("{}"), OperationStatuses.Failed, IdentifierPage);
        Assert.That(other.Holds("input.visible.click", Args("""{"label":"Next","window":262206}""")), Is.Null);

        flow.Reset();
        Assert.That(flow.Holds("input.visible.click", Args("""{"label":"Next","window":262206}""")), Is.Null);
    }

    // Shapes of an address, never a site's name: invented hosts.
    [TestCase("https://accounts.ejemplo.test/ServiceLogin?continue=x", true)]
    [TestCase("https://login.ejemplo.test/comun/oauth2/v2.0/authorize", true)]
    [TestCase("https://ejemplo.test/u/login?state=1", true)]
    [TestCase("https://tienda.ejemplo.test/users/sign_in", true)]
    [TestCase("https://tienda.ejemplo.test/ap/signin?openid.mode=checkid_setup", true)]
    [TestCase("https://ejemplo.test/entrar.php/login.php", true)]
    [TestCase("https://ejemplo.test/cb?response_type=code&client_id=abc&redirect_uri=x", true)]
    [TestCase("https://ejemplo.test/x?SAMLRequest=fVJN", true)]
    [TestCase("https://ejemplo.test/adfs?wa=wsignin1.0&wtrealm=x", true)]
    [TestCase("https://www.youtube.com/watch?v=v8F6yJt1ULo", false)]
    [TestCase("https://support.google.com/youtube/answer/3037019", false)]
    [TestCase("https://ejemplo.test/blog/como-hacer-login-seguro-en-tu-app", false)]
    [TestCase("https://ejemplo.test/?client_id=abc", false)]
    [TestCase("ftp://login.ejemplo.test/login", false)]
    public void ASignInAddressIsKnownByItsShape(string address, bool signIn)
    {
        Assert.That(AccountFlow.IsSignInAddress(new Uri(address)), Is.EqualTo(signIn));
    }

    [Test]
    public void ANavigationToASignInAddressWaitsAndOneToAnyOtherPageGoes()
    {
        var flow = new AccountFlow();
        Assert.That(flow.Holds("browser.navigate", Args("""{"url":"https://accounts.ejemplo.test/signin/identifier"}"""))
            ?.Cause, Is.EqualTo(AccountFlow.Cause));
        Assert.That(flow.Holds("browser.navigate", Args("""{"url":"https://www.ejemplo.test/watch?v=1"}""")), Is.Null);
    }

    private static JsonObject Args(string json) => JsonNode.Parse(json)!.AsObject();

    private static JsonElement Look(params (int Index, string Kind, string Name, string? Value, string State)[] controls)
    {
        var view = new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["title"] = "Easy Homemade Bread | Crispy Crust and Fluffy Crumb - YouTube - Profile 1 - Microsoft Edge",
                ["process"] = "msedge",
                ["hwnd"] = Window,
            },
            ["controls"] = new JsonArray([.. controls.Select(static control => (JsonNode)new JsonObject
            {
                ["i"] = control.Index,
                ["kind"] = control.Kind,
                ["name"] = control.Name,
                ["state"] = control.State,
                ["value"] = control.Value,
            })]),
        };
        using JsonDocument document = JsonDocument.Parse(view.ToJsonString());
        return document.RootElement.Clone();
    }
}
