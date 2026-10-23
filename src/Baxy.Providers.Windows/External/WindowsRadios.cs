using Windows.Devices.Radios;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Renew al máximo (w8): the radios (Wi-Fi, Bluetooth, mobile broadband) as the device adapter sees them. The adapter
/// called the WinRT Radio API directly, so how it reads a radio back after switching it could not be tested.
/// </summary>
internal interface IRadioSet
{
    ValueTask<RadioAccessStatus> RequestAccessAsync();

    ValueTask<IReadOnlyList<IRadioHandle>> ListAsync();
}

internal interface IRadioHandle
{
    RadioKind Kind { get; }

    string Name { get; }

    RadioState State { get; }

    ValueTask<RadioAccessStatus> SetStateAsync(RadioState state);
}

internal sealed class WindowsRadioSet : IRadioSet
{
    internal static readonly WindowsRadioSet Instance = new();

    public async ValueTask<RadioAccessStatus> RequestAccessAsync() => await Radio.RequestAccessAsync();

    public async ValueTask<IReadOnlyList<IRadioHandle>> ListAsync() =>
        (await Radio.GetRadiosAsync()).Select(static radio => (IRadioHandle)new Handle(radio)).ToArray();

    private sealed class Handle(Radio radio) : IRadioHandle
    {
        public RadioKind Kind => radio.Kind;

        public string Name => radio.Name;

        public RadioState State => radio.State;

        public async ValueTask<RadioAccessStatus> SetStateAsync(RadioState state) => await radio.SetStateAsync(state);
    }
}
