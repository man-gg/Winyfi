; Inno Setup Script for Winyfi Network Monitor
; Compile this with Inno Setup 6 to create a Windows installer
; Command: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

[Setup]
AppName=Winyfi Network Monitor
AppVersion=1.0.0
AppPublisher=Winyfi Project
AppPublisherURL=https://github.com/man-gg/Winyfi
AppSupportURL=https://github.com/man-gg/Winyfi/issues
AppUpdatesURL=https://github.com/man-gg/Winyfi
DefaultDirName={autopf}\Winyfi
DefaultGroupName=Winyfi
OutputDir=installer_output
OutputBaseFilename=Winyfi_Setup_v1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\Winyfi.exe
WizardStyle=modern
LicenseFile=TERMS_AND_CONDITIONS.txt
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
AllowNoIcons=yes
ShowLanguageDialog=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenu"; Description: "Create Start Menu folder"; GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunch"; Description: "Create Quick Launch icon"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable
Source: "dist\Winyfi.exe"; DestDir: "{app}"; Flags: ignoreversion

; Configuration and documentation
Source: "dist\db_config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\winyfi.sql"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\README_SETUP.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\check_database.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\check_mysql_before_launch.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "TERMS_AND_CONDITIONS.txt"; DestDir: "{app}"; Flags: ignoreversion

; Application resources and assets
Source: "dist\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\routerLocImg\*"; DestDir: "{app}\routerLocImg"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\migrations\*"; DestDir: "{app}\migrations"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; Create logs directory for application logs
Name: "{app}\logs"; Permissions: users-full

[Icons]
Name: "{group}\Winyfi Network Monitor"; Filename: "{app}\Winyfi.exe"; IconFilename: "{app}\icon.ico"; Comment: "Launch Winyfi Dashboard"
Name: "{group}\README - Setup Instructions"; Filename: "{app}\README_SETUP.txt"; Comment: "Installation instructions"
Name: "{group}\Database Schema"; Filename: "{app}\winyfi.sql"; Comment: "Database schema file"
Name: "{group}\{cm:UninstallProgram,Winyfi}"; Filename: "{uninstallexe}"; Comment: "Uninstall Winyfi"
Name: "{autodesktop}\Winyfi"; Filename: "{app}\Winyfi.exe"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon; Comment: "Winyfi Network Monitor"
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\Winyfi"; Filename: "{app}\Winyfi.exe"; Tasks: quicklaunch; Comment: "Winyfi"

[Run]
Filename: "{app}\Winyfi.exe"; Description: "{cm:LaunchProgram,Winyfi Network Monitor}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ErrorLogPath: String;

procedure LogInstallerError(ErrorMsg: String);
var
  LogFile: String;
  Timestamp: String;
begin
  try
    LogFile := ExpandConstant('{app}') + '\installer_error.log';
    Timestamp := GetDateTimeString('yyyy-mm-dd hh:nn:ss', #0, #0);
    SaveStringToFile(LogFile, '[' + Timestamp + '] ' + ErrorMsg + #13#10, True);
  except
    // Silently fail if we can't write log
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    ErrorLogPath := ExpandConstant('{app}') + '\mysql_connection_error.log';
    LogInstallerError('Installation completed successfully');
    LogInstallerError('Application path: ' + ExpandConstant('{app}'));
    LogInstallerError('Error logs will be saved to: ' + ErrorLogPath);
    
    MsgBox(
      'Installation Complete!' + #13#10 + #13#10 +
      'IMPORTANT: Before launching Winyfi, please:' + #13#10 + #13#10 +
      '1. Install XAMPP from: https://www.apachefriends.org/' + #13#10 +
      '2. Start MySQL service in XAMPP Control Panel' + #13#10 +
      '3. Open phpMyAdmin (http://localhost/phpmyadmin)' + #13#10 +
      '4. Create a new database named: winyfi' + #13#10 +
      '5. Import the winyfi.sql file:' + #13#10 +
      '   - Located in: ' + ExpandConstant('{app}') + '\winyfi.sql' + #13#10 + #13#10 +
      'TROUBLESHOOTING:' + #13#10 +
      'Error logs are created in the application directory:' + #13#10 +
      '  - ' + ExpandConstant('{app}') + '\mysql_connection_error.log' + #13#10 +
      '  - ' + ExpandConstant('{app}') + '\mysql_check_error.log' + #13#10 +
      '  - ' + ExpandConstant('{app}') + '\winyfi_error.log' + #13#10 +
      '  - ' + ExpandConstant('{app}') + '\winyfi_runtime_error.log' + #13#10 +
      '  - ' + ExpandConstant('{app}') + '\logs\ (service logs for Flask API & UniFi API)' + #13#10 + #13#10 +
      'If services fail to start, check the logs/ folder for:' + #13#10 +
      '  - flask-api.log (Flask API logs)' + #13#10 +
      '  - unifi-api.log (UniFi API logs)' + #13#10 +
      '  - flask-api-error.log, unifi-api-error.log (error details)' + #13#10 + #13#10 +
      'For detailed setup instructions, see: README_SETUP.txt' + #13#10 + #13#10 +
      'For help: https://github.com/man-gg/Winyfi/issues',
      mbInformation, MB_OK
    );
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  { Check for required files before installation }
  Result := '';
end;
