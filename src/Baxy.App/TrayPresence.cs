using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace Baxy.App;

/// <summary>
/// Icono de la bandeja y su menú. No conoce el ViewModel: emite pedidos.
/// </summary>
internal sealed class TrayPresence : IDisposable
{
    private readonly NotifyIcon _icon;
    private readonly ToolStripMenuItem _listenItem;
    private Icon? _mark;
    private bool _disposed;

    internal TrayPresence()
    {
        _mark = CreateMark();
        _listenItem = new ToolStripMenuItem("Escuchar")
        {
            CheckOnClick = false,
            Checked = true,
        };
        _listenItem.Click += (_, _) => ListenToggleRequested?.Invoke();

        var showItem = new ToolStripMenuItem("Mostrar BAXY");
        showItem.Click += (_, _) => ShowRequested?.Invoke();
        var quitItem = new ToolStripMenuItem("Salir");
        quitItem.Click += (_, _) => QuitRequested?.Invoke();

        var menu = new ContextMenuStrip();
        menu.Items.Add(showItem);
        menu.Items.Add(_listenItem);
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add(quitItem);

        _icon = new NotifyIcon
        {
            Icon = _mark,
            Text = "BAXY",
            Visible = true,
            ContextMenuStrip = menu,
        };
        _icon.DoubleClick += (_, _) => ShowRequested?.Invoke();
    }

    internal event Action? ShowRequested;

    internal event Action? QuitRequested;

    internal event Action? ListenToggleRequested;

    internal void SetListening(bool listening)
    {
        if (_disposed)
        {
            return;
        }

        _listenItem.Checked = listening;
        _listenItem.Text = listening ? "Escuchar (encendida)" : "Escuchar (apagada)";
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _icon.Visible = false;
        _icon.Dispose();
        _mark?.Dispose();
        _mark = null;
    }

    private static Icon CreateMark()
    {
        var bitmap = new Bitmap(16, 16);
        using (Graphics graphics = Graphics.FromImage(bitmap))
        using (var background = new SolidBrush(System.Drawing.Color.FromArgb(184, 58, 74)))
        using (var foreground = new SolidBrush(System.Drawing.Color.White))
        using (var font = new Font(
            "Segoe UI",
            8,
            System.Drawing.FontStyle.Bold,
            GraphicsUnit.Pixel))
        {
            graphics.Clear(System.Drawing.Color.Transparent);
            graphics.FillRectangle(background, 0, 0, 16, 16);
            graphics.DrawString("B", font, foreground, 2, 1);
        }

        nint handle = bitmap.GetHicon();
        Icon owned = (Icon)Icon.FromHandle(handle).Clone();
        _ = NativeMethods.DestroyIcon(handle);
        bitmap.Dispose();
        return owned;
    }

    private static class NativeMethods
    {
        [DllImport("user32.dll", SetLastError = true)]
        internal static extern bool DestroyIcon(nint handle);
    }
}
