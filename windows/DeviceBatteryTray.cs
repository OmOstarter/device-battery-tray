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
 public bool Dark=true;public string[] Names;
 internal static UserPreferences Current=new UserPreferences();
 static string FilePath {get{return Path.Combine(Application.StartupPath,"preferences.json");}}
 internal static void Load(){
  try{if(File.Exists(FilePath))Current=new JavaScriptSerializer().Deserialize<UserPreferences>(File.ReadAllText(FilePath))??new UserPreferences();}catch{}
  if(Current.Names!=null && Current.Names.Length==3)for(int i=0;i<3;i++)if(!string.IsNullOrWhiteSpace(Current.Names[i])&&Current.Names[i].Length<=32)BatteryReader.Names[i]=Current.Names[i].Trim();
 }
 internal static void Save(){Current.Names=(string[])BatteryReader.Names.Clone();File.WriteAllText(FilePath,new JavaScriptSerializer().Serialize(Current));}
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
 internal event Action Rename;
 internal DeviceCard(bool keyboard){Keyboard=keyboard;DoubleBuffered=true;Height=114;Margin=new Padding(0,0,0,12);rename.FlatAppearance.BorderSize=0;rename.Click+=(s,e)=>{if(Rename!=null)Rename();};Controls.Add(rename);}
 protected override void OnResize(EventArgs e){base.OnResize(e);rename.Location=new Point(Width-108,76);}
 internal void UpdateTheme(bool dark){Dark=dark;rename.BackColor=dark?Color.FromArgb(43,48,60):Color.FromArgb(232,237,244);rename.ForeColor=dark?Color.FromArgb(194,204,221):Color.FromArgb(63,77,101);Invalidate();}
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
   TextRenderer.DrawText(g,Data==null?"等待更新":"更新於 "+Data.Time.Substring(11),small,new Rectangle(22,81,190,20),muted,TextFormatFlags.NoPadding);
  }
  Rectangle track=new Rectangle(83,75,Math.Max(20,Width-245),5);
  using(SolidBrush b=new SolidBrush(Dark?Color.FromArgb(49,57,72):Color.FromArgb(228,234,242)))g.FillRectangle(b,track);
  if(percent.HasValue && percent>0)using(SolidBrush b=new SolidBrush(accent))g.FillRectangle(b,track.X,track.Y,(int)(track.Width*percent.Value/100.0),track.Height);
 }
 internal static GraphicsPath Round(Rectangle r,int radius){GraphicsPath p=new GraphicsPath();int d=radius*2;p.AddArc(r.X,r.Y,d,d,180,90);p.AddArc(r.Right-d,r.Y,d,d,270,90);p.AddArc(r.Right-d,r.Bottom-d,d,d,0,90);p.AddArc(r.X,r.Bottom-d,d,d,90,90);p.CloseFigure();return p;}
}
internal sealed class BatteryWindow:Form {
 [DllImport("dwmapi.dll")]static extern int DwmSetWindowAttribute(IntPtr hwnd,int attr,ref int value,int size);
 readonly DeviceCard[] cards=new DeviceCard[3];readonly Button theme=new Button(),refresh=new Button();
 readonly Label heading=new Label(),subtitle=new Label(),footer=new Label();readonly CheckBox startup=new CheckBox();
 readonly Action refreshAction;readonly Action<int,string> renameAction;readonly Action<bool> startupAction;bool dark;
 internal BatteryWindow(Action update,Action<int,string> rename,bool starts,Action<bool> changeStartup){
  refreshAction=update;renameAction=rename;startupAction=changeStartup;dark=UserPreferences.Current.Dark;
  Text="裝置電量";ClientSize=new Size(690,570);MinimumSize=new Size(650,600);StartPosition=FormStartPosition.CenterScreen;Font=new Font("Microsoft JhengHei UI",9);AutoScaleMode=AutoScaleMode.Dpi;DoubleBuffered=true;
  heading.Text="裝置電量";heading.Font=new Font("Microsoft JhengHei UI",24,FontStyle.Bold);heading.SetBounds(28,24,340,48);
  subtitle.Text="鍵盤與滑鼠的電量，一眼掌握。";subtitle.SetBounds(31,80,410,24);
  theme.SetBounds(532,37,128,34);theme.Click+=(s,e)=>{dark=!dark;UserPreferences.Current.Dark=dark;try{UserPreferences.Save();}catch(Exception ex){MessageBox.Show(this,ex.Message,"無法儲存設定");}ApplyTheme();};
  Controls.AddRange(new Control[]{heading,subtitle,theme});
  for(int i=0;i<3;i++){int slot=i;cards[i]=new DeviceCard(i==0){Location=new Point(28,122+i*126),Width=632,Anchor=AnchorStyles.Top|AnchorStyles.Left|AnchorStyles.Right,Data=new Reading(BatteryReader.Names[i]){Status="讀取中…"}};cards[i].Rename+=()=>EditName(slot);Controls.Add(cards[i]);}
  startup.Text="登入 Windows 時啟動";startup.AutoSize=true;startup.Checked=starts;startup.SetBounds(31,520,240,26);startup.CheckedChanged+=(s,e)=>startupAction(startup.Checked);
  refresh.Text="立即更新";refresh.SetBounds(544,513,116,36);refresh.Anchor=AnchorStyles.Bottom|AnchorStyles.Right;refresh.Click+=(s,e)=>refreshAction();
  footer.Text="每 30 秒更新 · 關閉視窗後仍在系統匣執行";footer.SetBounds(31,489,500,22);
  Controls.AddRange(new Control[]{startup,refresh,footer});ApplyTheme();
 }
 protected override void OnHandleCreated(EventArgs e){base.OnHandleCreated(e);ApplyTitleTheme();}
 void ApplyTitleTheme(){if(IsHandleCreated){int value=dark?1:0;try{DwmSetWindowAttribute(Handle,20,ref value,4);}catch{}}}
 void ApplyTheme(){
  BackColor=dark?Color.FromArgb(17,21,30):Color.FromArgb(244,247,251);ForeColor=dark?Color.FromArgb(235,240,249):Color.FromArgb(30,40,60);
  heading.ForeColor=ForeColor;startup.ForeColor=ForeColor;subtitle.ForeColor=footer.ForeColor=dark?Color.FromArgb(146,159,181):Color.FromArgb(102,118,139);
  foreach(Button button in new[]{theme,refresh}){button.FlatStyle=FlatStyle.Flat;button.FlatAppearance.BorderSize=0;button.Cursor=Cursors.Hand;button.BackColor=dark?Color.FromArgb(44,53,72):Color.FromArgb(225,233,246);button.ForeColor=ForeColor;}
  refresh.BackColor=Color.FromArgb(76,115,245);refresh.ForeColor=Color.White;theme.Text=dark?"切換淺色模式":"切換深色模式";
  foreach(DeviceCard card in cards)if(card!=null)card.UpdateTheme(dark);ApplyTitleTheme();Invalidate();
 }
 internal void UpdateReadings(Reading[] readings,bool busy){
  int visible=0;
  for(int i=0;i<cards.Length;i++){
   cards[i].Visible=readings!=null && readings[i].Present;
   if(readings!=null){cards[i].Data=readings[i];if(readings[i].Present)cards[i].Location=new Point(28,122+visible++*126);cards[i].Invalidate();}
  }
  subtitle.Text=readings==null?"正在偵測裝置…":visible==0?"尚未偵測到支援裝置，插入鍵盤、滑鼠或接收器後將自動顯示。":"鍵盤與滑鼠的電量，一眼掌握。";
  refresh.Enabled=!busy;refresh.Text=busy?"更新中…":"立即更新";
 }
 void EditName(int slot){
  using(Form dialog=new Form{Text="重新命名裝置",ClientSize=new Size(420,170),FormBorderStyle=FormBorderStyle.FixedDialog,StartPosition=FormStartPosition.CenterParent,MaximizeBox=false,MinimizeBox=false,BackColor=BackColor,ForeColor=ForeColor,Font=Font}){
   Label label=new Label{Text="裝置名稱（最多 32 個字元）",Location=new Point(24,20),AutoSize=true};
   TextBox field=new TextBox{Text=BatteryReader.Names[slot],MaxLength=32,Location=new Point(24,52),Width=372,BackColor=dark?Color.FromArgb(35,42,56):Color.White,ForeColor=ForeColor,BorderStyle=BorderStyle.FixedSingle};
   Button save=new Button{Text="儲存",DialogResult=DialogResult.OK,Location=new Point(306,112),Size=new Size(90,34),FlatStyle=FlatStyle.Flat,BackColor=Color.FromArgb(76,115,245),ForeColor=Color.White};
   Button cancel=new Button{Text="取消",DialogResult=DialogResult.Cancel,Location=new Point(204,112),Size=new Size(90,34),FlatStyle=FlatStyle.Flat,ForeColor=ForeColor};
   dialog.Controls.AddRange(new Control[]{label,field,save,cancel});dialog.AcceptButton=save;dialog.CancelButton=cancel;
   if(dialog.ShowDialog(this)==DialogResult.OK){if(string.IsNullOrWhiteSpace(field.Text)){MessageBox.Show(this,"名稱不能留空。","重新命名");return;}renameAction(slot,field.Text.Trim());}
  }
 }
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
 readonly string dataDir=Application.StartupPath;
 internal TrayApp(EventWaitHandle signal){
  showSignal=signal;
  IntPtr dispatchHandle=dispatch.Handle;
  for(int i=0;i<3;i++){
   int slot=i;
   ContextMenuStrip menu=new ContextMenuStrip();
   menu.Items.Add(BatteryReader.Names[i]).Enabled=false;
   menu.Items.Add("立即更新",null,(s,e)=>Refresh());
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
  if(busy||exiting)return;busy=true;if(window!=null&&!window.IsDisposed)window.UpdateReadings(latest,true);
  Task.Run(()=>{
   Reading[] readings;
   try{readings=new BatteryReader().Poll();}
   catch(Exception ex){readings=Array.ConvertAll(BatteryReader.Names,n=>new Reading(n){Status="讀取失敗："+ex.Message});}
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
  if(window==null||window.IsDisposed)window=new BatteryWindow(Refresh,Rename,IsStartup(),SetStartup);
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
 protected override void ExitThreadCore(){exiting=true;signalTimer.Stop();signalTimer.Dispose();if(window!=null)window.Dispose();timer.Stop();timer.Dispose();foreach(NotifyIcon n in icons){n.Visible=false;Icon ic=n.Icon;n.Dispose();ic.Dispose();}dispatch.Dispose();base.ExitThreadCore();}
}
internal static class Program {
 [STAThread] static int Main(string[] args){
  UserPreferences.Load();
  if(args.Length>0 && args[0]=="--preview-ui"){
   Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
   Reading[] sample=Array.ConvertAll(BatteryReader.Names,n=>new Reading(n){Percent=85,Connection="2.4 GHz 接收器",Status="已連線",Present=true});sample[1].Percent=48;sample[2].Percent=null;sample[2].Status="裝置離線";
   using(BatteryWindow form=new BatteryWindow(()=>{},(i,n)=>{},false,b=>{})){form.UpdateReadings(sample,false);form.Show();Application.DoEvents();using(Bitmap bitmap=new Bitmap(form.Width,form.Height)){form.DrawToBitmap(bitmap,new Rectangle(Point.Empty,form.Size));bitmap.Save(args[1],System.Drawing.Imaging.ImageFormat.Png);}}return 0;
  }
  if(args.Length>0 && args[0]=="--diagnose"){
   try{File.WriteAllText(args.Length>1?args[1]:"status.json",new JavaScriptSerializer().Serialize(new BatteryReader().Poll()));return 0;}
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
