using System.IO;
using System.Media;

namespace Baxy.App;

/// <summary>
/// «Sonido al despertar» (design v4, Settings → Voz): a short soft tone when «Baxy» is heard, played by the App so it
/// sounds with the window hidden too. The tone is synthesized once (two sine notes, 140 ms, low volume); nothing is read
/// from disk or the network.
/// </summary>
internal static class WakeChime
{
    private const int Rate = 22_050;

    private static readonly Lazy<byte[]> Wave = new(Build);

    internal static void Play()
    {
        try
        {
            var player = new SoundPlayer(new MemoryStream(Wave.Value, writable: false));
            player.Play();
        }
        catch (Exception exception) when (exception is InvalidOperationException or IOException)
        {
            // No output device: the wake still works, only silently.
        }
    }

    private static byte[] Build()
    {
        (double Hz, int Ms)[] notes = [(880, 70), (1320, 70)];
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
