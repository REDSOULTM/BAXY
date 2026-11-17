using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// DIAX11 (privacidad): BAXY's own browser profiles never take the person's account. Live counterpart:
/// <see cref="OwnBrowserProfileLiveCheck"/> (BAXY_OWN_BROWSER_SIGNIN_LIVE=1).
/// </summary>
[TestFixture]
public sealed class OwnBrowserProfileTests
{
    private const string Edge = @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe";
    private string _root = null!;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-own-browser-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
    }

    [TearDown]
    public void TearDown()
    {
        if (Directory.Exists(_root))
            Directory.Delete(_root, recursive: true);
    }

    // Vivo Radeon H-006 and PC (Edge 157): a new profile signed itself in with the Windows account and synced. Every
    // launch of an own profile turns off the OS-account sign-in and sync, whichever Chromium browser it is.
    [Test]
    public void EveryOwnProfileLaunchTurnsOffTheAccountSignInAndSync()
    {
        foreach (string browser in new[] { Edge, @"C:\Program Files\Google\Chrome\Application\chrome.exe" })
        {
            InvokerLaunch.LaunchPlan plan = CdpBrowserSession.LaunchPlan(browser, @"C:\Datos\edge");

            Assert.That(plan.Arguments, Does.Contain(" --disable-sync "));
            string features = plan.Arguments.Split(' ').Single(argument => argument.StartsWith(
                "--disable-features=", StringComparison.Ordinal))["--disable-features=".Length..];
            // The OS-account sign-in, and the single sign-on to Microsoft sites with the machine's account.
            Assert.That(features.Split(','), Does.Contain("msImplicitSignin").And.Contain("msSSOBrowserHint")
                .And.Contain("msSsoByHttpDefer").And.Contain("msAllowMSAPrtSSOForNonMSAProfile"));
            // Chromium keeps only the last «--disable-features»: the launch carries exactly one.
            Assert.That(plan.Arguments.Split(' ').Count(argument => argument.StartsWith(
                "--disable-features=", StringComparison.Ordinal)), Is.EqualTo(1));
            Assert.That(plan.Arguments, Does.EndWith(" about:blank"));
        }
    }

    [Test]
    public void AProfileWithAnAccountIsSeenAndACleanOneIsNot()
    {
        string signedIn = Profile("edge", localState: """{"profile":{"info_cache":{"Default":{"name":"Personal","gaia_id":"0123456789abcdef","user_name":"x","is_consented_primary_account":true}}}}""",
            preferences: """{"account_info":[{"account_id":"0123456789abcdef"}],"sync":{"has_setup_completed":true}}""");
        string onlyPreferences = Profile("brave", localState: """{"profile":{"info_cache":{"Default":{"name":"Persona 1","gaia_id":"","user_name":""}}}}""",
            preferences: """{"account_info":[{"account_id":"0123456789abcdef"}],"google":{"services":{"consented_to_sync":true}}}""");
        string onlyASite = Profile("vivaldi", localState: """{"profile":{"info_cache":{"Default":{"name":"Persona 1","gaia_id":"","user_name":""}}}}""",
            preferences: """{"account_info":[{"account_id":"0123456789abcdef"}],"google":{"services":{"consented_to_sync":false}}}""");
        string onlySync = Profile("opera", localState: null, preferences: """{"account_info":[],"sync":{"has_setup_completed":true}}""");
        string clean = Profile("chrome", localState: """{"profile":{"info_cache":{"Default":{"name":"Persona 1","gaia_id":"","user_name":"","is_consented_primary_account":false}}}}""",
            preferences: """{"account_info":[],"signin":{"allowed":true},"sync":{"has_setup_completed":false}}""");
        string unreadable = Profile("opera_gx", localState: "{{{", preferences: "\0\0\0");

        Assert.Multiple(() =>
        {
            Assert.That(OwnBrowserProfile.IsSignedIn(signedIn), Is.True);
            Assert.That(OwnBrowserProfile.IsSignedIn(onlyPreferences), Is.True);
            Assert.That(OwnBrowserProfile.IsSignedIn(onlySync), Is.True);
            Assert.That(OwnBrowserProfile.IsSignedIn(clean), Is.False);
            Assert.That(OwnBrowserProfile.IsSignedIn(onlyASite), Is.False, "a site's session in BAXY's browser is the person's");
            Assert.That(OwnBrowserProfile.IsSignedIn(unreadable), Is.False, "an unreadable file is no evidence");
            Assert.That(OwnBrowserProfile.IsSignedIn(Path.Combine(_root, "missing")), Is.False);
        });
    }

    // The 1.5.x profiles: the one that signed in is closed and discarded once, the clean one is kept, the person is
    // told once, and a later start does not look again (a sign-in the person makes on purpose later is theirs).
    [Test]
    public void ASignedInProfileIsDiscardedOnceAndSaidOnce()
    {
        string signedIn = Profile("edge", localState: """{"profile":{"info_cache":{"Default":{"gaia_id":"0123456789abcdef","is_consented_primary_account":true}}}}""",
            preferences: """{"account_info":[{"account_id":"0123456789abcdef"}]}""");
        string clean = Profile("chrome", localState: """{"profile":{"info_cache":{"Default":{"gaia_id":""}}}}""",
            preferences: """{"account_info":[]}""");
        File.WriteAllText(Path.Combine(clean, "Default", "History"), "kept");
        var closed = new List<string>();

        IReadOnlyList<string> discarded = OwnBrowserProfile.DiscardSignedInProfiles(_root, folder =>
        {
            closed.Add(Path.GetFileName(folder));
            return 1;
        });

        Assert.Multiple(() =>
        {
            Assert.That(discarded, Is.EqualTo(new[] { "edge" }));
            Assert.That(closed, Is.EqualTo(new[] { "edge" }), "only the browser of the profile discarded is closed");
            Assert.That(Directory.Exists(signedIn), Is.False);
            Assert.That(File.ReadAllText(Path.Combine(clean, "Default", "History")), Is.EqualTo("kept"));
            Assert.That(OwnBrowserProfile.ReadNotice(_root), Is.EqualTo(new[] { "edge" }));
        });

        OwnBrowserProfile.ForgetNotice(_root);
        Assert.That(OwnBrowserProfile.ReadNotice(_root), Is.Empty, "said once");
        Profile("edge", localState: null, preferences: """{"sync":{"has_setup_completed":true}}""");
        Assert.That(OwnBrowserProfile.DiscardSignedInProfiles(_root, _ => 0), Is.Empty, "checked once");
    }

    // REVX2 DX11-1: only Edge signs itself in with the account Windows is signed into (ImplicitSignInEnabled); Chrome,
    // Brave and Opera do not, so an account in their own profile is one the person put there on purpose. Theirs to keep:
    // not closed, not deleted, nothing said. The Edge one beside them goes as before.
    [Test]
    public void OnlyTheOwnEdgeProfileIsDiscardedAnAccountInAnotherBrowserIsThePersons()
    {
        string edge = Profile("edge", localState: """{"profile":{"info_cache":{"Default":{"gaia_id":"0123456789abcdef","is_consented_primary_account":true}}}}""",
            preferences: """{"sync":{"has_setup_completed":true}}""");
        string[] others =
        [
            Profile("chrome", localState: """{"profile":{"info_cache":{"Default":{"gaia_id":"0123456789abcdef","user_name":"x","is_consented_primary_account":true}}}}""",
                preferences: """{"google":{"services":{"consented_to_sync":true}}}"""),
            Profile("brave", localState: null, preferences: """{"google":{"services":{"consented_to_sync":true}}}"""),
            Profile("opera", localState: null, preferences: """{"sync":{"has_setup_completed":true}}"""),
            Profile("opera_gx", localState: """{"profile":{"info_cache":{"Default":{"user_name":"x"}}}}""",
                preferences: """{"sync":{"has_setup_completed":true}}"""),
        ];
        Assert.That(others.All(OwnBrowserProfile.IsSignedIn), Is.True, "each holds an account");
        var closed = new List<string>();

        IReadOnlyList<string> discarded = OwnBrowserProfile.DiscardSignedInProfiles(_root, folder =>
        {
            closed.Add(Path.GetFileName(folder));
            return 1;
        });

        Assert.Multiple(() =>
        {
            Assert.That(discarded, Is.EqualTo(new[] { "edge" }));
            Assert.That(closed, Is.EqualTo(new[] { "edge" }), "no other browser is closed");
            Assert.That(Directory.Exists(edge), Is.False);
            Assert.That(others.Where(Directory.Exists), Is.EqualTo(others), "their profiles stay whole");
            Assert.That(OwnBrowserProfile.ReadNotice(_root), Is.EqualTo(new[] { "edge" }));
        });
    }

    [Test]
    public void AnAccountOnlyInAnotherBrowserIsKeptAndNothingIsSaid()
    {
        string chrome = Profile("chrome", localState: """{"profile":{"info_cache":{"Default":{"gaia_id":"0123456789abcdef","is_consented_primary_account":true}}}}""",
            preferences: """{"google":{"services":{"consented_to_sync":true}}}""");
        File.WriteAllText(Path.Combine(chrome, "Default", "Cookies"), "kept");
        Profile("brave", localState: null, preferences: """{"google":{"services":{"consented_to_sync":true}}}""");
        Profile("opera", localState: null, preferences: """{"sync":{"has_setup_completed":true}}""");
        Profile("edge", localState: """{"profile":{"info_cache":{"Default":{"gaia_id":""}}}}""", preferences: """{"account_info":[]}""");

        IReadOnlyList<string> discarded = OwnBrowserProfile.DiscardSignedInProfiles(_root,
            folder => throw new AssertionException("closed " + folder));

        Assert.Multiple(() =>
        {
            Assert.That(discarded, Is.Empty);
            Assert.That(File.ReadAllText(Path.Combine(chrome, "Default", "Cookies")), Is.EqualTo("kept"));
            Assert.That(Directory.GetDirectories(_root).Select(Path.GetFileName),
                Is.EquivalentTo(new[] { "chrome", "brave", "opera", "edge" }));
            Assert.That(OwnBrowserProfile.ReadNotice(_root), Is.Empty, "nothing to say");
        });
    }

    // REVX2 DX11-3: the shared folder belongs to the BAXY installed for this Windows user. A core or App on another data
    // root (a live test, a dev instance: BAXY_DATA_DIR) neither discards its profiles nor takes its notice; the installed
    // one, at its next start, does both.
    [Test]
    public void AnInstanceOnAnotherDataRootLeavesTheInstalledProfilesAndNoticeAlone()
    {
        string installed = Path.Combine(_root, "Local", "BAXY", "1");
        string shared = Path.Combine(_root, "Local", "BAXY", "browser-session-v1");
        string edge = Profile("edge", localState: """{"profile":{"info_cache":{"Default":{"gaia_id":"0123456789abcdef","is_consented_primary_account":true}}}}""",
            preferences: """{"sync":{"has_setup_completed":true}}""", parent: shared);
        File.WriteAllText(Path.Combine(shared, OwnBrowserProfile.NoticeMarker), "edge" + Environment.NewLine);
        string isolated = Path.Combine(_root, "prueba-en-vivo", "datos");

        int? discarded = WindowsExternalCapabilityProvider.DiscardOwnBrowserProfilesWithAnAccount(isolated, shared,
            installed, folder => throw new AssertionException("closed " + folder));
        IReadOnlyList<string> notice = WindowsExternalCapabilityProvider.OwnBrowserAccountNotice(isolated, shared, installed);
        WindowsExternalCapabilityProvider.ForgetOwnBrowserAccountNotice(isolated, shared, installed);

        Assert.Multiple(() =>
        {
            Assert.That(discarded, Is.Null, "not this instance's profiles: said in the core's log");
            Assert.That(Directory.Exists(edge), Is.True, "the installed BAXY's profile is untouched");
            Assert.That(File.Exists(Path.Combine(shared, OwnBrowserProfile.CheckedMarker)), Is.False);
            Assert.That(notice, Is.Empty, "the notice is not this instance's to say");
            Assert.That(OwnBrowserProfile.ReadNotice(shared), Is.EqualTo(new[] { "edge" }), "nor to forget");
        });

        // The installed one (its data root however spelled) discards and says it.
        Assert.That(WindowsExternalCapabilityProvider.DiscardOwnBrowserProfilesWithAnAccount(
            installed.ToUpperInvariant() + Path.DirectorySeparatorChar, shared, installed, _ => 0), Is.EqualTo(1));
        Assert.That(Directory.Exists(edge), Is.False);
        Assert.That(WindowsExternalCapabilityProvider.OwnBrowserAccountNotice(installed, shared, installed),
            Is.EqualTo(new[] { "edge" }));
        WindowsExternalCapabilityProvider.ForgetOwnBrowserAccountNotice(installed, shared, installed);
        Assert.That(OwnBrowserProfile.ReadNotice(shared), Is.Empty);
    }

    // A profile still held (its files cannot be deleted) is not marked checked: the next start tries again.
    [Test]
    public void AProfileThatCannotBeDeletedIsTriedAgainNextStart()
    {
        string signedIn = Profile("edge", localState: null, preferences: """{"sync":{"has_setup_completed":true}}""");
        using (new FileStream(Path.Combine(signedIn, "Default", "Preferences"), FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            Assert.That(OwnBrowserProfile.DiscardSignedInProfiles(_root, _ => 0), Is.Empty);
        }
        Assert.That(File.Exists(Path.Combine(_root, OwnBrowserProfile.CheckedMarker)), Is.False);

        Assert.That(OwnBrowserProfile.DiscardSignedInProfiles(_root, _ => 0), Is.EqualTo(new[] { "edge" }));
    }

    [Test]
    public void TheSharedRootIsTheFolderOfTheOwnProfilesOnly()
    {
        string? root = OwnBrowserProfile.SharedRoot(@"C:\Datos\BAXY\1");

        Assert.That(root, Is.Null.Or.EndsWith(Path.DirectorySeparatorChar + "browser-session-v1"));
    }

    [TestCase(@"""C:\x\msedge.exe"" --disable-gpu --user-data-dir=C:\B\edge about:blank", true)]
    [TestCase(@"""C:\x\msedge.exe"" ""--user-data-dir=C:\B\edge"" about:blank", true)]
    [TestCase(@"""C:\x\msedge.exe"" --type=renderer --user-data-dir=""C:\B\edge"" --lang=es", true)]
    [TestCase(@"""C:\x\msedge.exe"" --user-data-dir=C:\B\edge", true)]
    [TestCase(@"""C:\x\msedge.exe"" --user-data-dir=C:\B\edge2 about:blank", false)]
    [TestCase(@"""C:\x\msedge.exe"" --profile-directory=Default", false)]
    [TestCase(null, false)]
    public void OnlyABrowserStartedOnThatVeryFolderIsClosed(string? commandLine, bool started)
    {
        Assert.That(OwnBrowserProfile.StartedOn(commandLine, @"C:\B\edge"), Is.EqualTo(started));
    }

    private string Profile(string family, string? localState, string preferences, string? parent = null)
    {
        string folder = Path.Combine(parent ?? _root, family);
        Directory.CreateDirectory(Path.Combine(folder, "Default"));
        if (localState is not null)
            File.WriteAllText(Path.Combine(folder, "Local State"), localState);
        File.WriteAllText(Path.Combine(folder, "Default", "Preferences"), preferences);
        return folder;
    }
}
