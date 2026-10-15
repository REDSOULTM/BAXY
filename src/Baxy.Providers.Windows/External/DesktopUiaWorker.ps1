# Worker UIA persistente del motor de computer use (CONTRATO_VISTA_ACCION.md §1, §2).
#
# Una sola carga de UIAutomationClient y de Add-Type por vida del proceso: la
# herencia (gemma4_agent, uia_fast.py) midio 243 ms de spawn mas 385 ms de
# Add-Type por cada llamada de la ruta anterior (DesktopListVisible.ps1 y
# DesktopClickVisible.ps1, que este worker sustituye). Protocolo: una linea JSON
# por peticion en stdin, una linea JSON por respuesta en stdout; nunca escribe
# otra cosa en stdout. El proceso termina con «exit», con EOF o cuando muere
# su padre.
#
# Comandos:
#   {"cmd":"ping"}
#   {"cmd":"view","hwnd":123,"limit":60}
#   {"cmd":"signature","hwnd":123,"limit":60,"budgetMs":1200}   (tipo y nombre de los primeros controles y si hay texto
#      seleccionado, acotado en tiempo; no toca la ultima vista: Do-Signature)
#   {"cmd":"click","hwnd":123,"aliases":["Biblioteca"],"controlId":"42.1837.4"}
#      (con «manner»: open | menu | double, ese control de la vista abierto por su flecha, su menu contextual o un doble
#      clic, solo por su identidad: Invoke-MannerControl)
#   {"cmd":"at","hwnd":123,"x":640,"y":380,"aliases":["Biblioteca"]}   (el control con patron del punto que la etiqueta nombra, sin raton;
#      con «controlId», ese control del punto aunque no tenga nombre: el que su tooltip nombro)
#   {"cmd":"postread"}   (el control del ultimo clic: ausente, seleccionado o conmutado)
#   {"cmd":"scroll","hwnd":123,"controlId":"42.1837.4","direction":"down","amount":3}
#   {"cmd":"find","hwnd":123,"aliases":["Biblioteca"]}
#   {"cmd":"reveal","hwnd":123,"aliases":["Omega"],"direction":"down","amount":10}   (trae a la vista un elemento fuera de ella)
#   {"cmd":"field","hwnd":123,"controlId":"42.1837.4","text":"hola","replace":false}   (texto dirigido; sin «text», solo lo lee)
#   {"cmd":"script","script":"...","args":["123"]}   (un guion de UserBrowserScripts, $args como en -Command)
#   {"cmd":"unnamed","hwnd":123,"limit":24}   (accionables sin nombre ni respaldo: candidatos a leer su tooltip)
#   {"cmd":"tooltips","hwnd":123,"pids":[4242]}   (los tooltips visibles de esos procesos y de la ventana, con su texto)
#   {"cmd":"exit"}
#
# -DpiUnaware: el worker de los guiones del navegador conserva la escala que
# tenia el PowerShell de cada llamada al que sustituye (sus coordenadas de
# pestana se convierten en el proceso del producto).
param([switch]$DpiUnaware)
$ErrorActionPreference='Stop'
[Console]::InputEncoding=[System.Text.Encoding]::UTF8
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -ReferencedAssemblies Accessibility -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class BaxyUiaWorkerNative {
  private delegate bool EnumProc(IntPtr hwnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
  [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr hwnd, uint command);
  [DllImport("user32.dll")] private static extern bool EnumWindows(EnumProc callback, IntPtr value);
  [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr lParam);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int count);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetClassName(IntPtr hwnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr hwnd);
  [DllImport("user32.dll")] private static extern IntPtr SendMessage(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] private static extern bool PostMessage(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] private static extern IntPtr ChildWindowFromPointEx(IntPtr parent, POINT point, uint flags);
  [DllImport("user32.dll")] private static extern bool ScreenToClient(IntPtr hwnd, ref POINT point);
  [DllImport("user32.dll")] private static extern uint GetDpiForWindow(IntPtr hwnd);
  [DllImport("user32.dll")] private static extern IntPtr MonitorFromWindow(IntPtr hwnd, uint flags);
  [DllImport("shcore.dll")] private static extern int GetDpiForMonitor(IntPtr monitor, int kind, out uint dpiX, out uint dpiY);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint procId);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
  [DllImport("user32.dll")] public static extern IntPtr SetProcessDpiAwarenessContext(IntPtr context);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
  // Windows PowerShell 5.1 compila Add-Type con C# 5: sin declaraciones «out» en linea (UI1273).
  public static IntPtr[] FindVisibleButtons(IntPtr top, string[] labels) {
    var matches=new List<IntPtr>();
    if(top==IntPtr.Zero) return matches.ToArray();
    EnumChildWindows(top,(child,unusedChild)=>{
      var cls=new StringBuilder(128);GetClassName(child,cls,cls.Capacity);
      if(cls.ToString().IndexOf("BUTTON",StringComparison.OrdinalIgnoreCase)<0
          || !IsWindowVisible(child) || !IsWindowEnabled(child)) return true;
      var name=new StringBuilder(512);GetWindowText(child,name,name.Capacity);
      foreach(string label in labels) if(string.Equals(label,name.ToString(),StringComparison.OrdinalIgnoreCase)) {matches.Add(child);break;}
      return true;
    },IntPtr.Zero);
    return matches.ToArray();
  }
  // The visible child windows of a window, at most «limit» (Get-ShownDescendants looks among them for long lists).
  public static IntPtr[] VisibleChildWindows(IntPtr top, int limit) {
    var found=new List<IntPtr>();
    if(top==IntPtr.Zero) return found.ToArray();
    EnumChildWindows(top,(child,unusedChild)=>{ if(IsWindowVisible(child)) found.Add(child); return found.Count<limit; },IntPtr.Zero);
    return found.ToArray();
  }
  public static void Click(IntPtr hwnd) { SendMessage(hwnd,0x00F5,IntPtr.Zero,IntPtr.Zero); }
  public static string Text(IntPtr hwnd) { var text=new StringBuilder(512);GetWindowText(hwnd,text,text.Capacity);return text.ToString(); }
  // A press posted to the deepest child window under a screen point: a classic Win32 window reads it from its message
  // queue, so neither the cursor nor the foreground moves. Only where the window counts in the screen's own pixels
  // (its DPI is its monitor's): a posted point is never rescaled for a window that Windows scales.
  public static bool PostClick(IntPtr top, int x, int y) {
    IntPtr target=ClassicAt(top,x,y);
    return target!=IntPtr.Zero && PostPress(target,x,y,false);
  }
  // Review of fable/cu-v3-recibo-del-clic-por-estado (finding 2): a row of a list or a tree takes the posted press only
  // when the deepest classic child window under its point is the window that holds it (as the double click): a row
  // scrolled out of its list, whose point falls on a sibling window, is never pressed through that sibling.
  public static bool PostClick(IntPtr top, int x, int y, IntPtr holder) {
    IntPtr target=ClassicAt(top,x,y);
    return target!=IntPtr.Zero && holder!=IntPtr.Zero && target==holder && PostPress(target,x,y,false);
  }
  // r20b palanca 4 (v3-42, v3-43): a toolbar button the UIA client sees through its MSAA proxy. Its Invoke is the
  // proxy's default action, which pressed with the physical mouse (an unmarked click at the button's point, measured
  // within 200 ms of the Invoke). Instead the press is posted to the bar, only when the deepest classic window under the
  // point (from the bar's own root, whatever is in front) is the bar and the bar's own hit test answers this child.
  // Answers: none (no bar at the point, or scaled), other (another window or another button there: nothing is sent),
  // nohit (the bar did not answer), post-failed or posted.
  public static string ToolbarPress(IntPtr top, int x, int y, IntPtr bar, int child) {
    if(bar==IntPtr.Zero || !IsWindow(bar)) return "none";
    IntPtr root=GetAncestor(bar,2);
    IntPtr target=ClassicAt(root!=IntPtr.Zero ? root : top,x,y);
    if(target==IntPtr.Zero) return "none";
    if(target!=bar) return "other";
    try {
      Guid iid=new Guid("618736e0-3c3d-11cf-810c-00aa00389b71");
      object raw; if(AccessibleObjectFromWindow(bar,0xFFFFFFFC,ref iid,out raw)!=0 || raw==null) return "nohit";
      Accessibility.IAccessible accessible=raw as Accessibility.IAccessible; if(accessible==null) return "nohit";
      object hit=accessible.accHitTest(x,y);
      if(hit==null) return "nohit";
      if(!(hit is int) || (int)hit!=child) return "other";
    } catch (Exception) { return "nohit"; }
    return PostPress(target,x,y,false) ? "posted" : "post-failed";
  }
  // Goal v3 B3: the double click, posted the same way, and only when the deepest classic child window under the point
  // is the window that holds the element (review finding 2: another child window at that point is not the element).
  public static bool PostDoubleClick(IntPtr top, int x, int y, IntPtr holder) {
    IntPtr target=ClassicAt(top,x,y);
    return target!=IntPtr.Zero && target==holder && PostPress(target,x,y,true);
  }
  // The deepest child window under the screen point, when it counts in the screen's own pixels; zero otherwise.
  private static IntPtr ClassicAt(IntPtr top, int x, int y) {
    if(top==IntPtr.Zero) return IntPtr.Zero;
    IntPtr target=top;
    for(int depth=0;depth<32;depth++){
      POINT local=new POINT(); local.X=x; local.Y=y;
      if(!ScreenToClient(target,ref local)) return IntPtr.Zero;
      IntPtr child=ChildWindowFromPointEx(target,local,0x0001|0x0002|0x0004);
      if(child==IntPtr.Zero){ if(depth==0) return IntPtr.Zero; break; }
      if(child==target) break;
      target=child;
    }
    return SameDpi(target) ? target : IntPtr.Zero;
  }
  // Move, down, up (and, for a double click, the double-click message and its up) in the window's client coordinates.
  private static bool PostPress(IntPtr target, int x, int y, bool twice) {
    POINT client=new POINT(); client.X=x; client.Y=y;
    if(!ScreenToClient(target,ref client)) return false;
    IntPtr position=(IntPtr)(((client.Y & 0xFFFF) << 16) | (client.X & 0xFFFF));
    bool posted=PostMessage(target,0x0200,IntPtr.Zero,position)
      && PostMessage(target,0x0201,(IntPtr)1,position)
      && PostMessage(target,0x0202,IntPtr.Zero,position);
    return posted && (!twice || (PostMessage(target,0x0203,(IntPtr)1,position) && PostMessage(target,0x0202,IntPtr.Zero,position)));
  }
  // Ronda 20b, palanca 7 (v3-49): the classic menu bar of a window (its HMENU) is read statically, without opening any
  // popup: each command entry with its path («Ver › Detalles»), the shortcut written after its tab, and its checked or
  // disabled state. A submenu empty in that static read is filled by the application when it opens (FillsOnOpen). A
  // window without an HMENU (a ribbon, UWP, Qt, Chromium) gives none. Pressing an entry is the WM_COMMAND its window
  // receives from the menu loop, posted with neither the front nor the cursor.
  [DllImport("user32.dll")] private static extern IntPtr GetMenu(IntPtr hwnd);
  [DllImport("user32.dll")] private static extern int GetMenuItemCount(IntPtr menu);
  [DllImport("user32.dll")] private static extern IntPtr GetSubMenu(IntPtr menu, int position);
  [DllImport("user32.dll")] private static extern uint GetMenuItemID(IntPtr menu, int position);
  [DllImport("user32.dll")] private static extern uint GetMenuState(IntPtr menu, uint item, uint flags);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetMenuString(IntPtr menu, uint item, StringBuilder text, int max, uint flags);
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] private struct MENUITEMINFO { public uint cbSize; public uint fMask; public uint fType; public uint fState; public uint wID; public IntPtr hSubMenu; public IntPtr hbmpChecked; public IntPtr hbmpUnchecked; public IntPtr dwItemData; public IntPtr dwTypeData; public uint cch; public IntPtr hbmpItem; }
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern bool GetMenuItemInfo(IntPtr menu, uint item, bool byPosition, ref MENUITEMINFO info);
  // Revision 2 de la ronda 20b (B2): la entrada es marcable cuando su lectura estatica la muestra marcada (MFS_CHECKED)
  // o de opcion (MFT_RADIOCHECK), o con mapas de bits propios de marca: un ajuste, nunca un estado de ahora.
  private static bool MenuCheckable(IntPtr menu, int position, uint state) {
    if((state & 0x8)!=0) return true;
    var info=new MENUITEMINFO();
    info.cbSize=(uint)Marshal.SizeOf(typeof(MENUITEMINFO));
    info.fMask=0x100 | 0x1 | 0x8;
    if(!GetMenuItemInfo(menu,(uint)position,true,ref info)) return false;
    return (info.fType & 0x200)!=0 || (info.fState & 0x8)!=0 || info.hbmpChecked!=IntPtr.Zero;
  }
  public class MenuEntry { public string Path = ""; public string Shortcut = ""; public int Id; public bool Checked; public bool Checkable; public bool Disabled; public bool FillsOnOpen; }
  public static MenuEntry[] MenuEntries(IntPtr hwnd, int limit) {
    var found=new List<MenuEntry>();
    if(hwnd==IntPtr.Zero || !IsWindow(hwnd)) return found.ToArray();
    IntPtr bar=GetMenu(hwnd);
    if(bar==IntPtr.Zero) return found.ToArray();
    AddMenuEntries(bar,"",found,limit,0);
    return found.ToArray();
  }
  public static string MenuLabel(string raw) {
    string text=raw ?? "";
    int tab=text.IndexOf('\t');
    if(tab>=0) text=text.Substring(0,tab);
    text=text.Replace("&&","\u0001").Replace("&","").Replace("\u0001","&");
    return text.Trim();
  }
  public static string MenuShortcut(string raw) {
    string text=raw ?? "";
    int tab=text.IndexOf('\t');
    return tab>=0 ? text.Substring(tab+1).Trim() : "";
  }
  private static void AddMenuEntries(IntPtr menu, string prefix, List<MenuEntry> found, int limit, int depth) {
    int count=GetMenuItemCount(menu);
    for(int position=0;position<count && found.Count<limit;position++){
      uint state=GetMenuState(menu,(uint)position,0x400);
      if(state==0xFFFFFFFF) continue;
      IntPtr sub=GetSubMenu(menu,position);
      if(sub==IntPtr.Zero && (state & 0x800)!=0) continue;
      var text=new StringBuilder(256);
      GetMenuString(menu,(uint)position,text,text.Capacity,0x400);
      string label=MenuLabel(text.ToString());
      if(label.Length==0) continue;
      string path=prefix.Length==0 ? label : prefix+" "+(char)0x203A+" "+label;
      bool disabled=(state & 0x3)!=0;
      if(sub!=IntPtr.Zero){
        if(depth>=3) continue;
        if(GetMenuItemCount(sub)<=0){ var empty=new MenuEntry(); empty.Path=path; empty.Disabled=disabled; empty.FillsOnOpen=true; found.Add(empty); continue; }
        AddMenuEntries(sub,path,found,limit,depth+1);
        continue;
      }
      uint id=GetMenuItemID(menu,position);
      if(id==0xFFFFFFFF || id==0) continue;
      var entry=new MenuEntry();
      entry.Path=path; entry.Shortcut=MenuShortcut(text.ToString()); entry.Id=(int)(id & 0xFFFF);
      entry.Checked=(state & 0x8)!=0; entry.Disabled=disabled;
      try { entry.Checkable=MenuCheckable(menu,position,state); } catch { entry.Checkable=entry.Checked; }
      found.Add(entry);
    }
  }
  // The entry's state now, by its command (searched through the submenus): -1 when the window has no such entry.
  public static int MenuCommandState(IntPtr hwnd, int id) {
    if(hwnd==IntPtr.Zero || !IsWindow(hwnd)) return -1;
    IntPtr bar=GetMenu(hwnd);
    if(bar==IntPtr.Zero) return -1;
    uint state=GetMenuState(bar,(uint)id,0);
    return state==0xFFFFFFFF ? -1 : (int)(state & 0xFFFF);
  }
  public static bool PostCommand(IntPtr hwnd, int id) {
    if(hwnd==IntPtr.Zero || !IsWindow(hwnd) || id<=0) return false;
    return PostMessage(hwnd,0x0111,(IntPtr)(id & 0xFFFF),IntPtr.Zero);
  }
  // Goal v3 B3: the context menu of a control that is its own classic window, asked by the message a right click or
  // Shift+F10 sends it (WM_CONTEXTMENU at the control's point), with neither the cursor nor the keyboard.
  public static bool PostContextMenu(IntPtr own, int x, int y) {
    if(own==IntPtr.Zero || !IsWindow(own)) return false;
    IntPtr position=(IntPtr)(((y & 0xFFFF) << 16) | (x & 0xFFFF));
    return PostMessage(own,0x007B,own,position);
  }
  // Ronda 20b, palanca 6, revision 2 (hallazgo 3): the Escape a popup's own window gets as its key (WM_KEYDOWN and
  // WM_KEYUP of VK_ESCAPE posted to it), with neither the keyboard nor the front: the menu loop of a context menu and a
  // flyout's host close on it. Never to a window that is not alive.
  public static bool PostEscape(IntPtr popup) {
    if(popup==IntPtr.Zero || !IsWindow(popup)) return false;
    return PostMessage(popup,0x0100,(IntPtr)0x1B,(IntPtr)0x00010001)
      && PostMessage(popup,0x0101,(IntPtr)0x1B,new IntPtr(unchecked((int)0xC0010001)));
  }
  // fable/cu-v3-clic-chromium: the render surface of a Chromium host (WebView2, CEF, Electron), told by its window
  // class, never by an application's name. Measured live on a WebView2 messaging client behind the person's window: a
  // press posted to its render surface window in client coordinates gave its search field the keyboard's focus
  // and selected a tab, with neither the front nor the cursor moved; SelectionItem.Select on the same tab brought the
  // window to the front, and the field had no pattern and no default action (the pointer was its only way). A host is
  // the window the click is bound to and the content windows of its process family the adapter hands over.
  // fable/cu-v3-worker-sin-nombres: the surface's window classes are data (render_surface_classes.v1.json, read by
  // UiaWorkerHost and handed over in its first «ping»); until they arrive no window is a render surface.
  public static string[] RenderClasses = new string[0];
  public static bool IsRenderClass(string cls) {
    string[] known=RenderClasses;
    if(known==null || string.IsNullOrEmpty(cls)) return false;
    foreach(string name in known) if(string.Equals(cls,name,StringComparison.Ordinal)) return true;
    return false;
  }
  // The render surface of one of the hosts holding the screen point (the smallest when several do), or zero. With a
  // process named (an accessible element's), only a surface of that process: a frame's own caption button lying over
  // its content window's rectangle is never pressed through the content.
  public static IntPtr RenderAt(IntPtr[] hosts, int x, int y, uint process) {
    IntPtr best=IntPtr.Zero; long bestArea=long.MaxValue;
    if(hosts==null) return best;
    foreach(IntPtr host in hosts){
      if(host==IntPtr.Zero || !IsWindow(host)) continue;
      EnumChildWindows(host,(child,unused)=>{
        var cls=new StringBuilder(64); GetClassName(child,cls,cls.Capacity);
        if(!IsRenderClass(cls.ToString()) || !IsWindowVisible(child)) return true;
        uint owner; GetWindowThreadProcessId(child,out owner);
        if(process!=0 && owner!=process) return true;
        RECT r; if(!GetWindowRect(child,out r)) return true;
        if(x<r.Left || x>=r.Right || y<r.Top || y>=r.Bottom) return true;
        long area=(long)(r.Right-r.Left)*(r.Bottom-r.Top);
        if(area>0 && area<bestArea){ best=child; bestArea=area; }
        return true;
      },IntPtr.Zero);
    }
    return best;
  }
  // Whether any host shows a render surface at all (the planner's fact «render»).
  public static bool HostsRender(IntPtr[] hosts, uint process) {
    if(hosts==null) return false;
    foreach(IntPtr host in hosts){
      if(host==IntPtr.Zero || !IsWindow(host)) continue;
      bool found=false;
      EnumChildWindows(host,(child,unused)=>{
        var cls=new StringBuilder(64); GetClassName(child,cls,cls.Capacity);
        uint owner; GetWindowThreadProcessId(child,out owner);
        if(IsRenderClass(cls.ToString()) && IsWindowVisible(child) && (process==0 || owner==process)){ found=true; return false; }
        return true;
      },IntPtr.Zero);
      if(found) return true;
    }
    return false;
  }
  // Whether the surface counts in the screen's own pixels (its DPI is its monitor's): a posted point is never rescaled.
  public static bool SameDpi(IntPtr target) {
    uint monitorX; uint monitorY;
    return target!=IntPtr.Zero
      && GetDpiForMonitor(MonitorFromWindow(target,2),0,out monitorX,out monitorY)==0 && GetDpiForWindow(target)==monitorX;
  }
  // Review of fable/cu-v3-clic-chromium (finding 1): what the page itself has at the screen point, read before anything
  // is posted there. The surface's own accessible object answers accHitTest from the page, whatever the window's Z
  // order (a window behind is never hit-tested through the person's): the first call starts the page's own hit test
  // (its layers: a fixed header, a banner, a modal) and answers from the tree's boxes; the second, HitSettleMs later,
  // answers with the page's result when it holds the point. A pop-up of its own (a select's list, an autofill, a menu)
  // is another window: the page under it answers. The chain goes from the node hit up to the document (role 15) or the
  // window (9, 10), at most HitDepth nodes: name, box and role of each. Empty when nothing answers (and then nothing is
  // posted). Measured live behind the person's window (read only): the first call answered a WebView2 client's document
  // and the second, 80 ms later, its «Chats» button; a browser's page answered its link the same way; each node read
  // costs a few cross-process calls (a chain of 19 took 430 ms on an Electron client), so the chain stops at HitDepth.
  public class RenderHit { public string Name = ""; public int Left; public int Top; public int Width; public int Height; public int Role; }
  public static int HitSettleMs = 80;
  public static int HitDepth = 10;
  public static RenderHit[] HitChain(IntPtr surface, int x, int y) {
    var chain=new List<RenderHit>();
    if(surface==IntPtr.Zero) return chain.ToArray();
    try {
      Guid iid=new Guid("618736e0-3c3d-11cf-810c-00aa00389b71");
      object raw; if(AccessibleObjectFromWindow(surface,0xFFFFFFFC,ref iid,out raw)!=0 || raw==null) return chain.ToArray();
      Accessibility.IAccessible root=raw as Accessibility.IAccessible; if(root==null) return chain.ToArray();
      object hit=root.accHitTest(x,y);
      if(HitSettleMs>0){ System.Threading.Thread.Sleep(HitSettleMs); hit=root.accHitTest(x,y); }
      Accessibility.IAccessible node=hit as Accessibility.IAccessible;
      if(node==null){ if(hit is int && (int)hit==0) node=root; else return chain.ToArray(); }
      for(int depth=0;node!=null && depth<HitDepth;depth++){
        var entry=new RenderHit();
        try { entry.Name=node.get_accName(0) ?? ""; } catch { entry.Name=""; }
        try { int l; int t; int w; int h; node.accLocation(out l,out t,out w,out h,0); entry.Left=l; entry.Top=t; entry.Width=w; entry.Height=h; } catch {}
        try { object role=node.get_accRole(0); if(role is int) entry.Role=(int)role; } catch {}
        chain.Add(entry);
        if(entry.Role==15 || entry.Role==9 || entry.Role==10) break;
        object parent=null; try { parent=node.accParent; } catch { parent=null; }
        node=parent as Accessibility.IAccessible;
      }
    } catch (Exception) { }
    return chain.ToArray();
  }
  // A press posted to a render surface at the screen point: move, down, up in its client coordinates.
  public static bool PostAt(IntPtr target, int x, int y) {
    return target!=IntPtr.Zero && PostPress(target,x,y,false);
  }
  public static bool PostDoubleAt(IntPtr target, int x, int y) {
    return target!=IntPtr.Zero && PostPress(target,x,y,true);
  }
  // LegacyIAccessible's default action (the managed client has no such pattern): the element is found again through
  // the COM client by its RuntimeId under the window and its default action is done. In a web view that is a
  // synthetic click inside the page, with no cursor. Answers the action's name, or "" when there is none or it failed.
  private static IBaxyUia _uia;
  // Where the last attempt stopped (create, root, condition, find, pattern, cast, none, action, done, or the exception):
  // the click receipt carries it, so a control that ends needing the pointer says why.
  public static string LegacyStep = "";
  [DllImport("oleacc.dll")] private static extern int AccessibleObjectFromWindow(IntPtr hwnd, uint id, ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object accessible);
  // A control that is its own window answers through its own IAccessible (WM_GETOBJECT), never through the client-side
  // proxies the managed UIA client registers in this process (measured: they show a WinForms button as a Pane whose
  // LegacyIAccessible has no default action, while its window's own object says «Presionar»).
  public static string WindowDefault(IntPtr hwnd) {
    LegacyStep = "window";
    if(hwnd==IntPtr.Zero) return "";
    try {
      Guid iid=new Guid("618736e0-3c3d-11cf-810c-00aa00389b71");
      object raw; if(AccessibleObjectFromWindow(hwnd,0xFFFFFFFC,ref iid,out raw)!=0 || raw==null) return "";
      Accessibility.IAccessible accessible=raw as Accessibility.IAccessible; if(accessible==null) return "";
      LegacyStep = "window-none";
      string action=accessible.get_accDefaultAction(0); if(string.IsNullOrWhiteSpace(action)) return "";
      LegacyStep = "window-action";
      accessible.accDoDefaultAction(0);
      LegacyStep = "window-done";
      return action;
    } catch (Exception failure) { LegacyStep = LegacyStep + ":" + failure.GetType().Name; return ""; }
  }
  // The element under the window found again through the COM client by its RuntimeId, or null; the step it stopped at
  // goes to LegacyStep (create, root, condition, find).
  private static IBaxyUiaElement FindByRuntimeId(IntPtr top, int[] runtimeId) {
    LegacyStep = "create";
    if(_uia==null) _uia=(IBaxyUia)Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("ff48dba4-60ef-4201-aa87-54103eef594e")));
    LegacyStep = "root";
    IBaxyUiaElement root; if(_uia.ElementFromHandle(top,out root)!=0 || root==null) return null;
    LegacyStep = "condition";
    IBaxyUiaCondition condition; if(_uia.CreatePropertyCondition(30000,runtimeId,out condition)!=0 || condition==null) return null;
    LegacyStep = "find";
    IBaxyUiaElement found; if(root.FindFirst(7,condition,out found)!=0 || found==null) return null;
    return found;
  }
  // Goal v3 B3: the element's own context menu (IUIAutomationElement3::ShowContextMenu, Windows 8.1 and later): the
  // application shows the menu a right click or Shift+F10 would, with neither the cursor nor the keyboard. The managed
  // client has no such call; its slot is read from the interface table: IUnknown (3), IUIAutomationElement (82) and
  // IUIAutomationElement2 (6) come before it, so it is slot 91. Answers whether the element accepted it.
  [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int ElementCall(IntPtr self);
  private const int ShowContextMenuSlot = 91;
  public static bool ShowContextMenu(IntPtr top, int[] runtimeId) {
    LegacyStep = "argument";
    if(top==IntPtr.Zero || runtimeId==null || runtimeId.Length==0) return false;
    IntPtr unknown=IntPtr.Zero; IntPtr third=IntPtr.Zero;
    try {
      IBaxyUiaElement found=FindByRuntimeId(top,runtimeId); if(found==null) return false;
      LegacyStep = "interface";
      unknown=Marshal.GetIUnknownForObject(found);
      Guid iid=new Guid("8471df34-aee0-4a01-a7de-7db9af12c296");
      if(Marshal.QueryInterface(unknown,ref iid,out third)!=0 || third==IntPtr.Zero) return false;
      ElementCall show=(ElementCall)Marshal.GetDelegateForFunctionPointer(
        Marshal.ReadIntPtr(Marshal.ReadIntPtr(third),ShowContextMenuSlot*IntPtr.Size),typeof(ElementCall));
      LegacyStep = "menu";
      int answer=show(third);
      LegacyStep = answer==0 ? "menu-done" : "menu-refused";
      return answer==0;
    } catch (Exception failure) { LegacyStep = LegacyStep + ":" + failure.GetType().Name; return false; }
    finally {
      if(third!=IntPtr.Zero) Marshal.Release(third);
      if(unknown!=IntPtr.Zero) Marshal.Release(unknown);
    }
  }
  public static string LegacyDefault(IntPtr top, int[] runtimeId) {
    LegacyStep = "argument";
    if(top==IntPtr.Zero || runtimeId==null || runtimeId.Length==0) return "";
    try {
      IBaxyUiaElement found=FindByRuntimeId(top,runtimeId); if(found==null) return "";
      LegacyStep = "pattern";
      object raw; if(found.GetCurrentPattern(10018,out raw)!=0 || raw==null) return "";
      LegacyStep = "cast";
      IBaxyUiaLegacy legacy=raw as IBaxyUiaLegacy; if(legacy==null) return "";
      LegacyStep = "none";
      string action; if(legacy.GetDefaultAction(out action)!=0 || string.IsNullOrWhiteSpace(action)) return "";
      LegacyStep = "action";
      if(legacy.DoDefaultAction()!=0) return "";
      LegacyStep = "done";
      return action;
    } catch (Exception failure) { LegacyStep = LegacyStep + ":" + failure.GetType().Name; return ""; }
  }
}
// The few slots of the UI Automation COM client that LegacyDefault calls; the others only hold their place.
[ComImport, Guid("352ffba8-0973-437c-a61f-f64cafd81df9"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IBaxyUiaCondition {}
[ComImport, Guid("30cbe57d-d9d0-452a-ab13-7ac5ac4825ee"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IBaxyUia {
  void CompareElements(); void CompareRuntimeIds(); void GetRootElement();
  [PreserveSig] int ElementFromHandle(IntPtr hwnd, out IBaxyUiaElement element);
  void ElementFromPoint(); void GetFocusedElement(); void GetRootElementBuildCache(); void ElementFromHandleBuildCache();
  void ElementFromPointBuildCache(); void GetFocusedElementBuildCache(); void CreateTreeWalker(); void ControlViewWalker();
  void ContentViewWalker(); void RawViewWalker(); void RawViewCondition(); void ControlViewCondition(); void ContentViewCondition();
  void CreateCacheRequest(); void CreateTrueCondition(); void CreateFalseCondition();
  [PreserveSig] int CreatePropertyCondition(int propertyId, [MarshalAs(UnmanagedType.Struct)] object value, out IBaxyUiaCondition condition);
}
[ComImport, Guid("d22108aa-8ac5-49a5-837b-37bbb3d7591e"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IBaxyUiaElement {
  void SetFocus(); void GetRuntimeId();
  [PreserveSig] int FindFirst(int scope, IBaxyUiaCondition condition, out IBaxyUiaElement found);
  void FindAll(); void FindFirstBuildCache(); void FindAllBuildCache(); void BuildUpdatedCache(); void GetCurrentPropertyValue();
  void GetCurrentPropertyValueEx(); void GetCachedPropertyValue(); void GetCachedPropertyValueEx(); void GetCurrentPatternAs();
  void GetCachedPatternAs();
  [PreserveSig] int GetCurrentPattern(int patternId, [MarshalAs(UnmanagedType.IUnknown)] out object pattern);
}
[ComImport, Guid("828055ad-355b-4435-86d5-3b51c14a9b1b"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IBaxyUiaLegacy {
  void Select(); [PreserveSig] int DoDefaultAction(); void SetValue(); void ChildId(); void Name(); void Value(); void Description();
  void Role(); void State(); void Help(); void KeyboardShortcut(); void GetCurrentSelection();
  [PreserveSig] int GetDefaultAction([MarshalAs(UnmanagedType.BStr)] out string action);
}
'@
# Recibo del clic por estado (r15b v3-51): Invoke on a button whose application runs a modal loop (a Qt dialog opened by
# the press) does not return until the dialog closes; the worker then answered nothing for 15 s and the adapter gave
# «visible_click_no_receipt» while the dialog was open. The press runs on a pool thread and is waited for briefly: if it
# has not returned, the press is pending and «blocked», and the worker keeps answering the postreads.
Add-Type -ReferencedAssemblies UIAutomationClient,UIAutomationTypes,WindowsBase -TypeDefinition @'
using System;
using System.Windows.Automation;
public static class BaxyUiaTimedPress {
  public static bool InvokeWithin(AutomationElement element, int milliseconds) {
    InvokePattern pattern = (InvokePattern)element.GetCurrentPattern(InvokePattern.Pattern);
    System.Threading.Tasks.Task press = System.Threading.Tasks.Task.Run(() => pattern.Invoke());
    try { return press.Wait(milliseconds); }
    catch (AggregateException failed) { throw failed.InnerException; }
  }
}
'@
# BEGIN BaxyUiaQuietInput
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
// Goal v3 punto 0 (r4a M1): before a pattern method (Invoke, Select, Toggle, SetValue, SetFocus...) UIAutomationCore
// asks Windows for the foreground permission and hands it to the application, so a window behind comes to the front by
// itself. When the person has just typed the permission is locked, and the client wins it by injecting an unmarked key
// (VK 0xB9) that lands in the person's window. This class takes SendInput and RegisterHotKey out of the client's import
// table in this process: its input is dropped (nothing reaches the screen, so no permission is won and the application
// stays behind) and the wait that followed it is answered with the message it was waiting for: its MsgWait returns
// and its GetMessage/PeekMessage reads the WM_HOTKEY, without the message ever entering the thread's queue (measured: a
// posted WM_HOTKEY behind an older message was read late and the client waited its full 2 s). Only the client's own
// import slots are replaced; the worker's own input never passes through UIAutomationCore.
public static class BaxyUiaQuietInput {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] private static extern IntPtr GetModuleHandle(string name);
  [DllImport("kernel32.dll", CharSet=CharSet.Ansi)] private static extern IntPtr GetProcAddress(IntPtr module, string name);
  [DllImport("kernel32.dll")] private static extern bool VirtualProtect(IntPtr address, UIntPtr size, uint protect, out uint old);
  [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
  [DllImport("kernel32.dll")] private static extern uint GetTickCount();
  [UnmanagedFunctionPointer(CallingConvention.Winapi)] public delegate uint SendInputCall(uint count, IntPtr inputs, int size);
  [UnmanagedFunctionPointer(CallingConvention.Winapi)] public delegate bool RegisterHotKeyCall(IntPtr hwnd, int id, uint modifiers, uint key);
  [UnmanagedFunctionPointer(CallingConvention.Winapi)] public delegate bool UnregisterHotKeyCall(IntPtr hwnd, int id);
  [UnmanagedFunctionPointer(CallingConvention.Winapi)] public delegate uint MsgWaitCall(uint count, IntPtr handles, bool all, uint milliseconds, uint mask);
  [UnmanagedFunctionPointer(CallingConvention.Winapi)] public delegate int GetMessageCall(IntPtr msg, IntPtr hwnd, uint first, uint last);
  [UnmanagedFunctionPointer(CallingConvention.Winapi)] public delegate bool PeekMessageCall(IntPtr msg, IntPtr hwnd, uint first, uint last, uint remove);
  private struct Hot { public IntPtr Hwnd; public int Id; public uint Modifiers; public uint Key; public uint Thread; }
  private static readonly object Gate = new object();
  private static readonly List<Hot> Hots = new List<Hot>();
  private static readonly List<KeyValuePair<IntPtr, IntPtr>> Saved = new List<KeyValuePair<IntPtr, IntPtr>>();
  private static SendInputCall _send;
  private static RegisterHotKeyCall _register;
  private static UnregisterHotKeyCall _unregister;
  private static RegisterHotKeyCall _realRegister;
  private static UnregisterHotKeyCall _realUnregister;
  private static MsgWaitCall _wait;
  private static GetMessageCall _get;
  private static PeekMessageCall _peek;
  private static MsgWaitCall _realWait;
  private static GetMessageCall _realGet;
  private static PeekMessageCall _realPeek;
  // The hotkey message owed to each thread whose key was dropped: answered by the client's own wait and read.
  private static readonly Dictionary<uint, Hot> Owed = new Dictionary<uint, Hot>();
  public static int Dropped;
  // Calls refused whole: input that is not the client's hotkey key (never sent, answered 0).
  public static int Refused;
  public static int Answered;
  public static string State = "off";

  // The import slots of «function» in a loaded 64-bit module: the ordinary table and the delay-loaded one.
  public static IntPtr[] FindSlots(IntPtr module, string function) {
    var slots = new List<IntPtr>();
    if (module == IntPtr.Zero || IntPtr.Size != 8) return slots.ToArray();
    long b = module.ToInt64();
    int pe = Marshal.ReadInt32(new IntPtr(b + 0x3C));
    if (Marshal.ReadInt16(new IntPtr(b + pe + 24)) != 0x20B) return slots.ToArray();
    long directories = b + pe + 24 + 112;
    for (int pass = 0; pass < 2; pass++) {
      bool delay = pass == 1;
      int rva = Marshal.ReadInt32(new IntPtr(directories + (delay ? 13 : 1) * 8));
      if (rva == 0) continue;
      for (long d = b + rva; ; d += delay ? 32 : 20) {
        int nameRva = Marshal.ReadInt32(new IntPtr(d + (delay ? 4 : 12)));
        if (nameRva == 0) break;
        int iat = Marshal.ReadInt32(new IntPtr(d + (delay ? 12 : 16)));
        int names = Marshal.ReadInt32(new IntPtr(d + (delay ? 16 : 0)));
        if (names == 0) names = iat;
        for (int i = 0; ; i++) {
          long thunk = Marshal.ReadInt64(new IntPtr(b + names + i * 8L));
          if (thunk == 0) break;
          if (thunk < 0) continue;
          string name = Marshal.PtrToStringAnsi(new IntPtr(b + (thunk & 0x7FFFFFFF) + 2));
          if (string.Equals(name, function, StringComparison.Ordinal)) slots.Add(new IntPtr(b + iat + i * 8L));
        }
      }
    }
    return slots.ToArray();
  }

  public static IntPtr Read(IntPtr slot) { return Marshal.ReadIntPtr(slot); }

  public static bool Write(IntPtr slot, IntPtr value) {
    uint old;
    if (!VirtualProtect(slot, new UIntPtr(8), 0x04, out old)) return false;
    Marshal.WriteIntPtr(slot, value);
    uint unused;
    VirtualProtect(slot, new UIntPtr(8), old, out unused);
    return true;
  }

  private static int Replace(IntPtr module, string function, IntPtr value) {
    int done = 0;
    foreach (IntPtr slot in FindSlots(module, function)) {
      IntPtr before = Read(slot);
      if (Write(slot, value)) { lock (Gate) Saved.Add(new KeyValuePair<IntPtr, IntPtr>(slot, before)); done++; }
    }
    return done;
  }

  // «on» once the client's SendInput is taken; otherwise why not (absent: the client is not loaded yet).
  public static string Install(string module) {
    lock (Gate) { if (State == "on") return State; }
    IntPtr core = GetModuleHandle(module);
    if (core == IntPtr.Zero) { State = "absent"; return State; }
    if (IntPtr.Size != 8) { State = "x86"; return State; }
    IntPtr user = GetModuleHandle("user32.dll");
    IntPtr register = GetProcAddress(user, "RegisterHotKey");
    IntPtr unregister = GetProcAddress(user, "UnregisterHotKey");
    IntPtr wait = GetProcAddress(user, "MsgWaitForMultipleObjects");
    IntPtr get = GetProcAddress(user, "GetMessageW");
    IntPtr peek = GetProcAddress(user, "PeekMessageW");
    if (register == IntPtr.Zero || unregister == IntPtr.Zero || wait == IntPtr.Zero || get == IntPtr.Zero || peek == IntPtr.Zero) { State = "user32"; return State; }
    _realWait = (MsgWaitCall)Marshal.GetDelegateForFunctionPointer(wait, typeof(MsgWaitCall));
    _realGet = (GetMessageCall)Marshal.GetDelegateForFunctionPointer(get, typeof(GetMessageCall));
    _realPeek = (PeekMessageCall)Marshal.GetDelegateForFunctionPointer(peek, typeof(PeekMessageCall));
    _realRegister = (RegisterHotKeyCall)Marshal.GetDelegateForFunctionPointer(register, typeof(RegisterHotKeyCall));
    _realUnregister = (UnregisterHotKeyCall)Marshal.GetDelegateForFunctionPointer(unregister, typeof(UnregisterHotKeyCall));
    _send = new SendInputCall(QuietSend);
    _register = new RegisterHotKeyCall(TrackRegister);
    _unregister = new UnregisterHotKeyCall(TrackUnregister);
    _wait = new MsgWaitCall(AnsweredWait);
    _get = new GetMessageCall(AnsweredGet);
    _peek = new PeekMessageCall(AnsweredPeek);
    Replace(core, "MsgWaitForMultipleObjects", Marshal.GetFunctionPointerForDelegate(_wait));
    Replace(core, "GetMessageW", Marshal.GetFunctionPointerForDelegate(_get));
    Replace(core, "PeekMessageW", Marshal.GetFunctionPointerForDelegate(_peek));
    Replace(core, "RegisterHotKey", Marshal.GetFunctionPointerForDelegate(_register));
    Replace(core, "UnregisterHotKey", Marshal.GetFunctionPointerForDelegate(_unregister));
    int taken = Replace(core, "SendInput", Marshal.GetFunctionPointerForDelegate(_send));
    State = taken > 0 ? "on" : "no_slot";
    return State;
  }

  // Every slot back to what it held before Install.
  public static void Restore() {
    lock (Gate) {
      for (int i = Saved.Count - 1; i >= 0; i--) Write(Saved[i].Key, Saved[i].Value);
      Saved.Clear();
      Hots.Clear();
      Owed.Clear();
      State = "off";
    }
  }

  private static bool TrackRegister(IntPtr hwnd, int id, uint modifiers, uint key) {
    bool done = _realRegister(hwnd, id, modifiers, key);
    if (done) {
      Hot hot = new Hot(); hot.Hwnd = hwnd; hot.Id = id; hot.Modifiers = modifiers; hot.Key = key; hot.Thread = GetCurrentThreadId();
      lock (Gate) Hots.Add(hot);
    }
    return done;
  }

  private static bool TrackUnregister(IntPtr hwnd, int id) {
    lock (Gate) {
      Hots.RemoveAll(delegate(Hot hot) { return hot.Hwnd == hwnd && hot.Id == id; });
      uint thread = GetCurrentThreadId();
      Hot owed;
      if (Owed.TryGetValue(thread, out owed) && owed.Hwnd == hwnd && owed.Id == id) Owed.Remove(thread);
    }
    return _realUnregister(hwnd, id);
  }

  // INPUT on x64: type (4), padding (4), then KEYBDINPUT: wVk (2), wScan (2), dwFlags (4), time (4), dwExtraInfo (8).
  // Only what was measured is dropped: keys whose virtual key is a hotkey this same thread registered (the client's
  // bid for the foreground permission). Anything else (a mouse event, any other key) is not sent either, and the call
  // answers 0, a failure the caller sees: a pattern that needed simulated input never reports a press that did not
  // happen. Nothing of a refused call is sent, so no input of the client reaches the screen.
  public static bool IsOwnHotkey(uint type, uint key, uint[] registered) {
    if (type != 1 || registered == null) return false;
    foreach (uint hot in registered) if (hot == key) return true;
    return false;
  }

  private static uint QuietSend(uint count, IntPtr inputs, int size) {
    if (inputs == IntPtr.Zero || size <= 0 || count == 0) { Interlocked.Increment(ref Refused); return 0; }
    uint thread = GetCurrentThreadId();
    uint[] registered;
    lock (Gate) {
      var keys = new List<uint>();
      foreach (Hot hot in Hots) if (hot.Thread == thread) keys.Add(hot.Key);
      registered = keys.ToArray();
    }
    for (uint i = 0; i < count; i++) {
      long item = inputs.ToInt64() + i * (long)size;
      uint type = (uint)Marshal.ReadInt32(new IntPtr(item));
      uint key = type == 1 ? (uint)(ushort)Marshal.ReadInt16(new IntPtr(item + 8)) : 0;
      if (!IsOwnHotkey(type, key, registered)) { Interlocked.Increment(ref Refused); return 0; }
    }
    for (uint i = 0; i < count; i++) {
      long item = inputs.ToInt64() + i * (long)size;
      uint key = (ushort)Marshal.ReadInt16(new IntPtr(item + 8));
      uint flags = (uint)Marshal.ReadInt32(new IntPtr(item + 12));
      Interlocked.Increment(ref Dropped);
      if ((flags & 0x0002) != 0) continue;
      lock (Gate) {
        foreach (Hot hot in Hots) {
          if (hot.Key == key && hot.Thread == thread) { Owed[thread] = hot; break; }
        }
      }
    }
    return count;
  }

  private static bool TakeOwed(bool remove, IntPtr hwndFilter, uint first, uint last, out Hot hot) {
    hot = new Hot();
    if (first != 0 || last != 0) { if (first > 0x0312 || last < 0x0312) return false; }
    uint thread = GetCurrentThreadId();
    lock (Gate) {
      if (!Owed.TryGetValue(thread, out hot)) return false;
      if (hwndFilter != IntPtr.Zero && hwndFilter != hot.Hwnd) return false;
      if (remove) Owed.Remove(thread);
    }
    return true;
  }

  private static void Fill(IntPtr msg, Hot hot) {
    // MSG on x64: hwnd (8), message (4) + padding, wParam (8), lParam (8), time (4), pt (8), lPrivate (4).
    for (int i = 0; i < 48; i++) Marshal.WriteByte(msg, i, 0);
    Marshal.WriteIntPtr(msg, 0, hot.Hwnd);
    Marshal.WriteInt32(msg, 8, 0x0312);
    Marshal.WriteIntPtr(msg, 16, new IntPtr(hot.Id));
    Marshal.WriteIntPtr(msg, 24, new IntPtr((long)((hot.Key & 0xFFFF) << 16) | (hot.Modifiers & 0xFFFF)));
    Marshal.WriteInt32(msg, 32, (int)GetTickCount());
  }

  // The client waits for its hotkey after the key: with the message owed, the wait ends at once («input available»).
  private static uint AnsweredWait(uint count, IntPtr handles, bool all, uint milliseconds, uint mask) {
    Hot hot;
    if ((mask & 0x0080) != 0 && TakeOwed(false, IntPtr.Zero, 0, 0, out hot)) return count;
    return _realWait(count, handles, all, milliseconds, mask);
  }

  // ...and reads it: the hotkey message it waited for, never placed in the thread's queue.
  private static int AnsweredGet(IntPtr msg, IntPtr hwnd, uint first, uint last) {
    Hot hot;
    if (msg != IntPtr.Zero && TakeOwed(true, hwnd, first, last, out hot)) { Fill(msg, hot); Interlocked.Increment(ref Answered); return 1; }
    return _realGet(msg, hwnd, first, last);
  }

  private static bool AnsweredPeek(IntPtr msg, IntPtr hwnd, uint first, uint last, uint remove) {
    Hot hot;
    if (msg != IntPtr.Zero && TakeOwed((remove & 0x0001) != 0, hwnd, first, last, out hot)) {
      Fill(msg, hot);
      if ((remove & 0x0001) != 0) Interlocked.Increment(ref Answered);
      return true;
    }
    return _realPeek(msg, hwnd, first, last, remove);
  }
}
// The net under the patterns (r4a M1, fix c): without the key the client still hands the permission over while the
// person is not typing, and the application it acts on comes to the front by itself. While a command acts, and for a
// short tail after a pattern that acted, a change of the foreground to the target's family (its window, its process,
// the processes of its child windows, a window it owns) is given back to the window that was in front (when Windows
// refuses, the watch's thread first wins the right with a marked press of its own hotkey, see Bid), and only once
// the front is really back there the target is placed just below it without activation: a return that failed leaves
// the order alone, so the window the keyboard goes to is never drawn under another one. A change the person made (a
// click, a key that moves the front: Tab, Enter, Esc, Alt, Win, a function key; told by Raw Input, BAXY's own marked
// input left out) is theirs and is never fought. Nothing is watched when the target was already in front or nothing
// was. Each watch keeps its own report (taken, returned, failed, longest return), read by the command that ran under it.
public static class BaxyFrontKeeper {
  private delegate void WinEventProc(IntPtr hook, uint eventType, IntPtr hwnd, int objectId, int childId, uint thread, uint time);
  private delegate bool EnumProc(IntPtr hwnd, IntPtr lParam);
  [DllImport("user32.dll")] private static extern IntPtr SetWinEventHook(uint min, uint max, IntPtr module, WinEventProc proc, uint process, uint thread, uint flags);
  [DllImport("user32.dll")] private static extern bool GetMessage(out Msg msg, IntPtr hwnd, uint min, uint max);
  [DllImport("user32.dll")] private static extern bool PeekMessage(out Msg msg, IntPtr hwnd, uint min, uint max, uint remove);
  [DllImport("user32.dll")] private static extern IntPtr DispatchMessage(ref Msg msg);
  [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] private static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
  [DllImport("user32.dll")] private static extern IntPtr GetWindow(IntPtr hwnd, uint command);
  [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint process);
  [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr lParam);
  [DllImport("user32.dll")] private static extern bool AttachThreadInput(uint attach, uint to, bool doAttach);
  [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr hwnd);
  [DllImport("user32.dll")] private static extern bool RegisterHotKey(IntPtr hwnd, int id, uint modifiers, uint key);
  [DllImport("user32.dll")] private static extern uint SendInput(uint count, BidInput[] inputs, int size);
  [DllImport("user32.dll")] private static extern uint MsgWaitForMultipleObjects(uint count, IntPtr handles, bool all, uint milliseconds, uint mask);
  [DllImport("user32.dll")] private static extern bool SetWindowPos(IntPtr hwnd, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] private static extern bool IsWindow(IntPtr hwnd);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern IntPtr CreateWindowEx(uint exStyle, string className, string name, uint style, int x, int y, int w, int h, IntPtr parent, IntPtr menu, IntPtr instance, IntPtr param);
  [DllImport("user32.dll")] private static extern bool RegisterRawInputDevices(RawDevice[] devices, uint count, uint size);
  [DllImport("user32.dll")] private static extern uint GetRawInputData(IntPtr input, uint command, IntPtr data, ref uint size, uint header);
  [DllImport("user32.dll")] private static extern bool GetLastInputInfo(ref LastInput info);
  [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] private static extern IntPtr OpenFileMapping(uint access, bool inherit, string name);
  [DllImport("kernel32.dll")] private static extern IntPtr MapViewOfFile(IntPtr mapping, uint access, uint high, uint low, UIntPtr bytes);
  [DllImport("kernel32.dll")] private static extern bool UnmapViewOfFile(IntPtr view);
  [DllImport("kernel32.dll")] private static extern bool CloseHandle(IntPtr handle);
  [DllImport("kernel32.dll")] private static extern ulong GetTickCount64();
  [StructLayout(LayoutKind.Sequential)] private struct Msg { public IntPtr Hwnd; public uint Message; public IntPtr WParam; public IntPtr LParam; public uint Time; public int X; public int Y; }
  [StructLayout(LayoutKind.Sequential)] private struct RawDevice { public ushort Page; public ushort Usage; public uint Flags; public IntPtr Target; }
  [StructLayout(LayoutKind.Sequential)] private struct LastInput { public uint Size; public uint Tick; }
  // INPUT on x64 for one key: type at 0, KEYBDINPUT from 8 (wVk, wScan, dwFlags, time, dwExtraInfo at 24), 40 bytes.
  [StructLayout(LayoutKind.Explicit, Size=40)] private struct BidInput { [FieldOffset(0)] public uint Type; [FieldOffset(8)] public ushort Vk; [FieldOffset(10)] public ushort Scan; [FieldOffset(12)] public uint Flags; [FieldOffset(16)] public uint Time; [FieldOffset(24)] public IntPtr Extra; }
  private const uint BaxyMark = 0x42415859;
  private static readonly object Gate = new object();
  private static WinEventProc _proc;
  private static Thread _thread;
  private static IntPtr _sink;
  private static bool _raw;
  private static IntPtr _person;
  private static IntPtr _top;
  private static uint[] _family = new uint[0];
  private static bool _acting;
  private static bool _tail;
  private static bool _released;
  private static int _until;
  private static uint _beganInput;
  private static bool _personActed;
  // The report of the current watch (reset by Begin).
  public static int WatchTaken;
  public static int WatchReturned;
  public static int WatchFailed;
  public static int WatchLongestMs = -1;
  // Since the worker started (the ping).
  public static int Returned;
  public static int Failed;
  public static int Yielded;
  public static int LeaseYielded;
  // Changes to the target's family that came after the watch had ended (up to 5 s after it, not after a Release), and
  // how late the last one came: never fought, only counted.
  public static int Late;
  public static int LateMs = -1;
  // The block where BAXY's foreground lease says which window it is bringing up and when (LeaseFrontSignal.Name).
  public const string LeaseBlock = @"Local\BaxyLeaseFront";
  public static int LeaseFreshMs = 2000;
  public static int LastReturnMs = -1;
  public static int TailMs = 300;
  // The bid for the right to give the front back (the way the UI Automation client wins it): a hotkey of this thread on
  // a virtual key no keyboard has, registered with every modifier combination, and one marked press of it. The system
  // takes the press as the hotkey (it never reaches the window in front) and posts WM_HOTKEY to this thread, which then
  // holds the right to set the foreground.
  public static readonly uint[] BidKeys = { 0x97, 0x98, 0x99, 0x9A, 0x9B, 0x9C, 0x9D, 0x9E, 0x9F, 0x88, 0x89, 0x8A, 0x8B };
  public const int BidId = 0x4258;
  public static uint BidKey;
  public static int Bids;
  public static int BidsAnswered;
  public static int BidBudgetMs = 200;
  private static bool _returning;

  // Whether the person's input is told apart (Raw Input started); without it any input counts as theirs.
  public static bool RawInput { get { return _raw; } }

  // Pure rule: is «foreground» (a root window of process «process», owned by «owner») the target's family taking the
  // person's front? Never when nothing was in front, when the target was already in front, or when the front is the
  // person's own window again.
  public static bool IsTheft(IntPtr person, IntPtr top, uint[] family, IntPtr foreground, uint process, IntPtr owner) {
    if (person == IntPtr.Zero || top == IntPtr.Zero || foreground == IntPtr.Zero) return false;
    if (person == top || foreground == person) return false;
    if (foreground == top || owner == top) return true;
    foreach (uint member in family) if (member != 0 && member == process) return true;
    return false;
  }

  // Pure rule: the target goes just below the person's window only when the front really is theirs again («now» and
  // its root, read after the return). Otherwise the target keeps the keyboard and stays where it is seen.
  public static bool MayLower(IntPtr person, IntPtr now, IntPtr nowRoot) {
    return person != IntPtr.Zero && (now == person || nowRoot == person);
  }

  // Pure rule: one Raw Input event is the person moving the front themselves: a mouse button pressed, or a key pressed
  // that can move it (Tab, Enter, Esc, Alt, the Win keys, a function key). Typing text cannot; BAXY's own input (its
  // mark) is never the person's.
  public static bool IsPersonsMove(bool mouse, ushort buttonFlags, ushort key, ushort keyFlags, uint extra) {
    if (extra == BaxyMark) return false;
    if (mouse) return (buttonFlags & 0x0155) != 0;
    if ((keyFlags & 0x0001) != 0) return false;
    if (key == 0x09 || key == 0x0D || key == 0x1B || key == 0x12 || key == 0xA4 || key == 0xA5 || key == 0x5B || key == 0x5C) return true;
    return key >= 0x70 && key <= 0x87;
  }

  // Pure rule: the front is the one BAXY's own lease is bringing up («leased», said «age» ms ago): the leased window
  // itself, its root or the target, said recently. Never with no window said, or said long ago.
  public static bool IsLeaseFront(IntPtr leased, long age, IntPtr leasedRoot, IntPtr foreground, IntPtr top) {
    if (leased == IntPtr.Zero || age < 0 || age > LeaseFreshMs) return false;
    return leased == foreground || leasedRoot == foreground || leased == top;
  }

  private static bool LeaseHolds(IntPtr foreground, IntPtr top) {
    IntPtr mapping = OpenFileMapping(0x0004, false, LeaseBlock);
    if (mapping == IntPtr.Zero) return false;
    try {
      IntPtr view = MapViewOfFile(mapping, 0x0004, 0, 0, new UIntPtr(16));
      if (view == IntPtr.Zero) return false;
      try {
        IntPtr leased = new IntPtr(Marshal.ReadInt64(view, 0));
        long age = (long)GetTickCount64() - Marshal.ReadInt64(view, 8);
        IntPtr leasedRoot = leased == IntPtr.Zero ? IntPtr.Zero : GetAncestor(leased, 2);
        return IsLeaseFront(leased, age, leasedRoot, foreground, top);
      } finally { UnmapViewOfFile(view); }
    } finally { CloseHandle(mapping); }
  }

  private static uint ProcessOf(IntPtr hwnd) { uint process; GetWindowThreadProcessId(hwnd, out process); return process; }

  private static uint[] FamilyOf(IntPtr top) {
    var family = new List<uint>();
    family.Add(ProcessOf(top));
    EnumChildWindows(top, delegate(IntPtr child, IntPtr unused) {
      uint process = ProcessOf(child);
      if (!family.Contains(process)) family.Add(process);
      return family.Count < 16;
    }, IntPtr.Zero);
    return family.ToArray();
  }

  private static uint LastInputTick() { LastInput info = new LastInput(); info.Size = 8; GetLastInputInfo(ref info); return info.Tick; }

  // RAWINPUTHEADER on x64 is 24 bytes; RAWMOUSE: usButtonFlags at 4, ulExtraInformation at 20; RAWKEYBOARD: Flags at
  // 2, VKey at 6, ExtraInformation at 12. Only whether it moved the front is kept, never the key or the position.
  private static void Record(IntPtr input) {
    // Outside a watch nothing is read (the mouse's moves arrive all the time).
    lock (Gate) { if (!_acting && !_tail) return; }
    uint size = 0;
    if (GetRawInputData(input, 0x10000003, IntPtr.Zero, ref size, 24) != 0 || size < 24 || size > 512) return;
    IntPtr data = Marshal.AllocHGlobal((int)size);
    try {
      if (GetRawInputData(input, 0x10000003, data, ref size, 24) != size) return;
      int type = Marshal.ReadInt32(data);
      bool moved;
      if (type == 0 && size >= 48) moved = IsPersonsMove(true, (ushort)Marshal.ReadInt16(data, 28), 0, 0, (uint)Marshal.ReadInt32(data, 44));
      else if (type == 1 && size >= 40) moved = IsPersonsMove(false, 0, (ushort)Marshal.ReadInt16(data, 30), (ushort)Marshal.ReadInt16(data, 26), (uint)Marshal.ReadInt32(data, 36));
      else return;
      if (moved) lock (Gate) { if (_acting || _tail) _personActed = true; }
    } finally { Marshal.FreeHGlobal(data); }
  }

  // The input already queued for the sink, read before a front change is judged (its event can arrive first).
  private static void Drain() {
    if (_sink == IntPtr.Zero) return;
    Msg msg;
    while (PeekMessage(out msg, _sink, 0x00FF, 0x00FF, 0x0001)) { Record(msg.LParam); DispatchMessage(ref msg); }
  }

  private static void Start() {
    if (_thread != null) return;
    var ready = new ManualResetEvent(false);
    _thread = new Thread(delegate() {
      _proc = new WinEventProc(OnForeground);
      SetWinEventHook(0x0003, 0x0003, IntPtr.Zero, _proc, 0, 0, 0x0002);
      // A message-only window of the system's STATIC class takes the keyboard's and the mouse's Raw Input while other
      // windows are in front (RIDEV_INPUTSINK): passive, nothing sits in the input path.
      _sink = CreateWindowEx(0, "STATIC", "", 0, 0, 0, 0, 0, new IntPtr(-3), IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);
      if (_sink != IntPtr.Zero) {
        RawDevice[] devices = new RawDevice[2];
        devices[0].Page = 1; devices[0].Usage = 6; devices[0].Flags = 0x100; devices[0].Target = _sink;
        devices[1].Page = 1; devices[1].Usage = 2; devices[1].Flags = 0x100; devices[1].Target = _sink;
        _raw = RegisterRawInputDevices(devices, 2, (uint)Marshal.SizeOf(typeof(RawDevice)));
      }
      RegisterBid();
      ready.Set();
      Msg msg;
      while (GetMessage(out msg, IntPtr.Zero, 0, 0)) {
        if (msg.Message == 0x00FF) Record(msg.LParam);
        DispatchMessage(ref msg);
      }
    });
    _thread.IsBackground = true;
    _thread.SetApartmentState(ApartmentState.STA);
    _thread.Start();
    ready.WaitOne(2000);
  }

  // The first key of BidKeys this thread can take as a hotkey with no modifier (another process may hold one), then the
  // same key with each combination of Alt, Ctrl, Shift and Win, so a modifier the person holds never lets the press
  // through to their window. Registered once, on the watch's thread, for the worker's life.
  private static void RegisterBid() {
    foreach (uint key in BidKeys) {
      if (!RegisterHotKey(IntPtr.Zero, BidId, 0, key)) continue;
      for (uint modifiers = 1; modifiers < 16; modifiers++) RegisterHotKey(IntPtr.Zero, BidId + (int)modifiers, modifiers, key);
      BidKey = key;
      return;
    }
  }

  private static bool SendBid(bool release) {
    BidInput[] keys = new BidInput[1];
    keys[0].Type = 1; keys[0].Vk = (ushort)BidKey; keys[0].Flags = release ? 0x0002u : 0u; keys[0].Extra = new IntPtr(0x42415859); // BaxyMark: the census reads the mark at the call site
    return SendInput(1, keys, Marshal.SizeOf(typeof(BidInput))) == 1;
  }

  // One marked press of the bid key and the wait for its WM_HOTKEY (a thread message, read with hwnd -1 so nothing
  // else of the queue is touched): true once it arrived, within «budget» ms.
  private static bool Bid(int budget) {
    if (BidKey == 0) return false;
    Interlocked.Increment(ref Bids);
    Msg msg;
    while (PeekMessage(out msg, new IntPtr(-1), 0x0312, 0x0312, 0x0001)) { }
    // The press and its release at once, as the client does: measured live, the system takes both (neither the window
    // in front nor the person's window gets a keyboard message) and the WM_HOTKEY arrives in a few milliseconds.
    if (!SendBid(false)) return false;
    SendBid(true);
    int started = Environment.TickCount;
    while (true) {
      while (PeekMessage(out msg, new IntPtr(-1), 0x0312, 0x0312, 0x0001)) {
        long id = msg.WParam.ToInt64();
        if (id >= BidId && id < BidId + 16) { Interlocked.Increment(ref BidsAnswered); return true; }
      }
      int left = budget - (Environment.TickCount - started);
      if (left <= 0) return false;
      MsgWaitForMultipleObjects(0, IntPtr.Zero, false, (uint)left, 0x0080);
    }
  }

  // Before a command that may act on «top»: the window in front now is the person's.
  public static void Begin(IntPtr top) {
    Start();
    IntPtr person = GetForegroundWindow();
    if (person != IntPtr.Zero) { IntPtr root = GetAncestor(person, 2); if (root != IntPtr.Zero) person = root; }
    uint[] family = top == IntPtr.Zero ? new uint[0] : FamilyOf(top);
    if (person != IntPtr.Zero && ProcessOf(person) != 0) {
      foreach (uint member in family) if (member == ProcessOf(person)) { person = IntPtr.Zero; break; }
    }
    lock (Gate) {
      _person = person; _top = top; _family = family; _acting = true; _tail = false; _released = false;
      _beganInput = LastInputTick(); _personActed = false;
      WatchTaken = 0; WatchReturned = 0; WatchFailed = 0; WatchLongestMs = -1;
    }
  }

  // The command is about to do what needs the target in front (expanding a menu or a drop-down, which closes when its
  // window loses the activation): the watch ends here, with no tail.
  public static void Release() {
    lock (Gate) { if (_acting) { _acting = false; _tail = false; _released = true; } }
  }

  // After it: a tail only after a pattern acted (the client hands the permission over asynchronously); none when
  // nothing acted or a fallback will take the front on purpose (the pointer, the wheel, the keyboard, inside the
  // adapter's lease).
  public static void End(bool acted) {
    lock (Gate) {
      _acting = false;
      _tail = acted && !_released;
      _until = unchecked(Environment.TickCount + TailMs);
    }
  }

  private static void OnForeground(IntPtr hook, uint eventType, IntPtr hwnd, int objectId, int childId, uint thread, uint time) {
    IntPtr person; IntPtr top; uint[] family; bool late;
    int after;
    lock (Gate) {
      after = unchecked(Environment.TickCount - _until);
      late = !_acting && (!_tail || after > 0);
      if (late && (_released || after > 5000)) return;
      person = _person; top = _top; family = _family;
    }
    IntPtr foreground = GetForegroundWindow();
    if (foreground == IntPtr.Zero) return;
    IntPtr root = GetAncestor(foreground, 2); if (root != IntPtr.Zero) foreground = root;
    if (!IsTheft(person, top, family, foreground, ProcessOf(foreground), GetWindow(foreground, 4))) return;
    if (late) { Interlocked.Increment(ref Late); LateMs = after; return; }
    if (!IsWindow(person)) return;
    if (LeaseHolds(foreground, top)) {
      // BAXY's own lease brought it up on purpose (a fallback to the pointer, the wheel or the keyboard): the watch ends.
      lock (Gate) { _acting = false; _tail = false; }
      Interlocked.Increment(ref LeaseYielded);
      return;
    }
    Drain();
    bool persons;
    lock (Gate) {
      // Without Raw Input any input since the watch began counts as the person's: the front is never fought then.
      persons = _raw ? _personActed : unchecked((int)(LastInputTick() - _beganInput)) > 0;
      if (persons) { _acting = false; _tail = false; }
    }
    if (persons) { Interlocked.Increment(ref Yielded); return; }
    if (_returning) return;
    Interlocked.Increment(ref WatchTaken);
    int started = Environment.TickCount;
    IntPtr now; IntPtr nowRoot;
    _returning = true;
    try {
      uint foregroundThread = GetWindowThreadProcessId(foreground, out _ignored);
      uint current = GetCurrentThreadId();
      bool attached = foregroundThread != 0 && foregroundThread != current && AttachThreadInput(current, foregroundThread, true);
      try { SetForegroundWindow(person); }
      finally { if (attached) AttachThreadInput(current, foregroundThread, false); }
      now = GetForegroundWindow();
      nowRoot = now == IntPtr.Zero ? IntPtr.Zero : GetAncestor(now, 2);
      if (!MayLower(person, now, nowRoot)) {
        // Refused without the right (the person's input locks the foreground): this thread wins it with its hotkey.
        bool won = Bid(BidBudgetMs);
        if (won) SetForegroundWindow(person);
        now = GetForegroundWindow();
        nowRoot = now == IntPtr.Zero ? IntPtr.Zero : GetAncestor(now, 2);
      }
    } finally { _returning = false; }
    if (MayLower(person, now, nowRoot)) {
      SetWindowPos(top, person, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0200);
      int ms = Environment.TickCount - started;
      Interlocked.Increment(ref Returned); Interlocked.Increment(ref WatchReturned);
      LastReturnMs = ms;
      if (ms > WatchLongestMs) WatchLongestMs = ms;
    } else {
      // The target keeps the front and the keyboard where it is seen; the command's report says so.
      Interlocked.Increment(ref Failed); Interlocked.Increment(ref WatchFailed);
    }
  }
  private static uint _ignored;
}
'@
# END BaxyUiaQuietInput
# Coordenadas fisicas: la captura con la que se comparan los rectangulos se toma
# en pixeles fisicos (GdiScreenshotPlatform), asi que este proceso no puede ser
# virtualizado por el escalado del monitor. -4 = PER_MONITOR_AWARE_V2.
if(-not $DpiUnaware){ try { [void][BaxyUiaWorkerNative]::SetProcessDpiAwarenessContext([IntPtr](-4)) } catch {} }

$AE=[System.Windows.Automation.AutomationElement]
# Goal v3, analisis r3a M1: sin los proveedores del lado cliente, cada ventana de un control comun clasico (ComboBox,
# SysTreeView32, SysListView32, Button, Static) llega como un Pane opaco con el texto de su ventana (medido: una tabla
# de caracteres del sistema, 21 Pane y 1 Edit; con ellos, sus ComboBox, Button, Edit y ListItem; el arbol de carpetas del shell, de 0 a 21
# TreeItem). Se registran una vez, despues de la primera llamada a UIA (antes de ella el registro falla con
# NullReference), con la version, la cultura y la clave del propio cliente. El recibo de la vista dice si se cargaron.
# Se registra su tabla por clase de ventana, sin la entrada sin clase (el puente MSAA nativo para cualquier ventana que
# responde IAccessible por si misma): por ella el contenido de una ventana CEF sin UIA llegaba nodo a nodo entre procesos
# (medido en vivo 2026-10-08: el lanzador de un juego, miles de nodos a ~10 ms cada uno, la vista agotaba sus 20 s y la
# mision paraba con computer_use_view_unavailable; sin ella, 3 nodos en 16 ms y la vista sigue por lo dibujado).
$script:ClientProviders=$false
try {
  $null=$AE::RootElement
  $providers=$AE.Assembly.GetName()
  $providers.Name='UIAutomationClientsideProviders'
  $providerTable=[Reflection.Assembly]::Load($providers).GetType('UIAutomationClientsideProviders.UIAutomationClientSideProviders').GetField('ClientSideProviderDescriptionTable',[Reflection.BindingFlags]'Public,NonPublic,Static').GetValue($null)
  $byClass=@($providerTable | Where-Object { -not [string]::IsNullOrEmpty($_.ClassName) })
  if($byClass.Count -gt 0){
    [System.Windows.Automation.ClientSettings]::RegisterClientSideProviders([System.Windows.Automation.ClientSideProviderDescription[]]$byClass)
    $script:ClientProviders=$true
  }
} catch {}
# El cliente UIA ya esta cargado (RootElement): su SendInput deja de llegar a la pantalla (BaxyUiaQuietInput, r4a M1).
$script:QuietInput='off'
try { $script:QuietInput=[BaxyUiaQuietInput]::Install('UIAutomationCore.dll') } catch { $script:QuietInput='failed' }
# Ronda 21 (v3-64): un encabezado de columna (HeaderItem) se pulsa para ordenar por esa columna: es accionable.
$Actionable=@('Button','MenuItem','ListItem','TabItem','Hyperlink','CheckBox','RadioButton','Edit','ComboBox','TreeItem','SplitButton','Slider','Document','HeaderItem')
$script:LastView=@{ hwnd=[IntPtr]::Zero; elements=@{} }

function Send-Line($object){
  $line=($object | ConvertTo-Json -Compress -Depth 8)
  [Console]::Out.WriteLine($line)
  [Console]::Out.Flush()
}
function Get-Root([long]$hwnd){
  if($hwnd -le 0){ $handle=[BaxyUiaWorkerNative]::GetForegroundWindow() } else { $handle=[IntPtr]$hwnd }
  if($handle -eq [IntPtr]::Zero){ return $null }
  return @{ hwnd=$handle; root=$AE::FromHandle($handle) }
}
function Format-Name([string]$name){
  if([string]::IsNullOrWhiteSpace($name)){ return '' }
  $name=($name -replace '\s+',' ').Trim()
  # Un nombre largo conserva su principio y su final: el titulo de una pestana
  # termina con el sitio («... - Sitio»), que es por lo que se la nombra.
  if($name.Length -gt 80){ $name=(Get-Cut $name 0 60).TrimEnd()+' ... '+(Get-Cut $name ($name.Length-16) $name.Length).TrimStart() }
  return $name
}
# Encargo WA5 (wab3, 4 de 4): un corte nunca parte un par sustituto (un emoji). Format-Name cortaba a los 60 entre las dos
# mitades de un emoji de la vista previa de un chat; con la mitad suelta, String.Normalize (Get-Folded) lanzaba y la vista
# entera fallaba (visible_controls_uia_failed) en cuanto ese nombre quedaba fuera del tope y la mirada llevaba palabras.
function Get-Cut([string]$text,[int]$start,[int]$end){
  if($start -gt 0 -and $start -lt $end -and [char]::IsLowSurrogate($text[$start])){ $start++ }
  if($end -lt $text.Length -and $end -gt $start -and [char]::IsHighSurrogate($text[$end-1])){ $end-- }
  return $text.Substring($start,$end-$start)
}
function Get-Name($el){
  # Los elementos del arbol vienen con cache; la raiz (FromHandle) no.
  $name=$null
  try { $name=$el.Cached.Name } catch { try { $name=$el.Current.Name } catch { $name=$null } }
  return (Format-Name ([string]$name))
}
# Una propiedad de la cache; fuera de ella (la raiz, o un elemento que no vino del arbol), su valor actual.
function Get-Prop($el,[string]$property){
  try { return $el.Cached.$property } catch { try { return $el.Current.$property } catch { return $null } }
}
# El AutomationId es el nombre que el programador dio al control («SettingsButton», «close_button»): se lee
# como palabras cuando lo es. Un numero, un GUID o un hash no nombran nada, y la palabra final que solo repite
# el tipo del control («Button» en un Button) se quita: el nombre es lo que hace, no lo que es. Tampoco nombran
# nada los ids que dicen lo que el control es o donde esta, no lo que hace: un nombre calificado (con «.»: un
# espacio de nombres, una clase), la clase del propio control (ClassName), el nombre por omision de un disenador
# o un ordinal (una palabra en minuscula o el tipo seguidos de un numero: «button1», «textBox1», «uid_12»), un id
# generado (una letra suelta: «radix-:r3:»; letras y cifras alternadas: «a8Xk2Lq9») o uno con mas numeros que
# palabras. El prefijo de las partes de plantilla de WPF («PART_») no es parte del nombre.
function Get-ReadableId([string]$automationId,[string]$kind,[string]$className=''){
  if([string]::IsNullOrWhiteSpace($automationId)){ return '' }
  $raw=$automationId.Trim().Trim('{','}')
  if($raw -match '^[0-9A-Fa-f]{8}-?([0-9A-Fa-f]{4}-?){3}[0-9A-Fa-f]{12}$'){ return '' }
  if($raw.Contains('.')){ return '' }
  if(-not [string]::IsNullOrWhiteSpace($className) -and [string]::Equals($raw,(($className.Trim() -split '\.')[-1]),[StringComparison]::OrdinalIgnoreCase)){ return '' }
  $raw=$raw -creplace '^PART_',''
  if($raw -cmatch '^(\p{L}+)[_-]?\p{N}+$'){
    $stem=$Matches[1]
    if($stem -cmatch '^\p{Ll}' -or [string]::Equals($stem,[string]$kind,[StringComparison]::OrdinalIgnoreCase)){ return '' }
  }
  $tokens=@($raw -split '[^\p{L}\p{N}]+' | Where-Object { $_.Length -gt 0 })
  foreach($token in $tokens){
    if($token -match '^[0-9A-Fa-f]{8,}$' -and $token -match '\d'){ return '' }
    # Cuatro tramos o mas de letras y cifras alternadas («a8Xk2Lq9»): un hash, no palabras.
    if((($token -replace '\p{L}+','a') -replace '\p{N}+','0').Length -ge 4){ return '' }
  }
  $words=New-Object System.Collections.Generic.List[string]
  foreach($token in $tokens){
    $spaced=$token -creplace '(?<=\p{Ll})(?=\p{Lu})',' ' -creplace '(?<=\p{Lu})(?=\p{Lu}\p{Ll})',' ' -replace '(?<=\p{L})(?=\p{N})',' ' -replace '(?<=\p{N})(?=\p{L})',' '
    foreach($word in ($spaced -split ' ')){ if($word.Length -gt 0){ $words.Add($word) } }
  }
  $kindWords=@((([string]$kind) -creplace '(?<=\p{Ll})(?=\p{Lu})',' ').Trim() -split ' ' | Where-Object { $_.Length -gt 0 })
  if($kindWords.Count -gt 0 -and $words.Count -ge $kindWords.Count){
    $tail=@($words.GetRange($words.Count-$kindWords.Count,$kindWords.Count)) -join ' '
    if([string]::Equals($tail,($kindWords -join ' '),[StringComparison]::OrdinalIgnoreCase)){ $words.RemoveRange($words.Count-$kindWords.Count,$kindWords.Count) }
    elseif([string]::Equals($words[$words.Count-1],$kindWords[$kindWords.Count-1],[StringComparison]::OrdinalIgnoreCase)){ $words.RemoveAt($words.Count-1) }
  }
  # Una letra suelta es un trozo de un id generado, no una palabra.
  if(@($words | Where-Object { $_ -match '^\p{L}$' }).Count -gt 0){ return '' }
  # Sin una palabra de dos letras o mas («12») no queda nombre; con mas numeros que palabras, es un indice.
  $alpha=@($words | Where-Object { $_ -match '^\p{L}{2,}$' }).Count
  $numeric=@($words | Where-Object { $_ -match '^\p{N}+$' }).Count
  if($alpha -eq 0 -or $numeric -gt $alpha){ return '' }
  return (Format-Name ($words -join ' '))
}
# Un control sin Name no queda mudo si su aplicacion lo nombra de otro modo: su texto de ayuda (el ToolTip de
# WPF se publica como HelpText), el nombre del rotulo que lo etiqueta (LabeledBy, un campo de formulario) o su
# AutomationId legible, en ese orden. «source» dice de donde salio; vacio si no hay nombre.
function Get-FallbackName([string]$helpText,[string]$labelName,[string]$automationId,[string]$kind,[string]$className=''){
  $help=Format-Name $helpText
  if($help.Length -gt 0){ return @{ name=$help; source='helpText' } }
  $label=Format-Name $labelName
  if($label.Length -gt 0){ return @{ name=$label; source='labeledBy' } }
  $readable=Get-ReadableId $automationId $kind $className
  if($readable.Length -gt 0){ return @{ name=$readable; source='automationId' } }
  return @{ name=''; source='' }
}
# El nombre con que se muestra y se busca un control: su Name; sin el, y solo en un accionable (un panel o un
# grupo sin nombre sigue sin informar de nada), el nombre de respaldo. source vacio = su propio Name.
function Get-ShownName($el){
  $name=Get-Name $el
  if($name.Length -gt 0){ return @{ name=$name; source='' } }
  $kind=([string](Get-Prop $el 'ControlType').ProgrammaticName) -replace '^ControlType\.',''
  if($Actionable -notcontains $kind){ return @{ name=''; source='' } }
  $labelName=''
  $label=Get-Prop $el 'LabeledBy'
  if($null -ne $label){ $labelName=Get-Name $label }
  return (Get-FallbackName ([string](Get-Prop $el 'HelpText')) $labelName ([string](Get-Prop $el 'AutomationId')) $kind ([string](Get-Prop $el 'ClassName')))
}
# Ronda 24 (v3-39): la clave con que la vista junta controles iguales. Un control elegido (selected, on) no es el
# duplicado de uno igual sin elegir: el desplegable «Perfil predeterminado» elige «Windows PowerShell» y la lista de
# perfiles tiene otro «Windows PowerShell»; descartar el elegido borraba el dato. Dos filas iguales sin estado distinto
# siguen juntas (x2).
function Get-SeenKey([string]$kind,[string]$name,[string]$state){
  $key=$kind+'|'+$name
  $chosen=@(([string]$state) -split ' ' | Where-Object { $_ -eq 'selected' -or $_ -eq 'on' })
  if($chosen.Count -gt 0){ $key+='|'+($chosen -join ' ') }
  return $key
}
# Ronda 24 (v3-39): el nombre del elemento elegido de un desplegable que expone SelectionPattern y no ValuePattern
# (WinUI: el combo «Perfil predeterminado» de Terminal). Vacio si no hay seleccion; $null si no se puede leer.
function Get-ChosenEntry($el){
  try {
    $pattern=$el.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern)
    if($null -eq $pattern){ return $null }
    $chosen=@($pattern.Current.GetSelection())
    if($chosen.Count -eq 0 -or $null -eq $chosen[0]){ return $null }
    $raw=([string]$chosen[0].Current.Name -replace '\s+',' ').Trim()
    if($raw.Length -eq 0){ return $null }
    if($raw.Length -gt 120){ $raw=Get-Cut $raw 0 120 }
    return $raw
  } catch { return $null }
}
function Get-State($el){
  $parts=@()
  $value=$null
  try {
    $pattern=$null
    if($el.TryGetCachedPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)){
      $state=([System.Windows.Automation.TogglePattern]$pattern).Cached.ToggleState
      if($state -eq [System.Windows.Automation.ToggleState]::On){$parts+='on'} elseif($state -eq [System.Windows.Automation.ToggleState]::Off){$parts+='off'}
    }
    if($el.TryGetCachedPattern([System.Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern)){
      if(([System.Windows.Automation.SelectionItemPattern]$pattern).Cached.IsSelected){$parts+='selected'}
    }
    if($el.TryGetCachedPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$pattern)){
      $state=([System.Windows.Automation.ExpandCollapsePattern]$pattern).Cached.ExpandCollapseState
      if($state -eq [System.Windows.Automation.ExpandCollapseState]::Expanded){$parts+='expanded'} elseif($state -eq [System.Windows.Automation.ExpandCollapseState]::Collapsed){$parts+='collapsed'}
    }
    if($el.TryGetCachedPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)){
      $vp=([System.Windows.Automation.ValuePattern]$pattern)
      if($vp.Cached.IsReadOnly){$parts+='readonly'}
      $raw=[string]$vp.Cached.Value
      # An exposed empty value is "" (known empty); a field that exposes none stays null (its content is unknown).
      if(-not [string]::IsNullOrWhiteSpace($raw)){ $raw=($raw -replace '\s+',' ').Trim(); if($raw.Length -gt 120){$raw=Get-Cut $raw 0 120}; $value=$raw } else { $value='' }
    } elseif($el.TryGetCachedPattern([System.Windows.Automation.RangeValuePattern]::Pattern,[ref]$pattern)){
      $value=[string]([System.Windows.Automation.RangeValuePattern]$pattern).Cached.Value
    } elseif(($el.Cached.ControlType.ProgrammaticName -replace '^ControlType\.','') -eq 'ComboBox'){
      # Ronda 24 (v3-39): un desplegable sin ValuePattern dice su valor por la seleccion: el nombre del elemento elegido.
      $value=Get-ChosenEntry $el
    }
    if($el.Cached.IsPassword){$parts+='password'}
    if($el.Cached.HasKeyboardFocus){$parts+='focused'}
  } catch [System.Windows.Automation.ElementNotAvailableException] {}
  return @{ state=($parts -join ' '); value=$value }
}
function Get-Rect($el){
  try {
    $r=$el.Cached.BoundingRectangle
    if($r.IsEmpty -or [double]::IsInfinity($r.Width) -or [double]::IsNaN($r.X)){ return $null }
    return @{ x=[int][math]::Round($r.X); y=[int][math]::Round($r.Y); w=[int][math]::Round($r.Width); h=[int][math]::Round($r.Height) }
  } catch { return $null }
}
function Get-Id($el){
  try { return (($el.GetRuntimeId() | ForEach-Object { [string]$_ }) -join '.') } catch { return '' }
}
# Auditoria P3: la etiqueta nombra un control solo si es su nombre, plegado como el Fold del adaptador (sin tildes, en
# minusculas, los espacios juntos; Get-LabelFolded). Ni alias, ni contener, ni erratas.
function Test-NameMatch([string]$name,[string[]]$aliases){
  $seen=Get-LabelFolded $name
  if($seen.Length -eq 0){ return $false }
  foreach($alias in $aliases){
    if((Get-LabelFolded $alias) -ceq $seen){ return $true }
    # Un nombre largo se muestra recortado (Format-Name): la etiqueta que lo da entero (Get-AskingName) es el mismo.
    if($alias.Length -gt 80 -and (Get-LabelFolded (Format-Name $alias)) -ceq $seen){ return $true }
  }
  return $false
}
function Get-LabelFolded([string]$text){
  if([string]::IsNullOrWhiteSpace($text)){ return '' }
  # Un par sustituto suelto (un emoji cortado) no se normaliza: se compara tal cual.
  $plain=$text; try { $plain=$text.Normalize([Text.NormalizationForm]::FormD) -replace '\p{Mn}','' } catch {}
  return ([regex]::Replace($plain.ToLowerInvariant(),'\s+',' ')).Trim()
}
# Plegado: sin acentos, en minusculas, solo letras y digitos separados por un espacio.
function Get-Folded([string]$text){
  if([string]::IsNullOrWhiteSpace($text)){ return '' }
  $plain=$text.Normalize([Text.NormalizationForm]::FormD) -replace '\p{Mn}',''
  return (($plain.ToLowerInvariant() -replace '[^\p{L}\p{N}]+',' ').Trim())
}
# El nombre lleva la etiqueta como palabras enteras: «Sitio» esta en la pestana «Un titulo largo - Sitio». Auditoria
# C10: ya no se pulsa por eso; cuando ningun nombre es igual a la etiqueta, esos nombres vuelven como candidatos para
# que el modelo nombre uno tal cual. Solo items que llevan un titulo (una pestana, una fila de lista o arbol, un
# enlace), nunca un panel o un documento cuyo nombre es la pagina entera (medido en una ventana CEF).
$script:TitledKinds=@('ControlType.TabItem','ControlType.ListItem','ControlType.TreeItem','ControlType.Hyperlink')
function Test-ItemHolds($el,[string[]]$aliases){
  # Del arbol con cache (una llamada por nodo menos); fuera de ella, su valor actual.
  $kind=''
  try { $kind=[string]$el.Cached.ControlType.ProgrammaticName } catch { $kind='' }
  if($kind.Length -eq 0){ try { $kind=[string]$el.Current.ControlType.ProgrammaticName } catch { return $false } }
  if($script:TitledKinds -notcontains $kind){ return $false }
  return (Test-NameHolds (Get-ShownName $el).name $aliases)
}
function Test-NameHolds([string]$name,[string[]]$aliases){
  $words=' '+(Get-Folded $name)+' '
  foreach($alias in $aliases){
    $needle=Get-Folded $alias
    if($needle.Length -gt 0 -and $words.Contains(' '+$needle+' ')){ return $true }
  }
  return $false
}
# Encargo V (banco e2, c7): RiskPolicy juzgo la etiqueta del clic y aqui se resuelve el control que se pulsa, a veces uno
# que la vista no listo y cuyo nombre solo contiene la etiqueta ('cotele' pulso el canal de voz 'Cotele..., Canal de voz,
# Choche' sin preguntar). Un control cuyo nombre pide la palabra de la persona (sale al mundo, llega a alguien o no se
# deshace) cuando ninguna etiqueta la pide no se pulsa: se responde con su nombre, para que el paso lo nombre y RiskPolicy
# pregunte. Patron y pista de atajo de RiskPolicy (peticion 'asks': AsksPattern, FoldHint); plegado como su Fold.
function Get-AskFolded([string]$text,[string]$hint){
  $form=$text.Normalize([Text.NormalizationForm]::FormD).ToLowerInvariant()
  $kept=New-Object System.Text.StringBuilder
  foreach($ch in $form.ToCharArray()){
    $category=[Globalization.CharUnicodeInfo]::GetUnicodeCategory($ch)
    if($category -ne [Globalization.UnicodeCategory]::NonSpacingMark -and $category -ne [Globalization.UnicodeCategory]::Format){ [void]$kept.Append($ch) }
  }
  $folded=$kept.ToString().Split([char[]]@(),[StringSplitOptions]::RemoveEmptyEntries) -join ' '
  return ([regex]::Replace($folded,$hint,'',[Text.RegularExpressions.RegexOptions]::CultureInvariant)).Trim()
}
function Test-Asks([string]$text,$asks){
  if([string]::IsNullOrWhiteSpace($text)){ return $false }
  return [regex]::IsMatch((Get-AskFolded $text ([string]$asks.hint)),[string]$asks.pattern,[Text.RegularExpressions.RegexOptions]::CultureInvariant)
}
function Test-AsksMore([string]$name,[string[]]$aliases,$asks){
  if($null -eq $asks -or ([string]$asks.pattern).Length -eq 0 -or -not (Test-Asks $name $asks)){ return $false }
  foreach($alias in $aliases){ if(Test-Asks $alias $asks){ return $false } }
  return $true
}
# Revision de V (H2, H3): lo que recibe la pulsacion. Su nombre crudo (Format-Name lo recorta a 80: un canal de voz de
# nombre largo perdia 'Canal de voz' en el recorte) y su nombre mostrado; y, si no se pulsa por si mismo (sin Invoke,
# SelectionItem, Toggle ni ExpandCollapse: el Text de dentro de un enlace, cuya pulsacion legacy, render o de puntero cae
# en el enlace), los de sus antecesores hasta el primero que si, como mucho LineageUp. El primero que pide mas que las
# etiquetas, o ''.
# Revision de V (H4): por la etiqueta sola, un control de cualquier tipo (un Button 'Iniciar Transmision' para
# 'Transmision'; solo los de TitledKinds se resuelven por contener) que contiene la etiqueta como palabras y pide mas que
# ella, cuando ninguno se llama exactamente asi: el clic responde con su nombre antes de nada (ni ambiguo, ni corte del
# plazo, ni la cascada de OCR y puntero). Solo durante un clic con el patron de RiskPolicy ($script:AskSearch).
$script:AskSearch=$null
$script:AskingName=''
function Get-AskAliases([string[]]$aliases){
  if($null -eq $script:AskSearch -or ([string]$script:AskSearch.pattern).Length -eq 0 -or $script:AskingName.Length -gt 0){ return $null }
  foreach($alias in $aliases){ if(Test-Asks $alias $script:AskSearch){ return $null } }
  return ,@($aliases)
}
function Note-AskingName([string]$raw,[string]$alias){
  if((Test-NameHolds $raw @($alias)) -and (Test-Asks $raw $script:AskSearch)){ $script:AskingName=($raw -replace '\s+',' ').Trim() }
}
function Test-PressesItself($el){
  $pattern=$null
  foreach($kind in @([System.Windows.Automation.InvokePattern]::Pattern,[System.Windows.Automation.SelectionItemPattern]::Pattern,
                     [System.Windows.Automation.TogglePattern]::Pattern,[System.Windows.Automation.ExpandCollapsePattern]::Pattern)){
    try { if($el.TryGetCurrentPattern($kind,[ref]$pattern)){ return $true } } catch {}
  }
  return $false
}
function Get-AskingName($el,[string]$shown,[string[]]$aliases,$asks){
  if($null -eq $asks -or ([string]$asks.pattern).Length -eq 0){ return '' }
  foreach($alias in $aliases){ if(Test-Asks $alias $asks){ return '' } }
  if(Test-Asks $shown $asks){ return $shown }
  $walker=Get-LineageWalker
  $node=$el
  for($steps=0;$null -ne $node -and $steps -le $script:LineageUp;$steps++){
    $raw=''
    try { $raw=[string]$node.Current.Name } catch { $raw='' }
    if(Test-Asks $raw $asks){ return (($raw -replace '\s+',' ').Trim()) }
    if(Test-PressesItself $node){ break }
    try { $node=$walker.GetParent($node) } catch { $node=$null }
  }
  return ''
}
# Lo que un control ofrece para pulsarlo sin raton: sus patrones, su tipo, si su valor se escribe y si es una ventana
# Win32 clasica (lee los mensajes de su cola).
function Get-ClickFacts($el){
  $facts=@{ invoke=$false; select=$false; toggle=$false; expand=$false; kind=''; value=$false; classic=$false; native=$false }
  $pattern=$null
  try { $facts.invoke=$el.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$pattern) } catch {}
  try { $facts.select=$el.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern) } catch {}
  try { $facts.toggle=$el.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern) } catch {}
  try { $facts.expand=$el.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$pattern) } catch {}
  try { $facts.kind=([string]$el.Current.ControlType.ProgrammaticName) -replace '^ControlType\.','' } catch {}
  try {
    if($el.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)){
      $facts.value=-not ([System.Windows.Automation.ValuePattern]$pattern).Current.IsReadOnly
    }
  } catch {}
  $framework=''
  try {
    $framework=[string]$el.Current.FrameworkId
    $facts.classic=@('Win32','WinForm') -contains $framework
    $facts.native=$script:NativeItemFrameworks -contains $framework
  } catch {}
  # r20b palanca 4 (v3-42, v3-43): un boton de barra de herramientas Win32 que el cliente UIA ve por su proxy MSAA
  # (RuntimeId 42.<ventana>.<objeto>.<hijo>, padre ToolBar). Su Invoke es la accion por defecto del proxy, que pulso
  # con el raton fisico (clic sin la marca de BAXY en el punto del boton, medido <=200 ms tras el Invoke); su ventana es
  # la barra (segundo componente) y su hijo el ultimo. Solo por como esta hecho el control, nunca por la aplicacion.
  $facts.toolbarProxy=$false
  if($framework -eq 'Win32'){
    try {
      $runtime=[int[]]$el.GetRuntimeId()
      if((Get-ToolbarProxy $framework $runtime 'ToolBar').proxy){
        $parentKind=''
        $parent=[System.Windows.Automation.TreeWalker]::RawViewWalker.GetParent($el)
        if($null -ne $parent){ $parentKind=([string]$parent.Current.ControlType.ProgrammaticName) -replace '^ControlType\.','' }
        $bar=Get-ToolbarProxy $framework $runtime $parentKind
        if($bar.proxy){ $facts.toolbarProxy=$true; $facts.toolbarWindow=$bar.window; $facts.toolbarChild=$bar.child }
      }
    } catch { $facts.toolbarProxy=$false }
  }
  return $facts
}
# El hecho «toolbarProxy» por la forma del control: marco Win32, RuntimeId del proxy MSAA (42, ventana, objeto, hijo) y
# padre ToolBar. Devuelve la ventana de la barra (sin signo) y el hijo.
function Get-ToolbarProxy([string]$framework,[int[]]$runtime,[string]$parentKind){
  $none=@{ proxy=$false; window=[long]0; child=0 }
  if($framework -ne 'Win32' -or $parentKind -ne 'ToolBar' -or $null -eq $runtime -or $runtime.Count -ne 4){ return $none }
  if($runtime[0] -ne 42 -or $runtime[1] -eq 0 -or $runtime[3] -le 0){ return $none }
  $bar=[long]$runtime[1]
  if($bar -lt 0){ $bar+=4294967296 }
  return @{ proxy=$true; window=$bar; child=[int]$runtime[3] }
}
# Ronda 20b, palanca 7 (v3-52, v3-53): los marcos cuyos elementos viven dentro de una ventana nativa que lee los mensajes
# del raton de su cola, aunque no sean controles Win32. DATOS medidos: Qt (su SelectionItem.Select marca la fila sin
# hacerla actual, y su Toggle cambia la casilla sin la senal que la aplicacion escucha). wx y GTK, cuando se midan.
$script:NativeItemFrameworks=@('Qt')
# Ronda 24b (banco r23 s04): los elementos que eligen un lugar al elegirse (un nodo de arbol, una pestana); su recibo
# lleva placeMoved. Y los contenedores que solo agrupan lo que se pulsa (u9).
$script:PlaceItemKinds=@('TreeItem','TabItem')
$script:ContainerKinds=@('List','Tree','DataGrid','Table')
# Clic sin raton siempre que exista una via (CONTRATO_VISTA_ACCION.md, arreglo 2 del punto 0): el primer patron que
# tenga (Invoke, SelectionItem.Select, Toggle, ExpandCollapse); un campo que toma texto (Edit o Document con valor
# escribible) no se pulsa, queda como destino del texto si toma el foco del teclado; si no, la accion por defecto de
# LegacyIAccessible; en una ventana Win32 clasica, la pulsacion enviada como mensaje a su ventana hija; y solo al
# final el puntero, que no mueve este proceso sino el adaptador. Devuelve las vias en orden de intento.
# fable/cu-v3-clic-chromium: sobre la superficie de render de Chromium (WebView2, CEF, Electron: el hecho «render», por
# la clase de su ventana) la pulsacion enviada a esa ventana va primero: medido en vivo, no toma el frente ni el cursor,
# mientras SelectionItem.Select trajo la ventana al frente y el buscador no tenia patron ni accion por defecto. El
# patron queda detras por si el punto no esta en la superficie; un campo sigue siendo destino solo con el foco.
# Revision de fable/cu-v3-clic-chromium (hallazgo 2): solo donde se midio. Antes del patron, solo con SelectionItem (el
# que trajo el frente); Invoke, Toggle y ExpandCollapse siguen solos, como antes (llegan al elemento exacto y ninguno
# se midio tomando el frente). Sin patron: el campo tras «target»; cualquier otro, tras la accion por defecto (que
# tambien llega al elemento exacto). Y nunca a ciegas: antes de enviar, lo que la pagina tiene en el punto es el
# elemento (Send-RenderPress).
# Recibo del clic por estado (r15b v3-46, v3-50, v3-52): lo que un clic elige (un elemento de lista, arbol, pestanas o
# cuadricula con SelectionItem, sin Toggle) y aun no esta elegido recibe una lista ordenada de vias, cada una solo si la
# anterior no lo dejo elegido (Invoke-NamedControl lo relee): Invoke, despues Select, despues la pulsacion enviada como
# mensaje en una ventana Win32 clasica. Un Toggle o un CheckBox nunca recibe una segunda via (dos pulsaciones lo dejarian
# como estaba). Un elemento de arbol cerrado que la mision pide abrir se abre por su manera «open» (Invoke-MannerControl:
# elegirlo y abrirlo en el mismo acto), nunca con el clic de elegir.
# r20b palanca 4: un boton de barra visto por el proxy MSAA (hecho «toolbarProxy») recibe primero la pulsacion enviada
# como mensaje a la barra en su punto, sin cursor ni frente (Invoke-NamedControl comprueba antes que la barra y su
# prueba de impacto dan ese boton en el punto); despues, como reserva, sus vias de siempre (Invoke, cuando la barra no
# esta en el punto). Un boton Win32 con ventana propia, uno XAML o WPF no son proxies: sin cambios.
$script:PatternMethods=@('invoke','select','toggle','expand','target','render')
function Select-ClickMethods($facts){
  if([bool]$facts.toolbarProxy){
    $plain=$facts.Clone(); $plain.toolbarProxy=$false
    return @(@('message')+@(Select-ClickMethods $plain | Where-Object { $_ -ne 'message' }))
  }
  $field=(@('Edit','Document') -contains [string]$facts.kind -and $facts.value)
  $render=[bool]$facts.render
  $choosing=([bool]$facts.select -and -not [bool]$facts.toggle -and @('ListItem','TreeItem','TabItem','DataItem') -contains [string]$facts.kind -and -not [bool]$facts.selected)
  if($choosing -and -not $render){
    $ways=@()
    if($facts.invoke){ $ways+='invoke' }
    $ways+='select'
    if($facts.classic -or $facts.native){ $ways+='message' }
    return $ways
  }
  foreach($name in @('invoke','select','toggle','expand')){
    if($facts.$name){ if($render -and $name -eq 'select' -and -not $field){ return @('render',$name) }; return @($name) }
  }
  $methods=@()
  if($field){ $methods+='target' }
  if($render -and $field){ $methods+='render' }
  $methods+='legacy'
  if($render -and -not $field){ $methods+='render' }
  if($facts.classic){ $methods+='message' }
  $methods+='pointer'
  return $methods
}
# La ventana de la mision es la del frente (o la raiz de la del frente): solo entonces se puede dar el foco del
# teclado a uno de sus campos sin traerla al frente.
function Test-InFront([IntPtr]$top){
  if($top -eq [IntPtr]::Zero){ return $false }
  $front=[BaxyUiaWorkerNative]::GetForegroundWindow()
  if($front -eq [IntPtr]::Zero){ return $false }
  return ([BaxyUiaWorkerNative]::GetAncestor($front,2) -eq [BaxyUiaWorkerNative]::GetAncestor($top,2))
}
# El punto que pulsaria una persona: el punto clicable que da el control o el centro de su rectangulo.
function Get-PressPoint($el){
  try { $point=$el.GetClickablePoint(); return @{ x=[int]$point.X; y=[int]$point.Y } } catch {}
  try {
    $box=$el.Current.BoundingRectangle
    if($box.IsEmpty -or $box.Width -le 0 -or $box.Height -le 0){ return $null }
    return @{ x=[int]($box.X+$box.Width/2); y=[int]($box.Y+$box.Height/2) }
  } catch { return $null }
}
function Get-CurrentRect($el){
  try {
    $r=$el.Current.BoundingRectangle
    if($r.IsEmpty -or [double]::IsInfinity($r.Width) -or [double]::IsNaN($r.X)){ return $null }
    return @{ x=[int][math]::Round($r.X); y=[int][math]::Round($r.Y); w=[int][math]::Round($r.Width); h=[int][math]::Round($r.Height) }
  } catch { return $null }
}
# Pulsa el control por la primera via que funcione. Devuelve method (invoke|select|toggle|expand|target|legacy|message|
# pointer); con «pointer» nada se pulso aun: lleva el punto y el rectangulo para el adaptador. Con -PatternsOnly solo
# se intentan los patrones y el campo destino. Nulo si ninguna via sirve.
$script:RenderHosts=@()
# Las ventanas donde se busca la superficie de render: la del clic y las de contenido de su familia que da el adaptador.
function Get-RenderHosts([IntPtr]$top){
  return [IntPtr[]](@($top)+@($script:RenderHosts | Where-Object { $null -ne $_ -and $_ -ne $top }))
}
# Revision de fable/cu-v3-clic-chromium (hallazgos 1, 3 y 4): la pulsacion enviada solo cae donde se pidio. La prueba
# de impacto de la propia pagina en el punto (HitChain: del nodo tocado hacia arriba) debe dar el elemento o algo
# dentro de el: una caja igual a la suya (2 px) con su nombre, sin pasar antes por nada que se salga de su rectangulo.
# Una capa de la pagina, una ventana emergente encima o otro control en ese punto dan otra cosa: nada se envia.
function Test-HitIsElement($chain,$el){
  try { $box=$el.Current.BoundingRectangle } catch { return $false }
  if($box.IsEmpty -or $box.Width -le 0 -or $box.Height -le 0){ return $false }
  $name=''
  try { $name=([string]$el.Current.Name).Trim() } catch { $name='' }
  foreach($node in @($chain)){
    if($node.Width -le 0 -or $node.Height -le 0){ continue }
    $same=([math]::Abs($node.Left-$box.X) -le 2 -and [math]::Abs($node.Top-$box.Y) -le 2 -and
      [math]::Abs($node.Width-$box.Width) -le 2 -and [math]::Abs($node.Height-$box.Height) -le 2)
    if($same -and ($name.Length -eq 0 -or [string]::Equals(([string]$node.Name).Trim(),$name,[StringComparison]::OrdinalIgnoreCase))){ return $true }
    if($node.Left -lt $box.X-2 -or $node.Top -lt $box.Y-2 -or ($node.Left+$node.Width) -gt ($box.X+$box.Width+2) -or
      ($node.Top+$node.Height) -gt ($box.Y+$box.Height+2)){ return $false }
  }
  return $false
}
# En «at» no hay elemento: lo que la pagina tiene en el punto debe nombrar la etiqueta leida en pantalla (el nodo
# tocado o uno de sus tres antecesores, nunca el documento). Lo leido por OCR o vision se comprueba en el momento de
# pulsar: una lista que se reordeno, el boton de titulo de un marco encima del contenido o una capa nueva no la nombran.
function Test-HitNamesLabel($chain,[string[]]$aliases){
  $depth=0
  foreach($node in @($chain)){
    if(@(15,9,10) -contains [int]$node.Role){ break }
    if(Test-NameHolds ([string]$node.Name) $aliases){ return $true }
    $depth++
    if($depth -ge 4){ break }
  }
  return $false
}
# La pulsacion enviada a la superficie de render bajo el punto, solo si la prueba de impacto de la pagina da lo que se
# pide (el elemento, o la etiqueta en «at»). Devuelve donde se paro: none (sin superficie), dpi, nohit (la pagina no
# respondio), other (otra cosa en el punto), post-failed o posted.
function Send-RenderPress([IntPtr[]]$hosts,[int]$x,[int]$y,[uint32]$process,$element,[string[]]$aliases){
  $surface=[BaxyUiaWorkerNative]::RenderAt($hosts,$x,$y,$process)
  if($surface -eq [IntPtr]::Zero){ return 'none' }
  if(-not [BaxyUiaWorkerNative]::SameDpi($surface)){ return 'dpi' }
  $chain=@([BaxyUiaWorkerNative]::HitChain($surface,$x,$y))
  if($chain.Count -eq 0){ return 'nohit' }
  $holds=$(if($null -ne $element){ Test-HitIsElement $chain $element } else { Test-HitNamesLabel $chain $aliases })
  if(-not $holds){ return 'other' }
  if(-not [BaxyUiaWorkerNative]::PostAt($surface,$x,$y)){ return 'post-failed' }
  return 'posted'
}
# Lo que un Invoke tiene para volver antes de quedar pendiente y bloqueado (un bucle modal de la aplicacion).
$script:InvokeWaitMs=1000
# Una via que elige: el elemento queda elegido en 300 ms (releido cada 50 ms).
function Wait-Chosen($el){
  for($look=0;$look -lt 6;$look++){
    if(Test-Selected $el){ return $true }
    Start-Sleep -Milliseconds 50
  }
  return [bool](Test-Selected $el)
}
# Revision r2 (hallazgo 3): un Invoke que hizo algo propio (la fila se fue o dejo de verse, se abrio un dialogo modal
# que deshabilito su ventana, o el titulo de su ventana cambio: se abrio o se reprodujo lo que nombra) es el recibo del
# clic aunque la fila no quede elegida; ninguna via mas se prueba sobre ella. Sin ninguna de esas huellas (la fila Qt de
# v3-52, que Invoke no hizo actual) sigue la siguiente via. Select y la pulsacion posteada solo eligen.
function Get-InvokeTrace($el,[IntPtr]$top){
  $present=$true
  try { $present=-not [bool]$el.Current.IsOffscreen } catch { $present=$false }
  $enabled=$true
  $title=''
  if($top -ne [IntPtr]::Zero){
    try { $enabled=[bool][BaxyUiaWorkerNative]::IsWindowEnabled($top); $title=[string][BaxyUiaWorkerNative]::Text($top) } catch {}
  }
  return @{ present=$present; enabled=$enabled; title=$title }
}
function Test-InvokeActedAlone($before,$after){
  if(-not [bool]$after.present){ return $true }
  if([bool]$before.enabled -and -not [bool]$after.enabled){ return $true }
  return ([string]$before.title -ne [string]$after.title)
}
function Select-Element($el){
  $pattern=$null
  [void]$el.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern)
  ([System.Windows.Automation.SelectionItemPattern]$pattern).Select()
}
# Ronda 20b, palanca 7: el lugar de la ventana, para saber si una eleccion lo movio: su titulo y lo que muestra, cada
# control con nombre por su identidad (RuntimeId) con su tipo y su nombre.
# Revision 2 (B3): una etiqueta viva (la barra de estado con «CPU: 1.4%, 30.00 fps», un contador de tiempo o de kb/s)
# cambia sola: comparar todos los nombres daba el lugar por movido sin que la eleccion hiciera nada.
function Get-PlaceTrace([IntPtr]$top){
  $title=''
  try { $title=[string][BaxyUiaWorkerNative]::Text($top) } catch { $title='' }
  $items=@{}
  try {
    $found=Get-Root ([long]$top)
    if($null -ne $found -and $null -ne $found.root){
      $position=0
      foreach($item in @(Get-Descendants $found.root)){
        $position++
        try {
          if($item.Cached.IsOffscreen){ continue }
          $name=[string]$item.Cached.Name
          if([string]::IsNullOrWhiteSpace($name)){ continue }
          $kind=[string]($item.Cached.ControlType.ProgrammaticName -replace '^ControlType\.','')
          $key=''
          try { $key=(($item.GetRuntimeId() | ForEach-Object { [string]$_ }) -join '.') } catch { $key='' }
          # Sin identidad, el tipo y el nombre: un cambio de nombre se ve como uno que se fue y otro que vino.
          if($key.Length -eq 0){ $key=$kind+'|'+$name+'#'+$position }
          $items[$key]=@{ kind=$kind; name=$name }
        } catch {}
      }
    }
  } catch {}
  return @{ title=$title; items=$items; volatile=@{} }
}
# Revision 2 de la ronda 24b (B1): la medida del lugar corre en cada pulsacion que elige un item, en cualquier marco, y
# cada lectura recorre el arbol entero (0,2-0,6 s en una ventana corriente; segundos en una consola MMC grande). Su
# coste tiene tope: el lugar se relee tras la pulsacion solo PlaceWaitMs en total (al menos una lectura); una lectura
# que cuesta mas que PlaceTwiceMs no se repite antes de pulsar (lo volatil no se aprende: un texto que cambia en su sitio
# ya no cuenta, Test-PlaceMoved); y una ventana cuya lectura costo mas que PlaceCeilingMs no se mide mas (ni despues de
# esa pulsacion ni en las siguientes): su recibo va sin placeMoved, como antes de r24b, y el clic cabe en su presupuesto.
$script:PlaceWaitMs=600
$script:PlaceTwiceMs=300
$script:PlaceCeilingMs=2000
# Lo que costo la ultima lectura del lugar de cada ventana (por su manija), para no volver a pagar una lectura cara.
$script:PlaceCostMs=@{}
# El lugar no se mide en una ventana cuya lectura ya costo mas que el tope.
function Test-PlaceTooDear([IntPtr]$top){
  $ceiling=[int]$script:PlaceCeilingMs
  if($ceiling -le 0 -or $null -eq $script:PlaceCostMs){ return $false }
  $key=[long]$top
  return ($script:PlaceCostMs.ContainsKey($key) -and [long]$script:PlaceCostMs[$key] -gt $ceiling)
}
# Lo volatil se aprende antes de pulsar: dos lecturas del lugar, y lo que cambio entre ellas (o vino o se fue) no cuenta.
# Revision 2 (B1): una lectura cara no se repite; la segunda solo si la primera costo como mucho PlaceTwiceMs.
function Get-SteadyPlace([IntPtr]$top){
  $watch=[System.Diagnostics.Stopwatch]::StartNew()
  $first=Get-PlaceTrace $top
  $cost=[long]$watch.ElapsedMilliseconds
  if($null -ne $script:PlaceCostMs){ $script:PlaceCostMs[[long]$top]=$cost }
  if([int]$script:PlaceTwiceMs -gt 0 -and $cost -gt [int]$script:PlaceTwiceMs){ return $first }
  $second=Get-PlaceTrace $top
  if($null -eq $first -or $null -eq $second){ return $second }
  $volatile=@{}
  foreach($key in @($first.items.Keys)){
    if(-not $second.items.ContainsKey($key) -or [string]$second.items[$key].name -ne [string]$first.items[$key].name){ $volatile[$key]=$true }
  }
  foreach($key in @($second.items.Keys)){ if(-not $first.items.ContainsKey($key)){ $volatile[$key]=$true } }
  $second.volatile=$volatile
  return $second
}
# El lugar se movio: cambio el titulo, vino o se fue un control con nombre, o cambio el nombre de uno que no es texto.
# Un texto que cambia de nombre en su sitio es una etiqueta que se actualiza (un estado, un contador), nunca otro lugar;
# lo aprendido como volatil antes de pulsar no cuenta.
function Test-PlaceMoved($before,$after){
  if($null -eq $before -or $null -eq $after){ return $true }
  if([string]$before.title -ne [string]$after.title){ return $true }
  $volatile=$(if($null -ne $before.volatile){ $before.volatile } else { @{} })
  $was=$(if($null -ne $before.items){ $before.items } else { @{} })
  $now=$(if($null -ne $after.items){ $after.items } else { @{} })
  foreach($key in @($now.Keys)){
    if($volatile.ContainsKey($key)){ continue }
    if(-not $was.ContainsKey($key)){ return $true }
    if([string]$was[$key].name -ne [string]$now[$key].name -and [string]$now[$key].kind -ne 'Text'){ return $true }
  }
  foreach($key in @($was.Keys)){ if(-not $volatile.ContainsKey($key) -and -not $now.ContainsKey($key)){ return $true } }
  return $false
}
# El lugar releido tras la pulsacion: movido o no. Revision 2 (B1): el tope es de tiempo (PlaceWaitMs en total, medido
# con reloj), no de lecturas: al menos una lectura, y ninguna nueva empieza pasado el tope.
function Wait-PlaceMoved($before,[IntPtr]$top){
  $watch=[System.Diagnostics.Stopwatch]::StartNew()
  $budget=[int]$script:PlaceWaitMs
  while($true){
    if(Test-PlaceMoved $before (Get-PlaceTrace $top)){ return $true }
    if($watch.ElapsedMilliseconds + 50 -ge $budget){ return $false }
    Start-Sleep -Milliseconds 50
  }
}
# Lo que UIA tiene en el punto es el elemento o algo dentro de el (tres niveles hacia arriba como mucho).
function Test-PointIsElement($el,$point){
  try {
    $hit=[System.Windows.Automation.AutomationElement]::FromPoint((New-Object System.Windows.Point($point.x,$point.y)))
    $walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker
    for($up=0;$up -lt 4 -and $null -ne $hit;$up++){
      if([System.Windows.Automation.Automation]::Compare($hit,$el)){ return $true }
      $hit=$walker.GetParent($hit)
    }
  } catch {}
  return $false
}
function Invoke-NamedControl($el,[IntPtr]$top,[switch]$PatternsOnly){
  $facts=Get-ClickFacts $el
  # Ronda 24b (banco r23 u9): un contenedor (lista, arbol, cuadricula, tabla) sin Invoke ni SelectionItem no es algo que
  # se pulse: su clic iria por el puntero a su centro y elegiria lo que alli hubiera (una sugerencia que cambio la
  # busqueda de la persona). Se rechaza antes de pulsar nada.
  if(@($script:ContainerKinds) -contains [string]$facts.kind -and -not [bool]$facts.invoke -and -not [bool]$facts.select){ return @{ method='container' } }
  $hosts=Get-RenderHosts $top
  $owner=[uint32]0
  try { $owner=[uint32]$el.Current.ProcessId } catch { $owner=[uint32]0 }
  # Sin proceso conocido del elemento no hay superficie suya: nada se envia a ciegas.
  try { $facts.render=($owner -ne 0) -and [BaxyUiaWorkerNative]::HostsRender($hosts,$owner) } catch { $facts.render=$false }
  # Solo lo que puede recibir la lista de vias que eligen se relee (la superficie de render guarda su orden medido).
  if($facts.select -and -not $facts.toggle -and -not $facts.render -and @('ListItem','TreeItem','TabItem','DataItem') -contains [string]$facts.kind){
    $facts.selected=[bool](Test-Selected $el)
  }
  $methods=@(Select-ClickMethods $facts)
  # La pulsacion enviada a una barra (proxy MSAA) va tambien con -PatternsOnly: sin ella, su Invoke pulsaria con el raton.
  if($PatternsOnly){ $methods=@($methods | Where-Object { $script:PatternMethods -contains $_ -or ($_ -eq 'message' -and [bool]$facts.toolbarProxy) }) }
  $choosing=([bool]$facts.select -and -not [bool]$facts.toggle -and @('ListItem','TreeItem','TabItem','DataItem') -contains [string]$facts.kind -and -not [bool]$facts.selected)
  # Ronda 20b, palanca 7 (v3-52): en un marco cuyo Select marca la fila sin hacerla actual, elegirla no prueba nada; lo
  # prueba que el lugar cambie (el titulo o los nombres de la ventana). Sin ese cambio, la via siguiente.
  # Revision 2 (B3): con lo volatil aprendido en dos lecturas antes del Select.
  $placeBefore=$(if($choosing -and [bool]$facts.native -and $methods -contains 'message'){ Get-SteadyPlace $top } else { $null })
  # Ronda 24b (banco r23 s04): elegido no es llegado. Un nodo de arbol o una pestana que se elige es un lugar: en
  # cualquier marco y tambien por Invoke, el lugar se lee antes (dos lecturas, lo volatil aparte) y el recibo dice si se
  # movio (placeMoved). Elegido y quieto 600 ms: la via siguiente que pulsa de verdad (la pulsacion enviada a su
  # ventana), una vez, y su postread solo prueba con el lugar movido; sin esa via, el recibo lleva placeMoved=false.
  # Estabilizacion y5 (banco h1): un lugar elegido por Invoke y quieto recibe otra vez su Invoke, ahora sobre el elemento
  # ya elegido (lo abre), nunca la pulsacion enviada. Medido en el arbol Win32 del Explorador (redpc, 2026-10-11): 2 de
  # 10 Invoke eligieron el nodo sin navegar y el segundo Invoke navego las 2 veces (~120 ms); la pulsacion enviada a ese
  # arbol no abrio la carpeta en 3 de 3 usos en vivo (g1, h1) y en uno dejo la ventana en otro lugar («Galeria» por
  # «Documentos»). Un Toggle nunca llega aqui ($choosing).
  # Revision 1 (B2): toda pulsacion que elige un item lee el lugar y su recibo lleva placeMoved (los items de navegacion
  # de WinUI y de muchas ventanas Electron son ListItem); solo un nodo o una pestana recibe la segunda via (la pulsacion
  # enviada): una fila de lista elegida y quieta se queda con su unica pulsacion, y la mente decide si era un lugar.
  # Revision 2 (B1): en una ventana cuya lectura del lugar ya paso el tope no se mide (ni antes ni despues); la lectura
  # que lo pasa ahora no se repite despues de pulsar: el recibo va sin placeMoved y el clic cabe en su presupuesto.
  $steadyBefore=$null
  if($choosing){
    if($null -ne $placeBefore){ $steadyBefore=$placeBefore }
    elseif(-not (Test-PlaceTooDear $top)){
      $steadyBefore=Get-SteadyPlace $top
      if(Test-PlaceTooDear $top){ $steadyBefore=$null }
    }
  }
  $placeItem=(@($script:PlaceItemKinds) -contains [string]$facts.kind)
  $chosenUnmoved=$false
  $pattern=$null
  $legacyStep=''
  $renderStep=''
  $ways=@()
  # Revision 1 de la ronda 24b (B3): las vias van en un bloque propio (en el mismo ambito) para que toda salida de un lugar elegido lleve
  # placeMoved (abajo), cualquiera que sea la via que la dio.
  $done=. {
  foreach($method in $methods){
    if($method -eq 'invoke'){
      $ways+='invoke'
      $trace=$(if($choosing){ Get-InvokeTrace $el $top } else { $null })
      if(-not [BaxyUiaTimedPress]::InvokeWithin($el,$script:InvokeWaitMs)){ return @{ method='invoke'; blocked=$true; ways=$ways; selectable=$choosing } }
      if(-not $choosing -or (Wait-Chosen $el)){
        if($null -eq $steadyBefore){ return @{ method='invoke'; ways=$ways; selectable=$choosing } }
        if(Wait-PlaceMoved $steadyBefore $top){ return @{ method='invoke'; ways=$ways; selectable=$choosing; placeMoved=$true } }
        # Elegido sin moverse: un lugar recibe su Invoke otra vez (lo abre), una vez; Select ya no elige nada mas.
        if(-not $placeItem){ return @{ method='invoke'; ways=$ways; selectable=$choosing; placeMoved=$false } }
        $ways+='invoke'
        if(-not [BaxyUiaTimedPress]::InvokeWithin($el,$script:InvokeWaitMs)){ return @{ method='invoke'; blocked=$true; ways=$ways; selectable=$choosing } }
        return @{ method='invoke'; ways=$ways; selectable=$choosing; placeMoved=[bool](Wait-PlaceMoved $steadyBefore $top) }
      }
      if(Test-InvokeActedAlone $trace (Get-InvokeTrace $el $top)){ return @{ method='invoke'; ways=$ways; selectable=$choosing } }
    } elseif($method -eq 'select'){
      if($chosenUnmoved){ continue }
      $ways+='select'
      # Lo que la via anterior ya hizo (el elemento se fue al pulsarlo) es su recibo: nunca «no se pudo pulsar».
      try { Select-Element $el } catch { if($ways.Count -gt 1){ return @{ method=$ways[-2]; ways=@($ways[0..($ways.Count-2)]); selectable=$choosing } }; throw }
      # La ultima via no espera: su recibo lo da el postread (revision, hallazgo 7: 300 ms menos por clic).
      if(-not $choosing -or $methods[-1] -eq 'select' -or (Wait-Chosen $el)){
        # Palanca 7: elegida, pero en un marco que no la hace actual solo vale si el lugar se movio.
        # Revision 1 de r24b (B3): el lugar que ya se vio movido aqui lo dice el recibo, sin otra lectura.
        $moved=$(if($null -ne $placeBefore){ [bool](Test-PlaceMoved $placeBefore (Get-PlaceTrace $top)) } else { $false })
        if($moved){ return @{ method='select'; ways=$ways; selectable=$choosing; placeMoved=$true } }
        if($null -eq $placeBefore){
          # Ronda 24b: un lugar (nodo, pestana) elegido por Select y quieto pasa una vez a la via que pulsa de verdad.
          if($null -ne $steadyBefore -and $null -eq $placeBefore -and $methods[-1] -ne 'select'){
            if(Wait-PlaceMoved $steadyBefore $top){ return @{ method='select'; ways=$ways; selectable=$choosing; placeMoved=$true } }
            if($methods -contains 'message' -and $placeItem){ $chosenUnmoved=$true; continue }
            return @{ method='select'; ways=$ways; selectable=$choosing; placeMoved=$false }
          }
          return @{ method='select'; ways=$ways; selectable=$choosing }
        }
      }
    } elseif($method -eq 'toggle'){
      [void]$el.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)
      ([System.Windows.Automation.TogglePattern]$pattern).Toggle(); return @{ method='toggle' }
    } elseif($method -eq 'expand'){
      [void]$el.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$pattern)
      $ec=([System.Windows.Automation.ExpandCollapsePattern]$pattern)
      # Un menu o un desplegable se cierra cuando su ventana pierde la activacion: la red no devuelve este frente.
      try { [BaxyFrontKeeper]::Release() } catch {}
      if($ec.Current.ExpandCollapseState -eq [System.Windows.Automation.ExpandCollapseState]::Expanded){ $ec.Collapse() } else { $ec.Expand() }
      return @{ method='expand' }
    } elseif($method -eq 'target'){
      # Hasta que el texto llegue al campo por su valor, el campo es destino solo si toma el foco del teclado: sin el,
      # el texto siguiente iria al control que su ventana tenia enfocado. SetFocus del cliente UIA trae al frente una
      # ventana tapada (robo de foco), asi que solo se pide con la ventana ya al frente; detras, la siguiente via.
      if(Test-InFront $top){
        $focused=$false
        try { $el.SetFocus(); $focused=[bool]$el.Current.HasKeyboardFocus } catch {}
        if($focused){ return @{ method='target'; focused=$true } }
      }
    } elseif($method -eq 'render'){
      # La pulsacion enviada a la superficie de render bajo el punto del control: sin frente ni cursor, y solo si la
      # pagina tiene ese control en el punto. Un campo solo es destino si tomo el foco del teclado (releido hasta
      # 400 ms); si no, la siguiente via, como con «target». Un campo que ya tenia el foco es ya el destino: no se pulsa
      # (su foco no probaria la pulsacion, y el clic dejaria el cursor de texto en medio de lo escrito).
      $field=(@('Edit','Document') -contains [string]$facts.kind -and $facts.value)
      if($field){
        $already=$false
        try { $already=[bool]$el.Current.HasKeyboardFocus } catch { $already=$false }
        if($already){ return @{ method='target'; focused=$true; via='prefocused' } }
      }
      $point=Get-PressPoint $el
      $renderStep='nopoint'
      if($null -ne $point){ try { $renderStep=[string](Send-RenderPress $hosts $point.x $point.y $owner $el @()) } catch { $renderStep='failed' } }
      if($renderStep -eq 'posted'){
        if(-not $field){ return @{ method='render' } }
        $focused=$false
        for($look=0;$look -lt 8 -and -not $focused;$look++){
          Start-Sleep -Milliseconds 50
          try { $focused=[bool]$el.Current.HasKeyboardFocus } catch { $focused=$false }
        }
        if($focused){ return @{ method='target'; focused=$true; via='render' } }
        $renderStep='unfocused'
      }
    } elseif($method -eq 'legacy'){
      $action=''
      # A control that is its own window: its own accessible object first; any other, through the COM client.
      $own=0
      try { $own=[int]$el.Current.NativeWindowHandle } catch { $own=0 }
      if($own -ne 0){ try { $action=[BaxyUiaWorkerNative]::WindowDefault([IntPtr]$own) } catch { $action='' } }
      $windowStep=$(if($own -ne 0){ [string][BaxyUiaWorkerNative]::LegacyStep } else { '' })
      if(([string]$action).Length -eq 0){
        try { $action=[BaxyUiaWorkerNative]::LegacyDefault($top,[int[]]$el.GetRuntimeId()) } catch { $action='' }
      }
      $legacyStep=(($windowStep+' '+[string][BaxyUiaWorkerNative]::LegacyStep).Trim())
      if(([string]$action).Length -gt 0){ return @{ method='legacy' } }
    } elseif($method -eq 'message' -and [bool]$facts.toolbarProxy){
      # r20b palanca 4: la barra en el punto y su propia prueba de impacto dan este boton: la pulsacion va como mensaje.
      # Otra ventana u otro boton en el punto: nada se envia, ni por Invoke (su clic fisico caeria en lo que hay ahi).
      # Sin la barra en el punto o sin respuesta de su prueba de impacto: la siguiente via, como antes.
      $point=Get-PressPoint $el
      $barStep='nopoint'
      if($null -ne $point){ try { $barStep=[string][BaxyUiaWorkerNative]::ToolbarPress($top,$point.x,$point.y,[IntPtr][long]$facts.toolbarWindow,[int]$facts.toolbarChild) } catch { $barStep='failed' } }
      if($barStep -eq 'posted'){ $ways+='message'; return @{ method='message'; ways=$ways } }
      if($barStep -eq 'other'){ return $null }
    } elseif($method -eq 'message'){
      $point=Get-PressPoint $el
      # Una fila que se elige: solo si en su punto esta la ventana que la contiene (revision, hallazgo 2).
      # Fuera de una ventana Win32 clasica (palanca 7: Qt), solo si lo que UIA tiene en ese punto es el elemento.
      if($null -ne $point -and [bool]$facts.native -and -not [bool]$facts.classic -and -not (Test-PointIsElement $el $point)){ $point=$null }
      $posted=$(if($choosing){ $null -ne $point -and [BaxyUiaWorkerNative]::PostClick($top,$point.x,$point.y,(Get-HolderWindow $el)) } else { $null -ne $point -and [BaxyUiaWorkerNative]::PostClick($top,$point.x,$point.y) })
      # Revision de la ronda 20b (hallazgo 3): si el Select ya se juzgo sin valor (el lugar no se movio), la marca que
      # dejo no prueba nada: el postread lo sabe por placeBefore y solo acepta el lugar movido.
      # Ronda 24b: tras un lugar ya elegido y quieto, la pulsacion enviada tambien se prueba solo con el lugar movido; si
      # no se mueve, el recibo dice elegido sin llegar (chosenAlready: la marca es de la via anterior, cierta).
      $unproved=$(if($null -ne $placeBefore){ $placeBefore } elseif($chosenUnmoved){ $steadyBefore } else { $null })
      if($posted){ $ways+='message'; return @{ method='message'; ways=$ways; selectable=$choosing; placeBefore=$unproved; chosenAlready=$chosenUnmoved } }
      if($chosenUnmoved){ return @{ method=$ways[-1]; ways=$ways; selectable=$choosing; placeMoved=$false } }
      if($choosing -and $ways.Count -gt 0){ return @{ method=$ways[-1]; ways=$ways; selectable=$choosing; placeBefore=$unproved } }
    } elseif($method -eq 'pointer'){
      $point=Get-PressPoint $el
      if($null -eq $point){ return $null }
      return @{ method='pointer'; point=$point; rect=(Get-CurrentRect $el); legacyStep=$legacyStep; renderStep=$renderStep }
    }
  }
  return $null
  }
  # Revision 1 de la ronda 24b (B3): un lugar (nodo, pestana) elegido lleva siempre placeMoved, verdadero o falso, por
  # la via que sea (solo Select en WPF o WinUI, el Select de Qt que movio el lugar, la pulsacion en la superficie de
  # render, el Invoke que actuo solo): sin la clave, la mente no sabe si llego. Lo que el postread prueba con el lugar
  # (placeBefore) lo dice alli; una pulsacion bloqueada o por el puntero aun no se dio: el postread lo lee con
  # steadyBefore.
  if($null -ne $steadyBefore -and $done -is [hashtable] -and $null -eq $done.placeMoved -and $null -eq $done.placeBefore -and [string]$done.method -ne 'container'){
    if([bool]$done.blocked -or [string]$done.method -eq 'pointer'){ $done.steadyBefore=$steadyBefore; $done.steadyTop=$top }
    else { $done.placeMoved=[bool](Wait-PlaceMoved $steadyBefore $top) }
  }
  return $done
}
# Goal v3 B3 (ordenes en menus cerrados): el control de la vista pulsado de otra manera que el clic, solo por su
# identidad y nunca con el puntero ni el teclado. open: solo su ExpandCollapse (la flecha de un boton dividido abre su
# lista; su Invoke, primero en Select-ClickMethods, abria otra pestana: v3-37); menu: su menu contextual (el del propio
# elemento por el cliente COM; si no, WM_CONTEXTMENU a su propia ventana Win32); double: el doble clic enviado como
# mensaje a la superficie de render o a la ventana Win32 clasica del punto. Devuelve method y, cuando la lista o el menu
# se leen abiertos, opened; error si el control no tiene esa via (nada se envio).
# Un menu de nivel superior del proceso cuenta solo junto al control (revision B3, hallazgo 8: en un proceso que aloja
# tambien la barra de tareas o Inicio, un menu que la persona abre alli en esa espera no es el del control).
function Get-OpenMenus($root,[int]$process,$el){
  $count=0
  $menu=New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty,[System.Windows.Automation.ControlType]::Menu)
  $box=$null
  try { $box=$el.Current.BoundingRectangle } catch { $box=$null }
  try {
    $own=New-Object System.Windows.Automation.PropertyCondition($AE::ProcessIdProperty,$process)
    foreach($top in @($AE::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,(New-Object System.Windows.Automation.AndCondition($menu,$own))))){
      $r=$null
      try { $r=$top.Current.BoundingRectangle } catch { $r=$null }
      if($null -eq $box -or $box.IsEmpty -or $null -eq $r -or $r.IsEmpty){ continue }
      if($r.Right+64 -ge $box.Left -and $r.Left-64 -le $box.Right -and $r.Bottom+64 -ge $box.Top -and $r.Top-64 -le $box.Bottom){ $count++ }
    }
  } catch {}
  try { $count+=@($root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$menu)).Count } catch {}
  return $count
}
# La ventana Win32 que contiene al elemento: la suya, o la del antecesor mas cercano que tenga una.
function Get-HolderWindow($el){
  $walker=[System.Windows.Automation.TreeWalker]::RawViewWalker
  $node=$el
  for($up=0;$up -lt 16 -and $null -ne $node;$up++){
    $own=0
    try { $own=[int]$node.Current.NativeWindowHandle } catch { $own=0 }
    if($own -ne 0){ return [IntPtr]$own }
    try { $node=$walker.GetParent($node) } catch { $node=$null }
  }
  return [IntPtr]::Zero
}
# Ronda 20b, palanca 6, revision 2 (hallazgo 3): las ventanas propias de los popups abiertos junto al control: un menu
# (ControlType Menu) o el anfitrion de un popup (su clase de marco dice Popup) de nivel superior del mismo proceso y a
# menos de 64 px del control (como Get-OpenMenus: nunca un menu que la persona abre en otra parte del proceso), o un menu
# dentro de la ventana. Solo la ventana que contiene a cada uno y nunca la ventana de la mision misma ni su raiz: el
# Escape nunca va al cuerpo de la ventana de la persona.
function Get-BornPopups($root,$el,[IntPtr]$top){
  $found=New-Object System.Collections.Generic.List[long]
  $process=0
  try { $process=[int]$el.Current.ProcessId } catch { $process=0 }
  if($process -eq 0){ return @() }
  $box=$null
  try { $box=$el.Current.BoundingRectangle } catch { $box=$null }
  $frame=[BaxyUiaWorkerNative]::GetAncestor($top,2)
  $menuType=[System.Windows.Automation.ControlType]::Menu
  $candidates=@()
  try {
    $own=New-Object System.Windows.Automation.PropertyCondition($AE::ProcessIdProperty,$process)
    foreach($shown in @($AE::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$own))){
      $isMenu=$false; $class=''
      try { $isMenu=$shown.Current.ControlType -eq $menuType; $class=[string]$shown.Current.ClassName } catch { continue }
      if(-not $isMenu -and $class -notmatch 'Popup'){ continue }
      $r=$null
      try { $r=$shown.Current.BoundingRectangle } catch { $r=$null }
      if($null -eq $box -or $box.IsEmpty -or $null -eq $r -or $r.IsEmpty){ continue }
      if($r.Right+64 -ge $box.Left -and $r.Left-64 -le $box.Right -and $r.Bottom+64 -ge $box.Top -and $r.Top-64 -le $box.Bottom){ $candidates+=$shown }
    }
  } catch {}
  try { $candidates+=@($root.FindAll([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty,$menuType)))) } catch {}
  foreach($candidate in $candidates){
    $holder=Get-HolderWindow $candidate
    if($holder -eq [IntPtr]::Zero -or $holder -eq $top -or $holder -eq $frame -or -not [BaxyUiaWorkerNative]::IsWindowVisible($holder)){ continue }
    if(-not $found.Contains($holder.ToInt64())){ $found.Add($holder.ToInt64()) }
  }
  return @($found | ForEach-Object { [IntPtr]$_ })
}
function Invoke-MannerControl($el,$root,[IntPtr]$top,[string]$manner){
  $pattern=$null
  if($manner -eq 'open'){
    if(-not $el.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$pattern)){ return @{ error='visible_control_cannot_open' } }
    $ec=([System.Windows.Automation.ExpandCollapsePattern]$pattern)
    $expanded=[System.Windows.Automation.ExpandCollapseState]::Expanded
    # Revision B3, hallazgo 6: lo que ya estaba abierto no lo abre este paso; nada se envia y no hay prueba que dar.
    if($ec.Current.ExpandCollapseState -eq $expanded){ return @{ error='visible_control_already_open' } }
    # Lo que se abre se cierra cuando su ventana pierde la activacion: la red no devuelve este frente (como «expand»).
    try { [BaxyFrontKeeper]::Release() } catch {}
    # Revision de fable/cu-v3-recibo-del-clic-por-estado (hallazgo 7): abrir no elige. Elegir un elemento de arbol navega
    # (un explorador de archivos, un editor del registro) y v3-46 no lo necesitaba: «Componentes» ya estaba elegido.
    $ec.Expand()
    for($look=0;$look -lt 8;$look++){
      if($ec.Current.ExpandCollapseState -eq $expanded){ return @{ method='expand'; opened=$true } }
      Start-Sleep -Milliseconds 50
    }
    return @{ method='expand' }
  }
  # Ronda 20b, palanca 6 (revision, hallazgo 1, v3-40 b): la lista que la mision abrio y dejo abierta al no llegar se
  # cierra por su propio ExpandCollapse, sin puntero ni teclado. No suelta la red: el frente vuelve a la persona como
  # tras cualquier patron que actuo (KeptMethods). Lo que ya no estaba abierto no se toca.
  # Revision 2 (hallazgo 3): sin ExpandCollapse abierto (el menu contextual de una pestana, el flyout de un boton dividido
  # abierto por su flecha con el puntero), el popup que sigue abierto junto al control se cierra con Escape enviado como
  # mensaje a su propia ventana (Get-BornPopups), nunca a la ventana de la persona ni por el teclado. Sin popup abierto
  # no se envia nada (visible_control_not_open); cerrado es solo el que se lee cerrado despues.
  # Revision 3 (hallazgo 1): 'collapse' es solo el ExpandCollapse de la lista que la mision abrio, nunca el de una rama
  # de arbol (TreeItem: donde navega la persona); 'dismiss' es solo el Escape al popup nacido en la mision y nunca toca
  # el ExpandCollapse del control (una rama o una lista de la persona junto al menu quedan como estaban).
  if($manner -eq 'collapse'){
    $expanded=[System.Windows.Automation.ExpandCollapseState]::Expanded
    $treeItem=$false
    try { $treeItem=$el.Current.ControlType -eq [System.Windows.Automation.ControlType]::TreeItem } catch { $treeItem=$true }
    if($treeItem -or -not $el.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$pattern)){
      return @{ error='visible_control_not_open' }
    }
    $ec=([System.Windows.Automation.ExpandCollapsePattern]$pattern)
    if($ec.Current.ExpandCollapseState -ne $expanded){ return @{ error='visible_control_not_open' } }
    $ec.Collapse()
    for($look=0;$look -lt 8;$look++){
      if($ec.Current.ExpandCollapseState -ne $expanded){ return @{ method='collapse'; closed=$true } }
      Start-Sleep -Milliseconds 50
    }
    return @{ method='collapse' }
  }
  if($manner -eq 'dismiss'){
    $popups=@(Get-BornPopups $root $el $top)
    if($popups.Count -eq 0){ return @{ error='visible_control_not_open' } }
    $sent=$false
    foreach($popup in $popups){ if([BaxyUiaWorkerNative]::PostEscape($popup)){ $sent=$true } }
    if(-not $sent){ return @{ error='visible_control_not_open' } }
    for($look=0;$look -lt 10;$look++){
      Start-Sleep -Milliseconds 60
      if(@(Get-BornPopups $root $el $top).Count -eq 0){ return @{ method='escape'; closed=$true } }
    }
    return @{ method='escape' }
  }
  $point=Get-PressPoint $el
  if($manner -eq 'menu'){
    $process=0
    try { $process=[int]$el.Current.ProcessId } catch { $process=0 }
    $before=Get-OpenMenus $root $process $el
    try { [BaxyFrontKeeper]::Release() } catch {}
    $shown=$false
    try { $shown=[BaxyUiaWorkerNative]::ShowContextMenu($top,[int[]]$el.GetRuntimeId()) } catch { $shown=$false }
    $step=[string][BaxyUiaWorkerNative]::LegacyStep
    if(-not $shown){
      $own=0
      try { $own=[int]$el.Current.NativeWindowHandle } catch { $own=0 }
      if($own -eq 0 -or $null -eq $point -or -not [BaxyUiaWorkerNative]::PostContextMenu([IntPtr]$own,$point.x,$point.y)){
        return @{ error='visible_control_no_context_menu'; legacyStep=$step }
      }
      $step='message'
    }
    for($look=0;$look -lt 10;$look++){
      Start-Sleep -Milliseconds 60
      if((Get-OpenMenus $root $process $el) -gt $before){ return @{ method='contextmenu'; opened=$true; legacyStep=$step } }
    }
    return @{ method='contextmenu'; legacyStep=$step }
  }
  if($manner -eq 'double'){
    $kind=''
    try { $kind=$el.Current.ControlType.ProgrammaticName -replace '^ControlType\.','' } catch { $kind='' }
    # Revision B3, hallazgo 2: el doble clic solo va a lo que se abre con el (un elemento de una lista, una cuadricula o
    # un arbol), a una pestana (elegirla dos veces) o a un documento (selecciona una palabra). En un boton, un enlace, un
    # elemento de menu o un boton dividido son dos activaciones (dos BN_CLICKED, dos eventos click): nada se envia. La
    # mente aplica la misma lista (_DOUBLE_KINDS).
    if(@('ListItem','DataItem','TreeItem','TabItem','Document') -notcontains $kind){ return @{ error='visible_control_no_double_click' } }
    if($null -eq $point){ return @{ error='visible_control_no_double_click' } }
    $owner=[uint32]0
    try { $owner=[uint32]$el.Current.ProcessId } catch { $owner=[uint32]0 }
    $surface=[IntPtr]::Zero
    if($owner -ne 0){ try { $surface=[BaxyUiaWorkerNative]::RenderAt((Get-RenderHosts $top),$point.x,$point.y,$owner) } catch { $surface=[IntPtr]::Zero } }
    if($surface -ne [IntPtr]::Zero){
      # Como el clic en la superficie de render: solo si lo que la pagina tiene en el punto es el elemento.
      $chain=@()
      if([BaxyUiaWorkerNative]::SameDpi($surface)){ $chain=@([BaxyUiaWorkerNative]::HitChain($surface,$point.x,$point.y)) }
      if($chain.Count -gt 0 -and (Test-HitIsElement $chain $el) -and [BaxyUiaWorkerNative]::PostDoubleAt($surface,$point.x,$point.y)){ return @{ method='render' } }
      return @{ error='visible_control_no_double_click' }
    }
    $classic=$false
    try { $classic=@('Win32','WinForm') -contains [string]$el.Current.FrameworkId } catch { $classic=$false }
    if($classic -and [BaxyUiaWorkerNative]::PostDoubleClick($top,$point.x,$point.y,(Get-HolderWindow $el))){ return @{ method='message' } }
    return @{ error='visible_control_no_double_click' }
  }
  return @{ error='visible_click_argument_invalid' }
}
function Test-Selected($el){
  try {
    $pattern=$null
    if($el.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern)){
      return ([System.Windows.Automation.SelectionItemPattern]$pattern).Current.IsSelected
    }
  } catch [System.Windows.Automation.ElementNotAvailableException] {}
  return $false
}
function Get-Toggle($el){
  try {
    $pattern=$null
    if($el.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)){
      return [string]([System.Windows.Automation.TogglePattern]$pattern).Current.ToggleState
    }
  } catch [System.Windows.Automation.ElementNotAvailableException] {}
  return $null
}
# Cada propiedad leida de un elemento es una llamada entre procesos; con un
# CacheRequest el arbol llega con sus propiedades y patrones en una sola
# (medido: VS Code 154 controles 2,2 s -> menos de 1 s).
$script:Cache=New-Object System.Windows.Automation.CacheRequest
foreach($prop in @($AE::NameProperty,$AE::ControlTypeProperty,$AE::IsOffscreenProperty,$AE::BoundingRectangleProperty,
                   $AE::HasKeyboardFocusProperty,$AE::IsPasswordProperty,$AE::IsEnabledProperty,$AE::RuntimeIdProperty,
                   $AE::ItemTypeProperty,$AE::HelpTextProperty,$AE::AutomationIdProperty,$AE::LabeledByProperty,
                   $AE::ClassNameProperty,$AE::AcceleratorKeyProperty,$AE::AccessKeyProperty)){ $script:Cache.Add($prop) }
foreach($pat in @([System.Windows.Automation.TogglePattern]::Pattern,[System.Windows.Automation.SelectionItemPattern]::Pattern,
                  [System.Windows.Automation.ExpandCollapsePattern]::Pattern,[System.Windows.Automation.ValuePattern]::Pattern,
                  [System.Windows.Automation.RangeValuePattern]::Pattern)){ $script:Cache.Add($pat) }
foreach($pp in @([System.Windows.Automation.TogglePattern]::ToggleStateProperty,[System.Windows.Automation.SelectionItemPattern]::IsSelectedProperty,
                 [System.Windows.Automation.ExpandCollapsePattern]::ExpandCollapseStateProperty,[System.Windows.Automation.ValuePattern]::ValueProperty,
                 [System.Windows.Automation.ValuePattern]::IsReadOnlyProperty,[System.Windows.Automation.RangeValuePattern]::ValueProperty)){ $script:Cache.Add($pp) }
$script:Cache.AutomationElementMode=[System.Windows.Automation.AutomationElementMode]::Full
$script:Cache.TreeScope=[System.Windows.Automation.TreeScope]::Element
# Los hijos de un nodo en la vista de control. Un navegador (medido en Opera GX
# tras abrir una pestana nueva) deja un primer hijo muerto: GetFirstChild falla
# alli y FindAll desde la ventana no encuentra nada, mientras los hijos vivos
# siguen alcanzandose desde el ultimo hacia atras (como UserBrowserScripts).
function Get-Children($walker,$node){
  $kids=New-Object System.Collections.Generic.List[object]
  try {
    $child=$walker.GetFirstChild($node,$script:Cache)
    while($null -ne $child -and $kids.Count -lt 400){ $kids.Add($child); $child=$walker.GetNextSibling($child,$script:Cache) }
    return ,$kids
  } catch {}
  $kids.Clear()
  try {
    $child=$walker.GetLastChild($node,$script:Cache)
    while($null -ne $child -and $kids.Count -lt 400){ $kids.Insert(0,$child); $child=$walker.GetPreviousSibling($child,$script:Cache) }
  } catch {}
  return ,$kids
}
# El arbol recorrido nodo a nodo, acotado, cuando FindAll no devuelve nada.
function Get-WalkedDescendants($root){
  $walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker
  $found=New-Object System.Collections.Generic.List[object]
  $queue=New-Object System.Collections.Generic.Queue[object]
  $queue.Enqueue(@($root,0))
  $visited=0
  while($queue.Count -gt 0 -and $visited -lt 2500){
    $pair=$queue.Dequeue(); $visited++
    foreach($child in (Get-Children $walker $pair[0])){
      try { if($child.Cached.IsEnabled){ $found.Add($child) } } catch {}
      if($pair[1] -lt 26){ $queue.Enqueue(@($child,($pair[1]+1))) }
    }
  }
  return ,$found
}
function Get-Descendants($root){
  $enabled=New-Object System.Windows.Automation.PropertyCondition($AE::IsEnabledProperty,$true)
  $activated=$script:Cache.Activate()
  try {
    $all=$null
    try { $all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$enabled) } catch {}
    if($null -eq $all -or $all.Count -eq 0){
      Start-Sleep -Milliseconds 400
      try { $all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$enabled) } catch { $all=$null }
    }
    if($null -eq $all -or $all.Count -eq 0){ $all=Get-WalkedDescendants $root }
  } finally { $activated.Dispose() }
  return $all
}
# El rotulo de un campo sin nombre: el Text visible mas cercano que termina a su izquierda en su misma franja o que
# queda encima solapando su ancho, a no mas de 120 px (un rotulo esta pegado a su campo). Vacio si no hay ninguno.
function Get-NearLabel($field,$all){
  $box=$null
  try { $box=$field.Cached.BoundingRectangle } catch { return '' }
  if($null -eq $box -or $box.IsEmpty){ return '' }
  $best='';$distance=121.0
  foreach($other in $all){
    try {
      if($other.Cached.ControlType.ProgrammaticName -ne 'ControlType.Text' -or $other.Cached.IsOffscreen){ continue }
      $text=Get-Name $other
      if($text.Length -eq 0 -or $text.Length -gt 40){ continue }
      $r=$other.Cached.BoundingRectangle
      if($r.IsEmpty){ continue }
      $gap=-1.0
      $middle=$r.Y+$r.Height/2
      if($r.Right -le $box.Left+2 -and $middle -ge $box.Top -and $middle -le $box.Bottom){ $gap=$box.Left-$r.Right }
      elseif($r.Bottom -le $box.Top+2 -and $r.Right -gt $box.Left -and $r.Left -lt $box.Right){ $gap=$box.Top-$r.Bottom }
      if($gap -ge -2 -and $gap -lt $distance){ $distance=$gap; $best=$text }
    } catch {}
  }
  return ($best -replace '[:：]\s*$','').Trim()
}
# La vista pide al arbol solo lo que se ve (r13a, causa 4: el Visor de eventos tiene 2 973 elementos y su FindAll
# tardaba 15-17 s; Servicios, mas de 40 s). La condicion IsEnabled y no IsOffscreen se evalua dentro de FindAll, nodo a
# nodo y sin podar: un hijo que se ve bajo un padre marcado fuera de pantalla (Chromium marca asi filas de un cliente de mensajeria cuyo
# boton se ve) sigue entrando, y el conjunto es el mismo que daba el arbol entero menos lo que no se ve, en el mismo
# orden. Lo que deja de costar es lo que no se ve: no viaja entre procesos ni se lee con sus propiedades (medido en
# caliente: VS Code 1 631-1 959 -> 249-257 ms con 4 284 nodos, 242 visibles; Edge 359-470 -> 148-161 ms). Las filas de
# una lista larga que no se ven son de esas.
$script:ShownCondition=New-Object System.Windows.Automation.AndCondition(@(
  (New-Object System.Windows.Automation.PropertyCondition($AE::IsEnabledProperty,$true)),
  (New-Object System.Windows.Automation.PropertyCondition($AE::IsOffscreenProperty,$false))))
# Ronda 25 (latencia): la vista que lista los deshabilitados que se ven los trae en este mismo recorrido, con la condicion
# sin IsEnabled ($script:WithDimmed); Do-View los aparta. Las demas lecturas piden solo los habilitados.
$script:OnScreenCondition=New-Object System.Windows.Automation.PropertyCondition($AE::IsOffscreenProperty,$false)
$script:WithDimmed=$false
# La excepcion es una lista larga que es una ventana propia (una lista o un arbol clasico de Win32): sus filas las sirve
# un proxy fila a fila, y hasta preguntar si una fila se ve cuesta una llamada entre procesos por fila y por celda
# (medido con una lista clasica de 3 000 filas y 5 columnas: el arbol entero mas de 90 s; solo lo que se ve, 20-22 s).
# De esas listas se leen solo las filas que se ven: desde la primera, las de arriba se saltan con una cache minima, y
# la lectura acaba en la primera fila que ya no se ve tras las que se ven (en una lista asi IsOffscreen es la posicion
# de la fila). Se leen como mucho $script:RowsRead (cada una con sus celdas cuesta 60-70 ms en esa lista); las demas
# que se ven solo se cuentan en controlCount. El resto del arbol sigue llegando con una llamada por subarbol.
$script:RowHolderTypes=@('ControlType.List','ControlType.DataGrid','ControlType.Table','ControlType.Tree')
$script:RowKinds=@('ControlType.ListItem','ControlType.DataItem','ControlType.TreeItem')
$script:LongList=60
$script:RowsRead=20
$script:RowsSeconds=2
$script:ShownUnread=0
# Ronda 21 (pasada r18 v3-63, v3-65, v3-25): el recorrido de lo visible tiene plazo propio, por debajo del que el host
# espera al worker (20 s una vista, 15 s un clic): pasado el plazo devuelve lo leido hasta ahi (partial) en vez de dejar
# que lo maten. La busqueda por nombre o por identidad recorre lo visible con su plazo y lee todas las filas que se ven.
$script:ViewSeconds=12
$script:LookupSeconds=10
$script:Until=[DateTime]::MaxValue
$script:Partial=$false
$script:AllRows=$false
$script:LookupPartial=$false
function Test-PastDeadline(){
  if([DateTime]::UtcNow -gt $script:Until){ $script:Partial=$true; return $true }
  return $false
}
$script:RowCache=New-Object System.Windows.Automation.CacheRequest
foreach($prop in @($AE::ControlTypeProperty,$AE::IsOffscreenProperty,$AE::RuntimeIdProperty,
                   [System.Windows.Automation.ExpandCollapsePattern]::ExpandCollapseStateProperty)){ $script:RowCache.Add($prop) }
$script:RowCache.Add([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
$script:RowCache.TreeScope=[System.Windows.Automation.TreeScope]::Element
# Sus filas, o $script:LongList+1 si son mas (basta saber que pasa del umbral).
function Get-RowCount($list){
  try {
    $pattern=$null
    if($list.TryGetCurrentPattern([System.Windows.Automation.GridPattern]::Pattern,[ref]$pattern)){
      $rows=([System.Windows.Automation.GridPattern]$pattern).Current.RowCount
      if($rows -gt 0){ return $rows }
    }
  } catch {}
  $count=0
  try {
    $walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker
    $row=$walker.GetFirstChild($list,$script:RowCache)
    while($null -ne $row -and $count -le $script:LongList){ $count++; $row=$walker.GetNextSibling($row,$script:RowCache) }
  } catch {}
  return $count
}
# Las listas largas que son ventanas propias dentro de la ventana, por su RuntimeId.
function Get-LongLists([long]$hwnd){
  $lists=@{}
  foreach($child in [BaxyUiaWorkerNative]::VisibleChildWindows([IntPtr]$hwnd,300)){
    try {
      $el=[System.Windows.Automation.AutomationElement]::FromHandle($child).GetUpdatedCache($script:RowCache)
      if($script:RowHolderTypes -contains [string]$el.Cached.ControlType.ProgrammaticName -and (Get-RowCount $el) -gt $script:LongList){
        $id=Get-Id $el
        if($id.Length -gt 0){ $lists[$id]=$el }
      }
    } catch {}
  }
  return $lists
}
function Test-Walked($el){
  try { return (($script:WithDimmed -or $el.Cached.IsEnabled) -and -not $el.Cached.IsOffscreen) } catch { return $false }
}
function Get-WalkCondition(){ if($script:WithDimmed){ return $script:OnScreenCondition }; return $script:ShownCondition }
function Add-ShownSubtree($node,$out){
  $activated=$script:Cache.Activate()
  try {
    $found=$null
    try { $found=$node.FindAll([System.Windows.Automation.TreeScope]::Descendants,(Get-WalkCondition)) } catch { $found=$null }
    if($null -ne $found){ foreach($el in $found){ $out.Add($el) } }
  } finally { $activated.Dispose() }
}
# Las filas que se ven de una lista larga, cada una con lo que se ve dentro, en orden.
function Add-ShownRows($list,$out){
  $walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker
  $until=[DateTime]::UtcNow.AddSeconds($script:RowsSeconds)
  if($script:AllRows -or $until -gt $script:Until){ $until=$script:Until }
  $rowsRead=$(if($script:AllRows){ [int]::MaxValue } else { $script:RowsRead })
  $seen=$false;$read=0
  $row=$null
  try { $row=$walker.GetFirstChild($list,$script:RowCache) } catch { $row=$null }
  while($null -ne $row -and -not (Test-PastDeadline)){
    if([DateTime]::UtcNow -gt $until){ break }
    try {
      $isRow=$script:RowKinds -contains [string]$row.Cached.ControlType.ProgrammaticName
      if(-not $isRow){
        # Lo que no es fila (la cabecera, la barra de desplazamiento) se lee entero y no marca donde empiezan las filas.
        if(-not $row.Cached.IsOffscreen){ $full=$row.GetUpdatedCache($script:Cache); if(Test-Walked $full){ $out.Add($full) } }
        Add-ShownSubtree $row $out
      } elseif(-not $row.Cached.IsOffscreen){
        $seen=$true
        # Pasado el tope, una fila que se ve solo se cuenta: sigue siendo un control visible (controlCount) y el clic
        # por rotulo la encuentra, pero leerla con sus celdas cuesta lo que una lectura entera.
        if($read -ge $rowsRead){ $script:ShownUnread++ }
        else {
          $read++
          $full=$row.GetUpdatedCache($script:Cache)
          if(Test-Walked $full){ $out.Add($full) }
          Add-ShownSubtree $row $out
        }
      } elseif($seen){ break }
      else {
        # Una rama desplegada de un arbol puede asomar por debajo de su fila, que ya quedo arriba.
        $state=$row.GetCachedPropertyValue([System.Windows.Automation.ExpandCollapsePattern]::ExpandCollapseStateProperty)
        if($state -is [System.Windows.Automation.ExpandCollapseState] -and $state -ne [System.Windows.Automation.ExpandCollapseState]::Collapsed -and $state -ne [System.Windows.Automation.ExpandCollapseState]::LeafNode){ Add-ShownSubtree $row $out }
      }
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
    try { $row=$walker.GetNextSibling($row,$script:RowCache) } catch { $row=$null }
  }
}
# Lo que se ve bajo $node, en orden de documento, sin entrar fila a fila en las listas largas: un hijo que no lleva
# ninguna dentro llega entero con una llamada; uno que la lleva se abre un nivel mas.
function Add-ShownAround($node,$out,$lists,$paths,[int]$depth){
  $kids=$null
  $activated=$script:Cache.Activate()
  try { $kids=$node.FindAll([System.Windows.Automation.TreeScope]::Children,[System.Windows.Automation.Condition]::TrueCondition) } catch { $kids=$null }
  finally { $activated.Dispose() }
  if($null -eq $kids -or $kids.Count -eq 0){ $kids=Get-Children ([System.Windows.Automation.TreeWalker]::ControlViewWalker) $node }
  foreach($kid in $kids){
    if(Test-PastDeadline){ break }
    $id=Get-Id $kid
    if(Test-Walked $kid){ $out.Add($kid) }
    if($lists.ContainsKey($id)){ Add-ShownRows $kid $out }
    elseif($paths.ContainsKey($id) -and $depth -lt 40){ Add-ShownAround $kid $out $lists $paths ($depth+1) }
    else { Add-ShownSubtree $kid $out }
  }
}
# Los descendientes que se ven y estan habilitados. Sin ninguno, la ventana puede no mostrar nada (minimizada: se
# devuelve vacio) o no tener aun arbol o un primer hijo muerto (Opera GX): entonces Get-Descendants, con su segunda
# mirada y su recorrido nodo a nodo, igual que antes. Con $dimmed trae tambien los deshabilitados que se ven.
function Get-ShownDescendants($root,[long]$hwnd=0,[double]$seconds=0,[bool]$dimmed=$false){
  $script:WithDimmed=$dimmed
  $script:ShownUnread=0
  $script:Partial=$false
  if($seconds -le 0){ $seconds=$script:ViewSeconds }
  $script:Until=[DateTime]::UtcNow.AddSeconds($seconds)
  $lists=@{}
  if($hwnd -ne 0){ $lists=Get-LongLists $hwnd }
  if($lists.Count -gt 0){
    # Los antecesores de cada lista larga hasta la raiz: por ellos se baja nivel a nivel.
    $paths=@{}
    $walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker
    foreach($list in @($lists.Values)){
      $chain=@();$up=$null
      try { $up=$walker.GetParent($list) } catch { $up=$null }
      for($steps=0;$null -ne $up -and $steps -lt 40;$steps++){
        if([System.Windows.Automation.Automation]::Compare($up,$root)){ foreach($k in $chain){ $paths[$k]=$true }; break }
        $chain+=@(Get-Id $up)
        try { $up=$walker.GetParent($up) } catch { $up=$null }
      }
    }
    $out=New-Object System.Collections.Generic.List[object]
    Add-ShownAround $root $out $lists $paths 0
    if($out.Count -gt 0){ return ,$out }
  }
  $activated=$script:Cache.Activate()
  try {
    $shown=$null
    try { $shown=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,(Get-WalkCondition)) } catch { $shown=$null }
    if($null -ne $shown -and $shown.Count -gt 0){ return $shown }
    if($null -ne $shown){
      $any=$null
      try { $any=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition($AE::IsEnabledProperty,$true))) } catch { $any=$null }
      if($null -ne $any){ return $shown }
    }
  } finally { $activated.Dispose() }
  return (Get-Descendants $root)
}
# Palanca 7 (v3-49): cada entrada del HMENU es un MenuItem de la vista con su ruta («Ver › Detalles») y su atajo; su
# identidad «hmenu.<id>» la pulsa por WM_COMMAND. Un submenu vacio en la lectura estatica lo llena la aplicacion al
# abrirlo: va con el estado fills-on-open y sin identidad (nada lo pulsa asi).
# Revision de la ronda 20b (hallazgo 2): la marca y el deshabilitado leidos sin abrir el menu no se publican. Muchas
# aplicaciones los ponen solo al abrirlo (WM_INITMENUPOPUP: MFC con ON_UPDATE_COMMAND_UI, un gestor de archivos que marca
# Ver › Detalles o Lista): leidos en estatico son los de la ultima vez que se abrio, nunca el estado de ahora.
$script:MenuEntriesMax=80
function ConvertTo-MenuViewEntries($menuEntries){
  $out=@()
  foreach($menu in @($menuEntries)){
    if($null -eq $menu -or ([string]$menu.Path).Length -eq 0){ continue }
    $parts=@()
    if([bool]$menu.FillsOnOpen){ $parts+='fills-on-open' }
    # Revision 2 (B2): marcable es un hecho neutro (la entrada conmuta un ajuste), no su estado: la mente no la pulsa
    # buscando un lugar.
    elseif([bool]$menu.Checkable -or [bool]$menu.Checked){ $parts+='checkable' }
    $id=$(if([bool]$menu.FillsOnOpen -or [int]$menu.Id -le 0){ '' } else { 'hmenu.'+[int]$menu.Id })
    $out+=@(@{ kind='MenuItem'; name=[string]$menu.Path; nameSource='menu'; id=$id; state=($parts -join ' '); value=$null; itemType=''; shortcut=[string]$menu.Shortcut; rect=$null; repeated=0 })
  }
  return $out
}
# La entrada del HMENU que pide el clic: por su identidad «hmenu.<id>», o por la etiqueta (la ruta entera o su ultimo
# tramo, igual). Devuelve la entrada, o un error: varias que lo dicen (ambiguo), o ninguna. El deshabilitado estatico no
# la rechaza (revision de la ronda 20b, hallazgo 2: puede ser el de la ultima apertura); la aplicacion decide al recibir
# la orden, y su recibo es lo que cambie (la marca, un dialogo, la superficie), nunca la orden enviada.
function Find-MenuCommand($menuEntries,[string[]]$aliases,[string]$controlId){
  $commands=@($menuEntries | Where-Object { $null -ne $_ -and -not [bool]$_.FillsOnOpen -and [int]$_.Id -gt 0 })
  $found=@()
  if($controlId.StartsWith('hmenu.')){
    $found=@($commands | Where-Object { ('hmenu.'+[int]$_.Id) -eq $controlId })
    if($found.Count -eq 1 -and $aliases.Count -gt 0){
      $path=[string]$found[0].Path
      $last=$path.Split([string[]]@(' '+[char]0x203A+' '),[StringSplitOptions]::None)[-1]
      if(-not (Test-NameMatch $path $aliases) -and -not (Test-NameMatch $last $aliases)){ return @{ error='visible_control_label_mismatch' } }
    }
  } else {
    $found=@($commands | Where-Object { $path=[string]$_.Path; (Test-NameMatch $path $aliases) -or (Test-NameMatch ($path.Split([string[]]@(' '+[char]0x203A+' '),[StringSplitOptions]::None)[-1]) $aliases) })
  }
  if($found.Count -gt 1){ return @{ error='visible_button_ambiguous' } }
  if($found.Count -eq 0){ return @{ error=$(if($controlId.Length -gt 0){ 'visible_control_identity_stale' } else { 'visible_button_not_found' }) } }
  return @{ entry=$found[0] }
}
# Revision 2 de la ronda 20b (B1): lo que se ve va antes que el menu cerrado. Primero los accionables del arbol, luego
# lo demas que se ve (Text, HeaderItem, DataItem, Group) y al final las entradas del HMENU, que no estan en pantalla:
# solo en el hueco que deja el arbol bajo el tope, sin llegar a el (una vista llena significa que el arbol tenia mas, y
# las entradas que no caben se pulsan igual por su etiqueta). Cuentan en el total solo las listadas.
# Ronda 21 (vista ordenada por objetivo y estructura; v3-24, v3-64, v3-65, t-drag-4): cuando lo que se ve no cabe en el
# tope, el corte ya no es el orden del arbol. (1) El campo de texto de una fila con su mismo nombre (la celda que
# renombra, dentro de su ListItem) se pliega en la fila: no es otro objetivo y llenaba el cupo. (2) Los accionables que
# no son filas (encabezados, pestanas, barras, menus, botones, campos). (3) Las filas (ListItem, TreeItem). (4) Lo demas
# que se ve. Lo elegido sale en el orden de siempre (accionables y luego lo demas, cada grupo en orden del arbol); sin
# corte la vista es la misma que antes. (5) Revision 1: hasta $script:WantedRoom controles que quedaron fuera y cuyo
# nombre lleva una palabra del objetivo del paso («wanted»: las que la mente usa para ordenar la vista) van DESPUES de
# todo lo anterior, marcados «reserved». Asi la base del corte no depende de las palabras: la mirada de antes del primer
# acto de un subobjetivo (sin palabras) y la de despues (con ellas) se comparan sobre lo mismo, y la mision no cuenta lo
# reservado como algo que el acto trajo (ComputerUseSuccessCheck.ComparedControls).
# Ronda 23 (indices de vista y esquema, t-menu-2): el tope de una mirada, el cupo reservado y el cuerpo numeran la
# vista de 0 a $script:ViewCap+$script:WantedRoom (VisibleViewNumbering en el kernel: el catalogo acepta ese rango y
# un test lee estas constantes de aqui).
$script:ViewCap=60
$script:ViewRowKinds=@('ListItem','TreeItem','DataItem')
$script:WantedRoom=10
function Test-WantedName([string]$name,[string[]]$wanted){
  $folded=Get-Folded $name
  if($folded.Length -eq 0){ return $false }
  foreach($word in @($wanted)){ $needle=Get-Folded ([string]$word); if($needle.Length -gt 0 -and $folded.Contains($needle)){ return $true } }
  return $false
}
# Los campos de texto que son la celda de una fila de su mismo nombre (el centro dentro de la fila, o sin rectangulo).
function Get-FoldedFields($entries){
  $drop=New-Object 'System.Collections.Generic.HashSet[object]'
  $rows=@{}
  foreach($entry in @($entries)){
    if($null -eq $entry -or $script:ViewRowKinds -notcontains [string]$entry.kind){ continue }
    $key=([string]$entry.name).ToLowerInvariant()
    if(-not $rows.ContainsKey($key)){ $rows[$key]=@() }
    $rows[$key]+=@($entry)
  }
  if($rows.Count -eq 0){ return ,$drop }
  foreach($entry in @($entries)){
    if($null -eq $entry -or [string]$entry.kind -ne 'Edit'){ continue }
    $key=([string]$entry.name).ToLowerInvariant()
    if(-not $rows.ContainsKey($key)){ continue }
    foreach($row in $rows[$key]){
      if($null -eq $entry.rect -or $null -eq $row.rect -or (Test-CenterWithin $row.rect $entry.rect)){ [void]$drop.Add($entry); break }
    }
  }
  return ,$drop
}
# Encargo IMP3 (imp2 imp-dc-leer: el MD abierto, 169 controles, los mensajes fuera de los 60 primeros): con «tail» el
# corte guarda las ultimas entradas del arbol (lo que la ventana dibujo al final: los mensajes mas nuevos de una
# conversacion), en su orden; sin el, el corte de siempre.
function Select-TailControls($primary,$secondary,[int]$limit){
  $all=@(@($primary)+@($secondary) | Where-Object { $null -ne $_ } | Sort-Object { [int]$_.seq })
  $controls=New-Object System.Collections.ArrayList
  foreach($entry in @($all | Select-Object -Last $limit)){ [void]$controls.Add($entry) }
  return @{ controls=$controls; menuListed=0; reserved=0 }
}
function Join-ViewControls($primary,$secondary,$menu,[int]$limit,[string[]]$wanted=@(),[bool]$tail=$false){
  if($tail -and (@($primary).Count+@($secondary).Count) -gt $limit){ return (Select-TailControls $primary $secondary $limit) }
  $controls=New-Object System.Collections.ArrayList
  $extra=New-Object System.Collections.ArrayList
  $pool=New-Object System.Collections.ArrayList
  foreach($entry in @($primary)){ if($null -ne $entry){ [void]$pool.Add(@{ entry=$entry; tier=$(if($script:ViewRowKinds -contains [string]$entry.kind){ 2 } else { 1 }) }) } }
  foreach($entry in @($secondary)){ if($null -ne $entry){ [void]$pool.Add(@{ entry=$entry; tier=3 }) } }
  if($pool.Count -gt $limit){
    $drop=Get-FoldedFields @($pool | ForEach-Object { $_.entry })
    $list=@($pool | Where-Object { -not $drop.Contains($_.entry) })
    $chosen=New-Object 'System.Collections.Generic.HashSet[int]'
    if($list.Count -gt $limit){
      foreach($tier in @(1,2,3)){
        for($k=0;$k -lt $list.Count -and $chosen.Count -lt $limit;$k++){ if($list[$k].tier -eq $tier){ [void]$chosen.Add($k) } }
      }
      if(@($wanted).Count -gt 0){
        for($k=0;$k -lt $list.Count -and $extra.Count -lt $script:WantedRoom;$k++){
          if($chosen.Contains($k)){ continue }
          $entry=$list[$k].entry
          if(-not [bool]$entry.systemMenu -and (Test-WantedName ([string]$entry.name) $wanted)){ [void]$extra.Add($entry) }
        }
      }
    } else { for($k=0;$k -lt $list.Count;$k++){ [void]$chosen.Add($k) } }
    for($k=0;$k -lt $list.Count;$k++){ if($chosen.Contains($k)){ [void]$controls.Add($list[$k].entry) } }
  } else {
    foreach($slot in $pool){ [void]$controls.Add($slot.entry) }
  }
  $room=$limit-1-$controls.Count
  $menuListed=0
  foreach($entry in @($menu)){ if($null -ne $entry -and $menuListed -lt $room){ [void]$controls.Add($entry); $menuListed++ } }
  foreach($entry in $extra){ $entry.reserved=$true; [void]$controls.Add($entry) }
  return @{ controls=$controls; menuListed=$menuListed; reserved=$extra.Count }
}
# Ronda 21 (t-drag-4): el cuerpo de la ventana es su superficie de contenido: el Pane, Custom, Image o Document de mayor
# area (al menos $script:BodyShare de la caja de la ventana) que no tiene dentro ningun accionable (el lienzo de un editor
# de imagenes, no el panel que envuelve la cinta y el lienzo). Va siempre en la vista, fuera del tope, con su nombre o,
# sin el, el de su tipo entre parentesis (como un campo sin nombre), y su rectangulo: un trazo se arrastra sobre el.
$script:BodyKinds=@('Pane','Custom','Image','Document')
$script:BodyShare=0.15
function Get-BodySurface($item,[string]$kind,[string]$name,$rect,$box){
  if($null -eq $rect -or $null -eq $box -or [double]$box.w -le 0 -or [double]$box.h -le 0){ return $null }
  $area=[double]$rect.w*[double]$rect.h
  if($area -lt $script:BodyShare*[double]$box.w*[double]$box.h){ return $null }
  $named=-not [string]::IsNullOrWhiteSpace($name)
  return @{ item=$item; kind=$kind; name=$(if($named){ $name } else { '(' + $kind.ToLowerInvariant() + ')' }); nameSource=$(if($named){ 'name' } else { 'kind' }); id=(Get-Id $item); rect=$rect; area=$area }
}
# Revision 2: el cuerpo se anade fuera del tope solo a una vista que ya lista mas de un control. Una ventana que lista
# como mucho uno (CEF, un lienzo) se lee por lo dibujado: el adaptador lee su texto sin pedirlo, con autoridad de lineas
# y marcas de tinta, y la mision firma su cambio por el texto; un cuerpo anadido la sacaria de ese regimen. Ya listado,
# solo se marca; un cuerpo que solo entro por la reserva sale de ella y va al final como siempre (la base no cambia).
function Add-ViewBody($controls,$body,$elements){
  if($null -eq $body){ return }
  $listed=$null
  $shown=0
  foreach($entry in $controls){
    if(-not [bool]$entry.reserved -and -not [string]::IsNullOrEmpty([string]$entry.name)){ $shown++ }
    if($null -eq $listed -and ([string]$entry.id).Length -gt 0 -and [string]$entry.id -eq [string]$body.id){ $listed=$entry }
  }
  if($null -ne $listed -and [bool]$listed.reserved){ [void]$controls.Remove($listed); $listed=$null }
  if($null -ne $listed){ $listed.body=$true; return }
  if($shown -le 1){ return }
  [void]$controls.Add(@{ kind=$body.kind; name=$body.name; nameSource=$body.nameSource; id=$body.id; state=''; value=$null; itemType=''; shortcut=''; rect=$body.rect; repeated=0; systemMenu=$false; body=$true })
  if(([string]$body.id).Length -gt 0){ $elements[[string]$body.id]=$body.item }
}
function Select-BodySurface($surfaces,$primary){
  $best=$null
  foreach($surface in @($surfaces)){
    if($null -eq $surface){ continue }
    if($null -ne $best -and [double]$surface.area -le [double]$best.area){ continue }
    $holds=$false
    foreach($entry in @($primary)){
      if($null -eq $entry -or $null -eq $entry.rect){ continue }
      if(([string]$entry.id).Length -gt 0 -and [string]$entry.id -eq [string]$surface.id){ continue }
      if(Test-CenterWithin $surface.rect $entry.rect){ $holds=$true; break }
    }
    if(-not $holds){ $best=$surface }
  }
  return $best
}
function Do-View($request){
  $limit=[int]$request.limit; if($limit -lt 1){$limit=1}; if($limit -gt $script:ViewCap){$limit=$script:ViewCap}
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return @{ ok=$false; error='active_window_not_found' } }
  $root=$target.root
  if($null -eq $root){ return @{ ok=$false; error='visible_controls_root_unavailable' } }
  # Ronda 25 (latencia): una sola busqueda del arbol. Los deshabilitados que se ven llegan en el mismo recorrido y se
  # apartan aqui (Get-DisabledShown los lista); el resto de la vista lee solo los habilitados, como antes.
  $withDimmed=($request.disabled -ne $false)
  $all=Get-ShownDescendants $root ([long]$target.hwnd) 0 $withDimmed
  $dimmed=New-Object System.Collections.Generic.List[object]
  if($withDimmed){
    $lit=New-Object System.Collections.Generic.List[object]
    foreach($el in $all){ try { if($el.Cached.IsEnabled){ $lit.Add($el) } else { $dimmed.Add($el) } } catch {} }
    $all=$lit
  }
  $viewPartial=$script:Partial
  # Ronda 20b, palanca 8: una vista solo de marco se relee (Get-ClientReread); sin contenido tampoco alli, sale marcada
  # «frameOnly» (sin arbol: el OCR la lee como hoy).
  $clientFrom='';$frameOnly=$false;$keepOffscreen=$false;$clientRoot=$null
  if(Test-FrameOnlyView $all){
    $reread=Get-ClientReread $root $target.hwnd
    if($null -ne $reread){
      $merged=New-Object System.Collections.Generic.List[object]
      foreach($el in $all){ $merged.Add($el) }
      foreach($el in $reread.items){ $merged.Add($el) }
      $all=$merged;$clientFrom=$reread.from;$keepOffscreen=($reread.from -eq 'unfiltered');$clientRoot=$reread.root
    } else { $frameOnly=$true }
  }
  # Las TitleBar de la vista: un MenuBar o MenuItem dibujado dentro de una se mira por su cadena (Test-SystemMenu).
  $titleBars=@()
  foreach($item in $all){ try { if(([string]$item.Cached.ControlType.ProgrammaticName) -eq 'ControlType.TitleBar'){ $titleBars+=@(Get-Rect $item) } } catch {} }
  $seen=@{}
  $primary=New-Object System.Collections.ArrayList
  $secondary=New-Object System.Collections.ArrayList
  $elements=@{}
  $focused=$null
  $total=0
  # Ronda 21 (t-drag-4): las superficies de contenido grandes (lienzo, documento, panel) que pueden ser el cuerpo.
  $box=Get-WindowBox ([IntPtr][long]$target.hwnd)
  $surfaces=New-Object System.Collections.ArrayList
  foreach($item in $all){
    try {
      if($item.Cached.IsOffscreen -and -not $keepOffscreen){ continue }
      $shown=Get-ShownName $item
      $name=$shown.name
      $kind=$item.Cached.ControlType.ProgrammaticName -replace '^ControlType\.',''
      if($script:BodyKinds -contains $kind){
        $surface=Get-BodySurface $item $kind $name (Get-Rect $item) $box
        if($null -ne $surface){ [void]$surfaces.Add($surface) }
      }
      $stateInfo=Get-State $item
      # Un campo de texto sin nombre (ni de respaldo) sigue siendo accionable: se
      # identifica por su valor o por su clase; el resto sin nombre no informa de nada.
      if([string]::IsNullOrWhiteSpace($name) -and ($kind -eq 'Edit' -or $kind -eq 'ComboBox' -or $kind -eq 'Spinner')){
        # Un campo de formulario sin nombre ni LabeledBy lo nombra su rotulo: el texto mas cercano a su izquierda o
        # encima (punto 2 del goal v3: «poner el ancho en 800»).
        $near=Get-NearLabel $item $all
        if($near.Length -gt 0){ $name=$near; $shown=@{ name=$near; source='nearText' } }
      }
      if([string]::IsNullOrWhiteSpace($name)){
        if($kind -eq 'Edit' -or $kind -eq 'Document'){ $name='(' + $kind.ToLowerInvariant() + ')' } else { continue }
      }
      $rect=Get-Rect $item
      $key=Get-SeenKey $kind $name $stateInfo.state
      if($seen.ContainsKey($key)){
        $seen[$key].repeated=[int]$seen[$key].repeated+1
        continue
      }
      $total++
      $id=Get-Id $item
      # Lo que la aplicacion dice que es un elemento de lista o arbol (una carpeta, un acceso directo, una aplicacion).
      $itemType=''
      if($kind -eq 'ListItem' -or $kind -eq 'DataItem' -or $kind -eq 'TreeItem'){
        try { $itemType=[string]$item.Cached.ItemType; if($null -eq $itemType){ $itemType='' } else { $itemType=($itemType -replace '\s+',' ').Trim() } } catch { $itemType='' }
      }
      # Goal v3 B3 (atajos): la tecla que la propia aplicacion declara para el control (AcceleratorKey, o su
      # AccessKey), leida del cache del arbol: el prompt la muestra junto al control, sin lista por aplicacion.
      $shortcut=''
      try { $shortcut=[string]$item.Cached.AcceleratorKey; if([string]::IsNullOrWhiteSpace($shortcut)){ $shortcut=[string]$item.Cached.AccessKey } } catch { $shortcut='' }
      if($null -eq $shortcut){ $shortcut='' } else { $shortcut=($shortcut -replace '\s+',' ').Trim() }
      if($shortcut.Length -gt 24){ $shortcut='' }
      # Ronda 20b, palanca 8 (v3-62): la cadena del menu del sistema bajo la TitleBar va marcada; la mision no la
      # cuenta como contenido y la mente la oculta salvo que el objetivo pida mover, restaurar o cerrar la ventana.
      $systemMenu=$false
      if(($kind -eq 'MenuItem' -or $kind -eq 'MenuBar') -and $titleBars.Count -gt 0){
        # Sin rectangulo (un menu del sistema leido asi) o dibujado dentro de una TitleBar: su cadena decide.
        $inBar=($null -eq $rect)
        foreach($bar in $titleBars){ if($inBar){ break }; if(Test-CenterWithin $bar $rect){ $inBar=$true } }
        if($inBar){ $systemMenu=(Test-SystemMenu $item) }
      }
      $entry=@{ kind=$kind; name=$name; nameSource=$shown.source; id=$id; state=$stateInfo.state; value=$stateInfo.value; itemType=$itemType; shortcut=$shortcut; rect=$rect; repeated=0; systemMenu=$systemMenu; seq=$total }
      $seen[$key]=$entry
      if($Actionable -contains $kind){ [void]$primary.Add($entry) } else { [void]$secondary.Add($entry) }
      if($stateInfo.state -match '\bfocused\b' -and $null -eq $focused){ $focused=$entry }
      if($id.Length -gt 0){ $elements[$id]=$item }
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  # Palanca 7 (v3-49): las entradas del menu clasico (HMENU) de la ventana, leidas sin abrir ninguno.
  $menuEntries=@()
  try { $menuEntries=@([BaxyUiaWorkerNative]::MenuEntries($target.hwnd,$script:MenuEntriesMax)) } catch { $menuEntries=@() }
  $menuView=New-Object System.Collections.ArrayList
  foreach($entry in @(ConvertTo-MenuViewEntries $menuEntries)){
    $key=$entry.kind+'|'+$entry.name
    if($seen.ContainsKey($key)){ continue }
    $seen[$key]=$entry
    [void]$menuView.Add($entry)
  }
  $wanted=@($request.wanted | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -First 24)
  $joined=Join-ViewControls $primary $secondary $menuView $limit $wanted ([bool]$request.tail)
  $controls=$joined.controls
  $total+=[int]$joined.menuListed
  # Ronda 21 (t-drag-4): el cuerpo de la ventana va siempre, fuera del tope: ya listado, solo se marca.
  $body=Select-BodySurface $surfaces $primary
  Add-ViewBody $controls $body $elements
  $script:LastView=@{ hwnd=$target.hwnd; elements=$elements; client=$clientRoot; unfiltered=$keepOffscreen }
  $ordered=@()
  $position=0
  foreach($entry in $controls){
    $ordered+=@([pscustomobject]@{ i=$position; kind=$entry.kind; name=$entry.name; nameSource=$entry.nameSource; id=$entry.id; state=$entry.state; value=$entry.value; itemType=$entry.itemType; shortcut=$entry.shortcut; rect=$entry.rect; repeated=$entry.repeated; systemMenu=[bool]$entry.systemMenu; body=[bool]$entry.body; reserved=[bool]$entry.reserved })
    $position++
  }
  # Revision de la rama (hallazgo 6): una mirada dentro de una rafaga (con el frente prestado) no los pide: solo busca
  # controles que pulsar, y su recorrido ni los trae.
  $disabled=@()
  # Ronda 24 (pasada r23 v3-27): sin @(): la funcion ya devuelve un arreglo plano; @() sobre su arreglo envuelto lo
  # anidaba ([[...]]) y el adaptador, que salta lo que no es objeto, recibia la lista vacia.
  if($withDimmed){ $disabled=Get-DisabledShown $dimmed $all.Count $seen }
  $focusedOut=$null
  if($null -ne $focused){
    # Su indice en la vista, si la vista lo entrego: el campo al que va un texto dirigido (input.text.type «index»).
    $focusedIndex=$null
    for($k=0;$k -lt $ordered.Count;$k++){ if([object]::ReferenceEquals($controls[$k],$focused)){ $focusedIndex=$k; break } }
    $focusedOut=[pscustomobject]@{ kind=$focused.kind; name=$focused.name; nameSource=$focused.nameSource; value=$focused.value; i=$focusedIndex }
  }
  return @{ ok=$true; error=''; hwnd=[long]$target.hwnd; window=(Get-Name $root); controls=$ordered; controlCount=($total+$script:ShownUnread); focused=$focusedOut; clientProviders=$script:ClientProviders; disabled=$disabled; clientFrom=$clientFrom; frameOnly=$frameOnly; partial=$viewPartial }
}
# Ronda 21, revision 1 (B2, B4): la firma barata de una ventana, para buscar el destino de un pedido sin aplicacion. Un
# recorrido en anchura del arbol de control acotado en nodos y en tiempo (budgetMs), sin releer el cliente, sin las
# entradas del HMENU ni la segunda lectura de deshabilitados, y sin tocar la ultima vista ($script:LastView): solo tipo y
# nombre de los primeros controles que se ven, y si un Document o un Edit tiene una seleccion de texto no vacia
# (TextPattern.GetSelection), leida, nunca supuesta.
# Revision 1 de la ronda 24 (B1): cada control que esta dentro de un Document (el contenido de una pagina, el boton
# «Guardar» de un video) sale con content=true, para que el destino nunca tome el contenido por el marco de la ventana.
$script:SignatureNodes=600
$script:SignatureTexts=4
function Test-TextSelected($el){
  $pattern=$null
  try {
    if(-not $el.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern,[ref]$pattern)){ return $false }
    foreach($range in @(([System.Windows.Automation.TextPattern]$pattern).GetSelection())){
      if(-not [string]::IsNullOrWhiteSpace([string]$range.GetText(256))){ return $true }
    }
  } catch {}
  return $false
}
function Do-Signature($request){
  $watch=[System.Diagnostics.Stopwatch]::StartNew()
  $limit=[int]$request.limit; if($limit -lt 1){$limit=1}; if($limit -gt $script:ViewCap){$limit=$script:ViewCap}
  $budget=[int]$request.budgetMs; if($budget -lt 100){$budget=100}; if($budget -gt 4000){$budget=4000}
  if([long]$request.hwnd -le 0){ return @{ ok=$false; error='active_window_not_found' } }
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target -or $null -eq $target.root){ return @{ ok=$false; error='visible_controls_root_unavailable' } }
  $walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker
  $queue=New-Object System.Collections.Generic.Queue[object]
  $inside=New-Object System.Collections.Generic.Queue[bool]
  $queue.Enqueue($target.root)
  $inside.Enqueue($false)
  $controls=New-Object System.Collections.ArrayList
  $seen=@{}
  $texts=0;$selection=$false;$visited=0;$complete=$true
  while($queue.Count -gt 0 -and $complete){
    $node=$queue.Dequeue()
    $nodeContent=$inside.Dequeue()
    $child=$null
    try { $child=$walker.GetFirstChild($node,$script:Cache) } catch { $child=$null }
    while($null -ne $child){
      if($watch.ElapsedMilliseconds -ge $budget -or $visited -ge $script:SignatureNodes){ $complete=$false; break }
      $visited++
      $shown=$false;$kind='';$name=''
      try {
        $shown=-not $child.Cached.IsOffscreen
        $kind=$child.Cached.ControlType.ProgrammaticName -replace '^ControlType\.',''
        $name=Format-Name ([string]$child.Cached.Name)
      } catch { $shown=$false }
      if($shown -and -not $selection -and $texts -lt $script:SignatureTexts -and ($kind -eq 'Document' -or $kind -eq 'Edit')){
        $texts++
        $selection=Test-TextSelected $child
      }
      $key=$kind+'|'+$name+'|'+$nodeContent
      if($shown -and $name.Length -gt 0 -and $controls.Count -lt $limit -and -not $seen.ContainsKey($key)){
        $seen[$key]=$true
        if($nodeContent){ [void]$controls.Add([pscustomobject]@{ kind=$kind; name=$name; content=$true }) }
        else { [void]$controls.Add([pscustomobject]@{ kind=$kind; name=$name }) }
      }
      $queue.Enqueue($child)
      $inside.Enqueue(($nodeContent -or $kind -eq 'Document'))
      try { $child=$walker.GetNextSibling($child,$script:Cache) } catch { $child=$null }
    }
  }
  return @{ ok=$true; error=''; hwnd=[long]$target.hwnd; controls=@($controls); selection=$selection; complete=$complete; visited=$visited; elapsedMs=[long]$watch.ElapsedMilliseconds }
}
# Los accionables que se ven pero estan deshabilitados (pasada r15b, v3-27 y v3-29: «Copiar» y «Buscar» del Mapa de
# caracteres esperan texto en su campo y la vista los quitaba, asi que el modelo no sabia que existian). Van aparte de
# los controles, sin indice ni identidad (nada los pulsa), y solo en un arbol pequeno (con cientos de controles a la
# vista no se listan). Un nombre que ya lista un control habilitado de su tipo no se repite.
# Ronda 25 (latencia): $found son los deshabilitados que el recorrido de la vista ya trajo; ninguna busqueda propia.
# Devuelve un arreglo plano (envuelto con la coma para que la tuberia no lo desarme): se asigna tal cual, sin @().
$script:DisabledShownTree=150
$script:DisabledShownMax=12
function Get-DisabledShown($found,[int]$shownCount,$seen){
  $out=New-Object System.Collections.ArrayList
  if($shownCount -gt $script:DisabledShownTree){ return ,$out.ToArray() }
  $named=@{}
  foreach($item in $found){
    if($out.Count -ge $script:DisabledShownMax){ break }
    try {
      $kind=$item.Cached.ControlType.ProgrammaticName -replace '^ControlType\.',''
      if($Actionable -notcontains $kind -or $kind -eq 'Edit' -or $kind -eq 'Document'){ continue }
      $name=(Get-ShownName $item).name
      if([string]::IsNullOrWhiteSpace($name)){ continue }
      $key=$kind+'|'+$name
      if($seen.ContainsKey($key) -or $named.ContainsKey($key)){ continue }
      $named[$key]=$true
      [void]$out.Add([pscustomobject]@{ kind=$kind; name=$name; state='disabled'; rect=(Get-Rect $item) })
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  return ,$out.ToArray()
}
function Find-ById($root,[string]$controlId){
  if([string]::IsNullOrWhiteSpace($controlId)){ return $null }
  # Revision de la palanca 8 (hallazgo 3): si la ultima vista de esta ventana se leyo sin el filtro IsOffscreen, lo
  # marcado fuera de pantalla que cae dentro de la caja de la ventana sigue valiendo (es lo que se ofrecio).
  $offscreenBox=Get-UnfilteredBox $root
  $cached=$script:LastView.elements[$controlId]
  if($null -ne $cached){
    try { if($cached.Current.IsEnabled -and (Test-OffscreenUsable ([bool]$cached.Current.IsOffscreen) (Get-CurrentRect $cached) $offscreenBox)){ return $cached } } catch {}
  }
  foreach($item in (Get-LookupScope $root $offscreenBox)){
    try { if((Get-Id $item) -eq $controlId -and (Test-OffscreenUsable ([bool]$item.Cached.IsOffscreen) (Get-Rect $item) $offscreenBox)){ return $item } } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  # Ronda 20b, palanca 8: el contenido de un dialogo que la vista leyo bajo su ventana duena.
  $client=$script:LastView.client
  if($null -ne $client -and -not [System.Windows.Automation.Automation]::Compare($client,$root)){
    foreach($item in (Get-Descendants $client)){
      try { if((Get-Id $item) -eq $controlId){ return $item } } catch [System.Windows.Automation.ElementNotAvailableException] {}
    }
  }
  return $null
}
# El exterior contiene al interior: por la cadena de antecesores del interior
# (sus RuntimeId) o, sin ella, por su rectangulo dentro del del exterior.
function Test-Contains($outer,$inner){
  $ancestors=@($inner.ancestors | Where-Object { ([string]$_).Length -gt 0 })
  if($ancestors.Count -gt 0){ return (([string]$outer.key).Length -gt 0 -and ($ancestors -contains [string]$outer.key)) }
  $a=$outer.rect;$b=$inner.rect
  if($null -eq $a -or $null -eq $b -or $a.w -le 0 -or $a.h -le 0 -or $b.w -le 0 -or $b.h -le 0){ return $false }
  return ($a.x -le $b.x -and $a.y -le $b.y -and ($a.x+$a.w) -ge ($b.x+$b.w) -and ($a.y+$a.h) -ge ($b.y+$b.h))
}
# Varios controles con el mismo nombre en una sola linea de descendencia (uno
# contiene a los otros; medido en Paint: cada entrada de su galeria es un
# ListItem con un Button dentro, los dos «Rectangulo redondeado») son un solo
# objetivo: el que se invoca, si no el que se selecciona, si no el mas
# interior. Devuelve su posicion, o -1 si son controles separados (ambiguo).
# Cada entrada: name, key (RuntimeId), ancestors (RuntimeId de sus
# antecesores; vacio si no se pudo leer), rect (x,y,w,h o nulo), invoke, select,
# edit (toma texto) y kind (su ControlType: Group, ListItem...).
function Select-LineageOne($entries){
  $list=@($entries)
  if($list.Count -lt 2){ return ($list.Count-1) }
  $first=[string]$list[0].name
  foreach($entry in $list){ if(-not [string]::Equals([string]$entry.name,$first,[StringComparison]::OrdinalIgnoreCase)){ return -1 } }
  $depth=New-Object int[] $list.Count
  $holders=@{}
  for($i=0;$i -lt $list.Count;$i++){ $holders[$i]=@() }
  for($i=0;$i -lt $list.Count;$i++){
    for($j=$i+1;$j -lt $list.Count;$j++){
      $ij=Test-Contains $list[$i] $list[$j]; $ji=Test-Contains $list[$j] $list[$i]
      if(-not $ij -and -not $ji){ return -1 }
      if($ij){ $depth[$j]++; $holders[$j]+=@($i) }
      if($ji){ $depth[$i]++; $holders[$i]+=@($j) }
    }
  }
  $all=@(0..($list.Count-1))
  # A field that takes text inside a same-named control that invokes (a search box's Edit inside its Group) is what a
  # person clicks: measured on a store's search, the Group took the click and the field never got the keyboard.
  # Only inside a box (Group, Pane, Custom, ComboBox): in a row of Explorer's details view (ListItem, DataItem,
  # TreeItem) the same-named Edit is the rename field, and clicking it would let the next typing rename the file.
  $boxes=@('Group','Pane','Custom','ComboBox')
  $fields=@($all | Where-Object {
    $k=$_
    $list[$k].edit -and $holders[$k].Count -gt 0 -and
      @($holders[$k] | Where-Object { $boxes -notcontains [string]$list[$_].kind }).Count -eq 0
  })
  $pool=@($all | Where-Object { $list[$_].invoke -or $fields -contains $_ })
  if($pool.Count -eq 0){ $pool=@($all | Where-Object { $list[$_].select }) }
  if($pool.Count -eq 0){ $pool=$all }
  $best=$pool[0]
  foreach($k in $pool){ if($depth[$k] -ge $depth[$best]){ $best=$k } }
  return $best
}
function Get-LineageEntry($el){
  $ancestors=@()
  try {
    $walker=[System.Windows.Automation.TreeWalker]::RawViewWalker
    $node=$walker.GetParent($el);$steps=0
    while($null -ne $node -and $steps -lt 40){ $ancestors+=@(Get-Id $node); $node=$walker.GetParent($node); $steps++ }
  } catch { $ancestors=@() }
  $pattern=$null
  $invoke=$false;$select=$false;$toggle=$false;$expand=$false
  try { $invoke=$el.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$pattern) } catch {}
  try { $select=$el.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern) } catch {}
  try { $toggle=$el.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern) } catch {}
  try { $expand=$el.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$pattern) } catch {}
  $kind=''
  try { $kind=([string]$el.Current.ControlType.ProgrammaticName) -replace '^ControlType\.','' } catch {}
  return @{ name=(Get-ShownName $el).name; key=(Get-Id $el); ancestors=$ancestors; rect=(Get-Rect $el); invoke=$invoke; select=$select; toggle=$toggle; expand=$expand; edit=($kind -eq 'Edit'); kind=$kind }
}
# Los controles con ese nombre; sin ninguno igual, los que lo llevan como
# palabras (el clic solo sigue si es uno). Los iguales de una sola linea de
# descendencia son uno (Select-LineageOne); los demas de esa linea quedan en
# $script:NamedLineage para que el postread acepte su seleccion como prueba.
$script:NamedLineage=@()
$script:LineageToggles=@()
# Cuantos elementos tenia el arbol en la ultima busqueda por nombre: el adaptador sigue esperando una etiqueta tras
# abrir una aplicacion solo mientras su arbol crece (analisis r3a M7).
$script:TreeSize=-1
# Dos vistas de un mismo control. UIA puede publicar un elemento bajo dos padres: un desplegable de WPF abierto publica
# cada entrada como hija suya y otra vez dentro de su Popup, con otro id, y las dos comparten el mismo Text de dentro
# (medido: la busqueda daba dos ListItem «Verde» que no se contienen y el mismo Text dos veces, y el clic quedaba
# ambiguo). Cada elemento cuenta una vez, y de los padres con nombre que comparten un mismo hijo con nombre solo queda
# el que ese hijo da como su padre.
function Merge-SharedViews($matches){
  $seen=@{}; $unique=@()
  foreach($m in @($matches)){ $k=Get-Id $m; if($k.Length -eq 0 -or -not $seen.ContainsKey($k)){ if($k.Length -gt 0){ $seen[$k]=$true }; $unique+=@($m) } }
  if($unique.Count -lt 3){ return $unique }
  $walker=[System.Windows.Automation.TreeWalker]::RawViewWalker
  $keys=@{}; foreach($m in $unique){ $k=Get-Id $m; if($k.Length -gt 0){ $keys[$k]=$true } }
  $drop=@{}
  foreach($leaf in $unique){
    $leafKey=Get-Id $leaf
    $parent=''; try { $parent=Get-Id ($walker.GetParent($leaf)) } catch {}
    if($leafKey.Length -eq 0 -or $parent.Length -eq 0 -or -not $keys.ContainsKey($parent)){ continue }
    foreach($other in $unique){
      $otherKey=Get-Id $other
      if($otherKey.Length -eq 0 -or $otherKey -eq $leafKey -or $otherKey -eq $parent){ continue }
      $child=$null; try { $child=$walker.GetFirstChild($other) } catch {}
      for($n=0;$null -ne $child -and $n -lt 50;$n++){
        if((Get-Id $child) -eq $leafKey){ $drop[$otherKey]=$true; break }
        try { $child=$walker.GetNextSibling($child) } catch { $child=$null }
      }
    }
  }
  return @($unique | Where-Object { -not $drop.ContainsKey((Get-Id $_)) })
}
# El menu de sistema de la ventana (la MenuBar que cuelga de su TitleBar y el MenuItem de dentro) no es un lugar que una
# etiqueta nombre: el clic por nombre nunca lo pulsa, solo el que llega con la identidad que dio la vista (la mente lo
# deja pasar cuando el objetivo pide mover, restaurar o cerrar la ventana). Pasada r15b, v3-23: «hacer clic en sistema»
# en una consola MMC pulso el menu «Sistema» de la barra de titulo (lo abrio, expand) y el sub-objetivo se dio por
# cumplido; el registro «Sistema» de la lista no llego a elegirse.
function Test-SystemMenuChain([string]$kind,[string[]]$ancestorKinds){
  if($kind -ne 'MenuItem' -and $kind -ne 'MenuBar'){ return $false }
  return (@($ancestorKinds | Select-Object -First 2) -contains 'TitleBar')
}
function Test-SystemMenu($el){
  try {
    $kind=([string]$el.Current.ControlType.ProgrammaticName) -replace '^ControlType\.',''
    if($kind -ne 'MenuItem' -and $kind -ne 'MenuBar'){ return $false }
    $kinds=@()
    $node=[System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($el)
    for($n=0;$null -ne $node -and $n -lt 2;$n++){
      $kinds+=@(([string]$node.Current.ControlType.ProgrammaticName) -replace '^ControlType\.','')
      $node=[System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($node)
    }
    return (Test-SystemMenuChain $kind $kinds)
  } catch { return $false }
}
# Ronda 20b, palanca 8 (pasada r18, v3-51 y v3-62): una vista que solo trae el marco de la ventana (su TitleBar, los
# botones de leyenda y la cadena del menu del sistema que cuelga de ella) no es la ventana. Medido: el dialogo modal
# de una aplicacion Qt se leyo con TitleBar y Cerrar y su contenido colgaba del arbol de la ventana duena; una
# aplicacion empaquetada se dio por arrancada con el marco y su menu del sistema y el contenido llego despues. Pieza
# de marco: la TitleBar, o un Button, MenuBar o MenuItem cuyo centro cae dentro de una TitleBar de la misma vista. Un
# Pane, Group, Custom o Window no dice nada (la superficie vacia de un lienzo). Hace falta al menos una TitleBar y no
# mas de 12 piezas: una vista con contenido nunca paga esta comprobacion. El titulo y el icono (Text, Image) dibujados
# en la TitleBar tambien son marco. Cada pieza: kind y rect (x,y,w,h).
function Test-RectWithin($outer,$inner){
  if($null -eq $outer -or $null -eq $inner -or [double]$outer.w -le 0 -or [double]$outer.h -le 0 -or [double]$inner.w -le 0 -or [double]$inner.h -le 0){ return $false }
  return ([double]$inner.x -ge ([double]$outer.x-2) -and [double]$inner.y -ge ([double]$outer.y-2) -and
          ([double]$inner.x+[double]$inner.w) -le ([double]$outer.x+[double]$outer.w+2) -and
          ([double]$inner.y+[double]$inner.h) -le ([double]$outer.y+[double]$outer.h+2))
}
function Test-CenterWithin($outer,$inner){
  if($null -eq $outer -or $null -eq $inner -or [double]$outer.w -le 0 -or [double]$outer.h -le 0){ return $false }
  $cx=[double]$inner.x+[double]$inner.w/2;$cy=[double]$inner.y+[double]$inner.h/2
  return ($cx -ge [double]$outer.x -and $cx -le ([double]$outer.x+[double]$outer.w) -and $cy -ge [double]$outer.y -and $cy -le ([double]$outer.y+[double]$outer.h))
}
function Test-FramePiece($piece,$bars){
  $kind=[string]$piece.kind
  if($kind -eq 'TitleBar'){ return $true }
  if(@('Button','MenuBar','MenuItem','Text','Image') -notcontains $kind){ return $false }
  foreach($bar in @($bars)){ if(Test-CenterWithin $bar $piece.rect){ return $true } }
  return $false
}
function Test-FrameOnly($pieces){
  $list=@($pieces | Where-Object { $null -ne $_ })
  if($list.Count -eq 0 -or $list.Count -gt 12){ return $false }
  $bars=@($list | Where-Object { [string]$_.kind -eq 'TitleBar' } | ForEach-Object { $_.rect })
  if($bars.Count -eq 0){ return $false }
  foreach($piece in $list){
    if(@('Pane','Group','Custom','Window') -contains [string]$piece.kind){ continue }
    if(-not (Test-FramePiece $piece $bars)){ return $false }
  }
  return $true
}
# Lo que una relectura trae como contenido: piezas con rectangulo dentro de la caja del dialogo que no son marco ni
# superficie muda. Cuenta, no filtra: la relectura se usa si trae al menos una.
function Measure-ClientPieces($pieces,$box){
  $list=@($pieces | Where-Object { $null -ne $_ })
  $bars=@($list | Where-Object { [string]$_.kind -eq 'TitleBar' } | ForEach-Object { $_.rect })
  $count=0
  foreach($piece in $list){
    if(@('Pane','Group','Custom','Window') -contains [string]$piece.kind){ continue }
    if(-not (Test-RectWithin $box $piece.rect)){ continue }
    if(Test-FramePiece $piece $bars){ continue }
    $count++
  }
  return $count
}
function Get-Piece($el){
  try { return @{ kind=(([string]$el.Cached.ControlType.ProgrammaticName) -replace '^ControlType\.',''); rect=(Get-Rect $el) } } catch { return $null }
}
function Get-WindowBox([IntPtr]$hwnd){
  $r=New-Object BaxyUiaWorkerNative+RECT
  if(-not [BaxyUiaWorkerNative]::GetWindowRect($hwnd,[ref]$r)){ return $null }
  return @{ x=$r.Left; y=$r.Top; w=($r.Right-$r.Left); h=($r.Bottom-$r.Top) }
}
function Test-FrameOnlyView($all){
  if($null -eq $all -or $all.Count -eq 0 -or $all.Count -gt 12){ return $false }
  return (Test-FrameOnly @(foreach($el in $all){ Get-Piece $el }))
}
# La relectura de una vista solo de marco, en este orden: (a) la misma raiz sin el filtro de lo que no se ve (un arbol
# puede marcar su contenido fuera de pantalla mientras lo dibuja); (b) la ventana duena (GW_OWNER, si no la raiz
# poseedora): bajo ella, el subarbol del dialogo, un elemento cuyo rectangulo cae dentro del del dialogo y cubre al
# menos su mitad (primero uno que se llama como el, despues el mayor), y de el solo lo que cae dentro del dialogo:
# nunca un control de la ventana principal fuera de el. Nada si ninguna trae contenido (la vista queda «sin arbol»).
function Get-ClientReread($root,[IntPtr]$hwnd){
  $box=Get-WindowBox $hwnd
  if($null -eq $box){ return $null }
  $enabled=New-Object System.Windows.Automation.PropertyCondition($AE::IsEnabledProperty,$true)
  $found=$null
  $activated=$script:Cache.Activate()
  try { try { $found=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$enabled) } catch { $found=$null } }
  finally { $activated.Dispose() }
  if($null -ne $found -and $found.Count -le 400){
    if((Measure-ClientPieces @(foreach($el in $found){ Get-Piece $el }) $box) -gt 0){
      $inside=New-Object System.Collections.Generic.List[object]
      foreach($el in $found){ if(Test-RectWithin $box (Get-Rect $el)){ $inside.Add($el) } }
      return @{ from='unfiltered'; items=$inside; root=$null }
    }
  }
  $owner=[BaxyUiaWorkerNative]::GetWindow($hwnd,4)
  if($owner -eq [IntPtr]::Zero){ $rootOwner=[BaxyUiaWorkerNative]::GetAncestor($hwnd,3); if($rootOwner -ne $hwnd){ $owner=$rootOwner } }
  if($owner -eq [IntPtr]::Zero -or $owner -eq $hwnd){ return $null }
  $ownerRoot=$null
  try { $ownerRoot=$AE::FromHandle($owner) } catch { $ownerRoot=$null }
  if($null -eq $ownerRoot){ return $null }
  $title=''
  try { $title=[string]$root.Current.Name } catch { $title='' }
  $candidates=$null
  $activated=$script:Cache.Activate()
  try { try { $candidates=$ownerRoot.FindAll([System.Windows.Automation.TreeScope]::Descendants,$enabled) } catch { $candidates=$null } }
  finally { $activated.Dispose() }
  if($null -eq $candidates){ return $null }
  $half=[double]$box.w*[double]$box.h/2
  $best=$null;$bestArea=0.0;$named=$null;$checked=0
  foreach($el in $candidates){
    if(++$checked -gt 4000){ break }
    try {
      $rect=Get-Rect $el
      if(-not (Test-RectWithin $box $rect)){ continue }
      $area=[double]$rect.w*[double]$rect.h
      if($area -lt $half){ continue }
      if($null -eq $named -and $title.Length -gt 0 -and [string]::Equals([string]$el.Cached.Name,$title,[StringComparison]::OrdinalIgnoreCase)){ $named=$el }
      if($area -gt $bestArea){ $best=$el;$bestArea=$area }
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  $dialog=$named; if($null -eq $dialog){ $dialog=$best }
  if($null -eq $dialog){ return $null }
  $inside=New-Object System.Collections.Generic.List[object]
  foreach($el in (Get-ShownDescendants $dialog 0)){ if(Test-RectWithin $box (Get-Rect $el)){ $inside.Add($el) } }
  if((Measure-ClientPieces @(foreach($el in $inside){ Get-Piece $el }) $box) -eq 0){ return $null }
  return @{ from='owner'; items=$inside; root=$dialog }
}
# La raiz de contenido que la ultima vista de esta ventana tomo bajo su duena (Find-ById y Do-Click la prueban
# tambien), o nada.
# Revision de la palanca 8 (hallazgo 3): la relectura (a) ofrecio controles que el arbol marca fuera de pantalla. Un
# control asi se puede usar si la ultima vista de su ventana vino de esa relectura («unfiltered») y su rectangulo cae
# dentro de la caja de la ventana; uno sin rectangulo o fuera de ella, no. Un control visible vale siempre.
function Test-OffscreenUsable([bool]$offscreen,$rect,$box){
  if(-not $offscreen){ return $true }
  return (Test-RectWithin $box $rect)
}
# La caja de la ventana de esta raiz si su ultima vista se leyo sin el filtro IsOffscreen; si no, nada.
function Get-UnfilteredBox($root){
  if($null -eq $script:LastView -or -not $script:LastView.unfiltered){ return $null }
  $hwnd=0
  try { $hwnd=[long]$root.Current.NativeWindowHandle } catch { return $null }
  if($hwnd -eq 0 -or $hwnd -ne [long]$script:LastView.hwnd){ return $null }
  return (Get-WindowBox ([IntPtr]$hwnd))
}
function Get-ClientRootFor([IntPtr]$hwnd){
  if($null -eq $script:LastView.client -or $script:LastView.hwnd -ne $hwnd){ return $null }
  return $script:LastView.client
}
# Ronda 21: donde se busca un control por nombre o por identidad. Sin la caja de una vista leida sin el filtro
# IsOffscreen (lo unico que acepta lo marcado fuera de pantalla), el recorrido de lo visible con plazo y todas sus filas
# que se ven; si el plazo corta el recorrido, la busqueda lo dice (visible_lookup_timeout) y no que no hay nada.
function Get-LookupScope($root,$offscreenBox){
  if($null -ne $offscreenBox){ return (Get-Descendants $root) }
  $hwnd=0
  try { $hwnd=[long]$root.Current.NativeWindowHandle } catch { $hwnd=0 }
  $script:AllRows=$true
  try { $scope=Get-ShownDescendants $root $hwnd $script:LookupSeconds } finally { $script:AllRows=$false }
  if($script:Partial){ $script:LookupPartial=$true }
  return $scope
}
# Revision 1 de la ronda 21 (hallazgo 4): la busqueda por nombre cortada por su plazo no decide (ni unico ni ausente);
# la identidad que dio la vista si, porque es una sola.
function Test-NamedLookupCut([string]$controlId,[bool]$partial){
  return ($partial -and [string]::IsNullOrWhiteSpace($controlId))
}
# Los nombres que solo llevan la etiqueta, vistos por la ultima busqueda por nombre de un clic (auditoria C10).
$script:NamedCandidates=@()
function Find-Named($root,[string[]]$aliases,$offscreenBox=$null){
  $script:NamedLineage=@()
  $matches=@()
  $all=@(Get-LookupScope $root $offscreenBox)
  $script:TreeSize=$all.Count
  $askAliases=$(if($null -ne $script:AskSearch){ Get-AskAliases $aliases } else { $null })
  $compare=[Globalization.CultureInfo]::InvariantCulture.CompareInfo
  $options=[Globalization.CompareOptions]::IgnoreCase -bor [Globalization.CompareOptions]::IgnoreNonSpace
  foreach($item in $all){
    try {
      if(-not (Test-OffscreenUsable ([bool]$item.Cached.IsOffscreen) (Get-Rect $item) $offscreenBox)){ continue }
      $name=(Get-ShownName $item).name
      $exact=Test-NameMatch $name $aliases
      if($exact){ if(-not (Test-SystemMenu $item)){ $matches+=@($item) } }
      elseif((Test-ItemHolds $item $aliases) -and $script:NamedCandidates -notcontains $name -and -not (Test-SystemMenu $item)){ $script:NamedCandidates+=@($name) }
      if(-not $exact -and $null -ne $askAliases -and $script:AskingName.Length -eq 0){
        $raw=[string]$item.Cached.Name
        foreach($alias in $askAliases){ if($compare.IndexOf($raw,$alias,$options) -ge 0){ Note-AskingName $raw $alias; break } }
      }
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  if($matches.Count -gt 1){ $matches=@(Merge-SharedViews $matches) }
  if($matches.Count -gt 1){
    $one=Select-LineageOne @($matches | ForEach-Object { Get-LineageEntry $_ })
    if($one -ge 0){
      $script:NamedLineage=@(for($k=0;$k -lt $matches.Count;$k++){ if($k -ne $one){ $matches[$k] } })
      return @($matches[$one])
    }
  }
  if($matches.Count -gt 1){
    # Palanca 7 (v3-61): de los que siguen siendo varios, solo cuentan los que se pulsan (Invoke, SelectionItem, Toggle o
    # ExpandCollapse); el Text o el Group sin patron de una tarjeta no son otro objetivo. Dos que se pulsan siguen ambiguos.
    $pressable=Select-PressableOne @($matches | ForEach-Object { Get-ClickFacts $_ })
    if($pressable -ge 0){ return @($matches[$pressable]) }
  }
  return $matches
}
# La posicion del unico que tiene un patron de pulsar, o -1 (ninguno, o mas de uno). Revision de la ronda 20b (hallazgo
# 4): un campo que toma texto (Edit o Document con valor escribible, la via 'target' de Select-ClickMethods) y un
# ComboBox son tambien objetivos de un clic: un campo «Buscar» junto a un boton «Buscar» sigue siendo ambiguo.
function Select-PressableOne($facts){
  $list=@($facts)
  $found=-1
  for($k=0;$k -lt $list.Count;$k++){
    $f=$list[$k]
    $field=((@('Edit','Document') -contains [string]$f.kind -and [bool]$f.value) -or [string]$f.kind -eq 'ComboBox')
    if([bool]$f.invoke -or [bool]$f.select -or [bool]$f.toggle -or [bool]$f.expand -or $field){
      if($found -ge 0){ return -1 }
      $found=$k
    }
  }
  return $found
}
# Ronda 20b, palanca 7 (v3-53): un Toggle que cambia la casilla no prueba que la aplicacion lo oyera. Si la ventana tiene
# un control hermano del mismo tipo y la misma plantilla de nombre (el nombre sin la parte entre comillas) que ya esta en
# el estado al que va el nuestro, la marca que ese hermano pone en los controles que lo nombran (un deslizador «... 'B':
# (actualmente silenciado)») debe aparecer tambien en los que nombran al nuestro. Sin hermano, o con su marca ya igual a
# la nuestra, nada que corroborar. Cada entrada: name, kind, toggle (On, Off o vacio).
function Get-NameParts([string]$name){
  $text=([string]$name).Trim()
  $m=[regex]::Match($text,'([''"\u00AB\u2018\u201C])([^''"\u00BB\u2019\u201D]+)([''"\u00BB\u2019\u201D])')
  if(-not $m.Success){ return @{ template=$text; key='' } }
  $template=($text.Substring(0,$m.Index)+$m.Groups[1].Value+$m.Groups[3].Value+$text.Substring($m.Index+$m.Length)).Trim()
  return @{ template=$template; key=$m.Groups[2].Value.Trim() }
}
function Get-ToggleWitness([string]$name,[string]$kind,[string]$before,$entries){
  if(@('On','Off') -notcontains $before){ return $null }
  $goal=$(if($before -eq 'On'){ 'Off' } else { 'On' })
  $own=Get-NameParts $name
  if($own.key.Length -eq 0){ return $null }
  $list=@($entries | ForEach-Object { @{ name=[string]$_.name; kind=[string]$_.kind; toggle=[string]$_.toggle; parts=(Get-NameParts ([string]$_.name)) } })
  foreach($sibling in $list){
    if($sibling.kind -ne $kind -or $sibling.toggle -ne $goal){ continue }
    if($sibling.parts.key.Length -eq 0 -or $sibling.parts.key -eq $own.key -or $sibling.parts.template -ne $own.template){ continue }
    $expect=@()
    foreach($other in $list){
      if($other.parts.key -ne $sibling.parts.key -or ($other.kind -eq $kind -and $other.parts.template -eq $own.template)){ continue }
      $mine=@($list | Where-Object { $_.kind -eq $other.kind -and $_.parts.key -eq $own.key -and -not ($_.kind -eq $kind -and $_.parts.template -eq $own.template) })
      $same=@($mine | Where-Object { $_.parts.template -eq $other.parts.template })
      if($same.Count -gt 0){ continue }
      # Solo el control nuestro que corresponde al marcado: el que tiene su plantilla como comienzo (o al reves).
      $paired=@($mine | Where-Object { $other.parts.template.StartsWith($_.parts.template.TrimEnd(':',' ')) -or $_.parts.template.StartsWith($other.parts.template.TrimEnd(':',' ')) })
      if($paired.Count -eq 1){ $expect+=@(@{ kind=$other.kind; template=$other.parts.template }) }
    }
    if($expect.Count -gt 0){ return @{ key=$own.key; expect=$expect } }
    return $null
  }
  return $null
}
function Test-ToggleWitnessed($witness,$entries){
  if($null -eq $witness){ return $true }
  foreach($wanted in @($witness.expect)){
    $held=@($entries | Where-Object { [string]$_.kind -eq [string]$wanted.kind -and (Get-NameParts ([string]$_.name)).key -eq [string]$witness.key -and (Get-NameParts ([string]$_.name)).template -eq [string]$wanted.template })
    if($held.Count -eq 0){ return $false }
  }
  return $true
}
# Los controles visibles de la ventana como entradas para el testigo del Toggle (el estado solo de los del tipo pedido).
function Get-WitnessEntries($root,[string]$kind){
  $out=@()
  foreach($item in @(Get-Descendants $root)){
    try {
      if($item.Cached.IsOffscreen){ continue }
      $itemKind=([string]$item.Cached.ControlType.ProgrammaticName) -replace '^ControlType\.',''
      $state=''
      if($itemKind -eq $kind){ $read=Get-Toggle $item; if($null -ne $read){ $state=[string]$read } }
      $out+=@(@{ name=[string]$item.Cached.Name; kind=$itemKind; toggle=$state })
    } catch {}
  }
  return $out
}
# El testigo se relee hasta 600 ms (la aplicacion pone la marca al oir el cambio).
function Wait-ToggleWitness($pending){
  for($look=0;$look -lt 12;$look++){
    if(Test-ToggleWitnessed $pending.witness (Get-WitnessEntries $pending.root $pending.kind)){ return $true }
    Start-Sleep -Milliseconds 50
  }
  return $false
}
# La via siguiente para un Toggle que la aplicacion no oyo: el Toggle de nuevo deja la casilla como la aplicacion la
# tiene (nunca oyo el primero), y la pulsacion enviada a su ventana nativa, en su punto, la cambia por la via que escucha.
# Solo en un marco cuya ventana lee los mensajes del raton (Win32, WinForms o NativeItemFrameworks).
function Send-ToggleByMessage($pending){
  if(-not [bool]$pending.messageable){ return $false }
  $button=$pending.element
  $pattern=$null
  try {
    [void]$button.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)
    ([System.Windows.Automation.TogglePattern]$pattern).Toggle()
  } catch { return $false }
  if((Get-Toggle $button) -ne $pending.toggleBefore){ return $false }
  $point=Get-PressPoint $button
  if($null -eq $point -or -not (Test-PointIsElement $button $point)){ return $false }
  if(-not [BaxyUiaWorkerNative]::PostClick($pending.top,$point.x,$point.y,(Get-HolderWindow $button))){ return $false }
  for($look=0;$look -lt 8;$look++){
    if((Get-Toggle $button) -ne $pending.toggleBefore){ return $true }
    Start-Sleep -Milliseconds 50
  }
  return $false
}
function Click-Result([bool]$ok,[bool]$effect,[string]$error,[string]$name,[string]$identity,[bool]$absent,[bool]$selected,[bool]$toggled,[string]$kind){
  return @{ version=2; ok=$ok; effectObserved=$effect; error=$error; name=$name; kind=$kind; controlIdentity=$identity; absentOrDisabled=$absent; selected=$selected; toggled=$toggled; surfaceChanged=$false; cascadeStage='uia'; authority='windows_uia_or_win32_button_postread' }
}
# El clic responde en cuanto invoca («pending»): el adaptador pide «postread»
# cada 50 ms mientras compara la superficie, y se queda con la primera prueba
# (antes: 150 ms de espera previa y 20 x 100 ms de sondeo, 2,6-3,1 s por clic
# en una ventana Electron/CEF que no cambia de estado UIA).
$script:Pending=$null
function Pending-Result($pending){
  $result=Click-Result $false $true 'visible_button_postread_pending' $pending.name $pending.identity $false $false $false $pending.kind
  $result.pending=$true
  $result.method=[string]$pending.method
  return $result
}
# Ronda 21: la marca (Toggle) de cada uno de la linea del mismo nombre antes del clic, y si alguna cambio despues.
function Get-LineageToggles($lineage){
  $out=@()
  foreach($el in @($lineage)){ if($null -eq $el){ continue }; $before=Get-Toggle $el; if($null -ne $before){ $out+=@(@{ el=$el; before=$before }) } }
  return $out
}
function Test-LineageToggled($toggles){
  foreach($entry in @($toggles)){
    if($null -eq $entry){ continue }
    $now=$null
    try { $now=Get-Toggle $entry.el } catch { $now=$null }
    if($null -ne $now -and $now -ne $entry.before){ return $true }
  }
  return $false
}
function Do-Postread($request){
  $pending=$script:Pending
  if($null -eq $pending){ return (Click-Result $false $false 'visible_click_no_pending' '' '' $false $false $false '') }
  $absent=$false;$selected=$false;$toggled=$false;$fieldTook=$false
  if($null -ne $pending.command){
    # Una entrada del menu clasico: su marca, releida por su orden; marcada ahora y no antes, la eligio.
    $now=[BaxyUiaWorkerNative]::MenuCommandState($pending.top,[int]$pending.command)
    if($now -ge 0 -and [int]$pending.commandBefore -ge 0 -and (($now -band 8) -ne ([int]$pending.commandBefore -band 8))){
      if(($now -band 8) -ne 0){ $selected=$true } else { $toggled=$true }
    }
  } elseif($null -ne $pending.native){
    $handle=$pending.native
    $absent=(-not [BaxyUiaWorkerNative]::IsWindow($handle)) -or (-not [BaxyUiaWorkerNative]::IsWindowVisible($handle)) -or (-not [BaxyUiaWorkerNative]::IsWindowEnabled($handle))
  } else {
    $button=$pending.element
    try {
      if(-not $button.Current.IsEnabled -or $button.Current.IsOffscreen){$absent=$true}
      # Revision B3, hallazgo 6: el primer DOWN de un doble clic ya selecciona el elemento; su seleccion no prueba que
      # la aplicacion lo abriera (eso lo dice que se fuera o que la ventana cambiara).
      # Ronda 21 (t-menu-2): tampoco la de un menu contextual ni la de una apertura por su flecha: el elemento ya estaba
      # elegido antes del acto (un nodo de arbol) y su marca no dice que algo se abriera. Solo cuentan el menu leido
      # abierto (Invoke-MannerControl), un popup nacido o el cambio de la superficie, que mira el adaptador despues.
      elseif([string]$pending.manner -eq 'double' -or [string]$pending.manner -eq 'menu' -or [string]$pending.manner -eq 'open'){}
      # Revision de la ronda 20b (hallazgo 3): una eleccion cuyo Select dejo la fila marcada sin mover el lugar (Qt) no
      # se prueba con esa marca: solo con el lugar movido (titulo o nombres de la ventana), releido hasta 600 ms; si no
      # se movio, el efecto de la pulsacion enviada queda incierto (la superficie redibujo la marca del Select).
      elseif($null -ne $pending.placeBefore){
        if(Wait-PlaceMoved $pending.placeBefore $pending.top){ $selected=$true; $pending.placeMoved=$true }
        # Ronda 24b: el lugar ya estaba elegido por la via anterior (su marca es cierta) y la pulsacion no lo movio: el
        # recibo dice elegido sin llegar.
        elseif([bool]$pending.chosenAlready -and (Test-Selected $button)){ $selected=$true; $pending.placeMoved=$false }
        else {
          $script:Pending=$null
          $doubt=Click-Result $false $true 'visible_choice_uncorroborated' $pending.name $pending.identity $false $false $false $pending.kind
          $doubt.method=[string]$pending.method
          $doubt.effectUncertain=$true
          return $doubt
        }
      }
      elseif(Test-Selected $button){$selected=$true}
      elseif(@($pending.lineage | Where-Object { Test-Selected $_ }).Count -gt 0){$selected=$true}
      elseif($null -ne $pending.toggleBefore){ $after=Get-Toggle $button; if($null -ne $after -and $after -ne $pending.toggleBefore){$toggled=$true} }
      # Ronda 21 (t-drag-4): la marca de otro de su linea del mismo nombre (el Button de una galeria cuyo ListItem se
      # pulso, o al reves) tambien prueba el clic. Integracion de la ronda 21 (t-menu-2): no la de un doble clic, un menu
      # contextual ni una apertura por su flecha, a los que la marca del propio elemento tampoco prueba.
      if(-not $selected -and -not $toggled -and @('double','menu','open') -notcontains [string]$pending.manner -and $null -eq $pending.placeBefore -and
         (Test-LineageToggled $pending.lineageToggles)){ $toggled=$true }
      if(-not $selected -and -not $toggled -and $null -ne $pending.fieldBefore){ $fieldTook=Test-FieldTook $button $pending.fieldBefore }
    }
    catch [System.Windows.Automation.ElementNotAvailableException] {$absent=$true}
  }
  if($toggled -and -not $absent -and $null -ne $pending.witness){
    # Palanca 7: el cambio de la casilla solo vale con el testigo de su hermano; si no aparece, la via siguiente una vez.
    $seen=Wait-ToggleWitness $pending
    if(-not $seen -and -not [bool]$pending.retried){
      $pending.retried=$true
      if(Send-ToggleByMessage $pending){ $pending.method='message'; $seen=Wait-ToggleWitness $pending }
    }
    if(-not $seen){
      $script:Pending=$null
      $doubt=Click-Result $false $true 'visible_toggle_uncorroborated' $pending.name $pending.identity $false $false $false $pending.kind
      $doubt.method=[string]$pending.method
      $doubt.effectUncertain=$true
      return $doubt
    }
  }
  # Un dialogo modal deshabilita a su dueno: la ventana del clic, habilitada antes y deshabilitada ahora, abrio uno.
  $dialog=($pending.topEnabled -eq $true -and $null -ne $pending.top -and -not [BaxyUiaWorkerNative]::IsWindowEnabled($pending.top))
  if($fieldTook -or $dialog){
    $script:Pending=$null
    $took=Click-Result $true $true '' $pending.name $pending.identity $false $false $false $pending.kind
    $took.method=[string]$pending.method
    # Revision (hallazgo 1): sus propias claves, que el adaptador reconoce como prueba (PostreadHolds).
    if($fieldTook){ $took.fieldTook=$true }
    if($dialog){ $took.dialogOpened=$true }
    if($pending.blocked){ $took.blocked=$true }
    return $took
  }
  if(-not $absent -and -not $selected -and -not $toggled){
    $unchanged=Click-Result $false $true 'visible_button_postread_unchanged' $pending.name $pending.identity $false $false $false $pending.kind
    $unchanged.method=[string]$pending.method
    return $unchanged
  }
  $script:Pending=$null
  $held=Click-Result $true $true '' $pending.name $pending.identity $absent $selected $toggled $pending.kind
  $held.method=[string]$pending.method
  # Ronda 24b: si el lugar se movio con la eleccion (nodo de arbol, pestana), para la mente.
  if($null -ne $pending.placeMoved){ $held.placeMoved=[bool]$pending.placeMoved }
  # Revision 1 (B3): la pulsacion que aun no se habia dado al elegir (bloqueada) dice aqui si movio el lugar.
  elseif($null -ne $pending.steadyBefore -and $null -ne $pending.steadyTop){ $held.placeMoved=[bool](Wait-PlaceMoved $pending.steadyBefore $pending.steadyTop) }
  return $held
}
# Recibo del clic por estado (r15b v3-42): en un campo (Edit, Document, ComboBox) el efecto de un clic es que tome el
# foco del teclado o que cambie su valor; su lectura antes del clic y la comparacion despues.
function Get-FieldState($el){
  $state=@{ focus=$false; value=$null }
  try { $state.focus=[bool]$el.Current.HasKeyboardFocus } catch {}
  try {
    $pattern=$null
    if($el.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)){ $state.value=[string]([System.Windows.Automation.ValuePattern]$pattern).Current.Value }
  } catch {}
  return $state
}
function Test-FieldTook($el,$before){
  $now=Get-FieldState $el
  return (($now.focus -and -not $before.focus) -or ($null -ne $before.value -and $null -ne $now.value -and $now.value -ne $before.value))
}
# Lo que responde un control ya pulsado (o designado) por Invoke-NamedControl: el campo destino responde en el acto;
# el puntero responde sin efecto, con el punto que el adaptador pulsara; el resto queda pendiente de su postread.
function Pressed-Result($done,$button,[string]$name,[string]$identity,[string]$kind,$toggleBefore,$lineage){
  if($done.method -eq 'target'){
    $result=Click-Result $true $true '' $name $identity $false $false $false $kind
    $result.method='target'; $result.targeted=$true; $result.focused=[bool]$done.focused
    if(([string]$done.via).Length -gt 0){ $result.via=[string]$done.via }
    return $result
  }
  # Las marcas de la linea leidas por Do-Click antes de pulsar valen solo para esta pulsacion.
  $lineageToggles=@($script:LineageToggles); $script:LineageToggles=@()
  $script:Pending=@{ native=$null; element=$button; toggleBefore=$toggleBefore; lineage=$lineage; lineageToggles=$lineageToggles; name=$name; identity=$identity; kind=$kind; method=$done.method; blocked=[bool]$done.blocked; placeBefore=$done.placeBefore; placeMoved=$done.placeMoved; chosenAlready=[bool]$done.chosenAlready; steadyBefore=$done.steadyBefore; steadyTop=$done.steadyTop }
  $result=Pending-Result $script:Pending
  if($done.blocked){ $result.blocked=$true }
  if($done.selectable){ $result.selectable=$true }
  if(@($done.ways).Count -gt 1){ $result.ways=@($done.ways) }
  if($done.method -eq 'pointer'){
    $result.pending=$false; $result.effectObserved=$false; $result.error='visible_click_needs_pointer'
    $result.needsPointer=$true; $result.point=$done.point; $result.rect=$done.rect; $result.legacyStep=[string]$done.legacyStep
    if(([string]$done.renderStep).Length -gt 0){ $result.renderStep=[string]$done.renderStep }
  }
  return $result
}
# Las ventanas de contenido de la familia que el adaptador manda con el clic («hosts»), como manejadores.
function Read-RenderHosts($request){
  $hosts=@()
  foreach($value in @($request.hosts)){ try { if([long]$value -gt 0){ $hosts+=[IntPtr][long]$value } } catch {} }
  return $hosts
}
# La entrada se pulsa con el WM_COMMAND que su ventana recibe del menu: sin frente, sin cursor y sin abrir el menu. Su
# recibo queda pendiente del postread (su marca cambiada, un dialogo) o de la superficie que compara el adaptador.
function Press-MenuCommand($target,[string[]]$aliases,[string]$controlId){
  $menuEntries=@()
  try { $menuEntries=@([BaxyUiaWorkerNative]::MenuEntries($target.hwnd,$script:MenuEntriesMax)) } catch { $menuEntries=@() }
  $chosen=Find-MenuCommand $menuEntries $aliases $controlId
  if($null -eq $chosen.entry){ return (Click-Result $false $false ([string]$chosen.error) '' $controlId $false $false $false 'MenuItem') }
  $entry=$chosen.entry
  $id=[int]$entry.Id
  $identity='hmenu.'+$id
  $topEnabled=[bool][BaxyUiaWorkerNative]::IsWindowEnabled($target.hwnd)
  $before=[BaxyUiaWorkerNative]::MenuCommandState($target.hwnd,$id)
  if(-not [BaxyUiaWorkerNative]::PostCommand($target.hwnd,$id)){ return (Click-Result $false $false 'visible_button_not_invokable' ([string]$entry.Path) $identity $false $false $false 'MenuItem') }
  $script:Pending=@{ native=$null; element=$null; command=$id; commandBefore=$before; toggleBefore=$null; lineage=@(); name=[string]$entry.Path; identity=$identity; kind='MenuItem'; method='command'; top=$target.hwnd; topEnabled=$topEnabled }
  return (Pending-Result $script:Pending)
}
# Ronda 21: el elemento y los de su linea (hasta $script:LineageUp antecesores y $script:LineageDown niveles de hijos,
# como mucho $script:LineageNodes) que se llaman exactamente igual. Un nombre distinto corta la union: un ListItem
# «Documento» con un Button «Eliminar» dentro es solo el ListItem.
$script:LineageUp=3
$script:LineageDown=2
$script:LineageNodes=40
function Test-SameShownName($el,[string]$name){
  try { return [string]::Equals((Get-ShownName $el).name,$name,[StringComparison]::OrdinalIgnoreCase) } catch { return $false }
}
function Get-LineageWalker(){ return [System.Windows.Automation.TreeWalker]::RawViewWalker }
function Get-SameNameLineage($el){
  $line=@($el)
  $name=''
  try { $name=(Get-ShownName $el).name } catch { $name='' }
  if([string]::IsNullOrWhiteSpace($name)){ return $line }
  $walker=Get-LineageWalker
  try {
    $up=$walker.GetParent($el)
    for($steps=0;$null -ne $up -and $steps -lt $script:LineageUp;$steps++){
      if(-not (Test-SameShownName $up $name)){ break }
      $line+=@($up)
      $up=$walker.GetParent($up)
    }
  } catch {}
  $level=@($el);$visited=0
  for($depth=0;$depth -lt $script:LineageDown -and $level.Count -gt 0;$depth++){
    $next=@()
    foreach($node in $level){
      try {
        $child=$walker.GetFirstChild($node)
        while($null -ne $child -and $visited -lt $script:LineageNodes){
          $visited++
          if(Test-SameShownName $child $name){ $line+=@($child) }
          $next+=@($child)
          $child=$walker.GetNextSibling($child)
        }
      } catch {}
    }
    $level=$next
  }
  return $line
}
# Revision 1 de ronda 21: el elegido por su identidad que se pulsa por si mismo (Invoke), se alterna (Toggle: una
# CheckBox, un ToggleSwitch) o se despliega (ExpandCollapse) es el objetivo: la linea del mismo nombre no lo desvia (una
# CheckBox «Recordatorio» dentro de su fila homonima seguia la fila, y un interruptor «Bluetooth» dentro de su tarjeta
# Button pulsaba la tarjeta). Solo el que no hace nada de eso (el ListItem de una galeria que solo se selecciona, con su
# Button homonimo dentro: t-drag-4) se resuelve en su linea.
function Test-ActsByItself($entry){
  return ($null -ne $entry -and ([bool]$entry.invoke -or [bool]$entry.toggle -or [bool]$entry.expand))
}
function Resolve-ByIdLineage($byId){
  $out=@{ target=$byId; lineage=@() }
  if(Test-ActsByItself (Get-LineageEntry $byId)){ return $out }
  $line=@(Get-SameNameLineage $byId)
  if($line.Count -gt 1){
    $one=Select-LineageOne @($line | ForEach-Object { Get-LineageEntry $_ })
    if($one -ge 0){
      $out.lineage=@(for($k=0;$k -lt $line.Count;$k++){ if($k -ne $one){ $line[$k] } })
      $out.target=$line[$one]
    }
  }
  return $out
}
function Do-Click($request){
  $script:Pending=$null
  $script:LookupPartial=$false
  $script:AskSearch=$request.asks
  $script:AskingName=''
  try { return (Do-ClickJudged $request) } finally { $script:AskSearch=$null }
}
function Do-ClickJudged($request){
  $script:RenderHosts=@(Read-RenderHosts $request)
  $aliases=@($request.aliases | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  $controlId=[string]$request.controlId
  $manner=[string]$request.manner
  # Goal v3 B3: otra manera de pulsar solo por la identidad que dio la vista.
  if($manner.Length -gt 0 -and [string]::IsNullOrWhiteSpace($controlId)){ return (Click-Result $false $false 'visible_click_argument_invalid' '' '' $false $false $false '') }
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return (Click-Result $false $false 'active_window_not_found' '' '' $false $false $false '') }
  $root=$target.root
  $matches=@()
  $script:NamedLineage=@()
  $script:LineageToggles=@()
  $script:NamedCandidates=@()
  if($controlId.StartsWith('hmenu.')){
    if($manner.Length -gt 0){ return (Click-Result $false $false 'visible_click_argument_invalid' '' $controlId $false $false $false 'MenuItem') }
    return (Press-MenuCommand $target $aliases $controlId)
  }
  if(-not [string]::IsNullOrWhiteSpace($controlId)){
    $byId=Find-ById $root $controlId
    if($null -eq $byId -and $script:LookupPartial){ return (Click-Result $false $false 'visible_lookup_timeout' '' $controlId $false $false $false '') }
    if($null -eq $byId){ return (Click-Result $false $false 'visible_control_identity_stale' '' $controlId $false $false $false '') }
    if($aliases.Count -gt 0 -and -not (Test-NameMatch (Get-ShownName $byId).name $aliases)){
      return (Click-Result $false $false 'visible_control_label_mismatch' (Get-ShownName $byId).name $controlId $false $false $false '')
    }
    $matches=@($byId)
    # Ronda 21 (t-drag-4): por su identidad tambien se pulsa la linea de descendencia del mismo nombre (el ListItem de
    # una galeria y el Button de dentro, los dos «Linea»): Select-LineageOne elige el que se invoca y los demas quedan
    # en NamedLineage, cuya seleccion o marca tambien prueba el clic. Un hijo de otro nombre nunca se une, y un elegido
    # que actua por si mismo nunca se desvia (Resolve-ByIdLineage).
    $resolved=Resolve-ByIdLineage $byId
    $script:NamedLineage=@($resolved.lineage)
    $matches=@($resolved.target)
  } elseif($aliases.Count -gt 0) {
    $matches=@(Find-Named $root $aliases)
    # Revision de la palanca 8 (hallazgo 3): nada visible con ese nombre y la ultima vista vino sin el filtro
    # IsOffscreen: se busca otra vez aceptando lo marcado fuera de pantalla dentro de la caja de la ventana.
    $offscreenBox=Get-UnfilteredBox $root
    if($matches.Count -eq 0 -and $null -ne $offscreenBox){ $matches=@(Find-Named $root $aliases $offscreenBox) }
    # Ronda 20b, palanca 8: un dialogo cuyo contenido cuelga de su ventana duena se busca alli, solo dentro de el.
    $client=Get-ClientRootFor $target.hwnd
    if($matches.Count -eq 0 -and $null -ne $client){
      $box=Get-WindowBox $target.hwnd
      $matches=@(Find-Named $client $aliases | Where-Object { try { Test-RectWithin $box (Get-CurrentRect $_) } catch { $false } })
    }
  } else {
    return (Click-Result $false $false 'visible_click_argument_invalid' '' '' $false $false $false '')
  }
  if($controlId.Length -eq 0 -and $script:AskingName.Length -gt 0 -and
     @($matches | Where-Object { Test-NameMatch (Get-ShownName $_).name $aliases }).Count -eq 0){
    return (Click-Result $false $false 'visible_control_needs_confirmation' $script:AskingName '' $false $false $false '')
  }
  # Revision 1 de la ronda 21 (hallazgo 4): una busqueda por nombre que el plazo corto no prueba que el control falte
  # ni que sea el unico con ese rotulo (otro igual pudo quedar en lo no recorrido): responde antes de pulsar nada.
  if(Test-NamedLookupCut $controlId $script:LookupPartial){ return (Click-Result $false $false 'visible_lookup_timeout' (Get-Name $root) '' $false $false $false '') }
  if($matches.Count -eq 0){
    $native=@([BaxyUiaWorkerNative]::FindVisibleButtons($target.hwnd,[string[]]$aliases))
    if($native.Count -gt 1){ return (Click-Result $false $false 'visible_button_ambiguous' '' '' $false $false $false '') }
    if($native.Count -eq 1){
      $nativeButton=$native[0];$name=[BaxyUiaWorkerNative]::Text($nativeButton);$identity=('hwnd.'+$nativeButton.ToInt64())
      [BaxyUiaWorkerNative]::Click($nativeButton)
      $script:Pending=@{ native=$nativeButton; element=$null; toggleBefore=$null; name=$name; identity=$identity; kind='Button'; method='message' }
      return (Pending-Result $script:Pending)
    }
    if($controlId.Length -eq 0 -and $manner.Length -eq 0){
      # Palanca 7: lo que el arbol no tiene puede ser una entrada del menu clasico de la ventana.
      $menuPress=Press-MenuCommand $target $aliases ''
      if([string]$menuPress.error -ne 'visible_button_not_found'){ return $menuPress }
    }
    $missing=Click-Result $false $false 'visible_button_not_found' (Get-Name $root) '' $false $false $false ''
    if($controlId.Length -eq 0){ $missing.treeSize=$script:TreeSize }
    # Auditoria C10: los items cuyo titulo lleva la etiqueta, sin pulsar ninguno (Find-Named).
    if($script:NamedCandidates.Count -gt 0){ $missing.candidates=@($script:NamedCandidates | Select-Object -First 10) }
    return $missing
  }
  if($matches.Count -ne 1){ return (Click-Result $false $false 'visible_button_ambiguous' '' '' $false $false $false '') }
  $button=$matches[0];$name=(Get-ShownName $button).name;$identity=Get-Id $button
  $kind=$button.Current.ControlType.ProgrammaticName -replace '^ControlType\.',''
  # Encargo V: por su identidad, en su manera o por su etiqueta, lo que pide mas que su etiqueta no se pulsa (Get-AskingName).
  $asking=Get-AskingName $button $name $aliases $request.asks
  if($asking.Length -gt 0){ return (Click-Result $false $false 'visible_control_needs_confirmation' $asking $identity $false $false $false $kind) }
  $toggleBefore=Get-Toggle $button
  # El mismo objetivo en su linea de descendencia (el ListItem del Button
  # invocado): su seleccion tras el clic tambien lo prueba, si antes no lo estaba.
  $lineage=@($script:NamedLineage | Where-Object { -not (Test-Selected $_) })
  $script:LineageToggles=@(Get-LineageToggles $script:NamedLineage)
  $done=$null
  if($manner.Length -gt 0){
    try { $done=Invoke-MannerControl $button $root $target.hwnd $manner }
    catch { return (Click-Result $false $false 'visible_button_not_invokable' $name $identity $false $false $false $kind) }
    if(([string]$done.error).Length -gt 0){
      $refused=Click-Result $false $false ([string]$done.error) $name $identity $false $false $false $kind
      if(([string]$done.legacyStep).Length -gt 0){ $refused.legacyStep=[string]$done.legacyStep }
      return $refused
    }
    if($done.opened){
      # La lista o el menu se leen abiertos: esa es la prueba del paso.
      $held=Click-Result $true $true '' $name $identity $false $false $false $kind
      $held.method=[string]$done.method; $held.opened=$true; $held.manner=$manner
      return $held
    }
    if($done.closed){
      # La lista que la mision dejo abierta se lee cerrada: esa es la prueba del cierre.
      $held=Click-Result $true $true '' $name $identity $false $false $false $kind
      $held.method=[string]$done.method; $held.closed=$true; $held.manner=$manner
      return $held
    }
    $pending=Pressed-Result $done $button $name $identity $kind $toggleBefore $lineage
    $pending.manner=$manner
    if($null -ne $script:Pending){ $script:Pending.manner=$manner }
    return $pending
  }
  $fieldBefore=$(if(@('Edit','Document','ComboBox') -contains $kind){ Get-FieldState $button } else { $null })
  $topEnabled=[bool][BaxyUiaWorkerNative]::IsWindowEnabled($target.hwnd)
  # Palanca 7 (v3-53): el testigo de un Toggle se lee antes de pulsar (el hermano y su marca, tal como estan ahora).
  $witness=$null
  if($null -ne $toggleBefore){
    try { $witness=Get-ToggleWitness $name $kind ([string]$toggleBefore) @(Get-WitnessEntries $root $kind) } catch { $witness=$null }
  }
  try { $done=Invoke-NamedControl $button $target.hwnd }
  catch { return (Click-Result $false $false 'visible_button_not_invokable' $name $identity $false $false $false $kind) }
  if($null -eq $done){ return (Click-Result $false $false 'visible_button_not_invokable' $name $identity $false $false $false $kind) }
  if([string]$done.method -eq 'container'){ return (Click-Result $false $false 'visible_control_is_container' $name $identity $false $false $false $kind) }
  $pressed=Pressed-Result $done $button $name $identity $kind $toggleBefore $lineage
  if($null -ne $script:Pending){ $script:Pending.fieldBefore=$fieldBefore; $script:Pending.top=$target.hwnd; $script:Pending.topEnabled=$topEnabled }
  if($null -ne $script:Pending -and $null -ne $witness -and [string]$done.method -eq 'toggle'){
    $facts=Get-ClickFacts $button
    $script:Pending.witness=$witness; $script:Pending.root=$root; $script:Pending.retried=$false
    $script:Pending.messageable=([bool]$facts.classic -or [bool]$facts.native)
  }
  return $pressed
}
# El nombre de un control o el texto de dentro lleva la etiqueta: igual, o como palabras enteras. Auditoria P3: aqui no
# se elige un control por su nombre; el punto es donde el OCR o la vision leyeron la etiqueta exacta, y esto solo
# comprueba que lo que hay en ese punto la lleva (una fila de chat «Juan Perez 12:30 Hola» donde se leyo «Juan Perez»).
function Test-NamesLabel($names,[string[]]$aliases){
  foreach($name in @($names)){
    $text=[string]$name
    if([string]::IsNullOrWhiteSpace($text)){ continue }
    if((Test-NameMatch $text $aliases) -or (Test-NameHolds $text $aliases)){ return $true }
  }
  return $false
}
# Los candidatos de un punto, del mas interior al mas exterior, cada uno con sus nombres (el suyo y los del texto de
# dentro que se leyo) y su area: las posiciones de los que la etiqueta nombra sin pasar del limite (un cuarto de la
# ventana; 0 = sin limite), en ese orden. Ninguno: nada se pulsa sin raton.
# Un lugar recordado de un icono sin nombre (CONTRATO §8.2): un control del punto de hasta cuatro veces su area con un
# nombre (dos letras al menos) es otro control que esta ahi ahora. Sin area conocida, ninguno lo es.
function Test-NamedOther($entries,[double]$most){
  if($most -le 0){ return $false }
  foreach($entry in @($entries)){
    $area=[double]$entry.area
    if($area -le 0 -or $area -gt $most){ continue }
    foreach($name in @($entry.names)){ if(([string]$name) -match '\p{L}.*\p{L}'){ return $true } }
  }
  return $false
}
function Select-PointHolders($entries,[string[]]$aliases,[double]$limit){
  $chosen=@()
  $list=@($entries)
  for($k=0;$k -lt $list.Count;$k++){
    $area=[double]$list[$k].area
    if($area -le 0){ continue }
    if($limit -gt 0 -and $area -gt $limit){ continue }
    if(Test-NamesLabel $list[$k].names $aliases){ $chosen+=@($k) }
  }
  return $chosen
}
# Lo que se ve en el punto: el elemento que da FromPoint (el orden de apilado ya resuelto: una capa o un modal tapa lo
# de debajo) y sus antecesores hasta la ventana, sin ella. Nulo si ese elemento no es de la ventana (otra la tapa ahi).
function Get-PointChain($root,[double]$x,[double]$y){
  $hit=$null
  try { $hit=$AE::FromPoint((New-Object System.Windows.Point($x,$y))) } catch { return $null }
  if($null -eq $hit){ return $null }
  $walker=[System.Windows.Automation.TreeWalker]::ControlViewWalker
  $chain=New-Object System.Collections.ArrayList
  $node=$hit
  for($steps=0;$null -ne $node -and $steps -lt 60;$steps++){
    try { if([System.Windows.Automation.Automation]::Compare($node,$root)){ return ,$chain } } catch { return $null }
    [void]$chain.Add($node)
    try { $node=$walker.GetParent($node) } catch { return $null }
  }
  return $null
}
# Los nombres de un control y del texto de dentro (acotado).
function Get-SubtreeNames($el){
  $names=@(Get-Name $el)
  try {
    $activated=$script:Cache.Activate()
    try { $inner=$el.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition) }
    finally { $activated.Dispose() }
    $count=0
    foreach($child in $inner){ if($count -ge 200){ break }; $names+=@(Get-Name $child); $count++ }
  } catch {}
  return $names
}
# Un punto de la ventana (lo que leyo el OCR o la vision), pulsado sin raton cuando se puede: el control con patron
# (o campo que toma texto) del punto cuyo nombre, o el texto de dentro, es la etiqueta leida. Con la ventana visible en
# el punto, la cadena de FromPoint (lo que se ve, no lo que queda debajo de una capa); con la ventana tapada ahi, los
# controles cuyo rectangulo contiene el punto (los rectangulos del arbol valen aunque este tapada), del mas pequeno
# al mas grande. Un control que ocupa mas de un cuarto de la ventana no es «el control de ese punto». Sin ninguno que
# la etiqueta nombre, nada se pulsa y el adaptador decide el puntero.
# Si el punto cae en el control ya pulsado (su identidad entre los que contienen el punto, el o un antepasado).
function Test-HoldsPressed([string[]]$ids,[string]$pressed){
  if([string]::IsNullOrEmpty($pressed)){ return $false }
  return (@($ids) -contains $pressed)
}
function Do-At($request){
  $script:Pending=$null
  $script:RenderHosts=@(Read-RenderHosts $request)
  $aliases=@($request.aliases | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return (Click-Result $false $false 'active_window_not_found' '' '' $false $false $false '') }
  $x=[double]$request.x; $y=[double]$request.y
  $limit=0
  try { $frame=$target.root.Current.BoundingRectangle; if(-not $frame.IsEmpty){ $limit=$frame.Width*$frame.Height/4 } } catch {}
  $entries=New-Object System.Collections.ArrayList
  $chain=Get-PointChain $target.root $x $y
  if($null -ne $chain){
    $seen=@()
    foreach($node in $chain){
      try {
        $seen+=@(Get-Name $node)
        $box=$node.Current.BoundingRectangle
        $area=$(if($box.IsEmpty){ 0 } else { $box.Width*$box.Height })
        [void]$entries.Add([pscustomobject]@{ element=$node; area=$area; names=@($seen) })
      } catch [System.Windows.Automation.ElementNotAvailableException] {}
    }
  } else {
    $hits=New-Object System.Collections.ArrayList
    foreach($item in (Get-Descendants $target.root)){
      try {
        if($item.Cached.IsOffscreen){ continue }
        $box=$item.Cached.BoundingRectangle
        if($box.IsEmpty -or $box.Width -le 0 -or $box.Height -le 0){ continue }
        if($x -lt $box.X -or $y -lt $box.Y -or $x -ge ($box.X+$box.Width) -or $y -ge ($box.Y+$box.Height)){ continue }
        $area=$box.Width*$box.Height
        if($limit -gt 0 -and $area -gt $limit){ continue }
        [void]$hits.Add([pscustomobject]@{ element=$item; area=$area })
      } catch [System.Windows.Automation.ElementNotAvailableException] {}
    }
    foreach($hit in @($hits | Sort-Object area)){
      [void]$entries.Add([pscustomobject]@{ element=$hit.element; area=$hit.area; names=@(Get-SubtreeNames $hit.element) })
    }
  }
  # Revision de lat-apertura-clic (hallazgo 4): el control que el arbol ya pulso en este clic sin ver cambio no se pulsa
  # otra vez desde un punto (OCR, tooltip, vision): una segunda pulsacion deshace un conmutador o envia dos veces. Otro
  # control con el mismo nombre (un duplicado oculto que el arbol eligio, el visible aqui) si se pulsa.
  if(([string]$request.pressed).Length -gt 0 -and (Test-HoldsPressed @($entries | ForEach-Object { try { Get-Id $_.element } catch { '' } }) ([string]$request.pressed))){
    return (Click-Result $false $false 'visible_point_already_pressed' '' '' $false $false $false '')
  }
  $chosen=@(Select-PointHolders $entries $aliases $limit)
  # Un control sin nombre que su tooltip nombro (CONTRATO §8.2) llega con su identidad: cuenta como nombrado.
  $known=[string]$request.controlId
  if($known.Length -gt 0){
    for($k=0;$k -lt $entries.Count;$k++){
      $held=$false
      try { $held=((Get-Id $entries[$k].element) -eq $known) } catch { $held=$false }
      if($held){ $chosen=@($k)+@($chosen | Where-Object { $_ -ne $k }); break }
    }
  }
  # Un lugar recordado (el que se nombraba lo aprendio su tooltip) con otro control con nombre: ni patron ni puntero.
  if($chosen.Count -eq 0 -and [bool]$request.remembered){
    if(Test-NamedOther $entries (4*[double]$request.w*[double]$request.h)){ return (Click-Result $false $false 'visible_point_named_other' '' '' $false $false $false '') }
  }
  foreach($k in $chosen){
    $button=$entries[$k].element
    $done=$null
    try {
      $name=Get-Name $button;$identity=Get-Id $button
      $kind=$button.Current.ControlType.ProgrammaticName -replace '^ControlType\.',''
      # Encargo V: ni desde un punto (OCR, tooltip, vision), ni con el puntero despues (PointPressFrom: Refused).
      $asking=Get-AskingName $button $name $aliases $request.asks
      if($asking.Length -gt 0){ return (Click-Result $false $false 'visible_control_needs_confirmation' $asking $identity $false $false $false $kind) }
      $toggleBefore=Get-Toggle $button
      $done=Invoke-NamedControl $button $target.hwnd -PatternsOnly
    } catch { return (Click-Result $false $false 'visible_button_not_invokable' '' '' $false $false $false '') }
    # Revision 1 de r24b (B4): un contenedor sin Invoke ni SelectionItem no se pulsa, pero en un punto (OCR, tooltip) no
    # corta: el siguiente de la cadena, la superficie de render, y sin via, visible_point_no_pattern (el adaptador pulsa
    # con el puntero en el punto leido, no en el centro del contenedor). Nada se envio: nunca un recibo de «pudo haber
    # efecto».
    if([string]$done.method -eq 'container'){ continue }
    if($null -ne $done){ return (Pressed-Result $done $button $name $identity $kind $toggleBefore @()) }
  }
  # Nada del arbol en el punto tiene via, pero el punto cae en la superficie de render de Chromium (de la ventana o de
  # su familia): la pulsacion enviada ahi pulsa lo que se ve, como el puntero, sin frente ni cursor. Su prueba es la
  # superficie que cambia (el postread del localizador); sin superficie, el adaptador decide el puntero como antes.
  # Revision (hallazgos 3 y 4): solo si lo que la pagina tiene en el punto, en el momento de pulsar, nombra la etiqueta
  # (Test-HitNamesLabel); de cualquier proceso de la familia, porque esa comprobacion es la que impide pulsar a traves
  # del contenido algo que no es lo leido. Un lugar recordado sin nombre (§8.2) nunca va por aqui: su nombre no esta.
  $step='none'
  if(-not [bool]$request.remembered -and ([string]$request.controlId).Length -eq 0){
    try { $step=[string](Send-RenderPress (Get-RenderHosts $target.hwnd) ([int][math]::Round($x)) ([int][math]::Round($y)) ([uint32]0) $null $aliases) } catch { $step='failed' }
  }
  if($step -eq 'posted'){
    $pressed=Click-Result $false $true 'visible_button_postread_pending' '' '' $false $false $false ''
    $pressed.pending=$true; $pressed.method='render'; $pressed.cascadeStage='point'
    return $pressed
  }
  $none=Click-Result $false $false 'visible_point_no_pattern' '' '' $false $false $false ''
  $none.renderStep=$step
  return $none
}
# input.scroll con «index»: el control de la ultima vista se desplaza por su
# ScrollPattern y la prueba es su porcentaje vertical antes y despues; sin
# patron (o sin desplazamiento vertical) el adaptador usa la rueda en su centro.
# cu-v3-scroll-pegar-direccion (t-scroll-1, medido: la lista de una pagina que se desplaza entera no tiene ScrollPattern
# ni rectangulo en pantalla, scroll_control_unreachable): el control o el primer contenedor que lo contiene y se desplaza
# en vertical, hasta la ventana.
function Get-VerticalScroll($node){
  $pattern=$null
  if(-not $node.TryGetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern,[ref]$pattern)){ return $null }
  $scroll=[System.Windows.Automation.ScrollPattern]$pattern
  if($scroll.Current.VerticallyScrollable){ return $scroll }
  return $null
}
function Get-ParentOf($node){ return [System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($node) }
function Test-SameElement($a,$b){ return [System.Windows.Automation.Automation]::Compare($a,$b) }
function Find-ScrollOwner($element,$root){
  $node=$element
  for($depth=0;$null -ne $node -and $depth -lt 16;$depth++){
    try {
      $scroll=Get-VerticalScroll $node
      if($null -ne $scroll){ return @{ scroll=$scroll; own=($depth -eq 0) } }
      if(Test-SameElement $node $root){ return $null }
      $node=Get-ParentOf $node
    } catch { return $null }
  }
  return $null
}
function Do-Scroll($request){
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return @{ ok=$false; error='active_window_not_found' } }
  $element=Find-ById $target.root ([string]$request.controlId)
  if($null -eq $element){ return @{ ok=$false; error='visible_control_identity_stale' } }
  $owner=Find-ScrollOwner $element $target.root
  if($null -eq $owner){ return @{ ok=$false; error='scroll_pattern_unavailable' } }
  $scroll=$owner.scroll
  $before=[double]$scroll.Current.VerticalScrollPercent
  $step=$(if([string]$request.direction -eq 'up'){[System.Windows.Automation.ScrollAmount]::SmallDecrement}else{[System.Windows.Automation.ScrollAmount]::SmallIncrement})
  $amount=[int]$request.amount; if($amount -lt 1){$amount=1}; if($amount -gt 10){$amount=10}
  # Una muesca de rueda son tres lineas.
  for($i=0;$i -lt $amount*3;$i++){
    try { $scroll.Scroll([System.Windows.Automation.ScrollAmount]::NoAmount,$step) } catch [System.InvalidOperationException] { break }
  }
  $after=[double]$scroll.Current.VerticalScrollPercent
  return @{ ok=$true; error=''; scrolled=($after -ne $before); percentBefore=$before; percentAfter=$after; name=(Get-ShownName $element).name; container=(-not $owner.own) }
}
# input.scroll con «label» (goal v3 punto 2, revelar): el elemento con ese nombre que esta fuera de vista se trae a la
# vista sin rueda ni raton. Primero entre los que el arbol ya tiene (IsOffscreen) por su ScrollItemPattern; si no esta,
# por cada contenedor con ItemContainerPattern (una lista virtualizada solo tiene en el arbol lo que dibujo) se busca por
# nombre, se realiza (VirtualizedItemPattern) y se trae; si tampoco, el contenedor desplazable mas grande baja por su
# ScrollPattern, una pagina a la vez, releyendo hasta verlo o llegar al final. La prueba es el elemento visible
# (no IsOffscreen) releido despues; «already» = ya se veia y no se movio nada.
# Los que se llaman asi. Auditoria C10: las filas cuyo nombre solo lleva la etiqueta como palabras enteras (t-scroll-1,
# medido: la fila de una lista de programas se llama «<nombre>, <version>, <editor>, <fecha>») no se traen a la vista:
# sus nombres quedan en $script:NamedCandidates, para que el modelo nombre una tal cual.
function Find-AnyNamed($root,[string[]]$aliases,$until=$null){
  $hits=@()
  foreach($item in (Get-Descendants $root)){
    # Each name read crosses to the window's process: a long walk stops at the deadline with what it found.
    if($null -ne $until -and [DateTime]::UtcNow -gt $until){ break }
    try {
      $name=(Get-ShownName $item).name
      if(Test-NameMatch $name $aliases){ $hits+=@($item) }
      elseif((Test-ItemHolds $item $aliases) -and $script:NamedCandidates -notcontains $name){ $script:NamedCandidates+=@($name) }
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  return $hits
}
function Test-Shown($el){
  try { return (-not $el.Current.IsOffscreen) } catch { return $false }
}
function Reveal-Result([bool]$ok,[string]$error,[string]$method,$el){
  $name=''
  if($null -ne $el){ $name=(Get-ShownName $el).name }
  $result=@{ ok=$ok; error=$error; method=$method; name=$name; revealed=($ok -and $method -ne 'already'); visible=($null -ne $el -and (Test-Shown $el)) }
  if(-not $ok -and $script:NamedCandidates.Count -gt 0){ $result.candidates=@($script:NamedCandidates | Select-Object -First 10) }
  return $result
}
# Los que el arbol ya tiene: el que se ve («already»), si no el que su ScrollItemPattern trae («scrollintoview»).
# $touched.Value queda en verdadero si se llamo a ScrollIntoView (pudo moverse algo aunque no se vea).
function Reveal-Listed($hits,[ref]$touched){
  foreach($hit in $hits){ if(Test-Shown $hit){ return (Reveal-Result $true '' 'already' $hit) } }
  $pattern=$null
  foreach($hit in $hits){
    try {
      if($hit.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern,[ref]$pattern)){
        $touched.Value=$true
        ([System.Windows.Automation.ScrollItemPattern]$pattern).ScrollIntoView()
        if(Test-Shown $hit){ return (Reveal-Result $true '' 'scrollintoview' $hit) }
      }
    } catch {}
  }
  return $null
}
# Por cada contenedor con ItemContainerPattern (una lista virtualizada solo tiene en el arbol lo que dibujo), el
# elemento que se llama exactamente asi, realizado y traido; $touched.Value queda en verdadero si se encontro alguno.
function Find-InContainers($root,[string[]]$aliases,$until,[ref]$touched){
  $pattern=$null
  $containers=@()
  if([DateTime]::UtcNow -lt $until){
    try {
      $holds=New-Object System.Windows.Automation.PropertyCondition($AE::IsItemContainerPatternAvailableProperty,$true)
      $containers=@($root.FindAll([System.Windows.Automation.TreeScope]::Subtree,$holds))
    } catch { $containers=@() }
  }
  foreach($container in $containers){
    if([DateTime]::UtcNow -gt $until){ break }
    foreach($alias in $aliases){
      $found=$null
      try {
        $holder=[System.Windows.Automation.ItemContainerPattern]$container.GetCurrentPattern([System.Windows.Automation.ItemContainerPattern]::Pattern)
        $found=$holder.FindItemByProperty($null,$AE::NameProperty,$alias)
      } catch { $found=$null }
      if($null -eq $found){ continue }
      $touched.Value=$true
      if($found.TryGetCurrentPattern([System.Windows.Automation.VirtualizedItemPattern]::Pattern,[ref]$pattern)){
        try { ([System.Windows.Automation.VirtualizedItemPattern]$pattern).Realize() } catch {}
      }
      if($found.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern,[ref]$pattern)){
        try { ([System.Windows.Automation.ScrollItemPattern]$pattern).ScrollIntoView() } catch {}
      }
      if(Test-Shown $found){ return (Reveal-Result $true '' 'itemcontainer' $found) }
    }
  }
  return $null
}
# El plazo del worker para revelar, por debajo del presupuesto del adaptador (15 s): cada recorrido de elementos (los
# nombres, los contenedores, la busqueda del desplazable y cada pagina) se corta al llegar, y responde «no encontrado»
# con lo que movio en vez de quedarse sin respuesta (scroll_receipt_invalid). Una sola llamada FindAll de UI Automation
# no se puede cortar por dentro: el plazo se mira antes y despues de cada una.
$script:RevealSeconds=11
function Do-Reveal($request){
  $deadline=[DateTime]::UtcNow.AddSeconds($script:RevealSeconds)
  $aliases=@($request.aliases | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  if($aliases.Count -eq 0){ return @{ ok=$false; error='visible_click_argument_invalid' } }
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return @{ ok=$false; error='active_window_not_found' } }
  $root=$target.root
  $touched=$false
  $script:NamedCandidates=@()
  $hits=@(Find-AnyNamed $root $aliases $deadline)
  if($hits.Count -gt 0){
    $listed=Reveal-Listed $hits ([ref]$touched)
    if($null -ne $listed){ return $listed }
  }
  $contained=Find-InContainers $root $aliases $deadline ([ref]$touched)
  if($null -ne $contained){ return $contained }
  # Lo que pudo haberse movido ya (un ScrollIntoView, un Realize) es un efecto: el metodo no queda vacio.
  $tried=$(if($touched){ 'scrollintoview' } else { '' })
  if([DateTime]::UtcNow -gt $deadline){ return (Reveal-Result $false 'reveal_not_found' $tried $null) }
  # El contenedor desplazable verticalmente mas grande, por pagina, hasta verlo o llegar al final.
  $pattern=$null;$scroller=$null;$area=0;$holder=$root
  foreach($item in @($root) + @(Get-Descendants $root)){
    if([DateTime]::UtcNow -gt $deadline){ break }
    try {
      if(-not $item.TryGetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern,[ref]$pattern)){ continue }
      $scroll=[System.Windows.Automation.ScrollPattern]$pattern
      if(-not $scroll.Current.VerticallyScrollable){ continue }
      $box=$item.Current.BoundingRectangle
      $size=$(if($box.IsEmpty){ 0 } else { $box.Width*$box.Height })
      if($null -eq $scroller -or $size -gt $area){ $scroller=$scroll; $area=$size; $holder=$item }
    } catch {}
  }
  if($null -eq $scroller -or [DateTime]::UtcNow -gt $deadline){ return (Reveal-Result $false 'reveal_not_found' $tried $null) }
  $step=$(if([string]$request.direction -eq 'up'){[System.Windows.Automation.ScrollAmount]::LargeDecrement}else{[System.Windows.Automation.ScrollAmount]::LargeIncrement})
  $pages=[int]$request.amount; if($pages -lt 1){ $pages=10 }; if($pages -gt 40){ $pages=40 }
  for($page=0;$page -lt $pages -and [DateTime]::UtcNow -lt $deadline;$page++){
    $before=[double]$scroller.Current.VerticalScrollPercent
    try { $scroller.Scroll([System.Windows.Automation.ScrollAmount]::NoAmount,$step) } catch { break }
    # Solo lo que contiene el contenedor que se desplaza: el resto de la ventana no cambio con la pagina.
    foreach($hit in @(Find-AnyNamed $holder $aliases $deadline)){ if(Test-Shown $hit){ return (Reveal-Result $true '' 'scroll' $hit) } }
    if([double]$scroller.Current.VerticalScrollPercent -eq $before){ break }
  }
  return (Reveal-Result $false 'reveal_not_found' 'scroll' $null)
}
# Los guiones del navegador (UserBrowserScripts) corren en un runspace propio y
# persistente: su «exit» termina el guion, no el worker, y sus variables no se
# filtran entre llamadas. Antes, un PowerShell nuevo por lectura del marco
# (cierre de pestanas medido: 3,1 s por pestana).
$script:ScriptRunspace=$null
function Do-Script($request){
  if($null -eq $script:ScriptRunspace){
    $script:ScriptRunspace=[runspacefactory]::CreateRunspace()
    $script:ScriptRunspace.ApartmentState='STA'
    $script:ScriptRunspace.Open()
  }
  $shell=[powershell]::Create()
  try {
    $shell.Runspace=$script:ScriptRunspace
    [void]$shell.AddScript([string]$request.script,$true)
    foreach($argument in @($request.args)){ [void]$shell.AddArgument([string]$argument) }
    $line=$null
    foreach($item in $shell.Invoke()){
      $text=([string]$item).Trim()
      if($text.StartsWith('{')){ $line=$text }
    }
    if($null -eq $line){ return @{ ok=$false; error='script_no_receipt' } }
    return @{ ok=$true; error=''; line=$line }
  } finally { $shell.Dispose() }
}
function Do-Find($request){
  $aliases=@($request.aliases | ForEach-Object { [string]$_ })
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return @{ ok=$false; error='active_window_not_found'; count=0 } }
  $script:NamedCandidates=@()
  $matches=@(Find-Named $target.root $aliases)
  $names=@($matches | ForEach-Object { (Get-ShownName $_).name })
  return @{ ok=$true; error=''; count=$matches.Count; names=$names }
}
# Ronda 24 (cliente en frio listo por interaccion): una ventana esta lista para usarse cuando expone contenido con el
# que una persona interactua (un campo editable o una lista), no cuando tiene titulo; y un atajo abrio su buscador cuando
# un campo editable de esa ventana tiene el foco. Solo lectura: aqui nada se pulsa, se enfoca ni se escribe.
function Do-Interaction($request){
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target -or $null -eq $target.root){ return @{ ok=$false; error='active_window_not_found' } }
  $root=$target.root
  $owner=0; try { $owner=[int]$root.Current.ProcessId } catch { return @{ ok=$false; error='active_window_not_found' } }
  $focusedOut=$null
  try {
    $f=$AE::FocusedElement
    if($null -ne $f -and [int]$f.Current.ProcessId -eq $owner){
      $kind=[string]$f.Current.ControlType.ProgrammaticName -replace '^ControlType\.',''
      $editable=$false
      $vp=$null
      if($f.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$vp)){
        try { $editable=-not ([System.Windows.Automation.ValuePattern]$vp).Current.IsReadOnly } catch {}
      } elseif($kind -eq 'Edit'){ $editable=$true }
      $focusedOut=@{ kind=$kind; name=[string]$f.Current.Name; editable=$editable; id=((@($f.GetRuntimeId()) | ForEach-Object { [string]$_ }) -join '.') }
    }
  } catch { $focusedOut=$null }
  $content=$false
  if([bool]$request.content){
    try {
      $types=@([System.Windows.Automation.ControlType]::Edit,[System.Windows.Automation.ControlType]::List,[System.Windows.Automation.ControlType]::Tree)
      $conditions=[System.Windows.Automation.Condition[]]@($types | ForEach-Object { New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty,$_) })
      $any=New-Object System.Windows.Automation.OrCondition(,$conditions)
      $content=($null -ne $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$any))
    } catch { $content=$false }
  }
  return @{ ok=$true; error=''; content=$content; focused=$focusedOut }
}
# input.text.type dirigido (CONTRATO_VISTA_ACCION.md §2, arreglo 1 del goal v3): el campo de la ultima vista recibe el
# texto sin teclado ni primer plano. ValuePattern.SetValue reemplaza todo el contenido, asi que solo se usa donde
# reemplazar es lo mismo que teclear: un campo escribible (ni de solo lectura ni contrasena) que no es un Document y
# esta vacio o tiene todo su texto seleccionado. Si no, se devuelve el hwnd nativo del campo y su clase para que el
# adaptador inserte en el cursor con mensajes Win32. La prueba es el valor releido: de entrega, nunca de llegada.
# Un campo que dice ser de solo lectura (su ValuePattern), de contrasena o deshabilitado no recibe nada por ninguna
# via: readOnly/password/enabled van en la respuesta y el adaptador se niega antes de cualquier efecto.
# Goal v3 punto 2 (formularios): con «replace» el paso pide poner el campo en ese valor (un ancho, un tamano, un
# nombre de archivo), asi que SetValue vale aunque el campo tenga texto; nunca en un Document ni en una contrasena.
# Un ComboBox sin valor propio escribible toma el texto por el ValuePattern de su Edit; sin el, se despliega y se
# elige la entrada que se llama asi (SelectionItem.Select), y la prueba es la entrada seleccionada releida.
function Get-WritableValue($element){
  $pattern=$null
  if($element.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)){
    $vp=[System.Windows.Automation.ValuePattern]$pattern
    try { if(-not $vp.Current.IsReadOnly){ return $vp } } catch {}
  }
  return $null
}
function Get-ComboEdit($combo){
  try {
    $edit=New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty,[System.Windows.Automation.ControlType]::Edit)
    $inner=$combo.FindFirst([System.Windows.Automation.TreeScope]::Children,$edit)
    if($null -ne $inner -and $null -ne (Get-WritableValue $inner)){ return $inner }
  } catch {}
  return $null
}
# Ronda 22 (r18 t2-c04: «125» y la entrada «125% (recomendado)»): un numero pedido es la unica entrada cuyo nombre
# lo tiene como numero entero, nunca parte de otro: «150» no es «1500», y «2» no es la parte entera de «2,5» ni «125»
# la de «125,5 %» (la mente lee igual los numeros, _WHOLE_NUMBER). Dos entradas con ese numero, o ninguna: $null.
function Select-NumberedEntry($items,[string]$text){
  $number=([string]$text).Trim()
  if($number -notmatch '^\d+(?:[.,]\d+)?$'){ return $null }
  $wanted='(?<![\d.,])'+[regex]::Escape($number)+'(?!\d|[.,]\d)'
  $numbered=@(@($items) | Where-Object { $null -ne $_ -and [string](Get-Name $_) -match $wanted })
  if($numbered.Count -eq 1){ return $numbered[0] }
  return $null
}
function Select-ComboEntry($combo,[string]$text){
  $pattern=$null
  if(-not $combo.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$pattern)){ return $null }
  $expand=[System.Windows.Automation.ExpandCollapsePattern]$pattern
  try { $expand.Expand() } catch { return $null }
  $chosen=$null
  try {
    $items=@($combo.FindAll([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty,[System.Windows.Automation.ControlType]::ListItem))))
    foreach($item in $items){
      if(Test-NameMatch (Get-Name $item) @($text)){ $chosen=$item; break }
    }
    if($null -eq $chosen){ $chosen=Select-NumberedEntry $items $text }
    if($null -ne $chosen){
      $select=$null
      if($chosen.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern,[ref]$select)){ try { ([System.Windows.Automation.ScrollItemPattern]$select).ScrollIntoView() } catch {} }
      if($chosen.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern,[ref]$select)){ ([System.Windows.Automation.SelectionItemPattern]$select).Select() } else { $chosen=$null }
    }
  } finally { try { $expand.Collapse() } catch {} }
  if($null -eq $chosen){ return $null }
  if(-not [bool](Test-Selected $chosen)){ return $false }
  # Revision de combos-galerias: una caja que publica su valor lo dice con la entrada elegida (una lista marcada que la
  # caja no tomo no es entrega).
  $value=$null
  if($combo.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$value)){
    $vp=[System.Windows.Automation.ValuePattern]$value
    $name=Get-Name $chosen
    $after=Wait-ValueSet { [string]$vp.Current.Value } $name 300
    if([string]::IsNullOrWhiteSpace([string]$after)){ return $true }
    return [string]::Equals(([string]$after).Trim(),([string]$name).Trim(),[StringComparison]::OrdinalIgnoreCase)
  }
  return $true
}
# Regresiones r2 M3 (live v8): Chromium publica el valor nuevo de un campo un poco despues de SetValue; releido a los
# 95 ms todavia mostraba el anterior y el texto se dio por no verificado. Se relee cada 40 ms hasta $limitMs (300 como
# mucho) y se devuelve el primer valor igual al texto, o el ultimo leido.
function Wait-ValueSet([scriptblock]$read,[string]$text,[int]$limitMs){
  $limit=[Math]::Min([Math]::Max($limitMs,0),300)
  $watch=[System.Diagnostics.Stopwatch]::StartNew()
  $after=$null
  while($true){
    try { $after=[string](& $read) } catch { $after=$null }
    if($after -eq $text -or $watch.ElapsedMilliseconds -ge $limit){ return $after }
    Start-Sleep -Milliseconds 40
  }
}
function Do-Field($request){
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return @{ ok=$false; error='active_window_not_found' } }
  $element=Find-ById $target.root ([string]$request.controlId)
  if($null -eq $element){ return @{ ok=$false; error='visible_control_identity_stale' } }
  $replace=[bool]$request.replace
  $kind='';$className='';$native=0;$password=$false;$enabled=$true
  try { $kind=([string]$element.Current.ControlType.ProgrammaticName) -replace '^ControlType\.','' } catch {}
  try { $password=[bool]$element.Current.IsPassword } catch {}
  try { $enabled=[bool]$element.Current.IsEnabled } catch {}
  # Revision de combos-galerias (hallazgo 1): con «entry» el texto solo se elige como una entrada de la propia lista
  # (por patron, la seleccion y el valor releidos); nunca se escribe en la caja ni en su Edit. Sin una entrada que se
  # llame asi, nada cambia (method vacio).
  if([bool]$request.entry){
    $result=@{ ok=$true; error=''; kind=$kind; className=''; password=$password; enabled=$enabled; entry=$true; method=''; delivered=$false }
    if($kind -ne 'ComboBox' -or -not $enabled -or $password -or [string]::IsNullOrWhiteSpace([string]$request.text)){ return $result }
    try { $result.className=[string]$element.Current.ClassName } catch {}
    $picked=Select-ComboEntry $element ([string]$request.text)
    if($null -ne $picked){ $result.method='select'; $result.delivered=[bool]$picked }
    return $result
  }
  $combo=$null
  if($kind -eq 'ComboBox' -and $null -eq (Get-WritableValue $element)){
    $inner=Get-ComboEdit $element
    if($null -ne $inner){ $combo=$element; $element=$inner }
  }
  try { $className=[string]$element.Current.ClassName } catch {}
  try { $native=[long]$element.Current.NativeWindowHandle } catch {}
  # r25: solo un campo con el foco del teclado puede recibir el texto por teclado si su valor y sus mensajes no llegan.
  $focused=$false; try { $focused=[bool]$element.Current.HasKeyboardFocus } catch {}
  $pattern=$null;$writable=$false;$readOnly=$false;$value=$null
  if($element.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)){
    $vp=[System.Windows.Automation.ValuePattern]$pattern
    try { $readOnly=[bool]$vp.Current.IsReadOnly; $writable=-not $readOnly; $value=[string]$vp.Current.Value } catch { $writable=$false }
  }
  $wholeSelected=$false
  $textPattern=$null
  if(-not [string]::IsNullOrEmpty($value) -and $element.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern,[ref]$textPattern)){
    try {
      $tp=[System.Windows.Automation.TextPattern]$textPattern
      $ranges=@($tp.GetSelection())
      if($ranges.Count -eq 1){ $wholeSelected=([string]$ranges[0].GetText(-1)) -eq ([string]$tp.DocumentRange.GetText(-1)) }
    } catch { $wholeSelected=$false }
  }
  $replaceable=$writable -and $enabled -and -not $password -and $kind -ne 'Document' -and ([string]::IsNullOrEmpty($value) -or $wholeSelected -or $replace)
  $result=@{ ok=$true; error=''; kind=$kind; className=$className; nativeHwnd=$native; focused=$focused; password=$password; readOnly=$readOnly; enabled=$enabled; writable=$writable; replaceable=$replaceable; replace=$replace; valueLength=$(if($null -eq $value){-1}else{$value.Length}); method=''; delivered=$false }
  $text=$request.text
  if($null -eq $text){ return $result }
  if(-not $replaceable){
    # Un ComboBox de solo lista (sin texto que escribir): su entrada con ese nombre, elegida por patron.
    if($kind -eq 'ComboBox' -and $enabled -and -not $writable -and $null -eq $combo){
      $picked=Select-ComboEntry $element ([string]$text)
      if($null -ne $picked){ $result.method='select'; $result.delivered=[bool]$picked; return $result }
    }
    return $result
  }
  try { $vp.SetValue([string]$text) } catch { $result.ok=$false; $result.error='field_setvalue_refused'; return $result }
  $result.method='setvalue'
  $after=Wait-ValueSet { [string]$vp.Current.Value } ([string]$text) 300
  $result.delivered=($after -eq [string]$text)
  $result.valueLength=$(if($null -eq $after){-1}else{$after.Length})
  # Revision 1 de r24b (v1): SetValue escribe sin mover el foco del teclado; el adaptador lo lee para la tecla
  # siguiente (Enter), que iria al control que la ventana tenia enfocado.
  $focusedField=$element
  if($null -ne $combo){ $focusedField=$combo }
  $result.focused=$false
  try { $result.focused=[bool]$element.Current.HasKeyboardFocus -or [bool]$focusedField.Current.HasKeyboardFocus } catch { $result.focused=$false }
  return $result
}
# Revision 1 de r24b (v1): el foco del teclado puesto por UIA en el campo de la ultima vista, antes de una tecla que va
# por el teclado. Solo con su ventana ya al frente (SetFocus trae al frente una ventana tapada: robo de foco); la
# prueba es HasKeyboardFocus releido.
function Do-Focus($request){
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target){ return @{ ok=$false; error='active_window_not_found' } }
  $element=Find-ById $target.root ([string]$request.controlId)
  if($null -eq $element){ return @{ ok=$false; error='visible_control_identity_stale' } }
  if(-not (Test-InFront $target.hwnd)){ return @{ ok=$true; error=''; focused=$false; behind=$true } }
  # Un ComboBox escrito por su Edit interior (Do-Field): el foco va a ese Edit, como fue el valor.
  $kind=''
  try { $kind=([string]$element.Current.ControlType.ProgrammaticName) -replace '^ControlType\.','' } catch {}
  if($kind -eq 'ComboBox' -and $null -eq (Get-WritableValue $element)){
    $inner=Get-ComboEdit $element
    if($null -ne $inner){ $element=$inner }
  }
  $focused=$false
  try { $focused=[bool]$element.Current.HasKeyboardFocus } catch { $focused=$false }
  if(-not $focused){
    try { $element.SetFocus() } catch {}
    for($look=0;$look -lt 8 -and -not $focused;$look++){
      try { $focused=[bool]$element.Current.HasKeyboardFocus } catch { $focused=$false }
      if(-not $focused){ Start-Sleep -Milliseconds 25 }
    }
  }
  return @{ ok=$true; error=''; focused=$focused; controlId=[string]$request.controlId }
}

# CONTRATO_VISTA_ACCION.md §8.2: un accionable que sigue sin nombre tras el respaldo (§8.1) es candidato a leer su
# tooltip: no un campo (se identifica por su valor), no uno sin rectangulo, ni uno del tamano de una zona (un boton que
# es solo un icono cabe en 200 px).
function Test-HoverCandidate([string]$kind,[string]$name,$rect){
  if($Actionable -notcontains $kind -or $kind -eq 'Edit' -or $kind -eq 'Document'){ return $false }
  if(-not [string]::IsNullOrWhiteSpace($name)){ return $false }
  if($null -eq $rect){ return $false }
  return ([int]$rect.w -ge 6 -and [int]$rect.h -ge 6 -and [int]$rect.w -le 200 -and [int]$rect.h -le 200)
}
function Do-Unnamed($request){
  $limit=[int]$request.limit; if($limit -lt 1){$limit=1}; if($limit -gt 24){$limit=24}
  $target=Get-Root ([long]$request.hwnd)
  if($null -eq $target -or $null -eq $target.root){ return @{ ok=$false; error='active_window_not_found' } }
  $all=Get-Descendants $target.root
  $out=New-Object System.Collections.ArrayList
  $named=0
  foreach($item in $all){
    try {
      if($item.Cached.IsOffscreen){ continue }
      $kind=$item.Cached.ControlType.ProgrammaticName -replace '^ControlType\.',''
      $shown=Get-ShownName $item
      if($shown.name.Length -gt 0){ $named++; continue }
      $rect=Get-Rect $item
      if(-not (Test-HoverCandidate $kind $shown.name $rect)){ continue }
      if($out.Count -lt $limit){ [void]$out.Add([pscustomobject]@{ kind=$kind; id=(Get-Id $item); rect=$rect }) }
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  return @{ ok=$true; error=''; hwnd=[long]$target.hwnd; named=$named; controls=@($out) }
}
# El texto de un tooltip: el nombre de un ToolTip, o el de un ToolTip de dentro (el Popup de XAML lo envuelve), o el de
# una ventana cuya clase dice que es un tooltip (la de comctl32 publica su texto como nombre). Vacio si no lo es.
function Get-TipName([string]$kind,[string]$name,[string]$className,[string]$innerName){
  if($kind -eq 'ToolTip' -and -not [string]::IsNullOrWhiteSpace($name)){ return (Format-Name $name) }
  if(-not [string]::IsNullOrWhiteSpace($innerName)){ return (Format-Name $innerName) }
  if($className -match '(?i)tool\s*tip' -and -not [string]::IsNullOrWhiteSpace($name)){ return (Format-Name $name) }
  return ''
}
# Los tooltips visibles ahora: las ventanas de primer nivel pequenas de esos procesos (un tooltip es una ventana aparte)
# y los ToolTip dentro de la ventana de la mision (una pagina que dibuja el suyo con role=tooltip). Solo lectura.
function Do-Tooltips($request){
  $tips=New-Object System.Collections.ArrayList
  $tipType=New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty,[System.Windows.Automation.ControlType]::ToolTip)
  foreach($p in @($request.pids)){
    $id=[int]$p
    if($id -le 0){ continue }
    $byProcess=New-Object System.Windows.Automation.PropertyCondition($AE::ProcessIdProperty,$id)
    $tops=$null
    try { $tops=$AE::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$byProcess) } catch { $tops=$null }
    foreach($top in @($tops)){
      try {
        if($null -eq $top -or $top.Current.IsOffscreen){ continue }
        $box=$top.Current.BoundingRectangle
        if($box.IsEmpty -or $box.Width -le 0 -or $box.Width -gt 900 -or $box.Height -gt 400){ continue }
        $kind=$top.Current.ControlType.ProgrammaticName -replace '^ControlType\.',''
        $inner=''
        if($kind -ne 'ToolTip'){ $found=$top.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$tipType); if($null -ne $found){ $inner=[string]$found.Current.Name } }
        $tip=Get-TipName $kind ([string]$top.Current.Name) ([string]$top.Current.ClassName) $inner
        if($tip.Length -gt 0){ [void]$tips.Add([pscustomobject]@{ name=$tip; rect=@{ x=[int]$box.X; y=[int]$box.Y; w=[int]$box.Width; h=[int]$box.Height } }) }
      } catch {}
    }
  }
  $target=$null
  if([long]$request.hwnd -gt 0){ $target=Get-Root ([long]$request.hwnd) }
  if($null -ne $target -and $null -ne $target.root){
    try {
      foreach($found in @($target.root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$tipType))){
        if($null -eq $found -or $found.Current.IsOffscreen){ continue }
        $tip=Get-TipName 'ToolTip' ([string]$found.Current.Name) '' ''
        if($tip.Length -gt 0){ $box=$found.Current.BoundingRectangle; [void]$tips.Add([pscustomobject]@{ name=$tip; rect=@{ x=[int]$box.X; y=[int]$box.Y; w=[int]$box.Width; h=[int]$box.Height } }) }
      }
    } catch {}
  }
  return @{ ok=$true; error=''; tips=@($tips) }
}

# Un comando que puede actuar por patron sobre una ventana que esta detras corre bajo BaxyFrontKeeper: si la familia
# del objetivo toma el frente mientras actua (o en la cola corta despues), se intenta devolver a la ventana que lo
# tenia. La cola solo sigue a un patron que actuo de verdad (pulso, eligio, alterno, escribio el valor, desplazo o
# revelo): cualquier otra respuesta puede seguir con el puntero, la rueda o el teclado del adaptador, que toman el
# frente a proposito dentro del lease, y la red no debe pelearlo.
$script:KeptMethods=@('invoke','select','toggle','legacy','message','setvalue','render','collapse','escape')
function Test-ActedByPattern($result){
  if($null -eq $result){ return $false }
  if($script:KeptMethods -contains [string]$result.method){ return $true }
  return ([bool]$result.scrolled -or [bool]$result.revealed)
}
# El parte de la vigilancia en curso (desde su Begin): si la familia del objetivo tomo el frente, si se devolvio
# siempre, cuantas veces fallo y el retorno mas largo. Lo lleva la respuesta del comando y la de su postread (la cola
# termina despues de la respuesta), y el adaptador lo copia al recibo para el medidor de molestia.
function Add-FrontReport($result){
  if($null -eq $result -or -not ($result -is [hashtable])){ return $result }
  $taken=[BaxyFrontKeeper]::WatchTaken
  if($taken -le 0){ return $result }
  $failed=[BaxyFrontKeeper]::WatchFailed
  $result.frontChanged=$true
  $result.frontRestored=($failed -eq 0)
  $result.frontReturnFailed=$failed
  $result.frontReturnMs=[BaxyFrontKeeper]::WatchLongestMs
  return $result
}
function Invoke-Kept($request,[scriptblock]$work){
  $top=[IntPtr]::Zero
  try { if([long]$request.hwnd -gt 0){ $top=[IntPtr][long]$request.hwnd } } catch {}
  $kept=$false
  try { [BaxyFrontKeeper]::Begin($top); $kept=$true } catch {}
  $result=$null; $acted=$false
  try { $result=& $work $request; $acted=Test-ActedByPattern $result }
  finally { if($kept){ try { [BaxyFrontKeeper]::End($acted) } catch {} } }
  if($kept){ $result=Add-FrontReport $result }
  return $result
}

# Las clases de ventana de la superficie de render llegan como dato con el primer «ping» del anfitrion
# (UiaWorkerHost, render_surface_classes.v1.json); un «ping» sin ellas conserva las que habia.
function Set-RenderClasses($request){
  if($null -eq $request -or -not ($request.PSObject.Properties.Name -contains 'renderClasses')){ return }
  $classes=@(@($request.renderClasses) | Where-Object { $_ -is [string] -and -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { $_.Trim() })
  [BaxyUiaWorkerNative]::RenderClasses=[string[]]$classes
}

while($true){
  $line=[Console]::In.ReadLine()
  if($null -eq $line){ break }
  if([string]::IsNullOrWhiteSpace($line)){ continue }
  try {
    $request=$line | ConvertFrom-Json
    $cmd=[string]$request.cmd
    if($cmd -eq 'exit'){ Send-Line @{ ok=$true; bye=$true }; break }
    elseif($cmd -eq 'ping'){ Set-RenderClasses $request; Send-Line @{ ok=$true; pid=$PID; renderClasses=@([BaxyUiaWorkerNative]::RenderClasses); clientProviders=$script:ClientProviders; quietInput=$script:QuietInput; uiaInputDropped=[BaxyUiaQuietInput]::Dropped; uiaInputRefused=[BaxyUiaQuietInput]::Refused; uiaWaitAnswered=[BaxyUiaQuietInput]::Answered; frontReturned=[BaxyFrontKeeper]::Returned; frontReturnFailed=[BaxyFrontKeeper]::Failed; frontReturnMs=[BaxyFrontKeeper]::LastReturnMs; frontYielded=[BaxyFrontKeeper]::Yielded; frontLeaseYielded=[BaxyFrontKeeper]::LeaseYielded; frontRawInput=[BaxyFrontKeeper]::RawInput; frontBidKey=[BaxyFrontKeeper]::BidKey; frontBids=[BaxyFrontKeeper]::Bids; frontBidsAnswered=[BaxyFrontKeeper]::BidsAnswered; frontLate=[BaxyFrontKeeper]::Late; frontLateMs=[BaxyFrontKeeper]::LateMs } }
    elseif($cmd -eq 'view'){ Send-Line (Do-View $request) }
    elseif($cmd -eq 'signature'){ Send-Line (Do-Signature $request) }
    elseif($cmd -eq 'click'){ Send-Line (Invoke-Kept $request { param($r) Do-Click $r }) }
    elseif($cmd -eq 'at'){ Send-Line (Invoke-Kept $request { param($r) Do-At $r }) }
    elseif($cmd -eq 'postread'){ Send-Line (Add-FrontReport (Do-Postread $request)) }
    elseif($cmd -eq 'scroll'){ Send-Line (Invoke-Kept $request { param($r) Do-Scroll $r }) }
    elseif($cmd -eq 'script'){ Send-Line (Do-Script $request) }
    elseif($cmd -eq 'find'){ Send-Line (Do-Find $request) }
    elseif($cmd -eq 'interaction'){ Send-Line (Do-Interaction $request) }
    elseif($cmd -eq 'field'){ Send-Line (Invoke-Kept $request { param($r) Do-Field $r }) }
    elseif($cmd -eq 'focus'){ Send-Line (Invoke-Kept $request { param($r) Do-Focus $r }) }
    elseif($cmd -eq 'unnamed'){ Send-Line (Do-Unnamed $request) }
    elseif($cmd -eq 'tooltips'){ Send-Line (Do-Tooltips $request) }
    elseif($cmd -eq 'reveal'){ Send-Line (Invoke-Kept $request { param($r) Do-Reveal $r }) }
    else { Send-Line @{ ok=$false; error='uia_worker_unknown_command' } }
  } catch {
    $reason=[string]$_.Exception.Message
    if($reason.Length -gt 200){ $reason=$reason.Substring(0,200) }
    Send-Line @{ ok=$false; error='visible_controls_uia_failed'; detail=$reason }
  }
}
# Las importaciones del cliente UIA vuelven a su sitio antes de salir: ningun hilo suyo entra en codigo que se descarga.
try { [BaxyUiaQuietInput]::Restore() } catch {}
