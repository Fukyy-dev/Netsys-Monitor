; Inno Setup (https://jrsoftware.org/isinfo.php). Build: iscc /DAppVersion=2.2 packaging\installer.iss
; Prasyarat: dist\NetsysMonitor.exe hasil PyInstaller (mode onefile).
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
[Setup]
AppId={{B7E6F2A1-4C2D-4B7E-9C1A-5E3D8A9F0C11}
AppName=Netsys Monitor
AppVersion={#AppVersion}
AppPublisher=Netsys Monitor contributors
DefaultDirName={autopf}\Netsys Monitor
DefaultGroupName=Netsys Monitor
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=NetsysMonitor-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\NetsysMonitor.exe
CloseApplications=force
RestartApplications=no
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Buat pintasan di Desktop"; Flags: unchecked
Name: "autostart"; Description: "Mulai otomatis dengan Windows (diam-diam di system tray)"; Flags: unchecked

[Files]
Source: "..\dist\NetsysMonitor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Netsys Monitor"; Filename: "{app}\NetsysMonitor.exe"
Name: "{group}\Hapus Netsys Monitor"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Netsys Monitor"; Filename: "{app}\NetsysMonitor.exe"; Tasks: desktopicon

[Registry]
; Sama dengan yang ditulis aplikasi sendiri dari menu tray (HKCU, tanpa admin)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "NetsysMonitor"; \
  ValueData: """{app}\NetsysMonitor.exe"" --background"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\NetsysMonitor.exe"; Description: "Jalankan Netsys Monitor"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Best effort: bersihkan entri hosts bila pernah memakai --hosts (butuh admin; gagal diam-diam bila tidak)
Filename: "{app}\NetsysMonitor.exe"; Parameters: "--remove-hosts"; Flags: runhidden; RunOnceId: "RemoveHosts"
