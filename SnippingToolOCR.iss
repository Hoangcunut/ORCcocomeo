[Setup]
AppName=SnippingToolOCR
AppVersion=1.0.0
AppPublisher=Hoangcunut
DefaultDirName={autopf}\SnippingToolOCR
DisableProgramGroupPage=yes
OutputBaseFilename=SnippingToolOCR-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\SnippingTool.exe
PrivilegesRequired=admin
OutputDir=dist

[Files]
Source: "dist\SnippingTool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SnippingToolOCR"; Filename: "{app}\SnippingTool.exe"
Name: "{autodesktop}\SnippingToolOCR"; Filename: "{app}\SnippingTool.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\SnippingTool.exe"; Description: "{cm:LaunchProgram,SnippingToolOCR}"; Flags: nowait postinstall skipifsilent
