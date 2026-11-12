using System.ComponentModel;
using System.Runtime.InteropServices;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// INS-2: the installer listed the cards by the screens Windows has in this session (EnumDisplayDevices) and BAXY by DXGI,
/// which also gives the adapters with no screen plugged. On a laptop whose screen hangs from the Intel graphics, the
/// installer said «only Intel» and did not download the NVIDIA part that BAXY then looked for. Both read one source now.
/// </summary>
[TestFixture]
public sealed class MachineGpuSourceTests
{
    private const ulong Gibibyte = 1024UL * 1024 * 1024;

    // DXGI's order: the adapter the desktop is shown on comes first. The second one has no output at all.
    private static readonly GpuAdapterReading IntelWithTheScreen =
        new(new GpuAdapterKey(1, 0), "Integrated", 0x8086, 0x9A49, 128 * 1024 * 1024, 0, 8 * Gibibyte);

    private static readonly GpuAdapterReading NvidiaWithNoScreen =
        new(new GpuAdapterKey(2, 0), "Discrete", 0x10DE, 0x1F99, 6 * Gibibyte, 0, 8 * Gibibyte);

    [Test]
    public void The_card_with_no_screen_plugged_is_seen_and_gets_its_download()
    {
        FakeProbe laptop = new(IntelWithTheScreen, NvidiaWithNoScreen);
        ReleaseManifest manifest = new("1.0.0", "https://example.invalid/", 10, [
            new ReleaseArchive("a", [new ReleasePart("a.zip", 1, new string('0', 64))]),
            new ReleaseArchive("cuda", [new ReleasePart("cuda.zip", 1, new string('1', 64))], GpuVendor: "10de", InstalledBytes: 2),
        ]);

        IReadOnlyList<GpuAdapter> adapters = MachineGpu.Installed(laptop);

        Assert.Multiple(() =>
        {
            Assert.That(MachineGpu.Choose(adapters), Is.EqualTo(GpuSupport.Measured));
            Assert.That(manifest.ForMachine(adapters).Archives.Select(archive => archive.Name), Is.EqualTo(new[] { "a", "cuda" }));
        });
    }

    [Test]
    public void The_installer_and_BAXY_read_the_same_vendors_in_the_same_order()
    {
        FakeProbe laptop = new(IntelWithTheScreen, NvidiaWithNoScreen);

        string?[] installer = [.. MachineGpu.Installed(laptop).Select(adapter => MachineGpu.Vendor(adapter.DeviceId))];
        string[] baxy = [.. WindowsGpuVendors.Read(laptop).Select(vendor => vendor.ToString("x4", System.Globalization.CultureInfo.InvariantCulture))];

        Assert.That(installer, Is.EqualTo(baxy));
        Assert.That(baxy, Is.EqualTo(new[] { "8086", "10de" }));
    }

    [Test]
    public void The_memory_told_is_the_dedicated_video_memory_of_the_card()
    {
        GpuAdapterReading small = NvidiaWithNoScreen with { DedicatedVideoMemoryBytes = 2 * Gibibyte };

        Assert.Multiple(() =>
        {
            Assert.That(MachineGpu.Installed(new FakeProbe(NvidiaWithNoScreen))[0].MemoryBytes, Is.EqualTo(6L * 1024 * 1024 * 1024));
            Assert.That(MachineGpu.Choose(MachineGpu.Installed(new FakeProbe(IntelWithTheScreen, small))), Is.EqualTo(GpuSupport.TooLittleMemory));
        });
    }

    [Test]
    public void A_vendor_that_is_not_a_PCI_id_is_no_known_maker()
    {
        // DXGI_ADAPTER_DESC1.VendorId above 0xFFFF is an ACPI id: its first four digits are nobody's PCI id.
        GpuAdapterReading acpi = NvidiaWithNoScreen with { VendorId = 0x10DE_4D4F };

        IReadOnlyList<GpuAdapter> adapters = MachineGpu.Installed(new FakeProbe(acpi));

        Assert.That(MachineGpu.Vendor(adapters[0].DeviceId), Is.Null);
        Assert.That(MachineGpu.Choose(adapters), Is.EqualTo(GpuSupport.None));
    }

    private static IEnumerable<Exception> WhatDxgiThrows() =>
    [
        new PlatformNotSupportedException("no hardware adapter"),
        new InvalidOperationException("DXGI did not return a factory."),
        // DXGI_ERROR_UNSUPPORTED, as the runtime itself raises it for a failed HRESULT.
        Marshal.GetExceptionForHR(unchecked((int)0x887A0004)) ?? new InvalidOperationException("no exception for the HRESULT"),
        new Win32Exception(5),
        new DllNotFoundException("dxgi.dll"),
        new EntryPointNotFoundException("CreateDXGIFactory1"),
    ];

    [TestCaseSource(nameof(WhatDxgiThrows))]
    public void A_machine_where_Windows_cannot_say_has_no_card_for_both(Exception failure)
    {
        FakeProbe broken = new() { Failure = failure };

        Assert.Multiple(() =>
        {
            Assert.That(MachineGpu.Installed(broken), Is.Empty);
            Assert.That(WindowsGpuVendors.Read(broken), Is.Empty);
            Assert.That(MachineGpu.Choose(MachineGpu.Installed(broken)), Is.EqualTo(GpuSupport.None));
        });
    }

    [Test]
    public void The_log_names_every_card_with_its_memory()
    {
        IReadOnlyList<GpuAdapter> adapters = MachineGpu.Installed(new FakeProbe(IntelWithTheScreen, NvidiaWithNoScreen));

        Assert.That(
            MachineGpu.Describe(adapters),
            Is.EqualTo(@"Measured [PCI\VEN_8086&DEV_9A49 0.1 GB, PCI\VEN_10DE&DEV_1F99 6.4 GB]"));
        Assert.That(MachineGpu.Describe([]), Is.EqualTo("None []"));
    }

    [Test]
    public void On_this_machine_the_installer_reads_what_BAXY_reads()
    {
        string?[] installer = [.. MachineGpu.Installed().Select(adapter => MachineGpu.Vendor(adapter.DeviceId))];
        string[] baxy = [.. WindowsGpuVendors.Read().Select(vendor => vendor.ToString("x4", System.Globalization.CultureInfo.InvariantCulture))];

        Assert.That(installer, Is.EqualTo(baxy));
    }

    [Test]
    public void The_installer_compiles_the_source_BAXY_reads_its_cards_with_and_no_reading_of_its_own()
    {
        string root = RepositoryRoot();
        string project = File.ReadAllText(Path.Combine(root, "src", "Baxy.Installer", "Baxy.Installer.csproj"));
        string machine = File.ReadAllText(Path.Combine(root, "src", "Baxy.Installer", "MachineGpu.cs"));

        Assert.Multiple(() =>
        {
            Assert.That(project, Does.Contain(@"..\Baxy.Providers.Windows\SystemStatus\WindowsGpuVendors.cs"));
            Assert.That(project, Does.Contain(@"..\Baxy.Providers.Windows\SystemStatus\WindowsGpuStatusProbe.cs"));
            Assert.That(machine, Does.Not.Contain("user32.dll"));
            Assert.That(machine, Does.Not.Contain("LibraryImport"));
        });
    }

    private static string RepositoryRoot()
    {
        DirectoryInfo? folder = new(TestContext.CurrentContext.TestDirectory);
        while (folder is not null && !File.Exists(Path.Combine(folder.FullName, "Baxy.slnx")))
        {
            folder = folder.Parent;
        }

        return folder?.FullName ?? throw new InvalidOperationException("the repository root was not found");
    }

    private sealed class FakeProbe(params GpuAdapterReading[] adapters) : IGpuStatusProbe
    {
        internal Exception? Failure { get; init; }

        public IGpuStatusProbeSession OpenSession() => new Session(this, adapters);

        private sealed class Session(FakeProbe owner, IReadOnlyList<GpuAdapterReading> adapters) : IGpuStatusProbeSession
        {
            public IReadOnlyList<GpuAdapterReading> ReadAdapters() => owner.Failure is null ? adapters : throw owner.Failure;

            public ValueTask<IReadOnlyList<GpuUsageReading>> ReadUsageAsync(
                IReadOnlyList<GpuAdapterKey> adapters,
                TimeSpan samplingInterval,
                CancellationToken cancellationToken) => throw new NotSupportedException();

            public bool IsCurrent() => true;

            public void Dispose()
            {
            }
        }
    }
}
