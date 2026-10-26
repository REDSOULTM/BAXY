using System.IO;
using System.Runtime.InteropServices;

namespace Baxy.App;

/// <summary>
/// BAXY's two sounds without words, played by the App on Windows' default output (the one BAXY's voice follows), so
/// they sound with the window hidden too. Each tone is synthesized once (sine notes, low volume, soft edges); nothing is
/// read from disk or the network. Windows plays it from the tone's own bytes after Play returns, so they live on the
/// pinned heap for good (revisión de final6: SoundPlayer hands PlaySound a copy that is pinned only during the call and
/// that the GC may move or collect while it sounds).
/// </summary>
internal sealed class Chime
{
    private const int Rate = 22_050;
    private const uint Async = 0x1, NoDefault = 0x2, Memory = 0x4;

    /// <summary>«Sonido al despertar» (design v4, Settings → Voz): «Baxy» was heard. Two notes up, 140 ms.</summary>
    internal static readonly Chime Wake = new([(880, 70), (1320, 70)]);

    /// <summary>A turn of the person's ended without an answer (final 6, accesibilidad): the view shows the failure as
    /// its state and the screen reader reads it, and this is what someone who does not look hears. A fixed line would
    /// be a fixed reply (invariante 5), so it is a sound. Two notes down, 260 ms.</summary>
    internal static readonly Chime TurnFailed = new([(660, 110), (440, 150)]);

    private readonly Lazy<byte[]> _wave;

    private Chime((double Hz, int Ms)[] notes) => _wave = new(() => Build(notes));

    /// <summary>The tone as a 16-bit mono PCM WAV file.</summary>
    internal byte[] Wave => _wave.Value;

    /// <summary>Starts the tone and returns; with no output device it is false and BAXY goes on, only silently.</summary>
    internal void Play() => _ = PlaySound(Wave, 0, Async | Memory | NoDefault);

    [DllImport("winmm.dll", EntryPoint = "PlaySoundW")]
    private static extern bool PlaySound(byte[] sound, nint module, uint flags);

    private static byte[] Build((double Hz, int Ms)[] notes)
    {
        int samples = notes.Sum(n => Rate * n.Ms / 1000);
        byte[] wave = GC.AllocateArray<byte>(44 + samples * 2, pinned: true);
        using var writer = new BinaryWriter(new MemoryStream(wave));
        writer.Write("RIFF"u8); writer.Write(36 + samples * 2); writer.Write("WAVE"u8);
        writer.Write("fmt "u8); writer.Write(16); writer.Write((short)1); writer.Write((short)1);
        writer.Write(Rate); writer.Write(Rate * 2); writer.Write((short)2); writer.Write((short)16);
        writer.Write("data"u8); writer.Write(samples * 2);
        foreach ((double hz, int ms) in notes)
        {
            int count = Rate * ms / 1000;
            for (int i = 0; i < count; i++)
            {
                double envelope = Math.Sin(Math.PI * i / count); // soft attack and release, no click
                writer.Write((short)(Math.Sin(2 * Math.PI * hz * i / Rate) * envelope * 0.18 * short.MaxValue));
            }
        }

        writer.Flush();
        return wave;
    }
}
