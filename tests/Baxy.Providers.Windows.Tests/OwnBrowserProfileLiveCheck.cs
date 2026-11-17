using System.Diagnostics;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// DIAX11 (privacidad), on the real desktop, opt-in only (Explicit and BAXY_OWN_BROWSER_SIGNIN_LIVE=1): the launch BAXY
/// gives its own browser (<see cref="CdpBrowserSession.LaunchPlan"/>), on a new profile in a temporary folder of the
/// test's own, does not end up holding the Windows account (<see cref="OwnBrowserProfile.IsSignedIn"/>, or any
/// account_info) within BAXY_OWN_BROWSER_SECONDS (90 by default). Its files are read every half second; the moment an account shows, the
/// browser is closed by its own processes and the folder deleted, so a failure never leaves the account in it. Keep it
/// under 240 s: the project's hang collector (tests/hang.runsettings, 5 min) ends the test host before its cleanup.
/// </summary>
[TestFixture]
[Explicit("Opens Edge on a profile of its own; on a Windows signed in with a Microsoft account a failure signs it in.")]
public sealed class OwnBrowserProfileLiveCheck
{
    [TestCase(@"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")]
    public async Task ANewOwnProfileNeverTakesTheWindowsAccount(string browser)
    {
        if (Environment.GetEnvironmentVariable("BAXY_OWN_BROWSER_SIGNIN_LIVE") != "1")
            Assert.Ignore("BAXY_OWN_BROWSER_SIGNIN_LIVE=1 is needed to open a browser.");
        if (!File.Exists(browser))
            Assert.Ignore("No browser at " + browser);
        int seconds = int.TryParse(Environment.GetEnvironmentVariable("BAXY_OWN_BROWSER_SECONDS"), out int asked)
            && asked > 0 ? asked : 90;
        string profile = Path.Combine(Path.GetTempPath(), "baxy-own-signin-" + Guid.NewGuid().ToString("N")[..8], "edge");
        Directory.CreateDirectory(profile);
        InvokerLaunch.LaunchPlan plan = CdpBrowserSession.LaunchPlan(browser, profile);
        double? signedInAt = null;
        var clock = Stopwatch.StartNew();
        try
        {
            using Process started = Process.Start(new ProcessStartInfo(plan.Executable,
                "--window-position=-2400,-2400 --mute-audio " + plan.Arguments)
            {
                UseShellExecute = false,
                WorkingDirectory = plan.WorkingDirectory,
            })!;
            while (clock.Elapsed.TotalSeconds < seconds)
            {
                await Task.Delay(500);
                if (OwnBrowserProfile.IsSignedIn(profile) || HoldsAnyAccount(profile))
                {
                    signedInAt = clock.Elapsed.TotalSeconds;
                    break;
                }
            }
        }
        finally
        {
            OwnBrowserProfile.CloseBrowsersOn(profile);
            for (int attempt = 0; attempt < 10 && Directory.Exists(Path.GetDirectoryName(profile)); attempt++)
            {
                try
                {
                    Directory.Delete(Path.GetDirectoryName(profile)!, recursive: true);
                }
                catch (IOException)
                {
                    await Task.Delay(500);
                }
            }
        }
        TestContext.Out.WriteLine(signedInAt is null
            ? $"no account in {seconds} s"
            : $"ACCOUNT at {signedInAt:0.0} s (closed and deleted)");
        Assert.That(signedInAt, Is.Null, "BAXY's own profile signed itself in with the Windows account");
    }

    // Stricter than IsSignedIn, for a profile nobody used: any account the profile tracks (account_info), the first
    // thing Edge's implicit sign-in writes (2.9 s on Edge 157), before the primary account and sync.
    private static bool HoldsAnyAccount(string profile)
    {
        string preferences = Path.Combine(profile, "Default", "Preferences");
        try
        {
            if (!File.Exists(preferences))
                return false;
            using var stream = new FileStream(preferences, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            using var document = System.Text.Json.JsonDocument.Parse(stream);
            return document.RootElement.TryGetProperty("account_info", out System.Text.Json.JsonElement accounts)
                && accounts.ValueKind == System.Text.Json.JsonValueKind.Array && accounts.GetArrayLength() > 0;
        }
        catch (Exception exception) when (exception is IOException or System.Text.Json.JsonException)
        {
            return false;
        }
    }
}
