using System;
using System.Windows.Forms;
static class C03WindowFixture {
    [STAThread] static void Main() {
        Application.EnableVisualStyles();
        using (var form = new Form()) {
            form.Text = "C03WindowFixture - ventana de prueba sin documentos";
            form.WindowState = FormWindowState.Maximized;
            Application.Run(form);
        }
    }
}
