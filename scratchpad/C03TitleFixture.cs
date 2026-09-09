using System;
using System.Windows.Forms;
static class C03TitleFixture {
    [STAThread] static void Main() {
        Application.EnableVisualStyles();
        using (var form = new Form()) {
            form.Text = "Ventana C03 de prueba";
            form.WindowState = FormWindowState.Maximized;
            Application.Run(form);
        }
    }
}
