using System.Diagnostics;
using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// G1 on the real system's media sessions, with no service and no account: an Edge of the test's own (its own profile,
/// a local page, silence) names a title in its media session, and the read the streaming flow makes tells it from the title
/// asked for. What it cannot say: what a real service's session names. Explicit, BAXY_G1_LIVE=1; ends by process id.
/// </summary>
[TestFixture]
[Explicit("Opens a browser window of its own.")]
[Category("LiveDesktop")]
public sealed class G1MediaSessionLiveCheck
{
    private const string Edge = @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe";
    private const string Playing = "Otra Pelicula De Prueba";

    private static void WriteSilence(string path, int seconds)
    {
        const int Rate = 8000;
        int bytes = Rate * seconds;
        using var writer = new BinaryWriter(File.Create(path));
        writer.Write(Encoding.ASCII.GetBytes("RIFF"));
        writer.Write(36 + bytes);
        writer.Write(Encoding.ASCII.GetBytes("WAVEfmt "));
        writer.Write(16);
        writer.Write((short)1);
        writer.Write((short)1);
        writer.Write(Rate);
        writer.Write(Rate);
        writer.Write((short)1);
        writer.Write((short)8);
        writer.Write(Encoding.ASCII.GetBytes("data"));
        writer.Write(bytes);
        writer.Write(Enumerable.Repeat((byte)128, bytes).ToArray());
    }

    [Test]
    public async Task ASessionThatNamesAnotherTitleIsToldApartFromTheOneAsked()
    {
        if (Environment.GetEnvironmentVariable("BAXY_G1_LIVE") != "1")
            Assert.Ignore("BAXY_G1_LIVE=1 is needed to open a window.");
        string folder = Path.Combine(Path.GetTempPath(), "baxy-g1-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        WriteSilence(Path.Combine(folder, "silencio.wav"), 120);
        string page = Path.Combine(folder, "pagina.html");
        File.WriteAllText(page, $$"""
            <!doctype html><meta charset="utf-8"><title>{{Playing}}</title>
            <audio id="a" src="silencio.wav" autoplay loop></audio>
            <script>navigator.mediaSession.metadata = new MediaMetadata({title: "{{Playing}}"});
            document.getElementById("a").play();</script>
            """);
        var start = new ProcessStartInfo(Edge) { UseShellExecute = false };
        foreach (string argument in new[]
                 {
                     "--user-data-dir=" + Path.Combine(folder, "perfil"), "--no-first-run", "--no-default-browser-check",
                     "--autoplay-policy=no-user-gesture-required", "--app=" + new Uri(page).AbsoluteUri,
                 })
            start.ArgumentList.Add(argument);
        using Process edge = Process.Start(start)!;
        try
        {
            UserMediaSession? session = null;
            for (int attempt = 0; attempt < 40 && session is null; attempt++)
            {
                await Task.Delay(500);
                session = (await MediaSessionCalls.ReadCompleteAsync(CancellationToken.None))?
                    .FirstOrDefault(static read => read.Title == Playing);
            }

            Assert.That(session, Is.Not.Null, "the system's media sessions show the page's title");
            TestContext.Out.WriteLine($"{session!.SourceAppUserModelId} {session.PlaybackStatus}");
            var service = new Uri("https://www.netflix.com/watch/1");
            Assert.Multiple(() =>
            {
                Assert.That(UserBrowserSurface.SessionNamesTitle(session, service, "La Pelicula Pedida", string.Empty), Is.False);
                Assert.That(UserBrowserSurface.SessionNamesTitle(session, service, Playing, string.Empty), Is.True);
            });
        }
        finally
        {
            if (!edge.HasExited)
                edge.Kill(entireProcessTree: true);
            await Task.Delay(1000);
            try
            {
                Directory.Delete(folder, recursive: true);
            }
            catch (IOException)
            {
                // A browser process that has not let go of its profile yet: the system's temporary folder cleans it.
            }
        }
    }
}
