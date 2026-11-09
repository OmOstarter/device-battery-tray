using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class ProfileTests {
 static void Check(bool value,string message){if(!value)throw new Exception(message);}
 internal static void Preview(string directory){
  Directory.CreateDirectory(directory);DeviceProfile profile=new DeviceProfile{name="小順青春版 84 鍵",vid="05AC",pid="024F",protocol="lofree"};
  AddedDevice device=new AddedDevice{Id=profile.Key(),Name=profile.name,Profile=profile,DriverPath=@"C:\Program Files\Lofree\HIDUsb.dll",Notes="84 鍵，2.4 GHz 接收器"};
  using(ProtocolEditor editor=new ProtocolEditor(device)){editor.Show();Application.DoEvents();Capture(editor,Path.Combine(directory,"protocol-form.png"));TabControl tabs=(TabControl)typeof(ProtocolEditor).GetField("tabs",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(editor);tabs.SelectedIndex=2;Application.DoEvents();Capture(editor,Path.Combine(directory,"protocol-prompt.png"));editor.Close();}
  using(UsbPicker picker=new UsbPicker(true)){picker.Show();Application.DoEvents();Capture(picker,Path.Combine(directory,"usb-monitor.png"));picker.Close();}
  using(Form form=new Form{ClientSize=new Size(740,150),BackColor=Color.FromArgb(17,21,30)}){DeviceCard card=new DeviceCard(true){Width=700,Location=new Point(20,16),Data=new Reading(device.Name){Present=true,Status="等待刷新…"}};card.SetCustom(true);card.UpdateTheme(true);form.Controls.Add(card);form.Show();Application.DoEvents();Capture(form,Path.Combine(directory,"custom-card.png"));form.Close();}
 }
 static void Capture(Form form,string path){using(Bitmap image=new Bitmap(form.Width,form.Height)){form.DrawToBitmap(image,new Rectangle(Point.Empty,form.Size));image.Save(path,System.Drawing.Imaging.ImageFormat.Png);}}
 internal static void Run(){
  const string example="{\"version\":1,\"name\":\"我的鍵盤\",\"vid\":\"05AC\",\"pid\":\"024F\",\"protocol\":\"lofree\"}";
  DeviceProfile profile=DeviceProfile.Parse(example);Check(profile.vid=="05AC","hex normalization");
  string encoded="DBT1:"+Convert.ToBase64String(Encoding.UTF8.GetBytes(example)).Replace('+','-').Replace('/','_').TrimEnd('=');Check(DeviceProfile.Parse(encoded).Key()==profile.Key(),"DBT1 roundtrip");
  foreach(string invalid in new[]{"[]","{}","05AC:024F","DBT1:???",example.Replace("lofree","unknown"),example.Replace("05AC","0000"),example.Replace("\"version\":1,","")}){bool rejected=false;try{DeviceProfile.Parse(invalid);}catch{rejected=true;}Check(rejected,"accepted invalid code: "+invalid);}
  foreach(string protocol in DeviceProfile.Protocols){byte[] request=DeviceProfile.Request(protocol,true);Check(request.Length==(protocol=="hecate-original"?64:17),"request length");byte[] response=(byte[])request.Clone();response[protocol=="hecate-original"?8:6]=73;if(response.Length==17){int sum=0;for(int i=0;i<16;i++)sum+=response[i];response[16]=(byte)((0x55-sum)&255);}Check(DeviceProfile.Response(protocol,response)==73,"response parse");response[0]^=1;Check(!DeviceProfile.Response(protocol,response).HasValue,"corrupt response accepted");}
  Dictionary<string,UsbDevice> before=new Dictionary<string,UsbDevice>{{"first",new UsbDevice{Id="first",Name="keyboard"}}},after=new Dictionary<string,UsbDevice>{{"second",new UsbDevice{Id="second",Name="mouse"}}};
  Check(UsbInventory.Changes(before,after).SequenceEqual(new[]{"拔除|first","插入|second"}),"hotplug diff");Check(UsbInventory.Changes(before,before).Count==0,"unchanged USB reported");
  UserPreferences prefs=new UserPreferences();prefs.Added.Add(new AddedDevice{Id=profile.Key(),Name=profile.name,Profile=profile,DriverPath=@"C:\vendor\HIDUsb.dll",Notes="84 keys"});JavaScriptSerializer json=new JavaScriptSerializer();UserPreferences restored=json.Deserialize<UserPreferences>(json.Serialize(prefs));Check(restored.Added.Count==1&&restored.Added[0].DriverPath==@"C:\vendor\HIDUsb.dll"&&restored.Added[0].Profile.Key()==profile.Key(),"settings roundtrip");
  string prompt=ProtocolEditor.Prompt("{\"name\":\"84 keys\"}");Check(prompt.Contains("84 keys")&&prompt.Contains("不可硬套")&&prompt.Contains("DeviceProfiles.cs")&&prompt.Contains("DBT1:"),"agent handoff prompt");
  Application.EnableVisualStyles();using(ProtocolEditor editor=new ProtocolEditor(prefs.Added[0])){Check(editor.Text=="編輯協定代碼","editor title");FieldInfo field=typeof(ProtocolEditor).GetField("fields",BindingFlags.Instance|BindingFlags.NonPublic);Dictionary<string,TextBox> fields=(Dictionary<string,TextBox>)field.GetValue(editor);Check(fields["vid"].Text=="05AC"&&fields["driver_path"].Text==@"C:\vendor\HIDUsb.dll","editor prefill");fields["notes"].Text="modified";TextBox output=(TextBox)typeof(ProtocolEditor).GetField("prompt",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(editor);Check(output.Text.Contains("modified"),"live prompt update");editor.Show();Application.DoEvents();editor.Close();}
  using(DeviceCard card=new DeviceCard(false)){card.SetCustom(true);card.UpdateTheme(true);card.Width=700;}
 }
}
