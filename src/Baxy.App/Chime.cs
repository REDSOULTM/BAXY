using System.IO;
using System.Media;

namespace Baxy.App;

/// <summary>
/// BAXY's sounds without words, played by the App on Windows' default output (the one BAXY's voice follows), so they
/// sound with the window hidden too. Each tone is synthesized once (sine notes, low volume, soft edges; a 0 Hz note is a
/// rest); nothing is read from disk or the network.
/// </summary>
internal sealed class Chime
{
    private const int Rate = 22_050;

    /// <summary>«Sonido al despertar» (design v4, Settings → Voz): «Baxy» was heard. Two notes up, 140 ms.</summary>
    internal static readonly Chime Wake = new([(880, 70), (1320, 70)]);

    /// <summary>A turn of the person's ended without an answer (final 6, accesibilidad): the view shows the failure as
    /// its state and the screen reader reads it, and this is what someone who does not look hears. A fixed line would
    /// be a fixed reply (invariante 5), so it is a sound. Two notes down, 260 ms.</summary>
    internal static readonly Chime TurnFailed = new([(660, 110), (440, 150)]);

    /// <summary>The ear failed while the person spoke (voice_error during a request: the microphone sent nothing or a
    /// block failed): what they said was not heard, and they say it again. Two low equal blips, 180 ms.</summary>
    internal static readonly Chime ListenFailed = new([(392, 70), (0, 40), (392, 70)]);

    /// <summary>The person was heard while a turn ran and the request started nothing (voice_dropped_busy): wait and say
    /// it again when BAXY is done. One short soft note, 90 ms.</summary>
    internal static readonly Chime Wait = new([(587, 90)]);

    private readonly Lazy<byte[]> _wave;

    private Chime((double Hz, int Ms)[] notes) => _wave = new(() => Build(notes));

    /// <summary>The tone as a 16-bit mono PCM WAV file.</summary>
    internal byte[] Wave => _wave.Value;

    internal void Play()
    {
        try
        {
            var player = new SoundPlayer(new MemoryStream(Wave, writable: false));
            player.Play();
        }
        catch (Exception exception) when (exception is InvalidOperationException or IOException)
        {
            // No output device: BAXY goes on, only silently.
        }
    }

    private static byte[] Build((double Hz, int Ms)[] notes)
    {
        int samples = notes.Sum(n => Rate * n.Ms / 1000);
        using var stream = new MemoryStream(44 + samples * 2);
        using var writer = new BinaryWriter(stream);
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
        return stream.ToArray();
    }
}
