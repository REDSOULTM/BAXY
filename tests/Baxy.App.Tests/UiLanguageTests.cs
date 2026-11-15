using System.Globalization;
using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Steam (2026-11-04): BAXY's own words come out in the interface's language, which the view chooses
/// (PUT /settings/language) and Windows decides until it does. ING5 (2026-11-13): the mind is told the language chosen
/// with its catalog and relaunched when it changes; what the App itself sends for the model stays in Spanish.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class UiLanguageTests
{
    [TearDown]
    public void BackToSpanish() => UiLanguage.Use(UiLanguage.Spanish);

    [TestCase("es-MX", "es")]
    [TestCase("es-ES", "es")]
    [TestCase("en-US", "en")]
    [TestCase("fr-FR", "en")]
    public void AutoAndNoChoiceAreWindowsDisplayLanguage(string culture, string language)
    {
        CultureInfo before = CultureInfo.CurrentUICulture;
        try
        {
            CultureInfo.CurrentUICulture = CultureInfo.GetCultureInfo(culture);
            UiLanguage.Use(null);
            string none = UiLanguage.Current;
            UiLanguage.Use(UiLanguage.Auto);
            JsonObject general = new FieldSettings(string.Empty).GeneralJson((null, null));

            Assert.Multiple(() =>
            {
                Assert.That(none, Is.EqualTo(language));
                Assert.That(UiLanguage.Current, Is.EqualTo(language));
                Assert.That((string?)general["language"], Is.EqualTo("auto"));
                Assert.That((string?)general["languageInUse"], Is.EqualTo(language));
            });
        }
        finally
        {
            CultureInfo.CurrentUICulture = before;
        }
    }

    [Test]
    public void EveryOperationHasATitleInEnglish()
    {
        FieldStepProjection.Validate();
        UiLanguage.Use(UiLanguage.English);
        string[] untitled = [.. ProductCatalog.ToolDescriptors.Select(static d => d.Name)
            .Where(static name => FieldStepProjection.Title(name) == name)];

        Assert.That(untitled, Is.Empty);
    }

    [Test]
    public void AStepIsSaidInEnglishWhenTheInterfaceIsInEnglish()
    {
        var arguments = new JsonObject { ["application"] = "Spotify" };
        string spanish = FieldStepProjection.Label("app.open", arguments);
        UiLanguage.Use(UiLanguage.English);
        JsonObject declined = FieldStepProjectionTests.Finished(OperationStatuses.Rejected, verified: false, new JsonObject(),
            errorCode: "declined_by_person", english: true);
        JsonObject verified = FieldStepProjectionTests.Finished(OperationStatuses.Completed, verified: true,
            new JsonObject { ["status"] = "completed", ["verification"] = OperationVisibleFacts.VerificationReadback },
            english: true);

        Assert.Multiple(() =>
        {
            Assert.That(spanish, Is.EqualTo("Abrir app · Spotify"));
            Assert.That(FieldStepProjection.Label("app.open", arguments), Is.EqualTo("Open app · Spotify"));
            Assert.That((string?)declined["reason"], Is.EqualTo("Not run: you said no"));
            Assert.That((string?)verified["obs"], Is.EqualTo("Verified"));
            Assert.That(FieldStepProjection.Catalog()["groups"]!.AsArray().Select(static g => (string?)g!["name"]),
                Does.Contain("Web and browser").And.Not.Contain("Web y navegador"));
        });
    }

    // Revisión (2026-11-04): a chip read the language once for its label and again for its reason; one that changed
    // between both was half in each. Every word of a step and a card is in the language its caller passed.
    [Test]
    public void AStepOrACardIsWhollyInTheLanguageItWasGiven()
    {
        UiLanguage.Use(UiLanguage.Spanish);
        JsonObject step = FieldStepProjectionTests.Finished(OperationStatuses.Completed, verified: true,
            new JsonObject
            {
                ["status"] = "completed", ["verification"] = OperationVisibleFacts.VerificationUnchanged, ["muted"] = true,
            },
            english: true);
        JsonObject card = FieldStepProjection.Card("k1", "confirm", "system.recyclebin.empty", new JsonObject(),
            OperationRisks.RecoverableDelete, DateTimeOffset.UtcNow.AddMinutes(2), context: null, english: true);

        Assert.Multiple(() =>
        {
            Assert.That((string?)step["label"], Is.EqualTo("Open app"));
            Assert.That((string?)step["obs"], Is.EqualTo("Already set · muted: yes"));
            Assert.That((string?)card["title"], Is.EqualTo("Empty the Recycle Bin"));
            Assert.That((string?)card["risk"], Is.EqualTo("deletes data"));
        });
    }

    [Test]
    public void TheTrayMenuSaysItsStateInEnglish()
    {
        UiLanguage.Use(UiLanguage.English);

        Assert.Multiple(() =>
        {
            Assert.That(Presentation.TrayMenu.StateLabel(new(Listening: false, MicAvailable: true, Powered: false, Ready: true)),
                Is.EqualTo("Asleep"));
            Assert.That(Presentation.TrayMenu.StateLabel(new(Listening: true, MicAvailable: true, Powered: true, Ready: true)),
                Is.EqualTo("Active · answers to “BAXY”"));
        });
    }

    [Test]
    public void TheThemesTheModelReadsStaySpanishInAnEnglishInterface()
    {
        UiLanguage.Use(UiLanguage.English);
        JsonObject request = MindSidecarClient.CreateCatalogConfigureRequest(
            [.. ProductCatalog.ToolDescriptors.Select(static descriptor =>
                ProductCatalog.CreateToolDescriptor(new OperationDefinition(descriptor)))],
            applicationCatalog: null);
        JsonObject Tool(string name) => request["capabilities"]!.AsArray().OfType<JsonObject>()
            .Single(tool => (string?)tool["name"] == name);

        Assert.Multiple(() =>
        {
            Assert.That((string?)Tool("web.search")["group"], Is.EqualTo("Web y navegador"));
            Assert.That((string?)Tool("backup.create")["group"], Is.EqualTo("Copias de seguridad"));
        });
    }

    // ING5 (owner's decision of 2026-11-13: the language is a setting, and choosing it puts all the model reads in it):
    // the mind is told the language chosen with its catalog, and keeps it for its life: the installed list arriving
    // after another was chosen is sent in the one it was started in (another language is another mind, below).
    [TestCase("en", "es")]
    [TestCase("es", "en")]
    public async Task TheMindIsConfiguredInTheLanguageChosenAndKeepsItForItsLife(string language, string other)
    {
        using var fake = new FakeMind();
        UiLanguage.Use(language);
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        UiLanguage.Use(other);
        var arrived = new ApplicationCatalogSnapshot(ApplicationCatalogContract.CurrentVersion, true, true, ["Bloc de notas"]);

        bool updated = await mind.UpdateApplicationCatalogAsync(arrived, TimeSpan.FromSeconds(10), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(updated, Is.True);
            Assert.That(fake.Requests("catalog.configure").Select(static r => (string?)r["lang"]),
                Is.EqualTo(new[] { language, language }));
            Assert.That(mind.ConfiguredLanguage, Is.EqualTo(language));
        });
    }

    [Test]
    public void AnotherLanguageThanTheRunningMindsNeedsARelaunchOnce()
    {
        var language = new MindLanguage();
        UiLanguage.Use(UiLanguage.English);
        bool withNoMindYet = language.NeedsSwitch;
        language.Started(UiLanguage.Spanish);
        bool chosenAfterItsStart = language.NeedsSwitch;
        language.Started(UiLanguage.Current);
        bool relaunched = language.NeedsSwitch;
        CultureInfo before = CultureInfo.CurrentUICulture;
        try
        {
            // «auto» on a Windows in English stands for the language the mind runs in: no change.
            CultureInfo.CurrentUICulture = CultureInfo.GetCultureInfo("en-US");
            UiLanguage.Use(UiLanguage.Auto);
            bool autoThatIsTheSame = language.NeedsSwitch;
            CultureInfo.CurrentUICulture = CultureInfo.GetCultureInfo("es-ES");
            bool autoThatIsTheOther = language.NeedsSwitch;

            Assert.Multiple(() =>
            {
                Assert.That(withNoMindYet, Is.False, "the next start takes it");
                Assert.That(chosenAfterItsStart, Is.True);
                Assert.That(relaunched, Is.False);
                Assert.That(autoThatIsTheSame, Is.False);
                Assert.That(autoThatIsTheOther, Is.True);
            });
        }
        finally
        {
            CultureInfo.CurrentUICulture = before;
        }
    }

    [Test]
    public async Task ALanguageChosenInTheViewTakesDownTheMindOfTheOtherAndTheNextIsConfiguredInIt()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            (int same, JsonObject _) = await view.SendAsync("PUT", "/settings/language", new JsonObject { ["lang"] = "es" });
            bool keptUp = viewModel.IsMindReady && !viewModel.ExternalModelState.Switching;
            (int status, JsonObject _) = await view.SendAsync("PUT", "/settings/language", new JsonObject { ["lang"] = "en" });
            // With no engine here no mind starts after the one in Spanish is taken down: the next start is in English.
            bool down = await ViewModelHarness.UntilAsync(() => !viewModel.IsMindReady && !viewModel.ExternalModelState.Switching);
            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.Multiple(() =>
            {
                Assert.That((same, status), Is.EqualTo((200, 200)));
                Assert.That(keptUp, Is.True, "the language it runs in: no relaunch");
                Assert.That(down, Is.True, "the mind that reads Spanish does not go on in an English BAXY");
                Assert.That(viewModel.IsMindReady, Is.True);
                Assert.That(fake.Requests("catalog.configure").Select(static r => (string?)r["lang"]),
                    Is.EqualTo(new[] { "es", "en" }));
                Assert.That(viewModel.LanguageState.NeedsSwitch, Is.False);
            });
        }
    }

    // ING5 (owner, 13-11: everything by voice): the language baxy.settings.set wrote in the settings' file is the view's
    // choice: BAXY's own words follow it at once and the mind of the language before is taken down once the turn ends.
    // Another setting changed by voice leaves the language in use as it is.
    [Test]
    public async Task ALanguageChosenByVoiceIsUsedAtOnceAndTakesDownTheMindOfTheOther()
    {
        using var fake = new FakeMind();
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
            object loop = typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
            var host = (NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!;
            NativeTurnStep Set(string setting, string value) => new("baxy.settings.set",
                new JsonObject { ["setting"] = setting, ["value"] = value }, OperationStatuses.Completed, true, null, 12,
                "{\"status\":\"completed\",\"verification\":\"readback\"}", "c1", Sent: true);

            // The engine wrote both (OwnSettingsHandler); the step of the other setting comes first.
            Baxy.Kernel.Policy.FieldSettingsStore.Write(fake.DataRoot, new JsonObject { ["language"] = "en", ["overlay"] = false });
            host.StepCompleted!(Set("overlay", "off"));
            string afterAnother = UiLanguage.Current;
            bool keptUp = viewModel.IsMindReady && !viewModel.LanguageState.NeedsSwitch;
            host.StepCompleted!(Set("language", "english"));
            string afterTheLanguage = UiLanguage.Current;
            bool down = await ViewModelHarness.UntilAsync(() => !viewModel.IsMindReady && !viewModel.ExternalModelState.Switching);

            Assert.Multiple(() =>
            {
                Assert.That(afterAnother, Is.EqualTo("es"));
                Assert.That(keptUp, Is.True);
                Assert.That(afterTheLanguage, Is.EqualTo("en"));
                Assert.That(down, Is.True, "the mind that reads Spanish does not go on in an English BAXY");
            });
        }
    }

    [TestCase("en")]
    [TestCase("es")]
    public async Task TheVoiceIsAskedToSpeakTheInterfacesLanguage(string language)
    {
        using var fake = new FakeMind();
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        UiLanguage.Use(language);

        bool accepted = await mind.VoiceSpeakAsync("Hello.", TimeSpan.FromSeconds(5), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(accepted, Is.True);
            Assert.That(fake.Requests("voice.speak").Select(static r => (string?)r["lang"]), Is.EqualTo(new[] { language }));
        });
    }

    [TestCase("en")]
    [TestCase("es")]
    public async Task ATurnTellsTheMindTheInterfacesLanguage(string language)
    {
        using var fake = new FakeMind();
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        UiLanguage.Use(language);

        MindStep? step = await mind.DecideAsync("hola", pendingConfirmation: null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(step, Is.Not.Null);
            Assert.That(fake.Requests("turn.decide").Select(static r => (string?)r["lang"]), Is.EqualTo(new[] { language }));
            Assert.That(fake.Requests("turn.decide").Select(static r => (string?)r["text"]), Is.EqualTo(new[] { "hola" }));
        });
    }

    [Test]
    public async Task TheHostKeepsThePersonsChoiceAndRefusesAnyOtherWord()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            (int _, JsonObject unset) = await view.SendAsync("GET", "/settings/general");
            (int status, JsonObject body) = await view.SendAsync("PUT", "/settings/language", new JsonObject { ["lang"] = "en" });
            string current = UiLanguage.Current;
            (int _, JsonObject general) = await view.SendAsync("GET", "/settings/general");
            (int french, JsonObject refused) = await view.SendAsync("PUT", "/settings/language", new JsonObject { ["lang"] = "fr" });
            (int number, JsonObject _) = await view.SendAsync("PUT", "/settings/language", new JsonObject { ["lang"] = 5 });
            string afterRefusals = UiLanguage.Current;
            (int auto, JsonObject automatic) = await view.SendAsync("PUT", "/settings/language", new JsonObject { ["lang"] = "auto" });

            Assert.Multiple(() =>
            {
                Assert.That((string?)unset["language"], Is.EqualTo("auto"), "no choice yet");
                Assert.That(status, Is.EqualTo(200));
                Assert.That((string?)body["language"], Is.EqualTo("en"));
                Assert.That((string?)body["languageInUse"], Is.EqualTo("en"));
                Assert.That(current, Is.EqualTo("en"));
                Assert.That((string?)general["language"], Is.EqualTo("en"));
                Assert.That((string?)general["languageInUse"], Is.EqualTo("en"));
                Assert.That(french, Is.EqualTo(400));
                Assert.That((string?)refused["error"], Is.EqualTo("invalid_language"));
                Assert.That(number, Is.EqualTo(400));
                Assert.That(afterRefusals, Is.EqualTo("en"));
                Assert.That(auto, Is.EqualTo(200));
                Assert.That((string?)automatic["language"], Is.EqualTo("auto"));
                Assert.That((string?)automatic["languageInUse"], Is.EqualTo(UiLanguage.Resolve(null)));
                Assert.That(new FieldSettings(fake.DataRoot).Language, Is.EqualTo("auto"), "kept for the next start");
            });
        }
    }

    [Test]
    public async Task TheInternetLogTheModelReadsIsInEnglishInAnEnglishView()
    {
        using var fake = new FakeMind();
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            UiLanguage.Use(UiLanguage.English);
            var step = new NativeTurnStep("web.search", new JsonObject { ["query"] = "clima" }, OperationStatuses.Completed,
                true, null, 12, "{\"status\":\"completed\",\"verification\":\"output_only\"}", "c1", Sent: true);
            const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
            object loop = typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
            var host = (NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!;
            host.StepCompleted!(step);
            JsonObject shown = view.Sink.Items.Single(static i => (string?)i["who"] == "baxy")["steps"]!.AsArray()
                .OfType<JsonObject>().Single();
            Baxy.Kernel.Operations.OperationOutcome read = OwnReadings.Internet(view.Sink.Items);

            Assert.Multiple(() =>
            {
                Assert.That((string?)shown["net"], Is.EqualTo("search «clima»"));
                // ING5B (owner, 2026-11-13: in English, not a word of Spanish in what the model reads).
                Assert.That(read.Result?.GetProperty("exits")[0].GetProperty("destination").GetString(),
                    Is.EqualTo("search «clima»"));
            });
        }
    }
}
