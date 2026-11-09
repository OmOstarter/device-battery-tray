using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;
using System.Web.Script.Serialization;

internal static class Native {
 static readonly Dictionary<string,IntPtr> modules=new Dictionary<string,IntPtr>(StringComparer.OrdinalIgnoreCase);
 [DllImport("kernel32", CharSet=CharSet.Unicode, SetLastError=true)] static extern IntPtr LoadLibraryEx(string path,IntPtr reserved,uint flags);
 [DllImport("kernel32", CharSet=CharSet.Ansi)] static extern IntPtr GetProcAddress(IntPtr module,string name);
 [DllImport("user32")] public static extern bool DestroyIcon(IntPtr icon);
 internal static T Function<T>(string file,string name) where T:class {
  IntPtr mod;
  lock(modules){if(!modules.TryGetValue(file,out mod)){mod=LoadLibraryEx(file,IntPtr.Zero,0x1100);if(mod!=IntPtr.Zero)modules[file]=mod;}}
  if(mod==IntPtr.Zero) throw new IOException("載入失敗："+file+" ("+Marshal.GetLastWin32Error()+")");
  IntPtr address=GetProcAddress(mod,name);
  if(address==IntPtr.Zero)throw new IOException("找不到函式："+name);
  return Marshal.GetDelegateForFunctionPointer(address,typeof(T)) as T;
 }
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate IntPtr Enumerate(ushort vid,ushort pid);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate void Free(IntPtr head);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate IntPtr Open([MarshalAs(UnmanagedType.LPStr)]string path);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate void Close(IntPtr handle);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate int Write(IntPtr handle,byte[] bytes,UIntPtr size);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate int Read(IntPtr handle,[Out]byte[] bytes,UIntPtr size,int milliseconds);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate byte Battery([MarshalAs(UnmanagedType.LPStr)]string path,[Out]byte[] result);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate byte OpenKeyboard([MarshalAs(UnmanagedType.LPStr)]string path);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate byte QueryKeyboard(byte[] request,[Out]byte[] result,byte length);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate void CloseKeyboard();
 [StructLayout(LayoutKind.Sequential)] internal struct HidInfo {
  public IntPtr path; public ushort vid,pid;public IntPtr serial;public ushort release;
  public IntPtr manufacturer,product;public ushort page,usage;public int iface;public IntPtr next;
 }
}
internal sealed class Reading {
 public string Name; public int? Percent;public string Status;public string Raw;public string Time;public string Connection;public bool Present;
 public Reading(string name){Name=name;Status="未連線";Raw="";Time=DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");}
}
internal sealed class UserPreferences {
 public bool Dark=true;public string[] Names;public List<AddedDevice> Added=new List<AddedDevice>();
 internal static UserPreferences Current=new UserPreferences();
 static string FilePath {get{return Path.Combine(Application.StartupPath,"preferences.json");}}
 internal static void Load(){
  try{if(File.Exists(FilePath))Current=new JavaScriptSerializer().Deserialize<UserPreferences>(File.ReadAllText(FilePath))??new UserPreferences();}catch{}
  if(Current.Added==null)Current.Added=new List<AddedDevice>();
  HashSet<string> seen=new HashSet<string>();Current.Added.RemoveAll(d=>{try{if(d==null||string.IsNullOrWhiteSpace(d.Id)||string.IsNullOrWhiteSpace(d.Name)||d.Name.Length>32||!seen.Add(d.Id))return true;if(d.Profile!=null){d.Profile=DeviceProfile.Parse(d.Profile.Code());if(d.Id!=d.Profile.Key())return true;}else if(!d.Id.StartsWith("usb:"))return true;return false;}catch{return true;}});
  if(Current.Names!=null && Current.Names.Length==3)for(int i=0;i<3;i++)if(!string.IsNullOrWhiteSpace(Current.Names[i])&&Current.Names[i].Length<=32)BatteryReader.Names[i]=Current.Names[i].Trim();
 }
 internal static void Save(){Current.Names=(string[])BatteryReader.Names.Clone();string temp=FilePath+".tmp";File.WriteAllText(temp,new JavaScriptSerializer().Serialize(Current));if(File.Exists(FilePath))File.Replace(temp,FilePath,null);else File.Move(temp,FilePath);}
}
internal sealed class TrayColors:ProfessionalColorTable {
 readonly bool dark;internal TrayColors(bool darkMode){dark=darkMode;UseSystemColors=false;}
 Color Surface {get{return dark?Color.FromArgb(28,33,44):Color.White;}}
 Color Hover {get{return dark?Color.FromArgb(48,58,79):Color.FromArgb(227,235,250);}}
 public override Color ToolStripDropDownBackground{get{return Surface;}}
 public override Color ImageMarginGradientBegin{get{return Surface;}}
 public override Color ImageMarginGradientMiddle{get{return Surface;}}
 public override Color ImageMarginGradientEnd{get{return Surface;}}
 public override Color MenuItemSelected{get{return Hover;}}
 public override Color MenuItemBorder{get{return Hover;}}
 public override Color MenuBorder{get{return dark?Color.FromArgb(55,64,81):Color.FromArgb(220,226,235);}}
}
internal sealed class DeviceCard:Control {
 internal Reading Data;internal bool Dark=true;internal bool Keyboard;
 readonly Button rename=new Button{Text="重新命名",FlatStyle=FlatStyle.Flat,Size=new Size(86,28),Cursor=Cursors.Hand,TabStop=true};
 internal event Action Rename,EditProtocol,Delete;
 readonly Button edit=new Button{Text="編輯協定代碼",FlatStyle=FlatStyle.Flat,Size=new Size(118,28),Visible=false},delete=new Button{Text="刪除",FlatStyle=FlatStyle.Flat,Size=new Size(56,28),Visible=false};
 internal void SetCustom(bool custom){edit.Visible=delete.Visible=custom;}
 internal DeviceCard(bool keyboard){Keyboard=keyboard;DoubleBuffered=true;Height=114;Margin=new Padding(0,0,0,12);rename.FlatAppearance.BorderSize=0;rename.Click+=(s,e)=>{if(Rename!=null)Rename();};Controls.Add(rename);edit.Click+=(s,e)=>{if(EditProtocol!=null)EditProtocol();};delete.Click+=(s,e)=>{if(Delete!=null)Delete();};Controls.Add(edit);Controls.Add(delete);}
 protected override void OnResize(EventArgs e){base.OnResize(e);rename.Location=new Point(Width-108,76);edit.Location=new Point(Width-234,76);delete.Location=new Point(Width-298,76);}
 internal void UpdateTheme(bool dark){Dark=dark;rename.BackColor=dark?Color.FromArgb(43,48,60):Color.FromArgb(232,237,244);rename.ForeColor=dark?Color.FromArgb(194,204,221):Color.FromArgb(63,77,101);edit.BackColor=delete.BackColor=rename.BackColor;edit.ForeColor=delete.ForeColor=rename.ForeColor;Invalidate();}
 protected override void OnPaint(PaintEventArgs e){
  base.OnPaint(e);Graphics g=e.Graphics;g.SmoothingMode=SmoothingMode.AntiAlias;
  Color surface=Dark?Color.FromArgb(28,33,44):Color.White;Color fg=Dark?Color.FromArgb(235,240,249):Color.FromArgb(30,40,60);Color muted=Dark?Color.FromArgb(146,159,181):Color.FromArgb(102,118,139);
  using(GraphicsPath p=Round(new Rectangle(0,0,Width-1,Height-1),16))using(SolidBrush b=new SolidBrush(surface))g.FillPath(b,p);
  int? percent=Data==null?null:Data.Percent;Color accent=TrayApp.BatteryColor(percent);
  using(SolidBrush b=new SolidBrush(Dark?Color.FromArgb(37,46,55):Color.FromArgb(237,247,242)))g.FillEllipse(b,20,21,48,48);
  using(Icon icon=TrayApp.MakeIcon(Keyboard,percent))g.DrawIcon(icon,28,29);
  using(Font name=new Font("Microsoft JhengHei UI",11,FontStyle.Bold))using(Font number=new Font("Segoe UI",25,FontStyle.Bold))using(Font small=new Font("Microsoft JhengHei UI",9)){
   TextRenderer.DrawText(g,Data==null?"讀取中…":Data.Name,name,new Rectangle(82,18,Width-230,26),fg,TextFormatFlags.EndEllipsis|TextFormatFlags.NoPadding);
   TextRenderer.DrawText(g,Data==null?"正在取得裝置狀態":percent.HasValue?Data.Connection:Data.Status,small,new Rectangle(83,47,Width-230,22),muted,TextFormatFlags.EndEllipsis|TextFormatFlags.NoPadding);
   TextRenderer.DrawText(g,percent.HasValue?percent+"%":"—",number,new Rectangle(Width-142,13,120,45),percent.HasValue?accent:muted,TextFormatFlags.Right|TextFormatFlags.NoPadding);
   TextRenderer.DrawText(g,Data==null?"等待刷新":"刷新於 "+Data.Time.Substring(11),small,new Rectangle(22,81,190,20),muted,TextFormatFlags.NoPadding);
  }
  Rectangle track=new Rectangle(83,75,Math.Max(20,Width-245),5);
  using(SolidBrush b=new SolidBrush(Dark?Color.FromArgb(49,57,72):Color.FromArgb(228,234,242)))g.FillRectangle(b,track);
  if(percent.HasValue && percent>0)using(SolidBrush b=new SolidBrush(accent))g.FillRectangle(b,track.X,track.Y,(int)(track.Width*percent.Value/100.0),track.Height);
 }
 internal static GraphicsPath Round(Rectangle r,int radius){GraphicsPath p=new GraphicsPath();int d=radius*2;p.AddArc(r.X,r.Y,d,d,180,90);p.AddArc(r.Right-d,r.Y,d,d,270,90);p.AddArc(r.Right-d,r.Bottom-d,d,d,0,90);p.AddArc(r.X,r.Bottom-d,d,d,90,90);p.CloseFigure();return p;}
}
internal sealed class BatteryWindow:Form {
 [DllImport("dwmapi.dll")]static extern int DwmSetWindowAttribute(IntPtr hwnd,int attr,ref int value,int size);
 readonly Dictionary<string,DeviceCard> cards=new Dictionary<string,DeviceCard>();
 readonly FlowLayoutPanel cardPanel=new FlowLayoutPanel{Dock=DockStyle.Fill,FlowDirection=FlowDirection.TopDown,WrapContents=false,AutoScroll=true,Padding=new Padding(0,10,0,0)};
 readonly Button theme=new Button{AutoSize=true},refresh=new Button{Text="立即刷新",AutoSize=true},add=new Button{Text="新增裝置／USB 拔插",AutoSize=true},code=new Button{Text="輸入協定代碼",AutoSize=true};
 readonly Label subtitle=new Label{AutoSize=true};readonly CheckBox startup=new CheckBox{Text="登入 Windows 時啟動",AutoSize=true};
 readonly Action refreshAction;readonly Action<int,string> renameAction;readonly DeviceManager manager;bool dark;
 internal BatteryWindow(Action update,Action<int,string> rename,bool starts,Action<bool> changeStartup,DeviceManager devices=null){
  refreshAction=update;renameAction=rename;manager=devices;dark=UserPreferences.Current.Dark;
  Text="裝置電量";ClientSize=new Size(800,650);MinimumSize=new Size(730,560);StartPosition=FormStartPosition.CenterScreen;Font=new Font("Microsoft JhengHei UI",9);AutoScaleMode=AutoScaleMode.Dpi;DoubleBuffered=true;
  TableLayoutPanel root=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(24),ColumnCount=1,RowCount=5};root.RowStyles.Add(new RowStyle(SizeType.AutoSize));root.RowStyles.Add(new RowStyle(SizeType.AutoSize));root.RowStyles.Add(new RowStyle(SizeType.Percent,100));root.RowStyles.Add(new RowStyle(SizeType.AutoSize));root.RowStyles.Add(new RowStyle(SizeType.AutoSize));Controls.Add(root);
  FlowLayoutPanel header=new FlowLayoutPanel{AutoSize=true,Dock=DockStyle.Fill};header.Controls.Add(new Label{Text="裝置電量",AutoSize=true,Font=new Font("Microsoft JhengHei UI",24,FontStyle.Bold),Margin=new Padding(0,0,24,4)});header.Controls.AddRange(new Control[]{theme,add,code});root.Controls.Add(header,0,0);
  theme.Click+=(s,e)=>{dark=!dark;UserPreferences.Current.Dark=dark;try{UserPreferences.Save();}catch(Exception ex){MessageBox.Show(this,ex.Message,"無法儲存設定");}ApplyTheme();};
  add.Enabled=code.Enabled=manager!=null;add.Click+=(s,e)=>manager.Add(this);code.Click+=(s,e)=>manager.EnterCode(this);
  subtitle.Text="鍵盤與滑鼠的電量，一眼掌握。";root.Controls.Add(subtitle,0,1);root.Controls.Add(cardPanel,0,2);
  root.Controls.Add(new Label{Text="每 30 秒刷新 · 關閉視窗後仍在系統匣執行",AutoSize=true},0,3);
  FlowLayoutPanel footer=new FlowLayoutPanel{AutoSize=true,Dock=DockStyle.Fill};startup.Checked=starts;startup.CheckedChanged+=(s,e)=>changeStartup(startup.Checked);footer.Controls.Add(startup);footer.Controls.Add(refresh);root.Controls.Add(footer,0,4);refresh.Click+=(s,e)=>refreshAction();
  cardPanel.SizeChanged+=(s,e)=>{foreach(DeviceCard card in cards.Values)card.Width=Math.Max(600,cardPanel.ClientSize.Width-24);};ApplyTheme();
 }
 protected override void OnHandleCreated(EventArgs e){base.OnHandleCreated(e);ApplyTheme();}
 void ApplyTheme(){BackColor=dark?Color.FromArgb(17,21,30):Color.FromArgb(244,247,251);ForeColor=dark?Color.FromArgb(235,240,249):Color.FromArgb(30,40,60);
  foreach(Button button in new[]{theme,refresh,add,code}){button.FlatStyle=FlatStyle.Flat;button.FlatAppearance.BorderSize=0;button.BackColor=dark?Color.FromArgb(44,53,72):Color.FromArgb(225,233,246);button.ForeColor=ForeColor;}
  refresh.BackColor=Color.FromArgb(76,115,245);refresh.ForeColor=Color.White;theme.Text=dark?"切換淺色模式":"切換深色模式";foreach(DeviceCard card in cards.Values)card.UpdateTheme(dark);
  if(IsHandleCreated){int value=dark?1:0;try{DwmSetWindowAttribute(Handle,20,ref value,4);}catch{}}
 }
 internal void UpdateReadings(Reading[] readings,bool busy){
  HashSet<string> active=new HashSet<string>();int visible=0;cardPanel.SuspendLayout();
  for(int i=0;i<3;i++){int slot=i;string key="builtin:"+i;active.Add(key);DeviceCard card=Card(key,i==0);if(card.Tag==null){card.Tag=key;card.Rename+=()=>EditName(slot);}card.Data=readings==null?new Reading(BatteryReader.Names[i]){Status="讀取中…"}:readings[i];card.Visible=readings!=null&&readings[i].Present;if(card.Visible)visible++;card.Invalidate();}
  if(manager!=null)foreach(AddedDevice device in manager.Devices){string id=device.Id;active.Add(id);DeviceCard card=Card(id,device.Profile!=null&&device.Profile.protocol=="lofree");if(card.Tag==null){card.Tag=id;card.SetCustom(true);card.Rename+=()=>manager.Rename(this,id);card.EditProtocol+=()=>manager.Edit(this,id);card.Delete+=()=>manager.Delete(this,id);}Reading reading;card.Data=manager.Latest.TryGetValue(id,out reading)?reading:new Reading(device.Name){Status="等待刷新…"};card.Visible=true;card.Invalidate();visible++;}
  foreach(string key in new List<string>(cards.Keys))if(!active.Contains(key)){DeviceCard card=cards[key];cardPanel.Controls.Remove(card);card.Dispose();cards.Remove(key);}cardPanel.ResumeLayout();
  subtitle.Text=readings==null?"正在偵測裝置…":visible==0?"尚未偵測到支援裝置，可使用新增裝置或 USB 拔插排查。":"鍵盤與滑鼠的電量，一眼掌握。";refresh.Enabled=!busy;refresh.Text=busy?"刷新中…":"立即刷新";
 }
 DeviceCard Card(string id,bool keyboard){DeviceCard card;if(!cards.TryGetValue(id,out card)){card=new DeviceCard(keyboard){Width=Math.Max(600,cardPanel.ClientSize.Width-24)};cards[id]=card;cardPanel.Controls.Add(card);card.UpdateTheme(dark);}card.Keyboard=keyboard;return card;}
 void EditName(int slot){using(Form dialog=new Form{Text="重新命名裝置",ClientSize=new Size(420,150),StartPosition=FormStartPosition.CenterParent,Font=Font}){TextBox field=new TextBox{Text=BatteryReader.Names[slot],MaxLength=32,Location=new Point(24,30),Width=372};Button save=new Button{Text="儲存",DialogResult=DialogResult.OK,Location=new Point(306,90)};dialog.Controls.AddRange(new Control[]{field,save});dialog.AcceptButton=save;if(dialog.ShowDialog(this)==DialogResult.OK){if(string.IsNullOrWhiteSpace(field.Text)){MessageBox.Show(this,"名稱不能留空。");return;}renameAction(slot,field.Text.Trim());}}}
}
internal sealed class BatteryReader {
 internal static readonly string[] Names={"LOFREE 小順青春版(100鍵)","HECATE G3M PRO","HECATE G3M PRO 升級版"};
 readonly Native.Enumerate enumerate;readonly Native.Free free;readonly Native.Open open;
 readonly Native.Close close;readonly Native.Write write;readonly Native.Read read;
 readonly Native.OpenKeyboard kbOpen;readonly Native.QueryKeyboard kbQuery;readonly Native.CloseKeyboard kbClose;
 readonly Native.Battery upgraded;
 internal BatteryReader(){
  string hecate=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),"HECATE");
  string lofree=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),"Lofree Key Mapper","Sys64","HIDUsb.dll");
  string hid=Path.Combine(hecate,"hidapi.dll");
  enumerate=Native.Function<Native.Enumerate>(hid,"hid_enumerate");free=Native.Function<Native.Free>(hid,"hid_free_enumeration");
  open=Native.Function<Native.Open>(hid,"hid_open_path");close=Native.Function<Native.Close>(hid,"hid_close");
  write=Native.Function<Native.Write>(hid,"hid_write");read=Native.Function<Native.Read>(hid,"hid_read_timeout");
  kbOpen=Native.Function<Native.OpenKeyboard>(lofree,"UsbFinderC_OpenDevice");
  kbQuery=Native.Function<Native.QueryKeyboard>(lofree,"UsbFinderC_ReadWriteDeviceData");
  kbClose=Native.Function<Native.CloseKeyboard>(lofree,"UsbFinderC_CloseDevice");
  upgraded=Native.Function<Native.Battery>(Path.Combine(hecate,"HIDUsb.dll"),"UsbMouseC_GetBatteryLevel");
 }
 internal Reading[] Poll(){
  Reading[] results=Array.ConvertAll(Names,n=>new Reading(n));
  IntPtr head=enumerate(0,0);
  try {
   for(IntPtr p=head;p!=IntPtr.Zero;){
    Native.HidInfo h=(Native.HidInfo)Marshal.PtrToStructure(p,typeof(Native.HidInfo));p=h.next;
    // Presence is based on the physical VID/PID, even when battery reads fail.
    int model=ModelSlot(h.vid,h.pid);
    if(model>=0){results[model].Present=true;if(results[model].Status=="未連線")results[model].Status="已插入，未找到電量控制介面";}
    string path=Marshal.PtrToStringAnsi(h.path);int index=-1;
    // Query only the vendor control collection; never keyboard/mouse input collections.
    if(h.vid==0x05ac && h.pid==0x024f && path.IndexOf("Col05",StringComparison.OrdinalIgnoreCase)>=0) index=0;
    if(h.vid==0x320f && (h.pid==0x706b||h.pid==0x706e) && h.page==0xff1c) index=1;
    if(h.vid==0x35bb && (h.pid==0xd3fb||h.pid==0xd3fc) && h.page==0xff02) index=2;
    if(index<0||results[index].Percent.HasValue)continue;
    Reading r=results[index];r.Status="無法讀取電量";
    // Air100 uses the same VID/PID in wired and receiver modes; its USB
    // product descriptor changes from Air100@Lofree to 2.4G Wireless Receiver.
    string product=Marshal.PtrToStringUni(h.product)??"";
    bool keyboardReceiver=index==0 && product.IndexOf("Wireless Receiver",StringComparison.OrdinalIgnoreCase)>=0;
    r.Connection=keyboardReceiver||(index==1 && h.pid==0x706e)||(index==2 && h.pid==0xd3fb)?"2.4 GHz 接收器":"USB 有線";
    try {
     if(index==0) {
      if(kbOpen(path)==0)continue;
      try {
       byte[] request=new byte[17],response=new byte[17];request[0]=8;request[1]=4;request[5]=0x80;
       request[16]=Checksum(request,16);
       if(kbQuery(request,response,17)!=0 && response[0]==8 && response[1]==4 && response[16]==Checksum(response,16)) {
        r.Raw=BitConverter.ToString(response);Set(r,response[6],response[7]!=0);
       }
      }finally{kbClose();}
     } else if(index==1) {
      IntPtr dev=open(path);if(dev==IntPtr.Zero)continue;
      try {
       byte[] request=new byte[64],response=new byte[64];request[0]=4;request[3]=0x1a;request[4]=6;request[1]=0x20;
       if(write(dev,request,(UIntPtr)64)!=64)continue;
       DateTime until=DateTime.UtcNow.AddMilliseconds(1200);
       while(DateTime.UtcNow<until){
        int count=read(dev,response,(UIntPtr)64,200);
        if(count==64 && response[0]==4 && response[3]==0x1a && response[4]==6 && response[7]!=0xff && response[7]!=0xfe){
         r.Raw=BitConverter.ToString(response);Set(r,response[8],response[9]==1);break;
        }
        if(count<0)break;
       }
      }finally{close(dev);}
     } else {
      byte[] response=new byte[64];
      for(int attempt=0;attempt<3;attempt++){
       Array.Clear(response,0,response.Length);
       if(upgraded(path,response)!=0){r.Raw=BitConverter.ToString(response,0,4);Set(r,response[0],response[1]!=0);break;}
       if(attempt<2)Thread.Sleep(80);
      }
     }
    } catch(Exception ex){r.Status="讀取失敗："+ex.Message;}
   }
  }finally{if(head!=IntPtr.Zero)free(head);}
  return results;
 }
 internal static int ModelSlot(ushort vid,ushort pid){
  if(vid==0x05ac && pid==0x024f)return 0;
  if(vid==0x320f && (pid==0x706b||pid==0x706e))return 1;
  if(vid==0x35bb && (pid==0xd3fb||pid==0xd3fc))return 2;
  return -1;
 }
 static byte Checksum(byte[] b,int count){int sum=0;for(int i=0;i<count;i++)sum+=b[i];return unchecked((byte)(0x55-sum));}
 static void Set(Reading r,int percent,bool charging){
  if(percent>100){r.Status="電量回應無效";return;}
  r.Percent=percent;r.Status="已連線";
 }
}
internal sealed class TrayApp:ApplicationContext {
 readonly EventWaitHandle showSignal;readonly System.Windows.Forms.Timer signalTimer;
 BatteryWindow window;
 readonly NotifyIcon[] icons=new NotifyIcon[3];readonly System.Windows.Forms.Timer timer;
 readonly Control dispatch=new Control();bool busy,exiting;Reading[] latest;
 readonly string dataDir=Application.StartupPath;readonly DeviceManager custom;
 internal TrayApp(EventWaitHandle signal){
  showSignal=signal;
  IntPtr dispatchHandle=dispatch.Handle;
  custom=new DeviceManager(dispatch,ShowReadings);custom.Changed+=()=>{if(window!=null&&!window.IsDisposed)window.UpdateReadings(latest,busy);};
  for(int i=0;i<3;i++){
   int slot=i;
   ContextMenuStrip menu=new ContextMenuStrip();
   menu.Items.Add(BatteryReader.Names[i]).Enabled=false;
   menu.Items.Add("立即刷新",null,(s,e)=>Refresh());
   menu.Items.Add("查看全部電量",null,(s,e)=>ShowReadings());
   ToolStripMenuItem auto=new ToolStripMenuItem("登入 Windows 時啟動");
   auto.Checked=IsStartup();auto.Click+=(s,e)=>{SetStartup(!IsStartup());};
   menu.Opening+=(s,e)=>{auto.Checked=IsStartup();menu.Items[0].Text=BatteryReader.Names[slot];menu.Renderer=new ToolStripProfessionalRenderer(new TrayColors(UserPreferences.Current.Dark));menu.ForeColor=UserPreferences.Current.Dark?Color.FromArgb(235,240,249):Color.FromArgb(30,40,60);};menu.Items.Add(auto);
   menu.Items.Add("結束全部圖示",null,(s,e)=>ExitThread());
   icons[i]=new NotifyIcon{Icon=MakeIcon(i==0,null),Text=BatteryReader.Names[i]+" — 讀取中",ContextMenuStrip=menu,Visible=false};
   icons[i].DoubleClick+=(s,e)=>ShowReadings();
  }
  timer=new System.Windows.Forms.Timer{Interval=30000};timer.Tick+=(s,e)=>Refresh();timer.Start();Refresh();ShowReadings();
  signalTimer=new System.Windows.Forms.Timer{Interval=500};signalTimer.Tick+=(s,e)=>{if(showSignal.WaitOne(0))ShowReadings();};signalTimer.Start();
 }
 internal static Color BatteryColor(int? p){return !p.HasValue?Color.FromArgb(145,151,160):p>70?Color.FromArgb(40,194,93):p>=30?Color.FromArgb(255,158,35):Color.FromArgb(239,65,65);}
 internal static Icon MakeIcon(bool keyboard,int? percent){
  // Native transparent 32 px artwork; each device owns a distinct NotifyIcon.
  using(Bitmap b=new Bitmap(32,32))using(Graphics g=Graphics.FromImage(b)){
   g.SmoothingMode=SmoothingMode.AntiAlias;g.Clear(Color.Transparent);Color color=BatteryColor(percent);
   using(Pen pen=new Pen(color,2.5f))using(SolidBrush brush=new SolidBrush(color)){
    if(keyboard){
     g.DrawRectangle(pen,2,7,28,19);
     for(int row=0;row<2;row++)for(int col=0;col<6;col++)g.FillRectangle(brush,5+col*4,11+row*5,2.2f,2.2f);
     g.FillRectangle(brush,9,21,14,2.5f);
    }else{
     using(GraphicsPath path=new GraphicsPath()){
      path.AddArc(6,2,20,20,180,180);path.AddLine(26,12,26,21);path.AddArc(6,11,20,20,0,180);path.CloseFigure();g.DrawPath(pen,path);
     }
     g.DrawLine(pen,16,3,16,14);g.DrawLine(pen,7,14,25,14);g.FillRectangle(brush,14.5f,6,3,5);
    }
    if(!percent.HasValue){using(Font f=new Font("Segoe UI",12,FontStyle.Bold))g.DrawString("?",f,brush,19,16);}
   }
   IntPtr handle=b.GetHicon();try{return (Icon)Icon.FromHandle(handle).Clone();}finally{Native.DestroyIcon(handle);}
  }
 }
 void Refresh(){
  if(busy||exiting)return;custom.Refresh();busy=true;if(window!=null&&!window.IsDisposed)window.UpdateReadings(latest,true);
  Task.Run(()=>{
   Reading[] readings;
   try{readings=new BatteryReader().Poll();}
   catch(Exception ex){try{readings=WindowsHid.ReadBuiltins();}catch(Exception nativeError){readings=Array.ConvertAll(BatteryReader.Names,n=>new Reading(n){Status="讀取失敗："+ex.Message+" / "+nativeError.Message});}}
   try{Directory.CreateDirectory(dataDir);File.WriteAllText(Path.Combine(dataDir,"status.json"),new JavaScriptSerializer().Serialize(readings));}catch{}
   if(exiting)return;
   try{dispatch.BeginInvoke((Action)(()=>{
    if(exiting)return;latest=readings;for(int i=0;i<3;i++)latest[i].Name=BatteryReader.Names[i];
    for(int i=0;i<3;i++){
     Reading r=readings[i];Icon old=icons[i].Icon;icons[i].Icon=MakeIcon(i==0,r.Percent);old.Dispose();
     string tip=r.Name+"\n"+(r.Percent.HasValue?r.Percent.Value+"% · "+r.Connection:r.Status);
     icons[i].Text=tip.Length>63?tip.Substring(0,63):tip;
     icons[i].Visible=r.Present;
    }
    busy=false;if(window!=null&&!window.IsDisposed)window.UpdateReadings(latest,false);
   }));}catch(InvalidOperationException){}
  });
 }
 void ShowReadings(){
  if(window==null||window.IsDisposed)window=new BatteryWindow(Refresh,Rename,IsStartup(),SetStartup,custom);
  window.UpdateReadings(latest,busy);window.Show();if(window.WindowState==FormWindowState.Minimized)window.WindowState=FormWindowState.Normal;window.Activate();
 }
 void Rename(int slot,string name){
  string previous=BatteryReader.Names[slot];BatteryReader.Names[slot]=name;
  try{UserPreferences.Save();}catch(Exception ex){BatteryReader.Names[slot]=previous;MessageBox.Show(ex.Message,"無法儲存名稱");return;}
  if(latest!=null){latest[slot].Name=name;Reading r=latest[slot];string tip=name+"\n"+(r.Percent.HasValue?r.Percent+"% · "+r.Connection:r.Status);icons[slot].Text=tip.Length>63?tip.Substring(0,63):tip;}
  else icons[slot].Text=name+" — 讀取中";
  window.UpdateReadings(latest,busy);
 }
 static bool IsStartup(){using(RegistryKey k=Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run"))return k!=null && (string)k.GetValue("DeviceBatteryTray")=="\""+Application.ExecutablePath+"\"";}
 static void SetStartup(bool enable){
  try{using(RegistryKey k=Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Run")){if(enable)k.SetValue("DeviceBatteryTray","\""+Application.ExecutablePath+"\"");else k.DeleteValue("DeviceBatteryTray",false);}}
  catch(Exception ex){MessageBox.Show(ex.Message,"無法變更自動啟動");}
 }
 protected override void ExitThreadCore(){exiting=true;custom.Dispose();signalTimer.Stop();signalTimer.Dispose();if(window!=null)window.Dispose();timer.Stop();timer.Dispose();foreach(NotifyIcon n in icons){n.Visible=false;Icon ic=n.Icon;n.Dispose();ic.Dispose();}dispatch.Dispose();base.ExitThreadCore();}
}
internal static class Program {
 [STAThread] static int Main(string[] args){
  UserPreferences.Load();
  if(args.Length>0&&args[0]=="--test-profiles"){
   try{ProfileTests.Run();return 0;}catch(Exception ex){Console.Error.WriteLine(ex);File.WriteAllText(Path.Combine(Path.GetTempPath(),"device-battery-profile-tests.log"),ex.ToString());return 10;}
  }
  if(args.Length>0 && args[0]=="--preview-ui"){
   Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
   Reading[] sample=Array.ConvertAll(BatteryReader.Names,n=>new Reading(n){Percent=85,Connection="2.4 GHz 接收器",Status="已連線",Present=true});sample[1].Percent=48;sample[2].Percent=null;sample[2].Status="裝置離線";
   using(BatteryWindow form=new BatteryWindow(()=>{},(i,n)=>{},false,b=>{})){form.UpdateReadings(sample,false);form.Show();Application.DoEvents();using(Bitmap bitmap=new Bitmap(form.Width,form.Height)){form.DrawToBitmap(bitmap,new Rectangle(Point.Empty,form.Size));bitmap.Save(args[1],System.Drawing.Imaging.ImageFormat.Png);}}return 0;
  }
  if(args.Length>0 && args[0]=="--diagnose"){
   try{File.WriteAllText(args.Length>1?args[1]:"status.json",new JavaScriptSerializer().Serialize(WindowsHid.ReadBuiltins()));return 0;}
   catch(Exception ex){File.WriteAllText(args.Length>1?args[1]:"status.json",ex.ToString());return 1;}
  }
  if(args.Length>0 && args[0]=="--self-test"){
   if(BatteryReader.ModelSlot(0x05ac,0x024f)!=0||BatteryReader.ModelSlot(0x320f,0x706e)!=1||BatteryReader.ModelSlot(0x35bb,0xd3fb)!=2||BatteryReader.ModelSlot(0,0)!=-1)return 3;
   if(TrayApp.BatteryColor(71)!=TrayApp.BatteryColor(100)||TrayApp.BatteryColor(30)!=TrayApp.BatteryColor(70)||TrayApp.BatteryColor(0)!=TrayApp.BatteryColor(29)||TrayApp.BatteryColor(30)==TrayApp.BatteryColor(29)||TrayApp.BatteryColor(70)==TrayApp.BatteryColor(71))return 1;
   using(Icon a=TrayApp.MakeIcon(true,95))using(Icon b=TrayApp.MakeIcon(false,20)){if(a.Handle==IntPtr.Zero||b.Handle==IntPtr.Zero)return 2;}
   if(args.Length>1){using(Bitmap preview=new Bitmap(480,130))using(Graphics g=Graphics.FromImage(preview))using(Font f=new Font("Segoe UI",10)){
    g.Clear(Color.FromArgb(30,33,40));int?[] levels={100,70,30,29,null};
    for(int i=0;i<levels.Length;i++){using(Icon a=TrayApp.MakeIcon(true,levels[i]))using(Icon b=TrayApp.MakeIcon(false,levels[i])){g.DrawIcon(a,i*96+14,14);g.DrawIcon(b,i*96+50,14);g.DrawString(levels[i].HasValue?levels[i]+"%":"Offline",f,Brushes.White,i*96+18,65);}}
    preview.Save(args[1],System.Drawing.Imaging.ImageFormat.Png);
   }}
   return 0;
  }
  bool created;using(Mutex mutex=new Mutex(true,@"Local\DeviceBatteryTray.Singleton",out created)){
   if(!created){try{using(EventWaitHandle signal=EventWaitHandle.OpenExisting(@"Local\DeviceBatteryTray.Show"))signal.Set();}catch(WaitHandleCannotBeOpenedException){}return 0;}
   using(EventWaitHandle signal=new EventWaitHandle(false,EventResetMode.AutoReset,@"Local\DeviceBatteryTray.Show")){Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new TrayApp(signal));}
  }return 0;
 }
}
