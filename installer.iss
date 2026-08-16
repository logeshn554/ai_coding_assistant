; =====================================================================
; Loopix AI Coding Assistant - Full VS Code Style Windows Installer
; =====================================================================

#define MyAppName "Loopix AI Editor"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Loopix Team"
#define MyAppURL "https://loopix.ai"
#define MyAppExeName "Loopix.exe"

[Setup]
AppId={{D37E8675-812C-4A2D-A32F-E2B45A884719}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\Loopix
DisableDirPage=no
DisableProgramGroupPage=auto
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
PrivilegesRequired=lowest
OutputDir=dist_installer
OutputBaseFilename=Loopix-Windows-Setup-{#MyAppVersion}
SetupIconFile=assets\devpilot.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
LicenseFile=TERMS_AND_CONDITIONS.txt
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addcontextmenufiles"; Description: "Add ""Open with Loopix"" action to Windows Explorer file context menu"; GroupDescription: "Other:"; Flags: checkedonce
Name: "addcontextmenufolders"; Description: "Add ""Open with Loopix"" action to Windows Explorer directory context menu"; GroupDescription: "Other:"; Flags: checkedonce
Name: "associatewithfiles"; Description: "Register Loopix as an editor for supported file types"; GroupDescription: "Other:"; Flags: unchecked
Name: "addtopath"; Description: "Add to PATH (restart terminals to apply)"; GroupDescription: "Other:"; Flags: checkedonce

[Files]
Source: "dist\Loopix\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; PATH environment variable
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Flags: preservestringtype

; "Open with Loopix" for files
Root: HKCU; Subkey: "Software\Classes\*\shell\Loopix"; ValueType: string; ValueName: ""; ValueData: "Open with Loopix"; Tasks: addcontextmenufiles; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\Loopix"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: addcontextmenufiles
Root: HKCU; Subkey: "Software\Classes\*\shell\Loopix\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: addcontextmenufiles

; "Open with Loopix" for folders
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Loopix"; ValueType: string; ValueName: ""; ValueData: "Open with Loopix"; Tasks: addcontextmenufolders; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Loopix"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: addcontextmenufolders
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Loopix\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%V"""; Tasks: addcontextmenufolders

; "Open with Loopix" for folder background
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\Loopix"; ValueType: string; ValueName: ""; ValueData: "Open with Loopix"; Tasks: addcontextmenufolders; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\Loopix"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: addcontextmenufolders
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\Loopix\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%V"""; Tasks: addcontextmenufolders

[Run]
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Loopix AI Editor"" dir=in action=allow program=""{app}\{#MyAppExeName}"" enable=yes"; Flags: runhidden
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Loopix AI Editor"""; Flags: runhidden
