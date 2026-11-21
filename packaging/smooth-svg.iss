; Build: iscc /DAppVersion=0.2.0 packaging\smooth-svg.iss  (needs dist\smooth-svg from PyInstaller and packaging\smooth-svg.ico from make_ico.py)
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Never change AppId: it is how upgrades find the installed copy.
AppId={{6F0E5B1C-3A52-4D8E-9B7A-5C1D2E8F4A93}
AppName=smooth-svg
AppVersion={#AppVersion}
AppPublisher=PatrikGuerra
AppPublisherURL=https://github.com/PatrikGuerra/smooth-svg
DefaultDirName={autopf}\smooth-svg
DefaultGroupName=smooth-svg
DisableProgramGroupPage=yes
; Per-user install: no administrator prompt. {autopf} becomes %LOCALAPPDATA%\Programs.
PrivilegesRequired=lowest
; The app must create this named mutex (same string) so setup can detect and close it.
AppMutex=smooth-svg-app
CloseApplications=yes
RestartApplications=yes
LicenseFile=..\LICENSE
SetupIconFile=smooth-svg.ico
UninstallDisplayIcon={app}\smooth-svg.exe
OutputDir=..\dist
OutputBaseFilename=smooth-svg-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
; Unchecked by default.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\smooth-svg\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "THIRD-PARTY.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\smooth-svg"; Filename: "{app}\smooth-svg.exe"; IconFilename: "{app}\smooth-svg.exe"
Name: "{autodesktop}\smooth-svg"; Filename: "{app}\smooth-svg.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\smooth-svg.exe"; Description: "{cm:LaunchProgram,smooth-svg}"; Flags: nowait postinstall skipifsilent

[Code]
function WebView2Installed(): Boolean;
var
  V: String;
begin
  // Evergreen runtime client GUID; per-machine (WOW6432Node) or per-user.
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) and (V <> '') and (V <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', V) and (V <> '') and (V <> '0.0.0.0'));
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  // Warn only: the app falls back to the browser when WebView2 is missing.
  if not WebView2Installed() and not WizardSilent() then
    MsgBox('Microsoft Edge WebView2 Runtime was not found. smooth-svg will open in your browser instead of its own window. To get the window, install it from https://go.microsoft.com/fwlink/p/?LinkId=2124703' + #13#10#13#10 +
           'O WebView2 Runtime n' + #227 + 'o foi encontrado. O smooth-svg abrir' + #225 + ' no navegador em vez de janela pr' + #243 + 'pria. Para ter a janela, instale em https://go.microsoft.com/fwlink/p/?LinkId=2124703',
           mbInformation, MB_OK);
end;

