using System.Media;
using System.Reflection;
using System.Runtime.InteropServices;

namespace Baxy.Installer;

/// <summary>
/// BAXY's voice in its installer: lines recorded with its own voice (scripts/voice/make_installer_voice.py). It starts off
/// when a screen reader is running, so the two never talk over each other, and when a BAXY is open, because its lines say
/// the wake word and that BAXY would answer (it did, 2026-11-04). A machine without audio stays silent.
/// </summary>
internal sealed partial class Voice : IDisposable
{
    private const uint GetScreenReader = 0x46;
    private const string BaxyInstance = @"Local\BAXY.Product.App";
    private readonly SoundPlayer player = new();
    private Stream? playing;

    /// <param name="allowed">False with --no-voice: on a machine where a BAXY may be listening and is not this one's.</param>
    internal Voice(bool allowed = true)
    {
        IsOn = allowed && !ScreenReaderIsRunning() && !BaxyIsOpen();
    }

    internal bool IsOn { get; set; }

    /// <summary>The single-instance mutex of the App (src/Baxy.App/App.xaml.cs).</summary>
    internal static bool BaxyIsOpen()
    {
        if (!Mutex.TryOpenExisting(BaxyInstance, out Mutex? instance))
        {
            return false;
        }

        instance.Dispose();
        return true;
    }

    internal void Say(string language, string line)
    {
        Stop();
        if (!IsOn)
        {
            return;
        }

        try
        {
            playing = Assembly.GetExecutingAssembly().GetManifestResourceStream($"Baxy.Installer.voice.{language}_{line}");
            player.Stream = playing;
            player.Play();
        }
        catch (Exception failure) when (failure is InvalidOperationException or TimeoutException or ExternalException)
        {
            Program.Log(failure.ToString());
        }
    }

    internal void Stop()
    {
        player.Stop();
        playing?.Dispose();
        playing = null;
    }

    public void Dispose()
    {
        Stop();
        player.Dispose();
    }

    private static bool ScreenReaderIsRunning() =>
        SystemParametersInfoW(GetScreenReader, 0, out int running, 0) && running != 0;

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SystemParametersInfoW(uint action, uint first, out int result, uint flags);
}
