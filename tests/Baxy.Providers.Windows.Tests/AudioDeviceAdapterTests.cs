using System.Text.Json;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// RUT2: audio.device.list and audio.device.set against a fake set of endpoints (invented names): no test changes the
/// PC's sound. The name said is matched with the listed names by form; one match is set and read back, none or several
/// change nothing and list the devices; a default that reads otherwise afterwards is no success.
/// </summary>
[TestFixture]
public sealed class AudioDeviceAdapterTests
{
    private static readonly string[] Outputs =
    [
        "Altavoces (Realtone High Definition Audio)",
        "Auriculares (Kestrel Cloud Wireless)",
        "Speakers (2- Vantor R1100)",
    ];

    private static Task<ExternalCapabilityReceipt> Invoke(FakeAudio audio, string operation, object arguments) =>
        new WindowsAudioDeviceAdapter(audio).InvokeAsync(
            operation, JsonSerializer.SerializeToElement(arguments), CancellationToken.None).AsTask();

    [Test]
    public async Task TheListSaysEveryActiveOutputAndInputAndTheDefaults()
    {
        var audio = new FakeAudio(Outputs, defaultOutput: 0);

        ExternalCapabilityReceipt receipt = await Invoke(audio, "audio.device.list", new { });

        JsonElement outputs = receipt.Result!.Value.GetProperty("outputs");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(outputs.GetArrayLength(), Is.EqualTo(3));
            Assert.That(outputs[0].GetProperty("default").GetBoolean(), Is.True);
            Assert.That(outputs[2].GetProperty("name").GetString(), Is.EqualTo("Speakers (2- Vantor R1100)"));
            Assert.That(receipt.Result!.Value.GetProperty("inputs").GetArrayLength(), Is.EqualTo(1));
            Assert.That(audio.Set, Is.Empty);
        });
    }

    // RUT5 (VIVOR2: «el micrófono» with three): a word they all hold, in either number, is all three, never one of them.
    [Test]
    public void ThreeLookAlikeMicrophonesAllMatchAWordTheyShare()
    {
        string[] inputs =
        [
            "Micrófono (Corvia Streaming Microphone)",
            "Micrófono de los auriculares con micrófono (Kestrel Cloud)",
            "Varios micrófonos (Realtone Audio)",
        ];

        Assert.Multiple(() =>
        {
            Assert.That(WindowsAudioDeviceAdapter.Matching("el micrófono", inputs), Is.EqualTo(new[] { 0, 1, 2 }));
            Assert.That(WindowsAudioDeviceAdapter.Matching("los micrófonos", inputs), Is.EqualTo(new[] { 0, 1, 2 }));
        });
    }

    [TestCase("Kestrel", 1)]
    [TestCase("los audífonos kestrel", -1)]
    [TestCase("kestrell", 1)]
    [TestCase("Vantr", 2)]
    [TestCase("vantor r1100", 2)]
    [TestCase("los Vantor", 2)]
    [TestCase("Speakers (2- Vantor R1100)", 2)]
    [TestCase("Corvia", -1)]
    [TestCase("el altavoz", 0)]
    [TestCase("altavoz realtone", 0)]
    [TestCase("the speaker", 2)]
    [TestCase("auricular", 1)]
    public void ANameMatchesByFormOnly(string said, int expected)
    {
        IReadOnlyList<int> matching = WindowsAudioDeviceAdapter.Matching(said, Outputs);

        Assert.That(matching, Is.EqualTo(expected < 0 ? Array.Empty<int>() : new[] { expected }));
    }

    [Test]
    public async Task OneMatchIsSetForBothRolesAndReadBack()
    {
        var audio = new FakeAudio(Outputs, defaultOutput: 0);

        ExternalCapabilityReceipt receipt = await Invoke(audio, "audio.device.set", new { device = "Vantor" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(audio.Set, Is.EqualTo(new[] { "out-2" }));
            Assert.That(receipt.Result!.Value.GetProperty("device").GetString(), Is.EqualTo("Speakers (2- Vantor R1100)"));
            Assert.That(receipt.Result!.Value.GetProperty("previous").GetString(), Does.StartWith("Altavoces"));
            Assert.That(receipt.Result!.Value.GetProperty("changed").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task TwoLookAlikeDevicesChangeNothingAndAreListed()
    {
        var audio = new FakeAudio(["Auriculares (Kestrel Cloud)", "Auriculares (Kestrel Cloud Alpha)", "Altavoces (Realtone)"], 2);

        ExternalCapabilityReceipt receipt = await Invoke(audio, "audio.device.set", new { device = "Kestrel Cloud" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsAudioDeviceAdapter.Ambiguous));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(audio.Set, Is.Empty);
            Assert.That(receipt.Result!.Value.GetProperty("devices").GetArrayLength(), Is.EqualTo(2));
        });
    }

    [Test]
    public async Task ANameNoDeviceHasChangesNothingAndListsThemAll()
    {
        var audio = new FakeAudio(Outputs, 0);

        ExternalCapabilityReceipt receipt = await Invoke(audio, "audio.device.set", new { device = "Corvia" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsAudioDeviceAdapter.NotMatched));
            Assert.That(audio.Set, Is.Empty);
            Assert.That(receipt.Result!.Value.GetProperty("devices").GetArrayLength(), Is.EqualTo(3));
        });
    }

    [Test]
    public async Task TheDefaultAlreadyIsTheStateReachedWithNoCall()
    {
        var audio = new FakeAudio(Outputs, 1);

        ExternalCapabilityReceipt receipt = await Invoke(audio, "audio.device.set", new { device = "Kestrel" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(audio.Set, Is.Empty);
        });
    }

    [Test]
    public async Task ADefaultThatDoesNotChangeIsNoSuccess()
    {
        var audio = new FakeAudio(Outputs, 0) { Ignores = true };

        ExternalCapabilityReceipt receipt = await Invoke(audio, "audio.device.set", new { device = "Vantor" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsAudioDeviceAdapter.NotVerified));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("stateAfter").GetProperty("default").GetString(), Does.StartWith("Altavoces"));
        });
    }

    [Test]
    public async Task AFailedSetIsAFailureAfterTheBoundary()
    {
        var audio = new FakeAudio(Outputs, 0) { Throws = true };

        ExternalCapabilityReceipt receipt = await Invoke(audio, "audio.device.set", new { device = "Vantor" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("audio_device_failed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
        });
    }

    // Revisión ciega RUT2 (8): the multimedia default alone is not the device set: the console role is set too.
    [Test]
    public async Task ADefaultForMultimediaOnlyIsStillSetForBothRoles()
    {
        var audio = new FakeAudio(Outputs, 1) { ConsoleDefault = "out-0" };

        ExternalCapabilityReceipt receipt = await Invoke(audio, "audio.device.set", new { device = "Kestrel" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(audio.Set, Is.EqualTo(new[] { "out-1" }));
        });
    }

    [Test]
    public async Task KindInputSetsTheMicrophone()
    {
        var audio = new FakeAudio(Outputs, 0);

        ExternalCapabilityReceipt receipt = await Invoke(audio, "audio.device.set", new { device = "Strato", kind = "input" });

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("kind").GetString(), Is.EqualTo("input"));
        });
    }

    private sealed class FakeAudio(string[] outputs, int defaultOutput) : IAudioDevicePlatform
    {
        private string _default = "out-" + defaultOutput;

        public string? ConsoleDefault { get; set; }

        public List<string> Set { get; } = [];

        public bool Ignores { get; init; }

        public bool Throws { get; init; }

        public IReadOnlyList<AudioDevice> Active(bool capture) => capture
            ? [new AudioDevice("in-0", "Micrófono (Strato USB)", true, true)]
            : outputs.Select((name, index) => new AudioDevice(
                "out-" + index, name, "out-" + index == _default, "out-" + index == (ConsoleDefault ?? _default))).ToArray();

        public void SetDefault(string endpointId)
        {
            if (Throws)
            {
                throw new AudioPlatformException("audio_endpoint_unavailable");
            }

            Set.Add(endpointId);
            if (!Ignores)
            {
                _default = endpointId;
                ConsoleDefault = null;
            }
        }
    }
}
