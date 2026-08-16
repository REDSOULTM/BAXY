using System.Globalization;
using System.Text.Json;
using NAudio.CoreAudioApi;
using NAudio.Wave;
using NAudio.Wave.SampleProviders;

static double ParseDuration(string value)
{
    if (!double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var duration)
        || duration <= 0
        || duration > 30)
    {
        throw new ArgumentException("duration must be in (0, 30]");
    }
    return duration;
}

static async Task<(WasapiRecorder Recorder, byte[] Audio)> CaptureRawAsync(
    MMDevice microphone,
    double duration,
    bool announceReady)
{
    var recorder = new WasapiRecorderBuilder()
        .WithDevice(microphone)
        .WithRawMode()
        .Build();
    var audio = new MemoryStream();
    var gate = new object();
    var stopped = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
    recorder.DataAvailable += (buffer, _, _, _) =>
    {
        lock (gate)
        {
            audio.Write(buffer);
        }
    };
    recorder.RecordingStopped += (_, eventArgs) =>
    {
        if (eventArgs.Exception is not null)
        {
            stopped.TrySetException(eventArgs.Exception);
        }
        else
        {
            stopped.TrySetResult();
        }
    };

    recorder.StartRecording();
    if (announceReady)
    {
        Console.WriteLine("READY");
        Console.Out.Flush();
    }
    await Task.Delay(TimeSpan.FromSeconds(duration));
    recorder.StopRecording();
    await stopped.Task.WaitAsync(TimeSpan.FromSeconds(10));
    lock (gate)
    {
        return (recorder, audio.ToArray());
    }
}

using var enumerator = new MMDeviceEnumerator();
using var microphone = enumerator.GetDefaultAudioEndpoint(DataFlow.Capture, Role.Multimedia);

if (args.Length == 3 && args[0] == "capture")
{
    var output = Path.GetFullPath(args[1]);
    if (File.Exists(output))
    {
        Console.Error.WriteLine("output already exists");
        return 2;
    }
    var duration = ParseDuration(args[2]);
    var (recorder, audio) = await CaptureRawAsync(microphone, duration, announceReady: true);
    await using (recorder)
    using (var source = new RawSourceWaveStream(audio, 0, audio.Length, recorder.WaveFormat))
    {
        ISampleProvider samples = source.ToSampleProvider();
        if (samples.WaveFormat.Channels == 2)
        {
            samples = new StereoToMonoSampleProvider(samples)
            {
                LeftVolume = 0.5f,
                RightVolume = 0.5f,
            };
        }
        else if (samples.WaveFormat.Channels != 1)
        {
            throw new InvalidOperationException("raw capture channel count is unsupported");
        }
        WaveFileWriter.CreateWaveFile16(output, samples);
    }
    Console.WriteLine(JsonSerializer.Serialize(new
    {
        schema = "baxy.raw-audio-capture.v1",
        microphone = microphone.FriendlyName,
        format = recorder.WaveFormat.ToString(),
        capturedBytes = audio.Length,
        requestedRawMode = true,
    }));
    return audio.Length > 0 ? 0 : 1;
}

var probeDuration = args.Length == 1 ? ParseDuration(args[0]) : 1.0;
var (probeRecorder, probeAudio) = await CaptureRawAsync(
    microphone,
    probeDuration,
    announceReady: false);
await using (probeRecorder)
{
    Console.WriteLine(JsonSerializer.Serialize(new
    {
        schema = "baxy.raw-audio-probe.v1",
        microphone = microphone.FriendlyName,
        format = probeRecorder.WaveFormat.ToString(),
        capturedBytes = probeAudio.Length,
        requestedRawMode = true,
    }));
}
return probeAudio.Length > 0 ? 0 : 1;
