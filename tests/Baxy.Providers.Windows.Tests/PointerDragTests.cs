using System.Reflection;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Feria 2026-10-27, caso 18: drawing on a canvas had no tool (the clicks on one point left nothing). input.pointer.drag
/// holds the left button down along a path on the body of the window's last look, its points fractions of that body.
/// The button is always let go, and the drag is verified only by the image inside the body: an image not read is said
/// unread, never unchanged.
/// </summary>
[TestFixture]
public sealed class PointerDragTests
{
    // The window's capture: 256 × 192 at (100, 80); the body (its canvas) lies at (132, 112), 160 × 96.
    private const int Left = 100, Top = 80, Width = 256, Height = 192;
    private static readonly WindowsVisibleControlAdapter.Rect Canvas = new(132, 112, 160, 96);

    [Test]
    public void ALookMarksItsBodyAndOnlyThatIndexIsABody()
    {
        using JsonDocument look = JsonDocument.Parse("""
            {"controls":[{"kind":"Button","name":"Lápiz","id":"1.1","state":"","value":null},
            {"kind":"Pane","name":"(pane)","id":"9.1","state":"","value":null,"rect":{"x":132,"y":112,"w":160,"h":96},
            "body":true}]}
            """);

        List<WindowsVisibleControlAdapter.ViewControl> controls = WindowsVisibleControlAdapter.ParseControls(look.RootElement);

        Assert.That(controls.Select(control => control.Body), Is.EqualTo(new[] { false, true }));
    }

    [Test]
    public void APathIsPressedWholeInsideTheBodyAndVerifiedByItsImage()
    {
        WithWindow(window =>
        {
            using var drag = new Drag(window, after: Painted(inside: true));

            ExternalCapabilityReceipt receipt = drag.Run("""{"index":1,"points":[0,0,1,1,0,1]}""");

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
                Assert.That(receipt.EffectObserved, Is.True);
                Assert.That(receipt.Result!.Value.GetProperty("authority").GetString(),
                    Is.EqualTo("win32_pointer_drag_body_surface_postread"));
                Assert.That(drag.Buttons, Is.EqualTo(new[] { true, false }), "down once, up once");
                Assert.That(drag.Moves[0], Is.EqualTo((132, 112)), "the first point is the body's top left");
                Assert.That(drag.Moves, Does.Contain((291, 207)), "through its bottom right");
                Assert.That(drag.Moves[^1], Is.EqualTo((132, 207)), "and ends on its bottom left");
                Assert.That(drag.Moves.All(point => point.X >= 132 && point.X <= 291 && point.Y >= 112 && point.Y <= 207),
                    Is.True, "never outside the body");
                Assert.That(drag.Lease.Burst!.Restores, Is.GreaterThanOrEqualTo(1));
            });
        });
    }

    // The person's input stops the path partway: the button is let go all the same, and what was drawn is not the path.
    [Test]
    public void ThePersonsInputStopsThePathAndTheButtonIsLetGo()
    {
        WithWindow(window =>
        {
            using var drag = new Drag(window, after: Painted(inside: true)) { PersonActsAfterMoves = 3 };

            ExternalCapabilityReceipt receipt = drag.Run("""{"index":1,"points":[0,0,1,1]}""");

            Assert.Multiple(() =>
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("input_user_interrupted"));
                Assert.That(receipt.EffectMayHaveOccurred, Is.True);
                Assert.That(drag.Buttons, Is.EqualTo(new[] { true, false }));
            });
        });
    }

    // Regla 3: an image not read after the drag says nothing of it; one that changed only outside the body (the status
    // bar that follows the pointer) is no stroke on the canvas.
    [Test]
    public void AnUnreadImageIsUnreadAndAChangeOutsideTheBodyIsUnchanged()
    {
        WithWindow(window =>
        {
            using var notRead = new Drag(window, after: null);
            using var besides = new Drag(window, after: Painted(inside: false));
            ExternalCapabilityReceipt unread = notRead.Run("""{"index":1,"points":[0.2,0.2,0.8,0.8]}""");
            ExternalCapabilityReceipt outside = besides.Run("""{"index":1,"points":[0.2,0.2,0.8,0.8]}""");

            Assert.Multiple(() =>
            {
                Assert.That(unread.ErrorCode, Is.EqualTo("pointer_drag_postread_unread"));
                Assert.That(unread.EffectMayHaveOccurred, Is.True);
                Assert.That(outside.ErrorCode, Is.EqualTo("pointer_drag_surface_unchanged"));
                Assert.That(outside.EffectMayHaveOccurred, Is.True);
            });
        });
    }

    // Contracases, nothing pressed and no burst taken: an index that is no body (a button of the look), a window other
    // than the look's, a path of one point or with a point outside the body.
    [TestCase("""{"index":0,"points":[0,0,1,1]}""", "pointer_drag_index_not_body")]
    [TestCase("""{"index":1,"points":[0,0,1,1],"window":1}""", "visible_control_identity_stale")]
    [TestCase("""{"index":1,"points":[0.5,0.5]}""", "pointer_drag_argument_invalid")]
    [TestCase("""{"index":1,"points":[0,0,1.5,1]}""", "pointer_drag_argument_invalid")]
    [TestCase("""{"index":1,"points":[0,0,1]}""", "pointer_drag_argument_invalid")]
    public void WhatIsNoPathOnTheLookedBodyIsRefusedBeforeAnyEffect(string arguments, string error)
    {
        WithWindow(window =>
        {
            using var drag = new Drag(window, after: Painted(inside: true));

            ExternalCapabilityReceipt receipt = drag.Run(arguments);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo(error));
                Assert.That(receipt.EffectMayHaveOccurred, Is.False);
                Assert.That(drag.Lease.Burst, Is.Null);
                Assert.That(drag.Buttons, Is.Empty);
            });
        });
    }

    // The capture after the drag: a dark cell inside the body, or in the window's bottom strip outside it.
    private static byte[] Painted(bool inside)
    {
        byte[] bmp = Bitmap();
        (int x, int y) = inside ? (Canvas.X - Left + 40, Canvas.Y - Top + 40) : (8, Height - 8);
        Paint(bmp, x, y);
        return bmp;
    }

    // A white 32-bit bitmap of the window's size, top-down.
    private static byte[] Bitmap()
    {
        const int header = 54;
        byte[] bmp = new byte[header + (Width * Height * 4)];
        bmp[0] = (byte)'B';
        bmp[1] = (byte)'M';
        BitConverter.GetBytes(bmp.Length).CopyTo(bmp, 2);
        BitConverter.GetBytes(header).CopyTo(bmp, 10);
        BitConverter.GetBytes(40).CopyTo(bmp, 14);
        BitConverter.GetBytes(Width).CopyTo(bmp, 18);
        BitConverter.GetBytes(-Height).CopyTo(bmp, 22);
        BitConverter.GetBytes((short)1).CopyTo(bmp, 26);
        BitConverter.GetBytes((short)32).CopyTo(bmp, 28);
        Array.Fill(bmp, (byte)0xFF, header, bmp.Length - header);
        return bmp;
    }

    private static void Paint(byte[] bmp, int x, int y)
    {
        int at = 54 + (((y * Width) + x) * 4);
        bmp[at] = bmp[at + 1] = bmp[at + 2] = 0;
    }

    private static VisibleControlSurface.CapturedWindow Capture(nint window, byte[] bmp, string sha) =>
        new(window, bmp, Left, Top, Width, Height, sha);

    // A drag on a look of the window: [0] a button, [1] its body; every input is recorded, none is sent.
    private sealed class Drag : IDisposable
    {
        private readonly nint _window;
        private readonly byte[]? _after;
        private readonly WindowsVisibleControlAdapter _controls;
        private int _captures;

        internal Drag(nint window, byte[]? after)
        {
            _window = window;
            _after = after;
            _controls = new WindowsVisibleControlAdapter(new ComputerUsePerceptionTests.ScriptedUiaWorker(), null, null);
            RememberView(_controls, window);
            Lease = new GrantingLease();
        }

        internal GrantingLease Lease { get; }

        public void Dispose() => _controls.Dispose();

        internal List<(int X, int Y)> Moves { get; } = [];

        internal List<bool> Buttons { get; } = [];

        internal int? PersonActsAfterMoves { get; init; }

        internal ExternalCapabilityReceipt Run(string arguments)
        {
            using JsonDocument parsed = JsonDocument.Parse(arguments);
            var named = new Dictionary<string, object?> { ["window"] = (long)_window };
            foreach (JsonProperty property in parsed.RootElement.EnumerateObject())
                named[property.Name] = property.Value.Clone();
            JsonElement call = JsonSerializer.SerializeToElement(named);
            var adapter = new WindowsPointerDragAdapter(
                _controls,
                Lease,
                capture: (_, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                    _captures++ == 0 ? Capture(_window, Bitmap(), "before")
                    : _after is null ? null
                    : Capture(_window, _after, "after")),
                shows: (_, _, _) => true,
                inFront: _ => true,
                pointAt: (burst, x, y) =>
                {
                    if (!burst.MayAct)
                        return false;
                    Moves.Add((x, y));
                    if (Moves.Count == PersonActsAfterMoves && burst is FakeInputBurst fake)
                        fake.UserActed = true;
                    return true;
                },
                button: Buttons.Add);
            return adapter.InvokeAsync("input.pointer.drag", call, CancellationToken.None).AsTask().GetAwaiter().GetResult();
        }
    }

    // A lease that grants its burst at once: the person paused.
    private sealed class GrantingLease : IForegroundLease
    {
        internal FakeInputBurst? Burst { get; private set; }

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken)
        {
            Burst = new FakeInputBurst();
            return ValueTask.FromResult<IInputBurst>(Burst);
        }

        public ValueTask<IInputBurst> AcquireForHelperAsync(CancellationToken cancellationToken) =>
            AcquireAsync(0, cancellationToken);
    }

    // The last view, as input.visible.controls leaves it: [0] a button, [1] the window's body.
    private static void RememberView(WindowsVisibleControlAdapter adapter, nint window)
    {
        FieldInfo field = typeof(WindowsVisibleControlAdapter).GetField(
            "_lastView", BindingFlags.NonPublic | BindingFlags.Instance)!;
        List<WindowsVisibleControlAdapter.ViewControl> controls =
        [
            new() { Index = 0, Id = "1.1", Kind = "Button", Name = "Lápiz", RectValue = new(110, 84, 20, 20) },
            new() { Index = 1, Id = "9.1", Kind = "Pane", Name = "(pane)", RectValue = Canvas, Body = true },
        ];
        object view = Activator.CreateInstance(
            field.FieldType, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance, null,
            [window, controls], null)!;
        field.SetValue(adapter, view);
    }

    // An off-screen window of this test that takes no activation: alive for the adapter, never the person's.
    private static void WithWindow(Action<nint> test)
    {
        nint window = CreateWindowEx(0x08000080, "STATIC", "BAXY drag fixture", 0x90000000u,
            -31000, -31000, 200, 120, 0, 0, 0, 0);
        Assert.That(window, Is.Not.EqualTo(nint.Zero));
        try
        {
            test(window);
        }
        finally
        {
            _ = DestroyWindow(window);
        }
    }

    [DllImport("user32.dll", EntryPoint = "CreateWindowExW",
        CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    private static extern nint CreateWindowEx(uint extendedStyle, string className,
        string title, uint style, int x, int y, int width, int height,
        nint parent, nint menu, nint instance, nint parameter);

    [DllImport("user32.dll", ExactSpelling = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DestroyWindow(nint window);
}
