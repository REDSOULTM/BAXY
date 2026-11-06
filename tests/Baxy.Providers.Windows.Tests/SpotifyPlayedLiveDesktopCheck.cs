using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso-110 on the real desktop: media.play.query through the adapter as the product builds it, against the same adapter
/// that finds the client's session only by its id (the base, f31c3eca4), the two arms taking turns over searches that
/// never repeat. What each receipt says is written to the output, then compared by hand with what Windows' session says
/// plays. Never runs in a suite: Explicit and BAXY_SPOTIFY_PLAYED_LIVE=1, with the client signed in and no one at the
/// desktop. It pauses what it played and leaves the client as it is.
/// </summary>
[TestFixture]
[Explicit("Plays music in the Spotify client on the person's desktop.")]
[Category("LiveDesktop")]
public sealed class SpotifyPlayedLiveDesktopCheck
{
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetForegroundWindow(nint window);

    [DllImport("user32.dll")]
    private static extern nint GetForegroundWindow();

    [DllImport("user32.dll")]
    private static extern void keybd_event(byte key, byte scan, uint flags, nuint extra);

    private static void BringUp(nint window)
    {
        const byte Alt = 0x12;
        for (int attempt = 0; attempt < 5 && GetForegroundWindow() != window; attempt++)
        {
            keybd_event(Alt, 0, 0, 0);
            keybd_event(Alt, 0, 2, 0);
            _ = SetForegroundWindow(window);
            Thread.Sleep(300);
        }

        TestContext.Out.WriteLine($"frente={GetForegroundWindow() == window}");
    }

    private static nint ClientWindow()
    {
        Process[] processes = Process.GetProcessesByName("Spotify");
        nint window = processes.Select(static process => process.MainWindowHandle).FirstOrDefault(static handle => handle != 0);
        foreach (Process process in processes)
            process.Dispose();
        return window;
    }

    [Test]
    public async Task WhatASearchPlayedIsToldAsItIs()
    {
        if (Environment.GetEnvironmentVariable("BAXY_SPOTIFY_PLAYED_LIVE") != "1")
            Assert.Ignore("BAXY_SPOTIFY_PLAYED_LIVE=1 is needed to touch the desktop.");
        string[] queries = (Environment.GetEnvironmentVariable("BAXY_SPOTIFY_PLAYED_QUERIES") ?? "lofi;clair de lune").Split(';');
        string script = Path.Combine(AppContext.BaseDirectory, "SpotifyDesktopAutomation.ps1");
        using var worker = new PowerShellScriptWorker(script);
        (string Name, SpotifyDesktopAdapter Adapter)[] arms =
        [
            ("rama", new SpotifyDesktopAdapter(
                worker, script, clientWindow: ClientWindow, sessions: static token => MediaSessionCalls.ReadAsync(token),
                shownName: Baxy.Providers.Windows.Audio.WindowsCoreAudioPlatform.AppsFolderName)),
            ("base", new SpotifyDesktopAdapter(
                worker, script, clientWindow: ClientWindow, sessions: static token => MediaSessionCalls.ReadAsync(token))),
        ];
        for (int index = 0; index < queries.Length; index++)
        {
            (string name, SpotifyDesktopAdapter adapter) = arms[index % arms.Length];
            using JsonDocument arguments = JsonDocument.Parse(JsonSerializer.Serialize(new { provider = "spotify", query = queries[index] }));
            // No lease: another session's input on this desktop would stop every call. The client is brought up here.
            BringUp(ClientWindow());
            var clock = Stopwatch.StartNew();
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("media.play.query", arguments.RootElement, CancellationToken.None);
            clock.Stop();
            IReadOnlyList<UserMediaSession> sessions = await MediaSessionCalls.ReadAsync();
            UserMediaSession? playing = sessions.FirstOrDefault(session => session.PlaybackStatus == "playing");
            TestContext.Out.WriteLine(string.Create(CultureInfo.InvariantCulture,
                $"{name} «{queries[index]}» {clock.Elapsed.TotalMilliseconds:F0} ms verified={receipt.Verified} error={receipt.ErrorCode} "
                + $"sesion={playing?.Title}/{playing?.Artist} result={receipt.Result?.GetRawText()}"));
            if (playing is not null)
                await MediaSessionCalls.ControlAsync(playing.SourceAppUserModelId, playing.Title, pause: true);
            await Task.Delay(1200);
        }
    }
}
